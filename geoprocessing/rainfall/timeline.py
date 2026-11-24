"""Evolución temporal simplificada por intervalos sobre el hietograma (Fase 3, SDD §4.5, §6.5 y §14 Fase 3).

Requisitos obligatorios del SDD (§6.5 y §14 Fase 3):
- Aceptar serie temporal de lluvia por intervalos (hietograma).
- Dividir el evento en pasos temporales + pasos de recesión post-tormenta.
- Calcular lluvia acumulada, pérdidas (Ia + infiltración F) y excedente de escorrentía ΔQ por intervalo.
- Enrutar el excedente sobre la topografía manteniendo un balance de masa exacto en cada intervalo:
      P_acum(t) = Pérdidas_acum(t) + Almacenamiento_en_tránsito(t) + Retención_bajos(t) + Salida_acum(t)
- Generar partículas/trazas georreferenciadas en 3D vinculadas al flujo calculado en cada paso temporal.
- No inventar velocidad física en m/s ni profundidad hidrodinámica 2D: el indicador por celda y paso
  es `transit_runoff_load_mm` (carga de escorrentía en tránsito en el instante t).
"""

from __future__ import annotations

import math

import numpy as np

from geoprocessing.crs import WGS84, to_crs
from geoprocessing.dem.terrain import Dem
from geoprocessing.hydrology.flow import CODE_TO_DELTA
from geoprocessing.rainfall.nrcs_cn import AntecedentMoisture, compute_nrcs_cn


