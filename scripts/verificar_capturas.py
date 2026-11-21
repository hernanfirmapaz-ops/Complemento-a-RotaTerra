"""Verificación visual y de rendimiento con Playwright.

Criterios:
1. Captura la primera pantalla a 390 px (móvil) y 1440 px (escritorio).
2. Falla si hay desplazamiento horizontal (scrollWidth > clientWidth).
3. Falla si en la primera pantalla se descarga Three.js (vendor-three) o MapLibre (vendor-maplibre).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def verificar_pantalla(url: str, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    viewports = [
        ("390px", 390, 844),
        ("1440px", 1440, 900),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for label, width, height in viewports:
            print(f"--- Verificando primera pantalla ({label}: {width}x{height}) ---")
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()

            peticiones: list[str] = []

            def on_request(req):
                peticiones.append(req.url)

            page.on("request", on_request)

            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)

            # 1. Verificar chunks pesados en primera pantalla
            for req_url in peticiones:
                if "vendor-three" in req_url:
                    raise AssertionError(f"[{label}] Error: se descargó vendor-three en primera pantalla: {req_url}")
                if "vendor-maplibre" in req_url:
                    raise AssertionError(f"[{label}] Error: se descargó vendor-maplibre en primera pantalla: {req_url}")

            # 2. Verificar desplazamiento horizontal
            scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
            client_width = page.evaluate("() => document.documentElement.clientWidth")
            print(f"[{label}] scrollWidth={scroll_width}, clientWidth={client_width}")

            if scroll_width > client_width:
                raise AssertionError(
                    f"[{label}] Error: desplazamiento horizontal detectado ({scroll_width} > {client_width})"
                )

            # 3. Guardar captura
            archivo_captura = output_dir / f"captura_{label}.png"
            page.screenshot(path=str(archivo_captura), full_page=False)
            print(f"[{label}] [OK] Captura guardada en: {archivo_captura}")

            context.close()

        browser.close()

    print("[EXITO] Todas las verificaciones visuales y de rendimiento pasaron correctamente.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Verificar capturas y bundles en primera pantalla")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="URL base de la app")
    parser.add_argument("--output-dir", default="dist-capturas", help="Directorio para guardar capturas")
    args = parser.parse_args()

    try:
        return verificar_pantalla(args.url, Path(args.output_dir))
    except Exception as exc:
        print(f"[FALLO] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
