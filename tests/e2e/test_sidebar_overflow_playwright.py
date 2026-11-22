"""Prueba automatizada de no-desbordamiento de la barra lateral (Issue #83).

Verifica que en distintas resoluciones (1440, 1024 y 390 px) la barra lateral
`aside.flow-sidebar` y sus elementos hijos (selector de tormenta, tarjetas KPI,
navegación de pasos) no presenten desplazamiento horizontal (scrollWidth <= clientWidth).
"""

from __future__ import annotations

import time
import pytest
from playwright.sync_api import sync_playwright


import socket

def _is_server_running() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=1):
            return True
    except OSError:
        return False

@pytest.mark.skipif(
    not _is_server_running(),
    reason="Requiere servidor local activo en http://127.0.0.1:8000"
)
def test_flow_sidebar_no_horizontal_overflow():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state("networkidle")

        # 1. 1440px
        sidebar = page.locator("aside.flow-sidebar")
        if sidebar.is_visible():
            box = page.evaluate("() => ({ client: document.querySelector('aside.flow-sidebar').clientWidth, scroll: document.querySelector('aside.flow-sidebar').scrollWidth })")
            assert box["scroll"] <= box["client"], f"Overflow en 1440px: {box}"

        # 2. 1024px
        page.set_viewport_size({"width": 1024, "height": 768})
        time.sleep(0.5)
        if sidebar.is_visible():
            box = page.evaluate("() => ({ client: document.querySelector('aside.flow-sidebar').clientWidth, scroll: document.querySelector('aside.flow-sidebar').scrollWidth })")
            assert box["scroll"] <= box["client"], f"Overflow en 1024px: {box}"

        # 3. 390px
        page.set_viewport_size({"width": 390, "height": 844})
        time.sleep(0.5)
        doc_overflow = page.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth")
        assert not doc_overflow, "Overflow horizontal detectado en viewport móvil 390px"

        browser.close()
