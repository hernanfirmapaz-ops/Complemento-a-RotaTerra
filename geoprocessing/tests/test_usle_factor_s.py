"""Tests para el factor topográfico S de McCool et al. (1987) y Moore & Burch (1986) en USLE/RUSLE."""

import math

import numpy as np
import pytest

from geoprocessing.agronomy.erosion_usle import compute_ls_factor_grid, compute_usle_s_factor
from geoprocessing.supuestos import (
    SUPUESTO_USLE_MAX_SLOPE_LENGTH_M,
    SUPUESTO_USLE_MCCOOL_COEF_A,
    SUPUESTO_USLE_MCCOOL_COEF_B,
    SUPUESTO_USLE_SLOPE_THRESHOLD_PCT,
)


def test_usle_supuestos_citations_and_metadata():
    """Verifica que los supuestos del factor S y longitud máxima tengan citas y metadatos válidos."""
    assert SUPUESTO_USLE_SLOPE_THRESHOLD_PCT.valor == 9.0
    assert SUPUESTO_USLE_SLOPE_THRESHOLD_PCT.unidad == "%"
    assert "McCool" in SUPUESTO_USLE_SLOPE_THRESHOLD_PCT.fuente_referencia
    assert "703" in SUPUESTO_USLE_SLOPE_THRESHOLD_PCT.fuente_referencia

    assert SUPUESTO_USLE_MCCOOL_COEF_A.valor == 10.8
    assert "McCool" in SUPUESTO_USLE_MCCOOL_COEF_A.fuente_referencia

    assert SUPUESTO_USLE_MCCOOL_COEF_B.valor == 0.03
    assert "McCool" in SUPUESTO_USLE_MCCOOL_COEF_B.fuente_referencia

    assert SUPUESTO_USLE_MAX_SLOPE_LENGTH_M.valor == 180.0
    assert SUPUESTO_USLE_MAX_SLOPE_LENGTH_M.unidad == "m"


def test_usle_s_factor_low_slope_0_5_pct():
    """Valida el factor S a 0.5% de pendiente (llanura típica de San Luis / región pampeana).

    Formula McCool et al. (1987) para s < 9%:
        s = 0.005 -> sin(beta) = 0.005 / sqrt(1 + 0.005^2) ≈ 0.0049999
        S = 10.8 * sin(beta) + 0.03 ≈ 0.084
    En contraste, Moore & Burch daría (0.005 / 0.0896)**1.3 ≈ 0.023, subestimando
    el efecto del impacto de gota en llanura.
    """
    s_05 = compute_usle_s_factor(0.5)
    expected = 10.8 * (0.005 / math.sqrt(1.0 + 0.005**2)) + 0.03
    assert isinstance(s_05, float)
    assert pytest.approx(s_05, rel=1e-4) == expected
    assert pytest.approx(s_05, abs=0.001) == 0.084


def test_usle_s_factor_moderate_slope_3_pct():
    """Valida el factor S a 3.0% de pendiente (ondulado suave).

    Formula McCool et al. (1987) para s < 9%:
        s = 0.03 -> sin(beta) = 0.03 / sqrt(1 + 0.03^2) ≈ 0.0299865
        S = 10.8 * 0.0299865 + 0.03 ≈ 0.354
    """
    s_3 = compute_usle_s_factor(3.0)
    expected = 10.8 * (0.03 / math.sqrt(1.0 + 0.03**2)) + 0.03
    assert isinstance(s_3, float)
    assert pytest.approx(s_3, rel=1e-4) == expected
    assert pytest.approx(s_3, abs=0.001) == 0.354


def test_usle_s_factor_steep_slope_12_pct():
    """Valida el factor S a 12.0% de pendiente (ladera pronunciada >= 9%).

    Formula Moore & Burch (1986) para s >= 9%:
        s = 0.12 -> sin(beta) = 0.12 / sqrt(1 + 0.12^2) ≈ 0.119145
        S = (sin(beta) / 0.0896) ** 1.3 ≈ 1.448
    """
    s_12 = compute_usle_s_factor(12.0)
    sin_beta = 0.12 / math.sqrt(1.0 + 0.12**2)
    expected = (sin_beta / 0.0896) ** 1.3
    assert isinstance(s_12, float)
    assert pytest.approx(s_12, rel=1e-4) == expected
    assert pytest.approx(s_12, abs=0.002) == 1.448


def test_usle_s_factor_continuity_at_9_pct():
    """Verifica que la transición entre McCool (<9%) y Moore & Burch (>=9%) sea casi continua."""
    s_below = compute_usle_s_factor(8.99)
    s_above = compute_usle_s_factor(9.01)

    # Ambos valores deben estar muy cercanos a 1.0 (condición estándar del nomograma a 9%)
    assert pytest.approx(s_below, abs=0.02) == 1.0
    assert pytest.approx(s_above, abs=0.02) == 1.0
    # La diferencia en la frontera debe ser despreciable (< 0.02)
    assert abs(s_above - s_below) < 0.02


def test_usle_s_factor_vectorized_array():
    """Verifica el cálculo vectorizado con arreglos numpy de diferentes pendientes."""
    slopes = np.array([0.5, 3.0, 8.99, 9.0, 12.0, 20.0])
    s_arr = compute_usle_s_factor(slopes)

    assert isinstance(s_arr, np.ndarray)
    assert s_arr.shape == slopes.shape
    assert pytest.approx(s_arr[0], abs=0.001) == 0.084
    assert pytest.approx(s_arr[1], abs=0.001) == 0.354
    assert pytest.approx(s_arr[4], abs=0.002) == 1.448
    # Debe ser estrictamente monótono creciente
    assert np.all(np.diff(s_arr) > 0)


def test_compute_ls_factor_grid_with_mccool():
    """Verifica que compute_ls_factor_grid integre correctamente el nuevo factor S de McCool."""
    rows, cols = 5, 5
    pixel_size = 15.0
    mfd_area = np.full((rows, cols), 450.0, dtype=float)  # 2 celdas de acumulación
    # Celda (0,0) con pendiente 0.5% (McCool), celda (0,1) con 12% (Moore & Burch)
    slopes = np.full((rows, cols), 0.5, dtype=float)
    slopes[0, 1] = 12.0

    ls_grid = compute_ls_factor_grid(mfd_area, slopes, pixel_size_m=pixel_size)

    assert ls_grid.shape == (rows, cols)
    assert np.all(np.isfinite(ls_grid))

    # Celda (0,0): específica = 450 / 15 = 30 m -> L = (30/22.13)^0.4 ≈ 1.130
    # S = 0.084 -> LS ≈ 1.130 * 0.084 ≈ 0.095
    expected_l = (30.0 / 22.13) ** 0.4
    expected_s_05 = compute_usle_s_factor(0.5)
    assert pytest.approx(ls_grid[0, 0], rel=1e-3) == expected_l * expected_s_05

    # Celda (0,1): S(12%) ≈ 1.448 -> LS ≈ 1.130 * 1.448 ≈ 1.636
    expected_s_12 = compute_usle_s_factor(12.0)
    assert pytest.approx(ls_grid[0, 1], rel=1e-3) == expected_l * expected_s_12
