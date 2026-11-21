"""Pruebas unitarias para el Indicador de Confianza y el Motor de Escenarios (SDD-003 / Tarea 2.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from geoprocessing.hydrology.confidence import compute_confidence_indicator
from geoprocessing.rainfall.nrcs_cn import compare_runoff_scenarios, compute_nrcs_cn
from services.api.app.core import config
from services.api.app.main import app
from services.api.app.services import store, terrain


def test_confidence_indicator_flat_copernicus():
    """En llanura plana (<0.3%) con Copernicus 30 m, el nivel debe ser 'bajo'
    y la justificación debe advertir sobre el error vertical de ±2 m en micro-escurrimientos.
    """
    ci = compute_confidence_indicator(
        source_id="copernicus_glo30",
        resolution_m=30.0,
        mean_slope_pct=0.18,  # llanura plana
        soil_source="inta_regional",
        rain_source_type="regional_design",
    )
    assert ci["level"] == "bajo"
    assert ci["score"] < 0.60
    assert any("±2 m" in r for r in ci["reasons"])
    assert "30 m" in ci["relief_note"]


def test_confidence_indicator_high_res_lidar():
    """Con DEM de dron o LiDAR local (<= 2 m) y pluviómetro local, la confianza es 'alta'."""
    ci = compute_confidence_indicator(
        source_id="drone",
        resolution_m=1.5,
        mean_slope_pct=1.5,
        soil_source="local_survey",
        rain_source_type="gauge",
    )
    assert ci["level"] == "alto"
    assert ci["score"] >= 0.85
    assert any("submétrico" in r for r in ci["reasons"])
    assert "Pluviómetro local" in ci["rain_note"]


def test_confidence_indicator_nasa_power_satellite():
    """Lluvia satelital NASA POWER refleja baja resolución espacial (~55 km)."""
    ci = compute_confidence_indicator(
        source_id="copernicus_glo30",
        resolution_m=30.0,
        mean_slope_pct=1.2,
        soil_source="inta_regional",
        rain_source_type="nasa_power",
    )
    assert ci["level"] in ("medio", "bajo")
    assert "55 km" in ci["rain_note"]
    assert any("55 km" in r for r in ci["reasons"])


def test_compare_scenarios_deltas_and_summary():
    """Verifica que el comparador de escenarios devuelva todos los deltas de SDD-003
    (volumen m³, %, ha anegadas, t/ha suelo) y un resumen agronómico claro.
    """
    # Escenario A: 80 mm Siembra Directa
    cn_a = compute_nrcs_cn(precipitation_mm=80.0, cn_ii_base=72.0, antecedent_moisture="medium")
    run_a = {
        "id": "run-a",
        "name": "80 mm · Siembra Directa continua",
        "cn_result": cn_a.to_dict(),
        "spatial_summary": {
            "runoff_generated_q_mm": cn_a.runoff_q_mm,
            "field_runoff_generated_m3": 15000.0,
            "external_runoff_inflow_m3": 1200.0,
            "total_runoff_supply_m3": 16200.0,
            "potential_depression_retention_m3": 2500.0,
            "net_outflow_potential_m3": 13700.0,
            "high_concentration_area_ha": 1.2,
        },
        "hydrodynamic_2d_summary": {"ponded_area_in_field_ha": 2.1},
    }

    # Escenario B: 80 mm Labranza Convencional (mayor CN)
    cn_b = compute_nrcs_cn(precipitation_mm=80.0, cn_ii_base=82.0, antecedent_moisture="medium")
    run_b = {
        "id": "run-b",
        "name": "80 mm · Convencional con labranza",
        "cn_result": cn_b.to_dict(),
        "spatial_summary": {
            "runoff_generated_q_mm": cn_b.runoff_q_mm,
            "field_runoff_generated_m3": 27450.0,
            "external_runoff_inflow_m3": 1200.0,
            "total_runoff_supply_m3": 28650.0,
            "potential_depression_retention_m3": 2500.0,
            "net_outflow_potential_m3": 26150.0,
            "high_concentration_area_ha": 3.8,
        },
        "hydrodynamic_2d_summary": {"ponded_area_in_field_ha": 4.9},
    }

    comp = compare_runoff_scenarios(run_a, run_b)
    assert comp["run_a_id"] == "run-a"
    assert comp["run_b_id"] == "run-b"
    assert comp["delta_field_runoff_generated_m3"] == pytest.approx(12450.0)
    assert comp["delta_runoff_volume_m3"] == pytest.approx(12450.0)
    assert comp["delta_ponded_area_ha"] == pytest.approx(2.8)
    assert comp["delta_soil_loss_t_ha"] > 0
    assert "escorrentía" in comp["summary_text"]
    assert "erosión" in comp["summary_text"]


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "runs")
    monkeypatch.setattr(store, "DATA_DIR", tmp_path / "runs")
    terrain._cargar.cache_clear()
    return TestClient(app)


def test_api_scenarios_compare_and_presets(api_client: TestClient):
    """Prueba de integración API para el endpoint de comparación y los 3 presets estándar."""
    # 1. Crear lote sintético
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-65.31, -33.66],
                            [-65.30, -33.66],
                            [-65.30, -33.65],
                            [-65.31, -33.65],
                            [-65.31, -33.66],
                        ]
                    ],
                },
                "properties": {"name": "Lote Test Escenarios"},
            }
        ],
    }
    r_imp = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("lote.geojson", str(geojson).replace("'", '"').encode("utf-8"), "application/json")},
    )
    assert r_imp.status_code == 201
    field_id = r_imp.json()["fields"][0]["id"]

    # 2. Procesar DEM con Copernicus 30m (usará fixture o backup offline)
    r_dem = api_client.post(
        f"/api/v1/fields/{field_id}/terrain/process",
        data={"source_id": "copernicus_glo30", "buffer_m": "300"},
    )
    assert r_dem.status_code == 200

    # 3. Simular presets estándar (Conservador, Medio, Crítico)
    r_presets = api_client.post(f"/api/v1/fields/{field_id}/scenarios/simulate-presets")
    assert r_presets.status_code == 201
    presets = r_presets.json()
    assert len(presets) == 3

    # Verificar que cada preset tenga su indicador de confianza
    for p in presets:
        assert p["confidence"] is not None
        assert p["confidence"]["level"] in ("alto", "medio", "bajo")
        assert len(p["confidence"]["reasons"]) > 0

    run_conservador = presets[2]  # insertados en orden
    run_critico = presets[0]

    # 4. Comparar Conservador vs Crítico via nuevo endpoint /scenarios/compare
    r_comp = api_client.get(
        f"/api/v1/fields/{field_id}/scenarios/compare",
        params={"run_a_id": run_conservador["id"], "run_b_id": run_critico["id"]},
    )
    assert r_comp.status_code == 200
    comp_data = r_comp.json()
    assert comp_data["run_a_id"] == run_conservador["id"]
    assert comp_data["run_b_id"] == run_critico["id"]
    assert "delta_runoff_volume_m3" in comp_data
    assert "delta_ponded_area_ha" in comp_data
    assert "delta_soil_loss_t_ha" in comp_data
    assert len(comp_data["summary_text"]) > 10

    # 5. Verificar que el endpoint también responde en /api/fields/{id}/scenarios/compare
    r_comp_alt = api_client.get(
        f"/api/fields/{field_id}/scenarios/compare",
        params={"run_a_id": run_conservador["id"], "run_b_id": run_critico["id"]},
    )
    assert r_comp_alt.status_code == 200
