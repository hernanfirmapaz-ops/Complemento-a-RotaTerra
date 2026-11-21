"""Dirección de flujo D8, acumulación D8 y MFD, red de drenaje potencial y subcuencas (SDD §6.3).

Métodos implementados:
1. **D8 / SFD (Single Flow Direction)**: asigna el flujo de cada celda a la única vecina de descenso
   más pronunciado (`max((z - z_i) / dist_i)`). Útil para cauces y rutas concentradas.
2. **MFD (Multiple Flow Direction, Quinn et al. 1991)**: reparte el área de cada celda entre todas las
   celdas vecinas descendentes proporcionalmente a `(tan(beta_i) ** p) * L_i`. Más apropiado para
   representar escurrimiento superficial difuso sobre laderas agrícolas.

Códigos de dirección D8 (estándar ESRI / GIS):
    32 (NW)   64 (N)   128 (NE)
    16 (W)     0 (sink)  1 (E)
     8 (SW)    4 (S)     2 (SE)
"""

from __future__ import annotations

import math
from collections import deque
from typing import Literal

import numpy as np

from geoprocessing.crs import WGS84, to_crs
from geoprocessing.dem.terrain import Dem

try:
    from numba import njit

    _HAS_NUMBA = True
except ImportError:
    _HAS_NUMBA = False

    def njit(*args, **kwargs):
        def decorator(func):
            return func

        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator


# (dr, dc, código D8, azimut grados desde el norte, factor distancia centro a centro, factor ancho contorno L_i)
D8_TABLE: tuple[tuple[int, int, int, float, float, float], ...] = (
    (0, 1, 1, 90.0, 1.0, 0.5),             # E
    (1, 1, 2, 135.0, math.sqrt(2.0), 0.354),   # SE
    (1, 0, 4, 180.0, 1.0, 0.5),            # S
    (1, -1, 8, 225.0, math.sqrt(2.0), 0.354),  # SW
    (0, -1, 16, 270.0, 1.0, 0.5),          # W
    (-1, -1, 32, 315.0, math.sqrt(2.0), 0.354),  # NW
    (-1, 0, 64, 0.0, 1.0, 0.5),            # N
    (-1, 1, 128, 45.0, math.sqrt(2.0), 0.354),  # NE
)

_DR_ARR = np.array([t[0] for t in D8_TABLE], dtype=np.int64)
_DC_ARR = np.array([t[1] for t in D8_TABLE], dtype=np.int64)
_DIST_ARR = np.array([t[4] for t in D8_TABLE], dtype=np.float64)
_CONTOUR_ARR = np.array([t[5] for t in D8_TABLE], dtype=np.float64)


@njit
def _mfd_accumulation_numba(
    z_cond: np.ndarray,
    mfd_cells: np.ndarray,
    rs_ord: np.ndarray,
    cs_ord: np.ndarray,
    dr_arr: np.ndarray,
    dc_arr: np.ndarray,
    dist_arr: np.ndarray,
    contour_arr: np.ndarray,
    pixel_size_m: float,
    exponent_p: float,
) -> float:
    alto, ancho = z_cond.shape
    n_cells = len(rs_ord)
    outlet_cells_sum = 0.0
    for i in range(n_cells):
        r = rs_ord[i]
        c = cs_ord[i]
        z0 = float(z_cond[r, c])
        acc0 = mfd_cells[r, c]
        w_sum = 0.0
        n_nr = 0
        weights = np.zeros(8, dtype=np.float64)
        nrs = np.zeros(8, dtype=np.int64)
        ncs = np.zeros(8, dtype=np.int64)
        for k in range(8):
            nr = r + dr_arr[k]
            nc = c + dc_arr[k]
            if 0 <= nr < alto and 0 <= nc < ancho:
                zn = float(z_cond[nr, nc])
                if np.isfinite(zn) and zn < z0:
                    tan_beta = (z0 - zn) / (dist_arr[k] * pixel_size_m)
                    w = (tan_beta ** exponent_p) * contour_arr[k]
                    nrs[n_nr] = nr
                    ncs[n_nr] = nc
                    weights[n_nr] = w
                    w_sum += w
                    n_nr += 1
        if w_sum > 0.0:
            inv = acc0 / w_sum
            for k in range(n_nr):
                mfd_cells[nrs[k], ncs[k]] += weights[k] * inv
        else:
            outlet_cells_sum += acc0
    return outlet_cells_sum

