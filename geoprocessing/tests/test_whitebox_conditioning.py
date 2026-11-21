"""Pruebas de acondicionamiento de relieve para llanura con WhiteboxTools (Spec 005).

Criterios:
1. Relieve sintético con ruido: la pendiente media tras suavizado se aproxima a la real (diferencia < 20%).
2. Depresión artificial de 0.3 m en plano inclinado: se resuelve con brecha y no como laguna plana.
3. La grilla del motor 2D no se modifica con el acondicionamiento (arquitectura de dos grillas).
4. Tests sin internet.
"""

from __future__ import annotations

import numpy as np
import pytest
from rasterio.transform import from_origin

from geoprocessing.dem.terrain import Dem, slope_aspect
from geoprocessing.hydrology.conditioning import (
    condition_dem,
    is_whitebox_available,
    priority_flood_fill,
    whitebox_breach_and_smooth,
)
from geoprocessing.hydrology.shallow_water_2d import run_2d_diffusive_wave_simulation

# El paquete `whitebox` descarga su programa la primera vez: sin internet ni binario instalado,
# estos tests se saltean (regla: ningún test depende de internet). En GitHub se instala antes.
requiere_whitebox = pytest.mark.skipif(
    not is_whitebox_available(), reason="WhiteboxTools no instalado (sin binario local)"
)


def _create_synthetic_dem(z_arr: np.ndarray, pixel: float = 10.0) -> Dem:
    ny, nx = z_arr.shape
    transform = from_origin(500_000.0, 6_000_000.0, pixel, pixel)
    return Dem(
        z=z_arr.astype("float32"),
        transform=transform,
        crs="EPSG:32720",
    )


@requiere_whitebox
def test_whitebox_is_available():
    assert is_whitebox_available() is True, "WhiteboxTools debe estar instalado y disponible."


@requiere_whitebox
def test_feature_preserving_smoothing_restores_true_slope():
    """Criterio 1: Un plano con ruido satelital recupera su pendiente real tras FPS (diferencia < 20%)."""
    nx, ny = 60, 60
    pixel = 10.0
    x = np.arange(nx) * pixel
    xx, _ = np.meshgrid(x, np.arange(ny) * pixel)
    true_z = (100.0 + 0.01 * xx).astype("float32")  # 1.0% de pendiente teórica

    # Ruido gaussiano simulando instrumental satelital (std 0.12 m)
    np.random.seed(42)
    noisy_z = true_z + np.random.normal(0, 0.12, size=true_z.shape).astype("float32")

    dem = _create_synthetic_dem(noisy_z, pixel=pixel)

    slope_true, _, _ = slope_aspect(true_z, pixel, pixel)
    slope_noisy, _, _ = slope_aspect(noisy_z, pixel, pixel)
    true_mean_slope = float(slope_true[10:-10, 10:-10].mean())
    noisy_mean_slope = float(slope_noisy[10:-10, 10:-10].mean())

    # La pendiente en el ruidoso está inflada artificialmente
    assert noisy_mean_slope > true_mean_slope

    smoothed_z = whitebox_breach_and_smooth(
        dem=dem,
        z=noisy_z,
        filter_size=11,
        norm_diff=12.0,
    )

    slope_smooth, _, _ = slope_aspect(smoothed_z, pixel, pixel)
    smooth_mean_slope = float(slope_smooth[10:-10, 10:-10].mean())

    diff_pct = abs(smooth_mean_slope - true_mean_slope) / true_mean_slope * 100.0
    # Criterio: diferencia < 20%
    assert diff_pct < 20.0, f"Diferencia {diff_pct:.2f}% supera el umbral del 20%."


@requiere_whitebox
def test_breach_resolves_depression_without_flat_lake():
    """Criterio 2: Depresión artificial de 0.3 m en plano inclinado se resuelve abriendo brecha."""
    nx, ny = 40, 40
    pixel = 10.0
    x = np.arange(nx) * pixel
    xx, _ = np.meshgrid(x, np.arange(ny) * pixel)
    plane_z = (100.0 - 0.01 * xx).astype("float32")  # Pendiente descendente al este (1.0%)

    # Crear una depresión de 0.3 m en el interior
    z = plane_z.copy()
    z[18:22, 18:22] -= 0.30

    dem = _create_synthetic_dem(z, pixel=pixel)

    # 1. Con Priority-Flood (relleno tradicional crea laguna plana con pendiente ~0)
    z_filled = priority_flood_fill(z, eps=1e-4)
    s_fill, _, _ = slope_aspect(z_filled, pixel, pixel)
    # En el fondo de la laguna rellena la pendiente cae prácticamente a 0
    flat_cells_filled = int(np.sum(s_fill[18:22, 18:22] < 0.01))
    assert flat_cells_filled > 0, "El relleno puro debe generar celdas planas (laguna plana)."

    # 2. Con Whitebox en modo breach
    mascara = np.ones((ny, nx), dtype=bool)
    z_breached, _, _, _ = condition_dem(dem, mascara, mode="breach")
    s_breach, _, _ = slope_aspect(z_breached, pixel, pixel)

    # En breach se talla el canal hacia el vertedero
    cells_carved = int(np.sum(z_breached < z - 0.001))
    assert cells_carved > 0, "El modo breach debe abrir un canal de desagüe rebajando el borde."

    # No se genera laguna plana: la pendiente se mantiene cercana al gradiente regional
    flat_cells_breached = int(np.sum(s_breach[18:22, 18:22] < 0.01))
    assert flat_cells_breached == 0, "El modo breach no debe dejar celdas planas en la depresión."
    assert float(s_breach[18:22, 18:22].mean()) > 0.5


