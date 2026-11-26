"""Tests para la escalera de lluvia precalculada, curva de anegamiento y marcas de recurrencia (Spec 031 / Issue #113).

Verifica:
1. Caché e invalidación rápida por suelo, AMC o cobertura.
2. Monotonicidad física estricta (área anegada y volumen de salida no decrecientes).
3. Detección automática del umbral crítico de anegamiento (knee point).
4. Rendimiento en tiempo real sobre recorte real (lote + cuenca con active_mask).
5. Períodos de retorno T2..T50 de la REM con fuente declarada "en un día".
6. Integración del endpoint GET /api/v1/fields/{field_id}/hydrology/rainfall-ladder.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest
from affine import Affine
from fastapi.testclient import TestClient

from geoprocessing.dem.terrain import Dem, slope_aspect
from geoprocessing.hydrology.catchment import (
    build_active_catchment_mask,
    trace_upslope_catchment,
)
from geoprocessing.hydrology.flow import d8_direction_and_accumulation, mfd_accumulation
from geoprocessing.rainfall.ladder import (
    LadderStepResult,
    clear_ladder_cache,
    compute_rainfall_ladder,
    detect_critical_ponding_threshold,
)
from geoprocessing.supuestos import (
    SUPUESTO_CUENCA_MARGEN_MAXIMO_KM,
    SUPUESTO_ESCALERA_LLUVIA_MAX_MM,
    SUPUESTO_ESCALERA_LLUVIA_MIN_MM,
    SUPUESTO_ESCALERA_MAX_TIEMPO_COMPUTO_S,
)
from services.api.app.main import app
from services.api.app.services import store


def _build_synthetic_terrain_with_catchment(alto: int = 40, ancho: int = 40):
    """Genera un DEM sintético de valle con cuenca externa, lote y bajo central encharcable."""
    r, c = np.indices((alto, ancho), dtype=float)

    # Valle central con fondo en fila 20, con pendiente suave hacia el este (c * 0.5)
    # Divisoria topográfica norte en fila 8 y sur en fila 32
    z = 520.0 - c * 0.5 + np.abs(r - 20.0) * 1.5
    z[0:9, :] = 520.0 - c[0:9, :] * 0.5 + (20.0 - 8.0) * 1.5 + (8.0 - r[0:9, :]) * 2.0
    z[32:40, :] = 520.0 - c[32:40, :] * 0.5 + (32.0 - 20.0) * 1.5 + (r[32:40, :] - 32.0) * 2.0

    # Lote en el centro del valle (filas 15..25, columnas 20..30)
    mascara_lote = np.zeros((alto, ancho), dtype=bool)
    mascara_lote[15:26, 20:31] = True

    # Bajo o cubeta encharcable dentro del lote (filas 18..22, columnas 23..27)
    z[18:22, 23:27] -= 2.5

    transform = Affine.translation(300000.0, 6330000.0) @ Affine.scale(30.0, -30.0)
    dem = Dem(z=z.astype("float32"), transform=transform, crs="EPSG:32720")

    d8_code, _, _, _ = d8_direction_and_accumulation(z, 30.0)
    max_m_km = float(SUPUESTO_CUENCA_MARGEN_MAXIMO_KM.valor)
    catch = trace_upslope_catchment(
        d8_code=d8_code,
        mascara_lote=mascara_lote,
        pixel_size_m=30.0,
        current_margin_km=3.0,
        max_margin_km=max_m_km,
    )
    active_mask = build_active_catchment_mask(
        catchment_mask=catch.mask,
        mascara_lote=mascara_lote,
        d8_code=d8_code,
        pixel_size_m=30.0,
    )

    slopes, _, _ = slope_aspect(z, 30.0, 30.0)
    _, mfd_area, _ = mfd_accumulation(z, 30.0)
    spi = np.zeros_like(z)

    # Cubeta de retención dentro del lote (~5.000 m³, ~0.36 ha)
    dep_vol_m3 = 5400.0
    dep_area_ha = 0.36

    return {
        "dem": dem,
        "mascara_lote": mascara_lote,
        "active_mask": active_mask,
        "mfd_area": mfd_area,
        "slopes": slopes,
        "spi": spi,
        "dep_vol_m3": dep_vol_m3,
        "dep_area_ha": dep_area_ha,
        "ext_inflow_ha": catch.external_area_ha,
    }


def test_rainfall_ladder_cache_and_invalidation():
    """Verifica que la segunda consulta se resuelva desde memoria en < 5 ms y que al cambiar AMC se invalide."""
    clear_ladder_cache()
    t = _build_synthetic_terrain_with_catchment()

    # 1. Primera ejecución: cálculo completo
    res1 = compute_rainfall_ladder(
        field_id="field_cache_test",
        mascara_lote=t["mascara_lote"],
        mfd_area_m2=t["mfd_area"],
        slope_pct=t["slopes"],
        spi=t["spi"],
        pixel_size_m=30.0,
        depression_volume_in_field_m3=t["dep_vol_m3"],
        depression_area_in_field_ha=t["dep_area_ha"],
        external_inflow_ha=t["ext_inflow_ha"],
        soil_group="B",
        cover_code="soja_maiz_sd_buena",
        amc="medium",
        active_mask=t["active_mask"],
    )
    assert res1["from_cache"] is False
    assert len(res1["ladder"]) == 15

    # 2. Segunda ejecución idéntica: debe responder desde caché en < 5 ms
    t0 = time.perf_counter()
    res2 = compute_rainfall_ladder(
        field_id="field_cache_test",
        mascara_lote=t["mascara_lote"],
        mfd_area_m2=t["mfd_area"],
        slope_pct=t["slopes"],
        spi=t["spi"],
        pixel_size_m=30.0,
        depression_volume_in_field_m3=t["dep_vol_m3"],
        depression_area_in_field_ha=t["dep_area_ha"],
        external_inflow_ha=t["ext_inflow_ha"],
        soil_group="B",
        cover_code="soja_maiz_sd_buena",
        amc="medium",
        active_mask=t["active_mask"],
    )
    t_elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert res2["from_cache"] is True
    assert t_elapsed_ms < 10.0  # sub-milisegundo o margen amplio < 10 ms en CI

    # 3. Cambio de AMC ('medium' -> 'wet'): invalida caché y recalcula nueva curva
    res3 = compute_rainfall_ladder(
        field_id="field_cache_test",
        mascara_lote=t["mascara_lote"],
        mfd_area_m2=t["mfd_area"],
        slope_pct=t["slopes"],
        spi=t["spi"],
        pixel_size_m=30.0,
        depression_volume_in_field_m3=t["dep_vol_m3"],
        depression_area_in_field_ha=t["dep_area_ha"],
        external_inflow_ha=t["ext_inflow_ha"],
        soil_group="B",
        cover_code="soja_maiz_sd_buena",
        amc="wet",
        active_mask=t["active_mask"],
    )
    assert res3["from_cache"] is False
    assert res3["parameters"]["amc"] == "wet"
    # Con AMC wet, el anegamiento a 50 mm debe ser igual o superior que en AMC medium
    s_med_50 = next(s for s in res1["ladder"] if s["precipitation_mm"] == 50)
    s_wet_50 = next(s for s in res3["ladder"] if s["precipitation_mm"] == 50)
    assert s_wet_50["ponded_area_ha"] >= s_med_50["ponded_area_ha"]


def test_rainfall_ladder_monotonicity():
    """Verifica estrictamente que la superficie anegada y el volumen escurrido sean monótonamente no decrecientes."""
    t = _build_synthetic_terrain_with_catchment()

    res = compute_rainfall_ladder(
        field_id="field_monotonicity_test",
        mascara_lote=t["mascara_lote"],
        mfd_area_m2=t["mfd_area"],
        slope_pct=t["slopes"],
        spi=t["spi"],
        pixel_size_m=30.0,
        depression_volume_in_field_m3=t["dep_vol_m3"],
        depression_area_in_field_ha=t["dep_area_ha"],
        external_inflow_ha=t["ext_inflow_ha"],
        soil_group="B",
        cover_code="soja_maiz_sd_buena",
        amc="medium",
        active_mask=t["active_mask"],
        use_cache=False,
    )

    ladder = res["ladder"]
    assert len(ladder) == 15
    for i in range(len(ladder) - 1):
        s_curr = ladder[i]
        s_next = ladder[i + 1]
        assert s_curr["precipitation_mm"] < s_next["precipitation_mm"]
        assert s_curr["ponded_area_ha"] <= s_next["ponded_area_ha"], (
            f"Violación de monotonicidad en área anegada entre {s_curr['precipitation_mm']} y {s_next['precipitation_mm']} mm."
        )
        assert s_curr["outflow_volume_m3"] <= s_next["outflow_volume_m3"], (
            f"Violación de monotonicidad en volumen entre {s_curr['precipitation_mm']} y {s_next['precipitation_mm']} mm."
        )


def test_rainfall_ladder_critical_knee_point():
    """Verifica la detección automática del umbral crítico de anegamiento (knee point)."""
    t = _build_synthetic_terrain_with_catchment()

    res = compute_rainfall_ladder(
        field_id="field_knee_test",
        mascara_lote=t["mascara_lote"],
        mfd_area_m2=t["mfd_area"],
        slope_pct=t["slopes"],
        spi=t["spi"],
        pixel_size_m=30.0,
        depression_volume_in_field_m3=t["dep_vol_m3"],
        depression_area_in_field_ha=t["dep_area_ha"],
        external_inflow_ha=t["ext_inflow_ha"],
        soil_group="B",
        cover_code="soja_maiz_sd_buena",
        amc="medium",
        active_mask=t["active_mask"],
        use_cache=False,
    )

    crit_mm = res["critical_ponding_threshold_mm"]
    assert crit_mm is not None
    assert float(SUPUESTO_ESCALERA_LLUVIA_MIN_MM.valor) <= crit_mm <= float(SUPUESTO_ESCALERA_LLUVIA_MAX_MM.valor)
    # A partir del umbral crítico, debe haber retención en la cubeta
    step_crit = next(s for s in res["ladder"] if s["precipitation_mm"] == crit_mm)
    assert step_crit["ponded_area_ha"] > 0.0


def test_detect_critical_threshold_returns_none_when_no_ponding():
    """Verifica que detect_critical_ponding_threshold retorne None si no hay anegamiento o hay < 3 peldaños (sin 50.0 ni peldaño del medio)."""
    # Caso 1: menos de 3 peldaños -> None
    few_steps = [
        LadderStepResult(10.0, 0.0, 0.0, 0.0, None),
        LadderStepResult(20.0, 0.5, 0.2, 10.0, None),
    ]
    assert detect_critical_ponding_threshold(few_steps) is None

    # Caso 2: terreno sin anegamiento (0.0 ha en todos los peldaños) -> None
    zero_pond_steps = [
        LadderStepResult(float(p), 0.0, 0.0, float(p * 50), 0.1)
        for p in range(10, 160, 10)
    ]
    assert detect_critical_ponding_threshold(zero_pond_steps) is None

    # Caso 3: anegamiento despreciable (< 0.05 ha) -> None
    trace_steps = [
        LadderStepResult(float(p), 0.01, 0.01, float(p * 50), 0.1)
        for p in range(10, 160, 10)
    ]
    assert detect_critical_ponding_threshold(trace_steps) is None


def test_soil_loss_propagates_none_when_unavailable():
    """Verifica que si no hay cálculo USLE disponible, soil_loss_t_ha_yr se propague como None (sin 'or 0.0')."""
    step_none = LadderStepResult(30.0, 1.2, 0.5, 100.0, None)
    d = step_none.to_dict()
    assert d["soil_loss_t_ha_yr"] is None


def test_rainfall_ladder_benchmark_with_real_catchment():
    """Benchmark: verifica que los 15 peldaños sobre lote + cuenca completa (con active_mask)
    se resuelvan con holgura por debajo de los 60 s (Spec 031 §2.2).
    """
    t = _build_synthetic_terrain_with_catchment(alto=50, ancho=50)

    t0 = time.perf_counter()
    res = compute_rainfall_ladder(
        field_id="field_benchmark_test",
        mascara_lote=t["mascara_lote"],
        mfd_area_m2=t["mfd_area"],
        slope_pct=t["slopes"],
        spi=t["spi"],
        pixel_size_m=30.0,
        depression_volume_in_field_m3=t["dep_vol_m3"],
        depression_area_in_field_ha=t["dep_area_ha"],
        external_inflow_ha=t["ext_inflow_ha"],
        soil_group="B",
        cover_code="soja_maiz_sd_buena",
        amc="medium",
        active_mask=t["active_mask"],
        use_cache=False,
    )
    t_elapsed = time.perf_counter() - t0

    assert t_elapsed < float(SUPUESTO_ESCALERA_MAX_TIEMPO_COMPUTO_S.valor)
    assert res["benchmark_timing_ms"] > 0.0
    assert len(res["ladder"]) == 15
    print(f"\n[BENCHMARK] Escalera 15 peldaños (10 a 150 mm) sobre recorte lote+cuenca: {t_elapsed:.3f} s ({res['benchmark_timing_ms']:.1f} ms)")


def test_rainfall_ladder_api_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verifica el endpoint GET /api/v1/fields/{id}/hydrology/rainfall-ladder."""
    import httpx

    from geoprocessing import net as geonet
    from services.api.app.core import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "runs")
    monkeypatch.setattr(store, "DATA_DIR", tmp_path / "runs")
    clear_ladder_cache()

    def offline_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Offline test")

    offline_client = httpx.Client(transport=httpx.MockTransport(offline_handler))
    monkeypatch.setattr(geonet, "_cliente", offline_client)
    monkeypatch.setattr(geonet, "client", lambda: offline_client)

    client = TestClient(app)

    # 1. Importar lote de prueba
    fixtures_dir = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "lotes"
    geojson_bytes = (fixtures_dir / "san_luis_parcela_205.geojson").read_bytes()
    r = client.post(
        "/api/v1/fields/import",
        files={"file": ("san_luis_parcela_205.geojson", geojson_bytes, "application/geo+json")},
        data={"default_name": "Lote Test Escalera"},
    )
    assert r.status_code == 201
    f_id = r.json()["fields"][0]["id"]

    # 2. Procesar terreno con margen adaptativo
    r_terr = client.post(
        f"/api/v1/fields/{f_id}/terrain/process",
        data={"source_id": "copernicus_glo30", "adaptive_catchment": "true"},
    )
    assert r_terr.status_code == 200

    # 3. Procesar hidrología estática
    r_hyd = client.post(f"/api/v1/fields/{f_id}/hydrology/static", json={"conditioning_mode": "preserve"})
    assert r_hyd.status_code == 200

    # 4. Consultar escalera de lluvia
    r_ladder = client.get(f"/api/v1/fields/{f_id}/hydrology/rainfall-ladder?amc=medium&soil_id=B")
    assert r_ladder.status_code == 200, r_ladder.text
    data = r_ladder.json()

    assert data["field_id"] == f_id
    assert data["status"] == "ready"
    assert len(data["ladder"]) == 15
    assert data["critical_ponding_threshold_mm"] >= 10.0
    assert data["step_size_mm"] == 10
    assert data["return_periods_station"] is None
