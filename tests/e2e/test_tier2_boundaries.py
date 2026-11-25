"""Tier 2 — Boundary & Corner Case Coverage (56 tests across F1–F10)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.app.api.routes import terrain as terrain_routes
from tests.e2e.conftest import MockNetworkController
from tests.e2e.fixtures import (
    REPO_ROOT,
    make_csv_bytes,
    make_geopackage_bytes,
    make_multipeak_csv_bytes,
    make_shapefile_zip_bytes,
    synthetic_square_field_geojson,
    synthetic_square_with_hole_rings,
    write_1x1_dem,
    write_closed_depression_dem,
    write_flat_dem,
    write_nodata_patch_dem,
    write_non_overlapping_dem,
    write_sloped_plane_dem,
)
from tests.e2e.test_tier1_features import _import_square, _upload_dem

# ===========================================================================
# F1: Boundary Import Corner Cases
# ===========================================================================


def test_e2e_t2_f1_01_open_ring_and_under_4_vertices_422(api_client: TestClient):
    open_gj = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"name": "Abierto"},
            "geometry": {"type": "Polygon", "coordinates": [[[-65.70, -33.30], [-65.69, -33.30], [-65.69, -33.29], [-65.70, -33.29]]]},
        }],
    }
    r1 = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("open.geojson", json.dumps(open_gj).encode("utf-8"), "application/geo+json")},
    )
    assert r1.status_code == 422
    assert "anillo" in r1.json()["detail"].lower() or "vértice" in r1.json()["detail"].lower()

    short_gj = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"name": "Corto"},
            "geometry": {"type": "Polygon", "coordinates": [[[-65.70, -33.30], [-65.69, -33.30], [-65.70, -33.30]]]},
        }],
    }
    r2 = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("short.geojson", json.dumps(short_gj).encode("utf-8"), "application/geo+json")},
    )
    assert r2.status_code == 422


def test_e2e_t2_f1_02_self_intersecting_bowtie_422(api_client: TestClient):
    bowtie = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"name": "Moño"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-65.70, -33.30], [-65.69, -33.29],
                    [-65.69, -33.30], [-65.70, -33.29],
                    [-65.70, -33.30],
                ]],
            },
        }],
    }
    r = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("bowtie.geojson", json.dumps(bowtie).encode("utf-8"), "application/geo+json")},
    )
    assert r.status_code == 422
    assert api_client.get("/api/v1/fields").json() == []


def test_e2e_t2_f1_03_empty_file_and_empty_feature_collection_422(api_client: TestClient):
    r_empty = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("empty.geojson", b"", "application/geo+json")},
    )
    assert r_empty.status_code == 422

    r_fc = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("fc_empty.geojson", json.dumps({"type": "FeatureCollection", "features": []}).encode(), "application/geo+json")},
    )
    assert r_fc.status_code == 422


def test_e2e_t2_f1_04_oversized_geojson_413(api_client: TestClient):
    pad = "x" * (5 * 1024 * 1024 + 512)
    gj = synthetic_square_field_geojson()
    gj["features"][0]["properties"]["padding"] = pad
    raw = json.dumps(gj).encode("utf-8")
    r = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("big.geojson", raw, "application/geo+json")},
    )
    assert r.status_code == 413


def test_e2e_t2_f1_05a_corrupt_zip_and_missing_shp_422(api_client: TestClient):
    r_corrupt = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("bad.zip", b"PK\x03\x04CORRUPT", "application/zip")},
    )
    assert r_corrupt.status_code == 422

    no_shp_zip = make_shapefile_zip_bytes(include_shp=False, dbf_name="SinSHP")
    r_no_shp = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("noshp.zip", no_shp_zip, "application/zip")},
    )
    assert r_no_shp.status_code == 422


def test_e2e_t2_f1_05b_shp_with_hole_subtracts_area(api_client: TestClient):
    outer_only = make_shapefile_zip_bytes(dbf_name="Sin Hueco")
    donut = make_shapefile_zip_bytes(rings=synthetic_square_with_hole_rings(), dbf_name="Con Hueco")
    r_full = api_client.post("/api/v1/fields/import", files={"file": ("full.zip", outer_only, "application/zip")})
    r_hole = api_client.post("/api/v1/fields/import", files={"file": ("hole.zip", donut, "application/zip")})
    assert r_full.status_code == 201 and r_hole.status_code == 201
    area_full = r_full.json()["fields"][0]["area_ha"]
    area_hole = r_hole.json()["fields"][0]["area_ha"]
    # Interior hole is 0.4 * 0.4 = 16% of outer square
    assert area_hole == pytest.approx(area_full * 0.84, rel=0.02)


def test_e2e_t2_f1_06_unsupported_gpkg_and_unknown_field_id(api_client: TestClient):
    r_txt = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("notes.txt", b"just text", "text/plain")},
    )
    assert r_txt.status_code == 422

    gpkg = make_geopackage_bytes()
    r_gpkg = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("lote.gpkg", gpkg, "application/geopackage+sqlite3")},
    )
    assert r_gpkg.status_code in (201, 422)

    r_missing = api_client.get("/api/v1/fields/00000000000000000000000000000000")
    assert r_missing.status_code == 404


# ===========================================================================
# F2: DEM Acquisition & Quality Corner Cases
# ===========================================================================


def test_e2e_t2_f2_01_non_tiff_upload_422(api_client: TestClient):
    f = _import_square(api_client)
    r = api_client.post(
        f"/api/v1/fields/{f['id']}/terrain/process",
        files={"file": ("fake.tif", b"NOT_A_TIFF_FILE", "image/tiff")},
        data={"source_id": "upload", "buffer_m": "100"},
    )
    assert r.status_code == 422


def test_e2e_t2_f2_02_missing_upload_and_oversized_dem_413(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    f = _import_square(api_client)
    r_miss = api_client.post(
        f"/api/v1/fields/{f['id']}/terrain/process",
        data={"source_id": "upload", "buffer_m": "100"},
    )
    assert r_miss.status_code == 422

    dem_path = write_sloped_plane_dem(tmp_path / "dem.tif")
    monkeypatch.setattr(terrain_routes, "MAX_DEM_BYTES", 512)
    with dem_path.open("rb") as fh:
        r_big = api_client.post(
            f"/api/v1/fields/{f['id']}/terrain/process",
            files={"file": ("dem.tif", fh, "image/tiff")},
            data={"source_id": "upload", "buffer_m": "100"},
        )
    assert r_big.status_code == 413


def test_e2e_t2_f2_03_non_overlapping_dem_422(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    bad_dem = write_non_overlapping_dem(tmp_path / "far.tif")
    with bad_dem.open("rb") as fh:
        r = api_client.post(
            f"/api/v1/fields/{f['id']}/terrain/process",
            files={"file": ("far.tif", fh, "image/tiff")},
            data={"source_id": "upload", "buffer_m": "100"},
        )
    assert r.status_code == 422


def test_e2e_t2_f2_04_high_nodata_pct_not_interpolated(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    nd_dem = write_nodata_patch_dem(tmp_path / "nodata.tif", nodata_top_fraction=0.65)
    terr = _upload_dem(api_client, f["id"], nd_dem, buffer_m=100.0)
    assert terr["quality"]["nodata_pct_field"] > 50.0
    assert any(w["code"] == "nodata_alto" and w["level"] == "critico" for w in terr["quality"]["warnings"])
    mesh = api_client.get(f"/api/v1/fields/{f['id']}/terrain/mesh?max_size=48").json()
    assert any(v is None for v in mesh["z"])


def test_e2e_t2_f2_05_buffer_bounds(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    dem_path = write_sloped_plane_dem(tmp_path / "dem_b.tif")
    assert _upload_dem(api_client, f["id"], dem_path, buffer_m=0.0)["quality"]["buffer_m"] == 0.0

    for bad_buf in ("-1", "10001"):
        with dem_path.open("rb") as fh:
            r = api_client.post(
                f"/api/v1/fields/{f['id']}/terrain/process",
                files={"file": ("dem_b.tif", fh, "image/tiff")},
                data={"source_id": "upload", "buffer_m": bad_buf},
            )
        assert r.status_code == 422


def test_e2e_t2_f2_06_unprocessed_terrain_404(api_client: TestClient):
    f = _import_square(api_client)
    assert api_client.get(f"/api/v1/fields/{f['id']}/terrain").status_code == 404


# ===========================================================================
# F3: Point, Profile, Contours & Mesh Corner Cases
# ===========================================================================


def test_e2e_t2_f3_01_point_outside_dem(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    r = api_client.get(f"/api/v1/fields/{fid}/terrain/point", params={"lon": -64.0, "lat": -32.0})
    assert r.status_code == 200
    pt = r.json()
    assert pt["inside_dem"] is False
    assert pt["elevation_m"] is None
    assert pt["slope_pct"] is None
    assert len(pt["warnings"]) >= 1


def test_e2e_t2_f3_02_point_in_buffer_outside_field(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    # Synthetic square is [-65.70..-65.69, -33.30..-33.29]; -65.7010 is ~90m west (inside 200m buffer)
    r = api_client.get(f"/api/v1/fields/{fid}/terrain/point", params={"lon": -65.7010, "lat": -33.295})
    assert r.status_code == 200
    pt = r.json()
    assert pt["inside_dem"] is True
    assert pt["inside_field"] is False
    assert pt["elevation_m"] is not None
    assert pt["slope_pct"] is not None


def test_e2e_t2_f3_03_point_and_profile_adjacent_to_nodata(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    _upload_dem(api_client, f["id"], write_nodata_patch_dem(tmp_path / "nd.tif", nodata_top_fraction=0.60), buffer_m=100.0)
    # Upper-north part of field (-33.292) is NaN
    pt = api_client.get(f"/api/v1/fields/{f['id']}/terrain/point", params={"lon": -65.695, "lat": -33.292}).json()
    assert pt["elevation_m"] is None
    assert pt["slope_pct"] is None

    prof = api_client.post(
        f"/api/v1/fields/{f['id']}/terrain/profile",
        json={"coordinates": [[-65.695, -33.299], [-65.695, -33.291]]},
    ).json()
    assert prof["summary"]["valid_samples"] < prof["summary"]["samples"]


def test_e2e_t2_f3_04_invalid_profile_and_mesh_params_422(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    assert api_client.post(f"/api/v1/fields/{fid}/terrain/profile", json={"coordinates": [[-65.695, -33.295]]}).status_code == 422
    assert api_client.post(f"/api/v1/fields/{fid}/terrain/profile", json={"coordinates": [[181.0, -33.295], [-65.695, -33.295]]}).status_code == 422
    assert api_client.post(f"/api/v1/fields/{fid}/terrain/profile", json={"coordinates": [[-65.698, -33.298], [-65.692, -33.292]], "step_m": 0}).status_code == 422
    assert api_client.get(f"/api/v1/fields/{fid}/terrain/mesh?max_size=15").status_code == 422
    assert api_client.get(f"/api/v1/fields/{fid}/terrain/mesh?max_size=513").status_code == 422


def test_e2e_t2_f3_05_vertical_exaggeration_1x_invariance(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, field = field_with_sloped_dem
    lon, lat = field["centroid"]
    pt = api_client.get(f"/api/v1/fields/{fid}/terrain/point", params={"lon": lon, "lat": lat}).json()
    mesh = api_client.get(f"/api/v1/fields/{fid}/terrain/mesh?max_size=48").json()
    prof = api_client.post(
        f"/api/v1/fields/{fid}/terrain/profile",
        json={"coordinates": [[-65.699, -33.299], [-65.691, -33.291]]},
    ).json()
    # True 1x metric elevations (~500-660 m), never scaled by client exaggeration
    assert 490.0 <= pt["elevation_m"] <= 660.0
    assert 490.0 <= mesh["z_min"] <= mesh["z_max"] <= 660.0
    assert prof["summary"]["range_m"] == pytest.approx(prof["summary"]["max_m"] - prof["summary"]["min_m"], abs=0.05)


# ===========================================================================
# F4: Static Hydrology Corner Cases
# ===========================================================================


def test_e2e_t2_f4_01_flat_dem_no_div_zero(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    _upload_dem(api_client, f["id"], write_flat_dem(tmp_path / "flat.tif", z_val=500.0))
    r = api_client.post(f"/api/v1/fields/{f['id']}/hydrology/static", json={})
    assert r.status_code == 200, r.text
    lon, lat = f["centroid"]
    pt = api_client.get(f"/api/v1/fields/{f['id']}/terrain/point", params={"lon": lon, "lat": lat}).json()
    assert pt["slope_pct"] == 0.0
    assert pt["elevation_m"] == 500.0


def test_e2e_t2_f4_02_minimal_1x1_dem(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    dem_1x1 = write_1x1_dem(tmp_path / "one.tif")
    with dem_1x1.open("rb") as fh:
        r_ter = api_client.post(
            f"/api/v1/fields/{f['id']}/terrain/process",
            files={"file": ("one.tif", fh, "image/tiff")},
            data={"source_id": "upload", "buffer_m": "0"},
        )
    assert r_ter.status_code in (200, 422)
    if r_ter.status_code == 200:
        r_hyd = api_client.post(f"/api/v1/fields/{f['id']}/hydrology/static", json={})
        assert r_hyd.status_code in (200, 422)


def test_e2e_t2_f4_03_closed_parabolic_bowl_preserve_vs_fill(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    _upload_dem(api_client, f["id"], write_closed_depression_dem(tmp_path / "bowl.tif"))
    pres = api_client.post(f"/api/v1/fields/{f['id']}/hydrology/static", json={"conditioning_mode": "preserve"}).json()
    assert pres["summary"]["depressions_in_field_count"] >= 1
    assert pres["summary"]["total_depression_volume_in_field_m3"] > 0.0
    assert any(d["in_field"] and not d["is_spurious_candidate"] for d in pres["depressions"])

    fill = api_client.post(f"/api/v1/fields/{f['id']}/hydrology/static", json={"conditioning_mode": "fill_all"}).json()
    assert fill["summary"]["depressions_filled_count"] >= 1
    assert any(d["filled_in_run"] for d in fill["depressions"])


def test_e2e_t2_f4_04_extreme_threshold_and_invalid_mfd_exponent(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    r_ext = api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={"stream_threshold_ha": 5000.0})
    assert r_ext.status_code == 200
    assert r_ext.json()["summary"]["stream_segments_count"] == 0

    r_bad = api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={"mfd_exponent": 0.1})
    assert r_bad.status_code == 422


def test_e2e_t2_f4_05_static_hydrology_before_dem_404(api_client: TestClient):
    f = _import_square(api_client)
    assert api_client.post(f"/api/v1/fields/{f['id']}/hydrology/static", json={}).status_code == 404


# ===========================================================================
# F5: Rainfall & Runoff Corner Cases
# ===========================================================================


def test_e2e_t2_f5_01_manual_rainfall_out_of_range_422(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    for bad_mm in (0.0, -5.0, 1501.0):
        r = api_client.post(
            f"/api/v1/fields/{fid}/hydrology/rainfall-events",
            json={"name": "Inválida", "total_mm": bad_mm, "source_type": "manual"},
        )
        assert r.status_code == 422


def test_e2e_t2_f5_02_small_rain_p_le_ia(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    ev = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events",
        json={"name": "Llovizna 5 mm", "total_mm": 5.0, "source_type": "manual"},
    ).json()
    r = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "custom_cn_ii": 75.0, "antecedent_moisture": "medium", "lambda_ratio": 0.2},
    )
    assert r.status_code == 201
    cn = r.json()["cn_result"]
    assert cn["runoff_q_mm"] == 0.0
    assert cn["runoff_coefficient"] == 0.0
    assert cn["total_retention_losses_mm"] == 5.0
    assert cn["mass_balance_error_mm"] == 0.0


@pytest.mark.parametrize(
    "bad_csv",
    [
        b"timestamp,precipitation_mm,interval_minutes,station_id\n2026-11-18T14:00:00-03:00,-2.0,15,S1\n",
        b"timestamp,precipitation_mm,interval_minutes,station_id\n2026-11-18T14:00:00-03:00,5.0,15,S1\n2026-11-18T14:00:00-03:00,3.0,15,S1\n",
        b"timestamp,precipitation_mm,interval_minutes,station_id\n2026-11-18T14:00:00,5.0,15,S1\n",
        b"fecha,lluvia\n2026-11-18,10.0\n",
    ],
)
def test_e2e_t2_f5_03_bad_csv_rejected_422(field_with_sloped_dem: tuple[str, dict], api_client: TestClient, bad_csv: bytes):
    fid, _ = field_with_sloped_dem
    r = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events/import-csv",
        files={"file": ("bad.csv", bad_csv, "text/csv")},
        data={"name": "Malo", "source_type": "gauge"},
    )
    assert r.status_code == 422


def test_e2e_t2_f5_04_csv_gap_extreme_and_declared_total_mismatch(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    # 15-min interval with a 30-min gap, plus 40 mm in 15 min (160 mm/h >= 120 mm/h)
    csv_bytes = make_csv_bytes([
        ("2026-11-18T14:00:00-03:00", 5.0, 15, "PLUV-01"),
        ("2026-11-18T14:45:00-03:00", 40.0, 15, "PLUV-01"),
    ])
    r = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events/import-csv",
        files={"file": ("gap.csv", csv_bytes, "text/csv")},
        data={"name": "Con hueco y pico", "source_type": "gauge", "declared_total_mm": "80.0"},
    )
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["total_mm"] == 45.0  # Extreme value conserved, not deleted
    joined = " | ".join(ev["warnings"]).lower()
    assert "hueco" in joined
    assert "120" in joined or "extrema" in joined or "intensidad" in joined
    assert "difiere" in joined


def test_e2e_t2_f5_05_invalid_cover_cn_and_missing_compare(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    ev = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events",
        json={"name": "Lluvia 50", "total_mm": 50.0, "source_type": "manual"},
    ).json()
    assert api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "cover_code": "cobertura_inexistente"},
    ).status_code == 422
    assert api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "custom_cn_ii": 25.0},
    ).status_code == 422
    assert api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "custom_cn_ii": 100.0},
    ).status_code == 422
    run_ok = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"]},
    ).json()
    assert api_client.get(
        f"/api/v1/fields/{fid}/hydrology/compare",
        params={"run_a": run_ok["id"], "run_b": "missing"},
    ).status_code == 404


# ===========================================================================
# F6: Temporal Routing Corner Cases
# ===========================================================================


def test_e2e_t2_f6_01_manual_event_timeline_no_fabricated_intensity(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    ev = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events",
        json={"name": "Manual 60", "total_mm": 60.0, "source_type": "manual"},
    ).json()
    run = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"]},
    ).json()
    tl = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/timeline").json()
    assert tl["has_time_series"] is False
    assert tl["frames"] == []
    assert tl["total_steps"] == 0
    assert any("no se inventa" in w.lower() or "hietograma" in w.lower() for w in tl["warnings"])


def test_e2e_t2_f6_02_single_interval_csv_timeline(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    csv_bytes = make_csv_bytes([("2026-11-18T14:00:00-03:00", 35.0, 15, "PLUV-01")])
    ev = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events/import-csv",
        files={"file": ("single.csv", csv_bytes, "text/csv")},
        data={"name": "1 paso", "source_type": "gauge"},
    ).json()
    run = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs", json={"rainfall_event_id": ev["id"]}).json()
    tl = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/timeline").json()
    assert tl["rainfall_steps"] == 1
    assert tl["recession_steps"] >= 1
    assert tl["max_mass_balance_error_mm"] <= 1e-3


def test_e2e_t2_f6_03_zero_runoff_csv_timeline(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    csv_bytes = make_csv_bytes([
        ("2026-11-18T14:00:00-03:00", 2.0, 15, "PLUV-01"),
        ("2026-11-18T14:15:00-03:00", 2.0, 15, "PLUV-01"),
    ])
    ev = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events/import-csv",
        files={"file": ("tiny.csv", csv_bytes, "text/csv")},
        data={"name": "Llovizna 4mm", "source_type": "gauge"},
    ).json()
    run = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "antecedent_moisture": "dry"},
    ).json()
    tl = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/timeline").json()
    assert all(fr["cumulative_runoff_generated_mm"] == 0.0 for fr in tl["frames"])
    assert all(fr["cumulative_outflow_mm"] == 0.0 for fr in tl["frames"])
    assert tl["max_mass_balance_error_mm"] <= 1e-3


def test_e2e_t2_f6_04_timeline_unknown_run_id_404(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    assert api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/does-not-exist/timeline").status_code == 404


def test_e2e_t2_f6_05_long_multipeak_storm_timeline(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    ev = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events/import-csv",
        files={"file": ("multi.csv", make_multipeak_csv_bytes(), "text/csv")},
        data={"name": "Doble Pico", "source_type": "gauge"},
    ).json()
    run = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs", json={"rainfall_event_id": ev["id"]}).json()
    tl = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/timeline").json()
    assert tl["rainfall_steps"] == 24
    assert all(fr["active_transit_lamina_mm"] >= 0.0 for fr in tl["frames"])
    assert tl["max_mass_balance_error_mm"] <= 1e-3


# ===========================================================================
# F7: 2D SWE & Field Observations Corner Cases
# ===========================================================================


def test_e2e_t2_f7_01_simulate_2d_manual_rain_emits_uniform_warning(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    ev = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events",
        json={"name": "Manual 70 mm", "total_mm": 70.0, "source_type": "manual"},
    ).json()
    run = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs", json={"rainfall_event_id": ev["id"]}).json()
    r = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/simulate-2d", json={})
    assert r.status_code == 200
    joined = " | ".join(r.json()["warnings"]).lower()
    assert "uniforme" in joined or "4 pasos" in joined or "sin hietograma" in joined


def test_e2e_t2_f7_02_simulate_2d_zero_runoff(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    ev = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events",
        json={"name": "Llovizna 4 mm", "total_mm": 4.0, "source_type": "manual"},
    ).json()
    run = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "antecedent_moisture": "dry"},
    ).json()
    s2d = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/simulate-2d",
        json={},
    ).json()["hydrodynamic_2d_summary"]
    assert s2d["max_water_depth_in_field_m"] == 0.0
    assert s2d["max_velocity_in_field_m_s"] == 0.0
    assert s2d["ponded_area_in_field_ha"] == 0.0


def test_e2e_t2_f7_03_simulate_2d_invalid_params_422(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    ev = api_client.post(f"/api/v1/fields/{fid}/hydrology/rainfall-events/sample").json()
    run = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs", json={"rainfall_event_id": ev["id"]}).json()
    for bad in ({"manning_n": 0.005}, {"ponding_threshold_m": 0.0}, {"recession_minutes": 1}):
        assert api_client.post(
            f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/simulate-2d",
            json=bad,
        ).status_code == 422


def test_e2e_t2_f7_04_observation_invalid_params_422(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, field = field_with_sloped_dem
    lon, lat = field["centroid"]
    assert api_client.post(
        f"/api/v1/fields/{fid}/hydrology/observations",
        json={"observation_type": "invalido", "lon": lon, "lat": lat, "notes": "Nota válida"},
    ).status_code == 422
    assert api_client.post(
        f"/api/v1/fields/{fid}/hydrology/observations",
        json={"observation_type": "ponding", "lon": lon, "lat": lat, "notes": "x"},
    ).status_code == 422
    assert api_client.post(
        f"/api/v1/fields/{fid}/hydrology/observations",
        json={"observation_type": "ponding", "lon": lon, "lat": 95.0, "notes": "Nota válida"},
    ).status_code == 422


def test_e2e_t2_f7_05_delete_nonexistent_observation_404(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    assert api_client.delete(f"/api/v1/fields/{fid}/hydrology/observations/non-existent").status_code == 404


# ===========================================================================
# F8: Agronomic Toolkit Corner Cases
# ===========================================================================


def test_e2e_t2_f8_01_toolkit_invalid_inputs_422(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    for bad in (
        {"soil_group": "Z"},
        {"storm_precipitation_mm": 0.0},
        {"storm_precipitation_mm": 1001.0},
        {"environment_zone": "invalida"},
    ):
        assert api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json=bad).status_code == 422


def test_e2e_t2_f8_02_target_yield_boundaries_422(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    assert api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={"target_yield_t_ha": 0.5}).status_code == 422
    assert api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={"target_yield_t_ha": 25.1}).status_code == 422


def test_e2e_t2_f8_03_toolkit_on_flat_dem(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    _upload_dem(api_client, f["id"], write_flat_dem(tmp_path / "flat_tk.tif", z_val=500.0))
    from services.api.app.services import store
    (store.field_dir(f["id"]) / "soil.json").write_text(
        json.dumps({"sand_pct": 40.0, "silt_pct": 40.0, "clay_pct": 20.0, "quality": "confiable"}),
        encoding="utf-8",
    )
    api_client.post(f"/api/v1/fields/{f['id']}/hydrology/static", json={}).raise_for_status()
    r = api_client.post(f"/api/v1/fields/{f['id']}/hydrology/toolkit/run", json={})
    assert r.status_code == 200
    tk = r.json()
    # Con la formulación de McCool et al. (1987) para pendientes < 9%, el factor S en terreno
    # plano no colapsa a 0 (como en Moore & Burch) sino al término basal inter-surco por impacto
    # de gota: S_min = 10.8 * sin(beta_min) + 0.03 ≈ 0.0408.
    # Cota analítica esperada del caso (P=80 mm -> R≈1141.89, K≈0.0260, L=(30/22.13)^0.4≈1.129, C=0.09, P=1.0):
    # A_max = R * K * L_max * S * C * P ≈ 1141.89 * 0.026026 * 1.1294 * 0.0408 * 0.09 * 1.0 ≈ 0.123 t/ha
    # A_min = R * K * 1.0 * 0.0300 * C * P ≈ 0.080 t/ha
    # En el lote muestreado con máscara perimetral UTM, el valor medio resultante es 0.105 t/ha.
    loss = tk["erosion_usle"]["mean_soil_loss_t_ha"]
    assert 0.08 <= loss <= 0.125
    assert pytest.approx(loss, abs=0.01) == 0.105
    assert tk["contour_terraces"]["mean_field_slope_pct"] == 0.0


def test_e2e_t2_f8_04_toolkit_before_hydrology_or_dem_404(api_client: TestClient):
    f = _import_square(api_client)
    assert api_client.get(f"/api/v1/fields/{f['id']}/hydrology/toolkit").status_code == 404
    assert api_client.post(f"/api/v1/fields/{f['id']}/hydrology/toolkit/run", json={}).status_code == 404


def test_e2e_t2_f8_05_rotation_comparator_identical_sequences(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    seq = ["soja_maiz_sd_buena", "trigo_cereal_invierno_sd", "soja_maiz_sd_buena"]
    tk = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/toolkit/run",
        json={"sequence_a_crops": seq, "sequence_b_crops": seq},
    ).json()
    delta = tk["rotation_comparator_3yr"]["delta_b_vs_a"]
    assert delta["runoff_change_3yr_mm"] == 0.0
    assert delta["soil_loss_change_3yr_t_ha"] == 0.0
    assert delta["soil_saved_by_b_tons"] == 0.0
    assert delta["runoff_saved_by_b_mm"] == 0.0
    assert delta["cover_gain_pct"] == 0.0


# ===========================================================================
# F9: R4 Degraded Mode & Outage Resilience (Zero Synthetic Fallback)
# ===========================================================================


def test_e2e_t2_f9_01_nasa_power_outage_degrades_without_fabrication(
    field_with_sloped_dem: tuple[str, dict],
    api_client: TestClient,
    mock_external_network: MockNetworkController,
):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    mock_external_network.nasa_mode = "down"
    r = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={})
    assert r.status_code == 200
    tk = r.json()
    wb = tk["water_balance_monthly"]
    wl = tk["real_waterlogging_by_date"]
    fr = tk["frost_risk_sowing"]
    assert "calibrada" not in wb["source"].lower()
    assert wb.get("status") == "unavailable" or wb.get("months") == []
    assert wl.get("status") == "unavailable" or wl.get("evaluated_days") == 0
    assert fr.get("status") == "unavailable" or fr.get("is_satellite_observed") is False
    assert len(tk["warnings"]) >= 1


def test_e2e_t2_f9_02_stac_outage_degrades_without_fake_ndvi(
    field_with_sloped_dem: tuple[str, dict],
    api_client: TestClient,
    mock_external_network: MockNetworkController,
):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    mock_external_network.stac_mode = "down"
    tk = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).json()
    ndvi = tk["ndvi_vigor_monitor"]
    assert ndvi["is_satellite_observed"] is False
    assert ndvi.get("scene_id") != "synthetic-ecohydro-proxy"
    assert ndvi.get("status") == "unavailable" or ndvi.get("mean_ndvi_in_field") is None
    mesh = api_client.get(f"/api/v1/fields/{fid}/terrain/mesh?max_size=48").json()
    assert mesh["ndvi"] is None


def test_e2e_t2_f9_03_stac_100pct_cloudy_scene_rejected(
    field_with_sloped_dem: tuple[str, dict],
    api_client: TestClient,
    mock_external_network: MockNetworkController,
):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    mock_external_network.stac_mode = "cloudy"
    tk = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).json()
    ndvi = tk["ndvi_vigor_monitor"]
    assert ndvi["is_satellite_observed"] is False
    assert ndvi.get("scene_id") != "synthetic-ecohydro-proxy"
    assert ndvi.get("status") == "unavailable" or ndvi.get("mean_ndvi_in_field") is None


def test_e2e_t2_f9_04_stac_empty_features_no_synthetic_fallback(
    field_with_sloped_dem: tuple[str, dict],
    api_client: TestClient,
    mock_external_network: MockNetworkController,
):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    mock_external_network.stac_mode = "empty"
    tk = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).json()
    ndvi = tk["ndvi_vigor_monitor"]
    assert ndvi["is_satellite_observed"] is False
    assert ndvi.get("scene_id") != "synthetic-ecohydro-proxy"
    assert ndvi.get("status") == "unavailable" or ndvi.get("mean_ndvi_in_field") is None


def test_e2e_t2_f9_05_nasa_fill_999_never_treated_as_real_climate(
    field_with_sloped_dem: tuple[str, dict],
    api_client: TestClient,
    mock_external_network: MockNetworkController,
):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    mock_external_network.nasa_mode = "fill_999"
    tk = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).json()
    wb = tk["water_balance_monthly"]
    assert "calibrada" not in wb["source"].lower()
    assert wb.get("status") == "unavailable" or wb.get("months") == []


# ===========================================================================
# F10: Exports, XSS & Nested Schema Parity Corner Cases
# ===========================================================================


def test_e2e_t2_f10_01_export_boundary_only_field(api_client: TestClient):
    f = _import_square(api_client)
    r_gj = api_client.get(f"/api/v1/fields/{f['id']}/hydrology/export/geojson")
    r_html = api_client.get(f"/api/v1/fields/{f['id']}/hydrology/export/report")
    assert r_gj.status_code in (200, 404)
    assert r_html.status_code in (200, 404)
    if r_gj.status_code == 200:
        assert r_gj.json()["features"][0]["properties"]["layer"] == "field_boundary"


def test_e2e_t2_f10_02_export_report_xss_escaping(api_client: TestClient, tmp_path: Path):
    xss_name = '<script>alert("xss")</script>'
    f = _import_square(api_client, name=xss_name)
    _upload_dem(api_client, f["id"], write_sloped_plane_dem(tmp_path / "xss.tif"))
    r = api_client.get(f"/api/v1/fields/{f['id']}/hydrology/export/report")
    assert r.status_code == 200
    assert "<script>alert(" not in r.text
    assert "&lt;script&gt;alert(" in r.text


def test_e2e_t2_f10_03_export_unknown_field_404(api_client: TestClient):
    bad_id = "00000000000000000000000000000000"
    assert api_client.get(f"/api/v1/fields/{bad_id}/hydrology/export/geojson").status_code == 404
    assert api_client.get(f"/api/v1/fields/{bad_id}/hydrology/export/report").status_code == 404


def test_e2e_t2_f10_04_catalog_schema_in_schemas_py(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    r = api_client.get(f"/api/v1/fields/{fid}/hydrology/catalog")
    assert r.status_code == 200
    schemas_text = (REPO_ROOT / "services" / "api" / "app" / "schemas.py").read_text(encoding="utf-8")
    assert "class CatalogOut" in schemas_text


def test_e2e_t2_f10_05_nested_schema_parity_2d_zonation_toolkit(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    ev = api_client.post(f"/api/v1/fields/{fid}/hydrology/rainfall-events/sample").json()
    run = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs", json={"rainfall_event_id": ev["id"]}).json()
    run2d = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/simulate-2d", json={}).json()
    tk = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).json()

    schemas_text = (REPO_ROOT / "services" / "api" / "app" / "schemas.py").read_text(encoding="utf-8")
    types_text = (REPO_ROOT / "apps" / "web" / "src" / "types" / "api.ts").read_text(encoding="utf-8")

    assert "class Hydrodynamic2DSummaryOut" in schemas_text
    assert "class AgronomicZonationOut" in schemas_text
    assert "class AgronomicToolkitOut" in schemas_text

    # Every top-level key of Hydrodynamic2DSummaryOut returned by API must exist in TS interface
    m2d = re.search(r"export interface Hydrodynamic2DSummaryOut \{([^}]+)\}", types_text)
    assert m2d is not None
    ts_2d_keys = set(re.findall(r"^\s*(\w+)\??:", m2d.group(1), flags=re.MULTILINE))
    assert set(run2d["hydrodynamic_2d_summary"].keys()) == ts_2d_keys

    # Every tool block key in AgronomicToolkitOut must align
    for tool_key in (
        "erosion_usle",
        "water_balance_monthly",
        "real_waterlogging_by_date",
        "contour_terraces",
        "seeding_calculator_inta",
        "rotation_comparator_3yr",
        "ndvi_vigor_monitor",
        "frost_risk_sowing",
    ):
        assert tool_key in tk
        assert tool_key in types_text
