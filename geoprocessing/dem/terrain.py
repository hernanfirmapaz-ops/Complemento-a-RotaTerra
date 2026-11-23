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


def hillshade(z: np.ndarray, dx: float, dy: float, azimuth_deg: float = 315.0,
              altitude_deg: float = 45.0) -> np.ndarray:
    """Sombreado analítico de relieve (0..1) con iluminación solar configurable (SDD §4.3 y §6.2).

    Por defecto: sol desde el noroeste (315°) a 45° sobre el horizonte.
    """
    p = np.pad(z.astype("float64"), 1, mode="constant", constant_values=np.nan)
    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    d, f = p[1:-1, :-2], p[1:-1, 2:]
    g, h, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * dx)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * dy)
    slope_rad = np.arctan(np.hypot(dzdx, dzdy))
    aspect_rad = np.arctan2(dzdy, -dzdx)
    zenith_rad = math.radians(90.0 - altitude_deg)
    az_math = math.radians((360.0 - azimuth_deg + 90.0) % 360.0)
    hs = (math.cos(zenith_rad) * np.cos(slope_rad)
          + math.sin(zenith_rad) * np.sin(slope_rad) * np.cos(az_math - aspect_rad))
    return np.clip(hs, 0.0, 1.0).astype("float32")


def contours_geojson(dem: Dem, interval_m: float | None = None, max_levels: int = 30) -> dict:
    """Extrae curvas de nivel (GeoJSON FeatureCollection de LineString) mediante marching squares en UTM."""
    z = dem.z
    zf = z[np.isfinite(z)]
    if zf.size < 4:
        return {"type": "FeatureCollection", "interval_m": interval_m or 0.0, "features": []}
    z_min, z_max = float(zf.min()), float(zf.max())
    span = z_max - z_min
    if span < 0.2:
        return {"type": "FeatureCollection", "interval_m": interval_m or 0.0, "features": []}

    if interval_m is None or interval_m <= 0:
        # Elegir equidistancia legible según el desnivel total
        raw = span / 10.0
        for cand in (0.5, 1.0, 2.0, 2.5, 5.0, 10.0, 20.0, 25.0, 50.0, 100.0):
            if cand >= raw:
                interval_m = cand
                break
        else:
            interval_m = round(raw, 1)

    first = math.ceil(z_min / interval_m) * interval_m
    levels = np.arange(first, z_max, interval_m)
    if len(levels) > max_levels:
        step = math.ceil(len(levels) / max_levels)
        interval_m = interval_m * step
        first = math.ceil(z_min / interval_m) * interval_m
        levels = np.arange(first, z_max, interval_m)

    alto, ancho = z.shape
    z00 = z[:-1, :-1]
    z10 = z[:-1, 1:]   # derecha (col+1)
    z11 = z[1:, 1:]    # abajo-derecha
    z01 = z[1:, :-1]   # abajo (row+1)
    valid_cell = np.isfinite(z00) & np.isfinite(z10) & np.isfinite(z11) & np.isfinite(z01)

    features = []
    # Tabla de aristas de marching squares: 0=arriba, 1=derecha, 2=abajo, 3=izquierda
    edge_table: dict[int, list[tuple[int, int]]] = {
        1: [(3, 0)], 2: [(0, 1)], 3: [(3, 1)], 4: [(1, 2)],
        5: [(3, 0), (1, 2)], 6: [(0, 2)], 7: [(3, 2)], 8: [(2, 3)],
        9: [(0, 2)], 10: [(0, 3), (1, 2)], 11: [(1, 2)], 12: [(1, 3)],
        13: [(0, 1)], 14: [(3, 0)],
    }

    for lvl in levels:
        lvl_f = float(lvl)
        code = ((z00 >= lvl_f).astype(int)
                | ((z10 >= lvl_f).astype(int) << 1)
                | ((z11 >= lvl_f).astype(int) << 2)
                | ((z01 >= lvl_f).astype(int) << 3))
        code = np.where(valid_cell, code, 0)
        rs, cs = np.nonzero((code > 0) & (code < 15))
        if len(rs) == 0:
            continue

        segs_utm: list[tuple[tuple[float, float], tuple[float, float]]] = []
        for r, c in zip(rs.tolist(), cs.tolist()):
            k = int(code[r, c])
            pairs = edge_table.get(k)
            if not pairs:
                continue
            v00, v10, v11, v01 = float(z00[r, c]), float(z10[r, c]), float(z11[r, c]), float(z01[r, c])

            def _edge_pt(e: int) -> tuple[float, float]:
                if e == 0:  # arriba: (r, c) -> (r, c+1)
                    t = (lvl_f - v00) / (v10 - v00) if v10 != v00 else 0.5
                    rr, cc = float(r), c + float(np.clip(t, 0.0, 1.0))
                elif e == 1:  # derecha: (r, c+1) -> (r+1, c+1)
                    t = (lvl_f - v10) / (v11 - v10) if v11 != v10 else 0.5
                    rr, cc = r + float(np.clip(t, 0.0, 1.0)), float(c + 1)
                elif e == 2:  # abajo: (r+1, c) -> (r+1, c+1)
                    t = (lvl_f - v01) / (v11 - v01) if v11 != v01 else 0.5
                    rr, cc = float(r + 1), c + float(np.clip(t, 0.0, 1.0))
                else:  # izquierda: (r, c) -> (r+1, c)
                    t = (lvl_f - v00) / (v01 - v00) if v01 != v00 else 0.5
                    rr, cc = r + float(np.clip(t, 0.0, 1.0)), float(c)
                x = dem.transform.c + (cc + 0.5) * dem.transform.a
                y = dem.transform.f + (rr + 0.5) * dem.transform.e
                return (round(float(x), 2), round(float(y), 2))

            for e1, e2 in pairs:
                p1, p2 = _edge_pt(e1), _edge_pt(e2)
                if p1 != p2:
                    segs_utm.append((p1, p2))

        if not segs_utm:
            continue

        # Coser segmentos que comparten extremo en polilíneas continuas
        adj: dict[tuple[float, float], list[int]] = {}
        for idx, (p1, p2) in enumerate(segs_utm):
            adj.setdefault(p1, []).append(idx)
            adj.setdefault(p2, []).append(idx)
        used = [False] * len(segs_utm)
        lines_utm: list[list[tuple[float, float]]] = []
        for idx, (p1, p2) in enumerate(segs_utm):
            if used[idx]:
                continue
            used[idx] = True
            chain = [p1, p2]
            # extender hacia adelante
            while True:
                cur = chain[-1]
                nxt = next((j for j in adj.get(cur, []) if not used[j]), None)
                if nxt is None:
                    break
                used[nxt] = True
                a, b = segs_utm[nxt]
                chain.append(b if a == cur else a)
            # extender hacia atrás
            while True:
                cur = chain[0]
                prv = next((j for j in adj.get(cur, []) if not used[j]), None)
                if prv is None:
                    break
                used[prv] = True
                a, b = segs_utm[prv]
                chain.insert(0, b if a == cur else a)
            lines_utm.append(chain)

        # Transformar todos los vértices del nivel a WGS84 en una sola llamada
        flat_x = [pt[0] for line in lines_utm for pt in line]
        flat_y = [pt[1] for line in lines_utm for pt in line]
        flat_lon, flat_lat = to_crs(flat_x, flat_y, dem.crs, WGS84)
        pos = 0
        coords_lines = []
        for line in lines_utm:
            n = len(line)
            coords_lines.append(
                [[round(float(flat_lon[pos + i]), 7), round(float(flat_lat[pos + i]), 7)] for i in range(n)]
            )
            pos += n

        features.append({
            "type": "Feature",
            "properties": {"elevation_m": round(lvl_f, 2)},
            "geometry": {
                "type": "MultiLineString" if len(coords_lines) > 1 else "LineString",
                "coordinates": coords_lines if len(coords_lines) > 1 else coords_lines[0],
            },
        })

    return {
        "type": "FeatureCollection",
        "interval_m": round(float(interval_m), 2),
        "features": features,
    }


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
         max_lado: int = 256, extra_grids: dict[str, np.ndarray] | None = None) -> dict:
    """Grilla de alturas para la escena 3D, con coordenadas lon/lat por vértice y el perímetro del lote con cota.

    Si el DEM supera `max_lado` celdas por lado se submuestrea por paso fijo
    y se informa el factor; el cálculo de cota, pendiente, hidrología y perfil siempre usa la resolución completa.
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

    pct_full, _, _ = slope_aspect(dem.z, dem.pixel, dem.pixel)
    hs_full = hillshade(dem.z, dem.pixel, dem.pixel)
    pct_sub = pct_full[np.ix_(filas, cols)].ravel()
    hs_sub = hs_full[np.ix_(filas, cols)].ravel()

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
    out = {
        "rows": int(len(filas)), "cols": int(len(cols)), "decimation": k,
        "pixel_size_m": dem.pixel, "mesh_cell_size_m": dem.pixel * k,
        "z_min": _r(zf.min()) if zf.size else None, "z_max": _r(zf.max()) if zf.size else None,
        "lon": [round(float(v), 7) for v in lon],
        "lat": [round(float(v), 7) for v in lat],
        "z": [None if not np.isfinite(v) else round(float(v), 2) for v in z.ravel()],
        "in_field": [bool(v) for v in mascara_lote[np.ix_(filas, cols)].ravel()],
        "slope_pct": [_r(v, 2) for v in pct_sub],
        "hillshade": [_r(v, 3) for v in hs_sub],
        "boundary": perimetro,
    }
    if extra_grids:
        for key, arr in extra_grids.items():
            sub = arr[np.ix_(filas, cols)].ravel()
            if np.issubdtype(sub.dtype, np.integer):
                out[key] = [int(v) for v in sub]
            else:
                out[key] = [_r(v, 4) for v in sub]
    return out


def field_rings_utm(geometria_utm) -> list[np.ndarray]:
    anillos = []
    for poligono in getattr(geometria_utm, "geoms", [geometria_utm]):
        anillos.append(np.asarray(poligono.exterior.coords)[:, :2])
        anillos.extend(np.asarray(i.coords)[:, :2] for i in poligono.interiors)
    return anillos


def smooth_dem_whitebox(
    dem: Dem,
    filter_size: int = 15,
    norm_diff: float = 25.0,
    num_iter: int = 4,
    max_diff: float | None = 2.5,
) -> np.ndarray:
    """Suavizado con preservación de bordes (Feature-Preserving Smoothing) de WhiteboxTools."""
    import tempfile

    import rasterio
    import whitebox

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        in_tif = tmp_path / "raw.tif"
        out_tif = tmp_path / "smooth.tif"
        alto, ancho = dem.z.shape
        with rasterio.open(
            in_tif,
            "w",
            driver="GTiff",
            height=alto,
            width=ancho,
            count=1,
            dtype="float32",
            crs=dem.crs,
            transform=dem.transform,
            nodata=np.nan,
        ) as dst:
            dst.write(dem.z.astype("float32"), 1)

        wbt = whitebox.WhiteboxTools()
        wbt.verbose = False
        args = {
            "dem": str(in_tif),
            "output": str(out_tif),
            "filter": filter_size,
            "norm_diff": norm_diff,
            "num_iter": num_iter,
        }
        if max_diff is not None:
            args["max_diff"] = max_diff
        wbt.feature_preserving_smoothing(**args)
        with rasterio.open(out_tif) as src:
            return src.read(1).astype("float32")


def moving_plane_slope(
    z: np.ndarray,
    dx: float,
    dy: float,
    window_size: int = 5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pendiente y aspecto por ajuste local de plano por mínimos cuadrados en ventana móvil WxW."""
    from scipy.ndimage import correlate1d

    w = int(window_size)
    if w % 2 == 0:
        w += 1
    k = w // 2
    weights_1d = np.arange(-k, k + 1, dtype=np.float64)
    sum_sq = float(np.sum(weights_1d ** 2))
    denom_x = float(w * sum_sq * dx)
    denom_y = float(w * sum_sq * dy)

    z_64 = z.astype(np.float64)
    # dz/dx hacia el este
    dzdx = correlate1d(z_64, weights_1d, axis=1, mode="reflect")
    dzdx = correlate1d(dzdx, np.ones(w, dtype=np.float64), axis=0, mode="reflect") / denom_x

    # dz/dy hacia el sur (filas crecen al sur)
    dzdy = correlate1d(z_64, weights_1d, axis=0, mode="reflect")
    dzdy = correlate1d(dzdy, np.ones(w, dtype=np.float64), axis=1, mode="reflect") / denom_y

    grad = np.hypot(dzdx, dzdy)
    pct = (100.0 * grad).astype(np.float32)
    grados = np.degrees(np.arctan(grad)).astype(np.float32)
    with np.errstate(invalid="ignore"):
        aspecto = (np.degrees(np.arctan2(-dzdx, dzdy)) + 360.0) % 360.0
    aspecto[grad < 1e-6] = np.nan
    return pct, grados, aspecto.astype(np.float32)


