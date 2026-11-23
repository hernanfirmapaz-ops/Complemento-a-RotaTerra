"""Pruebas unitarias offline de validación de Copernicus GLO-30, GEM-15 DTM y Fusión vs. Mojones IGN (Spec 014).

Recalcula estadísticas robustas (mediana de sesgo, NMAD, RMSE y LE90) para las tres variantes
a partir del fixture geodésico offline 'ign_nivelacion_san_luis_20261122.geojson'
sin realizar peticiones de red.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from geoprocessing.supuestos import (
    SUPUESTO_DEM_DIFERENCIA_DATUM_VERTICAL_M,
    SUPUESTO_DEM_DISCREPANCIA_UMBRAL_M,
    SUPUESTO_DEM_MIN_MOJONES_IGN,
    SUPUESTO_DEM_RADIO_BUSQUEDA_IGN_R1_KM,
    SUPUESTO_DEM_RADIO_BUSQUEDA_IGN_R2_KM,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "dem" / "ign_nivelacion_san_luis_20261122.geojson"


def _compute_robust_stats(errors: np.ndarray) -> dict[str, float]:
    med = float(np.median(errors))
    nmad = float(1.4826 * np.median(np.abs(errors - med)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    le90 = float(np.percentile(np.abs(errors), 90))
    return {
        "mediana": round(med, 2),
        "nmad": round(nmad, 2),
        "rmse": round(rmse, 2),
        "le90": round(le90, 2),
    }


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
