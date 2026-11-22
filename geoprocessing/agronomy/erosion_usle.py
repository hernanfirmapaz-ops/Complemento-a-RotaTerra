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
from geoprocessing.supuestos import (
    SUPUESTO_CARCAVAS_UMBRAL_PERDIDA_T_HA,
    SUPUESTO_CARCAVAS_UMBRAL_SPI,
    SUPUESTO_I30_RATIO_PRECIPITACION,
    SUPUESTO_I30_TOPE_MAX_MM_H,
    SUPUESTO_MATERIA_ORGANICA_PCT,
    SUPUESTO_USLE_ESTRUCTURA_CODIGO,
    SUPUESTO_USLE_P_CONTOUR_DEFECTO,
    SUPUESTO_USLE_P_TERRAZAS,
    SUPUESTO_USLE_PERMEABILIDAD_CODIGO,
    SUPUESTOS_USLE_C_FACTOR,
)

# Factor C (cobertura y manejo, adimensional 0..1) por sistema productivo según supuestos declarados
COVER_C_FACTOR: dict[str, float] = {k: float(s.valor) for k, s in SUPUESTOS_USLE_C_FACTOR.items()}


def estimate_soil_erodibility_k(
    sand_pct: float | None,
    silt_pct: float | None,
    clay_pct: float | None,
    organic_matter_pct: float | None = None,
    structure_code: int | None = None,
    permeability_code: int | None = None,
) -> float | None:
    """Calcula el factor de erodabilidad del suelo K en unidades SI [t·ha·h / (ha·MJ·mm)].

    Formulación estándar del nomograma de Wischmeier & Smith (1978, USDA Agriculture Handbook 537):
        100 K = 2.1 * 10^-4 * M^1.14 * (12 - a) + 3.25 * (b - 2) + 2.5 * (c - 3)
    donde:
        M = silt * (100 - clay).
        a = porcentaje de materia orgánica en horizonte superficial (% MO, acotado a [0.5, 4.0]).
        b = código de estructura del suelo (1 a 4; por omisión SUPUESTO_USLE_ESTRUCTURA_CODIGO = 2).
        c = código de permeabilidad del perfil (1 a 6; por omisión SUPUESTO_USLE_PERMEABILIDAD_CODIGO = 3).

    Nota sobre textura y fracción arena muy fina:
        K posiblemente subestimado: SoilGrids no separa la fracción arena muy fina (0.05-0.10 mm) de la arena total.
        En el nomograma original de Wischmeier & Smith (1978), M = (silt + vfs) * (100 - clay).

    Cita bibliográfica:
    - Wischmeier, W. H., & Smith, D. D. (1978). Predicting rainfall erosion losses: a guide to conservation planning.
      USDA Agriculture Handbook No. 537, Washington, D.C.
    - Conversión a SI (Foster et al., 1981, Trans. ASAE 24(5): 1255–1262): K_SI = K_US * 0.1317.
    """
    if sand_pct is None or silt_pct is None or clay_pct is None:
        return None

    try:
        total = float(sand_pct + silt_pct + clay_pct)
    except (TypeError, ValueError):
        return None

    if total <= 0:
        return None

    silt = float(silt_pct) * 100.0 / total
    clay = float(clay_pct) * 100.0 / total

    om = (
        float(organic_matter_pct)
        if organic_matter_pct is not None and organic_matter_pct >= 0
        else float(SUPUESTO_MATERIA_ORGANICA_PCT.valor)
    )
    a = float(np.clip(om, 0.5, 4.0))

    m = max(0.0, silt * (100.0 - clay))
    b = float(structure_code if structure_code is not None else SUPUESTO_USLE_ESTRUCTURA_CODIGO.valor)
    c = float(permeability_code if permeability_code is not None else SUPUESTO_USLE_PERMEABILIDAD_CODIGO.valor)

    k100 = 2.1e-4 * (m**1.14) * (12.0 - a) + 3.25 * (b - 2.0) + 2.5 * (c - 3.0)
    k_us = max(0.0, k100 / 100.0)
    k_si = k_us * 0.1317
    return round(float(k_si), 6)


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
    """Erosividad de una tormenta individual (MJ·mm / (ha·h)).

    Formulación de energía cinética unitaria según RUSLE (Brown & Foster, 1987, Trans. ASAE 30(2): 379–386;
    adoptada en Renard et al., 1997, USDA Agriculture Handbook No. 703, pág. 24, Ecuación 2-1):
        e = 0.29 * (1 - 0.72 * exp(-0.05 * i30)) [MJ / (ha·mm)]

    Si no se dispone de intensidad máxima en 30 minutos medida en pluviógrafo (`max_intensity_mm_h`),
    se adopta el supuesto declarado (SUPUESTO_I30_RATIO_PRECIPITACION):
        i30 = min(SUPUESTO_I30_TOPE_MAX_MM_H.valor, SUPUESTO_I30_RATIO_PRECIPITACION.valor * P).
    """
    p = max(0.0, float(precipitation_mm))
    if p < 5.0:
        return 0.5 * p
    i30 = (
        float(max_intensity_mm_h)
        if max_intensity_mm_h and max_intensity_mm_h > 0
        else min(float(SUPUESTO_I30_TOPE_MAX_MM_H.valor), float(SUPUESTO_I30_RATIO_PRECIPITACION.valor) * p)
    )
    # Energía cinética unitaria e [MJ / (ha·mm)] (Brown & Foster 1987 / Renard et al. 1997, AH 703, pág. 24)
    e_unit = 0.29 * (1.0 - 0.72 * math.exp(-0.05 * i30))
    ei30 = (e_unit * p) * i30
    return round(float(ei30), 2)


