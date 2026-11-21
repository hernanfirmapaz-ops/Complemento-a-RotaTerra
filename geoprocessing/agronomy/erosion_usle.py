"""Herramienta 1 y 4: Erosión hídrica (USLE/RUSLE + MUSLE de evento) y diseño/simulación de Terrazas a nivel.

Fórmula USLE / RUSLE (Wischmeier & Smith 1978 / Renard et al. 1997):
    A = R * K * LS * C * P_usle     [t / ha / año  o  t / ha / evento]

Factor topográfico 2D (Moore & Burch 1986 / Desmet & Govers 1996) sobre la grilla UTM:
    LS = ((a / 22.13) ** 0.4) * ((sin(beta) / 0.0896) ** 1.3)
donde `a` es el área contribuyente específica MFD por unidad de ancho (m²/m) acotada a longitud
efectiva de ladera (máx. 180 m sin terrazas, o espaciamiento horizontal HI cuando hay terrazas).

Nota obligatoria (SDD §2.2): los valores de pérdida de suelo son estimaciones comparativas
derivadas del relieve y tablas paramétricas; requieren calibración local para uso definitivo.
"""

from __future__ import annotations

import math

import numpy as np

from geoprocessing.dem.terrain import Dem, contours_geojson

# Erodabilidad del suelo K (t·ha·h / (ha·MJ·mm)) orientativa por Grupo Hidrológico (tablas INTA / USDA)
SOIL_K_BY_GROUP: dict[str, float] = {
    "A": 0.018,  # arenosos / francos gruesos (baja susceptibilidad al desprendimiento, alta infiltración)
    "B": 0.032,  # francos / franco-limosos pampeanos y subhúmedos
    "C": 0.042,  # franco-arcillo-limosos con menor permeabilidad
    "D": 0.038,  # arcillosos / sódicos
}

# Factor C (cobertura y manejo, adimensional 0..1) por sistema productivo
COVER_C_FACTOR: dict[str, float] = {
    "soja_maiz_sd_buena": 0.09,
    "soja_maiz_convencional": 0.34,
    "trigo_cereal_invierno_sd": 0.06,
    "cultivo_cobertura_vicia_centeno": 0.03,
    "pastura_pradera_buena": 0.015,
    "pastura_sobrepastoreada": 0.18,
    "barbecho_con_rastrojo": 0.14,
    "barbecho_suelo_desnudo": 0.55,
}


def compute_ls_factor_grid(
    mfd_area_m2: np.ndarray,
    slope_pct: np.ndarray,
    pixel_size_m: float,
    max_slope_length_m: float = 180.0,
) -> np.ndarray:
    """Calcula el factor topográfico LS por celda en UTM, acotando la longitud efectiva de ladera."""
    valid = np.isfinite(mfd_area_m2) & np.isfinite(slope_pct)
    specific_a = np.where(
        valid,
        np.clip(mfd_area_m2 / float(pixel_size_m), float(pixel_size_m), float(max_slope_length_m)),
        np.nan,
    )
    slope_rad = np.arctan(np.maximum(0.001, slope_pct / 100.0))
    sin_beta = np.sin(slope_rad)

    with np.errstate(invalid="ignore"):
        l_factor = np.power(specific_a / 22.13, 0.4)
        s_factor = np.power(sin_beta / 0.0896, 1.3)
        ls = l_factor * s_factor

    return np.where(valid, ls, np.nan).astype("float32")


def estimate_storm_erosivity_r(precipitation_mm: float, max_intensity_mm_h: float | None = None) -> float:
    """Erosividad EI30 de una tormenta individual (MJ·mm / (ha·h)) según Wischmeier & Smith / Lombardi Neto.

    Nota de trazabilidad científica y supuestos conservadores (SDD §4.4 / Regla R4):
    Si no se suministra la intensidad máxima en 30 minutos observada en estación de campo (`max_intensity_mm_h`),
    se adopta como supuesto conservador documentado la relación empírica pampeana i30 ~ min(75.0, 0.65 * P)
    (Lombardi Neto et al. 1980; Bertoni & Lombardi Neto 1990; INTA Castelar).
    """
    p = max(0.0, float(precipitation_mm))
    if p < 5.0:
        return 0.5 * p
    i30 = float(max_intensity_mm_h) if max_intensity_mm_h and max_intensity_mm_h > 0 else min(75.0, 0.65 * p)
    # Energía cinética unitaria aproximada e ~ 0.29 * (1 - 0.72 * exp(-0.05 * i30)) [MJ / (ha·mm)]
    e_unit = 0.29 * (1.0 - 0.72 * math.exp(-0.05 * i30))
    ei30 = (e_unit * p) * i30
    return round(float(ei30), 2)


