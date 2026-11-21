"""Tests para verificar que las herramientas satelitales y agronómicas no contengan

datos inventados ni supuestos no declarados (Auditoría 21/11/2026, puntos 2, 3 y 13).
"""

from geoprocessing.satellite.nasa_power_imerg import (
    compute_ndvi_vigor_monitor,
    evaluate_frost_risk_and_sowing_dates,
    evaluate_real_date_waterlogging_risk,
)
from geoprocessing.supuestos import (
    SUPUESTO_NDVI_UMBRAL_ALTO_VIGOR,
    SUPUESTO_NDVI_UMBRAL_BAJO_VIGOR,
)


def test_waterlogging_no_data_returns_null_and_zero_days():
    """Punto 2: Anegamiento sin datos no inventa nada y retorna unavailable."""
    res = evaluate_real_date_waterlogging_risk(
        daily_rows=[],
        source_label="NASA POWER",
        soil_group="B",
        cover_code="soja_maiz_sd_buena",
        field_area_ha=100.0,
        low_zone_area_ha=10.0,
        depression_volume_m3=1000.0,
    )
    assert res["status"] == "unavailable"
    assert res["evaluated_days"] == 0
    assert res["significant_storms_count"] == 0
    assert res["top_historical_events"] == []


def test_waterlogging_with_data_reports_fill_pct_and_no_arbitrary_factors():
    """Punto 2: Anegamiento con datos no usa min(1.8, relleno) ni umbrales 25/8 mm sin fuente."""
    daily_rows = [
        {"date": f"2023-01-{i:02d}", "precip_mm": 5.0} for i in range(1, 10)
    ]
    # Evento de 60 mm en día 6 (tras 5 días de 5 mm = 25 mm acumulados -> amc 'medium')
    daily_rows[5]["precip_mm"] = 60.0

    res = evaluate_real_date_waterlogging_risk(
        daily_rows=daily_rows,
        source_label="NASA POWER (reanálisis ~55 km)",
        soil_group="B",
        cover_code="soja_maiz_sd_buena",
        field_area_ha=100.0,
        low_zone_area_ha=10.0,
        depression_volume_m3=5000.0,
    )
    assert res["status"] == "available"
    assert res["significant_storms_count"] >= 1
    ev = res["top_historical_events"][0]
    # Debe informar volumen escurrido y % de llenado de bajos
    assert "runoff_volume_m3" in ev
    assert ev["runoff_volume_m3"] > 0
    assert "depression_fill_pct" in ev
    assert ev["depression_fill_pct"] is not None
    # Hectáreas solo si vienen del motor 2D (aquí no hay simulación 2D para cada tormenta histórica)
    assert ev.get("estimated_waterlogged_area_ha") is None
    # No debe usar el factor inventado 1.8 ni umbrales sin fuente
    assert ev.get("waterlogging_risk") is None or ev.get("waterlogging_risk") == "descartada"


def test_frost_no_data_returns_null_and_descartada():
    """Punto 3: Heladas sin datos retorna null + descartada, sin días fijos 12/28 ni fechas 265/280/115."""
    res = evaluate_frost_risk_and_sowing_dates(
        daily_rows=[],
        source_label="NASA POWER (reanálisis ~55 km)",
    )
    assert res["status"] == "unavailable"
    assert res["is_satellite_observed"] is False
    assert res["calidad"] == "descartada"
    assert res["mean_meteorological_frost_days_yr"] is None
    assert res["mean_agronomic_frost_days_yr"] is None
    assert res["median_last_spring_frost_date"] is None
    assert res["safe_spring_sowing_start_date"] is None
    assert res["median_first_autumn_frost_date"] is None
    assert res["frost_free_period_days"] is None
    assert res["safe_sowing_windows_by_crop"] == []


def test_frost_with_data_is_never_satellite_observed_and_no_floor_120():
    """Punto 3: NASA POWER es reanálisis (is_satellite_observed=False) y no impone piso de 120 días."""
    # Simular un año con heladas muy tardías y tempranas para dar ventana < 120 días
    daily_rows = []
    # Año 2023 completo (365 días)
    for doy in range(1, 366):
        # Helada tardía día 300 (fin de octubre) y temprana día 85 (fines de marzo)
        # ventana = (365 - (300+5)) + 85 = 60 + 85 = 145 días, probemos día 320 y 80 -> 40 + 80 = 120
        # día 330 y día 80: ventana = (365 - 335) + 80 = 110 días (< 120)
        tmin = -2.0 if doy in (80, 330) else 10.0
        daily_rows.append({
            "date": f"2023-doy-{doy}",
            "year": 2023,
            "day_of_year": doy,
            "tmin_c": tmin,
            "tmax_c": 20.0,
            "precip_mm": 0.0,
        })

    res = evaluate_frost_risk_and_sowing_dates(
        daily_rows=daily_rows,
        source_label="NASA POWER (reanálisis ~55 km)",
    )
    assert res["status"] == "available"
    assert res["is_satellite_observed"] is False
    assert "reanálisis" in res["source"].lower()
    # Sin piso artificial de 120 días: la cuenta real da < 120
    assert res["frost_free_period_days"] < 120


def test_ndvi_no_data_returns_null_and_declared_supuestos():
    """Punto 13: NDVI sin datos retorna null y umbrales 0.38 y 0.60 como supuestos declarados."""
    import numpy as np

    class DummyDem:
        z = np.zeros((10, 10), dtype="float32")
        pixel = 20.0
        transform = None
        crs = None

    dem = DummyDem()
    mascara = np.ones((10, 10), dtype=bool)
    twi = np.zeros((10, 10), dtype="float32")
    zones = np.ones((10, 10), dtype="int32")

    res = compute_ndvi_vigor_monitor(
        dem=dem,
        mascara_lote=mascara,
        twi=twi,
        agronomic_zone_id=zones,
        bbox_4326=(-65.5, -33.5, -65.4, -33.4),
    )
    assert res["grid"] is None
    summary = res["summary"]
    assert summary["status"] == "unavailable"
    assert summary["calidad"] == "descartada"
    assert summary["mean_ndvi_in_field"] is None
    assert summary["min_ndvi_in_field"] is None
    assert summary["max_ndvi_in_field"] is None
    assert summary["low_vigor_area_ha"] is None
    assert summary["low_vigor_pct"] is None
    # Supuestos declarados
    assert summary["supuestos"]["umbral_bajo_vigor"] == SUPUESTO_NDVI_UMBRAL_BAJO_VIGOR.valor == 0.38
    assert summary["supuestos"]["umbral_alto_vigor"] == SUPUESTO_NDVI_UMBRAL_ALTO_VIGOR.valor == 0.60
