"""Tests de verificación para Paso 6 de la auditoría de relieve (Refs #73).

Cubre:
1. Desambiguación de punto silla en marching squares (contours_geojson) con Asymptotic Decider.
2. Indicador de confianza con pendiente sin dato (mean_slope_pct=None).
3. Conversión de LE90 a NMAD bajo distribución normal (LE90 / 1.645).
4. Corrección de supuestos: eliminación de 'llanura pampeana', fuentes calibrables y justificación de 7 celdas.
5. Umbrales de breach y longitud máxima de ladera en supuestos.
6. Cita y especificación oficial de NASADEM en sources.py.
"""

import numpy as np
import pytest
from affine import Affine

from geoprocessing.dem.sources import opentopography_info
from geoprocessing.dem.terrain import Dem, contours_geojson
from geoprocessing.hydrology.confidence import compute_confidence_indicator
from geoprocessing.supuestos import (
    SUPUESTO_BREACH_MAX_DEPTH_M,
    SUPUESTO_BREACH_MAX_DIST_CELLS,
    SUPUESTO_DEPRESION_MAX_FILL_AREA_M2,
    SUPUESTO_DEPRESION_MAX_FILL_DEPTH_M,
    SUPUESTO_LE90_A_NMAD_FACTOR,
    SUPUESTO_SLOPE_SMOOTHING_FALLBACK_WINDOW,
    SUPUESTO_USLE_MAX_SLOPE_LENGTH_M,
)


def test_contours_saddle_point_asymptotic_decider():
    """Valida la resolución de ambigüedad topológica en celdas de punto silla (marching squares)."""
    # Celda 2x2: (0,0)=top-left, (0,1)=top-right, (1,0)=bottom-left, (1,1)=bottom-right
    # Transformación arbitraria en UTM 20S
    transform = Affine.translation(500000.0, 6200000.0) @ Affine.scale(10.0, -10.0)

    # Caso 1: Punto silla ALTO (v_center >= lvl).
    # z: corner 00=12, 10(top-right)=20, 11(bottom-right)=12, 01(bottom-left)=20
    # Nivel lvl = 15.0 -> corners 10 y 01 son >= 15 (case 10).
    # v_center = (12 + 20 + 12 + 20) / 4 = 16.0 >= 15.0.
    # El centro es alto, por lo que separa las esquinas bajas (00 y 11).
    # Contorno conecta: (0, 3) arriba-izquierda y (1, 2) derecha-abajo.
    z_high_saddle = np.array([[12.0, 20.0], [20.0, 12.0]], dtype=float)
    dem_high = Dem(z=z_high_saddle, transform=transform, crs="EPSG:32720")
    fc_high = contours_geojson(dem_high, interval_m=15.0)

    assert fc_high["type"] == "FeatureCollection"
    # Cada nivel de elevación se emite como un Feature con MultiLineString
    assert len(fc_high["features"]) == 1
    coords_high = fc_high["features"][0]["geometry"]["coordinates"]
    # El punto silla desacopla el nivel en 2 líneas independientes
    assert len(coords_high) == 2

    # Caso 2: Punto silla BAJO (v_center < lvl).
    # z: corner 00=8, 10=20, 11=8, 01=20
    # v_center = (8 + 20 + 8 + 20) / 4 = 14.0 < 15.0.
    # El centro es bajo, por lo que separa las esquinas altas (10 y 01).
    # Contorno conecta: (0, 1) arriba-derecha y (3, 2) izquierda-abajo.
    z_low_saddle = np.array([[8.0, 20.0], [20.0, 8.0]], dtype=float)
    dem_low = Dem(z=z_low_saddle, transform=transform, crs="EPSG:32720")
    fc_low = contours_geojson(dem_low, interval_m=15.0)

    assert len(fc_low["features"]) == 1
    coords_low = fc_low["features"][0]["geometry"]["coordinates"]
    assert len(coords_low) == 2

    # La topología de conexión debe ser diferente entre silla alta y silla baja:
    # en silla alta conecta esquina (0,3) y (1,2); en silla baja conecta (0,1) y (3,2).
    # Por tanto, las coordenadas de los extremos no son idénticas en ambas configuraciones.
    assert coords_high != coords_low

    # Caso 3: Case 5 con centro alto vs centro bajo
    # Corners 00 y 11 altos (20.0), 10 y 01 bajos (12.0) -> v_center = 16.0 >= 15.0
    z_case5_high = np.array([[20.0, 12.0], [12.0, 20.0]], dtype=float)
    dem_c5_high = Dem(z=z_case5_high, transform=transform, crs="EPSG:32720")
    fc_c5_high = contours_geojson(dem_c5_high, interval_m=15.0)
    assert len(fc_c5_high["features"]) == 1
    assert len(fc_c5_high["features"][0]["geometry"]["coordinates"]) == 2

    z_case5_low = np.array([[20.0, 8.0], [8.0, 20.0]], dtype=float)
    dem_c5_low = Dem(z=z_case5_low, transform=transform, crs="EPSG:32720")
    fc_c5_low = contours_geojson(dem_c5_low, interval_m=15.0)
    assert len(fc_c5_low["features"]) == 1
    assert len(fc_c5_low["features"][0]["geometry"]["coordinates"]) == 2
    assert fc_c5_high["features"][0]["geometry"]["coordinates"] != fc_c5_low["features"][0]["geometry"]["coordinates"]


