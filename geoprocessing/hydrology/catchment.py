"""Delimitación de cuenca de aporte completa y margen adaptativo (Spec 032 §2 / Issue #114).

Calcula la cuenca vertiente completa aguas arriba (upslope contributing area)
que desagua hacia el lote a partir del operador de flujo D8.
Verifica si la divisoria topográfica toca el borde exterior del ráster y gestiona
la expansión adaptativa (3 km -> 5 km -> 10 km) y la advertencia de cuenca truncada.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from geoprocessing.hydrology.flow import D8_TABLE
from geoprocessing.supuestos import (
    SUPUESTO_CUENCA_DILATACION_CELDAS,
    SUPUESTO_CUENCA_DOWNSTREAM_BUFFER_M,
    SUPUESTO_CUENCA_MARGEN_EXPANSION_KM,
    SUPUESTO_CUENCA_MARGEN_INICIAL_KM,
    SUPUESTO_CUENCA_MARGEN_MAXIMO_KM,
)

D8_OFFSETS = {code: (dr, dc) for dr, dc, code, *_ in D8_TABLE}


@dataclass
class CatchmentResult:
    mask: np.ndarray
    touches_border: bool
    is_truncated: bool
    margin_km: float
    total_area_ha: float
    external_area_ha: float
    in_field_area_ha: float
    warning: str | None


def trace_upslope_catchment(
    d8_code: np.ndarray,
    mascara_lote: np.ndarray,
    pixel_size_m: float = 30.0,
    current_margin_km: float = 3.0,
    max_margin_km: float | None = None,
) -> CatchmentResult:
    """Traza la cuenca vertiente completa que drena hacia el lote y detecta si toca el borde.

    Parámetros:
    - d8_code: matriz con los códigos de dirección de flujo D8 (1, 2, 4, 8, 16, 32, 64, 128).
    - mascara_lote: máscara booleana con las celdas pertenecientes al lote.
    - pixel_size_m: tamaño de celda en metros.
    - current_margin_km: margen de recorte aplicado en kilómetros.
    - max_margin_km: margen máximo admisible antes de declarar truncamiento (por defecto SUPUESTO_CUENCA_MARGEN_MAXIMO_KM).
    """
    alto, ancho = d8_code.shape
    if max_margin_km is None:
        max_margin_km = float(SUPUESTO_CUENCA_MARGEN_MAXIMO_KM.valor)

    # 1. Construir grafo invertido de donantes D8
    donors: dict[tuple[int, int], list[tuple[int, int]]] = {}
    valid_d8 = np.isin(d8_code, list(D8_OFFSETS.keys()))
    rs, cs = np.nonzero(valid_d8)

    for r, c in zip(rs.tolist(), cs.tolist()):
        code = int(d8_code[r, c])
        dr, dc = D8_OFFSETS[code]
        nr, nc = r + dr, c + dc
        if 0 <= nr < alto and 0 <= nc < ancho:
            donors.setdefault((nr, nc), []).append((r, c))

    # 2. Cola BFS desde todas las celdas del lote
    catchment_mask = np.zeros((alto, ancho), dtype=bool)
    q: deque[tuple[int, int]] = deque()

    lot_rs, lot_cs = np.nonzero(mascara_lote)
    for lr, lc in zip(lot_rs.tolist(), lot_cs.tolist()):
        catchment_mask[lr, lc] = True
        q.append((lr, lc))

    while q:
        cr, cc = q.popleft()
        for dr_cell, dc_cell in donors.get((cr, cc), ()):
            if not catchment_mask[dr_cell, dc_cell]:
                catchment_mask[dr_cell, dc_cell] = True
                q.append((dr_cell, dc_cell))

    # 3. Control de frontera: verificar si la cuenca vertiente toca los límites del ráster
    touches_top = bool(np.any(catchment_mask[0, :]))
    touches_bottom = bool(np.any(catchment_mask[alto - 1, :]))
    touches_left = bool(np.any(catchment_mask[:, 0]))
    touches_right = bool(np.any(catchment_mask[:, ancho - 1]))

    touches_border = touches_top or touches_bottom or touches_left or touches_right

    # Es truncada si toca el borde y ya se alcanzó el margen máximo (o si el ráster no puede expandirse más)
    is_truncated = touches_border and (current_margin_km >= (max_margin_km - 0.01))

    cell_area_ha = float(pixel_size_m * pixel_size_m) / 10_000.0
    total_cells = int(np.count_nonzero(catchment_mask))
    in_field_cells = int(np.count_nonzero(catchment_mask & mascara_lote))
    ext_cells = max(0, total_cells - in_field_cells)

    warning = (
        f"Cuenca de aporte externa truncada a {max_margin_km:.0f} km: "
        "el caudal y volumen calculados representan un piso mínimo."
        if is_truncated
        else None
    )

    return CatchmentResult(
        mask=catchment_mask,
        touches_border=touches_border,
        is_truncated=is_truncated,
        margin_km=round(current_margin_km, 1),
        total_area_ha=round(total_cells * cell_area_ha, 3),
        external_area_ha=round(ext_cells * cell_area_ha, 3),
        in_field_area_ha=round(in_field_cells * cell_area_ha, 3),
        warning=warning,
    )


def resolve_adaptive_margin_steps() -> list[float]:
    """Retorna la secuencia de márgenes en metros para la expansión adaptativa [3000, 5000, 10000]."""
    return [
        float(SUPUESTO_CUENCA_MARGEN_INICIAL_KM.valor) * 1000.0,
        float(SUPUESTO_CUENCA_MARGEN_EXPANSION_KM.valor) * 1000.0,
        float(SUPUESTO_CUENCA_MARGEN_MAXIMO_KM.valor) * 1000.0,
    ]


def build_active_catchment_mask(
    catchment_mask: np.ndarray,
    mascara_lote: np.ndarray,
    d8_code: np.ndarray,
    pixel_size_m: float = 30.0,
    downstream_buffer_m: float | None = None,
    dilation_cells: int | None = None,
) -> np.ndarray:
    """Construye la máscara booleana del dominio hidrológico activo:
    Cuenca de aporte aguas arriba + Lote + Franja aguas abajo + Dilatación lateral.
    Permite restringir el motor 2D y el cálculo hidrológico sin procesar celdas irrelevantes.
    """
    if downstream_buffer_m is None:
        downstream_buffer_m = float(SUPUESTO_CUENCA_DOWNSTREAM_BUFFER_M.valor)
    if dilation_cells is None:
        dilation_cells = int(SUPUESTO_CUENCA_DILATACION_CELDAS.valor)

    alto, ancho = d8_code.shape
    max_steps = max(1, int(round(downstream_buffer_m / max(1.0, pixel_size_m))))

    # 1. Rastro aguas abajo desde las celdas del lote
    downstream = np.zeros((alto, ancho), dtype=bool)
    current_cells = set(zip(*np.nonzero(mascara_lote)))

    for _ in range(max_steps):
        next_cells = set()
        for r, c in current_cells:
            code = int(d8_code[r, c])
            if code in D8_OFFSETS:
                dr, dc = D8_OFFSETS[code]
                nr, nc = r + dr, c + dc
                if 0 <= nr < alto and 0 <= nc < ancho and not mascara_lote[nr, nc] and not downstream[nr, nc]:
                    downstream[nr, nc] = True
                    next_cells.add((nr, nc))
        if not next_cells:
            break
        current_cells = next_cells

    # 2. Unión de cuenca de aporte + lote + franja aguas abajo
    active = catchment_mask | mascara_lote | downstream

    # 3. Dilatación morfológica para márgenes de ribera y transferencias laterales
    if dilation_cells > 0:
        for _ in range(dilation_cells):
            padded = np.pad(active, 1, mode="constant", constant_values=False)
            new_active = active.copy()
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    new_active |= padded[1 + dr : 1 + dr + alto, 1 + dc : 1 + dc + ancho]
            active = new_active

    return active
