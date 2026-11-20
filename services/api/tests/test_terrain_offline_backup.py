"""Tests de verificación para la Tarea 0.3 / Tarea 4:
Respaldo de relieve real para lotes de ejemplo y mensaje claro sin conexión.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from geoprocessing import net as geonet
from geoprocessing.tests.fixtures.synthetic_dem import synthetic_square_field_geojson
from services.api.app.core import config
from services.api.app.main import app
from services.api.app.services import store, terrain

DATA_SAMPLE_DIR = Path(__file__).resolve().parents[3] / "data" / "sample"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "runs")
    monkeypatch.setattr(store, "DATA_DIR", tmp_path / "runs")
    terrain._cargar.cache_clear()
    return TestClient(app)


def test_sample_fields_load_real_dem_when_offline(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Verifica que sin internet los lotes de ejemplo carguen el relieve real de data/sample/ con sus metadatos."""
    # 1. Simular falla total de red (offline)
    def offline_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network unreachable (offline test)")

    offline_client = httpx.Client(transport=httpx.MockTransport(offline_handler))
    monkeypatch.setattr(geonet, "_cliente", offline_client)
    monkeypatch.setattr(geonet, "client", lambda: offline_client)

    # 2. Probar Lote de Ejemplo 1: Parcela Rural 205
    geojson_205 = (DATA_SAMPLE_DIR / "san_luis_parcela_205.geojson").read_bytes()
    r = client.post(
        "/api/v1/fields/import",
        files={"file": ("san_luis_parcela_205.geojson", geojson_205, "application/geo+json")},
        data={"default_name": "Parcela Rural 205 (San Luis)"},
    )
    assert r.status_code == 201
    f_205_id = r.json()["fields"][0]["id"]

    r_terr_205 = client.post(
        f"/api/v1/fields/{f_205_id}/terrain/process",
        data={"source_id": "copernicus_glo30", "buffer_m": "300"},
    )
    assert r_terr_205.status_code == 200, r_terr_205.text
    terr_205 = r_terr_205.json()
    assert "Copernicus DEM GLO-30" in terr_205["source"]["source_name"]
    assert "EGM2008" in terr_205["source"]["vertical_datum"]
    assert terr_205["source"]["license"] != ""
    assert terr_205["quality"]["cells_in_field"] > 100

    # 3. Probar Lote de Ejemplo 2: Piedemonte 492
    geojson_492 = (DATA_SAMPLE_DIR / "san_luis_piedemonte_492.geojson").read_bytes()
    r = client.post(
        "/api/v1/fields/import",
        files={"file": ("san_luis_piedemonte_492.geojson", geojson_492, "application/geo+json")},
        data={"default_name": "Lote Piedemonte El Trapiche #492 (San Luis)"},
    )
    assert r.status_code == 201
    f_492_id = r.json()["fields"][0]["id"]

    r_terr_492 = client.post(
        f"/api/v1/fields/{f_492_id}/terrain/process",
        data={"source_id": "copernicus_glo30", "buffer_m": "300"},
    )
    assert r_terr_492.status_code == 200, r_terr_492.text
    terr_492 = r_terr_492.json()
    assert "Copernicus DEM GLO-30" in terr_492["source"]["source_name"]
    assert "EGM2008" in terr_492["source"]["vertical_datum"]
    assert terr_492["quality"]["cells_in_field"] > 100

    # 4. Verificar que la malla 3D se genera correctamente sin conexión para ambos
    r_mesh = client.get(f"/api/v1/fields/{f_492_id}/terrain/mesh?max_size=120")
    assert r_mesh.status_code == 200
    assert len(r_mesh.json()["z"]) > 100


def test_user_field_offline_returns_clear_message_not_generic_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    """Verifica que un lote del usuario sin internet devuelva un mensaje claro sin inventar relieve sintético."""
    # 1. Simular falla total de red (offline)
    def offline_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network unreachable (offline test)")

    offline_client = httpx.Client(transport=httpx.MockTransport(offline_handler))
    monkeypatch.setattr(geonet, "_cliente", offline_client)
    monkeypatch.setattr(geonet, "client", lambda: offline_client)

    # 2. Importar lote genérico de usuario (no es lote de ejemplo)
    user_geojson = json.dumps(synthetic_square_field_geojson()).encode("utf-8")
    r = client.post(
        "/api/v1/fields/import",
        files={"file": ("lote_usuario_custom.geojson", user_geojson, "application/geo+json")},
        data={"default_name": "Lote Usuario Sin Red"},
    )
    assert r.status_code == 201
    user_field_id = r.json()["fields"][0]["id"]

    # 3. Intentar procesar relieve sin conexión
    r_terr = client.post(
        f"/api/v1/fields/{user_field_id}/terrain/process",
        data={"source_id": "copernicus_glo30", "buffer_m": "300"},
    )
    # No debe responder 422 genérico sino 503 con mensaje claro de falta de conexión
    assert r_terr.status_code == 503
    assert "Sin conexión: no se pudo descargar el relieve" in r_terr.json()["detail"]
