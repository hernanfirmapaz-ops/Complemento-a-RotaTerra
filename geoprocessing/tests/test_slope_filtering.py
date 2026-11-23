"""Tests de pendiente filtrada y ajuste de plano para hidrología (Paso 2 / Spec 014).

Criterios de aceptación (Auditoría de relieve):
1. Test con DEM sintético: plano inclinado al 0,4 % + ruido gaussiano de sigma 1 m.
   La pendiente filtrada tiene que dar 0,4 % ± 0,15. La cruda tiene que dar bastante más;
   dejarlo asertado para documentar el problema de sobrestimación en llanura.
2. Ajuste de plano sobre el lote por mínimos cuadrados (FAO T0231E ec. 117):
   recupera la pendiente macroscópica y orientación del lote con R² alto.
3. Fallback de ventana móvil cuando WhiteboxTools no está disponible.
"""

from __future__ import annotations

import numpy as np
import pytest
from affine import Affine

from geoprocessing.dem.terrain import (
    Dem,
    fit_plane_to_field,
    slope_aspect,
    slope_for_hydrology,
)


@pytest.fixture
def synthetic_noisy_plain_dem():
    """DEM sintético de llanura: plano inclinado al 0.4 % hacia el Este + ruido gaussiano sigma 1.0 m."""
    pixel_m = 25.0
    width, height = 120, 120
    x = np.arange(width) * pixel_m
    y = np.arange(height) * pixel_m
    xx, _ = np.meshgrid(x, y)

    slope_real = 0.004  # 0.4 %
    z_true = (100.0 + slope_real * xx).astype("float32")

    np.random.seed(42)
    noise = np.random.normal(0, 1.0, size=z_true.shape).astype("float32")
    z_noisy = z_true + noise

    transform = Affine(pixel_m, 0.0, 500000.0, 0.0, -pixel_m, 6000000.0)
    dem = Dem(z=z_noisy, transform=transform, crs="EPSG:32720")
    mask = np.zeros((height, width), dtype=bool)
    mask[20:-20, 20:-20] = True
    return dem, z_true, mask, pixel_m


def test_slope_filtering_mitigates_noise(synthetic_noisy_plain_dem):
    """Criterio 1: Pendiente filtrada da 0,4 % ± 0,15 en plano con ruido sigma 1 m, y la cruda es mucho mayor."""
    dem, z_true, mask, pixel_m = synthetic_noisy_plain_dem

    # 1. Pendiente cruda celda a celda (Horn sobre DEM sin filtrar)
    pct_raw, _, _ = slope_aspect(dem.z, pixel_m, pixel_m)
    raw_inner = pct_raw[mask & np.isfinite(pct_raw)]
    mean_raw = float(raw_inner.mean())

    # 2. Pendiente filtrada para hidrología
    pct_filtered, _, _ = slope_for_hydrology(dem)
    filtered_inner = pct_filtered[mask & np.isfinite(pct_filtered)]
    mean_filtered = float(filtered_inner.mean())

    # Documentar el problema de sobrestimación en llanura:
    # El ruido satelital de ±1 m infla la pendiente cruda varias veces (en este caso > 2.0 %)
    assert mean_raw > 2.0, f"La pendiente cruda {mean_raw:.2f}% debe ser bastante mayor que 0.4 %"
    assert mean_raw > 3.0 * mean_filtered, (
        f"La pendiente cruda ({mean_raw:.2f}%) debe triplicar al menos la filtrada ({mean_filtered:.2f}%)"
    )

    # La pendiente filtrada debe converger a 0,4 % ± 0,15 (entre 0,25 % y 0,55 %)
    assert 0.25 <= mean_filtered <= 0.55, (
        f"La pendiente filtrada {mean_filtered:.3f}% no cayó dentro de 0,4 % ± 0,15 (rango [0.25, 0.55])"
    )


def test_fit_plane_to_field_exact_on_pure_plane():
    """Criterio 2: Plano ajustado sobre un plano sintético perfecto recupera exactamente 0,40 % y R² = 1,00."""
    pixel_m = 10.0
    width, height = 80, 80
    x = np.arange(width) * pixel_m
    y = np.arange(height) * pixel_m
    xx, yy = np.meshgrid(x, y)

    # Inclinación 0.4 % hacia el Este
    z = (150.0 + 0.004 * xx).astype("float32")
    transform = Affine(pixel_m, 0.0, 500000.0, 0.0, -pixel_m, 6000000.0)
    dem = Dem(z=z, transform=transform, crs="EPSG:32720")
    mask = np.ones((height, width), dtype=bool)

    plane_res = fit_plane_to_field(dem, mask)
    assert plane_res["slope_pct"] == pytest.approx(0.4, abs=1e-3)
    assert plane_res["r_squared"] == pytest.approx(1.0, abs=1e-3)
    assert plane_res["aspect_deg"] == pytest.approx(270.0, abs=1.0)  # drena hacia el Oeste
    assert "0,4 %" in plane_res["description"]
    assert "plano ajustado R² = 1,00" in plane_res["description"]