def test_two_grids_architecture_2d_solver_keeps_original_terrain():
    """Criterio 3: La grilla del motor 2D no se modifica con el acondicionamiento (Spec 005 §2)."""
    nx, ny = 30, 30
    pixel = 10.0
    x = np.arange(nx) * pixel
    xx, _ = np.meshgrid(x, np.arange(ny) * pixel)
    plane_z = (100.0 - 0.01 * xx).astype("float32")

    # Bajo o depresión real en el lote
    z_raw = plane_z.copy()
    z_raw[12:18, 12:18] -= 0.40

    dem = _create_synthetic_dem(z_raw, pixel=pixel)
    mascara = np.ones((ny, nx), dtype=bool)

    # Acondicionamos en modo breach o fill_all para ruteo hidrológico
    z_cond, _, _, _ = condition_dem(dem, mascara, mode="fill_all")
    assert not np.array_equal(z_cond, z_raw)

    intervals = [
        {"timestamp": "2026-11-21T10:00:00-03:00", "precipitation_mm": 40.0, "interval_minutes": 15},
    ]

    # Ejecutar solver 2D pasando dem (que contiene z_raw en dem.z)
    sim2d = run_2d_diffusive_wave_simulation(
        dem=dem,
        z_cond=z_cond,
        mascara_lote=mascara,
        intervals=intervals,
        cn_ii_base=80.0,
        antecedent_moisture="medium",
        lambda_ratio=0.2,
        manning_n=0.08,
    )

    # El solver 2D debe acumular agua en el bajo real (profundidad en el bajo > fuera de él)
    depth_in_sink = float(sim2d["max_water_depth_m"][15, 15])
    depth_outside = float(sim2d["max_water_depth_m"][5, 5])

    assert depth_in_sink > depth_outside
    assert depth_in_sink > 0.005


def test_breach_without_whitebox_falls_back_to_fill_small(monkeypatch):
    """Sin WhiteboxTools, el modo 'breach' se comporta como 'fill_small' (no rellena todo en silencio)."""
    from geoprocessing.hydrology import conditioning

    monkeypatch.setattr(conditioning, "is_whitebox_available", lambda: False)
    nx, ny = 30, 30
    xx, _ = np.meshgrid(np.arange(nx) * 10.0, np.arange(ny) * 10.0)
    z = (100.0 - 0.01 * xx).astype("float32")
    z[12:18, 12:18] -= 0.60  # bajo real, más profundo que el umbral de relleno pequeño
    dem = _create_synthetic_dem(z)
    mascara = np.ones((ny, nx), dtype=bool)
    z_breach, *_ = conditioning.condition_dem(dem, mascara, mode="breach")
    z_small, *_ = conditioning.condition_dem(dem, mascara, mode="fill_small")
    np.testing.assert_array_equal(z_breach, z_small)


def test_whitebox_unavailable_when_binary_file_is_missing(monkeypatch, tmp_path):
    """Caso real de CI (21/11/2026): la caché restauró `whitebox/WBT/` pero no el ejecutable
    `whitebox/whitebox_tools`. El paquete no vuelve a descargar y las corridas fallan con
    `./whitebox_tools: No such file or directory`. La verificación debe mirar el archivo."""
    import sys
    import types

    from geoprocessing.hydrology import conditioning

    class WbtSinBinario:
        exe_path = str(tmp_path)
        exe_name = "whitebox_tools"

        def feature_preserving_smoothing(self, *a, **k):
            return 0

        def breach_depressions_least_cost(self, *a, **k):
            return 0

    falso = types.ModuleType("whitebox")
    falso.WhiteboxTools = WbtSinBinario
    monkeypatch.setitem(sys.modules, "whitebox", falso)
    conditioning.is_whitebox_available.cache_clear()
    try:
        assert conditioning.is_whitebox_available() is False

        binario = tmp_path / "whitebox_tools"
        binario.write_text("")
        binario.chmod(0o755)
        conditioning.is_whitebox_available.cache_clear()
        assert conditioning.is_whitebox_available() is True
    finally:
        conditioning.is_whitebox_available.cache_clear()
