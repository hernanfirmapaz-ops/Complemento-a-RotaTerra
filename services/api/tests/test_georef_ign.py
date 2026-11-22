"""Pruebas unitarias de georreferenciación de límites administrativos del IGN (Issue #84)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from services.api.app.main import app
from services.api.app.services.georef import (
    _query_wfs_point,
    clear_cache,
    resolve_ign_location,
    set_test_fixture,
    set_test_fixture_file,
)

client = TestClient(app)

FIXTURE_PATH = "geoprocessing/tests/fixtures/ign/ign_limites_referencia.geojson"


def setup_module():
    set_test_fixture_file(FIXTURE_PATH)
    clear_cache()


def teardown_module():
    set_test_fixture(None)
    clear_cache()


def test_georef_location_villa_mercedes_offline():
    # Villa Mercedes: San Luis / General Pedernera
    with patch("urllib.request.urlopen") as mock_url:
        response = client.get("/api/v1/georef/location?lon=-65.46&lat=-33.67")
        assert response.status_code == 200
        data = response.json()
        assert data["provincia"] == "San Luis"
        assert data["departamento"] == "General Pedernera"
        assert data["municipio"] is None
        assert "San Luis" in data["formatted"]
        assert "General Pedernera" in data["formatted"]
        assert data["fuente"] == "Instituto Geográfico Nacional (IGN)"
        # Debe ser 100% offline sin llamadas a WFS
        mock_url.assert_not_called()


def test_georef_location_piedemonte_offline():
    # El Trapiche / Coronel Pringles: San Luis
    with patch("urllib.request.urlopen") as mock_url:
        response = client.get("/api/v1/georef/location?lon=-66.085&lat=-33.128")
        assert response.status_code == 200
        data = response.json()
        assert data["provincia"] == "San Luis"
        assert data["departamento"] == "Coronel Pringles"
        assert data["municipio"] is None
        assert "San Luis" in data["formatted"]
        assert "Coronel Pringles" in data["formatted"]
        assert data["fuente"] == "Instituto Geográfico Nacional (IGN)"
        mock_url.assert_not_called()


def test_georef_location_outside_fixture_returns_none():
    # Coordenada en otra provincia o mar
    with patch("urllib.request.urlopen") as mock_url:
        response = client.get("/api/v1/georef/location?lon=-58.0&lat=-34.0")
        assert response.status_code == 200
        data = response.json()
        assert data["provincia"] is None
        assert data["departamento"] is None
        assert data["municipio"] is None
        assert data["formatted"] == "Argentina (-34.0000°, -58.0000°)"
        mock_url.assert_not_called()


def test_georef_location_invalid_coords():
    response = client.get("/api/v1/georef/location?lon=-200&lat=0")
    assert response.status_code == 422


def test_query_wfs_point_no_containment_returns_none():
    # Simular respuesta WFS con polígono que NO contiene el punto
    geojson_response = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[-64.0, -32.0], [-64.0, -31.0], [-63.0, -31.0], [-63.0, -32.0], [-64.0, -32.0]]
                    ],
                },
                "properties": {"nam": "Departamento Vecino", "fna": "Departamento Vecino"},
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(geojson_response).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        # Punto (-65.0, -33.0) está fuera del polígono
        res = _query_wfs_point("ign:departamento", -65.0, -33.0)
        assert res is None, "Si ningún polígono contiene el punto debe retornar None, nunca feats[0]"


def test_production_cache_avoids_repeated_wfs():
    # En modo producción (sin fixture de tests), la caché en memoria evita llamadas repetidas
    set_test_fixture(None)
    clear_cache()

    geojson_prov = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[-67.0, -34.0], [-67.0, -32.0], [-64.0, -32.0], [-64.0, -34.0], [-67.0, -34.0]]
                    ],
                },
                "properties": {"nam": "San Luis", "fna": "Provincia de San Luis"},
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(geojson_prov).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_url:
        loc1 = resolve_ign_location(-65.46, -33.67)
        assert loc1["provincia"] == "San Luis"
        call_count_1 = mock_url.call_count
        assert call_count_1 >= 1

        # Segunda llamada a las mismas coordenadas debe resolver desde caché sin llamar a urlopen
        loc2 = resolve_ign_location(-65.46, -33.67)
        assert loc2["provincia"] == "San Luis"
        assert mock_url.call_count == call_count_1