def estimate_mean_soil_loss_usle(
    precipitation_mm: float,
    runoff_q_mm: float,
    soil_group: str,
    cover_code: str,
    ls_mean: float,
    p_factor: float = 1.0,
    max_intensity_mm_h: float | None = None,
) -> float:
    """Calcula la pérdida media de suelo de evento (t/ha) usando la formulación USLE/RUSLE estándar.

    A = R * K * LS * C * P * SDR
    Donde SDR es el ratio de entrega de sedimentos (delivery_ratio) basado en escorrentía superficial
    (Williams & Berndt 1977; Wischmeier & Smith 1978).
    """
    k_factor = SOIL_K_BY_GROUP.get(soil_group, 0.032)
    c_factor = COVER_C_FACTOR.get(cover_code, 0.12)
    r_storm = estimate_storm_erosivity_r(precipitation_mm, max_intensity_mm_h)
    p = float(precipitation_mm)
    delivery_ratio = min(1.0, 0.15 + 0.85 * (runoff_q_mm / max(1.0, p))) if p > 0 else 0.0
    return float(r_storm * k_factor * float(ls_mean) * c_factor * float(p_factor) * delivery_ratio)


def compute_usle_erosion_and_gullies(
    mfd_area_m2: np.ndarray,
    slope_pct: np.ndarray,
    spi: np.ndarray,
    mascara_lote: np.ndarray,
    pixel_size_m: float,
    precipitation_mm: float,
    runoff_q_mm: float,
    soil_group: str = "B",
    cover_code: str = "soja_maiz_sd_buena",
    contour_farming: bool = False,
    terraces_active: bool = False,
    terrace_horizontal_spacing_m: float | None = None,
    max_intensity_mm_h: float | None = None,
) -> tuple[np.ndarray, dict]:
    """Calcula la pérdida potencial de suelo por tormenta (t/ha) y localiza focos de cárcavas.

    Si `terraces_active` es True, las terrazas acortan la longitud efectiva de escurrimiento a
    `terrace_horizontal_spacing_m` y reducen el factor de práctica P_usle.
    """
    max_len = (
        float(terrace_horizontal_spacing_m)
        if terraces_active and terrace_horizontal_spacing_m
        else 180.0
    )
    ls_grid = compute_ls_factor_grid(mfd_area_m2, slope_pct, pixel_size_m, max_slope_length_m=max_len)

    k_factor = SOIL_K_BY_GROUP.get(soil_group, 0.032)
    c_factor = COVER_C_FACTOR.get(cover_code, 0.12)
    p_factor = 1.0
    if contour_farming:
        p_factor *= 0.65
    if terraces_active:
        p_factor *= 0.50

    r_storm = estimate_storm_erosivity_r(precipitation_mm, max_intensity_mm_h)
    # Ratio de entrega de sedimentos (Sediment Delivery Ratio, SDR / delivery_ratio):
    # Enfoque empírico basado en escorrentía superficial efectiva (Williams & Berndt 1977, USDA SCS-TP-149;
    # Wischmeier & Smith 1978). Si Q == 0, el transporte de sedimentos fuera del lote es nulo.
    delivery_ratio = min(1.0, 0.15 + 0.85 * (runoff_q_mm / max(1.0, precipitation_mm))) if precipitation_mm > 0 else 0.0

    valid = np.isfinite(ls_grid)
    soil_loss_t_ha = np.where(
        valid,
        r_storm * k_factor * ls_grid * c_factor * p_factor * delivery_ratio,
        np.nan,
    ).astype("float32")

    in_field = mascara_lote & valid
    cell_area_ha = (float(pixel_size_m) ** 2) / 10_000.0
    loss_field = soil_loss_t_ha[in_field]
    ls_field = ls_grid[in_field]
    spi_field = spi[in_field & np.isfinite(spi)]

    # Focos de formación de cárcavas: celdas donde SPI >= 2.5 y pérdida >= 2.0 t/ha en el evento
    gully_mask = in_field & np.isfinite(spi) & (spi >= 2.5) & (soil_loss_t_ha >= 1.5)
    gully_cells = int(gully_mask.sum())
    gully_area_ha = gully_cells * cell_area_ha

    mean_loss = float(loss_field.mean()) if loss_field.size else 0.0
    max_loss = float(loss_field.max()) if loss_field.size else 0.0
    total_tons = float(loss_field.sum() * cell_area_ha) if loss_field.size else 0.0

    if mean_loss < 0.5:
        severity = "bajo"
    elif mean_loss < 2.0:
        severity = "moderado"
    elif mean_loss < 5.0:
        severity = "alto"
    else:
        severity = "severo"

    summary = {
        "r_storm_mj_mm_ha_h": r_storm,
        "k_factor": k_factor,
        "c_factor": c_factor,
        "p_factor": round(p_factor, 3),
        "ls_mean_in_field": round(float(ls_field.mean()), 3) if ls_field.size else 0.0,
        "ls_max_in_field": round(float(ls_field.max()), 3) if ls_field.size else 0.0,
        "effective_slope_length_cap_m": round(max_len, 1),
        "mean_soil_loss_t_ha": round(mean_loss, 3),
        "max_soil_loss_t_ha": round(max_loss, 3),
        "total_field_soil_loss_tons": round(total_tons, 2),
        "gully_initiation_cells": gully_cells,
        "gully_risk_area_ha": round(gully_area_ha, 3),
        "erosion_severity": severity,
        "spi_p95_in_field": round(float(np.percentile(spi_field, 95)), 3) if spi_field.size else 0.0,
    }
    return soil_loss_t_ha, summary


