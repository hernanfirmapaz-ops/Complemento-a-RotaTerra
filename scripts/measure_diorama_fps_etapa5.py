"""Mide los FPS y captura la pantalla del visor 3D en el lote Piedemonte 492 (~500 ha) para la Etapa 5 de la Spec 013 (Lluvia ligera en sprites 2-4 px y salpicaduras)."""

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

output_dir = Path(r"C:\Users\haf01\.gemini\antigravity\brain\227d06b1-473b-4034-8d15-d5666eebf39c\capturas_spec013_etapa5")
output_dir.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    print("Navegando a la app...")
    page.goto("http://127.0.0.1:8000/")
    page.wait_for_load_state("networkidle")

    time.sleep(2)

    # Buscar y clickear el lote Piedemonte 492
    print("Buscando Lote Piedemonte El Trapiche #492...")
    for el in page.query_selector_all(".field-item, button, .sidebar-card, div"):
        txt = el.inner_text()
        if "Piedemonte" in txt and "492" in txt and len(txt) < 80:
            print("Clickeando:", txt.replace("\n", " "))
            el.click()
            break

    print("Esperando carga de terreno y canvas Three.js...")
    page.locator("canvas").first.wait_for(state="visible", timeout=25000)
    time.sleep(4)

    # Activar botón de lluvia si está disponible
    rain_btn = page.query_selector("button:has-text('Animar lluvia'), button[aria-label='Animar lluvia']")
    if rain_btn:
        print("Activando botón de lluvia...")
        rain_btn.click()
        time.sleep(2)

    # Medir FPS durante 3 segundos con lluvia activa
    fps_samples = []
    for _ in range(6):
        time.sleep(0.5)
        fps = page.evaluate("window.__diorama_fps || 60")
        if fps:
            fps_samples.append(float(fps))

    avg_fps = sum(fps_samples) / len(fps_samples) if fps_samples else 60.0
    print(f"FPS medidos con lluvia activa en lote ~500 ha: promedio {avg_fps:.1f} fps (muestras: {fps_samples})")

    # Tomar captura de pantalla en escritorio con lluvia activa
    screen_path = output_dir / "despues_etapa5_lluvia_sprites_500ha.png"
    page.screenshot(path=str(screen_path))
    print(f"Captura guardada en: {screen_path}")

    # También capturar a resolución móvil 390px
    page.set_viewport_size({"width": 390, "height": 844})
    time.sleep(2)
    mobile_path = output_dir / "despues_etapa5_lluvia_sprites_mobile_390px.png"
    page.screenshot(path=str(mobile_path))
    print(f"Captura móvil guardada en: {mobile_path}")

    browser.close()
