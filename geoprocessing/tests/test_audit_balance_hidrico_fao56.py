"""Tests para verificar el balance hídrico mensual, radiación Ra y Kc según FAO-56

y umbrales estacionales de humedad antecedente según USDA-NRCS NEH-630 Tabla 10-1
(Issue #11 / Auditoría 21/11/2026, punto 5).
"""

from __future__ import annotations

import pytest

from geoprocessing.satellite.nasa_power_imerg import (
    compute_extraterrestrial_radiation_ra,
    compute_hargreaves_et0_daily,
    compute_monthly_water_balance,
    determine_nrcs_amc,
    get_crop_kc_fao56,
)


def test_fao56_example_8_extraterrestrial_radiation():
    """Valida el cálculo de radiación extraterrestre Ra contra el Ejemplo 8 resuelto

    de la publicación FAO Irrigation and Drainage Paper No. 56 (Allen et al. 1998, pág. 47).

    Datos del Ejemplo 8 resuelto de FAO-56:
    - Latitud: 20° Sur (latitude_deg = -20.0, phi = -0.349 rad)
    - Fecha: 3 de septiembre (día del año J = 246)
    - Valores resueltos en el documento:
        dr = 0.985
        delta = 0.120 rad
        omega_s = 1.527 rad
        Ra = 32.2 MJ / (m² · día)
        Ra (evaporación equivalente) = 0.408 * 32.2 = 13.1 mm / día
    """
    ra_mm, ra_mj = compute_extraterrestrial_radiation_ra(
        latitude_deg=-20.0,
        day_of_year=246,
        return_mj=True,
    )

    # Ra en MJ/(m²·día): documento reporta 32.2 MJ/m²/d
    assert ra_mj == pytest.approx(32.2, abs=0.15)
    # Ra en mm/día equivalente: documento reporta 13.1 mm/d
    assert ra_mm == pytest.approx(13.1, abs=0.1)


def test_hargreaves_et0_fao56_equation_52():
    """Valida el cálculo de ET0 Hargreaves según FAO-56 Eq. 52 (pág. 64)

    ET0 = 0.0023 * (Tmean + 17.8) * (Tmax - Tmin)^0.5 * Ra
    """
    # Usando Ra = 13.1 mm/día (Ejemplo 8)
    # Tmean = 21.5 °C, Tmax = 27.0 °C, Tmin = 16.0 °C
    # DT = 11.0 °C, sqrt(11.0) = 3.31662
    # ET0 = 0.0023 * (21.5 + 17.8) * 3.31662 * 13.1 = 0.0023 * 39.3 * 3.31662 * 13.1 = 3.927 mm/día
    et0 = compute_hargreaves_et0_daily(
        tmean_c=21.5,
        tmax_c=27.0,
        tmin_c=16.0,
        ra_mm_day=13.1,
    )
    assert et0 == pytest.approx(3.93, abs=0.05)


def test_nrcs_amc_thresholds_dormant_and_growing_seasons():
    """Valida los umbrales de humedad antecedente AMC (I, II, III) según

    USDA-NRCS National Engineering Handbook Part 630, Capítulo 10, Tabla 10-1 (pág. 10-2).

    Dormant season (reposo):
    - AMC I (Dry): < 12.7 mm (< 0.5 in)
    - AMC II (Medium): 12.7 a 27.9 mm (0.5 a 1.1 in)
    - AMC III (Wet): > 27.9 mm (> 1.1 in)

    Growing season (crecimiento):
    - AMC I (Dry): < 35.6 mm (< 1.4 in)
    - AMC II (Medium): 35.6 a 53.3 mm (1.4 a 2.1 in)
    - AMC III (Wet): > 53.3 mm (> 2.1 in)
    """
    # 1. Estación de reposo (dormant)
    assert determine_nrcs_amc(prior_5d_mm=10.0, season="dormant") == "dry"
    assert determine_nrcs_amc(prior_5d_mm=12.7, season="dormant") == "medium"
    assert determine_nrcs_amc(prior_5d_mm=20.0, season="dormant") == "medium"
    assert determine_nrcs_amc(prior_5d_mm=27.9, season="dormant") == "medium"
    assert determine_nrcs_amc(prior_5d_mm=30.0, season="dormant") == "wet"

    # 2. Estación de crecimiento (growing)
    assert determine_nrcs_amc(prior_5d_mm=20.0, season="growing") == "dry"  # En reposo 20 mm era medium, aquí es dry
    assert determine_nrcs_amc(prior_5d_mm=35.6, season="growing") == "medium"
    assert determine_nrcs_amc(prior_5d_mm=45.0, season="growing") == "medium"
    assert determine_nrcs_amc(prior_5d_mm=53.3, season="growing") == "medium"
    assert determine_nrcs_amc(prior_5d_mm=60.0, season="growing") == "wet"

    # 3. Determinación automática por mes en hemisferio sur (San Luis, lat = -33.3)
    # Mes 7 (Julio, invierno austral) -> dormant
    assert determine_nrcs_amc(prior_5d_mm=20.0, month=7, latitude_deg=-33.3) == "medium"
    # Mes 1 (Enero, verano austral) -> growing
    assert determine_nrcs_amc(prior_5d_mm=20.0, month=1, latitude_deg=-33.3) == "dry"


