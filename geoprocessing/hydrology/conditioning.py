"""Acondicionamiento hidrológico del DEM e identificación de depresiones (SDD §6.2).

Regla obligatoria del SDD (§6.2):
    "No rellenar todas las depresiones de forma automática y ciega. En zonas agrícolas los bajos
    pueden ser retenciones reales y relevantes para el manejo."

Modos admitidos:
- `preserve`: conserva todas las depresiones reales (solo resuelve planos con micro-gradiente ε).
- `fill_small`: rellena únicamente depresiones pequeñas probablemente espurias (profundidad máxima <=
  `max_fill_depth_m` y área <= `max_fill_area_m2`), conservando los bajos agrícolas mayores.
- `fill_all`: rellena todas las depresiones con Priority-Flood + ε para forzar continuidad de drenaje
  hacia los bordes del dominio.

Toda edición se guarda como una versión derivada sin modificar el DEM original.
"""

from __future__ import annotations

import heapq
from collections import deque
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np

from geoprocessing.crs import WGS84, to_crs
from geoprocessing.dem.terrain import Dem

ConditioningMode = Literal["preserve", "fill_small", "fill_all"]

_NEIGHBORS_8 = (
    (-1, 0), (-1, 1), (0, 1), (1, 1),
    (1, 0), (1, -1), (0, -1), (-1, -1),
)


@dataclass
class DepressionInfo:
    id: int
    cells: int
    area_m2: float
    area_ha: float
    max_depth_m: float
    mean_depth_m: float
    volume_m3: float
    pour_point_elevation_m: float
    min_elevation_m: float
    centroid_lon: float
    centroid_lat: float
    in_field: bool
    is_spurious_candidate: bool
    filled_in_run: bool

    def to_dict(self) -> dict:
        return asdict(self)


def priority_flood_fill(z: np.ndarray, eps: float = 1e-4) -> np.ndarray:
    """Priority-Flood + ε (Barnes, Lehman & Mulla 2014 / Wang & Liu 2006).

    Devuelve la superficie mínima hidrológicamente drenante hacia los bordes o celdas NaN,
    sin alterar las celdas NaN.
    """
    alto, ancho = z.shape
    out = z.astype("float64").copy()
    valid = np.isfinite(out)
    visited = ~valid
    pq: list[tuple[float, int, int]] = []
    plain_q: deque[tuple[float, int, int]] = deque()

    # Semillas: celdas válidas en el borde de la grilla o adyacentes a un NaN
    for r in range(alto):
        for c in range(ancho):
            if not valid[r, c]:
                continue
            is_seed = (r == 0 or r == alto - 1 or c == 0 or c == ancho - 1)
            if not is_seed:
                for dr, dc in _NEIGHBORS_8:
                    if not valid[r + dr, c + dc]:
                        is_seed = True
                        break
            if is_seed:
                visited[r, c] = True
                heapq.heappush(pq, (float(out[r, c]), r, c))

    while pq or plain_q:
        if plain_q:
            zv, r, c = plain_q.popleft()
        else:
            zv, r, c = heapq.heappop(pq)
        for dr, dc in _NEIGHBORS_8:
            nr, nc = r + dr, c + dc
            if 0 <= nr < alto and 0 <= nc < ancho and not visited[nr, nc]:
                visited[nr, nc] = True
                nz = float(out[nr, nc])
                if nz <= zv:
                    raised = zv + eps
                    out[nr, nc] = raised
                    plain_q.append((raised, nr, nc))
                else:
                    heapq.heappush(pq, (nz, nr, nc))

    return out.astype("float32")


def apply_burn_in(
    dem: Dem,
    z: np.ndarray,
    burn_lines_lonlat: list[list[list[float]]] | None,
    burn_depth_m: float = 0.5,
) -> np.ndarray:
    """Rebaja de forma controlada (`burn_depth_m`) las celdas por donde pasan líneas de drenaje conocidas."""
    if not burn_lines_lonlat or burn_depth_m <= 0:
        return z
    from rasterio.features import rasterize
    from shapely.geometry import LineString

    geoms = []
    for coords in burn_lines_lonlat:
        if len(coords) < 2:
            continue
        lons = [pt[0] for pt in coords]
        lats = [pt[1] for pt in coords]
        xs, ys = to_crs(lons, lats, WGS84, dem.crs)
        geoms.append(LineString(zip(xs, ys)).__geo_interface__)
    if not geoms:
        return z

    burned_mask = rasterize(
        geoms,
        out_shape=z.shape,
        transform=dem.transform,
        fill=0,
        default_value=1,
        all_touched=True,
        dtype="uint8",
    ).astype(bool)
    out = z.copy()
    valid_burn = burned_mask & np.isfinite(out)
    out[valid_burn] = out[valid_burn] - float(burn_depth_m)
    return out