def estimate_mean_soil_loss_usle(
    precipitation_mm: float,
    runoff_q_mm: float = 0.0,
    soil_group: str = "B",
    cover_code: str = "soja_maiz_sd_buena",
    ls_mean: float = 1.0,
    p_factor: float = 1.0,
    max_intensity_mm_h: float | None = None,
    sand_pct: float | None = None,
    silt_pct: float | None = None,
    clay_pct: float | None = None,
    organic_matter_pct: float | None = None,
    k_factor: float | None = None,
) -> float | None:
    """Calcula la pérdida media de suelo de evento (t/ha) in situ usando la formulación USLE/RUSLE estándar:

    A = R * K * LS * C * P  [t / ha]
    (Wischmeier & Smith 1978, AH 537; Renard et al. 1997, AH 703).
    Si no se dispone de k_factor explícito ni de textura completa (arena, limo, arcilla),
    devuelve None (descartada sin datos inventados).
    No se aplica razón de entrega de sedimentos (SDR) sobre la pérdida en el lugar (auditoría 21/11/2026, punto 4).
    """
    if k_factor is not None:
        k_eff = float(k_factor)
    elif sand_pct is not None and silt_pct is not None and clay_pct is not None:
        k_eff = estimate_soil_erodibility_k(
            sand_pct=sand_pct,
            silt_pct=silt_pct,
            clay_pct=clay_pct,
            organic_matter_pct=organic_matter_pct,
        )
    else:
        k_eff = None

    if k_eff is None:
        return None

    c_factor = COVER_C_FACTOR.get(cover_code)
    if c_factor is None:
        return None
    r_storm = estimate_storm_erosivity_r(precipitation_mm, max_intensity_mm_h)
    return float(r_storm * k_eff * float(ls_mean) * c_factor * float(p_factor))