def design_and_simulate_contour_terraces(
    dem: Dem,
    mascara_lote: np.ndarray,
    mfd_area_m2: np.ndarray,
    slope_pct: np.ndarray,
    spi: np.ndarray,
    precipitation_mm: float,
    runoff_q_mm: float,
    soil_group: str = "B",
    cover_code: str = "soja_maiz_sd_buena",
    terrace_channel_capacity_m3_per_m: float = 0.35,
) -> dict:
    """Herramienta 4: Traza curvas a nivel / terrazas dentro del lote y simula cómo frenan el agua y la erosión.

    1. Determina el intervalo vertical (VI) y espaciamiento horizontal medio (HI) según la pendiente media
       del lote (criterio técnico INTA / USDA-NRCS: VI ≈ 0.30 * (S_pct / 3 + 2)).
    2. Extrae las trazas de terrazas a nivel recortadas al interior del lote.
    3. Compara el lote **Sin Terrazas** vs. **Con Terrazas a Nivel**:
       - Volumen de agua frenado/retenido por los canales de terraza (m³ y mm equivalentes),
       - Reducción de escorrentía neta saliente del lote (m³ y %),
       - Reducción de pérdida de suelo por erosión USLE (t/ha y %).
    """
    valid_field = mascara_lote & np.isfinite(dem.z) & np.isfinite(slope_pct)
    slopes_f = slope_pct[valid_field]
    mean_s = float(slopes_f.mean()) if slopes_f.size else 2.0
    mean_s_eff = max(0.8, mean_s)

    # Intervalo vertical VI (m) y espaciamiento horizontal HI (m)
    vi_m = round(float(np.clip(0.30 * (mean_s_eff / 3.0 + 2.0), 0.75, 3.0)), 2)
    hi_m = round(float(np.clip((vi_m * 100.0) / mean_s_eff, 25.0, 120.0)), 1)

    # Generar curvas a nivel solo dentro del lote (enmascarando fuera del lote con NaN)
    z_masked = np.where(mascara_lote, dem.z, np.nan).astype("float32")
    dem_masked = Dem(z=z_masked, transform=dem.transform, crs=dem.crs)
    terraces_geojson = contours_geojson(dem_masked, interval_m=vi_m, max_levels=25)

    # Estimar longitud total de terrazas trazadas dentro del lote
    cell_area_m2 = float(dem.pixel * dem.pixel)
    field_area_m2 = float(valid_field.sum() * cell_area_m2)
    field_area_ha = field_area_m2 / 10_000.0
    estimated_terrace_length_m = round(field_area_m2 / hi_m, 0) if hi_m > 0 else 0.0

    # Escenario Base (Sin Terrazas)
    _, erosion_before = compute_usle_erosion_and_gullies(
        mfd_area_m2=mfd_area_m2,
        slope_pct=slope_pct,
        spi=spi,
        mascara_lote=mascara_lote,
        pixel_size_m=dem.pixel,
        precipitation_mm=precipitation_mm,
        runoff_q_mm=runoff_q_mm,
        soil_group=soil_group,
        cover_code=cover_code,
        contour_farming=False,
        terraces_active=False,
    )

    # Capacidad de intercepción hidráulica de las terrazas
    water_intercepted_m3 = min(
        (runoff_q_mm / 1000.0) * field_area_m2 * 0.75,
        estimated_terrace_length_m * float(terrace_channel_capacity_m3_per_m),
    )
    intercepted_mm = (water_intercepted_m3 / max(1.0, field_area_m2)) * 1000.0
    q_after_mm = max(0.0, runoff_q_mm - intercepted_mm)

    # Escenario Con Terrazas a Nivel (acorta longitud de ladera a HI y aplica práctica en contorno)
    _, erosion_after = compute_usle_erosion_and_gullies(
        mfd_area_m2=mfd_area_m2,
        slope_pct=slope_pct,
        spi=spi,
        mascara_lote=mascara_lote,
        pixel_size_m=dem.pixel,
        precipitation_mm=precipitation_mm,
        runoff_q_mm=q_after_mm,
        soil_group=soil_group,
        cover_code=cover_code,
        contour_farming=True,
        terraces_active=True,
        terrace_horizontal_spacing_m=hi_m,
    )

    runoff_before_m3 = (runoff_q_mm / 1000.0) * field_area_m2
    runoff_after_m3 = (q_after_mm / 1000.0) * field_area_m2
    runoff_reduction_pct = (
        round(100.0 * (runoff_before_m3 - runoff_after_m3) / runoff_before_m3, 1)
        if runoff_before_m3 > 0
        else 0.0
    )
    erosion_reduction_pct = (
        round(
            100.0
            * (erosion_before["total_field_soil_loss_tons"] - erosion_after["total_field_soil_loss_tons"])
            / erosion_before["total_field_soil_loss_tons"],
            1,
        )
        if erosion_before["total_field_soil_loss_tons"] > 0
        else 0.0
    )

    return {
        "mean_field_slope_pct": round(mean_s, 2),
        "recommended_vertical_interval_m": vi_m,
        "recommended_horizontal_spacing_m": hi_m,
        "terrace_levels_count": len(terraces_geojson["features"]),
        "estimated_total_terrace_length_m": estimated_terrace_length_m,
        "field_area_ha": round(field_area_ha, 2),
        "runoff_before_mm": round(runoff_q_mm, 2),
        "runoff_after_mm": round(q_after_mm, 2),
        "water_retained_by_terraces_m3": round(water_intercepted_m3, 1),
        "runoff_reduction_pct": runoff_reduction_pct,
        "soil_loss_before_t_ha": erosion_before["mean_soil_loss_t_ha"],
        "soil_loss_after_t_ha": erosion_after["mean_soil_loss_t_ha"],
        "soil_loss_saved_tons": round(
            erosion_before["total_field_soil_loss_tons"] - erosion_after["total_field_soil_loss_tons"],
            2,
        ),
        "erosion_reduction_pct": erosion_reduction_pct,
        "terraces_geojson": terraces_geojson,
    }
