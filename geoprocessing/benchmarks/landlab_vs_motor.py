"""Benchmark comparativo: Motor 2D de onda difusiva vs Landlab OverlandFlow (de Almeida 2012).

Compara sobre el mismo relieve, lluvia neta y rugosidad de Manning:
1. Plano inclinado regular (pendiente uniforme).
2. Bajo cerrado sintético (depresión sin salida).
3. Terreno real de prueba (Parcela 205 de San Luis, tests/fixtures/lotes/).

Métricas evaluadas:
- Área anegada (> 2 cm, o 0.02 m de lámina de agua) en hectáreas.
- Profundidad máxima de agua alcanzada (m).
- Volumen final retenido / almacenado (m³).
- Volumen exportado fuera del lote / límites (m³).
- Diferencia porcentual en área anegada (|A_motor - A_landlab| / max(A_motor, A_landlab) * 100).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Permitir ejecución directa como script independiente
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from landlab import RasterModelGrid  # noqa: E402
from landlab.components import OverlandFlow  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402

from geoprocessing.dem.terrain import Dem  # noqa: E402
from geoprocessing.hydrology.shallow_water_2d import run_2d_diffusive_wave_simulation  # noqa: E402
from geoprocessing.rainfall.nrcs_cn import compute_nrcs_cn  # noqa: E402


def run_benchmark_case(
    case_name: str,
    z_2d: np.ndarray,
    dx: float,
    intervals: list[dict],
    cn_ii: float,
    manning_n: float = 0.08,
    is_closed: bool = False,
    recession_minutes: int = 15,
    ponding_threshold_m: float = 0.02,
) -> dict:
    """Ejecuta ambos motores sobre la misma configuración física y calcula métricas."""
    alto, ancho = z_2d.shape
    cell_area_m2 = float(dx * dx)

    # Grilla interior (excluyendo borde perimetral para aislar diferencias en la condición de contorno)
    inner_mask = np.zeros((alto, ancho), dtype=bool)
    inner_mask[1:-1, 1:-1] = True
    inner_cells = int(np.sum(inner_mask))
    inner_ha = (inner_cells * cell_area_m2) / 10_000.0

    # 1. Simulación con Motor 2D RotaTerra (onda difusiva con Manning)
    transform = from_origin(500_000.0, 6_000_000.0, dx, dx)
    dem = Dem(z=z_2d.astype("float32"), transform=transform, crs="EPSG:32720")

    res_motor = run_2d_diffusive_wave_simulation(
        dem=dem,
        z_cond=z_2d,
        mascara_lote=inner_mask,
        intervals=intervals,
        cn_ii_base=cn_ii,
        antecedent_moisture="medium",
        lambda_ratio=0.2,
        manning_n=manning_n,
        recession_minutes=recession_minutes,
        ponding_threshold_m=ponding_threshold_m,
        solver_mode="inertial",
        is_closed=is_closed,
    )

    h_mot_max = res_motor["max_water_depth_m"]
    h_mot_final = res_motor["final_water_depth_m"]

    area_mot_ha = float(np.sum(h_mot_max[inner_mask] >= ponding_threshold_m) * cell_area_m2 / 10_000.0)
    max_d_mot = float(np.nanmax(h_mot_max[inner_mask]))
    vol_stored_mot = float(np.nansum(h_mot_final[inner_mask]) * cell_area_m2)
    vol_out_mot = float(res_motor["summary"]["domain_boundary_outflow_m3"])

    # 2. Simulación con Landlab OverlandFlow (de Almeida et al. 2012)
    grid = RasterModelGrid((alto, ancho), xy_spacing=dx)
    z_landlab = np.flipud(z_2d).astype(np.float64).flatten()
    grid.add_field("topographic__elevation", z_landlab, at="node")
    grid.add_zeros("surface_water__depth", at="node", dtype=np.float64)

    if is_closed:
        grid.set_closed_boundaries_at_grid_edges(True, True, True, True)

    of = OverlandFlow(grid, mannings_n=manning_n, steep_slopes=True)

    # Construir serie de lluvia efectiva idéntica (NRCS-CN)
    step_min = int(intervals[0]["interval_minutes"])
    cum_p = 0.0
    prev_q = 0.0
    forcing_steps: list[tuple[float, float]] = []
    for iv in intervals:
        cum_p += float(iv["precipitation_mm"])
        st = compute_nrcs_cn(cum_p, cn_ii, "medium", 0.2)
        dq_m = max(0.0, st.runoff_q_mm - prev_q) / 1000.0
        prev_q = st.runoff_q_mm
        forcing_steps.append((step_min * 60.0, dq_m))

    rec_steps = max(1, int(round(recession_minutes / max(1, step_min))))
    for _ in range(rec_steps):
        forcing_steps.append((step_min * 60.0, 0.0))

    max_h_ll_arr = np.zeros(grid.number_of_nodes, dtype=np.float64)
    total_rain_vol_ll = 0.0

    for dur_s, dq_m in forcing_steps:
        elapsed = 0.0
        rain_rate = dq_m / dur_s
        while elapsed < dur_s:
            # Sub-paso CFL adaptativo acotado a 10s para resolución gradual de lluvia
            dt = min(of.calc_time_step(), 10.0, dur_s - elapsed)
            if rain_rate > 0.0:
                grid.at_node["surface_water__depth"][grid.core_nodes] += rain_rate * dt
                total_rain_vol_ll += rain_rate * dt * len(grid.core_nodes) * cell_area_m2
            of.overland_flow(dt=dt)
            np.maximum(max_h_ll_arr, grid.at_node["surface_water__depth"], out=max_h_ll_arr)
            elapsed += dt

    h_ll_final_2d = np.flipud(grid.at_node["surface_water__depth"].reshape((alto, ancho)))
    h_ll_max_2d = np.flipud(max_h_ll_arr.reshape((alto, ancho)))

    area_ll_ha = float(np.sum(h_ll_max_2d[inner_mask] >= ponding_threshold_m) * cell_area_m2 / 10_000.0)
    max_d_ll = float(np.nanmax(h_ll_max_2d[inner_mask]))
    vol_stored_ll = float(np.nansum(h_ll_final_2d[inner_mask]) * cell_area_m2)
    vol_out_ll = max(0.0, total_rain_vol_ll - vol_stored_ll)

    # Comparación cuantitativa
    diff_area_ha = abs(area_mot_ha - area_ll_ha)
    denom_area = max(1e-4, max(area_mot_ha, area_ll_ha))
    diff_area_pct = 100.0 * diff_area_ha / denom_area

    vol_diff_pct = 100.0 * abs(vol_stored_mot - vol_stored_ll) / max(1.0, max(vol_stored_mot, vol_stored_ll))
    passes_15pct_criterion = bool(diff_area_pct < 15.0)

    return {
        "case": case_name,
        "grid_shape": [alto, ancho],
        "pixel_dx_m": dx,
        "inner_area_ha": round(inner_ha, 3),
        "motor": {
            "ponded_area_ha": round(area_mot_ha, 3),
            "max_depth_m": round(max_d_mot, 4),
            "stored_volume_m3": round(vol_stored_mot, 1),
            "outflow_volume_m3": round(vol_out_mot, 1),
        },
        "landlab": {
            "ponded_area_ha": round(area_ll_ha, 3),
            "max_depth_m": round(max_d_ll, 4),
            "stored_volume_m3": round(vol_stored_ll, 1),
            "outflow_volume_m3": round(vol_out_ll, 1),
        },
        "differences": {
            "ponded_area_diff_pct": round(diff_area_pct, 2),
            "stored_volume_diff_pct": round(vol_diff_pct, 2),
            "passes_15pct_area_criterion": passes_15pct_criterion,
        },
    }


def run_all_benchmarks(fixtures_dir: Path | None = None) -> list[dict]:
    """Ejecuta los tres casos de benchmark y retorna la lista de resultados."""
    if fixtures_dir is None:
        fixtures_dir = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "lotes"

    results = []

    # Caso 1: Plano inclinado (30x30, 10m pixel, pendiente uniforme 0.5% a lo largo de X)
    y, x = np.mgrid[:30, :30]
    z_plane = (100.0 - 0.005 * x * 10.0).astype("float32")
    res_1 = run_benchmark_case(
        case_name="Plano inclinado uniforme (pendiente 0.5%)",
        z_2d=z_plane,
        dx=10.0,
        intervals=[{"interval_minutes": 15, "precipitation_mm": 30.0}],
        cn_ii=85.0,
        manning_n=0.08,
        is_closed=False,
    )
    results.append(res_1)

    # Caso 2: Bajo cerrado sintético (30x30, 10m pixel, depresión central de 0.3 m)
    z_bowl = (100.0 + 0.002 * ((x - 15) ** 2 + (y - 15) ** 2)).astype("float32")
    z_bowl[13:17, 13:17] -= 0.30
    res_2 = run_benchmark_case(
        case_name="Bajo cerrado sintético (depresión sin salida)",
        z_2d=z_bowl,
        dx=10.0,
        intervals=[{"interval_minutes": 15, "precipitation_mm": 30.0}],
        cn_ii=85.0,
        manning_n=0.08,
        is_closed=True,
    )
    results.append(res_2)

    # Caso 3: Terreno real de prueba Parcela 205 (San Luis)
    tif_path = fixtures_dir / "san_luis_parcela_205_dem.tif"
    with rasterio.open(tif_path) as src:
        z_parcela = src.read(1)
        res_x = float(src.res[0])

    res_3 = run_benchmark_case(
        case_name="Relieve real de prueba: Parcela 205 (San Luis, 86x58)",
        z_2d=z_parcela,
        dx=res_x,
        intervals=[{"interval_minutes": 15, "precipitation_mm": 30.0}],
        cn_ii=80.0,
        manning_n=0.08,
        is_closed=False,
    )
    results.append(res_3)

    return results


if __name__ == "__main__":
    results = run_all_benchmarks()
    print("\n" + "=" * 80)
    print("RESULTADOS DEL BENCHMARK LANDLAB VS MOTOR 2D")
    print("=" * 80)
    for r in results:
        print(f"\nCaso: {r['case']}")
        print(f"  Dimensiones: {r['grid_shape']}, celda: {r['pixel_dx_m']} m, área interior: {r['inner_area_ha']} ha")
        print(f"  Motor 2D RotaTerra : Área={r['motor']['ponded_area_ha']} ha, ProfMax={r['motor']['max_depth_m']} m, VolRet={r['motor']['stored_volume_m3']} m³")
        print(f"  Landlab OverlandFlow: Área={r['landlab']['ponded_area_ha']} ha, ProfMax={r['landlab']['max_depth_m']} m, VolRet={r['landlab']['stored_volume_m3']} m³")
        print(f"  Diferencia Área: {r['differences']['ponded_area_diff_pct']}% | Diferencia Vol: {r['differences']['stored_volume_diff_pct']}% | Cumple (<15%): {r['differences']['passes_15pct_area_criterion']}")
    print("\n" + json.dumps(results, indent=2))
