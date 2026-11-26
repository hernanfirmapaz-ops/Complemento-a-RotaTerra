"""Cálculo de escalera de lluvia precalculada y detección de umbral crítico de anegamiento (Spec 031 / Issue #113).

Evalúa la respuesta hidrológica del lote en una grilla de milímetros (10 a 150 mm)
optimizando el cómputo sobre la topografía estática y el dominio activo (active_mask),
generando la curva 'Hectáreas anegadas vs. mm de lluvia' y detectando el umbral de desborde.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from geoprocessing.agronomy.erosion_usle import compute_usle_erosion_and_gullies
from geoprocessing.rainfall.nrcs_cn import (
    compute_nrcs_cn,
    distribute_event_runoff_mfd,
    lookup_cn_ii,
)
from geoprocessing.supuestos import (
    SUPUESTO_ESCALERA_LLUVIA_MAX_MM,
    SUPUESTO_ESCALERA_LLUVIA_MIN_MM,
    SUPUESTO_ESCALERA_LLUVIA_PASO_DEFAULT_MM,
    SUPUESTO_ESCALERA_LLUVIA_PASO_DEGRADADO_MM,
    SUPUESTO_ESCALERA_MAX_TIEMPO_COMPUTO_S,
    SUPUESTO_ESCALERA_MIN_SUPERFICIE_ANEGADA_HA,
    SUPUESTO_ESCALERA_RATIO_SENSIBILIDAD_CODO,
)

# Caché en memoria para respuesta sub-milisegundo en sliders interactivos
_LADDER_MEMORY_CACHE: dict[str, dict[str, Any]] = {}


@dataclass
class LadderStepResult:
    precipitation_mm: float
    ponded_area_ha: float
    ponded_area_pct: float
    outflow_volume_m3: float
    soil_loss_t_ha_yr: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_ladder_cache_key(
    field_id: str,
    soil_group: str,
    amc: str,
    cover_code: str,
    step_size_mm: int,
) -> str:
    """Genera la clave hash SHA256 unívoca para indexar la caché de la escalera."""
    raw = f"{field_id}:{soil_group.strip().upper()}:{amc.strip().lower()}:{cover_code.strip()}:{step_size_mm}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def clear_ladder_cache(field_id: str | None = None) -> None:
    """Invalida la caché en memoria de la escalera (para un lote específico o global)."""
    global _LADDER_MEMORY_CACHE
    if field_id is None:
        _LADDER_MEMORY_CACHE.clear()
    else:
        keys_to_del = [k for k in _LADDER_MEMORY_CACHE if k.startswith(field_id)]
        for k in keys_to_del:
            _LADDER_MEMORY_CACHE.pop(k, None)


def detect_critical_ponding_threshold(steps: list[LadderStepResult]) -> float | None:
    """Identifica el umbral crítico de saturación y anegamiento del lote (codo / knee point).

    Evalúa la tasa marginal de anegamiento d(ha)/dP. Cuando las micro-depresiones alcanzan
    su capacidad máxima de retención y comienzan a desbordar hacia vías de escurrimiento,
    la tasa de crecimiento de área anegada disminuye bruscamente.

    Criterio:
    1. Si hay menos de 3 peldaños o la superficie anegada máxima es inferior a
       SUPUESTO_ESCALERA_MIN_SUPERFICIE_ANEGADA_HA, se retorna None (sin anegamiento apreciable).
    2. Se localiza el peldaño de máxima tasa de llenado marginal (g_max = max(dHa/dP)).
    3. Se identifica el primer peldaño posterior a g_max donde el incremento marginal cae
       por debajo de SUPUESTO_ESCALERA_RATIO_SENSIBILIDAD_CODO * g_max (saturación de cubetas).
    4. Si no se verifica una desaceleración clara o la curva es estrictamente lineal,
       retorna None (sin codo evidente).
    """
    if len(steps) < 3:
        return None

    ha_max_lote = max(s.ponded_area_ha for s in steps)
    min_ha = float(SUPUESTO_ESCALERA_MIN_SUPERFICIE_ANEGADA_HA.valor)
    if ha_max_lote < min_ha:
        return None

    p_vals = [s.precipitation_mm for s in steps]
    ha_vals = [s.ponded_area_ha for s in steps]

    # Pendientes marginales dHa / dP
    slopes: list[float] = []
    for i in range(len(steps) - 1):
        dp = p_vals[i + 1] - p_vals[i]
        dha = ha_vals[i + 1] - ha_vals[i]
        slopes.append(dha / dp if dp > 0 else 0.0)

    max_slope = max(slopes)
    if max_slope <= 0.0:
        return None

    max_slope_idx = slopes.index(max_slope)
    ratio_sens = float(SUPUESTO_ESCALERA_RATIO_SENSIBILIDAD_CODO.valor)
    threshold_slope = ratio_sens * max_slope

    # Buscar el punto donde la pendiente decae tras el máximo (saturación de bajos)
    for i in range(max_slope_idx, len(slopes)):
        if slopes[i] <= threshold_slope:
            return float(round(p_vals[i + 1], 1))

    return None


def compute_rainfall_ladder(
    field_id: str,
    mascara_lote: np.ndarray,
    mfd_area_m2: np.ndarray,
    slope_pct: np.ndarray,
    spi: np.ndarray,
    pixel_size_m: float,
    depression_volume_in_field_m3: float,
    depression_area_in_field_ha: float,
    external_inflow_ha: float,
    soil_group: str = "B",
    cover_code: str = "soja_maiz_sd_buena",
    amc: str = "medium",
    sand_pct: float | None = None,
    silt_pct: float | None = None,
    clay_pct: float | None = None,
    k_factor: float | None = None,
    active_mask: np.ndarray | None = None,
    step_size_override_mm: int | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Calcula la escalera de 10 a 150 mm y la curva de anegamiento para el lote.

    Aplica el modelo hidrológico optimizado sobre la geometría activa del lote y cuenca,
    garantizando monotonicidad física y tiempo de respuesta sub-segundo con caché indexada.
    """
    t_start = time.perf_counter()

    p_min = int(SUPUESTO_ESCALERA_LLUVIA_MIN_MM.valor)
    p_max = int(SUPUESTO_ESCALERA_LLUVIA_MAX_MM.valor)
    step_default = int(SUPUESTO_ESCALERA_LLUVIA_PASO_DEFAULT_MM.valor)
    step_degraded = int(SUPUESTO_ESCALERA_LLUVIA_PASO_DEGRADADO_MM.valor)
    max_budget_s = float(SUPUESTO_ESCALERA_MAX_TIEMPO_COMPUTO_S.valor)

    chosen_step = step_size_override_mm or step_default
    cache_key = f"{field_id}:{compute_ladder_cache_key(field_id, soil_group, amc, cover_code, chosen_step)}"

    if use_cache and cache_key in _LADDER_MEMORY_CACHE:
        cached_res = dict(_LADDER_MEMORY_CACHE[cache_key])
        cached_res["benchmark_timing_ms"] = round((time.perf_counter() - t_start) * 1000.0, 2)
        cached_res["from_cache"] = True
        return cached_res

    # Determinar CN base para la combinación suelo/cobertura
    cn_base, _ = lookup_cn_ii(cover_code, soil_group)

    cell_area_m2 = float(pixel_size_m * pixel_size_m)
    field_cells = int(mascara_lote.sum())
    field_area_m2 = field_cells * cell_area_m2
    field_area_ha = max(0.01, field_area_m2 / 10_000.0)

    # Grilla de milímetros base
    mm_grid = list(range(p_min, p_max + 1, chosen_step))

    ladder_steps: list[LadderStepResult] = []
    prev_ponded_ha = 0.0
    prev_outflow_m3 = 0.0

    for idx, p_mm in enumerate(mm_grid):
        # Medir tiempo acumulado para activar degradación si se proyecta superar presupuesto
        elapsed_s = time.perf_counter() - t_start
        if idx == 3 and elapsed_s * (len(mm_grid) / 3.0) > max_budget_s and chosen_step < step_degraded:
            chosen_step = step_degraded
            mm_grid = list(range(p_min, p_max + 1, chosen_step))

        # 1. Escorrentía efectiva Q por celda
        cn_ev = compute_nrcs_cn(
            precipitation_mm=float(p_mm),
            cn_ii_base=cn_base,
            antecedent_moisture=amc,  # type: ignore
            lambda_ratio=0.2,
        )

        # 2. Distribución topográfica de escorrentía y retención en depresiones
        _, _, dist = distribute_event_runoff_mfd(
            cn_result=cn_ev,
            mfd_area_m2=mfd_area_m2,
            mascara_lote=mascara_lote,
            pixel_size_m=pixel_size_m,
            depression_volume_in_field_m3=depression_volume_in_field_m3,
            external_inflow_ha=external_inflow_ha,
        )

        # Cálculo de superficie anegada
        # Si la escorrentía directa es cero (lluvia <= Ia), el encharcamiento es cero
        if cn_ev.runoff_q_mm <= 0.0:
            ponded_ha = 0.0
            outflow_m3 = 0.0
        else:
            retained_m3 = dist["potential_depression_retention_m3"]
            outflow_m3 = dist["net_outflow_potential_m3"]

            if depression_volume_in_field_m3 > 0.0:
                fill_fraction = min(1.0, retained_m3 / depression_volume_in_field_m3)
                ponded_ha = round(fill_fraction * depression_area_in_field_ha, 3)
            else:
                # Si el terreno no tiene cubetas de retención, las zonas de alta concentración indican encharcamiento
                ponded_ha = round(dist["high_concentration_area_ha"], 3)

        # Monotonicidad física estricta (no puede haber menos agua anegada con mayor lluvia)
        ponded_ha = max(prev_ponded_ha, ponded_ha)
        outflow_m3 = max(prev_outflow_m3, outflow_m3)
        prev_ponded_ha = ponded_ha
        prev_outflow_m3 = outflow_m3

        ponded_pct = round(min(100.0, 100.0 * (ponded_ha / field_area_ha)), 2)

        # 3. Erosión hídrica USLE dentro del lote con active_mask
        _, ero_sum = compute_usle_erosion_and_gullies(
            mfd_area_m2=mfd_area_m2,
            slope_pct=slope_pct,
            spi=spi,
            mascara_lote=mascara_lote,
            pixel_size_m=pixel_size_m,
            precipitation_mm=float(p_mm),
            runoff_q_mm=cn_ev.runoff_q_mm,
            soil_group=soil_group,
            cover_code=cover_code,
            sand_pct=sand_pct,
            silt_pct=silt_pct,
            clay_pct=clay_pct,
            k_factor=k_factor,
            active_mask=active_mask,
        )
        mean_loss = ero_sum.get("mean_soil_loss_t_ha")
        soil_loss_tha = round(float(mean_loss), 2) if mean_loss is not None else None

        ladder_steps.append(
            LadderStepResult(
                precipitation_mm=float(p_mm),
                ponded_area_ha=round(ponded_ha, 3),
                ponded_area_pct=ponded_pct,
                outflow_volume_m3=round(outflow_m3, 1),
                soil_loss_t_ha_yr=soil_loss_tha,
            )
        )

    t_end = time.perf_counter()
    total_ms = round((t_end - t_start) * 1000.0, 2)

    crit_threshold_mm = detect_critical_ponding_threshold(ladder_steps)

    out = {
        "field_id": field_id,
        "status": "ready",
        "parameters": {
            "soil_id": soil_group,
            "amc": amc,
            "cover_type": cover_code,
            "cn_base": round(cn_base, 1),
        },
        "benchmark_timing_ms": total_ms,
        "step_size_mm": chosen_step,
        "critical_ponding_threshold_mm": crit_threshold_mm,
        "ladder": [s.to_dict() for s in ladder_steps],
        "from_cache": False,
    }

    if use_cache:
        _LADDER_MEMORY_CACHE[cache_key] = out

    return out
