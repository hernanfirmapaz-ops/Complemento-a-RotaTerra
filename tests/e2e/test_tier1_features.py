"""Tier 1 — Isolated Feature Coverage (55 tests across F1–F10).

Strict opaque-box tests exercising FastAPI /api/v1 routes, public sample data,
mocked network boundaries, and Pydantic <-> TypeScript contract parity.
"""

from __future__ import annotations

import ast
import json
import math
import re
import time
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.e2e.conftest import MockNetworkController
from tests.e2e.fixtures import (
    REPO_ROOT,
    SAMPLE_DIR,
    UTM20S_ESRI_WKT,
    make_early_peak_csv_bytes,
    make_kml_bytes,
    make_kmz_bytes,
    make_late_peak_csv_bytes,
    make_shapefile_zip_bytes,
    synthetic_square_field_geojson,
    synthetic_square_ring,
    write_ridge_berm_dem,
    write_sloped_plane_dem,
    write_sloped_with_micro_depression_dem,
)


def _import_square(client: TestClient, d_deg: float = 0.01, name: str = "Lote Prueba") -> dict:
    gj = json.dumps(synthetic_square_field_geojson(d_deg=d_deg, name=name)).encode("utf-8")
    r = client.post(
        "/api/v1/fields/import",
        files={"file": ("lote.geojson", gj, "application/geo+json")},
        data={"default_name": name},
    )
    assert r.status_code == 201, r.text
    return r.json()["fields"][0]


def _upload_dem(client: TestClient, field_id: str, dem_path: Path, buffer_m: float = 200.0) -> dict:
    with dem_path.open("rb") as fh:
        r = client.post(
            f"/api/v1/fields/{field_id}/terrain/process",
            files={"file": (dem_path.name, fh, "image/tiff")},
            data={
                "source_id": "upload",
                "buffer_m": str(buffer_m),
                "source_name": "DEM Sintético E2E",
                "surface_type": "DTM",
                "vertical_datum": "SRVN16",
                "vertical_accuracy_m": "0.1",
                "acquisition_date": "2026-01-10",
                "acquisition_method": "Levantamiento sintético",
            },
        )
    assert r.status_code == 200, r.text
    return r.json()


# ===========================================================================
# F1: Farm & Multi-Format Boundary Import, Validation & UTM Reprojection
# ===========================================================================


def test_e2e_t1_f1_01_import_geojson_parcela_205(api_client: TestClient):
    raw = (SAMPLE_DIR / "san_luis_parcela_205.geojson").read_bytes()
    r = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("san_luis_parcela_205.geojson", raw, "application/geo+json")},
        data={"default_name": "Parcela 205"},
    )
    assert r.status_code == 201, r.text
    fields = r.json()["fields"]
    assert len(fields) == 1
    f = fields[0]
    assert f["utm_epsg"] == 32720
    assert 195.0 <= f["area_ha"] <= 205.0
    assert f["declared_area_ha"] == pytest.approx(199.342, abs=0.05)
    assert f["has_terrain"] is False
    assert f["has_hydrology"] is False

    r_get = api_client.get(f"/api/v1/fields/{f['id']}")
    assert r_get.status_code == 200
    assert r_get.json()["geometry"] == f["geometry"]
    assert r_get.json()["area_ha"] == f["area_ha"]


def test_e2e_t1_f1_02_import_kml(api_client: TestClient):
    kml = make_kml_bytes(name="Lote KML San Luis")
    r = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("parcela.kml", kml, "application/vnd.google-earth.kml+xml")},
        data={"default_name": "Fallback"},
    )
    assert r.status_code == 201, r.text
    f = r.json()["fields"][0]
    assert f["area_ha"] > 50.0
    assert f["utm_epsg"] == 32720
    assert f["name"] == "Lote KML San Luis"
    assert any(item["id"] == f["id"] for item in api_client.get("/api/v1/fields").json())


def test_e2e_t1_f1_03_import_kmz_multipolygon(api_client: TestClient):
    kmz = make_kmz_bytes(name="Lote KMZ Multi", multipolygon=True)
    r = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("parcela.kmz", kmz, "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 201, r.text
    f = r.json()["fields"][0]
    assert f["geometry"]["type"] == "MultiPolygon"
    assert len(f["geometry"]["coordinates"]) == 2
    assert 120.0 <= f["area_ha"] <= 150.0


def test_e2e_t1_f1_04_import_shapefile_zip_prj_dbf(api_client: TestClient):
    # UTM Zone 20S square (~100 ha) matching synthetic_square_field_geojson region
    utm_ring = [
        [248_500.0, 6_312_000.0],
        [249_500.0, 6_312_000.0],
        [249_500.0, 6_313_000.0],
        [248_500.0, 6_313_000.0],
        [248_500.0, 6_312_000.0],
    ]
    shp_zip = make_shapefile_zip_bytes(
        rings=[utm_ring],
        prj_wkt=UTM20S_ESRI_WKT,
        dbf_name="Parcela SHP Catastral",
    )
    r = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("parcela_utm20s.zip", shp_zip, "application/zip")},
        data={"default_name": "Default"},
    )
    assert r.status_code == 201, r.text
    f = r.json()["fields"][0]
    assert f["utm_epsg"] == 32720
    assert -65.72 <= f["centroid"][0] <= -65.68
    assert -33.32 <= f["centroid"][1] <= -33.28
    assert f["name"] == "Parcela SHP Catastral"
    assert f["area_ha"] == pytest.approx(100.0, abs=1.5)


