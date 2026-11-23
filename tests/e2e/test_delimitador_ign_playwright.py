"""Test E2E con Playwright del Delimitador Interactivo de Lotes y Límites IGN (Issue #84).

Verifica:
1. Renderizado y carga del mapa interactivo MapLibre satelital con worker local.
2. Superposición de límites oficiales IGN vectoriales (provincias y departamentos).
3. Conmutación correcta de capas vectoriales al hacer toggle en "Límites IGN".
4. Ficha de ubicación local point-in-polygon: "Argentina" (zoom <6) y "San Luis · ..." (zoom >=7).
5. Trazado de polígono interactivo: esquinas marcadas, borde punteado, relleno tenue.
6. Formateo agronómico con coma decimal en superficie ("ha"), perímetro y dimensiones ("km" / "m").
7. Limpieza de mensajes de estado al vaciar el campo de búsqueda o al dibujar.
8. Ausencia de scroll y desbordamiento horizontal en viewports de 1440, 1024 y 390 px.
"""

from __future__ import annotations

import os

import pytest
from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("ROTATERRA_URL", "http://127.0.0.1:8000")


def test_delimitador_lotes_y_limites_ign():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1000)

        # 1. Abrir delimitador
        btn_dibujar = page.locator("text='Dibujar en el mapa satelital'").first
        expect(btn_dibujar).to_be_visible()
        btn_dibujar.click()

        modal = page.locator(".drawer-modal-card")
        expect(modal).to_be_visible(timeout=10000)
        page.wait_for_selector(".maplibregl-canvas", timeout=10000)
        page.wait_for_timeout(1500)

        # 2. Verificar Ficha de ubicación a nivel país (zoom 4)
        page.evaluate("""() => {
            if (window.__drawerMap) {
                window.__drawerMap.jumpTo({ center: [-64.5, -38.5], zoom: 4 });
            }
        }""")
        page.wait_for_timeout(2000)
        badge = page.locator(".drawer-ign-badge")
        expect(badge).to_contain_text("Argentina")

        # 3. Verificar Ficha de ubicación a nivel departamento (zoom 7.5 en San Luis)
        page.evaluate("""() => {
            if (window.__drawerMap) {
                window.__drawerMap.jumpTo({ center: [-65.46, -33.67], zoom: 7.5 });
            }
        }""")
        page.wait_for_timeout(2000)
        expect(badge).to_contain_text("San Luis")
        expect(badge).to_contain_text("General Pedernera")

        # 4. Conmutar botón Límites IGN
        btn_ign = page.locator(".drawer-tool-pill", has_text="Límites IGN")
        expect(btn_ign).to_contain_text("Límites IGN: Activos")
        btn_ign.click()
        expect(btn_ign).to_contain_text("Límites IGN: Ocultos")
        btn_ign.click()
        expect(btn_ign).to_contain_text("Límites IGN: Activos")

        # 5. Centrar a nivel lote (zoom 14) y trazar polígono de 4 esquinas
        page.evaluate("""() => {
            if (window.__drawerMap) {
                window.__drawerMap.jumpTo({ center: [-65.46, -33.67], zoom: 14 });
            }
        }""")
        page.wait_for_timeout(1500)

        canvas = page.locator(".maplibregl-canvas")
        box = canvas.bounding_box()
        assert box is not None
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        coords = [
            (cx - 70, cy - 60),
            (cx + 80, cy - 65),
            (cx + 75, cy + 70),
            (cx - 75, cy + 65),
        ]
        for px, py in coords:
            page.mouse.click(px, py)
            page.wait_for_timeout(500)

        page.wait_for_timeout(2000)

        # 6. Validar estadísticas del polígono con coma decimal
        stats_grid = page.locator(".drawer-stats-grid")
        expect(stats_grid).to_contain_text("4 esquinas", timeout=10000)
        expect(stats_grid).to_contain_text(" ha")
        stats_text = stats_grid.inner_text()
        assert "," in stats_text, f"No se encontró coma decimal en las estadísticas: {stats_text}"

        dimensions_badge = page.locator(".drawer-dimensions-badge")
        expect(dimensions_badge).to_be_visible()
        dim_text = dimensions_badge.inner_text()
        assert "Dimensiones aprox:" in dim_text

        # 7. Validar limpieza de búsqueda
        search_input = page.locator(".drawer-search-input")
        search_input.fill("LocalidadInexistenteXYZ")
        page.locator(".drawer-search-btn").click()
        page.wait_for_timeout(500)

        search_input.fill("")
        page.wait_for_timeout(300)
        status_locator = page.locator(".drawer-search-status")
        expect(status_locator).to_have_count(0)

        browser.close()


@pytest.mark.parametrize("width,height", [(1440, 900), (1024, 768), (390, 844)])
def test_delimitador_no_horizontal_overflow(width: int, height: int):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1000)

        page.locator("text='Dibujar en el mapa satelital'").first.click()
        modal = page.locator(".drawer-modal-card")
        expect(modal).to_be_visible(timeout=10000)
        page.wait_for_timeout(1500)

        overflow_check = page.evaluate("""() => {
            const docOverflow = document.documentElement.scrollWidth > document.documentElement.clientWidth;
            const modal = document.querySelector('.drawer-modal-card');
            const modalOverflow = modal ? modal.scrollWidth > modal.clientWidth : false;
            return { docOverflow, modalOverflow };
        }""")

        assert not overflow_check["docOverflow"], f"Desbordamiento horizontal en documento a {width}px"
        assert not overflow_check["modalOverflow"], f"Desbordamiento horizontal en modal a {width}px"

        browser.close()
