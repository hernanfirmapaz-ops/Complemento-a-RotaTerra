"""Solver hidrodinámico 2D de onda difusiva / aguas someras con ley de Manning (Fase 4, SDD §6.5, §6.6 y §14 Fase 4).

Resuelve explícitamente sobre la grilla métrica UTM la evolución temporal de:
- `water_depth_m` (h >= 0, profundidad física de la lámina de agua en metros),
- `velocity_m_s` (v >= 0, velocidad superficial estimada por Manning en m/s),
- `unit_discharge_m2_s` (q = h * v, caudal específico por unidad de ancho en m²/s).

Ecuaciones en cada sub-paso temporal dt:
1. Superficie libre del agua:
       eta(r, c) = z_bed(r, c) + h(r, c)
2. Entre cada celda (r, c) con h > h_dry y sus vecinas con eta_vecina < eta(r, c), el gradiente
   hidráulico es S_f = (eta - eta_vecina) / L.
3. Velocidad de Manning limitada por número de Froude máximo (Fr <= 1.2) para estabilidad física:
       v_manning = (1 / n) * (h_eff ** (2/3)) * sqrt(S_f)
       v = min(v_manning, 1.2 * sqrt(g * h_eff))
4. Conservación estricta de volumen en cada celda: la suma de caudales salientes en dt nunca puede
   exceder el volumen disponible `h * dx²`.

Estructuras hidráulicas relevadas (alcantarillas / canales de drenaje, SDD §6.2 y §14 Fase 4):
- Si el usuario registró observaciones de tipo `culvert` o `channel`, esas celdas reciben un
  rebaje local controlado de solera y menor rugosidad ($n = 0.025$).
"""

from __future__ import annotations

import math

import numpy as np

from geoprocessing.crs import WGS84, to_crs
from geoprocessing.dem.terrain import Dem
from geoprocessing.hydrology.flow import D8_TABLE
from geoprocessing.rainfall.nrcs_cn import AntecedentMoisture, compute_nrcs_cn

try:
    from numba import njit

    _HAS_NUMBA = True
except ImportError:
    _HAS_NUMBA = False

    def njit(*args, **kwargs):
        def decorator(func):
            return func

        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator

GRAVITY = 9.81
H_DRY_M = 1e-4  # 0.1 mm: umbral numérico de celda húmeda para tránsito

_DR_ARR = np.array([t[0] for t in D8_TABLE], dtype=np.int64)
_DC_ARR = np.array([t[1] for t in D8_TABLE], dtype=np.int64)
_DIST_ARR = np.array([t[4] for t in D8_TABLE], dtype=np.float64)
_CONTOUR_ARR = np.array([t[5] for t in D8_TABLE], dtype=np.float64)


