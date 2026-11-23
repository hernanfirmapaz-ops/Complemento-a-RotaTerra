"""Tests de cálculo de superficie anegable en % del lote según Issue #85.

Criterios de aceptación:
- Test de API: lote sintético de 100 ha con 25 ha anegables -> 25,0 %.
- Caso borde: si falta el área del lote o el área anegable -> null y 'sin dato'.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from services.api.app.main import app
from services.api.app.services import store
from services.api.app.services.hydrology import compute_ponded_area_pct

client = TestClient(app)


def test_compute_ponded_area_pct_formula():
    # Criterio de aceptación explícito: lote de 100 ha con 25 ha anegables -> 25.0 %
    assert compute_ponded_area_pct(25.0, 100.0) == 25.0

    # Lote de 222 ha con 42 ha anegables -> 18.9 %
    assert compute_ponded_area_pct(42.0, 222.0) == 18.9

    # 0 ha anegables
    assert compute_ponded_area_pct(0.0, 100.0) == 0.0

    # Casos nulos o inválidos -> None
    assert compute_ponded_area_pct(None, 100.0) is None
    assert compute_ponded_area_pct(25.0, None) is None
    assert compute_ponded_area_pct(None, None) is None
    assert compute_ponded_area_pct(25.0, 0.0) is None
    assert compute_ponded_area_pct(25.0, -10.0) is None


def test_api_runoff_runs_returns_ponded_area_pct_and_field_ha(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)

    # 1. Crear lote sintético de 100 ha
    field_id = store.new_id()
    field_doc = {
        "id": field_id,
        "name": "Lote Sintético 100 ha",
        "area_ha": 100.0,
        "utm_epsg": 32720,
        "centroid": [-65.46, -33.67],
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-65.46, -33.67],
                    [-65.45, -33.67],
                    [-65.45, -33.66],
                    [-65.46, -33.66],
                    [-65.46, -33.67],
                ]
            ],
        },
        "created_at": store.now_iso(),
    }
    store.save_field(field_doc)

    # 2. Guardar una corrida con 25 ha anegables en hydrodynamic_2d_summary
    run_doc = {
        "id": "run_sim_25ha",
        "field_id": field_id,
        "name": "Tormenta 80 mm",
        "rainfall_event_id": "ev_1",
        "rainfall_event_name": "Lluvia 80 mm",
        "model": "event_runoff_nrcs_cn_mfd_v1",
        "processing_version": "1.0",
        "created_at": store.now_iso(),
        "is_active": True,
        "field_conditions": {},
        "cn_result": {
            "precipitation_mm": 80.0,
            "cn_ii_base": 75.0,
            "cn_effective": 75.0,
            "antecedent_moisture": "amc_ii",
            "lambda_ratio": 0.2,
            "potential_retention_s_mm": 84.67,
            "initial_abstraction_ia_mm": 16.93,
            "infiltration_after_ia_f_mm": 35.0,
            "total_retention_losses_mm": 51.93,
            "runoff_q_mm": 28.07,
            "runoff_coefficient": 0.35,
            "mass_balance_error_mm": 0.0,
        },
        "spatial_summary": {
            "runoff_generated_q_mm": 28.07,
            "field_runoff_generated_m3": 28070.0,
            "external_runoff_inflow_m3": 0.0,
            "total_runoff_supply_m3": 28070.0,
            "potential_depression_retention_m3": 500.0,
            "net_outflow_potential_m3": 27570.0,
            "peak_discharge_m3_s": 1.2,
            "max_cell_cumulative_runoff_m3": 120.0,
            "max_cell_runoff_load_mm": 32.0,
            "mean_cell_runoff_load_mm": 28.07,
            "high_concentration_area_ha": 3.5,
        },
        "hydrodynamic_2d_summary": {
            "ponded_area_in_field_ha": 25.0,
            "ponded_retained_volume_in_field_m3": 5200.0,
        },
        "assumptions_and_notes": [],
        "warnings": [],
        "limitations": [],
    }
    store.save_runoff_runs(field_id, [run_doc])

    # 3. Consultar endpoint GET /api/v1/fields/{field_id}/hydrology/runoff-runs
    res = client.get(f"/api/v1/fields/{field_id}/hydrology/runoff-runs")
    assert res.status_code == 200
    runs = res.json()
    assert len(runs) == 1
    run_out = runs[0]

    # Verificar que el porcentaje devuelto por la API sea 25.0 % en el campo único ponded_area_pct
    assert run_out["ponded_area_pct"] == 25.0
    assert run_out["field_area_ha"] == 100.0


def test_api_runoff_runs_null_when_missing_2d(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)

    field_id = store.new_id()
    field_doc = {
        "id": field_id,
        "name": "Lote 50 ha",
        "area_ha": 50.0,
        "utm_epsg": 32720,
        "centroid": [-65.46, -33.67],
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-65.46, -33.67],
                    [-65.45, -33.67],
                    [-65.45, -33.66],
                    [-65.46, -33.66],
                    [-65.46, -33.67],
                ]
            ],
        },
        "created_at": store.now_iso(),
    }
    store.save_field(field_doc)

    # Corrida sin hydrodynamic_2d_summary
    run_doc = {
        "id": "run_no_2d",
        "field_id": field_id,
        "name": "Corrida sin 2D",
        "rainfall_event_id": "ev_1",
        "rainfall_event_name": "Lluvia 50 mm",
        "model": "event_runoff_nrcs_cn_mfd_v1",
        "processing_version": "1.0",
        "created_at": store.now_iso(),
        "is_active": True,
        "field_conditions": {},
        "cn_result": {
            "precipitation_mm": 50.0,
            "cn_ii_base": 70.0,
            "cn_effective": 70.0,
            "antecedent_moisture": "amc_ii",
            "lambda_ratio": 0.2,
            "potential_retention_s_mm": 108.86,
            "initial_abstraction_ia_mm": 21.77,
            "infiltration_after_ia_f_mm": 20.0,
            "total_retention_losses_mm": 41.77,
            "runoff_q_mm": 8.23,
            "runoff_coefficient": 0.16,
            "mass_balance_error_mm": 0.0,
        },
        "spatial_summary": {
            "runoff_generated_q_mm": 8.23,
            "field_runoff_generated_m3": 4115.0,
            "external_runoff_inflow_m3": 0.0,
            "total_runoff_supply_m3": 4115.0,
            "potential_depression_retention_m3": 100.0,
            "net_outflow_potential_m3": 4015.0,
            "peak_discharge_m3_s": 0.5,
            "max_cell_cumulative_runoff_m3": 50.0,
            "max_cell_runoff_load_mm": 10.0,
            "mean_cell_runoff_load_mm": 8.23,
            "high_concentration_area_ha": 1.2,
        },
        "hydrodynamic_2d_summary": None,
        "assumptions_and_notes": [],
        "warnings": [],
        "limitations": [],
    }
    store.save_runoff_runs(field_id, [run_doc])

    res = client.get(f"/api/v1/fields/{field_id}/hydrology/runoff-runs")
    assert res.status_code == 200
    runs = res.json()
    assert runs[0]["ponded_area_pct"] is None
    assert runs[0]["field_area_ha"] == 50.0
