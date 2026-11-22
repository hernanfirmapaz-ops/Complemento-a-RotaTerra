"""Script para capturar las vistas que utilizan MapLibre 6.x:
1. Dibujo del lote (PolygonMapDrawer)
2. Vista Mapa (TerrainScene3D / MapLibre GL 2D)
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

        # 1. Asegurar lote de prueba en API
        try:
            req = urllib.request.Request("http://127.0.0.1:8000/api/v1/fields/sample?preset=llanura", method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"Aviso al cargar preset: {e}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            page.goto("http://127.0.0.1:8000/", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)

            # --- CAPTURA 1: Dibujo del lote (MapLibre 6.x) ---
            print("Abriendo modal de dibujo de lote...")
            btn_dibujar = page.locator("text='Dibujar en el mapa satelital'")
            if btn_dibujar.count() > 0:
                btn_dibujar.first.click()
                page.wait_for_timeout(1500)
                # Esperar a que el modal del mapa esté visible
                page.wait_for_selector(".drawer-modal-card", timeout=10000)
                page.wait_for_timeout(2000)

                cap1_docs = out_docs / "captura_dibujo_lote_maplibre6.png"
                page.screenshot(path=str(cap1_docs), full_page=False)
                print(f"[OK] Captura 1 guardada: {cap1_docs}")

                # Cerrar modal
                btn_cerrar = page.locator(".drawer-close-btn")
                if btn_cerrar.count() > 0:
                    btn_cerrar.first.click()
                    page.wait_for_timeout(1000)

            # --- CAPTURA 2: Vista Mapa (MapLibre 6.x) ---
            print("Cambiando a vista Mapa...")
            # Seleccionar lote si hay uno en la lista
            lote_card = page.locator(".lot-card-item")
            if lote_card.count() > 0:
                lote_card.first.click()
                page.wait_for_timeout(1000)

            btn_mapa = page.locator("button:has-text('Mapa'), .ui-segmented-btn:has-text('Mapa')")
            if btn_mapa.count() > 0:
                btn_mapa.first.click()
                page.wait_for_timeout(2000)

            cap2_docs = out_docs / "captura_vista_mapa_maplibre6.png"
            page.screenshot(path=str(cap2_docs), full_page=False)
            print(f"[OK] Captura 2 guardada: {cap2_docs}")

            context.close()
            browser.close()
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    capturar()
