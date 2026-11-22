"""Tests de integración de la API FastAPI (Fase 0) usando un DEM sintético etiquetado."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from geoprocessing import net as geonet
from geoprocessing.tests.fixtures.synthetic_dem import (
    synthetic_square_field_geojson,
    write_synthetic_inclined_plane_utm,
)
from services.api.app.core import config
from services.api.app.main import app
from services.api.app.services import store, terrain

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "geoprocessing" / "tests" / "fixtures"
NASA_FIXTURE_PATH = FIXTURES_DIR / "nasa_power_daily_san_luis.json"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "runs")
    monkeypatch.setattr(store, "DATA_DIR", tmp_path / "runs")
    terrain._cargar.cache_clear()
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_nasa_power_network(monkeypatch: pytest.MonkeyPatch):
    """Simula la API de NASA POWER con MockTransport cargando el fixture grabado de San Luis."""
    with open(NASA_FIXTURE_PATH, encoding="utf-8") as f:
        fixture_payload = json.load(f)

    real_transport = httpx.HTTPTransport(verify=geonet.ssl_context())

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "power.larc.nasa.gov" in url_str:
            return httpx.Response(200, json=fixture_payload)
        try:
            return real_transport.handle_request(request)
        except Exception:
            return httpx.Response(503)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    monkeypatch.setattr(geonet, "_cliente", mock_client)
    monkeypatch.setattr(geonet, "client", lambda: mock_client)
    yield
    mock_client.close()
    monkeypatch.setattr(geonet, "_cliente", None)


def test_health_and_full_phase0_flow(client: TestClient, tmp_path: Path):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["phase"] == "fase-5-suite-completa-rotaterra"

    # 1. Importar lote sintético
    geojson_bytes = json.dumps(synthetic_square_field_geojson()).encode("utf-8")
    r = client.post(
        "/api/v1/fields/import",
        files={"file": ("lote_sintetico.geojson", geojson_bytes, "application/geo+json")},
        data={"default_name": "Lote Sintético"},
    )
    assert r.status_code == 201, r.text
    field = r.json()["fields"][0]
    field_id = field["id"]
    assert field["utm_epsg"] == 32720
    assert field["has_terrain"] is False

    # 2. Subir DEM sintético (plano inclinado 3% E, 4% S -> 5.0% pendiente total)
    dem_path = write_synthetic_inclined_plane_utm(
        tmp_path / "dem_sintetico.tif", slope_east=0.03, slope_south=0.04, pixel_m=10.0, width=220, height=220
    )
    with dem_path.open("rb") as fh:
        r = client.post(
            f"/api/v1/fields/{field_id}/terrain/process",
            files={"file": ("dem_sintetico.tif", fh, "image/tiff")},
            data={
                "source_id": "upload",
                "buffer_m": "100",
                "source_name": "DEM Sintético Plano Inclinado (TEST)",
                "surface_type": "DTM",
                "vertical_datum": "EGM2008",
                "vertical_accuracy_m": "0.1",
                "acquisition_date": "2026-01-01",
            },
        )
    assert r.status_code == 200, r.text
    terr = r.json()
    assert terr["quality"]["pixel_size_m"] == 10.0
    assert terr["quality"]["cells_in_field"] > 500
    assert terr["source"]["surface_type"] == "DTM"

    # 3. Malla 3D
    r = client.get(f"/api/v1/fields/{field_id}/terrain/mesh?max_size=120")
    assert r.status_code == 200
    malla = r.json()
    assert malla["rows"] > 10 and malla["cols"] > 10
    assert len(malla["z"]) == malla["rows"] * malla["cols"]
    assert len(malla["boundary"]) == 1

    # 4. Consulta de punto en el centroide: pendiente debe ser 5.0 %
    lon, lat = field["centroid"]
    r = client.get(f"/api/v1/fields/{field_id}/terrain/point", params={"lon": lon, "lat": lat})
    assert r.status_code == 200
    pt = r.json()
    assert pt["inside_field"] is True
    assert pt["slope_pct"] == pytest.approx(5.0, abs=0.05)

    # 5. Perfil altimétrico
    oeste, sur, este, norte = field["bbox"]
    r = client.post(
        f"/api/v1/fields/{field_id}/terrain/profile",
        json={"coordinates": [[oeste, sur], [este, norte]]},
    )
    assert r.status_code == 200
    pf = r.json()
    assert pf["summary"]["length_m"] > 1000
    assert pf["summary"]["valid_samples"] == pf["summary"]["samples"]

    # 6. Curvas de nivel e Hidrología estática (Fase 1)
    r = client.get(f"/api/v1/fields/{field_id}/terrain/contours?interval_m=5")
    assert r.status_code == 200
    assert len(r.json()["features"]) >= 3

    r = client.post(
        f"/api/v1/fields/{field_id}/hydrology/static",
        json={
            "conditioning_mode": "fill_small",
            "max_fill_depth_m": 0.35,
            "max_fill_area_m2": 4500.0,
            "mfd_exponent": 1.1,
            "routing_basis": "MFD",
        },
    )
    assert r.status_code == 200, r.text
    hyd = r.json()
    assert hyd["summary"]["mfd_mass_balance_error"] < 1e-5
    assert hyd["summary"]["max_mfd_area_in_field_ha"] > 0.5
    assert len(hyd["drainage_network"]["features"]) > 0
    assert len(hyd["outlets"]) >= 1

    # 7. El punto y la malla ahora incluyen atributos hidrológicos de Fase 1
    r = client.get(f"/api/v1/fields/{field_id}/terrain/point", params={"lon": lon, "lat": lat})
    assert r.status_code == 200
    pt_hyd = r.json()
    assert pt_hyd["d8_direction"] == "NO"
    assert pt_hyd["mfd_area_ha"] is not None and pt_hyd["mfd_area_ha"] > 0

    r = client.get(f"/api/v1/fields/{field_id}/terrain/mesh?max_size=120")
    assert r.status_code == 200
    malla_hyd = r.json()
    assert malla_hyd["mfd_area_ha"] is not None
    assert len(malla_hyd["mfd_area_ha"]) == malla_hyd["rows"] * malla_hyd["cols"]

    # 8. Fase 2: Eventos de lluvia (manual + CSV de muestra), corridas NRCS-CN y comparación de escenarios
    r = client.post(
        f"/api/v1/fields/{field_id}/hydrology/rainfall-events",
        json={"name": "Lluvia moderada 45 mm", "total_mm": 45.0, "source_type": "manual"},
    )
    assert r.status_code == 201, r.text
    ev_manual = r.json()

    r = client.post(f"/api/v1/fields/{field_id}/hydrology/rainfall-events/sample")
    assert r.status_code == 201, r.text
    ev_csv = r.json()
    assert ev_csv["has_time_series"] is True
    assert ev_csv["total_mm"] == pytest.approx(80.0)

    # Perfil de suelo local para cálculo de K de Wischmeier en USLE
    (store.field_dir(field_id) / "soil.json").write_text(
        json.dumps({"sand_pct": 40.0, "silt_pct": 40.0, "clay_pct": 20.0, "quality": "confiable"}),
        encoding="utf-8",
    )

    # Corrida A (45 mm, suelo B, humedad media)
    r = client.post(
        f"/api/v1/fields/{field_id}/hydrology/runoff-runs",
        json={
            "name": "Escenario A: 45 mm · Suelo B · AMC II",
            "rainfall_event_id": ev_manual["id"],
            "soil_group": "B",
            "cover_code": "soja_maiz_sd_buena",
            "antecedent_moisture": "medium",
        },
    )
    assert r.status_code == 201, r.text
    run_a = r.json()

    # Corrida B (80 mm CSV, suelo C, humedad húmeda AMC III)
    r = client.post(
        f"/api/v1/fields/{field_id}/hydrology/runoff-runs",
        json={
            "name": "Escenario B: 80 mm · Suelo C · AMC III",
            "rainfall_event_id": ev_csv["id"],
            "soil_group": "C",
            "cover_code": "barbecho_suelo_desnudo",
            "antecedent_moisture": "wet",
        },
    )
    assert r.status_code == 201, r.text
    run_b = r.json()
    assert run_b["cn_result"]["runoff_q_mm"] > run_a["cn_result"]["runoff_q_mm"]

    # Comparación entre Escenario A y Escenario B
    r = client.get(
        f"/api/v1/fields/{field_id}/hydrology/compare",
        params={"run_a": run_a["id"], "run_b": run_b["id"]},
    )
    assert r.status_code == 200
    comp = r.json()
    assert comp["delta_runoff_q_mm"] > 0
    assert comp["delta_field_runoff_generated_m3"] > 0

    # La malla y el punto ahora incluyen la carga de escorrentía (runoff_load_mm) de la corrida activa
    r = client.get(f"/api/v1/fields/{field_id}/terrain/point", params={"lon": lon, "lat": lat})
    assert r.status_code == 200
    assert r.json()["runoff_load_mm"] is not None

    # 9. Fase 3: Línea de tiempo por intervalos sobre el hietograma CSV, partículas 3D, observaciones y exportación
    r = client.get(f"/api/v1/fields/{field_id}/hydrology/runoff-runs/{run_b['id']}/timeline")
    assert r.status_code == 200, r.text
    tl = r.json()
    assert tl["has_time_series"] is True
    assert tl["total_steps"] == 12
    assert tl["max_mass_balance_error_mm"] < 1e-5
    assert len(tl["particle_paths"]) > 0

    # Registrar observación de campo (CU-06)
    r = client.post(
        f"/api/v1/fields/{field_id}/hydrology/observations",
        json={
            "observation_type": "ponding",
            "lon": lon,
            "lat": lat,
            "notes": "Charco observado 2 horas después de lluvia de 80 mm",
            "value": 0.18,
            "units": "m",
        },
    )
    assert r.status_code == 201, r.text
    obs = r.json()
    assert obs["elevation_m"] is not None

    # Exportar paquete GeoJSON e informe técnico HTML
    r = client.get(f"/api/v1/fields/{field_id}/hydrology/export/geojson")
    assert r.status_code == 200
    pkg = r.json()
    assert pkg["type"] == "FeatureCollection"
    assert pkg["rotaterra_metadata"]["field_id"] == field_id
    layers_exported = {f["properties"]["layer"] for f in pkg["features"]}
    assert {"field_boundary", "potential_drainage_network", "field_observation"} <= layers_exported

    r = client.get(f"/api/v1/fields/{field_id}/hydrology/export/report")
    assert r.status_code == 200
    assert "Informe Técnico Topográfico e Hidrológico" in r.text

    # 10. Fase 4 y Fase 5: Solver hidrodinámico 2D (Manning) + Zonificación hidro-agronómica RotaTerra
    r = client.post(
        f"/api/v1/fields/{field_id}/hydrology/runoff-runs/{run_b['id']}/simulate-2d",
        json={"manning_n": 0.08, "ponding_threshold_m": 0.04, "recession_minutes": 15},
    )
    assert r.status_code == 200, r.text
    run_2d = r.json()
    assert run_2d["hydrodynamic_2d_summary"]["mass_balance_relative_error"] < 1e-4
    assert run_2d["hydrodynamic_2d_summary"]["max_water_depth_in_field_m"] > 0.0
    assert len(run_2d["agronomic_zonation"]["zones"]) == 4

    # El punto y la malla ahora exponen water_depth_m, velocity_m_s, twi, spi y agronomic_zone_id
    r = client.get(f"/api/v1/fields/{field_id}/terrain/point", params={"lon": lon, "lat": lat})
    assert r.status_code == 200
    pt_full = r.json()
    assert pt_full["water_depth_m"] is not None
    assert pt_full["velocity_m_s"] is not None
    assert pt_full["twi"] is not None
    assert pt_full["agronomic_zone_id"] in (1, 2, 3, 4)

    # 11. Paquete de 8 herramientas complementarias (/toolkit/run)
    r = client.post(
        f"/api/v1/fields/{field_id}/hydrology/toolkit/run",
        json={"soil_group": "B", "cover_code": "soja_maiz_sd_buena", "storm_precipitation_mm": 80.0},
    )
    assert r.status_code == 200, r.text
    tk = r.json()
    assert tk["erosion_usle"]["mean_soil_loss_t_ha"] > 0
    assert tk["contour_terraces"]["erosion_reduction_pct"] > 0
    assert len(tk["water_balance_monthly"]["months"]) == 12
    assert tk["seeding_calculator_inta"]["seeds_to_sow_ha"] > 0
    assert tk["rotation_comparator_3yr"]["delta_b_vs_a"]["soil_saved_by_b_tons"] > 0
    assert tk["ndvi_vigor_monitor"]["status"] in ("available", "unavailable")
    if tk["ndvi_vigor_monitor"]["status"] == "available":
        assert tk["ndvi_vigor_monitor"]["mean_ndvi_in_field"] > 0
    assert tk["frost_risk_sowing"]["frost_free_period_days"] >= 120


def test_water_balance_offline_without_network_drops_series(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Verifica que sin conexión a internet no se fabriquen datos sintéticos:
    el balance hídrico mensual devuelve months == [] y calidad descartada.
    """
    # 1. Simular falla total de red (sin conexión a internet)
    def offline_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network unreachable (offline test)")

    offline_client = httpx.Client(transport=httpx.MockTransport(offline_handler))
    monkeypatch.setattr(geonet, "_cliente", offline_client)
    monkeypatch.setattr(geonet, "client", lambda: offline_client)

    # 2. Importar lote sintético y preparar terreno + hidrología
    geojson_bytes = json.dumps(synthetic_square_field_geojson()).encode("utf-8")
    r = client.post(
        "/api/v1/fields/import",
        files={"file": ("lote_offline.geojson", geojson_bytes, "application/geo+json")},
        data={"default_name": "Lote Offline"},
    )
    assert r.status_code == 201
    field_id = r.json()["fields"][0]["id"]

    write_synthetic_inclined_plane_utm(
        tmp_path / "runs" / field_id / "dem_utm.tif", pixel_m=20.0, width=80, height=80
    )
    meta = {
        "field_id": field_id,
        "processed_at": store.now_iso(),
        "source": {
            "source_id": "synthetic_dem_for_tests",
            "source_name": "DEM sintético plano inclinado",
            "surface_type": "DTM",
            "vertical_datum": "EGM96",
            "vertical_accuracy_m": 0.0,
            "acquisition_start": "2026-01-01",
            "acquisition_end": "2026-01-01",
        },
        "quality": {
            "source_id": "synthetic_dem_for_tests",
            "pixel_size_m": 20.0,
            "cells_in_field": 6400,
            "elevation_field": {"min": 100.0, "max": 140.0, "range": 40.0},
            "warnings": [],
        },
        "warnings": [],
    }
    store.save_terrain(field_id, meta)
    client.post(f"/api/v1/fields/{field_id}/hydrology/static", json={})

    # 3. Ejecutar toolkit sin red
    r = client.post(
        f"/api/v1/fields/{field_id}/hydrology/toolkit/run",
        json={"soil_group": "B", "cover_code": "soja_maiz_sd_buena", "storm_precipitation_mm": 80.0},
    )
    assert r.status_code == 200, r.text
    tk = r.json()

    wb = tk["water_balance_monthly"]
    assert wb["status"] == "unavailable"
    assert wb["months"] == []
    assert wb["annual_precipitation_mm"] == 0.0
    assert "No disponible - sin conexión" in wb["source"]
    assert any("descartada por falta de conectividad" in w for w in tk["warnings"])