def condition_dem(
    dem: Dem,
    mascara_lote: np.ndarray,
    mode: ConditioningMode = "fill_small",
    max_fill_depth_m: float = 0.35,
    max_fill_area_m2: float = 4500.0,
    burn_lines_lonlat: list[list[list[float]]] | None = None,
    burn_depth_m: float = 0.5,
    min_depression_depth_m: float = 0.05,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[DepressionInfo]]:
    """Acondiciona el DEM según la estrategia elegida e identifica todas las depresiones cerradas.

    Devuelve:
        z_conditioned: grilla float32 acondicionada según `mode`
        sink_depth_m: profundidad original de depresión por celda (m, >= 0)
        depression_id_grid: int32 (0 fuera de depresión, 1..N en cada depresión conectada)
        depressions: catálogo de depresiones ordenadas de mayor a menor volumen
    """
    z_work = apply_burn_in(dem, dem.z, burn_lines_lonlat, burn_depth_m)
    z_full_filled = priority_flood_fill(z_work, eps=1e-4)
    diff = np.where(np.isfinite(z_work), np.maximum(0.0, z_full_filled - z_work), 0.0).astype("float32")

    # Etiquetar componentes conexos (8-vecinos) donde diff > min_depression_depth_m
    is_sink = diff > float(min_depression_depth_m)
    alto, ancho = z_work.shape
    raw_labels = np.zeros((alto, ancho), dtype="int32")
    comps: list[list[tuple[int, int]]] = []
    cur_label = 0

    for r in range(alto):
        for c in range(ancho):
            if is_sink[r, c] and raw_labels[r, c] == 0:
                cur_label += 1
                cells: list[tuple[int, int]] = []
                q = deque([(r, c)])
                raw_labels[r, c] = cur_label
                while q:
                    cr, cc = q.popleft()
                    cells.append((cr, cc))
                    for dr, dc in _NEIGHBORS_8:
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < alto and 0 <= nc < ancho and is_sink[nr, nc] and raw_labels[nr, nc] == 0:
                            raw_labels[nr, nc] = cur_label
                            q.append((nr, nc))
                comps.append(cells)

    cell_area = float(dem.pixel * dem.pixel)
    raw_infos: list[tuple[float, list[tuple[int, int]], dict]] = []
    for cells in comps:
        rs = np.array([p[0] for p in cells], dtype=int)
        cs = np.array([p[1] for p in cells], dtype=int)
        depths = diff[rs, cs]
        z_orig_vals = z_work[rs, cs]
        z_fill_vals = z_full_filled[rs, cs]
        n_cells = len(cells)
        area_m2 = n_cells * cell_area
        max_d = float(depths.max())
        mean_d = float(depths.mean())
        vol_m3 = float(depths.sum() * cell_area)
        in_fld = bool(mascara_lote[rs, cs].any())
        spurious = (max_d <= max_fill_depth_m) and (area_m2 <= max_fill_area_m2)
        filled = (mode == "fill_all") or (mode == "fill_small" and spurious)
        x_c, y_c = dem.xy_of_cell(float(rs.mean()), float(cs.mean()))
        raw_infos.append((
            vol_m3,
            cells,
            {
                "cells": n_cells,
                "area_m2": round(area_m2, 1),
                "area_ha": round(area_m2 / 10_000.0, 4),
                "max_depth_m": round(max_d, 3),
                "mean_depth_m": round(mean_d, 3),
                "volume_m3": round(vol_m3, 1),
                "pour_point_elevation_m": round(float(z_fill_vals.max()), 2),
                "min_elevation_m": round(float(z_orig_vals.min()), 2),
                "x_utm": float(x_c),
                "y_utm": float(y_c),
                "in_field": in_fld,
                "is_spurious_candidate": spurious,
                "filled_in_run": filled,
            },
        ))

    # Ordenar de mayor a menor volumen y renumerar 1..N
    raw_infos.sort(key=lambda item: item[0], reverse=True)
    depression_id_grid = np.zeros((alto, ancho), dtype="int32")
    z_conditioned = z_work.copy()

    if mode == "fill_all":
        z_conditioned = z_full_filled.copy()

    xs = [info["x_utm"] for _, _, info in raw_infos]
    ys = [info["y_utm"] for _, _, info in raw_infos]
    lons, lats = to_crs(xs, ys, dem.crs, WGS84) if xs else (np.array([]), np.array([]))

    depressions: list[DepressionInfo] = []
    for idx, (_, cells, info) in enumerate(raw_infos, start=1):
        rs = np.array([p[0] for p in cells], dtype=int)
        cs = np.array([p[1] for p in cells], dtype=int)
        depression_id_grid[rs, cs] = idx
        if mode == "fill_small" and info["filled_in_run"]:
            z_conditioned[rs, cs] = z_full_filled[rs, cs]
        depressions.append(
            DepressionInfo(
                id=idx,
                cells=info["cells"],
                area_m2=info["area_m2"],
                area_ha=info["area_ha"],
                max_depth_m=info["max_depth_m"],
                mean_depth_m=info["mean_depth_m"],
                volume_m3=info["volume_m3"],
                pour_point_elevation_m=info["pour_point_elevation_m"],
                min_elevation_m=info["min_elevation_m"],
                centroid_lon=round(float(lons[idx - 1]), 7),
                centroid_lat=round(float(lats[idx - 1]), 7),
                in_field=info["in_field"],
                is_spurious_candidate=info["is_spurious_candidate"],
                filled_in_run=info["filled_in_run"],
            )
        )

    return z_conditioned.astype("float32"), diff, depression_id_grid, depressions
