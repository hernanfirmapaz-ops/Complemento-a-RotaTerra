"""Capturas con Playwright de la barra de milímetros y escalera precalculada (Issue #113 / Spec 031 · Parte b)."""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


def esperar_servidor(url: str = "http://127.0.0.1:8000/api/v1/health", max_segundos: int = 25) -> bool:
    inicio = time.time()
    while time.time() - inicio < max_segundos:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def capturar():
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "services.api.app.main:app", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        print("Esperando servidor en http://127.0.0.1:8000...")
        if not esperar_servidor():
            raise RuntimeError("El servidor no respondió a tiempo.")

        out_docs = Path("docs/capturas")
        out_docs.mkdir(parents=True, exist_ok=True)
        out_artifact = Path("C:/Users/haf01/.gemini/antigravity/brain/227d06b1-473b-4034-8d15-d5666eebf39c/capturas_tarea_113")
        out_artifact.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            # 1. Escritorio (1440x900)
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            context.route("**/fonts.googleapis.com/**", lambda route: route.abort())
            context.route("**/fonts.gstatic.com/**", lambda route: route.abort())
            page = context.new_page()

            page.goto("http://127.0.0.1:8000/", timeout=30000)
            page.wait_for_timeout(2000)

            # Seleccionar lote con relieve e hidrología procesada (MICAM PITO)
            lote_btn = page.locator("button:has-text('MICAM PITO')")
            if lote_btn.count() > 0:
                lote_btn.first.click()
            else:
                page.locator("button:has-text('Continuar a Lluvia')").first.click()

            # Esperar a que cargue el lote y la escalera en segundo plano
            page.wait_for_timeout(4000)

            # Captura completa del panel lateral con la barra de lluvia
            box_aside = page.evaluate("""() => {
                const el = document.querySelector('aside');
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return { x: r.x, y: r.y, width: r.width, height: r.height };
            }""")
            if box_aside:
                page.screenshot(path=str(out_docs / "escritorio_1440px_panel_lluvia_escalera.png"), clip=box_aside)
                page.screenshot(path=str(out_artifact / "escritorio_1440px_panel_lluvia_escalera.png"), clip=box_aside)
                print(f"[OK] Guardado panel lluvia escritorio en {out_docs / 'escritorio_1440px_panel_lluvia_escalera.png'}")

            # Captura con zoom del componente RainfallSlider
            box_slider = page.evaluate("""() => {
                const el = document.querySelector('.rainfall-slider-box');
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return { x: r.x, y: r.y, width: r.width, height: r.height };
            }""")
            if box_slider:
                page.screenshot(path=str(out_docs / "zoom_barra_mm_curva_anegamiento.png"), clip=box_slider)
                page.screenshot(path=str(out_artifact / "zoom_barra_mm_curva_anegamiento.png"), clip=box_slider)
                print(f"[OK] Guardado zoom componente en {out_docs / 'zoom_barra_mm_curva_anegamiento.png'}")

            browser.close()

            # 2. Móvil (390x844)
            browser_mob = p.chromium.launch(headless=True)
            context_mob = browser_mob.new_context(viewport={"width": 390, "height": 844})
            context_mob.route("**/fonts.googleapis.com/**", lambda route: route.abort())
            context_mob.route("**/fonts.gstatic.com/**", lambda route: route.abort())
            page_mob = context_mob.new_page()

            page_mob.goto("http://127.0.0.1:8000/", timeout=30000)
            page_mob.wait_for_timeout(2000)

            lote_mob = page_mob.locator("button:has-text('MICAM PITO')")
            if lote_mob.count() > 0:
                lote_mob.first.click()
            else:
                page_mob.locator("button:has-text('Continuar a Lluvia')").first.click()

            page_mob.wait_for_timeout(4000)

            page_mob.screenshot(path=str(out_docs / "movil_390px_lluvia_escalera.png"))
            page_mob.screenshot(path=str(out_artifact / "movil_390px_lluvia_escalera.png"))
            print(f"[OK] Guardado captura móvil en {out_docs / 'movil_390px_lluvia_escalera.png'}")

            browser_mob.close()

    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    capturar()
