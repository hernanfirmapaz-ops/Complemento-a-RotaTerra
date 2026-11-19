"""Sistemas de referencia: elegir la zona UTM métrica del área de trabajo."""

import numpy as np

WGS84 = "EPSG:4326"


def utm_epsg(lon: float, lat: float) -> int:
    """Código EPSG de la zona UTM WGS84 que contiene el punto (326xx norte, 327xx sur).

    Ejemplo: San Luis (-65.7, -33.3) -> zona 20 sur -> EPSG:32720.
    """
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError(f"Coordenadas fuera de rango: lon={lon}, lat={lat}")
    zona = min(int((lon + 180) // 6) + 1, 60)
    return (32600 if lat >= 0 else 32700) + zona


def to_crs(xs, ys, src: str, dst: str) -> tuple[np.ndarray, np.ndarray]:
    """Transforma arreglos de coordenadas entre dos CRS (usa PROJ vía rasterio)."""
    from rasterio.warp import transform

    x2, y2 = transform(src, dst, list(np.asarray(xs, dtype=float)), list(np.asarray(ys, dtype=float)))
    return np.asarray(x2), np.asarray(y2)
