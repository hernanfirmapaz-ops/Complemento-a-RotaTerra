"""Pruebas de umbrales de depresión y encharcamiento según error del DEM (Paso 3 / SDD §6.2).

Verifica:
1. Umbrales de acondicionamiento hidrológico (max_fill_depth_m, max_fill_area_m2, min_depression_depth_m)
   tomados como supuestos metodológicos calibrables desde geoprocessing.supuestos.
2. Clasificación de depresiones: las de profundidad menor al umbral de precisión vertical (1 × NMAD, 1,1 m
   por defecto) se marcan como "no distinguibles del error del DEM", no suman al volumen/área anegable real
   ni se dibujan como bajo real.
3. Advertencia en QualityReport cuando más del 50% de las depresiones detectadas son artefactos potenciales.
4. Registro del modo de condicionamiento aplicado ('breach' o 'fill_small') en informe y parámetros.
"""

from __future__ import annotations

import numpy as np
from rasterio.transform import from_origin

from geoprocessing import supuestos
from geoprocessing.dem.quality import check_depression_artifacts
from geoprocessing.dem.terrain import Dem
from geoprocessing.hydrology.conditioning import condition_dem


def _make_dem(z: np.ndarray, pixel: float = 10.0) -> Dem:
    ny, nx = z.shape
    transform = from_origin(500_000.0, 6_000_000.0, pixel, pixel)
    return Dem(z=z.astype("float32"), transform=transform, crs="EPSG:32720")


def test_depression_thresholds_defaults_from_supuestos():
    """Valida que los valores por omisión de condition_dem provienen de geoprocessing.supuestos."""
    assert supuestos.SUPUESTO_DEPRESION_MAX_FILL_DEPTH_M.valor == 0.35
    assert supuestos.SUPUESTO_DEPRESION_MAX_FILL_AREA_M2.valor == 4500.0
    assert supuestos.SUPUESTO_DEPRESION_MIN_DEPTH_M.valor == 0.05
    assert supuestos.SUPUESTO_DEPRESION_ACCURACY_NMAD_M.valor == 1.15


def test_depressions_distinguishability_against_vertical_accuracy():
    """Depresiones con profundidad < 1 × NMAD se clasifican como no distinguibles del error."""
    nx, ny = 40, 40
    pixel = 10.0
    # Plano suave con pendiente general hacia el Este
    x = np.arange(nx) * pixel
    xx, _ = np.meshgrid(x, np.arange(ny) * pixel)
    z = (100.0 - 0.01 * xx).astype("float32")

    # Depresión 1: profundidad 0.5 m (< 1.15 m de Copernicus NMAD)
    z[10:15, 10:15] -= 0.50

    # Depresión 2: profundidad 1.8 m (>= 1.15 m, bajo real distinguible)
    z[25:32, 25:32] -= 1.80

    dem = _make_dem(z, pixel=pixel)
    mascara = np.ones((ny, nx), dtype=bool)

    # Ejecutar con precisión vertical de 1.15 m
    z_cond, sink_depth_m, dep_id_grid, depressions = condition_dem(
        dem,
        mascara,
        mode="preserve",
        vertical_accuracy_m=1.15,
    )

    assert len(depressions) == 2
    # Ordenadas por volumen (la de 1.8 m es mayor)
    dep_real = next(d for d in depressions if d.max_depth_m > 1.0)
    dep_art = next(d for d in depressions if d.max_depth_m < 1.0)

    assert dep_real.is_real is True
    assert dep_real.classification == "real"

    assert dep_art.is_real is False
    assert dep_art.classification == "no_distinguible_del_error_dem"


def test_quality_report_warning_when_majority_of_depressions_are_below_error_threshold():
    """Genera QualityWarning con código 'depresiones_artefacto_dem' si > 50% de depresiones son menores al umbral."""
    nx, ny = 50, 50
    pixel = 10.0
    xx, _ = np.meshgrid(np.arange(nx) * pixel, np.arange(ny) * pixel)
    z = (100.0 - 0.01 * xx).astype("float32")

    # Crear 3 depresiones: 2 chicas (0.4 m, 0.6 m) y 1 grande (2.0 m)
    z[5:9, 5:9] -= 0.40
    z[15:19, 15:19] -= 0.60
    z[30:38, 30:38] -= 2.00

    dem = _make_dem(z, pixel=pixel)
    mascara = np.ones((ny, nx), dtype=bool)

    _, _, _, depressions = condition_dem(dem, mascara, mode="preserve", vertical_accuracy_m=1.15)
    assert len(depressions) == 3

    # 2 de 3 (< 1.15 m) -> 66.7% > 50%: debe disparar el warning
    warn = check_depression_artifacts(depressions, vertical_accuracy_m=1.15, source_name="Copernicus DEM GLO-30 (ESA)")
    assert warn is not None
    assert warn.code == "depresiones_artefacto_dem"
    assert warn.level == "advertencia"
    assert "2 depresiones de 3 (<1.15 m) podrían ser artefactos del DEM Copernicus (error vertical ±1.15 m)" in warn.message


def test_quality_report_no_warning_when_minority_are_below_error():
    """No genera advertencia si las depresiones dudosas son <= 50%."""
    nx, ny = 50, 50
    pixel = 10.0
    xx, _ = np.meshgrid(np.arange(nx) * pixel, np.arange(ny) * pixel)
    z = (100.0 - 0.01 * xx).astype("float32")

    # 1 chica (0.4 m) y 2 grandes (1.5 m, 2.0 m)
    z[5:9, 5:9] -= 0.40
    z[15:23, 15:23] -= 1.50
    z[30:38, 30:38] -= 2.00

    dem = _make_dem(z, pixel=pixel)
    mascara = np.ones((ny, nx), dtype=bool)

    _, _, _, depressions = condition_dem(dem, mascara, mode="preserve", vertical_accuracy_m=1.15)
    assert len(depressions) == 3

    # 1 de 3 (< 1.15 m) -> 33.3% <= 50%: no dispara warning
    warn = check_depression_artifacts(depressions, vertical_accuracy_m=1.15, source_name="Copernicus")
    assert warn is None
