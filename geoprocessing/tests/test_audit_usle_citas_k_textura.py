"""Tests para verificar la formulación USLE con citas verificadas y K por textura

(Auditoría 21/11/2026, punto 4 / Issue #10).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from geoprocessing.agronomy.erosion_usle import (
    compute_usle_erosion_and_gullies,
    estimate_mean_soil_loss_usle,
    estimate_soil_erodibility_k,
    estimate_storm_erosivity_r,
)
from geoprocessing.supuestos import (
    SUPUESTO_I30_RATIO_PRECIPITACION,
)


def test_k_factor_wischmeier_hand_calculated_values():
    """Verifica el cálculo del factor K por nomograma de Wischmeier & Smith (1978, pág. 12)

    con valores calculados a mano y conversión a unidades SI (Foster et al. 1981).
    100 K = 2.1 * 10^-4 * M^1.14 * (12 - a) + 3.25 * (b - 2) + 2.5 * (c - 3)
    donde M = silt * (100 - clay), a = %MO, b = estructura (def 2), c = permeabilidad (def 3).
    K_SI = (100 K / 100) * 0.1317  [t·ha·h / (ha·MJ·mm)]
    """
    # 1. Suelo Franco típico pampeano: 40% arena, 40% limo, 20% arcilla, 2.5% MO
    # M = 40 * (100 - 20) = 3200
    # M^1.14 = 3200^1.14 = 9904.5518...
    # 100 K = 2.1e-4 * 9904.5518 * (12 - 2.5) = 19.75958...
    # K_US = 0.197596
    # K_SI = 0.197596 * 0.1317 = 0.026023...
    k_franca = estimate_soil_erodibility_k(
        sand_pct=40.0,
        silt_pct=40.0,
        clay_pct=20.0,
        organic_matter_pct=2.5,
        structure_code=2,
        permeability_code=3,
    )
    assert k_franca == pytest.approx(0.026023, rel=1e-3)

    # 2. Suelo Franco limoso (alto limo, alta susceptibilidad a la erosión):
    # 17% arena, 70% limo, 13% arcilla, 2.5% MO
    # M = 70 * (100 - 13) = 6090
    # M^1.14 = 6090^1.14 = 20628.313...
    # 100 K = 2.1e-4 * 20628.313 * (12 - 2.5) = 41.1535...
    # K_US = 0.411535
    # K_SI = 0.411535 * 0.1317 = 0.054199...
    k_franco_limoso = estimate_soil_erodibility_k(
        sand_pct=17.0,
        silt_pct=70.0,
        clay_pct=13.0,
        organic_matter_pct=2.5,
        structure_code=2,
        permeability_code=3,
    )
    assert k_franco_limoso == pytest.approx(0.054199, rel=1e-3)
    # El franco limoso debe ser notablemente más erodible que el franco
    assert k_franco_limoso > k_franca

    # 3. Suelo Arenoso (baja retención de limo, c=2 permeabilidad moderada-rápida):
    # 90% arena, 5% limo, 5% arcilla, 1.0% MO, c=2
    # M = 5 * 95 = 475
    # M^1.14 = 475^1.14 = 1125.721...
    # 100 K = 2.1e-4 * 1125.721 * 11 + 2.5 * (2 - 3) = 2.6004 - 2.5 = 0.1004...
    # K_US = 0.001004
    # K_SI = 0.001004 * 0.1317 = 0.000132...
    k_arenosa = estimate_soil_erodibility_k(
        sand_pct=90.0,
        silt_pct=5.0,
        clay_pct=5.0,
        organic_matter_pct=1.0,
        structure_code=2,
        permeability_code=2,
    )
    assert k_arenosa == pytest.approx(0.000132, rel=1e-2)
    assert k_arenosa < k_franca


def test_no_delivery_ratio_applied_to_inplace_soil_loss():
    """Verifica que NO se aplique la razón de entrega (delivery_ratio) sobre la pérdida

    de suelo en el lugar (in situ), ya que USLE calcula A = R * K * LS * C * P (t/ha).
    """
    p = 50.0
    i30 = 30.0
    r = estimate_storm_erosivity_r(p, max_intensity_mm_h=i30)
    k = 0.026
    ls = 1.5
    c = 0.09
    p_fac = 1.0

    # Pérdida teórica exacta sin razón de entrega
    expected_loss = r * k * ls * c * p_fac

    # Con runoff_q_mm = 10 mm
    loss_q10 = estimate_mean_soil_loss_usle(
        precipitation_mm=p,
        runoff_q_mm=10.0,
        k_factor=k,
        cover_code="soja_maiz_sd_buena",
        ls_mean=ls,
        p_factor=p_fac,
        max_intensity_mm_h=i30,
    )
    # Con runoff_q_mm = 40 mm
    loss_q40 = estimate_mean_soil_loss_usle(
        precipitation_mm=p,
        runoff_q_mm=40.0,
        k_factor=k,
        cover_code="soja_maiz_sd_buena",
        ls_mean=ls,
        p_factor=p_fac,
        max_intensity_mm_h=i30,
    )

    # La pérdida de suelo in situ USLE no debe reducirse por la escorrentía superficial
    assert loss_q10 == pytest.approx(expected_loss, rel=1e-3)
    assert loss_q40 == pytest.approx(expected_loss, rel=1e-3)
    assert loss_q10 == loss_q40


def test_storm_erosivity_r_hand_calculated_and_supuesto():
    """Verifica el cálculo de erosividad R y el uso del supuesto editable i30."""
    # Cálculo a mano: P = 50 mm, I30 = 30 mm/h
    # e_unit = 0.29 * (1 - 0.72 * exp(-0.05 * 30))
    # exp(-1.5) = 0.223130
    # e_unit = 0.29 * (1 - 0.72 * 0.223130) = 0.29 * 0.839346 = 0.243410 MJ/(ha·mm)
    # EI30 = e_unit * 50 * 30 = 0.243410 * 1500 = 365.115 ~ 365.12 MJ·mm/(ha·h)
    r_medido = estimate_storm_erosivity_r(50.0, max_intensity_mm_h=30.0)
    assert r_medido == pytest.approx(365.12, abs=0.1)

    # Sin i30 suministrado: debe usar el supuesto declarado i30 = min(75, SUPUESTO * P)
    r_estimado = estimate_storm_erosivity_r(50.0, max_intensity_mm_h=None)
    i30_esperado = min(75.0, SUPUESTO_I30_RATIO_PRECIPITACION.valor * 50.0)
    e_unit_esp = 0.29 * (1.0 - 0.72 * math.exp(-0.05 * i30_esperado))
    r_esperado = round((e_unit_esp * 50.0) * i30_esperado, 2)
    assert r_estimado == pytest.approx(r_esperado, abs=0.1)


def test_compute_usle_with_soilgrids_texture_grid():
    """Verifica que compute_usle_erosion_and_gullies use textura de SoilGrids si se provee."""
    mfd = np.full((10, 10), 1000.0, dtype=np.float32)
    slope = np.full((10, 10), 3.0, dtype=np.float32)
    spi = np.full((10, 10), 1.0, dtype=np.float32)
    mascara = np.ones((10, 10), dtype=bool)

    # Correr con textura Franca vs Franco Limosa
    _, res_franca = compute_usle_erosion_and_gullies(
        mfd_area_m2=mfd,
        slope_pct=slope,
        spi=spi,
        mascara_lote=mascara,
        pixel_size_m=30.0,
        precipitation_mm=50.0,
        runoff_q_mm=15.0,
        sand_pct=40.0,
        silt_pct=40.0,
        clay_pct=20.0,
    )

    _, res_franco_limosa = compute_usle_erosion_and_gullies(
        mfd_area_m2=mfd,
        slope_pct=slope,
        spi=spi,
        mascara_lote=mascara,
        pixel_size_m=30.0,
        precipitation_mm=50.0,
        runoff_q_mm=15.0,
        sand_pct=17.0,
        silt_pct=70.0,
        clay_pct=13.0,
    )

    # La pérdida con suelo franco limoso debe ser mayor debido a mayor K
    assert res_franco_limosa["k_factor"] > res_franca["k_factor"]
    assert res_franco_limosa["mean_soil_loss_t_ha"] > res_franca["mean_soil_loss_t_ha"]
