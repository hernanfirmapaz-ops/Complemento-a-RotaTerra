"""No-desbordamiento horizontal del panel lateral en TODOS los pasos (Issue #83).

El desborde reportado en #83 estaba en la pantalla de RESULTADOS, no en la inicial. Por eso
el test carga un lote de prueba (fixture de `tests/fixtures/lotes`, con su DEM subido, sin
internet), avanza a "2. Lluvia" y "3. Resultado" y mide en cada paso a 1440, 1024 y 390 px:

- Escritorio (>= 768 px): `aside.flow-sidebar`. Móvil (< 768 px): `.ui-bottom-sheet`.
- El panel tiene que estar visible (`expect(...).to_be_visible()`): si no aparece, el test falla.
- `scrollWidth <= clientWidth` del panel, ningún descendiente sobresale por su borde derecho
  y la página no tiene scroll horizontal.

Requiere la app servida en `ROTATERRA_URL` (por omisión http://127.0.0.1:8000). Corre en el
trabajo de CI "Calidad visual y capturas (Playwright)", que levanta la app; no se saltea.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect, sync_playwright

BASE_URL = os.environ.get("ROTATERRA_URL", "http://127.0.0.1:8000")
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "lotes"
DEM_TIF = FIXTURES / "san_luis_piedemonte_492_dem.tif"
STEP_TIMEOUT_MS = 120_000

VIEWPORTS = [
    (1440, 900, "aside.flow-sidebar"),
    (1024, 768, "aside.flow-sidebar"),
    (390, 844, ".ui-bottom-sheet"),
]

MEASURE_JS = """(selector) => {
  const panel = document.querySelector(selector);
  if (!panel) return { error: 'panel not found: ' + selector };
  const pr = panel.getBoundingClientRect();
  const offenders = [];
  panel.querySelectorAll('*').forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.right > pr.right + 1) {
      offenders.push(`${el.tagName.toLowerCase()}.${String(el.className).slice(0, 40)} right=${r.right.toFixed(0)}`);
    }
  });
  return {
    client: panel.clientWidth,
    scroll: panel.scrollWidth,
    offenders: offenders.slice(0, 5),
    docOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  };
}"""


@pytest.fixture(scope="module")
def lote_con_relieve() -> str:
    """Lote de prueba con DEM de fixture ya procesado (idempotente, sin red)."""
    with httpx.Client(base_url=BASE_URL, timeout=120) as api:
        resp = api.post("/api/v1/fields/sample", params={"preset": "serrano"})
        resp.raise_for_status()
        campo = resp.json()["fields"][0]
        if not campo.get("has_terrain"):
            with open(DEM_TIF, "rb") as dem:
                proc = api.post(
                    f"/api/v1/fields/{campo['id']}/terrain/process",
                    data={
                        "source_id": "upload",
                        "buffer_m": "300",
                        "source_name": "Fixture DEM de prueba (san_luis_piedemonte_492_dem.tif)",
                        "surface_type": "DSM",
                    },
                    files={"file": (DEM_TIF.name, dem, "image/tiff")},
                )
            proc.raise_for_status()
        return campo["name"]


def _medir_viewports(page: Page, etapa: str) -> None:
    for ancho, alto, selector in VIEWPORTS:
        page.set_viewport_size({"width": ancho, "height": alto})
        time.sleep(0.3)
        panel = page.locator(selector).first
        expect(panel, f"El panel {selector} debe estar visible en {etapa} a {ancho}px").to_be_visible()
        medida = page.evaluate(MEASURE_JS, selector)
        assert "error" not in medida, medida["error"]
        assert medida["scroll"] <= medida["client"], f"Overflow del panel en {etapa} a {ancho}px: {medida}"
        assert not medida["offenders"], f"Elementos fuera del panel en {etapa} a {ancho}px: {medida}"
        assert not medida["docOverflow"], f"Scroll horizontal de página en {etapa} a {ancho}px: {medida}"


def test_panel_sin_desborde_en_lote_lluvia_y_resultado(lote_con_relieve: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-webgl", "--disable-3d-apis"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE_URL, wait_until="networkidle")

        # Paso 1: Lote (medir en 1440, 1024, 390 px)
        _medir_viewports(page, "1. Lote")
        page.set_viewport_size({"width": 1440, "height": 900})
        page.locator(".lot-card-item", has_text=lote_con_relieve).first.click()

        # Paso 2: Lluvia (esperar botón de simulación habilitado)
        page.wait_for_function(
            '() => { const b = document.querySelector(".rain-cta-stack button.ui-btn-primary"); return b && !b.disabled; }',
            timeout=STEP_TIMEOUT_MS,
        )
        _medir_viewports(page, "2. Lluvia")

        # Iniciar simulación y esperar a Paso 3 (Resultado)
        page.set_viewport_size({"width": 1440, "height": 900})
        page.evaluate('() => document.querySelector(".rain-cta-stack button.ui-btn-primary").click()')
        expect(page.get_by_role("heading", name=re.compile(r"Qué pasó con"))).to_be_visible(timeout=STEP_TIMEOUT_MS)

        # Paso 3: Resultado (pantalla donde se reportó el desborde en #83)
        _medir_viewports(page, "3. Resultado")

        browser.close()
