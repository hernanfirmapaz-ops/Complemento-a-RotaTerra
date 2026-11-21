"""Integración con el motor agronómico de RotaTerra (Fase 5, SDD §14 Fase 5).

Subdivide el lote en 4 ambientes hidro-topográficos cuantitativos:
1. `loma_bien_drenada` (código 1): sectores altos o con buen escurrimiento sin concentración erosiva.
2. `media_loma_transito` (código 2): laderas de tránsito difuso moderado.
3. `via_escurrimiento_concentrado` (código 3): ejes con SPI alto o área contribuyente concentrada
   (riesgo de erosión hídrica / lavado de semillas).
4. `bajo_acumulacion_anegable` (código 4): depresiones topográficas, zonas con TWI elevado o
   lámina 2D (`water_depth_m`) que supera el umbral de anegamiento.

Evalúa el riesgo de transitabilidad de maquinaria post-lluvia y genera criterios hidro-agronómicos
para el planificador trienal de cultivos de RotaTerra, respetando la regla obligatoria del SDD §14 Fase 5:
    "No convertir automáticamente una zona potencialmente húmeda en una recomendación agronómica
    sin considerar suelo, cultivo, drenaje, datos históricos y validación técnica."
"""

from __future__ import annotations

import numpy as np

ZONE_CATALOG: dict[int, dict[str, str]] = {
    1: {
        "code": "loma_bien_drenada",
        "label": "Ambiente 1 — Loma / Alto bien drenado",
        "hydro_behavior": "Baja acumulación superficial y rápida evacuación tras tormentas.",
        "management_guideline": (
            "Apto para siembra temprana e implantación de cultivos sensibles al anegamiento "
            "(ej. maíz temprano, girasol, alfalfa); priorizar cobertura de rastrojo para retener humedad."
        ),
    },
    2: {
        "code": "media_loma_transito",
        "label": "Ambiente 2 — Media loma de tránsito difuso",
        "hydro_behavior": "Escurrimiento laminar moderado sin estancamiento prolongado.",
        "management_guideline": (
            "Apto para rotación agrícola estándar (soja / maíz / trigo-soja de 2ª) en siembra directa "
            "manteniendo cobertura > 30 % para maximizar infiltración."
        ),
    },
    3: {
        "code": "via_escurrimiento_concentrado",
        "label": "Ambiente 3 — Vía de escurrimiento concentrado (riesgo erosivo)",
        "hydro_behavior": "Convergencia de flujo desde aguas arriba y alta potencia de escurrimiento (SPI).",
        "management_guideline": (
            "Evitar suelo descubierto y labranza a favor de la pendiente. Incorporar cultivos de servicio "
            "invernales de raíz densa (centeno / vicia / avena) o franjas empastadas en las vaguadas."
        ),
    },
    4: {
        "code": "bajo_acumulacion_anegable",
        "label": "Ambiente 4 — Bajo receptor / propenso a exceso hídrico",
        "hydro_behavior": "Depresión topográfica o alto índice de humedad (TWI) donde converge y se retiene el agua.",
        "management_guideline": (
            "Riesgo de anoxia radicular y falta de piso post-lluvia. Evaluar fechas de siembra diferidas, "
            "híbridos/variedades tolerantes o pasturas adaptadas a bajos, sujeto a análisis de suelo y napa."
        ),
    },
}


