"""Tests unitarios de Fase 4 (Solver 2D Manning), Fase 5 (Zonificación RotaTerra), TWI/SPI e importación KML."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from geoprocessing.agronomy.zonation import classify_hydro_agronomic_zones
from geoprocessing.dem.quality import field_mask
from geoprocessing.dem.terrain import Dem, slope_aspect
from geoprocessing.fields import parse_field_file, parse_geojson
from geoprocessing.hydrology.conditioning import condition_dem
from geoprocessing.hydrology.flow import mfd_accumulation
from geoprocessing.hydrology.indices import compute_twi_and_spi
from geoprocessing.hydrology.shallow_water_2d import run_2d_diffusive_wave_simulation
from geoprocessing.tests.fixtures.synthetic_dem import (
    synthetic_square_field_geojson,
    write_synthetic_bowl_utm,
)


def test_parse_kml_polygon():
    kml = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>
        <Placemark>
          <name>Lote KML San Luis</name>
          <Polygon>
            <outerBoundaryIs>
              <LinearRing>
                <coordinates>
                  -65.7000,-33.3000,0 -65.6900,-33.3000,0 -65.6900,-33.2900,0 -65.7000,-33.2900,0 -65.7000,-33.3000,0
                </coordinates>
              </LinearRing>
            </outerBoundaryIs>
          </Polygon>
        </Placemark>
      </Document>
    </kml>"""
    lotes = parse_field_file(kml.encode("utf-8"), filename="lote.kml")
    assert len(lotes) == 1
    assert lotes[0].name == "Lote KML San Luis"
    assert lotes[0].utm_epsg == 32720
    assert lotes[0].area_ha > 90.0


def test_twi_spi_and_phase5_zonation_on_synthetic_bowl(tmp_path: Path):
    lote = parse_geojson(synthetic_square_field_geojson())[0]
    tif = write_synthetic_bowl_utm(tmp_path / "bowl_z.tif", pixel_m=20.0, width=90, height=90)
    dem = Dem.open(tif)
    mascara = field_mask(lote.geometry, lote.utm_epsg, dem.transform, dem.z.shape)
    z_cond, sink_d, _, _ = condition_dem(dem, mascara, mode="preserve")
    _, mfd_area, _ = mfd_accumulation(z_cond, dem.pixel)
    pct, _, _ = slope_aspect(dem.z, dem.pixel, dem.pixel)

    twi, spi = compute_twi_and_spi(mfd_area, pct, dem.pixel)
    mid = dem.z.shape[0] // 2
    # En el centro del cuenco (baja pendiente, alta acumulación) el TWI es mayor que en el borde alto
    assert float(twi[mid, mid]) > float(twi[5, 5])

    zone_grid, agro = classify_hydro_agronomic_zones(
        z=dem.z,
        slope_pct=pct,
        sink_depth_m=sink_d,
        twi=twi,
        spi=spi,
        mascara_lote=mascara,
        pixel_size_m=dem.pixel,
        soil_group="C",
    )
    # El centro del cuenco debe quedar clasificado como Ambiente 4 (Bajo receptor / anegable)
    assert int(zone_grid[mid, mid]) == 4
    assert len(agro["zones"]) == 4
    assert agro["trafficability"]["risk_level"] in ("moderado", "alto")


def test_phase4_2d_diffusive_wave_solver_mass_balance_and_ponding(tmp_path: Path):
    lote = parse_geojson(synthetic_square_field_geojson())[0]
    tif = write_synthetic_bowl_utm(tmp_path / "bowl_2d.tif", pixel_m=25.0, width=60, height=60)
    dem = Dem.open(tif)
    mascara = field_mask(lote.geometry, lote.utm_epsg, dem.transform, dem.z.shape)

    intervals = [
        {"timestamp": "2026-11-18T14:00:00-03:00", "precipitation_mm": 25.0, "interval_minutes": 15},
        {"timestamp": "2026-11-18T14:15:00-03:00", "precipitation_mm": 35.0, "interval_minutes": 15},
        {"timestamp": "2026-11-18T14:30:00-03:00", "precipitation_mm": 20.0, "interval_minutes": 15},
    ]

    sim2d = run_2d_diffusive_wave_simulation(
        dem=dem,
        z_cond=dem.z,
        mascara_lote=mascara,
        intervals=intervals,
        cn_ii_base=84.0,
        antecedent_moisture="wet",
        lambda_ratio=0.2,
        manning_n=0.08,
        ponding_threshold_m=0.05,
        recession_minutes=15,
    )
    s = sim2d["summary"]
    assert s["mass_balance_relative_error"] < 1e-4
    assert s["max_water_depth_in_field_m"] > 0.05
    assert s["max_velocity_in_field_m_s"] > 0.0
    assert s["ponded_area_in_field_ha"] > 0.0
    mid = dem.z.shape[0] // 2
    # El fondo del cuenco acumula mayor profundidad de agua que el borde exterior
    assert float(sim2d["max_water_depth_m"][mid, mid]) > float(sim2d["max_water_depth_m"][2, 2])