def estimate_usle_p_factor(
    slope_pct: float | None = None,
    contour_farming: bool = False,
    terraces_active: bool = False,
) -> float:
    """Calcula el factor P de prácticas de conservación (USLE).

    Cita bibliográfica:
    - Cultivo en contorno: USDA Agriculture Handbook 537 (Wischmeier & Smith 1978, pág. 35, Tabla 14),
      función de la pendiente:
      1.1 a 2.0 % -> P = 0.60
      2.1 a 7.0 % -> P = 0.50
      7.1 a 12.0 % -> P = 0.60
      12.1 a 18.0 % -> P = 0.80
      18.1 a 24.0 % -> P = 0.90
      pendientes llanas <= 1.0 % -> P = 1.0 (sin efecto de contorno).
    - Terrazas: USDA AH 537 (pág. 39, Tabla 15), factor reductor complementario declarado
      en supuestos.py (0.50).
    """
    p = 1.0
    if contour_farming:
        if slope_pct is None:
            p_contour = float(SUPUESTO_USLE_P_CONTOUR_DEFECTO.valor)
        elif slope_pct <= 1.0:
            p_contour = 1.0
        elif slope_pct <= 2.0:
            p_contour = 0.60
        elif slope_pct <= 7.0:
            p_contour = 0.50
        elif slope_pct <= 12.0:
            p_contour = 0.60
        elif slope_pct <= 18.0:
            p_contour = 0.80
        elif slope_pct <= 24.0:
            p_contour = 0.90
        else:
            p_contour = 1.0
        p *= p_contour

    if terraces_active:
        p *= float(SUPUESTO_USLE_P_TERRAZAS.valor)

    return float(p)


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
    sand_pct: float | None = None,
    silt_pct: float | None = None,
    clay_pct: float | None = None,
    organic_matter_pct: float | None = None,
    k_factor: float | None = None,
) -> tuple[np.ndarray, dict]:
    """Calcula la pérdida potencial de suelo por tormenta (t/ha) y localiza focos de cárcavas.

    Si no se dispone de textura ni factor K explícito, devuelve calidad 'descartada' y None en pérdida.
    Si `terraces_active` es True, las terrazas acortan la longitud efectiva de escurrimiento a
    `terrace_horizontal_spacing_m` y reducen el factor de práctica P_usle.
    """
    max_len = (
        float(terrace_horizontal_spacing_m)
        if terraces_active and terrace_horizontal_spacing_m
        else 180.0
    )
    ls_grid = compute_ls_factor_grid(mfd_area_m2, slope_pct, pixel_size_m, max_slope_length_m=max_len)

    if k_factor is not None:
        k_eff = float(k_factor)
        k_method = "explicit"
    elif sand_pct is not None and silt_pct is not None and clay_pct is not None:
        k_eff = estimate_soil_erodibility_k(
            sand_pct=sand_pct,
            silt_pct=silt_pct,
            clay_pct=clay_pct,
            organic_matter_pct=organic_matter_pct,
        )
        k_method = "wischmeier_texture" if k_eff is not None else "sin_datos_textura"
    else:
        k_eff = None
        k_method = "sin_datos_textura"

    c_factor = COVER_C_FACTOR.get(cover_code)

    r_storm = estimate_storm_erosivity_r(precipitation_mm, max_intensity_mm_h)

    valid = np.isfinite(ls_grid)
    in_field = mascara_lote & valid
    cell_area_ha = (float(pixel_size_m) ** 2) / 10_000.0
    ls_field = ls_grid[in_field]
    spi_field = spi[in_field & np.isfinite(spi)]
    slope_field = slope_pct[in_field & np.isfinite(slope_pct)]
    mean_slope = float(slope_field.mean()) if slope_field.size else None

    p_factor = estimate_usle_p_factor(mean_slope, contour_farming, terraces_active)

    ls_mean_val = round(float(ls_field.mean()), 3) if ls_field.size else None
    ls_max_val = round(float(ls_field.max()), 3) if ls_field.size else None
    spi_p95_val = round(float(np.percentile(spi_field, 95)), 3) if spi_field.size else None

    if k_eff is None or c_factor is None:
        empty_loss = np.full_like(ls_grid, np.nan, dtype="float32")
        motivo = (
            f"Código de cobertura desconocido '{cover_code}'. Sin factor C para USLE."
            if c_factor is None
            else "Sin datos de textura de suelo (% arena, limo, arcilla) para calcular factor K de Wischmeier"
        )
        summary = {
            "r_storm_mj_mm_ha_h": r_storm,
            "k_factor": round(float(k_eff), 6) if k_eff is not None else None,
            "k_calculation_method": k_method,
            "c_factor": c_factor,
            "p_factor": round(p_factor, 3),
            "ls_mean_in_field": ls_mean_val,
            "ls_max_in_field": ls_max_val,
            "effective_slope_length_cap_m": round(max_len, 1),
            "mean_soil_loss_t_ha": None,
            "max_soil_loss_t_ha": None,
            "total_field_soil_loss_tons": None,
            "gully_initiation_cells": 0,
            "gully_risk_area_ha": 0.0,
            "erosion_severity": "descartada",
            "calidad": "descartada",
            "motivo_descarte": motivo,
            "spi_p95_in_field": spi_p95_val,
        }
        return empty_loss, summary

    soil_loss_t_ha = np.where(
        valid,
        r_storm * k_eff * ls_grid * c_factor * p_factor,
        np.nan,
    ).astype("float32")

    loss_field = soil_loss_t_ha[in_field]

    # Focos de formación de cárcavas: celdas donde SPI >= umbral y pérdida >= umbral en el evento
    spi_thresh = float(SUPUESTO_CARCAVAS_UMBRAL_SPI.valor)
    loss_thresh = float(SUPUESTO_CARCAVAS_UMBRAL_PERDIDA_T_HA.valor)
    gully_mask = in_field & np.isfinite(spi) & (spi >= spi_thresh) & (soil_loss_t_ha >= loss_thresh)
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
        "k_factor": round(float(k_eff), 6),
        "k_calculation_method": k_method,
        "c_factor": c_factor,
        "p_factor": round(p_factor, 3),
        "ls_mean_in_field": ls_mean_val,
        "ls_max_in_field": ls_max_val,
        "effective_slope_length_cap_m": round(max_len, 1),
        "mean_soil_loss_t_ha": round(mean_loss, 3),
        "max_soil_loss_t_ha": round(max_loss, 3),
        "total_field_soil_loss_tons": round(total_tons, 2),
        "gully_initiation_cells": gully_cells,
        "gully_risk_area_ha": round(gully_area_ha, 3),
        "erosion_severity": severity,
        "calidad": "confiable",
        "spi_p95_in_field": spi_p95_val,
    }
    if k_method == "wischmeier_texture":
        summary["nota_k"] = "K posiblemente subestimado: SoilGrids no separa arena muy fina"
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
    sand_pct: float | None = None,
    silt_pct: float | None = None,
    clay_pct: float | None = None,
    organic_matter_pct: float | None = None,
    k_factor: float | None = None,
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
        sand_pct=sand_pct,
        silt_pct=silt_pct,
        clay_pct=clay_pct,
        organic_matter_pct=organic_matter_pct,
        k_factor=k_factor,
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
        sand_pct=sand_pct,
        silt_pct=silt_pct,
        clay_pct=clay_pct,
        organic_matter_pct=organic_matter_pct,
        k_factor=k_factor,
    )

    runoff_before_m3 = (runoff_q_mm / 1000.0) * field_area_m2
    runoff_after_m3 = (q_after_mm / 1000.0) * field_area_m2
    runoff_reduction_pct = (
        round(100.0 * (runoff_before_m3 - runoff_after_m3) / runoff_before_m3, 1)
        if runoff_before_m3 > 0
        else 0.0
    )

    loss_before_tons = erosion_before.get("total_field_soil_loss_tons")
    loss_after_tons = erosion_after.get("total_field_soil_loss_tons")
    if loss_before_tons is not None and loss_after_tons is not None and loss_before_tons > 0:
        soil_loss_saved_tons = round(loss_before_tons - loss_after_tons, 2)
        erosion_reduction_pct = round(100.0 * (loss_before_tons - loss_after_tons) / loss_before_tons, 1)
    else:
        soil_loss_saved_tons = None
        erosion_reduction_pct = None

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
        "soil_loss_before_t_ha": erosion_before.get("mean_soil_loss_t_ha"),
        "soil_loss_after_t_ha": erosion_after.get("mean_soil_loss_t_ha"),
        "soil_loss_saved_tons": soil_loss_saved_tons,
        "erosion_reduction_pct": erosion_reduction_pct,
        "terraces_geojson": terraces_geojson,
    }
