"""Tests para verificar que eventos de lluvia menores a 1 mm no se simulen como 1 mm

(Issue #36 / Auditoría 21/11/2026).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.e2e.fixtures import REPO_ROOT


def test_app_tsx_does_not_use_math_max_1_for_rain_event():
    """Verifica que App.tsx no fuerce Math.max(1.0, res.event.total_mm) inventando 1 mm de lluvia

    cuando el evento real fue menor a 1 mm (por ejemplo 0.3 mm), y que no simule.
    """
    app_tsx_path = REPO_ROOT / "apps" / "web" / "src" / "App.tsx"
    assert app_tsx_path.exists(), f"No se encontró {app_tsx_path}"
    content = app_tsx_path.read_text(encoding="utf-8")

    # 1. No debe forzar Math.max(1.0, res.event.total_mm)
    assert "Math.max(1.0, res.event.total_mm)" not in content, (
        "App.tsx todavía contiene 'Math.max(1.0, res.event.total_mm)', falseando eventos < 1 mm."
    )

    # 2. Con menos de 1 mm, debe mostrar el mensaje exacto y no simular
    assert "Lluvia insuficiente para generar escurrimiento" in content, (
        "App.tsx no contiene el mensaje 'Lluvia insuficiente para generar escurrimiento' requerido para eventos < 1 mm."
    )


def test_api_runoff_run_with_sub_millimeter_rainfall_yields_zero_runoff(
    api_client: TestClient, field_with_sloped_dem: tuple[str, dict]
):
    """Verifica a nivel de API que un evento menor a 1 mm (ej. 0.3 mm) genera 0.0 mm de escorrentía

    y 0.0 m³ de volumen, confirmando que la lluvia es insuficiente para generar escurrimiento.
    """
    fid, _ = field_with_sloped_dem

    ev_resp = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/rainfall-events",
        json={"name": "Lluvia 0.3 mm", "total_mm": 0.3, "source_type": "manual"},
    )
    assert ev_resp.status_code == 201
    ev = ev_resp.json()
    assert ev["total_mm"] == 0.3

    run_resp = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={"name": "Corrida 0.3 mm", "rainfall_event_id": ev["id"]},
    )
    assert run_resp.status_code == 201
    run = run_resp.json()

    assert run["cn_result"]["runoff_q_mm"] == 0.0
    assert run["spatial_summary"]["field_runoff_generated_m3"] == 0.0
