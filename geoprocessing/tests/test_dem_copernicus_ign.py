"""Pruebas unitarias offline de validación de Copernicus GLO-30, GEM-15 DTM y Fusión vs. Mojones IGN (Spec 014).

Recalcula estadísticas robustas (mediana de sesgo, NMAD, RMSE y LE90) para las tres variantes
a partir del fixture geodésico offline 'ign_nivelacion_san_luis_20261122.geojson'
sin realizar peticiones de red.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from geoprocessing.dem.validation import (
    assume_same_vertical_datum,
    compute_robust_stats,
    leave_one_out_validation,
    validate_dem_against_reference_raster,
)
from geoprocessing.supuestos import (
    SUPUESTO_DEM_DATUM_COMUN_VERTICAL,
    SUPUESTO_DEM_DATUM_DIFERENCIA_DESPRECIABLE,
    SUPUESTO_DEM_DIFERENCIA_DATUM_VERTICAL_M,
    SUPUESTO_DEM_DISCREPANCIA_UMBRAL_M,
    SUPUESTO_DEM_EXCLUIR_RED_TOPOGRAFICA,
    SUPUESTO_DEM_MIN_MOJONES_IGN,
    SUPUESTO_DEM_RADIO_BUSQUEDA_IGN_R1_KM,
    SUPUESTO_DEM_RADIO_BUSQUEDA_IGN_R2_KM,
    SUPUESTO_DEM_RASTER_REFERENCIA_PATH,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "dem" / "ign_nivelacion_san_luis_20261122.geojson"


def _compute_robust_stats(errors: np.ndarray) -> dict[str, float]:
    return compute_robust_stats(errors)


def test_fixture_exists_and_contains_metadata():
    assert FIXTURE_PATH.exists(), f"No se encontró fixture en {FIXTURE_PATH}"
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert data["type"] == "FeatureCollection"
    assert "metadata" in data
    assert data["metadata"]["fecha_descarga"] == "2026-11-22"
    assert len(data["features"]) == 121
    assert "fuentes_evaluadas" in data["metadata"]


def test_recalculate_metrics_offline():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        data = json.load(f)

    alta_cop, alta_gem, alta_fus = [], [], []
    prec_cop, prec_gem, prec_fus = [], [], []
    topo_cop = []

    for feat in data["features"]:
        props = feat["properties"]
        err_c = props["error_copernicus_m"]
        err_g = props.get("error_gem15_m")
        err_f = props.get("error_fusion_m")
        assert err_c is not None, f"Mojón sin error copernicus: {props}"
        assert err_g is not None, f"Mojón sin error gem15: {props}"
        assert err_f is not None, f"Mojón sin error fusión: {props}"

        red = props["red"]
        if red == "alta_precision":
            assert not props["excluida"]
            alta_cop.append(err_c)
            alta_gem.append(err_g)
            alta_fus.append(err_f)
        elif red == "precision":
            assert not props["excluida"]
            prec_cop.append(err_c)
            prec_gem.append(err_g)
            prec_fus.append(err_f)
        elif red == "topografica":
            assert props["excluida"]
            assert "motivo_exclusion" in props
            topo_cop.append(err_c)

    # 1. Alta precisión (n=44)
    assert len(alta_cop) == 44
    stats_alta_cop = _compute_robust_stats(np.array(alta_cop))
    stats_alta_gem = _compute_robust_stats(np.array(alta_gem))
    stats_alta_fus = _compute_robust_stats(np.array(alta_fus))

    # Copernicus
    assert abs(stats_alta_cop["mediana"] - 0.50) <= 0.05
    assert abs(stats_alta_cop["nmad"] - 1.08) <= 0.05
    assert abs(stats_alta_cop["rmse"] - 1.59) <= 0.05
    assert abs(stats_alta_cop["le90"] - 2.42) <= 0.05

    # GEM-15 DTM
    assert abs(stats_alta_gem["mediana"] - 3.09) <= 0.05
    assert abs(stats_alta_gem["nmad"] - 0.91) <= 0.05

    # Fusión RotaTerra
    assert abs(stats_alta_fus["mediana"]) <= 0.05, "El sesgo sistemático debe ser cancelado tras calibración local"
    assert stats_alta_fus["nmad"] <= stats_alta_cop["nmad"], "La dispersión de la fusión debe igualar o mejorar a Copernicus"
    assert stats_alta_fus["nmad"] <= stats_alta_gem["nmad"], "La dispersión de la fusión debe igualar o mejorar a GEM-15"

    # 2. Combinada Alta + Precisión (n=76)
    comb_cop = np.array(alta_cop + prec_cop)
    comb_gem = np.array(alta_gem + prec_gem)
    comb_fus = np.array(alta_fus + prec_fus)
    assert len(comb_cop) == 76
    stats_comb_cop = _compute_robust_stats(comb_cop)
    stats_comb_gem = _compute_robust_stats(comb_gem)
    stats_comb_fus = _compute_robust_stats(comb_fus)

    assert abs(stats_comb_cop["mediana"] - 0.45) <= 0.05
    assert abs(stats_comb_cop["nmad"] - 1.15) <= 0.05
    assert abs(stats_comb_gem["mediana"] - 3.15) <= 0.10
    assert stats_comb_gem["nmad"] <= 1.20
    assert stats_comb_fus["nmad"] <= stats_comb_cop["nmad"], "En la combinación, NMAD fusión debe ser <= Copernicus"

    # 3. Topográfica (excluida, n=45)
    assert len(topo_cop) == 45
    stats_topo = _compute_robust_stats(np.array(topo_cop))
    assert stats_topo["nmad"] > 3.0, "La red topográfica tiene dispersión significativamente mayor"


def test_supuestos_relieve_declarados():
    assert SUPUESTO_DEM_RADIO_BUSQUEDA_IGN_R1_KM.valor == 25.0
    assert SUPUESTO_DEM_RADIO_BUSQUEDA_IGN_R2_KM.valor == 50.0
    assert SUPUESTO_DEM_MIN_MOJONES_IGN.valor == 3
    assert SUPUESTO_DEM_DIFERENCIA_DATUM_VERTICAL_M.valor is None
    assert "EGM2008" in SUPUESTO_DEM_DIFERENCIA_DATUM_VERTICAL_M.motivo
    assert SUPUESTO_DEM_DISCREPANCIA_UMBRAL_M.valor == 2.5
    assert SUPUESTO_DEM_DISCREPANCIA_UMBRAL_M.unidad == "m"
    assert SUPUESTO_DEM_DATUM_COMUN_VERTICAL.valor == "EGM2008"
    assert SUPUESTO_DEM_EXCLUIR_RED_TOPOGRAFICA.valor is True
    assert "mde_ign_5m" in SUPUESTO_DEM_RASTER_REFERENCIA_PATH.valor


def test_leave_one_out_validation_alta_precision():
    """Valida fuera de muestra (Leave-One-Out) con n=44 de alta precisión.

    El sesgo se calibra con n-1 mojones y se evalúa en el excluido.
    Comprueba que la dispersión fuera de muestra mejora a Copernicus y cancela el sesgo.
    """
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        data = json.load(f)

    alta_feats = [f for f in data["features"] if f["properties"]["red"] == "alta_precision"]
    res = leave_one_out_validation(alta_feats, dem_key="cota_gem15_m", ign_key="cota_ign_m")

    assert res["status"] == "ok"
    assert res["n_valid"] == 44
    assert res["n_excluded"] == 0

    loo = res["out_of_sample_stats"]
    raw = res["raw_stats"]
    ins = res["in_sample_stats"]

    # Sesgo empírico crudo de GEM-15 ≈ +3.09 m
    assert abs(raw["mediana"] - 3.09) <= 0.05
    # En leave-one-out, el sesgo mediano fuera de muestra es 0.0 m
    assert abs(loo["mediana"]) <= 0.05
    # NMAD fuera de muestra (0.96 m) es mejor que Copernicus (1.08 m)
    assert loo["nmad"] <= 1.00
    assert loo["nmad"] < 1.08
    # RMSE fuera de muestra (1.21 m) mejora sustancialmente a GEM-15 crudo (3.36 m) y a Copernicus (1.59 m)
    assert loo["rmse"] <= 1.30
    assert loo["rmse"] < 1.59
    # In-sample vs out-of-sample: LOO es ligeramente más conservador
    assert loo["nmad"] >= ins["nmad"] or abs(loo["nmad"] - ins["nmad"]) <= 0.10


def test_leave_one_out_validation_alta_mas_precision():
    """Valida fuera de muestra (Leave-One-Out) con n=76 combinada (alta + precisión)."""
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # Pasar todas las features (incluyendo topográficas para verificar filtrado automático)
    res = leave_one_out_validation(data["features"], dem_key="cota_gem15_m", ign_key="cota_ign_m")

    assert res["status"] == "ok"
    assert res["n_valid"] == 76
    assert res["n_excluded"] == 45  # 45 mojones topográficos excluidos

    loo = res["out_of_sample_stats"]
    assert abs(loo["mediana"]) <= 0.05
    # NMAD fuera de muestra (1.11 m) mejora a Copernicus (1.15 m)
    assert loo["nmad"] <= 1.15
    # RMSE fuera de muestra (1.96 m) es marcadamente inferior a Copernicus (2.77 m)
    assert loo["rmse"] <= 2.10


def test_leave_one_out_excludes_topografica_automatically():
    """Verifica que la red topográfica (20+ mojones con cota dudosa) queda excluida."""
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        data = json.load(f)

    topo_feats = [f for f in data["features"] if f["properties"]["red"] == "topografica"]
    assert len(topo_feats) == 45

    res = leave_one_out_validation(topo_feats, dem_key="cota_copernicus_m", ign_key="cota_ign_m")
    # Al excluir la red topográfica, ningún mojón debe ser considerado válido
    assert res["n_valid"] == 0
    assert res["n_excluded"] == 45


def test_vertical_datum_conversion():
    """Verifica adopción de datum vertical bajo supuesto metodológico declarado."""
    z_cop = 500.0
    z_gem = 503.09

    # Copernicus en EGM2008 a EGM2008 es identidad
    assert assume_same_vertical_datum(z_cop, source_datum="EGM2008", target_datum="EGM2008") == 500.0

    # GEM-15 en EGM96: no se resta 3 m artificiales en el datum; el sesgo de +3.1 m es empírico
    z_conv = assume_same_vertical_datum(z_gem, source_datum="EGM96", target_datum="EGM2008")
    assert z_conv == 503.09

    # Sin datum declarado explícitamente se eleva ValueError (sin fallback silencioso 'or')
    import pytest
    with pytest.raises(ValueError, match="Sin datum declarado"):
        assume_same_vertical_datum(z_cop, source_datum=None)

    with pytest.raises(ValueError, match="Sin datum declarado"):
        assume_same_vertical_datum(z_cop, source_datum="")

    # Verifica que el supuesto metodológico declare la limitación del Sistema de Alturas Nacional (IGN)
    assert SUPUESTO_DEM_DATUM_DIFERENCIA_DESPRECIABLE.valor is True
    assert "Sistema de Alturas Nacional" in SUPUESTO_DEM_DATUM_DIFERENCIA_DESPRECIABLE.motivo


def test_validate_dem_against_reference_raster_missing_and_synthetic(tmp_path: Path):
    """Prueba el punto de entrada de validación contra ráster de referencia (MDE IGN 5 m)."""
    # 0. Caso array en memoria sin CRS declarado eleva ValueError
    import pytest
    dem_test = np.ones((20, 20), dtype="float32") * 100.0
    ref_dummy = tmp_path / "ref_dummy.tif"
    with open(ref_dummy, "wb") as f:
        f.write(b"")

    # Si el ráster no existe, se detecta antes de reproject
    missing_path = tmp_path / "mde_ign_5m_no_existe.tif"
    res_missing = validate_dem_against_reference_raster(dem_test, reference_raster=missing_path)
    assert res_missing["status"] == "raster_no_disponible"
    assert "no se encuentra disponible" in res_missing["motivo"]
    assert res_missing["metrics"] is None

    # 2. Caso ráster de referencia sintético disponible
    import rasterio
    from rasterio.transform import from_origin

    ref_path = tmp_path / "ref_synthetic_5m.tif"
    eval_path = tmp_path / "eval_synthetic_15m.tif"

    # Ráster de referencia 5 m: plano calculado según coordenadas espaciales
    transform_5m = from_origin(500_000.0, 6_000_000.0, 5.0, 5.0)
    cols_5m, rows_5m = np.meshgrid(np.arange(30), np.arange(30))
    x_5m = 500_000.0 + (cols_5m + 0.5) * 5.0
    y_5m = 6_000_000.0 - (rows_5m + 0.5) * 5.0
    data_ref = (500.0 + 0.01 * (x_5m - 500_000.0) - 0.01 * (y_5m - 6_000_000.0)).astype("float32")
    with rasterio.open(
        ref_path, "w", driver="GTiff", height=30, width=30, count=1, dtype="float32",
        crs="EPSG:32720", transform=transform_5m
    ) as dst:
        dst.write(data_ref, 1)

    # DEM evaluado 15 m: mismo plano espacial con sesgo exacto de +0.50 m
    transform_15m = from_origin(500_000.0, 6_000_000.0, 15.0, 15.0)
    cols_15m, rows_15m = np.meshgrid(np.arange(10), np.arange(10))
    x_15m = 500_000.0 + (cols_15m + 0.5) * 15.0
    y_15m = 6_000_000.0 - (rows_15m + 0.5) * 15.0
    data_eval = (500.0 + 0.01 * (x_15m - 500_000.0) - 0.01 * (y_15m - 6_000_000.0) + 0.50).astype("float32")
    with rasterio.open(
        eval_path, "w", driver="GTiff", height=10, width=10, count=1, dtype="float32",
        crs="EPSG:32720", transform=transform_15m
    ) as dst:
        dst.write(data_eval, 1)

    res_ok = validate_dem_against_reference_raster(eval_path, reference_raster=ref_path)
    assert res_ok["status"] == "ok"
    assert res_ok["valid_cells"] > 0
    metrics = res_ok["metrics"]
    assert abs(metrics["mediana"] - 0.50) <= 0.05
    assert metrics["nmad"] <= 0.10

    # 3. Array en memoria sin CRS declarado eleva ValueError
    with pytest.raises(ValueError, match="Sin CRS declarado"):
        validate_dem_against_reference_raster(data_eval, reference_raster=ref_path, evaluated_transform=transform_15m)

    # Con CRS y transformación declarados explícitamente se procesa con éxito
    res_mem = validate_dem_against_reference_raster(
        data_eval,
        reference_raster=ref_path,
        evaluated_transform=transform_15m,
        evaluated_crs="EPSG:32720",
    )
    assert res_mem["status"] == "ok"
    assert abs(res_mem["metrics"]["mediana"] - 0.50) <= 0.05