@njit
def _shallow_water_substeps_numba(
    h: np.ndarray,
    max_h: np.ndarray,
    max_v: np.ndarray,
    max_q: np.ndarray,
    z_bed: np.ndarray,
    n_grid: np.ndarray,
    valid: np.ndarray,
    is_boundary: np.ndarray,
    dr_arr: np.ndarray,
    dc_arr: np.ndarray,
    dist_arr: np.ndarray,
    contour_arr: np.ndarray,
    dx: float,
    dt: float,
    cell_area_m2: float,
    rain_rate: float,
    n_sub: int,
) -> float:
    alto, ancho = h.shape
    total_outflow_m3 = 0.0

    dh_out = np.zeros((8, alto, ancho), dtype=np.float64)
    weight_sum = np.zeros((alto, ancho), dtype=np.float64)
    step_max_v = np.zeros((alto, ancho), dtype=np.float64)
    delta_h = np.zeros((alto, ancho), dtype=np.float64)

    for _ in range(n_sub):
        if rain_rate > 0.0:
            for r in range(alto):
                for c in range(ancho):
                    if valid[r, c]:
                        h[r, c] += rain_rate

        dh_out.fill(0.0)
        weight_sum.fill(0.0)
        step_max_v.fill(0.0)
        delta_h.fill(0.0)

        any_wet = False
        for r in range(alto):
            for c in range(ancho):
                if valid[r, c] and h[r, c] > H_DRY_M:
                    any_wet = True
                    break
            if any_wet:
                break
        if not any_wet:
            continue

        for r in range(alto):
            for c in range(ancho):
                if not (valid[r, c] and h[r, c] > H_DRY_M):
                    continue
                eta0 = z_bed[r, c] + h[r, c]
                h_src = h[r, c]
                n_src = n_grid[r, c]
                v_froude = 1.2 * math.sqrt(GRAVITY * h_src)
                w_sum = 0.0
                smv = 0.0

                for k in range(8):
                    nr = r + dr_arr[k]
                    nc = c + dc_arr[k]
                    if 0 <= nr < alto and 0 <= nc < ancho and valid[nr, nc]:
                        eta_n = z_bed[nr, nc] + h[nr, nc]
                        d_eta = eta0 - eta_n
                        if d_eta > 1e-5:
                            dist = dist_arr[k] * dx
                            width_eff = contour_arr[k] * dx
                            sf = d_eta / dist
                            v_man = (1.0 / n_src) * (h_src ** (2.0 / 3.0)) * math.sqrt(sf)
                            v_dir = min(v_man, v_froude)
                            dh = (v_dir * h_src * width_eff * dt) / cell_area_m2
                            max_t = 0.45 * max(0.0, d_eta)
                            if dh > max_t:
                                dh = max_t
                            dh_out[k, r, c] = dh
                            w_sum += dh
                            if v_dir > smv:
                                smv = v_dir
                weight_sum[r, c] = w_sum
                step_max_v[r, c] = smv

        for r in range(alto):
            for c in range(ancho):
                if valid[r, c] and h[r, c] > H_DRY_M and is_boundary[r, c]:
                    h_b = h[r, c]
                    v_b = min(
                        (1.0 / n_grid[r, c]) * (h_b ** (2.0 / 3.0)) * math.sqrt(0.005),
                        1.2 * math.sqrt(GRAVITY * h_b),
                    )
                    dh_bnd = min(0.5 * h_b, (v_b * h_b * dx * dt) / cell_area_m2)
                    w_bnd = weight_sum[r, c] + dh_bnd
                    scale_bnd = (h_b / max(1e-12, w_bnd)) if w_bnd > h_b else 1.0
                    dh_bnd_actual = dh_bnd * scale_bnd
                    h[r, c] -= dh_bnd_actual
                    total_outflow_m3 += dh_bnd_actual * cell_area_m2
                    if v_b > step_max_v[r, c]:
                        step_max_v[r, c] = v_b

        for r in range(alto):
            for c in range(ancho):
                if valid[r, c] and h[r, c] > H_DRY_M:
                    h_curr = h[r, c]
                    w = weight_sum[r, c]
                    s = (0.95 * h_curr / max(1e-12, w)) if w > 0.95 * h_curr else 1.0
                    for k in range(8):
                        dh = dh_out[k, r, c]
                        if dh > 0.0:
                            actual = dh * s
                            delta_h[r, c] -= actual
                            delta_h[r + dr_arr[k], c + dc_arr[k]] += actual

        for r in range(alto):
            for c in range(ancho):
                if valid[r, c]:
                    new_h = h[r, c] + delta_h[r, c]
                    if new_h < 0.0:
                        new_h = 0.0
                    h[r, c] = new_h
                    if new_h > max_h[r, c]:
                        max_h[r, c] = new_h
                    smv = step_max_v[r, c]
                    if smv > max_v[r, c]:
                        max_v[r, c] = smv
                    q = new_h * smv
                    if q > max_q[r, c]:
                        max_q[r, c] = q

    return total_outflow_m3

# Coeficientes de rugosidad de Manning n recomendados para superficies agrícolas (Chow 1959 / NRCS)
MANNING_N_BY_COVER: dict[str, float] = {
    "soja_maiz_sd_buena": 0.12,
    "soja_maiz_convencional": 0.06,
    "trigo_cereal_invierno_sd": 0.14,
    "cultivo_cobertura_vicia_centeno": 0.18,
    "pastura_pradera_buena": 0.20,
    "pastura_sobrepastoreada": 0.08,
    "barbecho_con_rastrojo": 0.10,
    "barbecho_suelo_desnudo": 0.035,
}


