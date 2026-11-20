"""Modelo de evento NRCS Curve Number (CN), distribución espacial con MFD y comparación de escenarios (SDD §6.4).

Ecuaciones en unidades métricas (SDD §6.4):
    S  = 25400 / CN - 254
    Ia = lambda * S
    Q  = 0                              si P <= Ia
    Q  = (P - Ia)^2 / (P - Ia + S)      si P >  Ia

Advertencia obligatoria (SDD §6.4):
    Este método calcula una profundidad de escorrentía directa de evento (mm); no produce por sí
    solo un hidrograma temporal ni una profundidad instantánea de inundación en cada celda.
    Jamás presentar Q ni la carga acumulada MFD como profundidad física de inundación.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np

SoilGroup = Literal["A", "B", "C", "D"]
AntecedentMoisture = Literal["dry", "medium", "wet"]

# Tabla base de números de curva en condición antecedente media (CN_II) basada en NRCS TR-55 (uso agrícola)
CN_II_LOOKUP: dict[str, dict[str, any]] = {
    "soja_maiz_sd_buena": {
        "label": "Cultivo anual (Soja / Maíz) en Siembra Directa con rastrojo (>30% cobertura)",
        "values": {"A": 74, "B": 80, "C": 86, "D": 89},
    },
    "soja_maiz_convencional": {
        "label": "Cultivo anual en hilera con baja cobertura / labranza convencional",
        "values": {"A": 77, "B": 86, "C": 91, "D": 94},
    },
    "trigo_cereal_invierno_sd": {
        "label": "Cereal de invierno / cultivo denso (Trigo / Cebada / Centeno) en Siembra Directa",
        "values": {"A": 63, "B": 74, "C": 82, "D": 85},
    },
    "cultivo_cobertura_vicia_centeno": {
        "label": "Cultivo de servicio / cobertura densa activa (Vicia / Centeno / Avena)",
        "values": {"A": 58, "B": 71, "C": 79, "D": 83},
    },
    "pastura_pradera_buena": {
        "label": "Pastura consociada / verdeos en buena condición hidrológica",
        "values": {"A": 49, "B": 69, "C": 79, "D": 84},
    },
    "pastura_sobrepastoreada": {
        "label": "Pastizal / campo natural con pastoreo intenso o compactación superficial",
        "values": {"A": 68, "B": 79, "C": 86, "D": 89},
    },
    "barbecho_con_rastrojo": {
        "label": "Barbecho químico con cobertura de rastrojo conservada",
        "values": {"A": 74, "B": 83, "C": 88, "D": 90},
    },
    "barbecho_suelo_desnudo": {
        "label": "Barbecho descubierto / suelo desnudo sin residuos",
        "values": {"A": 77, "B": 86, "C": 91, "D": 94},
    },
}

TABLE_CN_II = CN_II_LOOKUP


@dataclass
class CnEventResult:
    precipitation_mm: float
    cn_ii_base: float
    cn_effective: float
    antecedent_moisture: AntecedentMoisture
    lambda_ratio: float
    potential_retention_s_mm: float
    initial_abstraction_ia_mm: float
    infiltration_after_ia_f_mm: float
    total_retention_losses_mm: float
    runoff_q_mm: float
    runoff_coefficient: float
    mass_balance_error_mm: float

    def to_dict(self) -> dict:
        return asdict(self)


def lookup_cn_ii(
    cover_code: str,
    soil_group: SoilGroup,
    cover_percent: float | None = None,
    compaction_high: bool = False,
) -> tuple[float, list[str]]:
    """Obtiene el CN_II base de la tabla NRCS TR-55 y aplica ajustes documentados por cobertura/compactación."""
    entry = CN_II_LOOKUP.get(cover_code, CN_II_LOOKUP["soja_maiz_sd_buena"])
    cn_ii = float(entry["values"][soil_group])
    notes: list[str] = [
        f"CN_II base = {cn_ii:.0f} para grupo hidrológico {soil_group} y cobertura '{entry['label']}'."
    ]
    if cover_percent is not None:
        # Ajuste suave (-2 a +3 puntos) cuando el porcentaje de cobertura medido se aparta del estándar
        if cover_percent >= 70:
            cn_ii = max(35.0, cn_ii - 2.0)
            notes.append(f"Ajuste -2 puntos en CN_II por alta cobertura superficial ({cover_percent:.0f} %).")
        elif cover_percent < 20:
            cn_ii = min(96.0, cn_ii + 2.0)
            notes.append(f"Ajuste +2 puntos en CN_II por baja cobertura superficial ({cover_percent:.0f} %).")
    if compaction_high:
        cn_ii = min(97.0, cn_ii + 3.0)
        notes.append("Ajuste +3 puntos en CN_II por compactación/huellas declaradas.")
    return round(cn_ii, 2), notes


def adjust_cn_for_amc(cn_ii: float, amc: AntecedentMoisture) -> float:
    """Ajusta CN_II a condición antecedente seca (AMC I) o húmeda (AMC III) según Chow, Maidment & Mays."""
    if not (30.0 <= cn_ii <= 99.0):
        raise ValueError(f"El Número de Curva (CN) debe estar entre 30 y 99 (recibido: {cn_ii}).")
    if amc == "dry":
        cn = (4.2 * cn_ii) / (10.0 - 0.058 * cn_ii)
    elif amc == "wet":
        cn = (23.0 * cn_ii) / (10.0 + 0.13 * cn_ii)
    else:
        cn = cn_ii
    return round(float(np.clip(cn, 30.0, 99.5)), 2)


def compute_nrcs_cn(
    precipitation_mm: float,
    cn_ii_base: float,
    antecedent_moisture: AntecedentMoisture = "medium",
    lambda_ratio: float = 0.2,
) -> CnEventResult:
    """Calcula S, Ia, pérdidas y escorrentía directa Q (mm) según NRCS-CN y verifica el balance P = Ia + F + Q."""
    if precipitation_mm < 0:
        raise ValueError("La precipitación acumulada no puede ser negativa.")
    if not (0.01 <= lambda_ratio <= 0.5):
        raise ValueError("La relación de abstracción inicial (lambda) debe estar entre 0,01 y 0,50.")

    cn_eff = adjust_cn_for_amc(cn_ii_base, antecedent_moisture)
    s_mm = (25400.0 / cn_eff) - 254.0
    ia_mm = lambda_ratio * s_mm

    p = float(precipitation_mm)
    if p <= ia_mm:
        q_mm = 0.0
        ia_used = p
        f_mm = 0.0
    else:
        q_mm = ((p - ia_mm) ** 2) / (p - ia_mm + s_mm)
        ia_used = ia_mm
        f_mm = p - ia_mm - q_mm

    losses_mm = ia_used + f_mm
    balance_err = abs(p - (losses_mm + q_mm))
    coeff = (q_mm / p) if p > 0 else 0.0

    return CnEventResult(
        precipitation_mm=round(p, 2),
        cn_ii_base=round(float(cn_ii_base), 2),
        cn_effective=cn_eff,
        antecedent_moisture=antecedent_moisture,
        lambda_ratio=round(float(lambda_ratio), 3),
        potential_retention_s_mm=round(s_mm, 2),
        initial_abstraction_ia_mm=round(ia_mm, 2),
        infiltration_after_ia_f_mm=round(f_mm, 2),
        total_retention_losses_mm=round(losses_mm, 2),
        runoff_q_mm=round(q_mm, 2),
        runoff_coefficient=round(coeff, 4),
        mass_balance_error_mm=round(balance_err, 8),
    )


def distribute_event_runoff_mfd(
    cn_result: CnEventResult,
    mfd_area_m2: np.ndarray,
    mascara_lote: np.ndarray,
    pixel_size_m: float,
    depression_volume_in_field_m3: float,
    external_inflow_ha: float,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Combina la lluvia efectiva Q (mm) con el enrutamiento topográfico MFD (SDD §6.4).

    Para cada celda válida con área contribuyente `A_mfd` (m²):
    - `cumulative_runoff_m3 = (Q_mm / 1000) * A_mfd` (volumen potencial de escorrentía que converge por la celda),
    - `runoff_load_mm = Q_mm * (A_mfd / A_celda)` (carga acumulada equivalente en mm por celda).

    IMPORTANTE (SDD §6.4): `runoff_load_mm` es un indicador espacial de concentración de escorrentía
    de evento; NO es profundidad de lámina de agua ni altura de inundación.
    """
    q_mm = cn_result.runoff_q_mm
    q_m = q_mm / 1000.0
    cell_area_m2 = float(pixel_size_m * pixel_size_m)
    valid = np.isfinite(mfd_area_m2)

    cumulative_runoff_m3 = np.where(valid, mfd_area_m2 * q_m, np.nan).astype("float32")
    runoff_load_mm = np.where(valid, q_mm * (mfd_area_m2 / cell_area_m2), np.nan).astype("float32")

    in_field_valid = mascara_lote & valid
    field_cells = int(in_field_valid.sum())
    field_area_m2 = field_cells * cell_area_m2

    generated_in_field_m3 = field_area_m2 * q_m
    external_inflow_m3 = (float(external_inflow_ha) * 10_000.0) * q_m
    total_supply_to_field_m3 = generated_in_field_m3 + external_inflow_m3

    # Retención potencial en bajos conservados dentro del lote
    retained_in_depressions_m3 = min(float(depression_volume_in_field_m3), total_supply_to_field_m3)
    net_export_potential_m3 = max(0.0, total_supply_to_field_m3 - retained_in_depressions_m3)

    load_in_field = runoff_load_mm[in_field_valid]
    vol_in_field = cumulative_runoff_m3[in_field_valid]

    spatial_summary = {
        "runoff_generated_q_mm": round(q_mm, 2),
        "field_runoff_generated_m3": round(generated_in_field_m3, 1),
        "external_runoff_inflow_m3": round(external_inflow_m3, 1),
        "total_runoff_supply_m3": round(total_supply_to_field_m3, 1),
        "potential_depression_retention_m3": round(retained_in_depressions_m3, 1),
        "net_outflow_potential_m3": round(net_export_potential_m3, 1),
        "max_cell_cumulative_runoff_m3": round(float(vol_in_field.max()), 1) if vol_in_field.size else 0.0,
        "max_cell_runoff_load_mm": round(float(load_in_field.max()), 1) if load_in_field.size else 0.0,
        "mean_cell_runoff_load_mm": round(float(load_in_field.mean()), 1) if load_in_field.size else 0.0,
        "high_concentration_area_ha": round(
            float((load_in_field >= max(50.0, 5.0 * q_mm)).sum() * cell_area_m2 / 10_000.0),
            3,
        ) if q_mm > 0 and load_in_field.size else 0.0,
    }
    return runoff_load_mm, cumulative_runoff_m3, spatial_summary


