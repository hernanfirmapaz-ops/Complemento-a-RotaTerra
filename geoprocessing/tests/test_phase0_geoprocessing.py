"""Tests unitarios de geoprocesamiento (Fase 0): CRS, validación de lotes, pendiente, perfil y calidad."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from rasterio.transform import from_origin

from geoprocessing.crs import utm_epsg
from geoprocessing.dem.prepare import prepare_dem
from geoprocessing.dem.quality import build_quality_report, field_mask
from geoprocessing.dem.sources import DemSourceInfo
from geoprocessing.dem.terrain import Dem, bilinear, point_info, profile, slope_aspect
from geoprocessing.fields import FieldValidationError, parse_geojson
from geoprocessing.tests.fixtures.synthetic_dem import (
    synthetic_square_field_geojson,
    write_synthetic_bowl_utm,
    write_synthetic_inclined_plane_utm,
)


def test_utm_epsg_argentina():
    # San Luis (-65.7, -33.3) -> huso 20 sur -> EPSG:32720
    assert utm_epsg(-65.7, -33.3) == 32720
    # Mendoza (-68.8, -32.9) -> huso 19 sur -> EPSG:32719
    assert utm_epsg(-68.8, -32.9) == 32719
    # Misiones (-54.6, -26.8) -> huso 21 sur -> EPSG:32721
    assert utm_epsg(-54.6, -26.8) == 32721
    with pytest.raises(ValueError):
        utm_epsg(-195.0, -33.0)


def test_parse_valid_sample_parcel():
    sample = Path(__file__).resolve().parents[2] / "data" / "sample" / "san_luis_parcela_205.geojson"
    lotes = parse_geojson(sample.read_bytes())
    assert len(lotes) == 1
    lote = lotes[0]
    assert lote.utm_epsg == 32720
    assert 198.0 <= lote.area_ha <= 200.5
    assert lote.declared_area_ha == pytest.approx(199.342, rel=1e-3)


def test_reject_invalid_geometries():
    # Anillo abierto
    abierto = {
        "type": "Polygon",
        "coordinates": [[[-65.7, -33.3], [-65.69, -33.3], [-65.69, -33.29], [-65.7, -33.29]]],
    }
    with pytest.raises(FieldValidationError, match="Anillo abierto"):
        parse_geojson(abierto)

    # Autointersección (moño)
    mono = {
        "type": "Polygon",
        "coordinates": [
            [
                [-65.70, -33.30],
                [-65.69, -33.29],
                [-65.70, -33.29],
                [-65.69, -33.30],
                [-65.70, -33.30],
            ]
        ],
    }
    with pytest.raises(FieldValidationError, match="Geometría inválida"):
        parse_geojson(mono)

    # Coordenadas fuera de rango (invertidas lat/lon con lon > 90 en latitud)
    invertido = {
        "type": "Polygon",
        "coordinates": [[[-33.30, -65.70], [-33.29, -65.70], [-33.29, -120.0], [-33.30, -65.70]]],
    }
    with pytest.raises(FieldValidationError, match="Coordenadas fuera de rango"):
        parse_geojson(invertido)


def test_slope_aspect_on_synthetic_inclined_plane(tmp_path: Path):
    """En un plano inclinado sintético con pendiente 3 % al este y 4 % al sur, Horn debe dar 5.00 %."""
    tif = write_synthetic_inclined_plane_utm(
        tmp_path / "plane.tif", slope_east=0.03, slope_south=0.04, pixel_m=10.0, width=40, height=40
    )
    dem = Dem.open(tif)
    pct, deg, asp = slope_aspect(dem.z, dem.pixel, dem.pixel)
    # Bordes son NaN
    assert np.isnan(pct[0, :]).all()
    interior = pct[1:-1, 1:-1]
    assert np.allclose(interior, 5.0, atol=1e-3)
    assert np.allclose(deg[1:-1, 1:-1], np.degrees(np.arctan(0.05)), atol=1e-3)
    # Si z crece hacia el este (+3%) y hacia el sur (+4%), el descenso máximo apunta al noroeste (~323.13°)
    assert np.allclose(asp[1:-1, 1:-1], (np.degrees(np.arctan2(-0.03, 0.04)) + 360) % 360, atol=1e-2)


def test_profile_and_point_on_synthetic_bowl(tmp_path: Path):
    geojson = synthetic_square_field_geojson()
    lote = parse_geojson(geojson)[0]
    tif_src = write_synthetic_bowl_utm(tmp_path / "bowl_src.tif", pixel_m=10.0, width=220, height=220)
    prep = prepare_dem(tif_src, lote.geometry, lote.utm_epsg, buffer_m=100.0, destino=tmp_path / "bowl_utm.tif")
    dem = Dem.open(prep.path)
    mascara = field_mask(lote.geometry, lote.utm_epsg, dem.transform, dem.z.shape)

    # Punto en el centroide del lote
    pt = point_info(dem, lote.centroid[0], lote.centroid[1], mascara)
    assert pt["inside_dem"] is True
    assert pt["inside_field"] is True
    assert pt["elevation_m"] is not None

    # Perfil diagonal a través del lote: el mínimo del cuenco debe ser menor que los extremos
    oeste, sur, este, norte = lote.bbox
    pf = profile(dem, [[oeste, sur], [este, norte]], paso_m=15.0)
    cotas = [s["elevation_m"] for s in pf["samples"] if s["elevation_m"] is not None]
    assert len(cotas) > 10
    assert min(cotas) < cotas[0] and min(cotas) < cotas[-1]


def test_quality_report_flags_low_resolution_and_nodata():
    z = np.full((6, 6), 500.0, dtype="float32")
    z[2, 2] = np.nan  # vacío interno
    mascara = np.zeros((6, 6), dtype=bool)
    mascara[1:4, 1:4] = True  # solo 9 celdas dentro del lote (< 25 -> crítico)
    transform = from_origin(248_000.0, 6_314_000.0, 30.0, 30.0)
    fuente = DemSourceInfo(
        source_id="test_synthetic",
        source_name="DEM Sintético 30 m",
        source_url=None,
        license=None,
        surface_type="DSM",
        nominal_resolution_m=30.0,
        vertical_datum="EGM2008",
        vertical_accuracy_m=4.0,
        vertical_accuracy_note=None,
        acquisition_start="2020-01-01",
        acquisition_end="2020-01-02",
        acquisition_method="Sintético",
    )
    rep = build_quality_report(z, transform, "EPSG:32720", mascara, 0.81, fuente, (30.0, 30.0), 60.0)
    codigos = {w.code for w in rep.warnings}
    assert "resolucion_insuficiente" in codigos
    assert "sin_microrelieve" in codigos
    assert "modelo_superficie" in codigos
    assert "nodata_alto" in codigos
    # Verificar que bilinear no interpola sobre NaN
    dem = Dem(z=z, transform=transform, crs="EPSG:32720")
    x_nan, y_nan = dem.xy_of_cell(2, 2)
    assert np.isnan(bilinear(dem, np.array([x_nan]), np.array([y_nan]))[0])
