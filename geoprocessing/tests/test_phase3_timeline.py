"""Tests unitarios de Fase 3: simulación temporal por hietograma, sensibilidad al patrón temporal y partículas 3D."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from geoprocessing.dem.terrain import Dem
from geoprocessing.hydrology.flow import d8_direction_and_accumulation, mfd_accumulation
from geoprocessing.rainfall.timeline import (
    extract_3d_flow_particle_paths,
    simulate_temporal_runoff,
)
from geoprocessing.tests.fixtures.synthetic_dem import write_synthetic_inclined_plane_utm


def test_temporal_simulation_mass_balance_and_pattern_sensitivity():
    """Criterio de aceptación SDD §14 Fase 3: la evolución temporal cambia al modificar el hietograma
    (mismo acumulado total de 80 mm, distinto patrón temporal) y conserva balance de masa en cada paso.
    """
    mfd_area = np.full((20, 20), 900.0, dtype="float32")
    mascara = np.ones((20, 20), dtype=bool)

    # Hietograma A: pico temprano (intervalos 1 y 2 concentran la lluvia fuerte)
    early_peak = [
        {"timestamp": f"2026-11-18T14:{15 * i:02d}:00-03:00", "precipitation_mm": p, "interval_minutes": 15}
        for i, p in enumerate([25.0, 30.0, 10.0, 5.0, 4.0, 3.0, 2.0, 1.0])
    ]
    # Hietograma B: pico tardío (mismo total 80 mm, pero concentrado al final)
    late_peak = [
        {"timestamp": f"2026-11-18T14:{15 * i:02d}:00-03:00", "precipitation_mm": p, "interval_minutes": 15}
        for i, p in enumerate([1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 25.0, 30.0])
    ]

    sim_early = simulate_temporal_runoff(
        intervals=early_peak,
        cn_ii_base=82.0,
        antecedent_moisture="medium",
        lambda_ratio=0.2,
        mfd_area_m2=mfd_area,
        mascara_lote=mascara,
        pixel_size_m=30.0,
        mean_slope_pct=2.5,
        depression_volume_in_field_m3=150.0,
        external_inflow_ha=2.0,
        recession_steps=4,
    )
    sim_late = simulate_temporal_runoff(
        intervals=late_peak,
        cn_ii_base=82.0,
        antecedent_moisture="medium",
        lambda_ratio=0.2,
        mfd_area_m2=mfd_area,
        mascara_lote=mascara,
        pixel_size_m=30.0,
        mean_slope_pct=2.5,
        depression_volume_in_field_m3=150.0,
        external_inflow_ha=2.0,
        recession_steps=4,
    )

    assert sim_early["max_mass_balance_error_mm"] < 1e-5
    assert sim_late["max_mass_balance_error_mm"] < 1e-5
    assert sim_early["total_steps"] == 12
    # El pico de tránsito ocurre antes en la tormenta temprana que en la tardía
    assert sim_early["peak_step_index"] < sim_late["peak_step_index"]
    # En el paso 2, la tormenta temprana ya tiene mucho más flujo en tránsito que la tardía
    assert (
        sim_early["frames"][2]["active_transit_lamina_mm"]
        > sim_late["frames"][2]["active_transit_lamina_mm"]
    )


def test_extract_3d_flow_particle_paths_on_inclined_plane(tmp_path: Path):
    tif = write_synthetic_inclined_plane_utm(
        tmp_path / "plane_paths.tif", slope_east=0.03, slope_south=0.04, pixel_m=10.0, width=40, height=40
    )
    dem = Dem.open(tif)
    d8_code, _, _, _ = d8_direction_and_accumulation(dem.z, dem.pixel)
    _, mfd_area, _ = mfd_accumulation(dem.z, dem.pixel)

    paths = extract_3d_flow_particle_paths(dem, d8_code, mfd_area, max_paths=20, min_steps=5)
    assert len(paths) >= 5
    for p in paths:
        assert len(p) >= 5
        # La cota z debe descender a lo largo de toda la trayectoria
        zs = [pt[2] for pt in p]
        assert zs[0] > zs[-1]