@pytest.mark.parametrize(
    ("preset", "expected_epsg", "expected_min_ha", "expected_max_ha"),
    [
        ("llanura", 32720, 195.0, 205.0),
        ("serrano", 32719, 218.0, 232.0),
    ],
)
def test_e2e_t1_f1_05_sample_presets_idempotent(
    api_client: TestClient,
    preset: str,
    expected_epsg: int,
    expected_min_ha: float,
    expected_max_ha: float,
):
    r1 = api_client.post(f"/api/v1/fields/sample?preset={preset}")
    assert r1.status_code == 201, r1.text
    f1 = r1.json()["fields"][0]
    assert f1["utm_epsg"] == expected_epsg
    assert expected_min_ha <= f1["area_ha"] <= expected_max_ha

    r2 = api_client.post(f"/api/v1/fields/sample?preset={preset}")
    assert r2.status_code == 201
    assert r2.json()["fields"][0]["id"] == f1["id"]


# ===========================================================================
# F2: DEM Acquisition, Conditioning, Quality Report & 30m Scale Warnings
# ===========================================================================


def test_e2e_t1_f2_01_upload_10m_dem_metadata(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    dem_path = write_sloped_plane_dem(tmp_path / "dem_10m.tif", pixel_m=10.0, width=220, height=220)
    with dem_path.open("rb") as fh:
        r = api_client.post(
            f"/api/v1/fields/{f['id']}/terrain/process",
            files={"file": ("dem_10m.tif", fh, "image/tiff")},
            data={
                "source_id": "upload",
                "buffer_m": "100",
                "source_name": "Dron RTK 10m",
                "surface_type": "DTM",
                "vertical_datum": "EGM2008",
                "vertical_accuracy_m": "0.15",
                "acquisition_date": "2026-02-01",
                "acquisition_method": "Fotogrametría RTK",
            },
        )
    assert r.status_code == 200, r.text
    terr = r.json()
    assert terr["source"]["surface_type"] == "DTM"
    assert terr["source"]["vertical_datum"] == "EGM2008"
    assert terr["source"]["vertical_accuracy_m"] == 0.15
    assert terr["source"]["acquisition_method"] == "Fotogrametría RTK"
    assert terr["quality"]["pixel_size_m"] >= 10.0
    assert terr["quality"]["nodata_pct_field"] == 0.0
    assert api_client.get(f"/api/v1/fields/{f['id']}/terrain").status_code == 200


def test_e2e_t1_f2_02_copernicus_glo30_mocked(api_client: TestClient):
    r_samp = api_client.post("/api/v1/fields/sample?preset=llanura")
    fid = r_samp.json()["fields"][0]["id"]
    r = api_client.post(
        f"/api/v1/fields/{fid}/terrain/process",
        data={"source_id": "copernicus_glo30", "buffer_m": "300"},
    )
    assert r.status_code == 200, r.text
    terr = r.json()
    assert terr["source"]["source_id"] == "copernicus_glo30"
    assert "EGM2008" in (terr["source"]["vertical_datum"] or "")
    assert terr["source"]["acquisition_start"] == "2011-01-15"
    assert terr["source"]["acquisition_end"] == "2014-12-20"
    assert terr["quality"]["buffer_m"] == 300.0
    assert any("30 m" in lim or "Copernicus" in lim for lim in terr["limitations"]) or any(
        w["code"] == "sin_microrelieve" for w in terr["quality"]["warnings"]
    )


def test_e2e_t1_f2_03_small_field_30m_scale_warning(api_client: TestClient):
    f = _import_square(api_client, d_deg=0.005, name="Lote Chico 25 ha")
    r = api_client.post(
        f"/api/v1/fields/{f['id']}/terrain/process",
        data={"source_id": "copernicus_glo30", "buffer_m": "200"},
    )
    assert r.status_code == 200, r.text
    q = r.json()["quality"]
    assert q["cells_in_field"] < 400
    assert any(
        w["code"] in ("resolucion_baja", "resolucion_insuficiente", "sin_microrelieve")
        and w["level"] in ("advertencia", "critico")
        for w in q["warnings"]
    )
    elev = q["elevation_field"]
    assert elev["min"] <= elev["mean"] <= elev["max"]


def test_e2e_t1_f2_04_buffer_and_immutable_source(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    dem_path = write_sloped_plane_dem(tmp_path / "dem_20m.tif", pixel_m=20.0, width=110, height=110)
    _upload_dem(api_client, f["id"], dem_path, buffer_m=300.0)
    r = api_client.get(f"/api/v1/fields/{f['id']}/terrain")
    assert r.status_code == 200
    terr = r.json()
    assert terr["quality"]["cells_in_area"] > terr["quality"]["cells_in_field"]
    assert terr["quality"]["field_area_ha"] == pytest.approx(f["area_ha"], rel=0.02)
    assert terr["files"]["original"].startswith("source/")
    assert terr["files"]["working_dem"] == "dem_utm.tif"


def test_e2e_t1_f2_05_reprocess_dem_updates_quality(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    t1 = _upload_dem(api_client, f["id"], write_sloped_plane_dem(tmp_path / "d20.tif", pixel_m=20.0, width=110, height=110))
    t2 = _upload_dem(api_client, f["id"], write_sloped_plane_dem(tmp_path / "d10.tif", pixel_m=10.0, width=220, height=220))
    assert t1["quality"]["pixel_size_m"] == 20.0
    assert t2["quality"]["pixel_size_m"] == 10.0
    assert t2["quality"]["cells_in_field"] > t1["quality"]["cells_in_field"] * 3


# ===========================================================================
# F3: Point Inspection, Elevation Profile, Contours & 3D Mesh
# ===========================================================================


def test_e2e_t1_f3_01_point_analytic_slope(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    _upload_dem(
        api_client,
        f["id"],
        write_sloped_plane_dem(tmp_path / "slope10.tif", pixel_m=10.0, width=220, height=220, slope_east=0.03, slope_south=0.04),
    )
    lon, lat = f["centroid"]
    r = api_client.get(f"/api/v1/fields/{f['id']}/terrain/point", params={"lon": lon, "lat": lat})
    assert r.status_code == 200, r.text
    pt = r.json()
    assert pt["inside_dem"] is True
    assert pt["inside_field"] is True
    assert pt["elevation_m"] is not None
    assert pt["slope_pct"] == pytest.approx(5.0, abs=0.2)
    assert pt["slope_deg"] == pytest.approx(math.degrees(math.atan(0.05)), abs=0.2)
    assert 0.0 <= pt["aspect_deg"] < 360.0


def test_e2e_t1_f3_02_profile_two_point_transect(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    r = api_client.post(
        f"/api/v1/fields/{fid}/terrain/profile",
        json={"coordinates": [[-65.699, -33.299], [-65.691, -33.291]]},
    )
    assert r.status_code == 200, r.text
    prof = r.json()
    s = prof["summary"]
    assert s["length_m"] > 500.0
    assert s["samples"] >= 2
    assert prof["samples"][0]["distance_m"] == 0.0
    dists = [pt["distance_m"] for pt in prof["samples"]]
    assert all(b > a for a, b in zip(dists, dists[1:]))
    assert s["range_m"] == pytest.approx(s["max_m"] - s["min_m"], abs=0.05)


def test_e2e_t1_f3_03_profile_multipoint_custom_step(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    coords = [[-65.699, -33.299], [-65.695, -33.296], [-65.691, -33.291]]
    r = api_client.post(
        f"/api/v1/fields/{fid}/terrain/profile",
        json={"coordinates": coords, "step_m": 10.0},
    )
    assert r.status_code == 200, r.text
    prof = r.json()
    assert len(prof["vertices_distance_m"]) == 3
    assert prof["vertices_distance_m"][-1] == pytest.approx(prof["summary"]["length_m"], abs=0.5)
    assert prof["summary"]["step_m"] <= 10.0


def test_e2e_t1_f3_04_contours_marching_squares(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    r = api_client.get(f"/api/v1/fields/{fid}/terrain/contours?interval_m=5.0")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["type"] == "FeatureCollection"
    assert data["interval_m"] == 5.0
    assert len(data["features"]) > 0
    for feat in data["features"]:
        assert feat["geometry"]["type"] in ("LineString", "MultiLineString")
        elev = feat["properties"]["elevation_m"]
        assert elev % 5.0 == pytest.approx(0.0, abs=1e-5)


def test_e2e_t1_f3_05_mesh_decimation(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    r = api_client.get(f"/api/v1/fields/{fid}/terrain/mesh?max_size=64")
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["rows"] <= 64 and m["cols"] <= 64
    n = m["rows"] * m["cols"]
    assert len(m["lon"]) == n
    assert len(m["lat"]) == n
    assert len(m["z"]) == n
    assert len(m["in_field"]) == n
    assert len(m["boundary"]) >= 1
    assert m["z_min"] <= m["z_max"]


# ===========================================================================
# F4: Static Hydrology & Phase 5 Zonation / Trafficability
# ===========================================================================


def test_e2e_t1_f4_01_static_hydrology_fill_small(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    _upload_dem(api_client, f["id"], write_sloped_with_micro_depression_dem(tmp_path / "dep.tif"))
    r = api_client.post(
        f"/api/v1/fields/{f['id']}/hydrology/static",
        json={"conditioning_mode": "fill_small"},
    )
    assert r.status_code == 200, r.text
    h = r.json()
    assert h["summary"]["mfd_mass_balance_error"] <= 1e-4
    assert h["summary"]["max_mfd_area_in_field_ha"] > 0.0
    assert h["summary"]["outlets_count"] >= 1
    assert len(h["drainage_network"]["features"]) >= 1
    assert api_client.get(f"/api/v1/fields/{f['id']}/hydrology").status_code == 200


def test_e2e_t1_f4_02_conditioning_preserve_vs_fill_all(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    _upload_dem(api_client, f["id"], write_sloped_with_micro_depression_dem(tmp_path / "dep2.tif"))
    r_pres = api_client.post(f"/api/v1/fields/{f['id']}/hydrology/static", json={"conditioning_mode": "preserve"})
    r_fill = api_client.post(f"/api/v1/fields/{f['id']}/hydrology/static", json={"conditioning_mode": "fill_all"})
    assert r_pres.status_code == 200 and r_fill.status_code == 200
    pres = r_pres.json()
    fill = r_fill.json()
    assert pres["summary"]["depressions_filled_count"] == 0
    assert pres["summary"]["total_depression_volume_in_field_m3"] > 0.0
    assert fill["summary"]["depressions_filled_count"] >= pres["summary"]["depressions_filled_count"]
    assert fill["summary"]["depressions_filled_count"] >= 1


@pytest.mark.parametrize("basis", ["MFD", "D8"])
def test_e2e_t1_f4_03_routing_basis_and_threshold(field_with_sloped_dem: tuple[str, dict], api_client: TestClient, basis: str):
    fid, _ = field_with_sloped_dem
    r_lo = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/static",
        json={"routing_basis": basis, "stream_threshold_ha": 0.5},
    )
    r_hi = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/static",
        json={"routing_basis": basis, "stream_threshold_ha": 10.0},
    )
    assert r_lo.status_code == 200 and r_hi.status_code == 200
    lo, hi = r_lo.json(), r_hi.json()
    assert lo["drainage_network"]["basis"] == basis
    assert lo["summary"]["stream_segments_count"] >= hi["summary"]["stream_segments_count"]
    assert lo["summary"]["total_stream_length_m"] >= hi["summary"]["total_stream_length_m"]


def test_e2e_t1_f4_04_burn_lines_channels_flow(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    _upload_dem(api_client, f["id"], write_ridge_berm_dem(tmp_path / "berm.tif"))
    r_base = api_client.post(f"/api/v1/fields/{f['id']}/hydrology/static", json={"conditioning_mode": "preserve"})
    burn = [[[-65.695, -33.293], [-65.695, -33.299]]]
    r_burn = api_client.post(
        f"/api/v1/fields/{f['id']}/hydrology/static",
        json={"conditioning_mode": "preserve", "burn_lines": burn, "burn_depth_m": 1.5},
    )
    assert r_base.status_code == 200 and r_burn.status_code == 200
    b = r_burn.json()
    assert b["parameters"]["burn_lines_count"] == 1
    assert b["parameters"]["burn_depth_m"] == 1.5
    # Original terrain elevation stats remain untouched
    terr = api_client.get(f"/api/v1/fields/{f['id']}/terrain").json()
    assert terr["files"]["original"].startswith("source/")


def test_e2e_t1_f4_05_agronomic_zonation_and_trafficability(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    r = api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={})
    assert r.status_code == 200
    az = r.json()["agronomic_zonation"]
    codes = {z["code"] for z in az["zones"]}
    assert codes == {
        "loma_bien_drenada",
        "media_loma_transito",
        "via_escurrimiento_concentrado",
        "bajo_acumulacion_anegable",
    }
    assert sum(z["percentage_of_field"] for z in az["zones"]) == pytest.approx(100.0, abs=0.5)
    traf = az["trafficability"]
    assert traf["estimated_wait_days_low_ground"] >= traf["estimated_wait_days_high_ground"]
    assert len(az["rotaterra_criteria"]) >= 1


# ===========================================================================
# F5: Rainfall Events, CSV Validation, NRCS-CN Runoff & Scenario Comparison
# ===========================================================================


def test_e2e_t1_f5_01_manual_rainfall_provenance(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    r = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events",
        json={"name": "Tormenta Diseño 80 mm", "total_mm": 80.0, "source_type": "manual"},
    )
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["has_time_series"] is False
    required_keys = {
        "source", "source_product", "spatial_resolution", "temporal_resolution",
        "valid_time_start", "valid_time_end", "downloaded_at", "units",
        "quality_flag", "uncertainty_note",
    }
    assert required_keys.issubset(ev["source_metadata"].keys())
    assert any("temporal" in w.lower() or "acumulada" in w.lower() for w in ev["warnings"])


def test_e2e_t1_f5_02_import_csv_evento_tormenta(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    csv_bytes = (SAMPLE_DIR / "evento_tormenta_pluvio.csv").read_bytes()
    r = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events/import-csv",
        files={"file": ("evento_tormenta_pluvio.csv", csv_bytes, "text/csv")},
        data={"name": "Tormenta San Luis", "source_type": "gauge"},
    )
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["has_time_series"] is True
    assert len(ev["intervals"]) == 8
    assert ev["total_mm"] == pytest.approx(80.0, abs=0.01)
    assert ev["interval_minutes"] == 15
    assert ev["max_intensity_mm_h"] == pytest.approx(84.0, abs=0.1)
    listed = api_client.get(f"/api/v1/fields/{fid}/hydrology/rainfall-events").json()
    assert any(item["id"] == ev["id"] for item in listed)


def test_e2e_t1_f5_03_runoff_nrcs_cn_mass_balance(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    ev = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events",
        json={"name": "Tormenta 80", "total_mm": 80.0, "source_type": "manual"},
    ).json()
    r = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={
            "rainfall_event_id": ev["id"],
            "soil_group": "B",
            "cover_code": "soja_maiz_sd_buena",
            "antecedent_moisture": "medium",
            "lambda_ratio": 0.2,
        },
    )
    assert r.status_code == 201, r.text
    run = r.json()
    cn = run["cn_result"]
    assert cn["mass_balance_error_mm"] <= 1e-3
    assert cn["precipitation_mm"] == pytest.approx(
        cn["initial_abstraction_ia_mm"] + cn["infiltration_after_ia_f_mm"] + cn["runoff_q_mm"],
        abs=0.05,
    )
    assert 0.0 <= cn["runoff_q_mm"] <= 80.0
    assert cn["runoff_coefficient"] == pytest.approx(cn["runoff_q_mm"] / 80.0, abs=1e-3)
    assert any("profundidad" in lim.lower() or "flood" in lim.lower() for lim in run["limitations"])


def test_e2e_t1_f5_04_amc_ordering_and_compare(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    ev = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events",
        json={"name": "Tormenta 80", "total_mm": 80.0, "source_type": "manual"},
    ).json()
    run_dry = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "antecedent_moisture": "dry"},
    ).json()
    run_med = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "antecedent_moisture": "medium"},
    ).json()
    run_wet = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "antecedent_moisture": "wet"},
    ).json()
    run_comp = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "antecedent_moisture": "medium", "compaction_high": True},
    ).json()

    assert run_wet["cn_result"]["cn_effective"] > run_med["cn_result"]["cn_effective"] > run_dry["cn_result"]["cn_effective"]
    assert run_wet["cn_result"]["runoff_q_mm"] > run_dry["cn_result"]["runoff_q_mm"]
    assert run_comp["cn_result"]["cn_effective"] >= run_med["cn_result"]["cn_effective"]

    cmp_r = api_client.get(
        f"/api/v1/fields/{fid}/hydrology/compare",
        params={"run_a": run_dry["id"], "run_b": run_wet["id"]},
    )
    assert cmp_r.status_code == 200
    assert cmp_r.json()["delta_runoff_q_mm"] > 0.0


