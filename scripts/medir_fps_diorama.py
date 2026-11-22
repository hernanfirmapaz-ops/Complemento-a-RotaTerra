"""Mide los FPS y captura la pantalla del visor 3D en un lote agronómico (por ej. Piedemonte 492 ~500 ha).

Herramienta manual de diagnóstico y auditoría visual contra el servidor local (http://127.0.0.1:8000).
No forma parte del pipeline automático de pytest.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Medición de FPS y capturas del visor 3D de RotaTerra")
    parser.add_argument(
        "--salida",
        type=Path,
        default=Path("./capturas"),
        help="Directorio de destino para las capturas (por defecto ./capturas)",
    )
    parser.add_argument(
        "--lote",
        type=str,
        default="492",
        help="Texto para identificar el lote en la interfaz (por defecto '492')",
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://127.0.0.1:8000/",
        help="URL base de la aplicación (por defecto http://127.0.0.1:8000/)",
    )
    parser.add_argument(
        "--con-lluvia",
        action="store_true",
        help="Activa la animación de lluvia y salpicaduras antes de medir",
    )
    parser.add_argument(
        "--muestras",
        type=int,
        default=6,
        help="Cantidad de muestras de FPS a tomar (intervalos de 500 ms)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Ejecuta el navegador con ventana visible (útil para GPU real)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.salida.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        print(f"Navegando a {args.url}...")
        page.goto(args.url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        print(f"Buscando lote con criterio '{args.lote}'...")
        clicked = False
        for el in page.query_selector_all(".field-item, button, .sidebar-card, div"):
            txt = el.inner_text()
            if args.lote in txt and len(txt) < 80:
                print("Lote encontrado y clickeado:", txt.replace("\n", " "))
                el.click()
                clicked = True
                break

        if not clicked:
            print("Aviso: no se encontró por coincidencia exacta, seleccionando primer elemento de lista...")
            first = page.query_selector(".field-item, .field-card, [role='button']")
            if first:
                first.click()

        print("Esperando renderizado de la escena Three.js...")
        page.locator("canvas").first.wait_for(state="visible", timeout=25000)
        time.sleep(3)

        if args.con_lluvia:
            rain_btn = page.query_selector("button:has-text('Animar lluvia'), button[aria-label='Animar lluvia']")
            if rain_btn:
                print("Activando animación de lluvia y salpicaduras...")
                rain_btn.click()
                time.sleep(2)

        print(f"Registrando {args.muestras} muestras reales de FPS...")
        fps_samples: list[float] = []
        for _ in range(args.muestras):
            time.sleep(0.5)
            val = page.evaluate("window.__diorama_fps")
            if val is not None and val > 0:
                fps_samples.append(float(val))

        if not fps_samples:
            browser.close()
            raise RuntimeError(
                "No se pudieron registrar muestras reales de FPS en window.__diorama_fps. "
                "Verifique que el canvas Three.js esté activo y renderizando cuadros."
            )

        avg_fps = sum(fps_samples) / len(fps_samples)
        min_fps = min(fps_samples)
        max_fps = max(fps_samples)
        print(f"Muestras reales registradas ({len(fps_samples)}): {fps_samples}")
        print(f"FPS: promedio {avg_fps:.1f} fps | mínimo {min_fps:.1f} fps | máximo {max_fps:.1f} fps")

        # Captura escritorio 1440x900
        desktop_path = output_dir / "escritorio_1440px.png"
        page.screenshot(path=str(desktop_path))
        print(f"Captura de escritorio guardada en: {desktop_path}")

        # Captura móvil 390x844
        page.set_viewport_size({"width": 390, "height": 844})
        time.sleep(2)
        mobile_path = output_dir / "movil_390px.png"
        page.screenshot(path=str(mobile_path))
        print(f"Captura móvil guardada en: {mobile_path}")

        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error en medición de FPS: {exc}", file=sys.stderr)
        sys.exit(1)
