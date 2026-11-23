"""Script para capturar las vistas del delimitador de lotes con límites IGN (Issue #84):
1. Nivel país (zoom 4): provincias IGN vectoriales blancas sobre satélite + ficha "Argentina".
2. Nivel provincia / San Luis (zoom 7.5): departamentos IGN vectoriales sobre satélite + ficha "San Luis · General Pedernera".
3. Nivel lote (zoom 14): polígono dibujado con relleno amarillo tenue, borde punteado, marcadores de esquinas,
   dimensiones y superficie con coma decimal (ej. "32,2 ha").
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs" / "capturas" / "tarea_84"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

ARTIFACTS_DIR = Path("C:/Users/haf01/.gemini/antigravity/brain/227d06b1-473b-4034-8d15-d5666eebf39c/capturas_tarea_84")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("Iniciando captura Playwright del delimitador de lotes e IGN...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto("http://127.0.0.1:8000/", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1000)

        # Abrir delimitador interactivo
        print("Abriendo modal delimitador...")
        btn_dibujar = page.locator("text='Dibujar en el mapa satelital'").first
        btn_dibujar.click()
        page.wait_for_selector(".drawer-modal-card", timeout=15000)
        page.wait_for_timeout(2500)

        # Esperar a que MapLibre esté listo
        page.wait_for_selector(".maplibregl-canvas", timeout=10000)

        # -------------------------------------------------------------
        # CAPTURA 1: Nivel País (zoom 4)
        # -------------------------------------------------------------
        print("Configurando vista País (zoom 4)...")
        page.evaluate("""() => {
            if (window.__drawerMap) {
                window.__drawerMap.jumpTo({ center: [-64.5, -38.5], zoom: 4 });
            }
        }""")
        page.wait_for_timeout(3000)

        cap_pais = DOCS_DIR / "pais_zoom4_limites_ign.png"
        page.screenshot(path=str(cap_pais))
        page.screenshot(path=str(ARTIFACTS_DIR / "pais_zoom4_limites_ign.png"))
        print(f"[OK] Captura 1 (País zoom 4) guardada: {cap_pais}")

        # -------------------------------------------------------------
        # CAPTURA 2: Nivel San Luis / Departamentos (zoom 7.5)
        # -------------------------------------------------------------
        print("Configurando vista San Luis / Departamentos (zoom 7.5)...")
        page.evaluate("""() => {
            if (window.__drawerMap) {
                window.__drawerMap.jumpTo({ center: [-65.46, -33.67], zoom: 7.5 });
            }
        }""")
        page.wait_for_timeout(3000)

        cap_sl = DOCS_DIR / "san_luis_zoom7_5_limites_ign.png"
        page.screenshot(path=str(cap_sl))
        page.screenshot(path=str(ARTIFACTS_DIR / "san_luis_zoom7_5_limites_ign.png"))
        print(f"[OK] Captura 2 (San Luis zoom 7.5) guardada: {cap_sl}")

        # -------------------------------------------------------------
        # CAPTURA 3: Nivel Lote (zoom 14 con polígono dibujado)
        # -------------------------------------------------------------
        print("Configurando vista Lote (zoom 14) y dibujando polígono...")
        page.evaluate("""() => {
            if (window.__drawerMap) {
                window.__drawerMap.jumpTo({ center: [-65.46, -33.67], zoom: 14 });
            }
        }""")
        page.wait_for_timeout(2000)

        canvas = page.locator(".maplibregl-canvas")
        box = canvas.bounding_box()
        if box:
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            p1 = (cx - 70, cy - 60)
            p2 = (cx + 80, cy - 65)
            p3 = (cx + 75, cy + 70)
            p4 = (cx - 75, cy + 65)

            for px, py in [p1, p2, p3, p4]:
                page.mouse.click(px, py)
                page.wait_for_timeout(350)

        page.wait_for_timeout(2500)

        cap_lote = DOCS_DIR / "lote_zoom14_poligono_completo.png"
        page.screenshot(path=str(cap_lote))
        page.screenshot(path=str(ARTIFACTS_DIR / "lote_zoom14_poligono_completo.png"))
        print(f"[OK] Captura 3 (Lote zoom 14 con polígono) guardada: {cap_lote}")

        # Captura recortada con zoom al detalle del estilo del polígono y estadísticas
        drawer_card = page.locator(".drawer-modal-card")
        cap_zoom = DOCS_DIR / "zoom_detalle_estilo_poligono.png"
        drawer_card.screenshot(path=str(cap_zoom))
        drawer_card.screenshot(path=str(ARTIFACTS_DIR / "zoom_detalle_estilo_poligono.png"))
        print(f"[OK] Captura 4 (Detalle modal y estilo) guardada: {cap_zoom}")

        browser.close()
        print("Todas las capturas se generaron exitosamente.")


if __name__ == "__main__":
    main()