def test_crop_kc_fao56_table_12():
    """Valida los coeficientes de cultivo Kc según FAO-56 Tabla 12 (págs. 110-114)."""
    # Soja (Glycine max): Kc_ini = 0.40, Kc_mid = 1.15, Kc_end = 0.50
    kc_soja_ini = get_crop_kc_fao56("soja", stage="ini")
    kc_soja_mid = get_crop_kc_fao56("soja", stage="mid")
    kc_soja_end = get_crop_kc_fao56("soja", stage="end")
    assert kc_soja_ini == pytest.approx(0.40)
    assert kc_soja_mid == pytest.approx(1.15)
    assert kc_soja_end == pytest.approx(0.50)

    # Maíz grano (Zea mays): Kc_ini = 0.30, Kc_mid = 1.20, Kc_end = 0.60 (o 0.35 cosecha seca)
    kc_maiz_mid = get_crop_kc_fao56("maiz", stage="mid")
    assert kc_maiz_mid == pytest.approx(1.20)

    # Trigo (Triticum aestivum): Kc_ini = 0.30/0.40, Kc_mid = 1.15
    kc_trigo_mid = get_crop_kc_fao56("trigo", stage="mid")
    assert kc_trigo_mid == pytest.approx(1.15)


def test_monthly_water_balance_uses_fao56_ra_and_lat():
    """Verifica que compute_monthly_water_balance use la radiación Ra de FAO-56 en función

    de la latitud y día del año, en lugar de un factor fijo hardcodeado 15.0.
    """
    days = [
        {
            "year": 2025,
            "month": 1,
            "day_of_year": 15,
            "precip_mm": 5.0,
            "tmin_c": 15.0,
            "tmax_c": 30.0,
            "tmean_c": 22.5,
        }
        for _ in range(30)
    ]
    # En latitud sur (-33.3°, San Luis) en enero (verano), Ra es alto (~16-17 mm/d)
    wb_sur = compute_monthly_water_balance(days, "NASA POWER", "B", latitude_deg=-33.3)
    et0_sur = wb_sur["months"][0]["et0_mm"]

    # En latitud norte (+50.0°, invierno boreal) en enero, Ra es muy bajo (~3-4 mm/d)
    wb_norte = compute_monthly_water_balance(days, "NASA POWER", "B", latitude_deg=50.0)
    et0_norte = wb_norte["months"][0]["et0_mm"]

    # ET0 en verano austral debe ser sustancialmente mayor que en invierno boreal para las mismas T
    assert et0_sur > 2.0 * et0_norte


def test_monthly_water_balance_discards_incomplete_rows_without_invented_defaults():
    """Auditoría 21/11 / Regla de datos: si falta temperatura, precipitación o fecha,

    el mes se marca como descartado / incompleto con valores null, nunca inventando 20 °C ni ±5 °C.
    """
    incomplete_days = [
        {
            "year": 2025,
            "month": 1,
            "day_of_year": 15,
            "precip_mm": 10.0,
            # tmean_c, tmax_c, tmin_c faltantes
        }
    ]
    wb = compute_monthly_water_balance(incomplete_days, "NASA POWER (test)", "B")

    # El balance global y el mes deben descartarse por incompletos
    assert wb["status"] == "unavailable"
    assert wb["calidad"] == "descartada"
    assert wb["annual_precipitation_mm"] is None
    assert wb["annual_et0_mm"] is None

    month_0 = wb["months"][0]
    assert month_0["calidad"] == "descartada"
    assert month_0["precipitation_mm"] is None
    assert month_0["et0_mm"] is None
    assert month_0["crop_demand_etc_mm"] is None
    assert month_0["available_water_mm"] is None
    assert "temperatura faltante" in month_0["motivo"]