def test_fit_plane_to_field_with_noise(synthetic_noisy_plain_dem):
    """Criterio 2b: En presencia de ruido gaussiano 1 m, el plano ajustado recupera la pendiente macroscópica."""
    dem, _, mask, _ = synthetic_noisy_plain_dem

    plane_res = fit_plane_to_field(dem, mask)
    # Debe estimar la pendiente macroscópica muy cerca de 0.4 %
    assert 0.35 <= plane_res["slope_pct"] <= 0.45, f"Pendiente del plano {plane_res['slope_pct']}% alejada de 0.4%"
    assert plane_res["r_squared"] > 0.0


def test_moving_plane_slope_fallback(synthetic_noisy_plain_dem, monkeypatch):
    """Criterio 3: El fallback de ventana móvil opera correctamente cuando Whitebox no está disponible."""
    dem, _, mask, pixel_m = synthetic_noisy_plain_dem

    # Forzar que is_whitebox_available() devuelva False
    import geoprocessing.hydrology.conditioning as cond
    monkeypatch.setattr(cond, "is_whitebox_available", lambda: False)

    pct_fb, _, _ = slope_for_hydrology(dem, fallback_window=9)
    fb_inner = pct_fb[mask & np.isfinite(pct_fb)]
    mean_fb = float(fb_inner.mean())

    assert 0.25 <= mean_fb <= 0.55, f"Fallback de ventana móvil {mean_fb:.3f}% fuera de 0,4 % ± 0,15"


def test_fit_plane_to_field_empty_or_nan_returns_null_and_descartada():
    """Valida que fit_plane_to_field devuelva null y calidad 'descartada' si no hay celdas válidas."""
    pixel_m = 10.0
    z = np.full((10, 10), np.nan, dtype="float32")
    transform = Affine(pixel_m, 0.0, 500000.0, 0.0, -pixel_m, 6000000.0)
    dem = Dem(z=z, transform=transform, crs="EPSG:32720")
    mask = np.ones((10, 10), dtype=bool)

    res = fit_plane_to_field(dem, mask)
    assert res["slope_pct"] is None
    assert res["r_squared"] is None
    assert res["aspect_deg"] is None
    assert res["z_mean_m"] is None
    assert res["calidad"] == "descartada"

    # Máscara vacía (ninguna celda en el lote)
    z_valid = np.full((10, 10), 100.0, dtype="float32")
    dem_valid = Dem(z=z_valid, transform=transform, crs="EPSG:32720")
    res_empty = fit_plane_to_field(dem_valid, np.zeros((10, 10), dtype=bool))
    assert res_empty["slope_pct"] is None
    assert res_empty["r_squared"] is None
    assert res_empty["calidad"] == "descartada"


def test_fit_plane_to_field_insufficient_cells_returns_descartada():
    """Con menos de 3 celdas, el plano es indeterminado y devuelve calidad 'descartada'."""
    pixel_m = 10.0
    z = np.full((10, 10), 100.0, dtype="float32")
    transform = Affine(pixel_m, 0.0, 500000.0, 0.0, -pixel_m, 6000000.0)
    dem = Dem(z=z, transform=transform, crs="EPSG:32720")
    mask = np.zeros((10, 10), dtype=bool)
    mask[1, 1] = True
    mask[1, 2] = True  # solo 2 celdas

    res = fit_plane_to_field(dem, mask)
    assert res["slope_pct"] is None
    assert res["r_squared"] is None
    assert res["calidad"] == "descartada"


def test_fit_plane_to_field_zero_variance_flat_plane():
    """En un plano perfectamente horizontal (sin varianza altimétrica, ss_tot = 0), r_squared es None."""
    pixel_m = 10.0
    z = np.full((20, 20), 120.0, dtype="float32")
    transform = Affine(pixel_m, 0.0, 500000.0, 0.0, -pixel_m, 6000000.0)
    dem = Dem(z=z, transform=transform, crs="EPSG:32720")
    mask = np.ones((20, 20), dtype=bool)

    res = fit_plane_to_field(dem, mask)
    assert res["slope_pct"] == 0.0
    assert res["r_squared"] is None
    assert res["calidad"] == "confiable"
    assert "sin varianza altimétrica" in res["description"]

