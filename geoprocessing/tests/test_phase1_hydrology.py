"""Tests unitarios de Fase 1 (Hidrología estática): acondicionamiento, D8, MFD, depresiones y curvas."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from geoprocessing.dem.quality import field_mask
from geoprocessing.dem.terrain import Dem, contours_geojson, hillshade
from geoprocessing.fields import parse_geojson
from geoprocessing.hydrology.conditioning import condition_dem
from geoprocessing.hydrology.flow import (
    d8_direction_and_accumulation,
    extract_drainage_network_and_basins,
    mfd_accumulation,
)
from geoprocessing.tests.fixtures.synthetic_dem import (
    synthetic_square_field_geojson,
    write_synthetic_bowl_utm,
    write_synthetic_inclined_plane_utm,
)


def test_d8_and_mfd_on_synthetic_inclined_plane(tmp_path: Path):
    """Plano que sube hacia el este (+3%) y hacia el sur (+4%) -> drena hacia el noroeste (D8=32)."""
    tif = write_synthetic_inclined_plane_utm(
        tmp_path / "plane.tif", slope_east=0.03, slope_south=0.04, pixel_m=10.0, width=50, height=50
    )
    dem = Dem.open(tif)
    mascara = np.ones_like(dem.z, dtype=bool)

    z_cond, sink_d, _, deps = condition_dem(dem, mascara, mode="fill_small")
    assert len(deps) == 0
    assert float(sink_d.max()) == pytest.approx(0.0, abs=1e-4)

    d8_code, d8_az, d8_cells, d8_area = d8_direction_and_accumulation(z_cond, dem.pixel)
    # En el interior (filas > 0, cols > 0), la dirección de máximo descenso es NW (código 32, azimut 315°)
    interior_codes = d8_code[2:-2, 2:-2]
    assert np.all(interior_codes == 32)
    assert np.allclose(d8_az[2:-2, 2:-2], 315.0)
    # La esquina noroeste (0, 0) acumula más celdas que la esquina sureste (-1, -1)
    assert int(d8_cells[0, 0]) > int(d8_cells[-1, -1]) == 1

    mfd_cells, mfd_area, balance = mfd_accumulation(z_cond, dem.pixel, exponent_p=1.1)
    assert balance["relative_error"] < 1e-6
    assert float(mfd_area[0, 0]) > float(mfd_area[-1, -1])


def test_depression_preservation_vs_selective_fill_on_synthetic_bowl(tmp_path: Path):
    """Verifica la regla SDD §6.2: no rellenar bajos grandes a ciegas en 'fill_small' ni en 'preserve'."""
    lote = parse_geojson(synthetic_square_field_geojson())[0]
    tif = write_synthetic_bowl_utm(tmp_path / "bowl.tif", pixel_m=20.0, width=110, height=110)
    dem = Dem.open(tif)
    mascara = field_mask(lote.geometry, lote.utm_epsg, dem.transform, dem.z.shape)

    # 1. Modo 'fill_small' con umbral pequeño (0.35 m, 4500 m²): el gran cuenco NO debe rellenarse
    z_small, sink_d, dep_grid, deps_small = condition_dem(
        dem, mascara, mode="fill_small", max_fill_depth_m=0.35, max_fill_area_m2=4500.0
    )
    assert len(deps_small) == 1
    big_dep = deps_small[0]
    assert big_dep.in_field is True
    assert big_dep.max_depth_m > 5.0
    assert big_dep.is_spurious_candidate is False
    assert big_dep.filled_in_run is False
    assert np.allclose(z_small, dem.z)

    # En el fondo del cuenco sin rellenar debe haber un sumidero interno (d8_code == 0)
    d8_code, _, _, d8_area = d8_direction_and_accumulation(z_small, dem.pixel)
    mfd_cells, mfd_area, balance = mfd_accumulation(z_small, dem.pixel)
    assert balance["relative_error"] < 1e-6
    mid = dem.z.shape[0] // 2
    assert int(d8_code[mid, mid]) == 0

    # 2. Modo 'fill_all': fuerza el relleno completo del cuenco para continuidad regional
    z_all, _, _, deps_all = condition_dem(dem, mascara, mode="fill_all")
    assert deps_all[0].filled_in_run is True
    d8_code_filled, _, _, _ = d8_direction_and_accumulation(z_all, dem.pixel)
    assert int(d8_code_filled[mid, mid]) != 0

    # 3. Extracción de red de drenaje y salidas
    net, subbasins, outlets = extract_drainage_network_and_basins(
        dem, mascara, d8_code, d8_area, mfd_area, threshold_ha=1.0, routing_basis="MFD"
    )
    assert len(net["features"]) > 0
    assert len(outlets) >= 1
    assert int(subbasins.max()) >= 1


def test_hillshade_and_contours_on_inclined_plane(tmp_path: Path):
    tif = write_synthetic_inclined_plane_utm(
        tmp_path / "plane_contours.tif", slope_east=0.04, slope_south=0.03, pixel_m=10.0, width=60, height=60
    )
    dem = Dem.open(tif)
    hs = hillshade(dem.z, dem.pixel, dem.pixel)
    interior_hs = hs[1:-1, 1:-1]
    assert np.isfinite(interior_hs).all()
    assert 0.0 <= float(interior_hs.min()) <= float(interior_hs.max()) <= 1.0

    ct = contours_geojson(dem, interval_m=5.0)
    assert ct["interval_m"] == 5.0
    assert len(ct["features"]) >= 4
    first_elev = ct["features"][0]["properties"]["elevation_m"]
    assert first_elev % 5.0 == pytest.approx(0.0)
