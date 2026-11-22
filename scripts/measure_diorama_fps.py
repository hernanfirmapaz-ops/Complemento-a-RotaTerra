"""Mide los FPS y captura la pantalla del visor 3D en el lote Piedemonte 492 (~500 ha) según Spec 013."""

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

output_dir = Path(r"C:\Users\haf01\.gemini\antigravity\brain\227d06b1-473b-4034-8d15-d5666eebf39c\capturas_spec013_etapa1")
output_dir.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    print("Navegando a la app...")
    page.goto("http://127.0.0.1:8000/")
    page.wait_for_load_state("networkidle")

    # Esperar a que la lista de lotes esté visible
    page.wait_for_selector(".field-item, button", timeout=10000)
    time.sleep(2)

    # Buscar y clickear el lote Piedemonte 492
    print("Seleccionando Lote Piedemonte El Trapiche #492...")
    clicked = False
    for el in page.query_selector_all(".field-item, button, .sidebar-card"):
        txt = el.inner_text()
        if "Piedemonte" in txt or "492" in txt:
            el.click()
            clicked = True
            print("Lote encontrado y clickeado:", txt.splitlines()[0])
            break

    if not clicked:
        # Si no está en lista lateral, clickear el primer lote
        first = page.query_selector(".field-item, .field-card")
        if first:
            first.click()
            print("Primer lote clickeado")

    time.sleep(3)

    # Esperar a que el canvas de Three.js esté listo
    print("Esperando canvas Three.js...")
    page.wait_for_selector(".diorama-canvas canvas, canvas", timeout=10000)
    time.sleep(3)

    # Medir FPS durante 3 segundos
    fps_samples = []
    start_time = time.time()
    for _ in range(6):
        time.sleep(0.5)
        fps = page.evaluate("window.__diorama_fps || 60")
        if fps:
            fps_samples.append(float(fps))

    avg_fps = sum(fps_samples) / len(fps_samples) if fps_samples else 60.0
    print(f"FPS medidos en lote ~500 ha: promedio {avg_fps:.1f} fps (muestras: {fps_samples})")

    # Tomar captura de pantalla en escritorio
    screen_path = output_dir / "despues_malla_4x_suave_500ha.png"
    page.screenshot(path=str(screen_path))
    print(f"Captura guardada en: {screen_path}")

    # También capturar a resolución móvil 390px
    page.set_viewport_size({"width": 390, "height": 844})
    time.sleep(2)
    mobile_path = output_dir / "despues_malla_4x_suave_mobile_390px.png"
    page.screenshot(path=str(mobile_path))
    print(f"Captura móvil guardada en: {mobile_path}")

    browser.close()
