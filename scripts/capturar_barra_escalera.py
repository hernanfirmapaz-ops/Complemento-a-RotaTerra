"""Capturas con Playwright de la barra de milímetros y escalera precalculada (Issue #113 / Spec 031)."""

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
            page = context.new_page()

            page.goto("http://127.0.0.1:8000/", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            # Seleccionar lote con relieve e hidrología procesada (MICAM PITO o Mi Lote Agrícola)
            lote_btn = page.locator("button:has-text('MICAM PITO')")
            if lote_btn.count() > 0:
                lote_btn.first.click()
            else:
                page.locator("button:has-text('Continuar a Lluvia')").first.click()

            page.wait_for_timeout(2000)

            # Ir al paso de lluvia si no estamos ahí
            nav_lluvia = page.locator("button:has-text('2. Lluvia')")
            if nav_lluvia.count() > 0:
                nav_lluvia.first.click()

            page.wait_for_timeout(2000)

            # Esperar a que la curva de anegamiento o el slider esté visible
            page.wait_for_selector(".rainfall-slider-box", timeout=10000)
            page.wait_for_timeout(1000)

            # Captura completa del panel lateral con la barra de lluvia
            aside = page.locator("aside").first
            if aside.count() > 0:
                aside.screenshot(path=str(out_docs / "escritorio_1440px_panel_lluvia_escalera.png"))
                aside.screenshot(path=str(out_artifact / "escritorio_1440px_panel_lluvia_escalera.png"))
                print(f"[OK] Guardado panel lluvia escritorio en {out_docs / 'escritorio_1440px_panel_lluvia_escalera.png'}")

            # Captura con zoom del componente RainfallSlider
            slider_box = page.locator(".rainfall-slider-box").first
            if slider_box.count() > 0:
                slider_box.screenshot(path=str(out_docs / "zoom_barra_mm_curva_anegamiento.png"))
                slider_box.screenshot(path=str(out_artifact / "zoom_barra_mm_curva_anegamiento.png"))
                print(f"[OK] Guardado zoom componente en {out_docs / 'zoom_barra_mm_curva_anegamiento.png'}")

            # Hover sobre marca T10 o T2 para mostrar tooltip "en un día"
            t10 = page.locator("text=T10")
            if t10.count() > 0:
                t10.first.hover()
                page.wait_for_timeout(500)
                slider_box.screenshot(path=str(out_docs / "zoom_tooltip_rem_en_un_dia.png"))
                slider_box.screenshot(path=str(out_artifact / "zoom_tooltip_rem_en_un_dia.png"))
                print(f"[OK] Guardado zoom tooltip REM en {out_docs / 'zoom_tooltip_rem_en_un_dia.png'}")

            browser.close()

            # 2. Móvil (390x844)
            browser_mob = p.chromium.launch(headless=True)
            context_mob = browser_mob.new_context(viewport={"width": 390, "height": 844})
            page_mob = context_mob.new_page()

            page_mob.goto("http://127.0.0.1:8000/", wait_until="networkidle", timeout=30000)
            page_mob.wait_for_timeout(2000)

            lote_mob = page_mob.locator("button:has-text('MICAM PITO')")
            if lote_mob.count() > 0:
                lote_mob.first.click()
            page_mob.wait_for_timeout(2000)

            nav_lluvia_mob = page_mob.locator("button:has-text('2. Lluvia')")
            if nav_lluvia_mob.count() > 0:
                nav_lluvia_mob.first.click()
            page_mob.wait_for_timeout(2000)

            page_mob.screenshot(path=str(out_docs / "movil_390px_lluvia_escalera.png"))
            page_mob.screenshot(path=str(out_artifact / "movil_390px_lluvia_escalera.png"))
            print(f"[OK] Guardado captura móvil en {out_docs / 'movil_390px_lluvia_escalera.png'}")

            browser_mob.close()

    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    capturar()
