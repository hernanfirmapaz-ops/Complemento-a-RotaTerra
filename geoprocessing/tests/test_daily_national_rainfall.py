"""Tests unitarios y de integración para el módulo de Precipitación Diaria Oficial (SMN + CONAE + NASA)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from geoprocessing.rainfall.daily_national import (
    determine_amc_from_prior_rain,
    find_nearest_smn_station,
    get_field_daily_rainfall_context,
    haversine_distance_km,
)
from services.api.app.main import app
from services.api.app.services import store


def test_haversine_distance():
    # Buenos Aires (-34.60, -58.38) a Córdoba (-31.42, -64.18) ~ 645 km
    d = haversine_distance_km(-58.38, -34.60, -64.18, -31.42)
    assert 600 < d < 700


def test_find_nearest_smn_station():
    # Coordenadas de San Luis capital
    st_sl = find_nearest_smn_station(-66.35, -33.26)
    assert "SAN LUIS" in st_sl["name"] or "REYNOLDS" in st_sl["name"]
    assert st_sl["distance_km"] < 50.0

    # Coordenadas de Marcos Juárez, Córdoba
    st_mj = find_nearest_smn_station(-62.15, -32.66)
    assert "MARCOS JUAREZ" in st_mj["name"]
    assert st_mj["distance_km"] < 15.0


def test_determine_amc_from_prior_rain():
    assert determine_amc_from_prior_rain(5.0) == "dry"
    assert determine_amc_from_prior_rain(14.9) == "dry"
    assert determine_amc_from_prior_rain(15.0) == "medium"
    assert determine_amc_from_prior_rain(38.0) == "medium"
    assert determine_amc_from_prior_rain(38.1) == "wet"
    assert determine_amc_from_prior_rain(120.0) == "wet"


def test_get_field_daily_rainfall_context():
    # Coordenadas de prueba en zona agrícola
    ctx = get_field_daily_rainfall_context(-65.98, -33.25, limit_rainy_days=10)
    assert ctx["status"] in ("available", "unavailable")
    assert "nearest_smn_station" in ctx
    assert ctx["nearest_smn_station"]["name"] != ""
    if ctx["status"] == "available":
        assert ctx["selected_day"] is not None
        assert "precipitation_mm" in ctx["selected_day"]
        assert "antecedent_moisture_amc" in ctx["selected_day"]
        assert "quality_flag" in ctx["selected_day"]


def test_api_daily_rainfall_endpoints():
    fields = store.list_fields()
    if not fields:
        pytest.skip("No hay lotes guardados para probar la API.")

    f_id = fields[0]["id"]
    client = TestClient(app)

    # 1. GET daily rainfall context
    r_get = client.get(f"/api/v1/fields/{f_id}/hydrology/daily-rainfall")
    assert r_get.status_code == 200
    data = r_get.json()
    assert "nearest_smn_station" in data
    assert "name" in data["nearest_smn_station"]
    assert "distance_km" in data["nearest_smn_station"]

    # 2. POST simulate daily rain
    if data.get("selected_day"):
        day_date = data["selected_day"]["date"]
        payload = {
            "date": day_date,
            "soil_group": "B",
            "cover_code": "soja_maiz_sd_buena",
            "cover_percent": 60.0,
            "compaction_high": False,
        }
        r_post = client.post(f"/api/v1/fields/{f_id}/hydrology/daily-rainfall/simulate", json=payload)
        assert r_post.status_code == 200
        res = r_post.json()
        assert "event" in res
        assert "runoff_run" in res
        assert res["runoff_run"]["is_active"] is True
        assert res["event"]["source_type"] == "SMN"
        assert res["event"]["total_mm"] >= 0.0
