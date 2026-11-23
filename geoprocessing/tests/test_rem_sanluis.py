"""Tests unitarios offline para el conector de la Red de Estaciones Meteorológicas de San Luis (REM).

Verifica la búsqueda de estaciones más cercanas, el parseo de archivos CSV con encoding Windows-1252,
el cálculo de precipitación acumulada de 5 días previos para AMC y la adhesión al supuesto de distancia máxima.
Cumple con las reglas de integridad de datos (sin conexión a internet, sin valores inventados).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from geoprocessing.rainfall.rem_sanluis import (
    determine_amc_from_prior_rain,
    find_nearest_rem_station,
    get_rem_antecedent_rainfall_5d,
    load_rem_stations,
    parse_rem_csv,
)
from geoprocessing.supuestos import SUPUESTO_REM_DISTANCIA_MAX_KM

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "rainfall" / "rem_villa_mercedes_sample.csv"


def test_rem_stations_catalogue():
    stations = load_rem_stations()
    assert len(stations) >= 10
    ids = {s["id"] for s in stations}
    assert 42 in ids  # Villa Mercedes
    assert 60 in ids  # Villa Reynolds
    assert 47 in ids  # El Trapiche


def test_find_nearest_rem_station_in_range():
    # Coordenadas cercanas a Villa Mercedes / Villa Reynolds
    lon, lat = -65.46, -33.67
    station = find_nearest_rem_station(lon, lat)
    assert station["id"] in (42, 60)
    assert station["distance_km"] < float(SUPUESTO_REM_DISTANCIA_MAX_KM.valor)
    assert station["in_range"] is True
    assert station["label"].startswith("REM ")
    assert "km)" in station["label"]
    assert "Universidad de La Punta" in station["source_citation"]


def test_find_nearest_rem_station_out_of_range():
    # Coordenadas en Pergamino, Buenos Aires (lejos de San Luis)
    lon, lat = -60.58, -33.91
    station = find_nearest_rem_station(lon, lat)
    assert station["distance_km"] > 300.0
    assert station["in_range"] is False


def test_parse_rem_csv_windows_1252():
    assert FIXTURE_CSV.exists(), f"No se encontró el fixture en {FIXTURE_CSV}"
    raw_bytes = FIXTURE_CSV.read_bytes()

    records = parse_rem_csv(raw_bytes)
    assert len(records) == 11

    # Verificar registro con valor normal
    r1 = next(r for r in records if r["date"] == "2026-11-15")
    assert r1["precipitation_mm"] == 12.4
    assert r1["temp_max_c"] == 23.0
    assert r1["temp_min_c"] == 11.5
    assert r1["temp_mean_c"] == 16.9

    # Verificar registro con valor vacío (11/13/2026 no tuvo dato de precipitación)
    r_empty = next(r for r in records if r["date"] == "2026-11-13")
    assert r_empty["precipitation_mm"] is None
    assert r_empty["temp_max_c"] == 22.0


def test_get_rem_antecedent_rainfall_5d_complete():
    raw_bytes = FIXTURE_CSV.read_bytes()
    records = parse_rem_csv(raw_bytes)

    # Para target_date = 2026-11-20:
    # 5 días previos: 11/15 (12.4), 11/16 (5.2), 11/17 (0.0), 11/18 (18.0), 11/19 (2.6)
    # Total = 12.4 + 5.2 + 0.0 + 18.0 + 2.6 = 38.2 mm -> AMC wet (> 38 mm)
    res = get_rem_antecedent_rainfall_5d(42, "2026-11-20", records=records)
    assert res is not None
    assert res["prior_5d_mm"] == 38.2
    assert res["antecedent_moisture_amc"] == "wet"
    assert len(res["days_evaluated"]) == 5
    assert "2026-11-19" in res["days_evaluated"]
    assert "2026-11-15" in res["days_evaluated"]


def test_get_rem_antecedent_rainfall_5d_missing_data_returns_none():
    raw_bytes = FIXTURE_CSV.read_bytes()
    records = parse_rem_csv(raw_bytes)

    # Para target_date = 2026-11-18:
    # 5 días previos incluyen 11/13 que tiene valor nulo/faltante.
    # No se deben inventar datos -> retorna None.
    res = get_rem_antecedent_rainfall_5d(42, "2026-11-18", records=records)
    assert res is None


def test_amc_thresholds():
    assert determine_amc_from_prior_rain(5.0) == "dry"
    assert determine_amc_from_prior_rain(14.9) == "dry"
    assert determine_amc_from_prior_rain(15.0) == "medium"
    assert determine_amc_from_prior_rain(30.0) == "medium"
    assert determine_amc_from_prior_rain(38.0) == "medium"
    assert determine_amc_from_prior_rain(38.1) == "wet"
    assert determine_amc_from_prior_rain(60.0) == "wet"


def test_rem_offline_guarantee():
    # Garantiza que en modo test no se realizan peticiones HTTP externas
    with patch("urllib.request.urlopen") as mock_url:
        lon, lat = -65.46, -33.67
        st = find_nearest_rem_station(lon, lat)
        assert st["name"] in ("Villa Mercedes", "Villa Reynolds")
        mock_url.assert_not_called()
