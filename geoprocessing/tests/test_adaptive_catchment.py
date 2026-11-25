"""Tests unitarios y de integración para la delimitación de cuenca adaptativa y truncamiento (Spec 032 §2 / Issue #114).

Verifica:
1. Cuenca cerrada en recorte de 3 km (no toca borde, no se expande).
2. Expansión adaptativa 3 -> 5 -> 10 km cuando la divisoria toca el borde.
3. Cuenca truncada a 10 km: bandera upstream_catchment_truncated = True, advertencia visible y penalización de -0,15 en el indicador de confianza.
4. Respeto de MAX_CELDAS en prepare_dem con remuestreo declarado fuera del lote.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from geoprocessing.dem.prepare import MAX_CELDAS, PreparedDem, prepare_dem
from geoprocessing.hydrology.catchment import (
    CatchmentResult,
    resolve_adaptive_margin_steps,
    trace_upslope_catchment,
)
from geoprocessing.hydrology.confidence import compute_confidence_indicator
from geoprocessing.supuestos import (
    SUPUESTO_CUENCA_MARGEN_EXPANSION_KM,
    SUPUESTO_CUENCA_MARGEN_INICIAL_KM,
    SUPUESTO_CUENCA_MARGEN_MAXIMO_KM,
    SUPUESTO_CUENCA_TRUNCADA_PENALIZACION_CONFIANZA,
)


def test_adaptive_margin_steps_values():
    """Verifica que los pasos adaptativos coincidan con los supuestos configurables (3, 5 y 10 km)."""
    steps = resolve_adaptive_margin_steps()
    assert steps == [
        float(SUPUESTO_CUENCA_MARGEN_INICIAL_KM.valor) * 1000.0,
        float(SUPUESTO_CUENCA_MARGEN_EXPANSION_KM.valor) * 1000.0,
        float(SUPUESTO_CUENCA_MARGEN_MAXIMO_KM.valor) * 1000.0,
    ]
    assert steps == [3000.0, 5000.0, 10000.0]


def test_catchment_closed_does_not_touch_border():
    """Cuenca en una lomada/divisoria local: el flujo se aleja del lote, no toca el borde exterior."""
    alto, ancho = 30, 30
    # Celdas del oeste fluyen al oeste (código 16), celdas del este al este (código 1)
    d8 = np.ones((alto, ancho), dtype=np.uint8)  # default fluye al este
    d8[:, :15] = 16  # mitad oeste fluye al oeste

    # Lote en el centro de la divisoria (filas 10..20, columnas 14..16)
    mascara_lote = np.zeros((alto, ancho), dtype=bool)
    mascara_lote[10:20, 14:17] = True

    res = trace_upslope_catchment(
        d8_code=d8,
        mascara_lote=mascara_lote,
        pixel_size_m=30.0,
        current_margin_km=3.0,
        max_margin_km=10.0,
    )

    assert not res.touches_border
    assert not res.is_truncated
    assert res.warning is None
    assert res.in_field_area_ha > 0.0
    assert res.external_area_ha == 0.0


def test_catchment_open_touches_border_and_truncates_at_max_margin():
    """Cuenca abierta donde el flujo atraviesa desde el borde del ráster hacia el lote."""
    alto, ancho = 20, 20
    # Todo el escurrimiento fluye de izquierda a derecha (código 1 = este)
    d8 = np.ones((alto, ancho), dtype=np.uint8)

    # Lote en la mitad derecha (filas 8..12, columnas 14..18)
    mascara_lote = np.zeros((alto, ancho), dtype=bool)
    mascara_lote[8:13, 14:19] = True

    # 1. A 3 km toca el borde pero aún no está en el margen máximo -> touches_border=True, is_truncated=False
    res_3k = trace_upslope_catchment(
        d8_code=d8,
        mascara_lote=mascara_lote,
        pixel_size_m=30.0,
        current_margin_km=3.0,
        max_margin_km=10.0,
    )
    assert res_3k.touches_border
    assert not res_3k.is_truncated
    assert res_3k.warning is None
    assert res_3k.external_area_ha > 0.0

    # 2. A 10 km (margen máximo) sigue tocando el borde -> is_truncated=True y genera advertencia
    res_10k = trace_upslope_catchment(
        d8_code=d8,
        mascara_lote=mascara_lote,
        pixel_size_m=30.0,
        current_margin_km=10.0,
        max_margin_km=10.0,
    )
    assert res_10k.touches_border
    assert res_10k.is_truncated
    assert res_10k.warning is not None
    assert "truncada a 10 km" in res_10k.warning
    assert "piso mínimo" in res_10k.warning


def test_confidence_indicator_penalizes_truncated_catchment():
    """El indicador de confianza debe penalizar 0,15 puntos y degradar el nivel si la cuenca está truncada."""
    # Línea base normal
    conf_base = compute_confidence_indicator(
        source_id="copernicus_glo30",
        resolution_m=30.0,
        mean_slope_pct=3.0,
        soil_source="soilgrids_direct",
        rain_source_type="smn_observed",
        upstream_catchment_truncated=False,
    )

    # Con cuenca truncada
    conf_trunc = compute_confidence_indicator(
        source_id="copernicus_glo30",
        resolution_m=30.0,
        mean_slope_pct=3.0,
        soil_source="soilgrids_direct",
        rain_source_type="smn_observed",
        upstream_catchment_truncated=True,
    )

    expected_penalty = float(SUPUESTO_CUENCA_TRUNCADA_PENALIZACION_CONFIANZA.valor)
    assert round(conf_base["score"] - conf_trunc["score"], 2) == round(expected_penalty, 2)
    assert conf_trunc["level"] in ("medio", "bajo")
    assert any("truncada" in r.lower() for r in conf_trunc["reasons"])


def test_prepare_dem_respects_max_celdas_and_declares_resampling(tmp_path: Path):
    """Verifica que prepare_dem remuestree fuera del lote cuando se superaría MAX_CELDAS."""
    import rasterio
    from rasterio.transform import from_origin

    # Crear GeoTIFF fuente sintético que cubra el lote
    tif_src = tmp_path / "src_dem.tif"
    transform = from_origin(300000.0, 6330000.0, 30.0, 30.0)
    data = np.full((300, 300), 500.0, dtype="float32")
    with rasterio.open(
        tif_src,
        "w",
        driver="GTiff",
        height=300,
        width=300,
        count=1,
        dtype="float32",
        crs="EPSG:32720",
        transform=transform,
    ) as dst:
        dst.write(data, 1)

    # Lote de prueba
    geom_4326 = {
        "type": "Polygon",
        "coordinates": [[
            [-65.10, -33.20],
            [-65.09, -33.20],
            [-65.09, -33.21],
            [-65.10, -33.21],
            [-65.10, -33.20],
        ]],
    }

    # Probar con un buffer normal (3000 m): celdas no superan MAX_CELDAS
    dest_normal = tmp_path / "normal_prep.tif"
    prep_norm = prepare_dem(tif_src, geom_4326, 32720, 3000.0, dest_normal)
    assert not prep_norm.resampling_outside_field
    assert prep_norm.resampled_resolution_m is None

    # Simular un límite de celdas bajo para testear la adaptación de resolución
    import geoprocessing.dem.prepare as prep_module
    old_max = prep_module.MAX_CELDAS
    try:
        prep_module.MAX_CELDAS = 1000  # forzar que la ventana requiera remuestreo
        dest_resampled = tmp_path / "resampled_prep.tif"
        prep_resamp = prep_module.prepare_dem(tif_src, geom_4326, 32720, 3000.0, dest_resampled)
        assert prep_resamp.resampling_outside_field
        assert prep_resamp.resampled_resolution_m is not None
        assert prep_resamp.pixel_size_m > prep_norm.pixel_size_m

        # Verificar tags en el archivo generado
        with rasterio.open(dest_resampled) as r_dst:
            tags = r_dst.tags()
            assert tags.get("RESAMPLING_OUTSIDE_FIELD") == "bilinear"
            assert "PIXEL_SIZE_OUTSIDE_FIELD_M" in tags
    finally:
        prep_module.MAX_CELDAS = old_max


def test_api_terrain_process_adaptive_catchment_integration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verifica la integración completa API de terreno e hidrología con cuenca adaptativa."""
    import httpx
    from fastapi.testclient import TestClient
    from geoprocessing import net as geonet
    from services.api.app.core import config
    from services.api.app.main import app
    from services.api.app.services import store, terrain

    # Aislar entorno de almacenamiento
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "runs")
    monkeypatch.setattr(store, "DATA_DIR", tmp_path / "runs")
    terrain._cargar.cache_clear()

    # Simular transporte offline
    def offline_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network unreachable (offline test)")

    offline_client = httpx.Client(transport=httpx.MockTransport(offline_handler))
    monkeypatch.setattr(geonet, "_cliente", offline_client)
    monkeypatch.setattr(geonet, "client", lambda: offline_client)

    client = TestClient(app)

    # Importar lote de ejemplo
    data_sample_dir = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "lotes"
    geojson_205 = (data_sample_dir / "san_luis_parcela_205.geojson").read_bytes()
    r = client.post(
        "/api/v1/fields/import",
        files={"file": ("san_luis_parcela_205.geojson", geojson_205, "application/geo+json")},
        data={"default_name": "Parcela Rural 205 (San Luis)"},
    )
    assert r.status_code == 201
    f_id = r.json()["fields"][0]["id"]

    # Procesar terreno con margen adaptativo por defecto
    r_terr = client.post(
        f"/api/v1/fields/{f_id}/terrain/process",
        data={"source_id": "copernicus_glo30", "adaptive_catchment": "true"},
    )
    assert r_terr.status_code == 200, r_terr.text
    terr = r_terr.json()
    assert "catchment" in terr
    assert "touches_border" in terr["catchment"]
    assert "is_truncated" in terr["catchment"]

    # Ejecutar hidrología estática
    r_hydro = client.post(f"/api/v1/fields/{f_id}/hydrology/static", json={"conditioning_mode": "preserve"})
    assert r_hydro.status_code == 200, r_hydro.text
    hydro = r_hydro.json()
    assert "upstream_catchment_truncated" in hydro["summary"]
    assert "upstream_catchment_margin_km" in hydro["summary"]
    assert "upstream_catchment_touches_border" in hydro["summary"]

