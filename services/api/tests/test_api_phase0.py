"""Tests de integración de la API FastAPI (Fase 0) usando un DEM sintético etiquetado."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from geoprocessing.tests.fixtures.synthetic_dem import (
    synthetic_square_field_geojson,
    write_synthetic_inclined_plane_utm,
)
from services.api.app.core import config
from services.api.app.main import app
from services.api.app.services import store, terrain


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "runs")
    monkeypatch.setattr(store, "DATA_DIR", tmp_path / "runs")
    terrain._cargar.cache_clear()
    return TestClient(app)


def test_health_and_full_phase0_flow(client: TestClient, tmp_path: Path):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["phase"] == "fase-0-prueba-geoespacial"

    # 1. Importar lote sintético
    geojson_bytes = json.dumps(synthetic_square_field_geojson()).encode("utf-8")
    r = client.post(
        "/api/v1/fields/import",
        files={"file": ("lote_sintetico.geojson", geojson_bytes, "application/geo+json")},
        data={"default_name": "Lote Sintético"},
    )
    assert r.status_code == 201, r.text
    field = r.json()["fields"][0]
    field_id = field["id"]
    assert field["utm_epsg"] == 32720
    assert field["has_terrain"] is False

    # 2. Subir DEM sintético (plano inclinado 3% E, 4% S -> 5.0% pendiente total)
    dem_path = write_synthetic_inclined_plane_utm(
        tmp_path / "dem_sintetico.tif", slope_east=0.03, slope_south=0.04, pixel_m=10.0, width=220, height=220
    )
    with dem_path.open("rb") as fh:
        r = client.post(
            f"/api/v1/fields/{field_id}/terrain/process",
            files={"file": ("dem_sintetico.tif", fh, "image/tiff")},
            data={
                "source_id": "upload",
                "buffer_m": "100",
                "source_name": "DEM Sintético Plano Inclinado (TEST)",
                "surface_type": "DTM",
                "vertical_datum": "EGM2008",
                "vertical_accuracy_m": "0.1",
                "acquisition_date": "2026-01-01",
            },
        )
    assert r.status_code == 200, r.text
    terr = r.json()
    assert terr["quality"]["pixel_size_m"] == 10.0
    assert terr["quality"]["cells_in_field"] > 500
    assert terr["source"]["surface_type"] == "DTM"

    # 3. Malla 3D
    r = client.get(f"/api/v1/fields/{field_id}/terrain/mesh?max_size=120")
    assert r.status_code == 200
    malla = r.json()
    assert malla["rows"] > 10 and malla["cols"] > 10
    assert len(malla["z"]) == malla["rows"] * malla["cols"]
    assert len(malla["boundary"]) == 1

    # 4. Consulta de punto en el centroide: pendiente debe ser 5.0 %
    lon, lat = field["centroid"]
    r = client.get(f"/api/v1/fields/{field_id}/terrain/point", params={"lon": lon, "lat": lat})
    assert r.status_code == 200
    pt = r.json()
    assert pt["inside_field"] is True
    assert pt["slope_pct"] == pytest.approx(5.0, abs=0.05)

    # 5. Perfil altimétrico
    oeste, sur, este, norte = field["bbox"]
    r = client.post(
        f"/api/v1/fields/{field_id}/terrain/profile",
        json={"coordinates": [[oeste, sur], [este, norte]]},
    )
    assert r.status_code == 200
    pf = r.json()
    assert pf["summary"]["length_m"] > 1000
    assert pf["summary"]["valid_samples"] == pf["summary"]["samples"]