def test_e2e_t1_f5_05_activate_run_updates_mesh(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    ev = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events",
        json={"name": "Tormenta 80", "total_mm": 80.0, "source_type": "manual"},
    ).json()
    run_a = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "antecedent_moisture": "dry"},
    ).json()
    run_b = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "antecedent_moisture": "wet"},
    ).json()
    assert run_b["is_active"] is True

    r_act = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run_a['id']}/activate")
    assert r_act.status_code == 200
    assert r_act.json()["is_active"] is True
    runs = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs").json()
    assert [r["id"] for r in runs if r["is_active"]] == [run_a["id"]]

    mesh = api_client.get(f"/api/v1/fields/{fid}/terrain/mesh?max_size=48").json()
    assert mesh["runoff_load_mm"] is not None
    assert mesh["cumulative_runoff_m3"] is not None


# ===========================================================================
# F6: Simplified Temporal Routing, Timeline & Mass Balance
# ===========================================================================


def _setup_csv_run(client: TestClient, fid: str, csv_bytes: bytes | None = None) -> dict:
    if csv_bytes is None:
        ev = client.post(f"/api/v1/fields/{fid}/hydrology/rainfall-events/sample").json()
    else:
        ev = client.post(
            f"/api/v1/fields/{fid}/hydrology/rainfall-events/import-csv",
            files={"file": ("storm.csv", csv_bytes, "text/csv")},
            data={"name": "Storm CSV", "source_type": "gauge"},
        ).json()
    return client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "soil_group": "B", "antecedent_moisture": "medium"},
    ).json()


