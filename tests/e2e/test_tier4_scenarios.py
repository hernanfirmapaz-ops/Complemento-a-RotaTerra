"""Tier 4 — Real-World San Luis Application Scenarios (6 E2E scenarios)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.e2e.conftest import MockNetworkController
from tests.e2e.fixtures import (
    SAMPLE_DIR,
    WGS84_ESRI_WKT,
    make_shapefile_zip_bytes,
    write_san_luis_parcela_205_dem,
    write_san_luis_piedemonte_492_dem,
)
from tests.e2e.test_tier1_features import _upload_dem


def test_e2e_t4_s1_piedemonte_serrano_storm_hazard_and_terraces(api_client: TestClient, tmp_path: Path):
    """S1: Piedemonte 492 (EPSG:32719) -> storm CSV -> runoff -> timeline -> 2D SWE -> 8-tool toolkit -> exports."""
    f = api_client.post("/api/v1/fields/sample?preset=serrano").json()["fields"][0]
    fid = f["id"]
    assert f["utm_epsg"] == 32719
    assert 218.0 <= f["area_ha"] <= 232.0

    _upload_dem(api_client, fid, write_san_luis_piedemonte_492_dem(tmp_path / "piedemonte.tif", pixel_m=30.0), buffer_m=300.0)
    hydro = api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={"conditioning_mode": "fill_small"}).json()
    assert hydro["summary"]["mfd_mass_balance_error"] <= 1e-4

    ev = api_client.post(f"/api/v1/fields/{fid}/hydrology/rainfall-events/sample").json()
    assert ev["total_mm"] == 80.0 and ev["max_intensity_mm_h"] == 84.0

    run = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={
            "name": "Tormenta Serrana 80mm",
            "rainfall_event_id": ev["id"],
            "soil_group": "C",
            "cover_code": "soja_maiz_convencional",
            "antecedent_moisture": "wet",
        },
    ).json()
    assert run["cn_result"]["mass_balance_error_mm"] <= 1e-3

    tl = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/timeline").json()
    assert tl["max_mass_balance_error_mm"] <= 1e-3
    assert tl["peak_step_index"] >= 3  # Peak aligns around/after 14:45 (step index 3)

    run2d = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/simulate-2d", json={}).json()
    assert run2d["hydrodynamic_2d_summary"]["mass_balance_relative_error"] <= 0.02

    tk = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/toolkit/run",
        json={"soil_group": "C", "cover_code": "soja_maiz_convencional", "storm_precipitation_mm": 80.0},
    ).json()
    assert tk["contour_terraces"]["soil_loss_saved_tons"] > 0.0
    assert tk["contour_terraces"]["runoff_after_mm"] <= tk["contour_terraces"]["runoff_before_mm"]

    html = api_client.get(f"/api/v1/fields/{fid}/hydrology/export/report")
    gj = api_client.get(f"/api/v1/fields/{fid}/hydrology/export/geojson")
    assert html.status_code == 200 and gj.status_code == 200
    assert "EPSG:32719" in html.text
    assert "limitaciones" in html.text.lower()


def test_e2e_t4_s2_llanura_parcela_205_management_and_rotation_cu04(api_client: TestClient, tmp_path: Path):
    """S2: Parcela 205 (EPSG:32720) -> preserve depressions -> Run A vs Run B compare -> activate Run B -> toolkit rotation."""
    f = api_client.post("/api/v1/fields/sample?preset=llanura").json()["fields"][0]
    fid = f["id"]
    assert f["utm_epsg"] == 32720

    _upload_dem(api_client, fid, write_san_luis_parcela_205_dem(tmp_path / "p205.tif", pixel_m=30.0), buffer_m=300.0)
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={"conditioning_mode": "preserve"}).raise_for_status()

    ev = api_client.post(f"/api/v1/fields/{fid}/hydrology/rainfall-events/sample").json()
    run_a = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"name": "Convencional", "rainfall_event_id": ev["id"], "cover_code": "soja_maiz_convencional", "antecedent_moisture": "medium"},
    ).json()
    run_b = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"name": "Cobertura", "rainfall_event_id": ev["id"], "cover_code": "cultivo_cobertura_vicia_centeno", "antecedent_moisture": "medium"},
    ).json()

    cmp_res = api_client.get(
        f"/api/v1/fields/{fid}/hydrology/compare",
        params={"run_a": run_a["id"], "run_b": run_b["id"]},
    ).json()
    assert cmp_res["delta_runoff_q_mm"] < 0.0
    assert cmp_res["delta_net_outflow_potential_m3"] <= 0.0

    api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run_b['id']}/activate").raise_for_status()
    tk = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={"storm_precipitation_mm": 80.0}).json()
    assert tk["rotation_comparator_3yr"]["delta_b_vs_a"]["soil_saved_by_b_tons"] > 0.0
    assert tk["rotation_comparator_3yr"]["delta_b_vs_a"]["runoff_saved_by_b_mm"] > 0.0

    mesh = api_client.get(f"/api/v1/fields/{fid}/terrain/mesh?max_size=48").json()
    assert mesh["runoff_load_mm"] is not None


def test_e2e_t4_s3_field_calibration_loop_structures_and_observations_cu06(api_client: TestClient, tmp_path: Path):
    """S3: Parcela 205 -> register 5 obs -> 2D SWE -> inspect point -> delete erroneous obs -> verify export."""
    f = api_client.post("/api/v1/fields/sample?preset=llanura").json()["fields"][0]
    fid = f["id"]
    lon, lat = f["centroid"]

    _upload_dem(api_client, fid, write_san_luis_parcela_205_dem(tmp_path / "p205_obs.tif", pixel_m=30.0), buffer_m=300.0)
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    ev = api_client.post(f"/api/v1/fields/{fid}/hydrology/rainfall-events/sample").json()
    run = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs", json={"rainfall_event_id": ev["id"]}).json()

    obs_specs = [
        ("ponding", 0.0, 0.0, None, None, "Bajo principal"),
        ("water_depth", 0.0004, 0.0, 0.22, "m", "Tirante medido post-lluvia"),
        ("culvert", -0.0005, -0.0005, 0.6, "m", "Alcantarilla salida norte"),
        ("channel", 0.0005, 0.0005, 0.5, "m", "Canal evacuador este"),
        ("terrace", 0.0, 0.0008, None, None, "Terraza errónea para borrar"),
    ]
    created_ids: dict[str, str] = {}
    for ot, dlon, dlat, val, unit, notes in obs_specs:
        r_obs = api_client.post(
            f"/api/v1/fields/{fid}/hydrology/observations",
            json={"observation_type": ot, "lon": lon + dlon, "lat": lat + dlat, "notes": notes, "value": val, "units": unit},
        )
        assert r_obs.status_code == 201
        assert r_obs.json()["elevation_m"] is not None
        created_ids[ot] = r_obs.json()["id"]

    run2d = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/simulate-2d", json={}).json()
    assert run2d["hydrodynamic_2d_summary"]["hydraulic_structures_applied"] >= 2

    pt = api_client.get(f"/api/v1/fields/{fid}/terrain/point", params={"lon": lon, "lat": lat}).json()
    assert pt["water_depth_m"] is not None
    assert pt["agronomic_zone_id"] in (1, 2, 3, 4)

    assert api_client.delete(f"/api/v1/fields/{fid}/hydrology/observations/{created_ids['terrace']}").status_code == 204
    obs_list = api_client.get(f"/api/v1/fields/{fid}/hydrology/observations").json()
    assert all(o["id"] != created_ids["terrace"] for o in obs_list)

    gj = api_client.get(f"/api/v1/fields/{fid}/hydrology/export/geojson").json()
    obs_notes = {ft["properties"]["notes"] for ft in gj["features"] if ft["properties"]["layer"] == "field_observation"}
    assert "Terraza errónea para borrar" not in obs_notes
    assert "Alcantarilla salida norte" in obs_notes


def test_e2e_t4_s4_multiformat_onboarding_copernicus_30m_vs_drone_5m(api_client: TestClient, tmp_path: Path):
    """S4: Parcela 205 as SHP ZIP with hole -> 30m mocked Copernicus -> reprocess with 5m drone DEM."""
    p205 = json.loads((SAMPLE_DIR / "san_luis_parcela_205.geojson").read_text(encoding="utf-8"))
    outer = p205["features"][0]["geometry"]["coordinates"][0]
    hole = [
        [-65.698, -33.302], [-65.698, -33.298],
        [-65.695, -33.298], [-65.695, -33.302],
        [-65.698, -33.302],
    ]
    shp_zip = make_shapefile_zip_bytes(rings=[outer, hole], prj_wkt=WGS84_ESRI_WKT, dbf_name="Parcela 205 SHP")
    r_imp = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("parcela205.zip", shp_zip, "application/zip")},
    )
    assert r_imp.status_code == 201
    f = r_imp.json()["fields"][0]
    fid = f["id"]
    assert f["name"] == "Parcela 205 SHP"
    assert 170.0 <= f["area_ha"] <= 190.0  # ~198.7 ha minus ~12 ha hole

    t30 = api_client.post(
        f"/api/v1/fields/{fid}/terrain/process",
        data={"source_id": "copernicus_glo30", "buffer_m": "300"},
    ).json()
    assert "EGM2008" in t30["source"]["vertical_datum"]
    assert t30["source"]["acquisition_start"] == "2011-01-15"
    assert any(w["code"] == "sin_microrelieve" for w in t30["quality"]["warnings"])

    dem_5m = write_san_luis_parcela_205_dem(tmp_path / "drone_5m.tif", pixel_m=5.0)
    with dem_5m.open("rb") as fh:
        t5 = api_client.post(
            f"/api/v1/fields/{fid}/terrain/process",
            files={"file": ("drone_5m.tif", fh, "image/tiff")},
            data={
                "source_id": "upload",
                "buffer_m": "100",
                "source_name": "Dron RTK 5 m",
                "surface_type": "DTM",
                "vertical_datum": "SRVN16",
                "vertical_accuracy_m": "0.08",
                "acquisition_date": "2026-03-01",
            },
        ).json()
    assert t5["quality"]["pixel_size_m"] == 5.0
    assert t5["source"]["vertical_datum"] == "SRVN16"
    assert t5["quality"]["cells_in_field"] > t30["quality"]["cells_in_field"] * 25


def test_e2e_t4_s5_offline_satellite_outage_and_cloud_resilience_r4(
    api_client: TestClient,
    tmp_path: Path,
    mock_external_network: MockNetworkController,
):
    """S5: Full Phases 0-4 on Parcela 205 + toolkit under NASA 503 + S2 100% cloud (R4 strict no-fabrication)."""
    f = api_client.post("/api/v1/fields/sample?preset=llanura").json()["fields"][0]
    fid = f["id"]
    _upload_dem(api_client, fid, write_san_luis_parcela_205_dem(tmp_path / "p205_r4.tif", pixel_m=30.0))
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    ev = api_client.post(f"/api/v1/fields/{fid}/hydrology/rainfall-events/sample").json()
    run = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs", json={"rainfall_event_id": ev["id"]}).json()
    api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/simulate-2d", json={}).raise_for_status()

    mock_external_network.nasa_mode = "down"
    mock_external_network.stac_mode = "cloudy"
    tk = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).json()

    assert tk["erosion_usle"]["mean_soil_loss_t_ha"] >= 0.0
    assert tk["seeding_calculator_inta"]["seeds_to_sow_ha"] > 0
    assert tk["ndvi_vigor_monitor"]["is_satellite_observed"] is False
    assert tk["ndvi_vigor_monitor"].get("scene_id") != "synthetic-ecohydro-proxy"
    assert "calibrada" not in tk["water_balance_monthly"]["source"].lower()
    assert len(tk["warnings"]) >= 1

    mesh = api_client.get(f"/api/v1/fields/{fid}/terrain/mesh?max_size=48").json()
    assert mesh["ndvi"] is None
    assert mesh["water_depth_m"] is not None


def test_e2e_t4_s6_convective_hyetograph_vs_uniform_manual_rain_audit(api_client: TestClient, tmp_path: Path):
    """S6: Piedemonte 492 -> CSV 80 mm vs Manual 80 mm -> identical event Q_mm, contrasting timeline & 2D warnings."""
    f = api_client.post("/api/v1/fields/sample?preset=serrano").json()["fields"][0]
    fid = f["id"]
    _upload_dem(api_client, fid, write_san_luis_piedemonte_492_dem(tmp_path / "pied_s6.tif", pixel_m=30.0))
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()

    ev_csv = api_client.post(f"/api/v1/fields/{fid}/hydrology/rainfall-events/sample").json()
    ev_man = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events",
        json={"name": "Manual 80 mm", "total_mm": 80.0, "source_type": "manual"},
    ).json()

    run_csv = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev_csv["id"], "soil_group": "B", "antecedent_moisture": "medium"},
    ).json()
    run_man = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev_man["id"], "soil_group": "B", "antecedent_moisture": "medium"},
    ).json()

    assert run_csv["cn_result"]["runoff_q_mm"] == pytest.approx(run_man["cn_result"]["runoff_q_mm"], abs=1e-3)

    tl_csv = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run_csv['id']}/timeline").json()
    tl_man = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run_man['id']}/timeline").json()
    assert tl_csv["has_time_series"] is True and tl_csv["max_mass_balance_error_mm"] <= 1e-3
    assert len(tl_csv["particle_paths"]) >= 1
    assert tl_man["has_time_series"] is False and tl_man["frames"] == [] and len(tl_man["warnings"]) >= 1

    r2d_man = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run_man['id']}/simulate-2d", json={}).json()
    assert any("uniforme" in w.lower() or "4 pasos" in w.lower() or "hietograma" in w.lower() for w in r2d_man["warnings"])
