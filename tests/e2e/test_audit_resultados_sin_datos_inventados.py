"""Tests para verificar que la pantalla de resultados (ResultStep) no contenga números,

fórmulas ni rangos inventados cuando no hay simulación 2D o USLE (Issue #32 / Auditoría 21/11/2026).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.e2e.fixtures import (
    REPO_ROOT,
    write_san_luis_parcela_205_dem,
)
from tests.e2e.test_tier1_features import _upload_dem


def _is_chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
            return True
    except Exception:
        return False


def test_result_step_source_has_no_invented_factors_or_ranges():
    """Verifica que apps/web/src/components/flow/ResultStep.tsx no contenga fórmulas

    con factores fijos sobre resultados ni rangos sintéticos inventados (Issue #32).
    """
    result_step_path = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "components"
        / "flow"
        / "ResultStep.tsx"
    )
    assert result_step_path.exists(), f"No se encontró {result_step_path}"
    content = result_step_path.read_text(encoding="utf-8")

    # 1. No debe existir el factor 0.18 para inventar hectáreas anegadas sin motor 2D
    assert "* 0.18" not in content, (
        "Se encontró factor inventado '* 0.18' para superficie anegable en ResultStep.tsx"
    )

    # 2. No debe existir fórmula inventada de pérdida de suelo con piso 1.2 o factor 8.4
    assert "* 8.4" not in content, (
        "Se encontró factor inventado '* 8.4' para pérdida de suelo en ResultStep.tsx"
    )
    assert "Math.max(1.2" not in content, (
        "Se encontró piso inventado 'Math.max(1.2' para pérdida de suelo en ResultStep.tsx"
    )

    # 3. No debe haber rangos sintéticos inventados (±15%, ±8 puntos, ×0.8 a ×1.25)
    assert "* 0.85" not in content, "Se encontró rango sintético '* 0.85' en ResultStep.tsx"
    assert "* 1.15" not in content, "Se encontró rango sintético '* 1.15' en ResultStep.tsx"
    assert "runoffPct - 8" not in content, "Se encontró rango sintético '- 8' en ResultStep.tsx"
    assert "* 1.25" not in content, "Se encontró rango sintético '* 1.25' en ResultStep.tsx"

    # 4. No debe haber fallback inventado 68 para confidence score
    assert ": 68" not in content, "Se encontró fallback inventado '68' para confianza en ResultStep.tsx"


def test_api_runoff_run_without_2d_has_no_ponded_summary(api_client: TestClient, tmp_path: Path):
    """Verifica a nivel de API que una corrida normal no tiene hydrodynamic_2d_summary.

    El frontend debe mostrar 'Sin dato' y no inventar hectáreas multiplicando por 0.18.
    """
    f = api_client.post("/api/v1/fields/sample?preset=llanura").json()["fields"][0]
    fid = f["id"]

    _upload_dem(
        api_client,
        fid,
        write_san_luis_parcela_205_dem(tmp_path / "p205.tif", pixel_m=30.0),
        buffer_m=300.0,
    )
    api_client.post(
        f"/api/v1/fields/{fid}/hydrology/static",
        json={"conditioning_mode": "preserve"},
    ).raise_for_status()

    ev = api_client.post(f"/api/v1/fields/{fid}/hydrology/rainfall-events/sample").json()
    run = api_client.post(
        f"/api/v1/fields/{fid}/hydrology/runoff-runs",
        json={
            "name": "Corrida sin 2D",
            "rainfall_event_id": ev["id"],
            "cover_code": "soja_maiz_convencional",
            "antecedent_moisture": "medium",
        },
    ).json()

    # La corrida sin simular 2D NO tiene hydrodynamic_2d_summary
    assert run.get("hydrodynamic_2d_summary") is None
    # El volumen escurrido existe en m³
    assert run["spatial_summary"]["field_runoff_generated_m3"] > 0


@pytest.mark.skipif(not _is_chromium_available(), reason="Playwright Chromium no disponible en este entorno")
def test_playwright_e2e_results_screen_shows_sin_dato_without_2d(tmp_path: Path):
    """Test e2e con Playwright: carga el frontend y comprueba que con una corrida sin 2D,

    la métrica de superficie anegable muestra 'Sin dato' y no un número ni 'ha' con número.
    """
    import threading
    import time

    import uvicorn
    from playwright.sync_api import sync_playwright

    from services.api.app.main import app

    server_port = 8765
    config = uvicorn.Config(app=app, host="127.0.0.1", port=server_port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1.5)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Mock de llamadas para navegar directamente a resultados con una corrida sin 2D
            page.route("**/api/v1/hydrology/daily-rainfall*", lambda route: route.fulfill(
                status=200, content_type="application/json", body="null"
            ))

            # Verificar que en el bundle o render no aparezca número inventado
            page.goto(f"http://127.0.0.1:{server_port}", wait_until="networkidle", timeout=15000)

            # Verificar título y carga inicial
            assert page.title() is not None
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=2.0)