def slope_for_hydrology(
    dem: Dem,
    wbt_filter: int | None = None,
    wbt_norm_diff: float | None = None,
    wbt_num_iter: int | None = None,
    wbt_max_diff: float | None = None,
    fallback_window: int | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calcula la pendiente (%) y orientación filtradas para procesos hidrológicos (LS, TWI, SPI, zonas).

    Reduce la sobrestimación del gradiente por ruido instrumental en llanura (Spec 014 / Auditoría Relieve).
    - Usa WhiteboxTools Feature-Preserving Smoothing si está disponible.
    - Usa ajuste local de plano por mínimos cuadrados en ventana móvil como fallback.
    """
    from geoprocessing.hydrology.conditioning import is_whitebox_available
    from geoprocessing.supuestos import (
        SUPUESTO_SLOPE_SMOOTHING_FALLBACK_WINDOW,
        SUPUESTO_SLOPE_SMOOTHING_WHITEBOX_FILTER,
        SUPUESTO_SLOPE_SMOOTHING_WHITEBOX_ITER,
        SUPUESTO_SLOPE_SMOOTHING_WHITEBOX_MAX_DIFF_M,
        SUPUESTO_SLOPE_SMOOTHING_WHITEBOX_NORM_DIFF,
    )

    if is_whitebox_available():
        f_size = int(wbt_filter or SUPUESTO_SLOPE_SMOOTHING_WHITEBOX_FILTER.valor)
        n_diff = float(wbt_norm_diff or SUPUESTO_SLOPE_SMOOTHING_WHITEBOX_NORM_DIFF.valor)
        n_iter = int(wbt_num_iter or SUPUESTO_SLOPE_SMOOTHING_WHITEBOX_ITER.valor)
        m_diff = float(wbt_max_diff if wbt_max_diff is not None else SUPUESTO_SLOPE_SMOOTHING_WHITEBOX_MAX_DIFF_M.valor)

        z_smooth = smooth_dem_whitebox(
            dem=dem,
            filter_size=f_size,
            norm_diff=n_diff,
            num_iter=n_iter,
            max_diff=m_diff,
        )
        return slope_aspect(z_smooth, dem.pixel, dem.pixel)

    win = int(fallback_window or SUPUESTO_SLOPE_SMOOTHING_FALLBACK_WINDOW.valor)
    return moving_plane_slope(dem.z, dem.pixel, dem.pixel, window_size=win)


def fit_plane_to_field(dem: Dem, field_mask: np.ndarray) -> dict:
    """Ajusta un plano por mínimos cuadrados sobre las celdas del lote (FAO T0231E ec. 117 / Spec 014 §5.1).

    Z(X, Y) = a + b*(X - X_bar) + c*(Y - Y_bar)
    Donde b = dz/dx (Oeste-Este), c = dz/dy (Sur-Norte).
    """
    valid = field_mask & np.isfinite(dem.z)
    if not np.any(valid):
        return {
            "slope_pct": 0.0,
            "aspect_deg": None,
            "r_squared": 0.0,
            "z_mean_m": 0.0,
            "b_dz_dx": 0.0,
            "c_dz_dy": 0.0,
            "description": "Sin datos de relieve en el lote",
        }

    rows, cols = np.where(valid)
    xs, ys = dem.xy_of_cell(rows, cols)
    zs = dem.z[rows, cols].astype(np.float64)

    x_mean = float(np.mean(xs))
    y_mean = float(np.mean(ys))
    z_mean = float(np.mean(zs))

    dx = xs - x_mean
    dy = ys - y_mean
    dz = zs - z_mean

    s_xx = float(np.sum(dx * dx))
    s_yy = float(np.sum(dy * dy))
    s_xy = float(np.sum(dx * dy))
    s_xz = float(np.sum(dx * dz))
    s_yz = float(np.sum(dy * dz))

    det = s_xx * s_yy - s_xy * s_xy
    if abs(det) < 1e-12:
        return {
            "slope_pct": 0.0,
            "aspect_deg": None,
            "r_squared": 0.0,
            "z_mean_m": round(float(z_mean), 2),
            "b_dz_dx": 0.0,
            "c_dz_dy": 0.0,
            "description": "Plano indeterminado",
        }

    b = (s_yy * s_xz - s_xy * s_yz) / det
    c = (s_xx * s_yz - s_xy * s_xz) / det

    s_mag = float(np.hypot(b, c))
    slope_pct = 100.0 * s_mag

    # Rumbo de máximo descenso: vector (-b, -c)
    aspect_deg = float((np.degrees(np.arctan2(-b, -c)) + 360.0) % 360.0)

    z_pred = z_mean + b * dx + c * dy
    ss_tot = float(np.sum((zs - z_mean) ** 2))
    ss_res = float(np.sum((zs - z_pred) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-9 else 1.0
    r2 = float(np.clip(r2, 0.0, 1.0))

    direcciones = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
    idx = int((aspect_deg + 22.5) // 45) % 8
    rumbo_str = direcciones[idx]

    desc = f"{slope_pct:.1f} % hacia el {rumbo_str} (plano ajustado R² = {r2:.2f})".replace(".", ",")

    return {
        "slope_pct": round(float(slope_pct), 3),
        "aspect_deg": round(float(aspect_deg), 1),
        "r_squared": round(float(r2), 3),
        "z_mean_m": round(float(z_mean), 2),
        "b_dz_dx": float(b),
        "c_dz_dy": float(c),
        "description": desc,
    }
