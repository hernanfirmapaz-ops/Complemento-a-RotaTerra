"""Pruebas de aceleración con Numba y equivalencia estricta con Python puro (Parte 2.2).

Verifica:
1. La acumulación de flujo MFD produce resultados numéricamente equivalentes con Numba y en Python puro.
2. La simulación 2D de aguas someras (onda difusiva con Manning) produce resultados equivalentes (dif < 1e-6 m).
3. Si Numba no está disponible o se deshabilita, el sistema continúa funcionando en Python puro.
"""

from __future__ import annotations

import numpy as np
from rasterio.transform import from_origin

import geoprocessing.hydrology.flow as flow_mod
import geoprocessing.hydrology.shallow_water_2d as sw2d_mod
from geoprocessing.dem.terrain import Dem
from geoprocessing.hydrology.flow import mfd_accumulation
from geoprocessing.hydrology.shallow_water_2d import run_2d_diffusive_wave_simulation


def _create_synthetic_dem(z_arr: np.ndarray, pixel: float = 10.0) -> Dem:
    transform = from_origin(500_000.0, 6_000_000.0, pixel, pixel)
    return Dem(
        z=z_arr.astype("float32"),
        transform=transform,
        crs="EPSG:32720",
    )


def test_mfd_numba_vs_pure_python_identical():
    """Verifica que el ruteo MFD con Numba produce resultados idénticos al bucle de Python puro."""
    ny, nx = 40, 40
    y, x = np.mgrid[:ny, :nx]
    z = (200.0 - 0.05 * x - 0.03 * y + 0.1 * np.sin(x / 3.0)).astype("float32")

    # Ejecutar con Numba
    orig_numba = flow_mod._HAS_NUMBA
    try:
        flow_mod._HAS_NUMBA = True
        cells_numba, area_numba, bal_numba = mfd_accumulation(z, pixel_size_m=10.0, exponent_p=1.1)

        # Ejecutar en Python puro
        flow_mod._HAS_NUMBA = False
        cells_py, area_py, bal_py = mfd_accumulation(z, pixel_size_m=10.0, exponent_p=1.1)
    finally:
        flow_mod._HAS_NUMBA = orig_numba

    max_diff_cells = np.nanmax(np.abs(cells_numba - cells_py))
    max_diff_area = np.nanmax(np.abs(area_numba - area_py))

    assert max_diff_cells < 1e-6, f"Diferencia en celdas MFD excede umbral: {max_diff_cells}"
    assert max_diff_area < 1e-4, f"Diferencia en área MFD excede umbral: {max_diff_area}"
    assert abs(bal_numba["total_outlet_area_ha"] - bal_py["total_outlet_area_ha"]) < 1e-4


def test_shallow_water_2d_numba_vs_pure_python_identical():
    """Verifica que el solver 2D con Numba produce profundidades idénticas (< 1e-6 m) a Python puro."""
    ny, nx = 25, 25
    y, x = np.mgrid[:ny, :nx]
    z = (100.0 - 0.02 * x - 0.01 * y).astype("float32")
    z[10:14, 10:14] -= 0.25  # Depresión controlada
    mask = np.ones((ny, nx), dtype=bool)
    dem = _create_synthetic_dem(z, pixel=10.0)

    intervals = [
        {"interval_minutes": 15, "precipitation_mm": 20.0},
        {"interval_minutes": 15, "precipitation_mm": 10.0},
    ]

    orig_numba = sw2d_mod._HAS_NUMBA
    try:
        # 1. Con Numba
        sw2d_mod._HAS_NUMBA = True
        res_numba = run_2d_diffusive_wave_simulation(
            dem=dem,
            z_cond=z,
            mascara_lote=mask,
            intervals=intervals,
            cn_ii_base=75.0,
            antecedent_moisture="medium",
            lambda_ratio=0.2,
            manning_n=0.08,
            recession_minutes=15,
        )

        # 2. En Python puro
        sw2d_mod._HAS_NUMBA = False
        res_py = run_2d_diffusive_wave_simulation(
            dem=dem,
            z_cond=z,
            mascara_lote=mask,
            intervals=intervals,
            cn_ii_base=75.0,
            antecedent_moisture="medium",
            lambda_ratio=0.2,
            manning_n=0.08,
            recession_minutes=15,
        )
    finally:
        sw2d_mod._HAS_NUMBA = orig_numba

    diff_max_h = np.nanmax(np.abs(res_numba["max_water_depth_m"] - res_py["max_water_depth_m"]))
    diff_final_h = np.nanmax(np.abs(res_numba["final_water_depth_m"] - res_py["final_water_depth_m"]))

    assert diff_max_h < 1e-6, f"Diferencia en max_h ({diff_max_h}) excede criterio 1e-6 m"
    assert diff_final_h < 1e-6, f"Diferencia en final_h ({diff_final_h}) excede criterio 1e-6 m"
    assert abs(res_numba["summary"]["ponded_area_in_field_ha"] - res_py["summary"]["ponded_area_in_field_ha"]) < 1e-4


def test_fallback_when_numba_not_available(monkeypatch):
    """Verifica que ante ausencia de Numba todo el flujo opera normalmente en Python puro."""
    monkeypatch.setattr(flow_mod, "_HAS_NUMBA", False)
    monkeypatch.setattr(sw2d_mod, "_HAS_NUMBA", False)

    ny, nx = 20, 20
    y, x = np.mgrid[:ny, :nx]
    z = (100.0 - 0.01 * x - 0.01 * y).astype("float32")
    mask = np.ones((ny, nx), dtype=bool)
    dem = _create_synthetic_dem(z, pixel=10.0)

    # Acumulación MFD funciona sin error
    cells, area, bal = mfd_accumulation(z, pixel_size_m=10.0)
    assert np.isfinite(cells).all()

    # Solver 2D funciona sin error
    res = run_2d_diffusive_wave_simulation(
        dem=dem,
        z_cond=z,
        mascara_lote=mask,
        intervals=[{"interval_minutes": 15, "precipitation_mm": 60.0}],
        cn_ii_base=80.0,
        antecedent_moisture="wet",
        lambda_ratio=0.2,
    )
    assert res["summary"]["domain_input_volume_m3"] > 0.0