def apply_hydraulic_structures_to_bed(
    dem: Dem,
    z_bed: np.ndarray,
    manning_grid: np.ndarray,
    observations: list[dict] | None,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Incorpora alcantarillas (`culvert`) y canales (`channel`) registrados en el terreno (SDD §14 Fase 4)."""
    if not observations:
        return z_bed, manning_grid, 0
    struct_obs = [o for o in observations if o.get("observation_type") in ("culvert", "channel")]
    if not struct_obs:
        return z_bed, manning_grid, 0

    z_out = z_bed.copy()
    n_out = manning_grid.copy()
    alto, ancho = z_out.shape
    applied = 0

    lons = [float(o["lon"]) for o in struct_obs]
    lats = [float(o["lat"]) for o in struct_obs]
    xs, ys = to_crs(lons, lats, WGS84, dem.crs)
    rows, cols = dem.rowcol_f(xs, ys)

    for idx, obs in enumerate(struct_obs):
        r = int(round(float(rows[idx])))
        c = int(round(float(cols[idx])))
        if 0 <= r < alto and 0 <= c < ancho and np.isfinite(z_out[r, c]):
            depth_cut = float(obs.get("value") or 0.45)
            depth_cut = float(np.clip(depth_cut, 0.15, 2.0))
            # Aplicar apertura en la celda y sus 4 vecinas cardinales para conectar a través de bordos/caminos
            for dr, dc in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < alto and 0 <= nc < ancho and np.isfinite(z_out[nr, nc]):
                    z_out[nr, nc] -= depth_cut
                    n_out[nr, nc] = 0.025
            applied += 1

    return z_out, n_out, applied


def run_2d_diffusive_wave_simulation(
    dem: Dem,
    z_cond: np.ndarray,
    mascara_lote: np.ndarray,
    intervals: list[dict],
    cn_ii_base: float,
    antecedent_moisture: AntecedentMoisture,
    lambda_ratio: float,
    manning_n: float = 0.10,
    ponding_threshold_m: float = 0.05,
    observations: list[dict] | None = None,
    recession_minutes: int = 30,
    z_bed: np.ndarray | None = None,
) -> dict:
    """Ejecuta el solver 2D de onda difusiva con ley de Manning sobre la grilla UTM del lote.

    Devuelve para cada celda del DEM:
    - `max_water_depth_m`: profundidad máxima alcanzada durante el evento (m),
    - `final_water_depth_m`: profundidad remanente al final de la simulación (m),
    - `max_velocity_m_s`: velocidad máxima alcanzada (m/s),
    - `max_unit_discharge_m2_s`: caudal específico máximo por unidad de ancho (m²/s),
    y un resumen cuantitativo de zonas anegadas (`water_depth_m >= ponding_threshold_m`) y balance de masa.
    """
    dx = float(dem.pixel)
    cell_area_m2 = dx * dx
    alto, ancho = z_cond.shape
    valid = np.isfinite(z_cond)
    n_valid = int(valid.sum())
    if n_valid == 0:
        raise ValueError("El DEM no tiene celdas válidas para la simulación hidrodinámica 2D.")

    # Se usa la topografía original mínimamente tocada para permitir encharcamiento en bajos reales (Spec 005)
    z_bed = (dem.z if z_bed is None else z_bed).astype("float64").copy()
    n_grid = np.full((alto, ancho), float(np.clip(manning_n, 0.015, 0.50)), dtype="float64")
    z_bed, n_grid, structures_applied = apply_hydraulic_structures_to_bed(
        dem, z_bed, n_grid, observations
    )

    # Identificar celdas de borde del dominio (condición de borde de salida libre por pendiente local)
    is_boundary = np.zeros((alto, ancho), dtype=bool)
    is_boundary[0, :] = True
    is_boundary[-1, :] = True
    is_boundary[:, 0] = True
    is_boundary[:, -1] = True
    for dr, dc, _, _, _, _ in D8_TABLE:
        r_s = slice(max(0, -dr), alto - max(0, dr))
        c_s = slice(max(0, -dc), ancho - max(0, dc))
        r_d = slice(max(0, dr), alto - max(0, -dr))
        c_d = slice(max(0, dc), ancho - max(0, -dc))
        is_boundary[r_s, c_s] |= valid[r_s, c_s] & (~valid[r_d, c_d])

    # Construir serie de pasos de entrada de lluvia efectiva ΔQ (en metros de lámina por intervalo)
    step_min = int(intervals[0]["interval_minutes"]) if intervals else 15
    rec_steps = max(1, int(round(recession_minutes / max(1, step_min))))

    cum_p_mm = 0.0
    prev_q_mm = 0.0
    prev_loss_mm = 0.0
    forcing_steps: list[tuple[float, float]] = []  # (duración_s, dQ_m)
    for iv in intervals:
        dp = float(iv["precipitation_mm"])
        cum_p_mm += dp
        st = compute_nrcs_cn(cum_p_mm, cn_ii_base, antecedent_moisture, lambda_ratio)
        dq_mm = max(0.0, st.runoff_q_mm - prev_q_mm)
        prev_q_mm = st.runoff_q_mm
        prev_loss_mm = st.total_retention_losses_mm
        forcing_steps.append((step_min * 60.0, dq_mm / 1000.0))

    for _ in range(rec_steps):
        forcing_steps.append((step_min * 60.0, 0.0))

    # Sub-paso temporal explícito dt_s (según tamaño de celda dx)
    dt_s = float(np.clip(dx * 0.4, 3.0, 20.0))

    h = np.zeros((alto, ancho), dtype="float64")
    max_h = np.zeros((alto, ancho), dtype="float64")
    max_v = np.zeros((alto, ancho), dtype="float64")
    max_q = np.zeros((alto, ancho), dtype="float64")

    total_input_runoff_m = 0.0
    total_boundary_outflow_m3 = 0.0

    for dur_s, dq_m in forcing_steps:
        n_sub = max(1, int(math.ceil(dur_s / dt_s)))
        dt = dur_s / n_sub
        rain_rate_m_per_sub = dq_m / n_sub

        if _HAS_NUMBA:
            if rain_rate_m_per_sub > 0.0:
                total_input_runoff_m += rain_rate_m_per_sub * n_sub
            total_boundary_outflow_m3 += _shallow_water_substeps_numba(
                h,
                max_h,
                max_v,
                max_q,
                z_bed,
                n_grid,
                valid,
                is_boundary,
                _DR_ARR,
                _DC_ARR,
                _DIST_ARR,
                _CONTOUR_ARR,
                dx,
                dt,
                cell_area_m2,
                rain_rate_m_per_sub,
                n_sub,
            )
        else:
            for _ in range(n_sub):
                if rain_rate_m_per_sub > 0.0:
                    h[valid] += rain_rate_m_per_sub
                    total_input_runoff_m += rain_rate_m_per_sub

                eta = z_bed + h
                wet = valid & (h > H_DRY_M)
                if not wet.any():
                    continue

                # Calcular velocidades y flujos salientes hacia los 8 vecinos
                out_flux = []
                weight_sum = np.zeros((alto, ancho), dtype="float64")
                step_max_v = np.zeros((alto, ancho), dtype="float64")

                for dr, dc, _, _, dist_f, contour_f in D8_TABLE:
                    dist = dist_f * dx
                    width_eff = contour_f * dx
                    r_s = slice(max(0, -dr), alto - max(0, dr))
                    c_s = slice(max(0, -dc), ancho - max(0, dc))
                    r_d = slice(max(0, dr), alto - max(0, -dr))
                    c_d = slice(max(0, dc), ancho - max(0, -dc))

                    d_eta = eta[r_s, c_s] - eta[r_d, c_d]
                    active = wet[r_s, c_s] & valid[r_d, c_d] & (d_eta > 1e-5)

                    sf = np.where(active, d_eta / dist, 0.0)
                    h_src = np.where(active, h[r_s, c_s], 0.0)
                    n_src = n_grid[r_s, c_s]

                    v_man = np.where(active, (1.0 / n_src) * np.power(h_src, 2.0 / 3.0) * np.sqrt(sf), 0.0)
                    v_froude = 1.2 * np.sqrt(GRAVITY * h_src)
                    v_dir = np.minimum(v_man, v_froude)

                    # Volumen potencial saliente en esa dirección expresado en altura de celda (m)
                    dh_out = (v_dir * h_src * width_eff * dt) / cell_area_m2
                    # No transferir más que la mitad del desnivel de superficie libre para evitar oscilación
                    dh_out = np.minimum(dh_out, 0.45 * np.maximum(0.0, d_eta))

                    out_flux.append((r_s, c_s, r_d, c_d, dh_out))
                    weight_sum[r_s, c_s] += dh_out
                    step_max_v[r_s, c_s] = np.maximum(step_max_v[r_s, c_s], v_dir)

                # Condición de borde de salida libre en el perímetro del dominio (pendiente normal S_0 = 0.005)
                bnd_wet = wet & is_boundary
                if bnd_wet.any():
                    h_b = h[bnd_wet]
                    v_b = np.minimum(
                        (1.0 / n_grid[bnd_wet]) * np.power(h_b, 2.0 / 3.0) * math.sqrt(0.005),
                        1.2 * np.sqrt(GRAVITY * h_b),
                    )
                    dh_bnd = np.minimum(0.5 * h_b, (v_b * h_b * dx * dt) / cell_area_m2)
                    weight_sum_bnd = weight_sum[bnd_wet] + dh_bnd
                    scale_bnd = np.where(weight_sum_bnd > h_b, h_b / np.maximum(1e-12, weight_sum_bnd), 1.0)
                    dh_bnd_actual = dh_bnd * scale_bnd
                    h[bnd_wet] -= dh_bnd_actual
                    total_boundary_outflow_m3 += float(dh_bnd_actual.sum() * cell_area_m2)
                    step_max_v[bnd_wet] = np.maximum(step_max_v[bnd_wet], v_b)

                # Factor limitador por celda para garantizar positividad estricta (sum(dh_out) <= 0.95 * h)
                scale = np.where(weight_sum > 0.95 * h, (0.95 * h) / np.maximum(1e-12, weight_sum), 1.0)

                delta_h = np.zeros((alto, ancho), dtype="float64")
                for r_s, c_s, r_d, c_d, dh_out in out_flux:
                    actual = dh_out * scale[r_s, c_s]
                    delta_h[r_s, c_s] -= actual
                    delta_h[r_d, c_d] += actual

                h += delta_h
                np.maximum(h, 0.0, out=h)

                np.maximum(max_h, h, out=max_h)
                np.maximum(max_v, step_max_v, out=max_v)
                np.maximum(max_q, h * step_max_v, out=max_q)

    # Verificación de conservación de masa en todo el dominio 2D:
    # Volumen total de lluvia efectiva ingresado == Volumen almacenado final + Volumen exportado por bordes
    total_input_m3 = float(total_input_runoff_m * n_valid * cell_area_m2)
    final_storage_m3 = float(h[valid].sum() * cell_area_m2)
    accounted_m3 = final_storage_m3 + total_boundary_outflow_m3
    rel_mass_err = abs(total_input_m3 - accounted_m3) / max(1.0, total_input_m3)

    in_field_valid = mascara_lote & valid
    max_h_field = max_h[in_field_valid]
    final_h_field = h[in_field_valid]
    max_v_field = max_v[in_field_valid]
    max_q_field = max_q[in_field_valid]

    ponded_mask_field = in_field_valid & (max_h >= float(ponding_threshold_m))
    ponded_cells = int(ponded_mask_field.sum())
    ponded_area_ha = (ponded_cells * cell_area_m2) / 10_000.0
    field_total_ha = (int(in_field_valid.sum()) * cell_area_m2) / 10_000.0
    ponded_pct = (100.0 * ponded_area_ha / field_total_ha) if field_total_ha > 0 else 0.0
    ponded_vol_m3 = float(final_h_field[final_h_field >= float(ponding_threshold_m)].sum() * cell_area_m2)

    out_max_h = np.where(valid, max_h, np.nan).astype("float32")
    out_final_h = np.where(valid, h, np.nan).astype("float32")
    out_max_v = np.where(valid, max_v, np.nan).astype("float32")
    out_max_q = np.where(valid, max_q, np.nan).astype("float32")

    summary = {
        "manning_n": round(float(manning_n), 3),
        "ponding_threshold_m": round(float(ponding_threshold_m), 3),
        "hydraulic_structures_applied": structures_applied,
        "Effective_runoff_input_mm": round(float(total_input_runoff_m * 1000.0), 2),
        "infiltration_losses_mm": round(float(prev_loss_mm), 2),
        "max_water_depth_in_field_m": round(float(max_h_field.max()), 3) if max_h_field.size else 0.0,
        "mean_max_water_depth_in_field_m": round(float(max_h_field.mean()), 4) if max_h_field.size else 0.0,
        "final_retained_water_depth_max_m": round(float(final_h_field.max()), 3) if final_h_field.size else 0.0,
        "max_velocity_in_field_m_s": round(float(max_v_field.max()), 3) if max_v_field.size else 0.0,
        "max_unit_discharge_in_field_m2_s": round(float(max_q_field.max()), 4) if max_q_field.size else 0.0,
        "ponded_area_in_field_ha": round(ponded_area_ha, 3),
        "ponded_area_in_field_pct": round(ponded_pct, 2),
        "ponded_retained_volume_in_field_m3": round(ponded_vol_m3, 1),
        "domain_input_volume_m3": round(total_input_m3, 1),
        "domain_final_storage_m3": round(final_storage_m3, 1),
        "domain_boundary_outflow_m3": round(total_boundary_outflow_m3, 1),
        "mass_balance_relative_error": round(float(rel_mass_err), 6),
    }
    return {
        "max_water_depth_m": out_max_h,
        "final_water_depth_m": out_final_h,
        "max_velocity_m_s": out_max_v,
        "max_unit_discharge_m2_s": out_max_q,
        "summary": summary,
    }
