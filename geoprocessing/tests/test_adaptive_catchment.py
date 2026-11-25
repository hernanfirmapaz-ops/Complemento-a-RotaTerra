"""Tests unitarios y de integración para la delimitación de cuenca adaptativa y truncamiento (Spec 032 §2 / Issue #114).

Verifica:
1. Cuenca cerrada en recorte de 3 km (no toca borde, no se expande).
2. Expansión adaptativa 3 -> 5 -> 10 km cuando la divisoria toca el borde.
3. Cuenca truncada a 10 km: bandera upstream_catchment_truncated = True, advertencia visible y penalización de -0,15 en el indicador de confianza.
4. Respeto de MAX_CELDAS en prepare_dem con remuestreo declarado fuera del lote.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from affine import Affine

from geoprocessing.agronomy.erosion_usle import compute_usle_erosion_and_gullies
from geoprocessing.dem.prepare import prepare_dem
from geoprocessing.dem.terrain import Dem, slope_aspect
from geoprocessing.hydrology.catchment import (
    build_active_catchment_mask,
    resolve_adaptive_margin_steps,
    trace_upslope_catchment,
)
from geoprocessing.hydrology.confidence import compute_confidence_indicator
from geoprocessing.hydrology.flow import d8_direction_and_accumulation, mfd_accumulation
from geoprocessing.hydrology.shallow_water_2d import run_2d_diffusive_wave_simulation
from geoprocessing.rainfall.nrcs_cn import compute_nrcs_cn, distribute_event_runoff_mfd
from geoprocessing.supuestos import (
    SUPUESTO_CUENCA_DILATACION_CELDAS,
    SUPUESTO_CUENCA_DOWNSTREAM_BUFFER_M,
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
        max_margin_km=float(SUPUESTO_CUENCA_MARGEN_MAXIMO_KM.valor),
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
        max_margin_km=float(SUPUESTO_CUENCA_MARGEN_MAXIMO_KM.valor),
    )
    assert res_3k.touches_border
    assert not res_3k.is_truncated
    assert res_3k.warning is None
    assert res_3k.external_area_ha > 0.0

    # 2. A margen máximo sigue tocando el borde -> is_truncated=True y genera advertencia
    max_m_km = float(SUPUESTO_CUENCA_MARGEN_MAXIMO_KM.valor)
    res_max = trace_upslope_catchment(
        d8_code=d8,
        mascara_lote=mascara_lote,
        pixel_size_m=30.0,
        current_margin_km=max_m_km,
        max_margin_km=max_m_km,
    )
    assert res_max.touches_border
    assert res_max.is_truncated
    assert res_max.warning is not None
    assert f"truncada a {int(max_m_km)} km" in res_max.warning
    assert "piso mínimo" in res_max.warning


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


def test_build_active_catchment_mask_includes_catchment_lot_and_downstream():
    """Verifica que la máscara activa una la cuenca aguas arriba, el lote y la franja aguas abajo."""
    alto, ancho = 30, 30
    d8 = np.ones((alto, ancho), dtype=np.uint8)  # todo fluye hacia el este (código 1)

    # Lote en columnas 10..14, filas 12..16
    mascara_lote = np.zeros((alto, ancho), dtype=bool)
    mascara_lote[12:17, 10:15] = True

    # Cuenca de aporte (columnas 5..9 fluyen hacia el lote)
    catchment_mask = np.zeros((alto, ancho), dtype=bool)
    catchment_mask[12:17, 5:10] = True

    active = build_active_catchment_mask(
        catchment_mask=catchment_mask,
        mascara_lote=mascara_lote,
        d8_code=d8,
        pixel_size_m=30.0,
        downstream_buffer_m=150.0,  # ~5 celdas aguas abajo
        dilation_cells=1,
    )

    # El lote completo debe estar activo
    assert np.all(active[mascara_lote])
    # La cuenca de aporte completa debe estar activa
    assert np.all(active[catchment_mask])
    # Debe haber celdas aguas abajo (este de columna 14) activas
    assert np.any(active[12:17, 15:20])
    # Las esquinas distantes deben estar inactivas (enmascaradas)
    assert not active[0, 0]
    assert not active[29, 29]
    assert not active[0, 29]
    assert not active[29, 0]


def test_catchment_active_mask_hydraulic_and_erosion_equivalence():
    """Test de equivalencia: verifica que enmascarar el dominio activo (cuenca de aporte + lote + aguas abajo)
    reproduce con exactitud (< 1 % de diferencia) los resultados hidrológicos y agronómicos dentro del lote:
    - ha anegadas (con bajo activo encharcable > 0 ha),
    - volumen retenido y volumen que entra por escorrentía externa (> 0 m³),
    - pérdida de suelo USLE (t/ha > 0).
    """
    alto, ancho = 40, 40
    r, c = np.indices((alto, ancho), dtype=float)

    # Valle central con fondo en fila 20, con pendiente suave hacia el este (c * 0.5)
    # Divisoria topográfica norte en fila 8 y sur en fila 32
    z = 520.0 - c * 0.5 + np.abs(r - 20.0) * 1.5

    # Al norte de fila 8 cae hacia el borde exterior norte (fuera de la cuenca del lote)
    z[0:9, :] = 520.0 - c[0:9, :] * 0.5 + (20.0 - 8.0) * 1.5 + (8.0 - r[0:9, :]) * 2.0
    # Al sur de fila 32 cae hacia el borde exterior sur (fuera de la cuenca del lote)
    z[32:40, :] = 520.0 - c[32:40, :] * 0.5 + (32.0 - 20.0) * 1.5 + (r[32:40, :] - 32.0) * 2.0

    # Lote en el centro del valle (filas 15..25, columnas 20..30)
    mascara_lote = np.zeros((alto, ancho), dtype=bool)
    mascara_lote[15:26, 20:31] = True

    # Bajo o cubeta encharcable dentro del lote (filas 18..22, columnas 23..27)
    z[18:22, 23:27] -= 2.5

    transform = Affine.translation(300000.0, 6330000.0) @ Affine.scale(30.0, -30.0)
    dem = Dem(z=z.astype("float32"), transform=transform, crs="EPSG:32720")

    # Dirección y acumulación D8
    d8_code, _, _, _ = d8_direction_and_accumulation(z, 30.0)

    # Trazado de cuenca vertiente completa aguas arriba
    max_m_km = float(SUPUESTO_CUENCA_MARGEN_MAXIMO_KM.valor)
    catch = trace_upslope_catchment(
        d8_code=d8_code,
        mascara_lote=mascara_lote,
        pixel_size_m=30.0,
        current_margin_km=3.0,
        max_margin_km=max_m_km,
    )
    assert catch.external_area_ha > 0.0, "Debe existir área de aporte externa drenando al lote."

    # Construcción de la máscara de dominio activo usando supuestos calibrables
    downstream_m = float(SUPUESTO_CUENCA_DOWNSTREAM_BUFFER_M.valor)
    dilation_c = int(SUPUESTO_CUENCA_DILATACION_CELDAS.valor)
    active = build_active_catchment_mask(
        catchment_mask=catch.mask,
        mascara_lote=mascara_lote,
        d8_code=d8_code,
        pixel_size_m=30.0,
        downstream_buffer_m=downstream_m,
        dilation_cells=dilation_c,
    )

    # La máscara reduce el dominio descartando laderas exteriores no aportantes
    assert active.sum() < z.size
    assert active.sum() > mascara_lote.sum()

    # Tormenta de diseño para activar escorrentía e inundar la cubeta
    intervals = [{"timestamp": "2026-11-18T14:00:00-03:00", "precipitation_mm": 60.0, "interval_minutes": 30}]

    # 1. Simulación hidrodinámica 2D: Sin máscara (dominio completo) vs Con active_mask
    s_full = run_2d_diffusive_wave_simulation(
        dem=dem,
        z_cond=z,
        mascara_lote=mascara_lote,
        intervals=intervals,
        cn_ii_base=78.0,
        antecedent_moisture="average",
        lambda_ratio=0.2,
        active_mask=None,
        ponding_threshold_m=0.05,
        manning_n=0.04,
        solver_mode="diffusive",
    )
    s_mask = run_2d_diffusive_wave_simulation(
        dem=dem,
        z_cond=z,
        mascara_lote=mascara_lote,
        intervals=intervals,
        cn_ii_base=78.0,
        antecedent_moisture="average",
        lambda_ratio=0.2,
        active_mask=active,
        ponding_threshold_m=0.05,
        manning_n=0.04,
        solver_mode="diffusive",
    )

    ha_full = s_full["summary"]["ponded_area_in_field_ha"]
    ha_mask = s_mask["summary"]["ponded_area_in_field_ha"]
    vol_full = s_full["summary"]["ponded_retained_volume_in_field_m3"]
    vol_mask = s_mask["summary"]["ponded_retained_volume_in_field_m3"]

    # El bajo en el lote debe registrar anegamiento positivo
    assert ha_full > 0.0, "El lote con cubeta debe registrar hectáreas anegadas."
    assert vol_full > 0.0, "El lote con cubeta debe registrar volumen de agua retenido."

    # Tolerancia estricta < 1% entre corrida completa y corrida enmascarada
    rel_diff_ha = abs(ha_full - ha_mask) / ha_full
    rel_diff_vol = abs(vol_full - vol_mask) / vol_full
    assert rel_diff_ha < 0.01, f"Diferencia en ha anegadas ({rel_diff_ha:.4%}) supera el 1 %."
    assert rel_diff_vol < 0.01, f"Diferencia en volumen retenido ({rel_diff_vol:.4%}) supera el 1 %."

    # 2. Volumen de escorrentía externa que entra al lote
    cn_res = compute_nrcs_cn(precipitation_mm=60.0, cn_ii_base=78.0, antecedent_moisture="average")
    _, mfd_area, _ = mfd_accumulation(z, 30.0)
    _, _, dist_full = distribute_event_runoff_mfd(
        cn_result=cn_res,
        mfd_area_m2=mfd_area,
        mascara_lote=mascara_lote,
        pixel_size_m=30.0,
        depression_volume_in_field_m3=vol_full,
        external_inflow_ha=catch.external_area_ha,
    )
    assert dist_full["external_runoff_inflow_m3"] > 0.0

    # 3. Erosión hídrica USLE dentro del lote: Sin máscara vs Con active_mask
    slopes, _, _ = slope_aspect(z, 30.0, 30.0)
    spi = np.zeros_like(z)
    _, e_full = compute_usle_erosion_and_gullies(
        mfd_area_m2=mfd_area,
        slope_pct=slopes,
        spi=spi,
        mascara_lote=mascara_lote,
        pixel_size_m=30.0,
        precipitation_mm=60.0,
        runoff_q_mm=cn_res.runoff_q_mm,
        sand_pct=40.0,
        silt_pct=40.0,
        clay_pct=20.0,
        active_mask=None,
    )
    _, e_mask = compute_usle_erosion_and_gullies(
        mfd_area_m2=mfd_area,
        slope_pct=slopes,
        spi=spi,
        mascara_lote=mascara_lote,
        pixel_size_m=30.0,
        precipitation_mm=60.0,
        runoff_q_mm=cn_res.runoff_q_mm,
        sand_pct=40.0,
        silt_pct=40.0,
        clay_pct=20.0,
        active_mask=active,
    )

    loss_full = e_full["mean_soil_loss_t_ha"]
    loss_mask = e_mask["mean_soil_loss_t_ha"]
    assert loss_full > 0.0, "Debe registrarse pérdida de suelo positiva."
    rel_diff_loss = abs(loss_full - loss_mask) / loss_full
    assert rel_diff_loss < 0.01, f"Diferencia en USLE ({rel_diff_loss:.4%}) supera el 1 %."


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