def simulate_temporal_runoff(
    intervals: list[dict],
    cn_ii_base: float,
    antecedent_moisture: AntecedentMoisture,
    lambda_ratio: float,
    mfd_area_m2: np.ndarray,
    mascara_lote: np.ndarray,
    pixel_size_m: float,
    mean_slope_pct: float | None = None,
    depression_volume_in_field_m3: float = 0.0,
    external_inflow_ha: float = 0.0,
    recession_steps: int = 4,
) -> dict:
    """Simula el tránsito temporal por intervalos a partir de un hietograma y parámetros NRCS-CN.

    Usa NRCS-CN incremental para particionar cada intervalo de lluvia ΔP(t) en pérdidas ΔLoss(t) y
    lluvia efectiva ΔQ(t), y un esquema de reservorio de tránsito superficial + retención en bajos
    cuyo coeficiente de evacuación por paso depende de la pendiente media y la duración del intervalo.

    La respuesta temporal cambia directamente al modificar la distribución temporal del hietograma
    (p. ej. tormenta con pico temprano vs. pico tardío), cumpliendo el criterio de aceptación de Fase 3.
    """
    if not intervals:
        raise ValueError("La simulación temporal requiere un evento de lluvia con serie temporal (hietograma).")

    step_min = int(intervals[0]["interval_minutes"])
    cell_area_m2 = float(pixel_size_m * pixel_size_m)
    valid = np.isfinite(mfd_area_m2)
    in_field_valid = mascara_lote & valid
    field_cells = int(in_field_valid.sum())
    field_area_m2 = field_cells * cell_area_m2
    ext_area_m2 = float(external_inflow_ha) * 10_000.0
    total_catchment_m2 = max(cell_area_m2, field_area_m2 + ext_area_m2)

    # Coeficiente de transferencia por intervalo según pendiente media y paso temporal (0.25 .. 0.70 por paso)
    slope_factor = (
        math.sqrt(max(0.2, float(mean_slope_pct)) / 2.0)
        if mean_slope_pct is not None
        else 1.0
    )
    k_drain = float(np.clip(0.32 * (step_min / 15.0) * slope_factor, 0.22, 0.72))

    # Capacidad máxima de retención en depresiones expresada en mm equivalentes sobre la cuenca aportante al lote
    max_dep_mm = (float(depression_volume_in_field_m3) / total_catchment_m2) * 1000.0

    # Construir lista de intervalos incluyendo cola de recesión post-lluvia (ΔP = 0)
    all_steps: list[dict] = [
        {
            "step_index": idx,
            "timestamp": iv["timestamp"],
            "precipitation_mm": float(iv["precipitation_mm"]),
            "interval_minutes": step_min,
            "is_recession": False,
        }
        for idx, iv in enumerate(intervals)
    ]
    last_ts = intervals[-1]["timestamp"]
    for r_idx in range(1, recession_steps + 1):
        all_steps.append({
            "step_index": len(all_steps),
            "timestamp": f"{last_ts} (+{r_idx * step_min} min recesión)",
            "precipitation_mm": 0.0,
            "interval_minutes": step_min,
            "is_recession": True,
        })

    cum_p_mm = 0.0
    prev_cum_q_mm = 0.0
    prev_cum_loss_mm = 0.0
    storage_transit_mm = 0.0
    depression_retained_mm = 0.0
    cum_outflow_mm = 0.0

    frames: list[dict] = []
    max_transit_mm = 0.0
    peak_step_index = 0

    for st in all_steps:
        dp = st["precipitation_mm"]
        cum_p_mm += dp

        cn_state = compute_nrcs_cn(
            precipitation_mm=cum_p_mm,
            cn_ii_base=cn_ii_base,
            antecedent_moisture=antecedent_moisture,
            lambda_ratio=lambda_ratio,
        )
        cum_q_mm = cn_state.runoff_q_mm
        cum_loss_mm = cn_state.total_retention_losses_mm

        dq_mm = max(0.0, cum_q_mm - prev_cum_q_mm)
        dloss_mm = max(0.0, cum_loss_mm - prev_cum_loss_mm)
        prev_cum_q_mm = cum_q_mm
        prev_cum_loss_mm = cum_loss_mm

        # Parte del nuevo excedente ΔQ llena primero la capacidad disponible en depresiones conservadas
        dep_free_mm = max(0.0, max_dep_mm - depression_retained_mm)
        to_dep_mm = min(dep_free_mm, 0.35 * dq_mm)
        depression_retained_mm += to_dep_mm

        # El resto ingresa al almacenamiento superficial en tránsito sobre las laderas/vías MFD
        available_transit_mm = storage_transit_mm + (dq_mm - to_dep_mm)
        outflow_step_mm = k_drain * available_transit_mm
        storage_transit_mm = max(0.0, available_transit_mm - outflow_step_mm)
        cum_outflow_mm += outflow_step_mm

        # Verificación estricta de balance de masa en el intervalo:
        # cum_p_mm == cum_loss_mm + depression_retained_mm + storage_transit_mm + cum_outflow_mm
        total_accounted_mm = cum_loss_mm + depression_retained_mm + storage_transit_mm + cum_outflow_mm
        balance_error_mm = abs(cum_p_mm - total_accounted_mm)

        if available_transit_mm > max_transit_mm:
            max_transit_mm = available_transit_mm
            peak_step_index = st["step_index"]

        frames.append({
            "step_index": st["step_index"],
            "timestamp": st["timestamp"],
            "interval_minutes": step_min,
            "is_recession": st["is_recession"],
            "interval_precipitation_mm": round(dp, 3),
            "cumulative_precipitation_mm": round(cum_p_mm, 3),
            "interval_infiltration_losses_mm": round(dloss_mm, 3),
            "cumulative_infiltration_losses_mm": round(cum_loss_mm, 3),
            "interval_runoff_generated_mm": round(dq_mm, 3),
            "cumulative_runoff_generated_mm": round(cum_q_mm, 3),
            "active_transit_lamina_mm": round(available_transit_mm, 3),
            "active_transit_volume_m3": round((available_transit_mm / 1000.0) * total_catchment_m2, 1),
            "depression_retained_mm": round(depression_retained_mm, 3),
            "depression_retained_volume_m3": round((depression_retained_mm / 1000.0) * total_catchment_m2, 1),
            "interval_outflow_mm": round(outflow_step_mm, 3),
            "interval_outflow_m3": round((outflow_step_mm / 1000.0) * total_catchment_m2, 1),
            "cumulative_outflow_mm": round(cum_outflow_mm, 3),
            "cumulative_outflow_m3": round((cum_outflow_mm / 1000.0) * total_catchment_m2, 1),
            "mass_balance_error_mm": round(balance_error_mm, 6),
        })

    # Normalizar factor de intensidad temporal (0..1) por frame para escalar la carga espacial y las partículas
    denom_transit = max(1e-4, max_transit_mm)
    for fr in frames:
        fr["transit_fraction_of_peak"] = round(fr["active_transit_lamina_mm"] / denom_transit, 4)

    max_err = max((fr["mass_balance_error_mm"] for fr in frames), default=0.0)
    return {
        "interval_minutes": step_min,
        "total_steps": len(frames),
        "rainfall_steps": len(intervals),
        "recession_steps": recession_steps,
        "routing_coefficient_k": round(k_drain, 4),
        "peak_step_index": peak_step_index,
        "peak_transit_lamina_mm": round(max_transit_mm, 3),
        "peak_transit_volume_m3": round((max_transit_mm / 1000.0) * total_catchment_m2, 1),
        "max_mass_balance_error_mm": round(max_err, 6),
        "frames": frames,
    }


