"""Tests unitarios de Fase 2: validación CSV de lluvia, ecuaciones NRCS-CN, balance de masa y comparación."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from geoprocessing.rainfall.events import (
    RainfallValidationError,
    build_event_metadata,
    parse_rainfall_csv,
)
from geoprocessing.rainfall.nrcs_cn import (
    adjust_cn_for_amc,
    compare_runoff_scenarios,
    compute_nrcs_cn,
    distribute_event_runoff_mfd,
    lookup_cn_ii,
)


def test_parse_valid_sample_rainfall_csv():
    sample_csv = Path(__file__).resolve().parents[2] / "data" / "sample" / "evento_tormenta_pluvio.csv"
    rep = parse_rainfall_csv(sample_csv.read_bytes(), declared_total_mm=80.0)
    assert rep.total_mm == pytest.approx(80.0, abs=1e-2)
    assert rep.interval_minutes == 15
    assert len(rep.intervals) == 8
    assert rep.gaps_detected == 0
    assert rep.max_interval_mm == pytest.approx(21.0)
    assert rep.max_intensity_mm_h == pytest.approx(84.0)


def test_reject_invalid_rainfall_csv():
    # Sin zona horaria en timestamp
    no_tz = (
        "timestamp,precipitation_mm,interval_minutes,station_id\n"
        "2026-11-18T14:00:00,5.0,15,PLUVIO-01\n"
    )
    with pytest.raises(RainfallValidationError, match="zona horaria"):
        parse_rainfall_csv(no_tz)

    # Precipitación negativa
    neg = (
        "timestamp,precipitation_mm,interval_minutes,station_id\n"
        "2026-11-18T14:00:00-03:00,-1.5,15,PLUVIO-01\n"
    )
    with pytest.raises(RainfallValidationError, match="no negativa"):
        parse_rainfall_csv(neg)

    # Timestamp duplicado
    dup = (
        "timestamp,precipitation_mm,interval_minutes,station_id\n"
        "2026-11-18T14:00:00-03:00,2.0,15,PLUVIO-01\n"
        "2026-11-18T14:00:00-03:00,3.0,15,PLUVIO-01\n"
    )
    with pytest.raises(RainfallValidationError, match="duplicado"):
        parse_rainfall_csv(dup)


def test_detect_gaps_and_total_mismatch_in_csv():
    with_gap = (
        "timestamp,precipitation_mm,interval_minutes,station_id\n"
        "2026-11-18T14:00:00-03:00,10.0,15,PLUVIO-01\n"
        "2026-11-18T14:45:00-03:00,15.0,15,PLUVIO-01\n"
    )
    rep = parse_rainfall_csv(with_gap, declared_total_mm=30.0)
    assert rep.gaps_detected == 1
    assert rep.total_mm == pytest.approx(25.0)
    assert any("huecos temporales" in w for w in rep.warnings)
    assert any("difiere del acumulado declarado" in w for w in rep.warnings)


def test_nrcs_cn_equations_and_mass_balance():
    """Verifica las ecuaciones S = 25400/CN - 254, Ia = 0.2*S y Q = (P-Ia)^2 / (P-Ia+S) (SDD §6.4)."""
    # Con CN = 80 (AMC II) -> S = 25400/80 - 254 = 317.5 - 254 = 63.5 mm; Ia = 0.2 * 63.5 = 12.7 mm
    res_low = compute_nrcs_cn(precipitation_mm=10.0, cn_ii_base=80.0, antecedent_moisture="medium", lambda_ratio=0.2)
    assert res_low.potential_retention_s_mm == pytest.approx(63.5, abs=1e-2)
    assert res_low.initial_abstraction_ia_mm == pytest.approx(12.7, abs=1e-2)
    assert res_low.runoff_q_mm == 0.0  # P <= Ia -> Q = 0
    assert res_low.mass_balance_error_mm < 1e-6

    # Con P = 80 mm y CN = 80 -> P - Ia = 67.3; P - Ia + S = 130.8 -> Q = 67.3^2 / 130.8 = 34.6276 mm
    res_storm = compute_nrcs_cn(precipitation_mm=80.0, cn_ii_base=80.0, antecedent_moisture="medium", lambda_ratio=0.2)
    assert res_storm.runoff_q_mm == pytest.approx((67.3 ** 2) / 130.8, abs=1e-2)
    assert res_storm.mass_balance_error_mm < 1e-6

    # AMC I (seco) < AMC II < AMC III (húmedo)
    cn_dry = adjust_cn_for_amc(80.0, "dry")
    cn_wet = adjust_cn_for_amc(80.0, "wet")
    assert cn_dry < 80.0 < cn_wet


def test_spatial_distribution_and_scenario_comparison():
    cn_ii, _ = lookup_cn_ii("soja_maiz_sd_buena", "B", cover_percent=65.0)
    res_a = compute_nrcs_cn(50.0, cn_ii, "medium")
    res_b = compute_nrcs_cn(100.0, cn_ii, "wet")

    mfd_area = np.full((10, 10), 900.0, dtype="float32")
    mfd_area[-1, -1] = 9000.0  # celda de concentración (10 celdas)
    mascara = np.ones((10, 10), dtype=bool)

    load_a, vol_a, sum_a = distribute_event_runoff_mfd(res_a, mfd_area, mascara, 30.0, 50.0, 0.0)
    load_b, vol_b, sum_b = distribute_event_runoff_mfd(res_b, mfd_area, mascara, 30.0, 50.0, 0.0)

    assert float(load_b[-1, -1]) > float(load_a[-1, -1])
    comp = compare_runoff_scenarios(
        {"id": "a", "name": "50 mm medio", "cn_result": res_a.to_dict(), "spatial_summary": sum_a},
        {"id": "b", "name": "100 mm húmedo", "cn_result": res_b.to_dict(), "spatial_summary": sum_b},
    )
    assert comp["delta_precipitation_mm"] == pytest.approx(50.0)
    assert comp["delta_runoff_q_mm"] > 40.0
    assert comp["delta_field_runoff_generated_m3"] > 0.0

    meta, warnings = build_event_metadata("IMERG", 60.0, None, None, has_time_series=False, interval_minutes=None)
    assert meta["units"] == "mm"
    assert any("no se inventa intensidad" in w for w in warnings)