def compare_runoff_scenarios(run_a: dict, run_b: dict) -> dict:
    """Compara dos corridas de escorrentía sobre el mismo lote (Escenario Base A vs. Escenario B, CU-04)."""
    ca, cb = run_a["cn_result"], run_b["cn_result"]
    sa, sb = run_a["spatial_summary"], run_b["spatial_summary"]

    dq_mm = round(cb["runoff_q_mm"] - ca["runoff_q_mm"], 2)
    dq_pct = (
        round(100.0 * (cb["runoff_q_mm"] - ca["runoff_q_mm"]) / ca["runoff_q_mm"], 1)
        if ca["runoff_q_mm"] > 0
        else None
    )
    d_vol_field = round(sb["field_runoff_generated_m3"] - sa["field_runoff_generated_m3"], 1)
    d_outflow = round(sb["net_outflow_potential_m3"] - sa["net_outflow_potential_m3"], 1)

    return {
        "run_a_id": run_a["id"],
        "run_a_name": run_a["name"],
        "run_b_id": run_b["id"],
        "run_b_name": run_b["name"],
        "delta_precipitation_mm": round(cb["precipitation_mm"] - ca["precipitation_mm"], 2),
        "delta_cn_effective": round(cb["cn_effective"] - ca["cn_effective"], 2),
        "delta_initial_abstraction_ia_mm": round(
            cb["initial_abstraction_ia_mm"] - ca["initial_abstraction_ia_mm"], 2
        ),
        "delta_runoff_q_mm": dq_mm,
        "delta_runoff_q_pct": dq_pct,
        "delta_runoff_coefficient": round(cb["runoff_coefficient"] - ca["runoff_coefficient"], 4),
        "delta_field_runoff_generated_m3": d_vol_field,
        "delta_net_outflow_potential_m3": d_outflow,
        "delta_high_concentration_area_ha": round(
            sb["high_concentration_area_ha"] - sa["high_concentration_area_ha"], 3
        ),
    }
