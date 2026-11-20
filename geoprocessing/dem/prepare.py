"""Preparación del DEM de trabajo (SDD §6.1–6.2, pasos 1–4).

A partir del DEM original (que nunca se modifica) se genera un DEM derivado:
- reproyectado a la zona UTM del lote (metros);
- recortado al lote más una zona de aporte configurable (el agua puede venir de afuera del lote);
- con nodata como NaN, sin interpolar vacíos.

La resolución de salida nunca es más fina que la del original: no se inventa detalle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geoprocessing.fields import field_utm_geometry

BUFFER_MAX_M = 5000.0
MAX_CELDAS = 4000 * 4000  # límite de seguridad para no agotar memoria en Fase 0 (medir con datos reales)


class DemPreparationError(ValueError):
    """El DEM no se puede preparar para este lote (no lo cubre, es demasiado grande, etc.)."""


@dataclass
class PreparedDem:
    path: Path
    crs: str
    pixel_size_m: float
    width: int
    height: int
    bounds: tuple[float, float, float, float]  # en UTM
    buffer_m: float
    source_pixel_size_m: tuple[float, float]


def source_pixel_size_m(src) -> tuple[float, float]:
    """Tamaño de píxel del original en metros (x, y). Si está en grados, se convierte en la latitud central."""
    rx, ry = abs(src.transform.a), abs(src.transform.e)
    if src.crs.is_geographic:
        lat = (src.bounds.bottom + src.bounds.top) / 2
        return rx * 111_320 * math.cos(math.radians(lat)), ry * 110_574
    factor = src.crs.linear_units_factor[1] if src.crs.linear_units_factor else 1.0
    return rx * factor, ry * factor


def prepare_dem(source_path: Path, geometry_4326: dict, epsg: int, buffer_m: float, destino: Path) -> PreparedDem:
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject

    if not (0 <= buffer_m <= BUFFER_MAX_M):
        raise DemPreparationError(f"La zona de aporte debe estar entre 0 y {BUFFER_MAX_M:.0f} m")

    lote = field_utm_geometry(geometry_4326, epsg)
    area = lote.buffer(buffer_m) if buffer_m > 0 else lote
    crs_dst = f"EPSG:{epsg}"

    with rasterio.open(source_path) as src:
        px, py = source_pixel_size_m(src)
        # nunca más fino que el original: se toma el lado más grueso del píxel y se redondea a 0,1 m
        res = max(round(max(px, py), 1), 0.1)
        oeste, sur, este, norte = area.bounds
        oeste, sur = math.floor(oeste / res) * res, math.floor(sur / res) * res
        este, norte = math.ceil(este / res) * res, math.ceil(norte / res) * res
        ancho, alto = int(round((este - oeste) / res)), int(round((norte - sur) / res))
        if ancho * alto > MAX_CELDAS:
            raise DemPreparationError(
                f"El área (lote + aporte) requiere {ancho}×{alto} celdas a {res} m: reducí la zona de aporte "
                "o usá un DEM de menor resolución para esta fase.")
        transform = from_origin(oeste, norte, res, res)
        datos = np.full((alto, ancho), np.nan, dtype="float32")
        nodata_src = src.nodata if src.nodata is not None else np.nan
        reproject(
            source=rasterio.band(src, 1),
            destination=datos,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=nodata_src,
            dst_transform=transform,
            dst_crs=crs_dst,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
        etiquetas = dict(src.tags())
        etiquetas["DERIVED_FROM"] = source_path.name
        etiquetas["BUFFER_M"] = str(buffer_m)
        etiquetas["RESAMPLING"] = "bilinear"

    if not np.isfinite(datos).any():
        raise DemPreparationError("El DEM no cubre el lote ni su zona de aporte.")

    destino.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(destino, "w", driver="GTiff", height=alto, width=ancho, count=1, dtype="float32",
                       crs=crs_dst, transform=transform, nodata=np.nan, compress="deflate") as dst:
        dst.write(datos, 1)
        dst.update_tags(**etiquetas)

    return PreparedDem(path=destino, crs=crs_dst, pixel_size_m=res, width=ancho, height=alto,
                       bounds=(oeste, sur, este, norte), buffer_m=buffer_m,
                       source_pixel_size_m=(round(px, 3), round(py, 3)))
