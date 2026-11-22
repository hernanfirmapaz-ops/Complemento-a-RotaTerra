"""Pruebas unitarias offline de validación de Copernicus GLO-30 vs. Mojones IGN (Spec 014).

Recalcula estadísticas robustas (mediana de sesgo, NMAD, RMSE y LE90)
a partir del fixture geodésico offline 'ign_nivelacion_san_luis_20261122.geojson'
sin realizar peticiones de red.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from geoprocessing.supuestos import (
    SUPUESTO_DEM_DIFERENCIA_DATUM_VERTICAL_M,
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


def test_recalculate_metrics_offline():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        data = json.load(f)

    alta_errs = []
    prec_errs = []
    topo_errs = []

    for feat in data["features"]:
        props = feat["properties"]
        err = props["error_copernicus_m"]
        assert err is not None, f"Mojón sin error: {props}"
        red = props["red"]
        if red == "alta_precision":
            assert not props["excluida"]
            alta_errs.append(err)
        elif red == "precision":
            assert not props["excluida"]
            prec_errs.append(err)
        elif red == "topografica":
            assert props["excluida"]
            assert "motivo_exclusion" in props
            topo_errs.append(err)

    # 1. Alta precisión (n=44)
    assert len(alta_errs) == 44
    stats_alta = _compute_robust_stats(np.array(alta_errs))
    assert abs(stats_alta["mediana"] - 0.50) <= 0.05
    assert abs(stats_alta["nmad"] - 1.08) <= 0.05
    assert abs(stats_alta["rmse"] - 1.59) <= 0.05
    assert abs(stats_alta["le90"] - 2.42) <= 0.05

    # 2. Precisión (n=32)
    assert len(prec_errs) == 32
    stats_prec = _compute_robust_stats(np.array(prec_errs))
    assert abs(stats_prec["mediana"] - 0.30) <= 0.05
    assert abs(stats_prec["nmad"] - 1.93) <= 0.05
    assert abs(stats_prec["rmse"] - 3.83) <= 0.05

    # 3. Combinada Alta + Precisión (n=76)
    comb_errs = np.array(alta_errs + prec_errs)
    assert len(comb_errs) == 76
    stats_comb = _compute_robust_stats(comb_errs)
    assert abs(stats_comb["mediana"] - 0.45) <= 0.05
    assert abs(stats_comb["nmad"] - 1.15) <= 0.05
    assert stats_comb["nmad"] < 1.50, "NMAD combinado en llanura debe ser menor a 1.5 m"

    # 4. Topográfica (excluida, n=45)
    assert len(topo_errs) == 45
    stats_topo = _compute_robust_stats(np.array(topo_errs))
    assert stats_topo["nmad"] > 3.0, "La red topográfica tiene dispersión significativamente mayor"
    assert stats_topo["rmse"] > 8.0, "La red topográfica contiene errores de cota que inflan el RMSE"


def test_supuestos_relieve_declarados():
    assert SUPUESTO_DEM_RADIO_BUSQUEDA_IGN_R1_KM.valor == 25.0
    assert SUPUESTO_DEM_RADIO_BUSQUEDA_IGN_R2_KM.valor == 50.0
    assert SUPUESTO_DEM_MIN_MOJONES_IGN.valor == 3
    assert SUPUESTO_DEM_DIFERENCIA_DATUM_VERTICAL_M.valor is None
    assert "EGM2008" in SUPUESTO_DEM_DIFERENCIA_DATUM_VERTICAL_M.motivo
