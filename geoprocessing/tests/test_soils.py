"""Pruebas sin internet de suelos (spec 004): textura USDA, grupo hidrológico y conector SoilGrids."""

from __future__ import annotations

import httpx
import pytest

from geoprocessing.soils.soilgrids import query_point, sample_points, soil_for_field
from geoprocessing.soils.texture import hydrologic_group_from_texture, usda_texture_class

LOTE = {
    "type": "Polygon",
    "coordinates": [[[-65.31, -33.66], [-65.30, -33.66], [-65.30, -33.65], [-65.31, -33.65], [-65.31, -33.66]]],
}


@pytest.mark.parametrize(
    ("sand", "silt", "clay", "esperado"),
    [
        (92, 5, 3, "Arenosa"),
        (82, 12, 6, "Arenosa franca"),
        (65, 25, 10, "Franco arenosa"),
        (40, 40, 20, "Franca"),
        (20, 65, 15, "Franco limosa"),
        (5, 88, 7, "Limosa"),
        (60, 15, 25, "Franco arcillo arenosa"),
        (32, 34, 34, "Franco arcillosa"),
        (10, 55, 35, "Franco arcillo limosa"),
        (50, 10, 40, "Arcillo arenosa"),
        (5, 50, 45, "Arcillo limosa"),
        (20, 20, 60, "Arcillosa"),
    ],
)
def test_usda_texture_class_reference_points(sand, silt, clay, esperado):
    assert usda_texture_class(sand, silt, clay) == esperado


def test_hydrologic_group_by_texture():
    assert hydrologic_group_from_texture("Franco arenosa") == "A"
    assert hydrologic_group_from_texture("Franca") == "B"
    assert hydrologic_group_from_texture("Franco arcillo arenosa") == "C"
    assert hydrologic_group_from_texture("Arcillosa") == "D"
    with pytest.raises(ValueError):
        hydrologic_group_from_texture("Turba")


def test_sample_points_are_inside_the_field():
    from shapely.geometry import Point, shape

    puntos = sample_points(LOTE)
    assert 1 <= len(puntos) <= 3
    geom = shape(LOTE)
    assert all(geom.contains(Point(lon, lat)) for lon, lat in puntos)


def _respuesta_soilgrids(clay: int, sand: int, silt: int) -> dict:
    """Respuesta con la forma real de la API (valores en g/kg × d_factor 10)."""

    def capa(nombre: str, valor: int) -> dict:
        return {
            "name": nombre,
            "unit_measure": {"d_factor": 10, "mapped_units": "g/kg", "target_units": "%"},
            "depths": [
                {"label": "0-5cm", "values": {"mean": valor}},
                {"label": "5-15cm", "values": {"mean": valor}},
                {"label": "15-30cm", "values": {"mean": valor}},
            ],
        }

    return {"properties": {"layers": [capa("clay", clay), capa("sand", sand), capa("silt", silt)]}}


def _cliente(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_query_point_converts_units_to_percent():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "rest.isric.org"
        assert request.url.params.get_list("property") == ["clay", "sand", "silt"]
        return httpx.Response(200, json=_respuesta_soilgrids(clay=1000, sand=7100, silt=1900))

    valores = query_point(-65.305, -33.655, http=_cliente(handler))
    assert valores == pytest.approx({"clay": 10.0, "sand": 71.0, "silt": 19.0})


def test_soil_for_field_with_real_shaped_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_respuesta_soilgrids(clay=1000, sand=7100, silt=1900))

    suelo = soil_for_field(LOTE, http=_cliente(handler))
    assert suelo["soil_group"] == "A"
    assert suelo["texture_class"] == "Franco arenosa"
    assert suelo["soil_source"] == "soilgrids"
    assert "SoilGrids" in suelo["source_label"]
    assert suelo["license"] == "CC BY 4.0"
    assert suelo["quality"] in ("buena", "dudosa")


def test_soil_for_field_offline_never_invents():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red", request=request)

    suelo = soil_for_field(LOTE, http=_cliente(handler))
    assert suelo["soil_group"] is None
    assert suelo["soil_source"] == "default"
    assert suelo["quality"] == "descartada"
    assert "SoilGrids" in suelo["notes"][0]


def test_soil_for_field_empty_layers_is_discarded():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"properties": {"layers": []}})

    suelo = soil_for_field(LOTE, http=_cliente(handler))
    assert suelo["soil_group"] is None
    assert suelo["quality"] == "descartada"


def test_api_soil_endpoint_uses_real_source_and_caches(tmp_path, monkeypatch):
    import json

    from fastapi.testclient import TestClient

    from geoprocessing.soils import soilgrids
    from geoprocessing.tests.fixtures.synthetic_dem import synthetic_square_field_geojson
    from services.api.app.core import config
    from services.api.app.main import app
    from services.api.app.services import store

    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "runs")
    monkeypatch.setattr(store, "DATA_DIR", tmp_path / "runs")
    llamadas = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        llamadas["n"] += 1
        return httpx.Response(200, json=_respuesta_soilgrids(clay=1000, sand=7100, silt=1900))

    monkeypatch.setattr(soilgrids, "client", lambda: _cliente(handler))
    api = TestClient(app)
    r = api.post(
        "/api/v1/fields/import",
        files={"file": ("lote.geojson", json.dumps(synthetic_square_field_geojson()).encode(), "application/geo+json")},
    )
    field_id = r.json()["fields"][0]["id"]

    r1 = api.get(f"/api/v1/fields/{field_id}/soil")
    assert r1.status_code == 200, r1.text
    assert r1.json()["soil_group"] == "A"
    assert r1.json()["soil_source"] == "soilgrids"
    primeras = llamadas["n"]
    assert primeras >= 1

    r2 = api.get(f"/api/v1/fields/{field_id}/soil")
    assert r2.json() == r1.json()
    assert llamadas["n"] == primeras  # segunda consulta sale de la caché
