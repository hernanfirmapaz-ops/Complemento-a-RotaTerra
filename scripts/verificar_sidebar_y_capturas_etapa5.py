"""Verificación de no desbordamiento de barra lateral (Issue #83) y capturas reales de lluvia Etapa 5."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("capturas/etapa5_revision")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    with sync_playwright() as p:
        # Usar Chromium visible con aceleración por hardware
        browser = p.chromium.launch(
            headless=False,
            args=["--enable-gpu", "--ignore-gpu-blocklist", "--use-gl=angle"],
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("1. Navegando a http://127.0.0.1:8000/...")
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # 1. Verificar barra lateral a 1440px (Paso 1: Lote)
        sidebar_overflow_1440 = page.evaluate("""() => {
            const el = document.querySelector('aside.flow-sidebar');
            if (!el) return { found: false };
            return {
                found: true,
                clientWidth: el.clientWidth,
                scrollWidth: el.scrollWidth,
                hasOverflow: el.scrollWidth > el.clientWidth
            };
        }""")
        print("Sidebar a 1440px (Paso 1):", sidebar_overflow_1440)
        assert not sidebar_overflow_1440.get("hasOverflow"), f"Overflow en 1440px: {sidebar_overflow_1440}"

        # 2. Seleccionar Lote Piedemonte 492
        print("2. Seleccionando Lote Piedemonte 492...")
        clicked = False
        for el in page.query_selector_all(".field-item, button, .sidebar-card, div"):
            txt = el.inner_text()
            if "492" in txt and len(txt) < 80:
                el.click()
                clicked = True
                break
        if not clicked:
            page.locator(".field-item, .field-card").first.click()
        time.sleep(2)

        # 3. Verificar barra lateral a 1440px en Paso 2 (Lluvia con selector de tormentas)
        sidebar_rain_1440 = page.evaluate("""() => {
            const el = document.querySelector('aside.flow-sidebar');
            const seg = document.querySelector('.ui-segmented');
            return {
                sidebar: { clientWidth: el.clientWidth, scrollWidth: el.scrollWidth, hasOverflow: el.scrollWidth > el.clientWidth },
                segmented: seg ? { clientWidth: seg.clientWidth, scrollWidth: seg.scrollWidth, hasOverflow: seg.scrollWidth > seg.clientWidth } : null
            };
        }""")
        print("Sidebar a 1440px (Paso 2 Lluvia):", sidebar_rain_1440)
        assert not sidebar_rain_1440["sidebar"]["hasOverflow"], f"Overflow en sidebar lluvia: {sidebar_rain_1440}"
        if sidebar_rain_1440["segmented"]:
            assert not sidebar_rain_1440["segmented"]["hasOverflow"], f"Overflow en segmented: {sidebar_rain_1440}"

        # 4. Iniciar simulación de lluvia y esperar que termine (botón 'Pausar lluvia')
        print("4. Iniciando simulación de lluvia de 80 mm...")
        sim_btn = page.query_selector("button:has-text('Simular lluvia')")
        if sim_btn:
            sim_btn.click()

        print("Esperando a que la simulación termine y aparezca 'Pausar lluvia'...")
        pausar_btn = page.locator("button:has-text('Pausar lluvia'), button[aria-label='Pausar lluvia'], .diorama-ctrl-btn.active")
        pausar_btn.first.wait_for(state="visible", timeout=90000)
        time.sleep(3)  # Dejar que las partículas de lluvia caigan activamente

        # 5. Verificar barra lateral a 1440px en Paso 3 (Resultados con tarjetas métricas)
        sidebar_res_1440 = page.evaluate("""() => {
            const el = document.querySelector('aside.flow-sidebar');
            const grid = document.querySelector('.result-metrics-grid');
            return {
                sidebar: { clientWidth: el.clientWidth, scrollWidth: el.scrollWidth, hasOverflow: el.scrollWidth > el.clientWidth },
                grid: grid ? { clientWidth: grid.clientWidth, scrollWidth: grid.scrollWidth, hasOverflow: grid.scrollWidth > grid.clientWidth } : null
            };
        }""")
        print("Sidebar a 1440px (Paso 3 Resultados):", sidebar_res_1440)
        assert not sidebar_res_1440["sidebar"]["hasOverflow"], f"Overflow en sidebar resultados: {sidebar_res_1440}"
        if sidebar_res_1440["grid"]:
            assert not sidebar_res_1440["grid"]["hasOverflow"], f"Overflow en grid resultados: {sidebar_res_1440}"

        # 6. Medir FPS reales con lluvia activa
        print("6. Midiendo FPS reales con animación de lluvia activa...")
        fps_samples = []
        for _ in range(8):
            time.sleep(0.5)
            val = page.evaluate("window.__diorama_fps")
            if val is not None and val > 0:
                fps_samples.append(float(val))
        print(f"FPS samples ({len(fps_samples)}): {fps_samples}")
        avg_fps = sum(fps_samples) / len(fps_samples)
        print(f"FPS promedio: {avg_fps:.1f} fps")

        # 7. Captura de escritorio a 1440px con lluvia activa y botón "Pausar lluvia" visible
        path_1440 = OUTPUT_DIR / "escritorio_1440px_lluvia_activa.png"
        page.screenshot(path=str(path_1440))
        print("Captura 1440px guardada en:", path_1440)

        # 8. Captura con zoom cercano al terreno para ver los sprites redondos de 2-4 px y salpicaduras
        print("8. Ajustando zoom de cámara en Three.js para capturar detalle de gotas y salpicaduras...")
        page.mouse.move(900, 450)
        # Rueda del mouse hacia adelante para acercar zoom
        for _ in range(8):
            page.mouse.wheel(0, -300)
            time.sleep(0.1)
        time.sleep(2)
        path_zoom = OUTPUT_DIR / "escritorio_1440px_zoom_gotas_sprites.png"
        page.screenshot(path=str(path_zoom))
        print("Captura zoom gotas guardada en:", path_zoom)

        # 9. Viewport 1024px (Tablet / Desktop chico)
        print("9. Evaluando viewport 1024x768...")
        page.set_viewport_size({"width": 1024, "height": 768})
        time.sleep(2)
        sidebar_1024 = page.evaluate("""() => {
            const el = document.querySelector('aside.flow-sidebar');
            return {
                clientWidth: el ? el.clientWidth : 0,
                scrollWidth: el ? el.scrollWidth : 0,
                hasOverflow: el ? (el.scrollWidth > el.clientWidth) : false
            };
        }""")
        print("Sidebar a 1024px:", sidebar_1024)
        assert not sidebar_1024["hasOverflow"], f"Overflow en 1024px: {sidebar_1024}"
        path_1024 = OUTPUT_DIR / "tablet_1024px_sin_overflow.png"
        page.screenshot(path=str(path_1024))
        print("Captura 1024px guardada en:", path_1024)

        # 10. Viewport 390px (Móvil)
        print("10. Evaluando viewport 390x844...")
        page.set_viewport_size({"width": 390, "height": 844})
        time.sleep(2)
        mobile_overflow = page.evaluate("""() => {
            const doc = document.documentElement;
            const sheet = document.querySelector('.bottom-sheet');
            return {
                docScroll: doc.scrollWidth,
                docClient: doc.clientWidth,
                docOverflow: doc.scrollWidth > doc.clientWidth,
                sheetOverflow: sheet ? (sheet.scrollWidth > sheet.clientWidth) : false
            };
        }""")
        print("Móvil a 390px:", mobile_overflow)
        assert not mobile_overflow["docOverflow"], f"Overflow horizontal en móvil 390px: {mobile_overflow}"
        path_390 = OUTPUT_DIR / "movil_390px_lluvia_activa.png"
        page.screenshot(path=str(path_390))
        print("Captura 390px guardada en:", path_390)

        browser.close()
        print("Verificación visual y mediciones completadas con éxito.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error en script: {exc}", file=sys.stderr)
        sys.exit(1)
