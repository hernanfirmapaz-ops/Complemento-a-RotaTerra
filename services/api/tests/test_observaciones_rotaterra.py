"""Spec 011: salida para Rotaterra en el contrato `Observacion` de N4-4-1.2 (sin internet)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from geoprocessing.tests.fixtures.synthetic_dem import (
    synthetic_square_field_geojson,
    write_synthetic_inclined_plane_utm,
)
from services.api.app.core import config
from services.api.app.main import app
from services.api.app.services import store

CAMPOS = {"lote_id", "fecha", "variable", "valor", "unidad", "fuente", "resolucion_m", "calidad", "nota"}


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "runs")
    monkeypatch.setattr(store, "DATA_DIR", tmp_path / "runs")
    return TestClient(app)


def _importar_lote(api: TestClient) -> str:
    r = api.post(
        "/api/v1/fields/import",
        files={"file": ("lote.geojson", json.dumps(synthetic_square_field_geojson()).encode(), "application/geo+json")},
    )
    assert r.status_code == 201, r.text
    return r.json()["fields"][0]["id"]


def _validar_contrato(obs: list[dict]) -> None:
    """Misma forma que rotaterra/contrato.py de N4-4-1.2."""
    for o in obs:
        assert set(o) == CAMPOS
        date.fromisoformat(o["fecha"])
        assert o["valor"] is None or isinstance(o["valor"], (int, float))
        assert 1 <= len(o["fuente"]) <= 32
        assert isinstance(o["resolucion_m"], int)
        assert o["calidad"] in ("buena", "dudosa", "descartada")
        if o["valor"] is None:
            assert o["calidad"] == "descartada" and o["nota"], o


def test_lote_sin_calculos_no_inventa_valores(api: TestClient):
    field_id = _importar_lote(api)
    r = api.get(f"/api/v1/fields/{field_id}/observaciones")
    assert r.status_code == 200, r.text
    obs = r.json()
    _validar_contrato(obs)
    por_var = {o["variable"]: o for o in obs}
    for variable in ("pendiente_media_pct", "escurrimiento_mm", "area_encharcada_ha", "perdida_suelo_t_ha",
                     "grupo_hidrologico"):
        assert por_var[variable]["valor"] is None
        assert por_var[variable]["calidad"] == "descartada"


def test_lote_completo_entrega_valores_reales(api: TestClient, tmp_path: Path):
    field_id = _importar_lote(api)
    dem = write_synthetic_inclined_plane_utm(
        tmp_path / "dem.tif", slope_east=0.01, slope_south=0.015, pixel_m=10.0, width=220, height=220
    )
    with dem.open("rb") as fh:
        r = api.post(
            f"/api/v1/fields/{field_id}/terrain/process",
            files={"file": ("dem.tif", fh, "image/tiff")},
            data={"source_id": "upload", "buffer_m": "100", "source_name": "DEM sintético (TEST)",
                  "surface_type": "DTM", "vertical_datum": "EGM2008", "vertical_accuracy_m": "0.1"},
        )
    assert r.status_code == 200, r.text
    assert api.post(f"/api/v1/fields/{field_id}/hydrology/static", json={}).status_code == 200
    ev = api.post(f"/api/v1/fields/{field_id}/hydrology/rainfall-events",
                  json={"name": "Tormenta 80 mm", "total_mm": 80.0, "source_type": "manual"}).json()
    run = api.post(f"/api/v1/fields/{field_id}/hydrology/runoff-runs",
                   json={"name": "80 mm", "rainfall_event_id": ev["id"], "soil_group": "B",
                         "cover_code": "soja_maiz_sd_buena", "antecedent_moisture": "medium"})
    assert run.status_code == 201, run.text
    tk = api.post(f"/api/v1/fields/{field_id}/hydrology/toolkit/run",
                  json={"soil_group": "B", "cover_code": "soja_maiz_sd_buena", "storm_precipitation_mm": 80.0})
    assert tk.status_code == 200, tk.text

    obs = api.get(f"/api/v1/fields/{field_id}/observaciones").json()
    _validar_contrato(obs)
    v = {o["variable"]: o for o in obs}

    # Pendiente real del plano sintético: hipotenusa de 1 % y 1,5 % ≈ 1,8 %
    assert v["pendiente_media_pct"]["valor"] == pytest.approx(1.8, abs=0.2)
    assert v["pendiente_media_pct"]["fuente"] == "DEM sintético (TEST)"
    assert v["lluvia_evento_mm"]["valor"] == pytest.approx(80.0)
    assert v["lluvia_evento_mm"]["calidad"] == "dudosa"  # tormenta de diseño, no medida
    assert v["escurrimiento_mm"]["valor"] == pytest.approx(run.json()["cn_result"]["runoff_q_mm"])
    assert v["perdida_suelo_t_ha"]["valor"] == pytest.approx(tk.json()["erosion_usle"]["mean_soil_loss_t_ha"])
    # Sin simulación 2D el área encharcada no se estima con fórmulas aproximadas
    assert v["area_encharcada_ha"]["valor"] is None
    assert "2D" in v["area_encharcada_ha"]["nota"]
    # Sin consulta de suelo: no se inventa
    assert v["grupo_hidrologico"]["valor"] is None


def test_corrida_inexistente_devuelve_404(api: TestClient):
    field_id = _importar_lote(api)
    assert api.get(f"/api/v1/fields/{field_id}/observaciones", params={"run_id": "no-existe"}).status_code == 404