def test_e2e_t1_f6_01_timeline_csv_hyetograph_steps(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    run = _setup_csv_run(api_client, fid)
    r = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/timeline")
    assert r.status_code == 200, r.text
    tl = r.json()
    assert tl["has_time_series"] is True
    assert tl["rainfall_steps"] == 8
    assert tl["recession_steps"] >= 1
    assert tl["total_steps"] == tl["rainfall_steps"] + tl["recession_steps"]
    assert tl["max_mass_balance_error_mm"] <= 1e-3


def test_e2e_t1_f6_02_timeline_frames_recession_and_transit(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    run = _setup_csv_run(api_client, fid)
    tl = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/timeline").json()
    frames = tl["frames"]
    cum_p = [fr["cumulative_precipitation_mm"] for fr in frames]
    assert all(b >= a for a, b in zip(cum_p, cum_p[1:]))
    assert cum_p[-1] == pytest.approx(80.0, abs=0.05)
    assert all(0.0 <= fr["transit_fraction_of_peak"] <= 1.0 + 1e-6 for fr in frames)
    peak_fr = frames[tl["peak_step_index"]]
    assert peak_fr["active_transit_lamina_mm"] == pytest.approx(tl["peak_transit_lamina_mm"], abs=1e-2)
    rec = [fr for fr in frames if fr["is_recession"]]
    assert all(fr["interval_precipitation_mm"] == 0.0 for fr in rec)
    assert rec[-1]["active_transit_lamina_mm"] <= rec[0]["active_transit_lamina_mm"] + 1e-6


def test_e2e_t1_f6_03_timeline_particle_paths_downslope(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    run = _setup_csv_run(api_client, fid)
    tl = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/timeline").json()
    paths = tl["particle_paths"]
    assert len(paths) >= 1
    for path in paths:
        assert len(path) >= 2
        for lon, lat, z in path:
            assert -66.0 <= lon <= -65.0
            assert -34.0 <= lat <= -33.0
            assert z > 0.0
        assert path[0][2] >= path[-1][2] - 0.05


def test_e2e_t1_f6_04_early_vs_late_peak_shift(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    run_early = _setup_csv_run(api_client, fid, make_early_peak_csv_bytes())
    run_late = _setup_csv_run(api_client, fid, make_late_peak_csv_bytes())
    tl_early = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run_early['id']}/timeline").json()
    tl_late = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run_late['id']}/timeline").json()
    assert tl_late["peak_step_index"] > tl_early["peak_step_index"]


def test_e2e_t1_f6_05_timeline_epistemic_boundaries(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    run = _setup_csv_run(api_client, fid)
    tl = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/timeline").json()
    assert any("reservorio" in lim.lower() or "saint-venant" in lim.lower() for lim in tl["limitations"])
    for fr in tl["frames"]:
        assert "active_transit_lamina_mm" in fr
        assert "depression_retained_mm" in fr
        assert "velocity_m_s" not in fr


# ===========================================================================
# F7: 2D Shallow Water Hydrodynamics & Field Observations / Calibration
# ===========================================================================


def test_e2e_t1_f7_01_simulate_2d_diffusive_wave(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    run = _setup_csv_run(api_client, fid)
    r = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/simulate-2d",
        json={"ponding_threshold_m": 0.05, "recession_minutes": 30},
    )
    assert r.status_code == 200, r.text
    s2d = r.json()["hydrodynamic_2d_summary"]
    assert s2d["max_water_depth_in_field_m"] >= 0.0
    assert s2d["max_velocity_in_field_m_s"] >= 0.0
    assert s2d["max_unit_discharge_in_field_m2_s"] >= 0.0
    assert s2d["mass_balance_relative_error"] <= 0.02


def test_e2e_t1_f7_02_post_2d_mesh_and_point_sync(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, field = field_with_sloped_dem
    run = _setup_csv_run(api_client, fid)
    api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/simulate-2d", json={}).raise_for_status()
    mesh = api_client.get(f"/api/v1/fields/{fid}/terrain/mesh?max_size=48").json()
    assert mesh["water_depth_m"] is not None
    assert mesh["velocity_m_s"] is not None
    lon, lat = field["centroid"]
    pt = api_client.get(f"/api/v1/fields/{fid}/terrain/point", params={"lon": lon, "lat": lat}).json()
    assert pt["water_depth_m"] is not None and pt["water_depth_m"] >= 0.0
    assert pt["velocity_m_s"] is not None and pt["velocity_m_s"] >= 0.0
    assert pt["agronomic_zone_id"] in (1, 2, 3, 4)


def test_e2e_t1_f7_03_observations_all_6_types(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, field = field_with_sloped_dem
    lon, lat = field["centroid"]
    types = ["ponding", "erosion", "culvert", "channel", "terrace", "water_depth"]
    for i, ot in enumerate(types):
        r = api_client.post(
            f"/api/v1/fields/{fid}/hydrology/observations",
            json={
                "observation_type": ot,
                "lon": lon + i * 0.0002,
                "lat": lat,
                "notes": f"Observación {ot}",
                "value": 0.35,
                "units": "m",
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["elevation_m"] is not None
    listed = api_client.get(f"/api/v1/fields/{fid}/hydrology/observations").json()
    assert {o["observation_type"] for o in listed} == set(types)


def test_e2e_t1_f7_04_culvert_and_channel_structures_applied(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, field = field_with_sloped_dem
    lon, lat = field["centroid"]
    for ot, dx in (("culvert", 0.0), ("channel", 0.0005)):
        api_client.post(
            f"/api/v1/fields/{fid}/hydrology/observations",
            json={"observation_type": ot, "lon": lon + dx, "lat": lat, "notes": f"Obra {ot}", "value": 0.5, "units": "m"},
        ).raise_for_status()
    run = _setup_csv_run(api_client, fid)
    s2d = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/simulate-2d",
        json={},
    ).json()["hydrodynamic_2d_summary"]
    assert s2d["hydraulic_structures_applied"] >= 2


def test_e2e_t1_f7_05_delete_observation(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, field = field_with_sloped_dem
    lon, lat = field["centroid"]
    obs = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/observations",
        json={"observation_type": "ponding", "lon": lon, "lat": lat, "notes": "Borrar esta obs"},
    ).json()
    r_del = api_client.delete(f"/api/v1/fields/{fid}/hydrology/observations/{obs['id']}")
    assert r_del.status_code == 204
    listed = api_client.get(f"/api/v1/fields/{fid}/hydrology/observations").json()
    assert all(item["id"] != obs["id"] for item in listed)


# ===========================================================================
# F8: Agronomic Toolkit (All 8 Tools)
# ===========================================================================


def test_e2e_t1_f8_01_toolkit_all_8_tools_and_get(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    r = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={})
    assert r.status_code == 200, r.text
    tk = r.json()
    expected_tools = {
        "erosion_usle",
        "water_balance_monthly",
        "real_waterlogging_by_date",
        "contour_terraces",
        "seeding_calculator_inta",
        "rotation_comparator_3yr",
        "ndvi_vigor_monitor",
        "frost_risk_sowing",
    }
    assert expected_tools.issubset(tk.keys())
    r_get = api_client.get(f"/api/v1/fields/{fid}/hydrology/toolkit")
    assert r_get.status_code == 200
    assert r_get.json() == tk


def test_e2e_t1_f8_02_usle_and_terraces_reduction(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    tk = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/toolkit/run",
        json={"storm_precipitation_mm": 80.0, "soil_group": "B"},
    ).json()
    assert tk["erosion_usle"]["mean_soil_loss_t_ha"] >= 0.0
    ter = tk["contour_terraces"]
    assert ter["runoff_after_mm"] <= ter["runoff_before_mm"]
    assert ter["soil_loss_after_t_ha"] <= ter["soil_loss_before_t_ha"]
    assert ter["terraces_geojson"]["type"] == "FeatureCollection"


@pytest.mark.parametrize("crop_code", ["maiz_temprano", "soja_primera", "trigo"])
def test_e2e_t1_f8_03_seeding_inta_crops(
    field_with_sloped_dem: tuple[str, dict],
    api_client: TestClient,
    crop_code: str,
):
    fid, field = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    tk = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/toolkit/run",
        json={"crop_code": crop_code, "environment_zone": "loma"},
    ).json()
    sc = tk["seeding_calculator_inta"]
    assert sc["seeds_to_sow_ha"] >= sc["target_plants_ha"]
    assert sc["total_seed_kg_for_field"] == pytest.approx(sc["seed_density_kg_ha"] * field["area_ha"], rel=0.05)
    assert all(v >= 0.0 for v in sc["nutrients_required_kg_ha"].values())
    assert all(v >= 0.0 for v in sc["commercial_fertilizer_guide_kg_ha"].values())


def test_e2e_t1_f8_04_rotation_comparator_3yr(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    tk = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).json()
    rot = tk["rotation_comparator_3yr"]
    assert rot["sequence_b"]["mean_cover_pct_3yr"] > rot["sequence_a"]["mean_cover_pct_3yr"]
    assert rot["sequence_b"]["mean_cn_3yr"] < rot["sequence_a"]["mean_cn_3yr"]
    assert rot["delta_b_vs_a"]["soil_saved_by_b_tons"] >= 0.0
    assert rot["delta_b_vs_a"]["runoff_saved_by_b_mm"] >= 0.0


def test_e2e_t1_f8_05_preserves_hydrology_processed_at(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    h_before = api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).json()
    # Sleep >1s so store.now_iso() (1s resolution) detects timestamp mutation bug if present
    time.sleep(1.1)
    api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).raise_for_status()
    h_after = api_client.get(f"/api/v1/fields/{fid}/hydrology").json()
    assert h_after["processed_at"] == h_before["processed_at"]
    mesh = api_client.get(f"/api/v1/fields/{fid}/terrain/mesh?max_size=48").json()
    assert mesh["soil_loss_t_ha"] is not None


# ===========================================================================
# F9: Earth Observation Provenance & Controlled Degraded Mode (R4)
# ===========================================================================


def test_e2e_t1_f9_01_nasa_power_provenance_and_dynamic_window(
    field_with_sloped_dem: tuple[str, dict],
    api_client: TestClient,
    mock_external_network: MockNetworkController,
):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    tk = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).json()

    wb = tk["water_balance_monthly"]
    wl = tk["real_waterlogging_by_date"]
    fr = tk["frost_risk_sowing"]
    assert "NASA POWER" in wb["source"]
    assert "NASA POWER" in wl["source"]
    assert "NASA POWER" in fr["source"]
    assert len(wb["months"]) == 12
    assert fr["mean_agronomic_frost_days_yr"] >= fr["mean_meteorological_frost_days_yr"]

    # Dynamic date.today() check on outbound NASA POWER query
    nasa_reqs = [u for _, u in mock_external_network.requests if "power.larc.nasa.gov" in u]
    assert nasa_reqs
    m = re.search(r"end=(\d{8})", nasa_reqs[-1])
    assert m is not None
    req_end = date(int(m.group(1)[:4]), int(m.group(1)[4:6]), int(m.group(1)[6:8]))
    assert date.today() - timedelta(days=7) <= req_end <= date.today()


def test_e2e_t1_f9_02_sentinel2_stac_ndvi_observed(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    tk = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).json()
    ndvi = tk["ndvi_vigor_monitor"]
    assert ndvi["is_satellite_observed"] is True
    assert "Sentinel-2" in ndvi["source"]
    assert ndvi["acquisition_date"] == "2026-01-15"
    assert -1.0 <= ndvi["mean_ndvi_in_field"] <= 1.0
    total_pct = ndvi["low_vigor_pct"] + ndvi["moderate_vigor_pct"] + ndvi["high_vigor_pct"]
    assert total_pct == pytest.approx(100.0, abs=0.5)
    mesh = api_client.get(f"/api/v1/fields/{fid}/terrain/mesh?max_size=48").json()
    assert mesh["ndvi"] is not None


def test_e2e_t1_f9_03_hargreaves_et0_austral_summer_gt_winter(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    tk = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).json()
    months = tk["water_balance_monthly"]["months"]
    summer_et0 = [m["et0_mm"] for m in months if m["month"] in (12, 1, 2)]
    winter_et0 = [m["et0_mm"] for m in months if m["month"] in (6, 7, 8)]
    assert summer_et0 and winter_et0
    assert sum(summer_et0) / len(summer_et0) > sum(winter_et0) / len(winter_et0)
    assert tk["water_balance_monthly"]["annual_et0_mm"] > 0.0


def test_e2e_t1_f9_04_hydrology_catalog_provenance(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    r = api_client.get(f"/api/v1/fields/{fid}/hydrology/catalog")
    assert r.status_code == 200
    cat = r.json()
    assert len(cat["covers"]) == 8
    assert {sg["code"] for sg in cat["soil_groups"]} == {"A", "B", "C", "D"}
    assert {a["code"] for a in cat["antecedent_moisture_options"]} == {"dry", "medium", "wet"}
    assert {rs["code"] for rs in cat["rainfall_sources"]} == {"gauge", "SMN", "IMERG", "CHIRPS", "ERA5-Land", "NASA_POWER", "manual"}
    for rs in cat["rainfall_sources"]:
        assert rs["spatial_resolution"] and rs["temporal_resolution"] and rs["uncertainty_note"]


def test_e2e_t1_f9_05_sentinel2_partial_cloud_scl_mask(
    field_with_sloped_dem: tuple[str, dict],
    api_client: TestClient,
    mock_external_network: MockNetworkController,
):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    mock_external_network.stac_mode = "partial_cloud"
    tk = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).json()
    ndvi = tk["ndvi_vigor_monitor"]
    # With SCL cloud pixels properly masked, cloudy pixels (NDVI ~0.006) are excluded
    assert ndvi["is_satellite_observed"] is True
    assert ndvi["mean_ndvi_in_field"] >= 0.45
    assert ndvi["min_ndvi_in_field"] >= 0.30


def test_e2e_t1_f9_06_awc_varies_by_soil_group(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    wb_a = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={"soil_group": "A"}).json()["water_balance_monthly"]
    wb_b = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={"soil_group": "B"}).json()["water_balance_monthly"]
    assert wb_b["available_water_capacity_max_mm"] > wb_a["available_water_capacity_max_mm"]


# ===========================================================================
# F10: Exports, Catalog/Health & API/TS Schema Contract Parity
# ===========================================================================


def test_e2e_t1_f10_01_export_geojson_package(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, field = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    _setup_csv_run(api_client, fid)
    lon, lat = field["centroid"]
    api_client.post(
        f"/api/v1/fields/{fid}/hydrology/observations",
        json={"observation_type": "ponding", "lon": lon, "lat": lat, "notes": "Bajo export"},
    ).raise_for_status()

    r = api_client.get(f"/api/v1/fields/{fid}/hydrology/export/geojson")
    assert r.status_code == 200
    assert "application/json" in r.headers["content-type"]
    assert ".geojson" in r.headers.get("content-disposition", "")
    pkg = r.json()
    assert pkg["type"] == "FeatureCollection"
    layers = {feat["properties"]["layer"] for feat in pkg["features"]}
    assert {"field_boundary", "potential_drainage_network", "field_observation"}.issubset(layers)
    assert pkg["rotaterra_metadata"]["calculation_crs"] == "EPSG:32720"


def test_e2e_t1_f10_02_export_report_html(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, field = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    _setup_csv_run(api_client, fid)
    r = api_client.get(f"/api/v1/fields/{fid}/hydrology/export/report")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text
    assert field["name"] in body
    assert "EPSG:32720" in body
    assert "DEM Sintético Plano 20m" in body
    assert "profundidad física de inundación" in body


def test_e2e_t1_f10_03_health_endpoint(api_client: TestClient):
    r = api_client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert isinstance(data["phase"], str) and data["phase"]
    assert isinstance(data["processing_version"], str) and data["processing_version"]


def _parse_pydantic_models(py_path: Path) -> dict[str, set[str]]:
    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    models: dict[str, set[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            base_names = [getattr(b, "id", "") for b in node.bases]
            if "BaseModel" in base_names:
                fields = {
                    stmt.target.id
                    for stmt in node.body
                    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
                }
                models[node.name] = fields
    return models


def _parse_ts_interfaces(ts_path: Path) -> dict[str, set[str]]:
    text = ts_path.read_text(encoding="utf-8")
    interfaces: dict[str, set[str]] = {}
    pattern = re.compile(r"export\s+interface\s+(\w+)\s*\{")
    for m in pattern.finditer(text):
        name = m.group(1)
        idx = m.end()
        depth = 1
        while idx < len(text) and depth > 0:
            if text[idx] == "{":
                depth += 1
            elif text[idx] == "}":
                depth -= 1
            idx += 1
        body = text[m.end() : idx - 1]
        # Top-level fields at brace depth 0
        fields: set[str] = set()
        d = 0
        for line in body.splitlines():
            stripped = line.strip()
            if d == 0:
                fm = re.match(r"^(\w+)\??\s*:", stripped)
                if fm:
                    fields.add(fm.group(1))
            d += line.count("{") - line.count("}")
        interfaces[name] = fields
    return interfaces


def test_e2e_t1_f10_04_pydantic_ts_schema_parity():
    schemas_py = REPO_ROOT / "services" / "api" / "app" / "schemas.py"
    types_ts = REPO_ROOT / "apps" / "web" / "src" / "types" / "api.ts"
    py_models = _parse_pydantic_models(schemas_py)
    ts_ifaces = _parse_ts_interfaces(types_ts)

    expected_shared = [
        "FieldOut", "DemSourceOut", "QualityWarningOut", "ElevationStats",
        "QualityReportOut", "TerrainOut", "MeshOut", "PointOut", "ProfileIn",
        "ProfileSample", "ProfileSummary", "ProfileOut", "ContoursOut",
        "HydrologyRunIn", "DepressionOut", "OutletOut", "HydrologySummaryOut",
        "HydrologyOut", "RainfallIntervalOut", "RainfallEventManualIn",
        "RainfallEventOut", "RunoffRunIn", "CnResultOut",
        "SpatialRunoffSummaryOut", "RunoffRunOut", "ScenarioComparisonOut",
        "TimelineFrameOut", "RunoffTimelineOut", "FieldObservationIn",
        "FieldObservationOut", "Hydrodynamic2DIn", "AgronomicToolkitIn",
        "AgronomicToolkitOut", "CatalogOut", "HealthOut",
    ]
    missing_py = [m for m in expected_shared if m not in py_models]
    missing_ts = [m for m in expected_shared if m not in ts_ifaces]
    assert not missing_py, f"Missing Pydantic schemas: {missing_py}"
    assert not missing_ts, f"Missing TypeScript interfaces: {missing_ts}"

    diffs = {}
    for name in expected_shared:
        only_py = sorted(py_models[name] - ts_ifaces[name])
        only_ts = sorted(ts_ifaces[name] - py_models[name])
        if only_py or only_ts:
            diffs[name] = {"only_py": only_py, "only_ts": only_ts}
    assert not diffs, f"Pydantic vs TS field mismatches: {diffs}"


def test_e2e_t1_f10_05_frontend_service_endpoint_parity():
    routes_hydro = (REPO_ROOT / "services" / "api" / "app" / "api" / "routes" / "hydrology.py").read_text(encoding="utf-8")
    api_ts = (REPO_ROOT / "apps" / "web" / "src" / "services" / "api.ts").read_text(encoding="utf-8")

    # Backend routes must declare explicit response_model for JSON endpoints
    assert '"/catalog", response_model=' in routes_hydro
    assert '"/toolkit", response_model=' in routes_hydro
    assert '"/toolkit/run", response_model=' in routes_hydro

    # Frontend API client must cover all endpoints and params
    for endpoint_frag in ("/health", "/terrain/contours", "/hydrology/catalog"):
        assert endpoint_frag in api_ts, f"Missing endpoint in apps/web/src/services/api.ts: {endpoint_frag}"
    for param_frag in ("declared_total_mm", "step_m"):
        assert param_frag in api_ts, f"Missing param in apps/web/src/services/api.ts: {param_frag}"
