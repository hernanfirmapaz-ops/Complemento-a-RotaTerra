"""Análisis del terreno sobre el DEM de trabajo en UTM: pendiente, orientación, cota, perfil y malla 3D.

Todas las operaciones trabajan en metros (UTM). Las celdas sin dato (NaN) se propagan: nunca se rellenan.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geoprocessing.crs import WGS84, to_crs

MAX_MUESTRAS_PERFIL = 2000
MAX_LADO_MALLA = 512


@dataclass
class Dem:
    z: np.ndarray  # float32, NaN = sin dato; fila 0 = borde norte
    transform: object  # affine.Affine
    crs: str

    @property
    def pixel(self) -> float:
        return abs(self.transform.a)

    @classmethod
    def open(cls, path: Path) -> "Dem":
        import rasterio

        with rasterio.open(path) as src:
            z = src.read(1).astype("float32")
            if src.nodata is not None and not math.isnan(src.nodata):
                z[z == src.nodata] = np.nan
            return cls(z=z, transform=src.transform, crs=src.crs.to_string())

    def rowcol_f(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Fila/columna fraccionarias referidas a los centros de celda."""
        t = self.transform
        col = (np.asarray(x) - t.c) / t.a - 0.5
        row = (np.asarray(y) - t.f) / t.e - 0.5
        return row, col

    def xy_of_cell(self, row, col) -> tuple[np.ndarray, np.ndarray]:
        t = self.transform
        return t.c + (np.asarray(col) + 0.5) * t.a, t.f + (np.asarray(row) + 0.5) * t.e


