"""Generadores de DEM SINTÉTICOS etiquetados para pruebas automatizadas (SDD §11.3, §17.4 y §17.8).

NUNCA usar estos generadores como datos reales en la interfaz de usuario.
Cada GeoTIFF generado lleva el tag `SYNTHETIC=TRUE` y `DESCRIPTION`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin


def synthetic_square_field_geojson(
    lon0: float = -65.70,
    lat0: float = -33.30,
    d_deg: float = 0.01,
    name: str = "Lote Sintético de Prueba (NO REAL)",
) -> dict:
    """Polígono cuadrado sintético (~1 km de lado) en EPSG:4326."""
    anillo = [
        [lon0, lat0],
        [lon0 + d_deg, lat0],
        [lon0 + d_deg, lat0 + d_deg],
        [lon0, lat0 + d_deg],
        [lon0, lat0],
    ]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": name, "synthetic": True},
                "geometry": {"type": "Polygon", "coordinates": [anillo]},
            }
        ],
    }


def write_synthetic_inclined_plane_utm(
    path: Path,
    epsg: int = 32720,
    x_origin: float = 248_000.0,
    y_origin: float = 6_313_900.0,
    pixel_m: float = 10.0,
    width: int = 220,
    height: int = 220,
    z0: float = 500.0,
    slope_east: float = 0.03,
    slope_south: float = 0.04,
) -> Path:
    """Escribe un DEM SINTÉTICO con plano inclinado exacto:

        z(x, y) = z0 + slope_east * (x - x_center_0) + slope_south * (y_center_0 - y)

    Pendiente analítica exacta en toda celda interior:
        hypot(slope_east, slope_south) * 100  (con 0.03 y 0.04 -> 5.00 %).
    """
    transform = from_origin(x_origin, y_origin, pixel_m, pixel_m)
    cols = np.arange(width, dtype="float64")
    rows = np.arange(height, dtype="float64")
    cc, rr = np.meshgrid(cols, rows)
    z = (z0 + slope_east * (cc * pixel_m) + slope_south * (rr * pixel_m)).astype("float32")

    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs=f"EPSG:{epsg}",
        transform=transform,
        nodata=np.nan,
    ) as dst:
        dst.write(z, 1)
        dst.update_tags(
            SYNTHETIC="TRUE",
            DESCRIPTION="DEM SINTETICO de plano inclinado para tests unitarios (no real)",
            SLOPE_EAST=str(slope_east),
            SLOPE_SOUTH=str(slope_south),
        )
    return path


def write_synthetic_bowl_utm(
    path: Path,
    epsg: int = 32720,
    x_origin: float = 248_000.0,
    y_origin: float = 6_313_900.0,
    pixel_m: float = 10.0,
    width: int = 220,
    height: int = 220,
    z_min: float = 480.0,
    curvature: float = 2e-5,
) -> Path:
    """Escribe un DEM SINTÉTICO parabólico (depresión cerrada en el centro)."""
    transform = from_origin(x_origin, y_origin, pixel_m, pixel_m)
    cols = np.arange(width, dtype="float64") - (width - 1) / 2
    rows = np.arange(height, dtype="float64") - (height - 1) / 2
    cc, rr = np.meshgrid(cols * pixel_m, rows * pixel_m)
    z = (z_min + curvature * (cc**2 + rr**2)).astype("float32")

    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs=f"EPSG:{epsg}",
        transform=transform,
        nodata=np.nan,
    ) as dst:
        dst.write(z, 1)
        dst.update_tags(
            SYNTHETIC="TRUE",
            DESCRIPTION="DEM SINTETICO parabolico (cuenco) para tests unitarios (no real)",
        )
    return path