def classify_hydro_agronomic_zones(
    z: np.ndarray,
    slope_pct: np.ndarray,
    sink_depth_m: np.ndarray,
    twi: np.ndarray,
    spi: np.ndarray,
    mascara_lote: np.ndarray,
    pixel_size_m: float,
    max_water_depth_m: np.ndarray | None = None,
    ponding_threshold_m: float = 0.05,
    soil_group: str = "B",
) -> tuple[np.ndarray, dict]:
    """Clasifica cada celda del lote en los 4 ambientes hidro-agronómicos y genera el resumen Fase 5."""
    valid = np.isfinite(z) & np.isfinite(twi) & np.isfinite(spi)
    in_field = mascara_lote & valid
    zone_grid = np.zeros(z.shape, dtype="int32")

    if not in_field.any():
        return zone_grid, {"zones": [], "trafficability": {}, "rotaterra_criteria": []}

    z_fld = z[in_field]
    twi_fld = twi[in_field]
    spi_fld = spi[in_field]

    z_p65 = float(np.percentile(z_fld, 65))
    twi_p82 = float(np.percentile(twi_fld, 82))
    spi_p85 = float(np.percentile(spi_fld, 85))

    # Reglas de asignación por celda válida:
    # Por defecto: Media loma (2); si cota >= P65 y TWI moderado -> Loma (1)
    zone_grid[valid] = 2
    high_ground = valid & (z >= z_p65) & (twi < twi_p82)
    zone_grid[high_ground] = 1

    # Vías de escurrimiento concentrado (3): SPI en el 15 % superior y pendiente > 0,6 %
    concentrated_flow = valid & (spi >= max(0.5, spi_p85)) & (slope_pct >= 0.6)
    zone_grid[concentrated_flow] = 3

    # Bajos receptores / anegables (4): depresión > 0.08 m, TWI en el 18 % superior con baja pendiente,
    # o profundidad 2D simulada >= ponding_threshold_m
    low_wet = valid & ((sink_depth_m >= 0.08) | ((twi >= twi_p82) & (slope_pct < 1.2)))
    if max_water_depth_m is not None:
        low_wet = low_wet | (valid & np.isfinite(max_water_depth_m) & (max_water_depth_m >= ponding_threshold_m))
    zone_grid[low_wet] = 4

    cell_area_ha = (float(pixel_size_m) ** 2) / 10_000.0
    total_field_cells = int(in_field.sum())

    zones_summary: list[dict] = []
    pct_by_zone: dict[int, float] = {}
    for z_id in (1, 2, 3, 4):
        mask_z = in_field & (zone_grid == z_id)
        cnt = int(mask_z.sum())
        area_ha = cnt * cell_area_ha
        pct = (100.0 * cnt / total_field_cells) if total_field_cells > 0 else 0.0
        pct_by_zone[z_id] = pct
        meta = ZONE_CATALOG[z_id]
        zones_summary.append({
            "zone_id": z_id,
            "code": meta["code"],
            "label": meta["label"],
            "cells": cnt,
            "area_ha": round(area_ha, 3),
            "percentage_of_field": round(pct, 2),
            "mean_elevation_m": round(float(z[mask_z].mean()), 2) if cnt else None,
            "mean_slope_pct": round(float(slope_pct[mask_z].mean()), 2) if cnt else None,
            "mean_twi": round(float(twi[mask_z].mean()), 2) if cnt else None,
            "mean_spi": round(float(spi[mask_z].mean()), 3) if cnt else None,
            "hydro_behavior": meta["hydro_behavior"],
            "management_guideline": meta["management_guideline"],
        })

    # Evaluación de transitabilidad de maquinaria (Fase 5, SDD §14 Fase 5)
    base_wait_days = {"A": 1.0, "B": 2.0, "C": 3.5, "D": 5.5}.get(soil_group, 2.5)
    wet_share = (pct_by_zone[3] + pct_by_zone[4]) / 100.0
    est_wait_days_lows = round(base_wait_days * (1.35 + 1.1 * wet_share), 1)
    est_wait_days_highs = round(max(0.5, base_wait_days * 0.65), 1)

    if pct_by_zone[4] >= 22.0 or soil_group in ("C", "D"):
        traffic_risk = "alto"
        traffic_note = (
            f"Riesgo alto de falta de piso en bajos ({pct_by_zone[4]:.1f} % del lote en Ambiente 4, "
            f"suelo grupo {soil_group}). Espera estimada post-tormenta fuerte: ~{est_wait_days_lows} días en bajos "
            f"vs. ~{est_wait_days_highs} días en lomas."
        )
    elif pct_by_zone[4] >= 10.0:
        traffic_risk = "moderado"
        traffic_note = (
            f"Transitabilidad condicionada en sectores bajos ({pct_by_zone[4]:.1f} % del lote). "
            f"Planificar ingreso de pulverizadora/sembradora separando lomas (~{est_wait_days_highs} días) "
            f"de bajos (~{est_wait_days_lows} días)."
        )
    else:
        traffic_risk = "bajo"
        traffic_note = (
            f"Buena transitabilidad general ({100.0 - pct_by_zone[4]:.1f} % del lote fuera de bajos receptores)."
        )

    rotaterra_criteria = [
        f"Zonificación por ambientes: {pct_by_zone[1]:.1f} % Loma bien drenada, {pct_by_zone[2]:.1f} % Media loma, "
        f"{pct_by_zone[3]:.1f} % Vías de escurrimiento concentrado y {pct_by_zone[4]:.1f} % Bajos receptores.",
        traffic_note,
        "Integración con rotación trienal RotaTerra: en lotes con más de 10 % en Ambiente 3 (vías concentradas), "
        "priorizar puente verde invernal (cultivo de cobertura gramínea + leguminosa) entre campañas estivales.",
        "Advertencia técnica SDD §14 Fase 5: esta clasificación es una variable topográfica-hidrológica dentro "
        "del análisis multicriterio; debe cruzarse con profundidad de napa, salinidad/sodicidad, textura e "
        "historia productiva antes de definir prescripciones de manejo por ambiente.",
    ]

    return zone_grid, {
        "twi_field_mean": round(float(twi_fld.mean()), 2),
        "twi_field_p90": round(float(np.percentile(twi_fld, 90)), 2),
        "spi_field_mean": round(float(spi_fld.mean()), 3),
        "spi_field_p90": round(float(np.percentile(spi_fld, 90)), 3),
        "zones": zones_summary,
        "trafficability": {
            "risk_level": traffic_risk,
            "soil_group_assumed": soil_group,
            "estimated_wait_days_high_ground": est_wait_days_highs,
            "estimated_wait_days_low_ground": est_wait_days_lows,
            "summary": traffic_note,
        },
        "rotaterra_criteria": rotaterra_criteria,
    }
