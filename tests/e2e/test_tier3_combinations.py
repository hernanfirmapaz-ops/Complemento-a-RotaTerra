"""Tier 3 — Cross-Feature Pairwise Combinations (18 tests)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.e2e.conftest import MockNetworkController
from tests.e2e.fixtures import (
    make_kmz_bytes,
    make_shapefile_zip_bytes,
    synthetic_square_with_hole_rings,
    write_closed_depression_dem,
    write_nodata_patch_dem,
    write_sloped_plane_dem,
    write_sloped_with_micro_depression_dem,
)
from tests.e2e.test_tier1_features import _import_square, _setup_csv_run, _upload_dem


def test_e2e_t3_01_f1_x_f2_kmz_to_uploaded_dem(api_client: TestClient, tmp_path: Path):
    kmz = make_kmz_bytes(name="Lote KMZ Combinado", multipolygon=False)
    f = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("campo.kmz", kmz, "application/vnd.google-earth.kmz")},
    ).json()["fields"][0]
    terr = _upload_dem(api_client, f["id"], write_sloped_plane_dem(tmp_path / "kmz_dem.tif"))
    assert terr["quality"]["crs"] == f"EPSG:{f['utm_epsg']}"
    assert terr["quality"]["field_area_ha"] == pytest.approx(f["area_ha"], rel=0.02)


def test_e2e_t3_02_f1_x_f3_polygon_with_hole_point_and_mesh(api_client: TestClient, tmp_path: Path):
    donut = make_shapefile_zip_bytes(rings=synthetic_square_with_hole_rings(), dbf_name="Lote Con Hueco")
    r_imp = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("donut.zip", donut, "application/zip")},
    )
    assert r_imp.status_code == 201
    f = r_imp.json()["fields"][0]
    _upload_dem(api_client, f["id"], write_sloped_plane_dem(tmp_path / "hole_dem.tif"))

    # Center (-65.695, -33.295) lies inside the interior hole
    pt = api_client.get(f"/api/v1/fields/{f['id']}/terrain/point", params={"lon": -65.695, "lat": -33.295}).json()
    assert pt["inside_dem"] is True
    assert pt["inside_field"] is False

    mesh = api_client.get(f"/api/v1/fields/{f['id']}/terrain/mesh?max_size=64").json()
    # Both inside-field and outside-field (hole + buffer) cells exist
    assert any(mesh["in_field"]) and not all(mesh["in_field"])


def test_e2e_t3_03_f2_x_f3_nodata_strip_buffer_point_profile_contours(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    _upload_dem(api_client, f["id"], write_nodata_patch_dem(tmp_path / "nd3.tif", nodata_top_fraction=0.60), buffer_m=300.0)

    pt_nd = api_client.get(f"/api/v1/fields/{f['id']}/terrain/point", params={"lon": -65.695, "lat": -33.292}).json()
    assert pt_nd["elevation_m"] is None

    pt_buf = api_client.get(f"/api/v1/fields/{f['id']}/terrain/point", params={"lon": -65.7015, "lat": -33.299}).json()
    assert pt_buf["inside_dem"] is True
    assert pt_buf["inside_field"] is False
    assert pt_buf["elevation_m"] is not None

    prof = api_client.post(
        f"/api/v1/fields/{f['id']}/terrain/profile",
        json={"coordinates": [[-65.695, -33.299], [-65.695, -33.291]]},
    ).json()
    assert prof["summary"]["valid_samples"] < prof["summary"]["samples"]

    contours = api_client.get(f"/api/v1/fields/{f['id']}/terrain/contours?interval_m=2.0").json()
    assert contours["type"] == "FeatureCollection"


def test_e2e_t3_04_f2_x_f4_highres_vs_coarse_dem_static_hydrology(api_client: TestClient, tmp_path: Path):
    f1 = _import_square(api_client, name="Lote 5m")
    _upload_dem(api_client, f1["id"], write_sloped_plane_dem(tmp_path / "d5.tif", pixel_m=5.0, width=320, height=320, x_origin=248_200.0, y_origin=6_313_500.0), buffer_m=100.0)
    h5 = api_client.post(f"/api/v1/fields/{f1['id']}/hydrology/static", json={}).json()
    assert api_client.get(f"/api/v1/fields/{f1['id']}").json()["has_hydrology"] is True

    f2 = _import_square(api_client, name="Lote 30m")
    _upload_dem(api_client, f2["id"], write_sloped_plane_dem(tmp_path / "d30.tif", pixel_m=30.0, width=74, height=74), buffer_m=100.0)
    h30 = api_client.post(f"/api/v1/fields/{f2['id']}/hydrology/static", json={}).json()
    assert h5["summary"]["mfd_mass_balance_error"] <= 1e-4
    assert h30["summary"]["mfd_mass_balance_error"] <= 1e-4


def test_e2e_t3_05_f3_x_f4_static_hydrology_point_and_mesh_sync(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, field = field_with_sloped_dem
    burn = [[[-65.696, -33.293], [-65.696, -33.298]]]
    api_client.post(
        f"/api/v1/fields/{fid}/hydrology/static",
        json={"conditioning_mode": "fill_small", "burn_lines": burn, "burn_depth_m": 0.8},
    ).raise_for_status()

    lon, lat = field["centroid"]
    pt = api_client.get(f"/api/v1/fields/{fid}/terrain/point", params={"lon": lon, "lat": lat}).json()
    for attr in ("d8_code", "d8_direction", "mfd_area_ha", "twi", "spi", "subbasin_id", "agronomic_zone_id"):
        assert pt[attr] is not None

    mesh = api_client.get(f"/api/v1/fields/{fid}/terrain/mesh?max_size=48").json()
    assert mesh["d8_code"] is not None
    assert mesh["twi"] is not None
    assert mesh["agronomic_zone_id"] is not None


def test_e2e_t3_06_f4_x_f5_preserve_vs_fill_all_runoff_retention(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    _upload_dem(api_client, f["id"], write_closed_depression_dem(tmp_path / "bowl_r.tif"))
    ev = api_client.post(
        f"/api/v1/fields/{f['id']}/hydrology/rainfall-events",
        json={"name": "Tormenta 80", "total_mm": 80.0, "source_type": "manual"},
    ).json()

    api_client.post(f"/api/v1/fields/{f['id']}/hydrology/static", json={"conditioning_mode": "preserve"}).raise_for_status()
    r_pres = api_client.post(f"/api/v1/fields/{f['id']}/hydrology/runoff-runs", json={"rainfall_event_id": ev["id"]}).json()

    api_client.post(f"/api/v1/fields/{f['id']}/hydrology/static", json={"conditioning_mode": "fill_all"}).raise_for_status()
    r_fill = api_client.post(f"/api/v1/fields/{f['id']}/hydrology/runoff-runs", json={"rainfall_event_id": ev["id"]}).json()

    assert r_pres["spatial_summary"]["potential_depression_retention_m3"] > r_fill["spatial_summary"]["potential_depression_retention_m3"]
    assert r_pres["spatial_summary"]["net_outflow_potential_m3"] <= r_fill["spatial_summary"]["net_outflow_potential_m3"]


def test_e2e_t3_07_f4_x_f5_external_inflow_buffer_runoff_supply(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    _upload_dem(api_client, f["id"], write_sloped_plane_dem(tmp_path / "ext_inf.tif"), buffer_m=300.0)
    h = api_client.post(f"/api/v1/fields/{f['id']}/hydrology/static", json={}).json()
    ev = api_client.post(
        f"/api/v1/fields/{f['id']}/hydrology/rainfall-events",
        json={"name": "Tormenta 80", "total_mm": 80.0, "source_type": "manual"},
    ).json()
    run = api_client.post(
        f"/api/v1/fields/{f['id']}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "antecedent_moisture": "wet"},
    ).json()
    sp = run["spatial_summary"]
    if h["summary"]["external_inflow_ha"] > 0:
        assert sp["external_runoff_inflow_m3"] > 0.0
    assert sp["total_runoff_supply_m3"] == pytest.approx(
        sp["field_runoff_generated_m3"] + sp["external_runoff_inflow_m3"],
        rel=0.01,
    )


def test_e2e_t3_08_f5_x_f6_csv_hyetograph_runoff_timeline_balance(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    run = _setup_csv_run(api_client, fid)
    tl = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/timeline").json()
    last = tl["frames"][-1]
    assert last["cumulative_precipitation_mm"] == pytest.approx(80.0, abs=0.05)
    assert last["cumulative_runoff_generated_mm"] == pytest.approx(run["cn_result"]["runoff_q_mm"], abs=0.05)


def test_e2e_t3_09_f5_x_f6_manual_rain_vs_csv_timeline(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    ev_man = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events",
        json={"name": "Manual 80", "total_mm": 80.0, "source_type": "manual"},
    ).json()
    r_man = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs", json={"rainfall_event_id": ev_man["id"]}).json()
    r_csv = _setup_csv_run(api_client, fid)

    tl_man = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{r_man['id']}/timeline").json()
    tl_csv = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{r_csv['id']}/timeline").json()

    assert tl_man["has_time_series"] is False and tl_man["frames"] == [] and len(tl_man["warnings"]) >= 1
    assert tl_csv["has_time_series"] is True and len(tl_csv["frames"]) > 8


def test_e2e_t3_10_f5_x_f7_amc_medium_vs_wet_simulate_2d(api_client: TestClient, tmp_path: Path):
    f = _import_square(api_client)
    _upload_dem(api_client, f["id"], write_sloped_with_micro_depression_dem(tmp_path / "amc2d.tif"))
    ev = api_client.post(f"/api/v1/fields/{f['id']}/hydrology/rainfall-events/sample").json()
    r_med = api_client.post(
        f"/api/v1/fields/{f['id']}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "antecedent_moisture": "medium"},
    ).json()
    r_wet = api_client.post(
        f"/api/v1/fields/{f['id']}/hydrology/runoff-runs",
        json={"rainfall_event_id": ev["id"], "antecedent_moisture": "wet"},
    ).json()

    s_med = api_client.post(f"/api/v1/fields/{f['id']}/hydrology/runoff-runs/{r_med['id']}/simulate-2d", json={}).json()["hydrodynamic_2d_summary"]
    s_wet = api_client.post(f"/api/v1/fields/{f['id']}/hydrology/runoff-runs/{r_wet['id']}/simulate-2d", json={}).json()["hydrodynamic_2d_summary"]

    assert s_wet["max_water_depth_in_field_m"] >= s_med["max_water_depth_in_field_m"]
    assert s_wet["ponded_area_in_field_ha"] >= s_med["ponded_area_in_field_ha"]


def test_e2e_t3_11_f6_x_f7_timeline_vs_simulate_2d_outputs(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, field = field_with_sloped_dem
    run = _setup_csv_run(api_client, fid)
    tl = api_client.get(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/timeline").json()
    assert "active_transit_lamina_mm" in tl["frames"][0]
    assert "water_depth_m" not in tl["frames"][0]

    api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/simulate-2d", json={}).raise_for_status()
    lon, lat = field["centroid"]
    pt = api_client.get(f"/api/v1/fields/{fid}/terrain/point", params={"lon": lon, "lat": lat}).json()
    assert pt["water_depth_m"] is not None
    assert pt["velocity_m_s"] is not None


def test_e2e_t3_12_f7_x_f4_f3_observations_2d_and_point_sync(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, field = field_with_sloped_dem
    lon, lat = field["centroid"]
    api_client.post(
        f"/api/v1/fields/{fid}/hydrology/observations",
        json={"observation_type": "culvert", "lon": lon, "lat": lat, "notes": "Alcantarilla", "value": 0.5, "units": "m"},
    ).raise_for_status()
    api_client.post(
        f"/api/v1/fields/{fid}/hydrology/observations",
        json={"observation_type": "channel", "lon": lon + 0.0004, "lat": lat, "notes": "Canal", "value": 0.4, "units": "m"},
    ).raise_for_status()
    run = _setup_csv_run(api_client, fid)
    run2d = api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/simulate-2d", json={}).json()
    assert run2d["hydrodynamic_2d_summary"]["hydraulic_structures_applied"] >= 2

    pt = api_client.get(f"/api/v1/fields/{fid}/terrain/point", params={"lon": lon, "lat": lat}).json()
    assert pt["water_depth_m"] is not None
    assert pt["velocity_m_s"] is not None
    assert pt["agronomic_zone_id"] in (1, 2, 3, 4)


def test_e2e_t3_13_f4_x_f8_static_hydrology_to_toolkit_preserves_timestamp(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    h_before = api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).json()
    time.sleep(1.1)
    tk = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).json()
    h_after = api_client.get(f"/api/v1/fields/{fid}/hydrology").json()

    assert h_after["processed_at"] == h_before["processed_at"]
    assert tk["contour_terraces"]["terraces_geojson"]["type"] == "FeatureCollection"
    assert len(tk["ndvi_vigor_monitor"]["ndvi_by_agronomic_zone"]) == 4


def test_e2e_t3_14_f5_f7_x_f8_runoff_2d_and_toolkit_mesh_coexistence(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    run = _setup_csv_run(api_client, fid)
    api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/simulate-2d", json={}).raise_for_status()
    api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).raise_for_status()

    mesh = api_client.get(f"/api/v1/fields/{fid}/terrain/mesh?max_size=48").json()
    assert mesh["water_depth_m"] is not None
    assert mesh["velocity_m_s"] is not None
    assert mesh["soil_loss_t_ha"] is not None
    assert mesh["ndvi"] is not None


def test_e2e_t3_15_f9_x_f8_degraded_nasa_and_cloudy_s2_toolkit(
    field_with_sloped_dem: tuple[str, dict],
    api_client: TestClient,
    mock_external_network: MockNetworkController,
):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    mock_external_network.nasa_mode = "down"
    mock_external_network.stac_mode = "cloudy"

    r = api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={})
    assert r.status_code == 200
    tk = r.json()
    # Physical & INTA tools still work cleanly
    assert tk["erosion_usle"]["mean_soil_loss_t_ha"] >= 0.0
    assert tk["contour_terraces"]["soil_loss_after_t_ha"] <= tk["contour_terraces"]["soil_loss_before_t_ha"]
    assert tk["seeding_calculator_inta"]["seeds_to_sow_ha"] > 0
    assert tk["rotation_comparator_3yr"]["delta_b_vs_a"]["cover_gain_pct"] > 0
    # Satellite tools degrade cleanly without fake data
    assert tk["ndvi_vigor_monitor"]["is_satellite_observed"] is False
    assert tk["ndvi_vigor_monitor"].get("scene_id") != "synthetic-ecohydro-proxy"
    assert "calibrada" not in tk["water_balance_monthly"]["source"].lower()


def test_e2e_t3_16_f8_x_f10_toolkit_to_exports(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    api_client.post(f"/api/v1/fields/{fid}/hydrology/static", json={}).raise_for_status()
    api_client.post(f"/api/v1/fields/{fid}/hydrology/toolkit/run", json={}).raise_for_status()

    gj = api_client.get(f"/api/v1/fields/{fid}/hydrology/export/geojson")
    html = api_client.get(f"/api/v1/fields/{fid}/hydrology/export/report")
    assert gj.status_code == 200 and html.status_code == 200
    assert "limitaciones" in html.text.lower()


def test_e2e_t3_17_f7_x_f10_observations_and_2d_to_exports(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, field = field_with_sloped_dem
    lon, lat = field["centroid"]
    api_client.post(
        f"/api/v1/fields/{fid}/hydrology/observations",
        json={"observation_type": "water_depth", "lon": lon, "lat": lat, "notes": "Tirante medido", "value": 0.22, "units": "m"},
    ).raise_for_status()
    run = _setup_csv_run(api_client, fid)
    api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run['id']}/simulate-2d", json={}).raise_for_status()

    gj = api_client.get(f"/api/v1/fields/{fid}/hydrology/export/geojson").json()
    obs_feats = [ft for ft in gj["features"] if ft["properties"]["layer"] == "field_observation"]
    assert len(obs_feats) == 1
    assert obs_feats[0]["properties"]["notes"] == "Tirante medido"

    html = api_client.get(f"/api/v1/fields/{fid}/hydrology/export/report").text
    assert "Tirante medido" in html


def test_e2e_t3_18_f5_f7_x_f10_activate_run_b_updates_exports(field_with_sloped_dem: tuple[str, dict], api_client: TestClient):
    fid, _ = field_with_sloped_dem
    ev = api_client.post(f"/api/v1/fields/{fid}/hydrology/rainfall-events/sample").json()
    run_a = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"name": "Escenario A Seco", "rainfall_event_id": ev["id"], "antecedent_moisture": "dry"},
    ).json()
    run_b = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"name": "Escenario B Humedo", "rainfall_event_id": ev["id"], "antecedent_moisture": "wet"},
    ).json()

    api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run_a['id']}/activate").raise_for_status()
    gj_a = api_client.get(f"/api/v1/fields/{fid}/hydrology/export/geojson").json()
    assert gj_a["rotaterra_metadata"]["active_runoff_scenario"]["name"] == "Escenario A Seco"

    api_client.post(f"/api/v1/fields/{fid}/hydrology/runoff-runs/{run_b['id']}/activate").raise_for_status()
    gj_b = api_client.get(f"/api/v1/fields/{fid}/hydrology/export/geojson").json()
    assert gj_b["rotaterra_metadata"]["active_runoff_scenario"]["name"] == "Escenario B Humedo"
