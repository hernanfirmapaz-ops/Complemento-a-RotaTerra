"""Captura de la interfaz mostrando 'Sin dato' en lugar de números inventados (Tarea A4)."""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


def esperar_servidor(url: str = "http://127.0.0.1:8000/api/v1/health", max_segundos: int = 20) -> bool:
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
        out_artifact = Path("C:/Users/haf01/.gemini/antigravity/brain/227d06b1-473b-4034-8d15-d5666eebf39c/capturas_tarea_a4")
        out_artifact.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()

            page.goto("http://127.0.0.1:8000/#showcase", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)

            # Buscar la sección del comparador
            header = page.locator("text=10. Comparador de Escenarios (Deltas con \"Sin dato\")")
            header.scroll_into_view_if_needed()
            page.wait_for_timeout(500)

            # Capturar la sección completa
            section = page.locator("section:has-text('10. Comparador de Escenarios')")
            if section.count() > 0:
                section.first.screenshot(path=str(out_docs / "comparador_sin_dato.png"))
                section.first.screenshot(path=str(out_artifact / "comparador_sin_dato.png"))
                print(f"[OK] Captura guardada en {out_docs / 'comparador_sin_dato.png'}")
                print(f"[OK] Captura guardada en {out_artifact / 'comparador_sin_dato.png'}")
            else:
                page.screenshot(path=str(out_docs / "comparador_sin_dato.png"))
                page.screenshot(path=str(out_artifact / "comparador_sin_dato.png"))
                print("[OK] Captura fallback guardada.")

            context.close()
            browser.close()
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    capturar()