def extract_3d_flow_particle_paths(
    dem: Dem,
    d8_code: np.ndarray,
    mfd_area_m2: np.ndarray,
    max_paths: int = 45,
    min_steps: int = 5,
) -> list[list[list[float]]]:
    """Extrae trayectorias 3D `[lon, lat, z_m]` a lo largo de las vías de concentración MFD/D8.

    Las partículas de la animación de Fase 3 se desplazan estrictamente sobre estas polilíneas
    calculadas por el modelo topográfico, con actividad proporcional a `transit_fraction_of_peak`
    de cada paso temporal (SDD §7.3 y §14 Fase 3).
    """
    alto, ancho = d8_code.shape
    cell_area = float(dem.pixel * dem.pixel)
    # Semillas en celdas con acumulación intermedia-alta (>= 4 celdas) ordenadas por área aportante
    valid = np.isfinite(mfd_area_m2) & np.isfinite(dem.z) & (d8_code > 0) & (mfd_area_m2 >= 4.0 * cell_area)
    rs, cs = np.nonzero(valid)
    if len(rs) == 0:
        return []

    areas = mfd_area_m2[rs, cs]
    order = np.argsort(-areas)
    # Distribuir semillas espacialmente evitando que todas nazcan en el mismo píxel
    stride = max(1, len(order) // (max_paths * 3))
    candidates = order[::stride]

    paths_rc: list[list[tuple[int, int]]] = []
    visited_starts: set[tuple[int, int]] = set()

    for idx in candidates:
        if len(paths_rc) >= max_paths:
            break
        sr, sc = int(rs[idx]), int(cs[idx])
        bucket = (sr // 2, sc // 2)
        if bucket in visited_starts:
            continue
        visited_starts.add(bucket)

        chain = [(sr, sc)]
        cr, cc = sr, sc
        seen_in_chain = {(sr, sc)}
        for _ in range(120):
            code = int(d8_code[cr, cc])
            if code == 0 or code not in CODE_TO_DELTA:
                break
            dr, dc = CODE_TO_DELTA[code]
            nr, nc = cr + dr, cc + dc
            if not (0 <= nr < alto and 0 <= nc < ancho) or (nr, nc) in seen_in_chain:
                break
            if not np.isfinite(dem.z[nr, nc]):
                break
            chain.append((nr, nc))
            seen_in_chain.add((nr, nc))
            cr, cc = nr, nc

        if len(chain) >= min_steps:
            paths_rc.append(chain)

    if not paths_rc:
        return []

    flat_r = [pt[0] for chain in paths_rc for pt in chain]
    flat_c = [pt[1] for chain in paths_rc for pt in chain]
    fx, fy = dem.xy_of_cell(flat_r, flat_c)
    flon, flat = to_crs(fx, fy, dem.crs, WGS84)

    paths_lonlatz: list[list[list[float]]] = []
    pos = 0
    for chain in paths_rc:
        n = len(chain)
        pts = []
        for i, (r, c) in enumerate(chain):
            pts.append([
                round(float(flon[pos + i]), 7),
                round(float(flat[pos + i]), 7),
                round(float(dem.z[r, c]), 2),
            ])
        pos += n
        paths_lonlatz.append(pts)

    return paths_lonlatz