def test_confidence_indicator_missing_slope():
    """Si no hay pendiente media disponible (None), el indicador debe reportar 'sin dato'."""
    ci = compute_confidence_indicator(
        source_id="copernicus_glo30",
        resolution_m=30.0,
        mean_slope_pct=None,
        soil_source="inta_regional",
        rain_source_type="regional_design",
    )
    assert "sin dato" in ci["relief_note"]
    assert any("sin dato" in r for r in ci["reasons"])
    assert ci["score"] < 0.70


def test_le90_to_nmad_conversion_supuesto():
    """Valida el factor de conversión LE90 a NMAD bajo hipótesis normal (1.645)."""
    assert SUPUESTO_LE90_A_NMAD_FACTOR.valor == 1.645
    assert SUPUESTO_LE90_A_NMAD_FACTOR.unidad == "adimensional"
    assert "1.645" in SUPUESTO_LE90_A_NMAD_FACTOR.motivo

    # Copernicus GLO-30 LE90 nominal es 4.0 m -> NMAD equivalente es ~2.432 m
    le90 = 4.0
    nmad_eq = round(le90 / SUPUESTO_LE90_A_NMAD_FACTOR.valor, 3)
    assert pytest.approx(nmad_eq, rel=1e-3) == 2.432


def test_supuestos_revisados_sin_llanura_pampeana():
    """Verifica que los supuestos de depresiones no citen 'llanura pampeana' y tengan fuente calibrable."""
    assert "llanura pampeana" not in SUPUESTO_DEPRESION_MAX_FILL_DEPTH_M.motivo.lower()
    assert SUPUESTO_DEPRESION_MAX_FILL_DEPTH_M.fuente_referencia == "supuesto, calibrable"

    assert "llanura pampeana" not in SUPUESTO_DEPRESION_MAX_FILL_AREA_M2.motivo.lower()
    assert SUPUESTO_DEPRESION_MAX_FILL_AREA_M2.fuente_referencia == "supuesto, calibrable"

    # Ventana de suavizado de reserva explica por qué 7 celdas
    assert SUPUESTO_SLOPE_SMOOTHING_FALLBACK_WINDOW.valor == 7
    assert "1/7" in SUPUESTO_SLOPE_SMOOTHING_FALLBACK_WINDOW.motivo
    assert "0.4%" in SUPUESTO_SLOPE_SMOOTHING_FALLBACK_WINDOW.motivo


def test_breach_and_slope_length_supuestos():
    """Verifica los supuestos de brecha y longitud máxima de ladera."""
    assert SUPUESTO_BREACH_MAX_DEPTH_M.valor == 0.8
    assert SUPUESTO_BREACH_MAX_DEPTH_M.unidad == "m"
    assert "Lindsay" in SUPUESTO_BREACH_MAX_DEPTH_M.fuente_referencia

    assert SUPUESTO_BREACH_MAX_DIST_CELLS.valor == 50
    assert SUPUESTO_BREACH_MAX_DIST_CELLS.unidad == "celdas"

    assert SUPUESTO_USLE_MAX_SLOPE_LENGTH_M.valor == 180.0
    assert SUPUESTO_USLE_MAX_SLOPE_LENGTH_M.unidad == "m"


def test_nasadem_source_info_citation():
    """Verifica que NASADEM en sources.py cite SRTM/Rodriguez o Buckley."""
    info = opentopography_info("NASADEM")
    note = info.vertical_accuracy_note
    assert note is not None
    assert "SRTM" in note or "Rodriguez" in note or "Buckley" in note