CODE_TO_DELTA: dict[int, tuple[int, int]] = {code: (dr, dc) for dr, dc, code, _, _, _ in D8_TABLE}
CODE_TO_AZIMUTH: dict[int, float] = {code: az for _, _, code, az, _, _ in D8_TABLE}
CODE_TO_LABEL: dict[int, str] = {
    0: "Sumidero / salida",
    1: "E", 2: "SE", 4: "S", 8: "SO", 16: "O", 32: "NO", 64: "N", 128: "NE",
}


def default_stream_threshold_ha(field_area_ha: float, pixel_size_m: float) -> float:
    """Umbral inicial sugerido de área contribuyente (ha) según área del lote y resolución (SDD §6.3).

    Nunca se usa un umbral universal fijo: escala entre al menos 12 celdas del DEM y ~1.5 % de la
    superficie del lote.
    """
    min_cells_ha = (12.0 * (pixel_size_m ** 2)) / 10_000.0
    by_area_ha = max(0.25, 0.015 * float(field_area_ha))
    return round(max(min_cells_ha, by_area_ha), 3)


def d8_direction_and_accumulation(
    z_cond: np.ndarray,
    pixel_size_m: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Calcula dirección D8, azimut D8 (grados), celdas acumuladas D8 y área contribuyente D8 (m²).

    Devuelve:
        d8_code: uint8 (0 en sumidero/borde o NaN; 1,2,4,8,16,32,64,128 en celdas con salida)
        d8_azimuth_deg: float32 (NaN donde d8_code == 0)
        d8_cells: int32 (1 en cabeceras, >=1 en toda celda válida, 0 en NaN)
        d8_area_m2: float32 (área contribuyente en m², NaN donde z_cond es NaN)
    """
    alto, ancho = z_cond.shape
    valid = np.isfinite(z_cond)
    d8_code = np.zeros((alto, ancho), dtype="uint8")
    d8_azimuth = np.full((alto, ancho), np.nan, dtype="float32")
    best_slope = np.zeros((alto, ancho), dtype="float64")
    receiver_r = np.full((alto, ancho), -1, dtype="int32")
    receiver_c = np.full((alto, ancho), -1, dtype="int32")

    for dr, dc, code, az, dist_f, _ in D8_TABLE:
        dist = dist_f * pixel_size_m
        r_src = slice(max(0, -dr), alto - max(0, dr))
        c_src = slice(max(0, -dc), ancho - max(0, dc))
        r_dst = slice(max(0, dr), alto - max(0, -dr))
        c_dst = slice(max(0, dc), ancho - max(0, -dc))

        z_s = z_cond[r_src, c_src]
        z_d = z_cond[r_dst, c_dst]
        ok = np.isfinite(z_s) & np.isfinite(z_d)
        slope = np.where(ok, (z_s - z_d) / dist, -1.0)

        cur_best = best_slope[r_src, c_src]
        better = slope > cur_best
        best_slope[r_src, c_src] = np.where(better, slope, cur_best)
        d8_code[r_src, c_src] = np.where(better, code, d8_code[r_src, c_src])
        d8_azimuth[r_src, c_src] = np.where(better, az, d8_azimuth[r_src, c_src])

        # Guardar coordenadas de la celda receptora
        rr_grid, cc_grid = np.meshgrid(
            np.arange(r_dst.start, r_dst.stop, dtype="int32"),
            np.arange(c_dst.start, c_dst.stop, dtype="int32"),
            indexing="ij",
        )
        receiver_r[r_src, c_src] = np.where(better, rr_grid, receiver_r[r_src, c_src])
        receiver_c[r_src, c_src] = np.where(better, cc_grid, receiver_c[r_src, c_src])

    # Acumulación por orden topológico (Kahn / grado de entrada)
    indegree = np.zeros((alto, ancho), dtype="int32")
    rs_valid, cs_valid = np.nonzero(valid)
    for r, c in zip(rs_valid.tolist(), cs_valid.tolist()):
        nr, nc = int(receiver_r[r, c]), int(receiver_c[r, c])
        if nr >= 0:
            indegree[nr, nc] += 1

    d8_cells = np.where(valid, 1, 0).astype("int32")
    q = deque(
        (int(r), int(c))
        for r, c in zip(rs_valid.tolist(), cs_valid.tolist())
        if indegree[r, c] == 0
    )
    while q:
        r, c = q.popleft()
        nr, nc = int(receiver_r[r, c]), int(receiver_c[r, c])
        if nr >= 0:
            d8_cells[nr, nc] += d8_cells[r, c]
            indegree[nr, nc] -= 1
            if indegree[nr, nc] == 0:
                q.append((nr, nc))

    cell_area = float(pixel_size_m * pixel_size_m)
    d8_area_m2 = np.where(valid, d8_cells * cell_area, np.nan).astype("float32")
    return d8_code, d8_azimuth, d8_cells, d8_area_m2


def mfd_accumulation(
    z_cond: np.ndarray,
    pixel_size_m: float,
    exponent_p: float = 1.1,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Acumulación de flujo MFD (Quinn et al. 1991) por orden decreciente de altura acondicionada.

    Cada celda válida aporta inicialmente 1 celda (`pixel_size_m²`) y reparte su caudal acumulado
    entre todas las vecinas estrictamente más bajas según `(tan(beta_i) ** p) * L_i`.

    Devuelve:
        mfd_cells: float32 (celdas equivalentes acumuladas, NaN donde z_cond es NaN)
        mfd_area_m2: float32 (área contribuyente MFD en m²)
        mass_balance: diccionario con verificación de conservación de área (`relative_error`)
    """
    alto, ancho = z_cond.shape
    valid = np.isfinite(z_cond)
    mfd_cells = np.where(valid, 1.0, np.nan).astype("float64")

    rs, cs = np.nonzero(valid)
    vals = z_cond[rs, cs]
    order = np.argsort(-vals, kind="mergesort")  # de mayor a menor cota
    p = float(exponent_p)

    rs_ord = rs[order]
    cs_ord = cs[order]

    if _HAS_NUMBA:
        outlet_cells_sum = _mfd_accumulation_numba(
            np.ascontiguousarray(z_cond, dtype=np.float64),
            mfd_cells,
            np.ascontiguousarray(rs_ord, dtype=np.int64),
            np.ascontiguousarray(cs_ord, dtype=np.int64),
            _DR_ARR,
            _DC_ARR,
            _DIST_ARR,
            _CONTOUR_ARR,
            float(pixel_size_m),
            p,
        )
    else:
        rs_ord_list = rs_ord.tolist()
        cs_ord_list = cs_ord.tolist()
        outlet_cells_sum = 0.0
        for r, c in zip(rs_ord_list, cs_ord_list):
            z0 = float(z_cond[r, c])
            acc0 = float(mfd_cells[r, c])
            weights: list[tuple[int, int, float]] = []
            w_sum = 0.0
            for dr, dc, _, _, dist_f, contour_f in D8_TABLE:
                nr, nc = r + dr, c + dc
                if 0 <= nr < alto and 0 <= nc < ancho:
                    zn = float(z_cond[nr, nc])
                    if math.isfinite(zn) and zn < z0:
                        tan_beta = (z0 - zn) / (dist_f * pixel_size_m)
                        w = (tan_beta ** p) * contour_f
                        weights.append((nr, nc, w))
                        w_sum += w
            if w_sum > 0.0:
                inv = acc0 / w_sum
                for nr, nc, w in weights:
                    mfd_cells[nr, nc] += w * inv
            else:
                # Celda sumidero o salida del dominio: retiene/exporta todo el flujo que llegó hasta ella
                outlet_cells_sum += acc0

    total_valid_cells = float(len(rs_ord))
    rel_err = abs(outlet_cells_sum - total_valid_cells) / max(1.0, total_valid_cells)
    cell_area = float(pixel_size_m * pixel_size_m)
    mfd_area_m2 = (mfd_cells * cell_area).astype("float32")
    balance = {
        "total_valid_cells": int(total_valid_cells),
        "total_input_area_ha": round(total_valid_cells * cell_area / 10_000.0, 4),
        "total_outlet_area_ha": round(outlet_cells_sum * cell_area / 10_000.0, 4),
        "relative_error": float(rel_err),
    }
    return mfd_cells.astype("float32"), mfd_area_m2, balance


def extract_drainage_network_and_basins(
    dem: Dem,
    mascara_lote: np.ndarray,
    d8_code: np.ndarray,
    d8_area_m2: np.ndarray,
    mfd_area_m2: np.ndarray,
    threshold_ha: float,
    routing_basis: Literal["MFD", "D8"] = "MFD",
    max_outlets: int = 8,
) -> tuple[dict, np.ndarray, list[dict]]:
    """Extrae la red de drenaje potencial (GeoJSON), los puntos de salida del lote y sus subcuencas.

    1. **Red de drenaje potencial**: celdas donde el área contribuyente (`MFD` o `D8`) supera
       `threshold_ha`. Se trazan siguiendo los enlaces D8 entre celdas de red para formar tramos
       continuos (`LineString` en EPSG:4326).
    2. **Puntos de salida del lote (outlets) y subcuencas**: celdas dentro del lote cuyo receptor D8
       cae fuera del lote (o son sumideros terminales internos) con mayor área contribuyente.
       Para los `max_outlets` principales se etiquetan todas las celdas aguas arriba (`subbasin_id`).
    """
    alto, ancho = d8_code.shape
    threshold_m2 = max(float(threshold_ha) * 10_000.0, float(dem.pixel * dem.pixel))
    area_grid = mfd_area_m2 if routing_basis == "MFD" else d8_area_m2
    is_stream = np.isfinite(area_grid) & (area_grid >= threshold_m2)

    # Mapa de receptor D8 por celda
    rec_r = np.full((alto, ancho), -1, dtype="int32")
    rec_c = np.full((alto, ancho), -1, dtype="int32")
    stream_indeg = np.zeros((alto, ancho), dtype="int32")

    rs_all, cs_all = np.nonzero(d8_code > 0)
    for r, c in zip(rs_all.tolist(), cs_all.tolist()):
        dr, dc = CODE_TO_DELTA[int(d8_code[r, c])]
        nr, nc = r + dr, c + dc
        if 0 <= nr < alto and 0 <= nc < ancho:
            rec_r[r, c] = nr
            rec_c[r, c] = nc
            if is_stream[r, c] and is_stream[nr, nc]:
                stream_indeg[nr, nc] += 1

    # Trazar tramos desde cabeceras de red (indeg == 0) o confluencias (indeg > 1)
    starts = [
        (int(r), int(c))
        for r, c in zip(*np.nonzero(is_stream & ((stream_indeg == 0) | (stream_indeg > 1))))
    ]

    tramos_cells: list[tuple[list[tuple[int, int]], float, bool]] = []
    for sr, sc in starts:
        chain = [(sr, sc)]
        max_a = float(area_grid[sr, sc])
        touches_field = bool(mascara_lote[sr, sc])
        cr, cc = sr, sc
        while True:
            nr, nc = int(rec_r[cr, cc]), int(rec_c[cr, cc])
            if nr < 0 or not is_stream[nr, nc]:
                break
            chain.append((nr, nc))
            if float(area_grid[nr, nc]) > max_a:
                max_a = float(area_grid[nr, nc])
            if mascara_lote[nr, nc]:
                touches_field = True
            if stream_indeg[nr, nc] > 1:
                break
            cr, cc = nr, nc
        if len(chain) >= 2:
            tramos_cells.append((chain, max_a, touches_field))

    features = []
    if tramos_cells:
        flat_r = [pt[0] for chain, _, _ in tramos_cells for pt in chain]
        flat_c = [pt[1] for chain, _, _ in tramos_cells for pt in chain]
        fx, fy = dem.xy_of_cell(flat_r, flat_c)
        flon, flat = to_crs(fx, fy, dem.crs, WGS84)
        pos = 0
        for idx, (chain, max_a, touches_field) in enumerate(tramos_cells, start=1):
            n = len(chain)
            xs_seg = fx[pos:pos + n]
            ys_seg = fy[pos:pos + n]
            length_m = float(np.hypot(np.diff(xs_seg), np.diff(ys_seg)).sum())
            coords = [
                [round(float(flon[pos + i]), 7), round(float(flat[pos + i]), 7)]
                for i in range(n)
            ]
            pos += n
            features.append({
                "type": "Feature",
                "properties": {
                    "id": idx,
                    "max_contributing_ha": round(max_a / 10_000.0, 3),
                    "length_m": round(length_m, 1),
                    "intersects_field": touches_field,
                    "basis": routing_basis,
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            })

    network_geojson = {
        "type": "FeatureCollection",
        "threshold_ha": round(float(threshold_ha), 3),
        "basis": routing_basis,
        "features": features,
    }

    # Identificar puntos de salida del lote (celdas dentro del lote que drenan fuera del lote o son sumidero)
    candidate_outlets: list[tuple[float, int, int, str]] = []
    rs_fld, cs_fld = np.nonzero(mascara_lote & np.isfinite(area_grid))
    for r, c in zip(rs_fld.tolist(), cs_fld.tolist()):
        nr, nc = int(rec_r[r, c]), int(rec_c[r, c])
        if nr < 0:
            candidate_outlets.append((float(area_grid[r, c]), r, c, "sumidero_interno"))
        elif not mascara_lote[nr, nc]:
            candidate_outlets.append((float(area_grid[r, c]), r, c, "salida_perimetro"))

    candidate_outlets.sort(key=lambda item: item[0], reverse=True)
    # Filtrar salidas significativas (>= 2 celdas o top max_outlets)
    min_outlet_m2 = 2.0 * float(dem.pixel * dem.pixel)
    top_outlets = [it for it in candidate_outlets if it[0] >= min_outlet_m2][:max_outlets]
    if not top_outlets and candidate_outlets:
        top_outlets = candidate_outlets[:1]

    # Construir lista invertida de donantes D8 para etiquetar la subcuenca aguas arriba de cada salida
    donors: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for r, c in zip(rs_all.tolist(), cs_all.tolist()):
        nr, nc = int(rec_r[r, c]), int(rec_c[r, c])
        if nr >= 0:
            donors.setdefault((nr, nc), []).append((r, c))

    subbasin_grid = np.zeros((alto, ancho), dtype="int32")
    outlets_info: list[dict] = []

    if top_outlets:
        ox, oy = dem.xy_of_cell([it[1] for it in top_outlets], [it[2] for it in top_outlets])
        olon, olat = to_crs(ox, oy, dem.crs, WGS84)
        cell_area = float(dem.pixel * dem.pixel)

        for basin_id, (area_val, r_out, c_out, kind) in enumerate(top_outlets, start=1):
            q = deque([(r_out, c_out)])
            subbasin_grid[r_out, c_out] = basin_id
            basin_cells = 0
            basin_in_field_cells = 0
            while q:
                cr, cc = q.popleft()
                basin_cells += 1
                if mascara_lote[cr, cc]:
                    basin_in_field_cells += 1
                for dr_cell, dc_cell in donors.get((cr, cc), ()):
                    if subbasin_grid[dr_cell, dc_cell] == 0:
                        subbasin_grid[dr_cell, dc_cell] = basin_id
                        q.append((dr_cell, dc_cell))

            total_ha = (basin_cells * cell_area) / 10_000.0
            in_field_ha = (basin_in_field_cells * cell_area) / 10_000.0
            ext_ha = max(0.0, total_ha - in_field_ha)
            code = int(d8_code[r_out, c_out])
            outlets_info.append({
                "id": basin_id,
                "type": kind,
                "lon": round(float(olon[basin_id - 1]), 7),
                "lat": round(float(olat[basin_id - 1]), 7),
                "elevation_m": round(float(dem.z[r_out, c_out]), 2),
                "d8_direction": CODE_TO_LABEL.get(code, "s/d"),
                "contributing_area_mfd_ha": round(float(mfd_area_m2[r_out, c_out]) / 10_000.0, 3),
                "contributing_area_d8_ha": round(float(d8_area_m2[r_out, c_out]) / 10_000.0, 3),
                "subbasin_total_ha": round(total_ha, 3),
                "subbasin_in_field_ha": round(in_field_ha, 3),
                "subbasin_external_inflow_ha": round(ext_ha, 3),
            })

    return network_geojson, subbasin_grid, outlets_info