def slope_aspect(z: np.ndarray, dx: float, dy: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pendiente (%), pendiente (grados) y orientación (grados desde el norte, horario) por el método de Horn.

    Las celdas del borde y las vecinas de un NaN quedan en NaN (no se extrapola).
    Orientación: hacia dónde mira la ladera (dirección de máximo descenso). NaN en terreno plano.
    """
    p = np.pad(z.astype("float64"), 1, mode="constant", constant_values=np.nan)
    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    d, f = p[1:-1, :-2], p[1:-1, 2:]
    g, h, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * dx)  # hacia el este
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * dy)  # hacia el sur (filas crecen al sur)
    grad = np.hypot(dzdx, dzdy)
    pct = 100 * grad
    grados = np.degrees(np.arctan(grad))
    # dirección de descenso: vector (-dzdx este, +dzdy norte); azimut desde el norte
    with np.errstate(invalid="ignore"):
        aspecto = (np.degrees(np.arctan2(-dzdx, dzdy)) + 360) % 360
    aspecto[grad < 1e-6] = np.nan
    return pct.astype("float32"), grados.astype("float32"), aspecto.astype("float32")


def bilinear(dem: Dem, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Cota interpolada bilinealmente. NaN si el punto cae fuera o si alguna de las 4 celdas no tiene dato."""
    row, col = dem.rowcol_f(np.atleast_1d(x), np.atleast_1d(y))
    alto, ancho = dem.z.shape
    r0, c0 = np.floor(row).astype(int), np.floor(col).astype(int)
    fr, fc = row - r0, col - c0
    fuera = (r0 < 0) | (c0 < 0) | (r0 + 1 >= alto) | (c0 + 1 >= ancho)
    r0c, c0c = np.clip(r0, 0, alto - 2), np.clip(c0, 0, ancho - 2)
    z = dem.z
    v = (z[r0c, c0c] * (1 - fr) * (1 - fc) + z[r0c, c0c + 1] * (1 - fr) * fc
         + z[r0c + 1, c0c] * fr * (1 - fc) + z[r0c + 1, c0c + 1] * fr * fc)
    v = v.astype("float64")
    v[fuera] = np.nan
    return v


def _r(v, nd=2):
    return None if v is None or not np.isfinite(v) else round(float(v), nd)


def point_info(dem: Dem, lon: float, lat: float, mascara_lote: np.ndarray | None = None) -> dict:
    xs, ys = to_crs([lon], [lat], WGS84, dem.crs)
    x, y = float(xs[0]), float(ys[0])
    row, col = dem.rowcol_f(x, y)
    fila, columna = int(round(float(row))), int(round(float(col)))
    alto, ancho = dem.z.shape
    dentro_dem = 0 <= fila < alto and 0 <= columna < ancho
    resultado = {"lon": lon, "lat": lat, "x_utm": round(x, 2), "y_utm": round(y, 2), "inside_dem": dentro_dem,
                 "inside_field": None, "elevation_m": None, "cell_elevation_m": None, "slope_pct": None,
                 "slope_deg": None, "aspect_deg": None, "row": fila, "col": columna}
    if not dentro_dem:
        return resultado
    r0, r1, c0, c1 = max(fila - 1, 0), min(fila + 2, alto), max(columna - 1, 0), min(columna + 2, ancho)
    pct, grados, aspecto = slope_aspect(dem.z[r0:r1, c0:c1], dem.pixel, dem.pixel)
    rr, cc = fila - r0, columna - c0
    resultado.update(
        inside_field=bool(mascara_lote[fila, columna]) if mascara_lote is not None else None,
        elevation_m=_r(bilinear(dem, np.array([x]), np.array([y]))[0]),
        cell_elevation_m=_r(dem.z[fila, columna]),
        slope_pct=_r(pct[rr, cc]), slope_deg=_r(grados[rr, cc]), aspect_deg=_r(aspecto[rr, cc], 0),
    )
    return resultado


def profile(dem: Dem, coords_lonlat: list[list[float]], paso_m: float | None = None) -> dict:
    """Perfil altimétrico a lo largo de una polilínea (lon, lat), muestreado cada `paso_m` (por defecto medio píxel)."""
    if len(coords_lonlat) < 2:
        raise ValueError("El perfil necesita al menos 2 puntos")
    lons = [c[0] for c in coords_lonlat]
    lats = [c[1] for c in coords_lonlat]
    xs, ys = to_crs(lons, lats, WGS84, dem.crs)
    tramos = np.hypot(np.diff(xs), np.diff(ys))
    largo = float(tramos.sum())
    if largo <= 0:
        raise ValueError("La línea del perfil tiene largo cero")
    paso = paso_m or dem.pixel / 2
    paso = max(paso, largo / MAX_MUESTRAS_PERFIL)
    acumulado = np.concatenate([[0], np.cumsum(tramos)])
    distancias = np.append(np.arange(0, largo, paso), largo)
    mx = np.interp(distancias, acumulado, xs)
    my = np.interp(distancias, acumulado, ys)
    z = bilinear(dem, mx, my)
    mlon, mlat = to_crs(mx, my, dem.crs, WGS84)
    validos = np.isfinite(z)
    resumen = {"length_m": round(largo, 1), "step_m": round(paso, 2), "samples": int(len(z)),
               "valid_samples": int(validos.sum()), "min_m": None, "max_m": None, "range_m": None,
               "start_end_diff_m": None, "mean_abs_slope_pct": None}
    if validos.any():
        zv = z[validos]
        resumen.update(min_m=_r(zv.min()), max_m=_r(zv.max()), range_m=_r(zv.max() - zv.min()))
        if validos[0] and validos[-1]:
            resumen["start_end_diff_m"] = _r(z[-1] - z[0])
        dz = np.diff(z)
        dd = np.diff(distancias)
        ok = np.isfinite(dz) & (dd > 0)
        if ok.any():
            resumen["mean_abs_slope_pct"] = _r(100 * np.average(np.abs(dz[ok] / dd[ok]), weights=dd[ok]))
    return {
        "summary": resumen,
        "vertices_distance_m": [round(float(d), 1) for d in acumulado],
        "samples": [{"distance_m": round(float(d), 2), "elevation_m": _r(e), "lon": round(float(lo), 7),
                     "lat": round(float(la), 7)} for d, e, lo, la in zip(distancias, z, mlon, mlat)],
    }


def mesh(dem: Dem, mascara_lote: np.ndarray, anillos_lote_utm: list[np.ndarray],
         max_lado: int = 256) -> dict:
    """Grilla de alturas para la escena 3D, con coordenadas lon/lat por vértice y el perímetro del lote con cota.

    Si el DEM supera `max_lado` celdas por lado se submuestrea por paso fijo (nivel de detalle simple de Fase 0)
    y se informa el factor; el cálculo de cota, pendiente y perfil siempre usa la resolución completa.
    """
    max_lado = int(min(max(max_lado, 16), MAX_LADO_MALLA))
    alto, ancho = dem.z.shape
    k = max(1, math.ceil(max(alto, ancho) / max_lado))
    filas = np.arange(0, alto, k)
    cols = np.arange(0, ancho, k)
    z = dem.z[np.ix_(filas, cols)]
    rr, cc = np.meshgrid(filas, cols, indexing="ij")
    x, y = dem.xy_of_cell(rr.ravel(), cc.ravel())
    lon, lat = to_crs(x, y, dem.crs, WGS84)

    perimetro = []
    for anillo in anillos_lote_utm:
        # densificar a medio píxel para que la línea siga el relieve
        tramos = np.hypot(np.diff(anillo[:, 0]), np.diff(anillo[:, 1]))
        acum = np.concatenate([[0], np.cumsum(tramos)])
        d = np.append(np.arange(0, acum[-1], dem.pixel / 2), acum[-1])
        px, py = np.interp(d, acum, anillo[:, 0]), np.interp(d, acum, anillo[:, 1])
        pz = bilinear(dem, px, py)
        plon, plat = to_crs(px, py, dem.crs, WGS84)
        perimetro.append([[round(float(a), 7), round(float(b), 7), _r(c)] for a, b, c in zip(plon, plat, pz)])

    zf = z[np.isfinite(z)]
    return {
        "rows": int(len(filas)), "cols": int(len(cols)), "decimation": k,
        "pixel_size_m": dem.pixel, "mesh_cell_size_m": dem.pixel * k,
        "z_min": _r(zf.min()) if zf.size else None, "z_max": _r(zf.max()) if zf.size else None,
        "lon": [round(float(v), 7) for v in lon],
        "lat": [round(float(v), 7) for v in lat],
        "z": [None if not np.isfinite(v) else round(float(v), 2) for v in z.ravel()],
        "in_field": [bool(v) for v in mascara_lote[np.ix_(filas, cols)].ravel()],
        "boundary": perimetro,
    }


def field_rings_utm(geometria_utm) -> list[np.ndarray]:
    anillos = []
    for poligono in getattr(geometria_utm, "geoms", [geometria_utm]):
        anillos.append(np.asarray(poligono.exterior.coords)[:, :2])
        anillos.extend(np.asarray(i.coords)[:, :2] for i in poligono.interiors)
    return anillos
