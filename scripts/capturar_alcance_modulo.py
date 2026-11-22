"""Captura de verificación visual para el Issue #14:
1. PolygonMapDrawer sin el botón de generar lote preestablecido.
2. AgronomicToolkitPanel con las 6 herramientas agro-hidrológicas sin siembra ni rotaciones.
"""

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


def main():
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "services.api.app.main:app", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        print("Iniciando backend uvicorn...")
        if not esperar_servidor():
            raise RuntimeError("El servidor no respondió a tiempo.")

        out_docs = Path("docs/capturas")
        out_docs.mkdir(parents=True, exist_ok=True)
        out_art = Path("C:/Users/haf01/.gemini/antigravity/brain/227d06b1-473b-4034-8d15-d5666eebf39c/capturas_tarea_a5")
        out_art.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            page.goto("http://127.0.0.1:8000/", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)

            # 1. Abrir el modal de dibujo de polígono
            dibujar_btn = page.locator("button:has-text('Dibujar en el mapa')")
            if dibujar_btn.count() > 0 and dibujar_btn.first.is_visible():
                dibujar_btn.first.click()
                page.wait_for_timeout(1500)

                # Capturar el modal de dibujo mostrando las herramientas sin "Marcar lote aquí y ajustar"
                modal = page.locator(".drawer-modal-card")
                if modal.count() > 0:
                    modal.first.screenshot(path=str(out_docs / "captura_dibujo_lote_sin_preset.png"))
                    modal.first.screenshot(path=str(out_art / "captura_dibujo_lote_sin_preset.png"))
                    print("[OK] Captura guardada: captura_dibujo_lote_sin_preset.png")

                # Cerrar modal
                close_btn = page.locator("button:has-text('Cerrar')")
                if close_btn.count() > 0:
                    close_btn.first.click()
                    page.wait_for_timeout(500)

            # 2. Navegar al showcase para inspeccionar AgronomicToolkitPanel
            page.goto("http://127.0.0.1:8000/#showcase", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)

            # Buscar la sección del panel agronómico o el botón de ejecutar
            page.screenshot(path=str(out_docs / "captura_alcance_showcase.png"))
            page.screenshot(path=str(out_art / "captura_alcance_showcase.png"))
            print("[OK] Captura general guardada: captura_alcance_showcase.png")

            context.close()
            browser.close()
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
