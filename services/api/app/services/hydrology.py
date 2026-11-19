"""Orquestación del análisis topográfico e hidrología estática de Fase 1 (SDD §6.2–6.3 y §14 Fase 1)."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import rasterio

from geoprocessing import PROCESSING_VERSION
from geoprocessing.dem.quality import field_mask
from geoprocessing.dem.terrain import Dem, contours_geojson
from geoprocessing.hydrology.conditioning import condition_dem
from geoprocessing.hydrology.flow import (
    CODE_TO_LABEL,
    d8_direction_and_accumulation,
    default_stream_threshold_ha,
    extract_drainage_network_and_basins,
    mfd_accumulation,
)
from geoprocessing.rainfall.events import (
    SOURCE_PRESETS,
    build_event_metadata,
    parse_rainfall_csv,
)
from geoprocessing.rainfall.nrcs_cn import (
    CN_II_LOOKUP,
    compare_runoff_scenarios,
    compute_nrcs_cn,
    distribute_event_runoff_mfd,
    lookup_cn_ii,
)
from services.api.app.core.config import SAMPLE_DIR
from services.api.app.schemas import HydrologyRunIn, RainfallEventManualIn, RunoffRunIn
from services.api.app.services import store

LIMITACIONES_FASE1 = [
    "Fase 1 (Hidrología estática): las direcciones D8, acumulaciones MFD/D8, depresiones y rutas de drenaje "
    "son puramente topográficas (derivadas del DEM). No representan caudales en m³/s, velocidad ni profundidad "
    "de lámina de agua ante una tormenta.",
    "El acondicionamiento selectivo ('fill_small') rellena solo micro-depresiones menores a los umbrales "
    "configurados y conserva los bajos mayores como retenciones reales.",
    "Con un DEM de 30 m (Copernicus GLO-30), las rutas potenciales reflejan el macro-drenaje de la ladera; "
    "alcantarillas, cunetas, bordos, huellas o terrazas no relevadas no están representadas.",
]


def run_static_hydrology(field_id: str, params: HydrologyRunIn) -> dict:
    field = store.load_field(field_id)
    terreno = store.load_terrain(field_id)
    carpeta = store.field_dir(field_id)
    dem = Dem.open(carpeta / "dem_utm.tif")
    mascara = field_mask(field["geometry"], field["utm_epsg"], dem.transform, dem.z.shape)

    burn_lines = (
        [[[float(lon), float(lat)] for lon, lat in line] for line in params.burn_lines]
        if params.burn_lines
        else None
    )

    z_cond, sink_depth_m, dep_id_grid, depressions = condition_dem(
        dem=dem,
        mascara_lote=mascara,
        mode=params.conditioning_mode,
        max_fill_depth_m=params.max_fill_depth_m,
        max_fill_area_m2=params.max_fill_area_m2,
        burn_lines_lonlat=burn_lines,
        burn_depth_m=params.burn_depth_m,
    )

    # Guardar el DEM acondicionado como archivo derivado sin tocar dem_utm.tif ni source/
    cond_path = carpeta / "dem_conditioned_utm.tif"
    with rasterio.open(
        cond_path,
        "w",
        driver="GTiff",
        height=z_cond.shape[0],
        width=z_cond.shape[1],
        count=1,
        dtype="float32",
        crs=dem.crs,
        transform=dem.transform,
        nodata=np.nan,
        compress="deflate",
    ) as dst:
        dst.write(z_cond, 1)
        dst.update_tags(
            DERIVED_FROM="dem_utm.tif",
            CONDITIONING_MODE=params.conditioning_mode,
            MAX_FILL_DEPTH_M=str(params.max_fill_depth_m),
            MAX_FILL_AREA_M2=str(params.max_fill_area_m2),
        )

    d8_code, d8_az, d8_cells, d8_area_m2 = d8_direction_and_accumulation(z_cond, dem.pixel)
    mfd_cells, mfd_area_m2, mfd_balance = mfd_accumulation(
        z_cond, dem.pixel, exponent_p=params.mfd_exponent
    )

    threshold_ha = (
        float(params.stream_threshold_ha)
        if params.stream_threshold_ha is not None
        else default_stream_threshold_ha(field["area_ha"], dem.pixel)
    )

    network_geojson, subbasin_grid, outlets_info = extract_drainage_network_and_basins(
        dem=dem,
        mascara_lote=mascara,
        d8_code=d8_code,
        d8_area_m2=d8_area_m2,
        mfd_area_m2=mfd_area_m2,
        threshold_ha=threshold_ha,
        routing_basis=params.routing_basis,
    )

    contours = contours_geojson(dem, interval_m=params.contour_interval_m)

    # Persistir grillas hidrológicas comprimidas para consulta rápida en malla 3D e inspector de punto
    np.savez_compressed(
        carpeta / "hydrology_grids.npz",
        z_cond=z_cond,
        sink_depth_m=sink_depth_m,
        depression_id=dep_id_grid,
        d8_code=d8_code,
        d8_azimuth_deg=d8_az,
        d8_area_m2=d8_area_m2,
        mfd_area_m2=mfd_area_m2,
        subbasin_id=subbasin_grid,
    )

    deps_in_field = [d for d in depressions if d.in_field]
    deps_filled = [d for d in depressions if d.filled_in_run]
    mfd_in_field = mfd_area_m2[mascara & np.isfinite(mfd_area_m2)]
    d8_in_field = d8_area_m2[mascara & np.isfinite(d8_area_m2)]
    sink_in_field = sink_depth_m[mascara & np.isfinite(sink_depth_m)]

    total_stream_len = sum(
        float(feat["properties"].get("length_m", 0.0)) for feat in network_geojson["features"]
    )
    ext_inflow_ha = sum(float(o["subbasin_external_inflow_ha"]) for o in outlets_info)

    summary = {
        "depressions_count": len(depressions),
        "depressions_in_field_count": len(deps_in_field),
        "depressions_filled_count": len(deps_filled),
        "total_depression_area_in_field_ha": round(sum(d.area_ha for d in deps_in_field), 4),
        "total_depression_volume_in_field_m3": round(sum(d.volume_m3 for d in deps_in_field), 1),
        "max_depression_depth_in_field_m": round(float(sink_in_field.max()), 3) if sink_in_field.size else 0.0,
        "max_mfd_area_in_field_ha": round(float(mfd_in_field.max()) / 10_000.0, 3) if mfd_in_field.size else 0.0,
        "max_d8_area_in_field_ha": round(float(d8_in_field.max()) / 10_000.0, 3) if d8_in_field.size else 0.0,
        "stream_segments_count": len(network_geojson["features"]),
        "total_stream_length_m": round(total_stream_len, 1),
        "outlets_count": len(outlets_info),
        "external_inflow_ha": round(ext_inflow_ha, 3),
        "mfd_mass_balance_error": round(float(mfd_balance["relative_error"]), 8),
    }

    avisos = [w["message"] for w in terreno["quality"]["warnings"] if w["level"] in ("critico", "advertencia")]
    if params.conditioning_mode == "fill_all" and deps_in_field:
        avisos.append(
            f"Se rellenaron todas las depresiones ({len(deps_in_field)} dentro del lote) para forzar drenaje "
            "continuo. Si el lote tiene bajos reales que retienen agua, compará con 'fill_small' o 'preserve'."
        )
    if ext_inflow_ha > 0.5:
        avisos.append(
            f"Se detectan ~{ext_inflow_ha:.1f} ha de área contribuyente externa que ingresa al lote desde aguas arriba."
        )

    hydro_doc = {
        "field_id": field_id,
        "processing_version": PROCESSING_VERSION,
        "processed_at": store.now_iso(),
        "parameters": {
            "conditioning_mode": params.conditioning_mode,
            "max_fill_depth_m": params.max_fill_depth_m,
            "max_fill_area_m2": params.max_fill_area_m2,
            "mfd_exponent": params.mfd_exponent,
            "stream_threshold_ha": threshold_ha,
            "routing_basis": params.routing_basis,
            "contour_interval_m": contours["interval_m"],
            "burn_lines_count": len(burn_lines) if burn_lines else 0,
            "burn_depth_m": params.burn_depth_m if burn_lines else 0.0,
        },
        "summary": summary,
        "depressions": [d.to_dict() for d in depressions],
        "outlets": outlets_info,
        "drainage_network": network_geojson,
        "contours": contours,
        "warnings": avisos,
        "limitations": LIMITACIONES_FASE1,
    }
    store.save_hydrology(field_id, hydro_doc)
    load_hydrology_grids.cache_clear()
    return hydro_doc


@lru_cache(maxsize=8)
def load_hydrology_grids(field_id: str, processed_at: str) -> dict[str, np.ndarray]:
    npz_path = store.field_dir(field_id) / "hydrology_grids.npz"
    with np.load(npz_path) as data:
        return {k: data[k] for k in data.files}


def optional_hydrology_grids(field_id: str) -> dict[str, np.ndarray] | None:
    carpeta = store.field_dir(field_id)
    if not (carpeta / "hydrology.json").exists() or not (carpeta / "hydrology_grids.npz").exists():
        return None
    hydro = store.load_hydrology(field_id)
    return load_hydrology_grids(field_id, hydro["processed_at"])


def point_hydrology_attrs(grids: dict[str, np.ndarray], row: int, col: int) -> dict:
    code = int(grids["d8_code"][row, col])
    az = float(grids["d8_azimuth_deg"][row, col])
    d8_m2 = float(grids["d8_area_m2"][row, col])
    mfd_m2 = float(grids["mfd_area_m2"][row, col])
    sink_d = float(grids["sink_depth_m"][row, col])
    dep_id = int(grids["depression_id"][row, col])
    bas_id = int(grids["subbasin_id"][row, col])
    return {
        "sink_depth_m": round(sink_d, 3) if np.isfinite(sink_d) else None,
        "depression_id": dep_id if dep_id > 0 else None,
        "d8_code": code,
        "d8_direction": CODE_TO_LABEL.get(code, "s/d"),
        "d8_azimuth_deg": round(az, 1) if np.isfinite(az) else None,
        "d8_area_m2": round(d8_m2, 1) if np.isfinite(d8_m2) else None,
        "d8_area_ha": round(d8_m2 / 10_000.0, 4) if np.isfinite(d8_m2) else None,
        "mfd_area_m2": round(mfd_m2, 1) if np.isfinite(mfd_m2) else None,
        "mfd_area_ha": round(mfd_m2 / 10_000.0, 4) if np.isfinite(mfd_m2) else None,
        "subbasin_id": bas_id if bas_id > 0 else None,
    }


LIMITACIONES_FASE2 = [
    "Fase 2 (Modelo de evento NRCS Curve Number + enrutamiento MFD): calcula escorrentía directa "
    "acumulada del evento (Q, en mm) y carga potencial acumulada por celda (runoff_load_mm / m³).",
    "NO representa profundidad instantánea de inundación (water_depth_m), velocidad física (m/s) ni "
    "hidrograma hidrodinámico 2D resuelto (SDD §6.4 y §14 Fase 2).",
    "El Número de Curva (CN) es un parámetro empírico de evento que requiere validación local con "
    "infiltración, textura, cobertura real y observaciones de campo.",
]


def get_hydrology_catalog() -> dict:
    return {
        "covers": [
            {"code": code, "label": info["label"], "cn_ii_by_soil_group": info["values"]}
            for code, info in CN_II_LOOKUP.items()
        ],
        "soil_groups": [
            {"code": "A", "description": "Grupo A — Alta infiltración (arenosos profundos, bien drenados)"},
            {"code": "B", "description": "Grupo B — Infiltración moderada (francos / franco-limosos bien estructurados)"},
            {"code": "C", "description": "Grupo C — Infiltración lenta (franco-arcillosos o con impedancia subsuperficial)"},
            {"code": "D", "description": "Grupo D — Muy baja infiltración (arcillosos expansivos, sódicos o napa somera)"},
        ],
        "antecedent_moisture_options": [
            {"code": "dry", "label": "AMC I — Seca (suelo seco al inicio del evento)"},
            {"code": "medium", "label": "AMC II — Media / Normal (condición de referencia NRCS)"},
            {"code": "wet", "label": "AMC III — Húmeda (lluvias previas recientes / suelo cercano a capacidad de campo)"},
        ],
        "rainfall_sources": [
            {"code": code, **meta} for code, meta in SOURCE_PRESETS.items()
        ],
    }


def create_manual_rainfall_event(field_id: str, payload: RainfallEventManualIn) -> dict:
    store.load_field(field_id)
    now = store.now_iso()
    start_at = payload.start_at or now
    end_at = payload.end_at or start_at
    meta, warnings = build_event_metadata(
        source_type=payload.source_type,
        total_mm=payload.total_mm,
        start_at=start_at,
        end_at=end_at,
        has_time_series=False,
        interval_minutes=None,
        custom_source_product=payload.source_product,
        custom_spatial_resolution=payload.spatial_resolution,
        quality_flag=payload.quality_flag,
        custom_uncertainty_note=payload.uncertainty_note,
    )
    event = {
        "id": store.new_id(),
        "field_id": field_id,
        "name": payload.name.strip(),
        "total_mm": round(float(payload.total_mm), 2),
        "source_type": payload.source_type,
        "start_at": start_at,
        "end_at": end_at,
        "has_time_series": False,
        "interval_minutes": None,
        "intervals": [],
        "max_intensity_mm_h": None,
        "source_metadata": meta,
        "warnings": warnings,
        "created_at": now,
    }
    events = store.list_rainfall_events(field_id)
    events.insert(0, event)
    store.save_rainfall_events(field_id, events)
    return event


def import_csv_rainfall_event(
    field_id: str,
    csv_bytes: bytes | str,
    name: str,
    source_type: str = "gauge",
    declared_total_mm: float | None = None,
) -> dict:
    store.load_field(field_id)
    rep = parse_rainfall_csv(csv_bytes, declared_total_mm=declared_total_mm)
    now = store.now_iso()
    meta, meta_warnings = build_event_metadata(
        source_type=source_type,
        total_mm=rep.total_mm,
        start_at=rep.start_at,
        end_at=rep.end_at,
        has_time_series=True,
        interval_minutes=rep.interval_minutes,
    )
    event = {
        "id": store.new_id(),
        "field_id": field_id,
        "name": name.strip() or "Tormenta CSV",
        "total_mm": rep.total_mm,
        "source_type": source_type,
        "start_at": rep.start_at,
        "end_at": rep.end_at,
        "has_time_series": True,
        "interval_minutes": rep.interval_minutes,
        "intervals": [iv.to_dict() for iv in rep.intervals],
        "max_intensity_mm_h": rep.max_intensity_mm_h,
        "source_metadata": meta,
        "warnings": rep.warnings + meta_warnings,
        "created_at": now,
    }
    events = store.list_rainfall_events(field_id)
    events.insert(0, event)
    store.save_rainfall_events(field_id, events)
    return event


def load_sample_rainfall_event(field_id: str) -> dict:
    store.load_field(field_id)
    for ev in store.list_rainfall_events(field_id):
        if ev.get("name") == "Tormenta Pluviómetro Local 80 mm (CSV 15 min)":
            return ev
    sample_csv = SAMPLE_DIR / "evento_tormenta_pluvio.csv"
    return import_csv_rainfall_event(
        field_id=field_id,
        csv_bytes=sample_csv.read_bytes(),
        name="Tormenta Pluviómetro Local 80 mm (CSV 15 min)",
        source_type="gauge",
        declared_total_mm=80.0,
    )


def execute_runoff_run(field_id: str, payload: RunoffRunIn) -> dict:
    field = store.load_field(field_id)
    terreno = store.load_terrain(field_id)
    carpeta = store.field_dir(field_id)

    # Si aún no se corrió la hidrología estática de Fase 1, ejecutarla con parámetros por defecto
    if not (carpeta / "hydrology.json").exists() or not (carpeta / "hydrology_grids.npz").exists():
        run_static_hydrology(field_id, HydrologyRunIn())

    hydro = store.load_hydrology(field_id)
    grids = load_hydrology_grids(field_id, hydro["processed_at"])

    events = store.list_rainfall_events(field_id)
    rain_ev = next((e for e in events if e["id"] == payload.rainfall_event_id), None)
    if rain_ev is None:
        raise store.NotFound(f"rainfall_event:{payload.rainfall_event_id}")

    dem = Dem.open(carpeta / "dem_utm.tif")
    mascara = field_mask(field["geometry"], field["utm_epsg"], dem.transform, dem.z.shape)

    if payload.custom_cn_ii is not None:
        cn_ii = float(payload.custom_cn_ii)
        notes = [f"CN_II base ingresado manualmente por el usuario: {cn_ii:.1f}."]
    else:
        cn_ii, notes = lookup_cn_ii(
            cover_code=payload.cover_code,
            soil_group=payload.soil_group,
            cover_percent=payload.cover_percent,
            compaction_high=payload.compaction_high,
        )

    cn_res = compute_nrcs_cn(
        precipitation_mm=rain_ev["total_mm"],
        cn_ii_base=cn_ii,
        antecedent_moisture=payload.antecedent_moisture,
        lambda_ratio=payload.lambda_ratio,
    )

    runoff_load_mm, cumulative_runoff_m3, spatial_summary = distribute_event_runoff_mfd(
        cn_result=cn_res,
        mfd_area_m2=grids["mfd_area_m2"],
        mascara_lote=mascara,
        pixel_size_m=dem.pixel,
        depression_volume_in_field_m3=hydro["summary"]["total_depression_volume_in_field_m3"],
        external_inflow_ha=hydro["summary"]["external_inflow_ha"],
    )

    run_id = store.new_id()
    run_grids_dir = carpeta / "runoff_grids"
    run_grids_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        run_grids_dir / f"{run_id}.npz",
        runoff_load_mm=runoff_load_mm,
        cumulative_runoff_m3=cumulative_runoff_m3,
    )

    cover_label = CN_II_LOOKUP.get(payload.cover_code, {}).get("label", payload.cover_code)
    auto_name = (
        payload.name.strip()
        if payload.name and payload.name.strip()
        else f"{rain_ev['total_mm']:.0f} mm · Suelo {payload.soil_group} · AMC {payload.antecedent_moisture} (CN {cn_res.cn_effective:.0f})"
    )

    warnings = list(rain_ev.get("warnings", [])) + [
        w["message"] for w in terreno["quality"]["warnings"] if w["level"] in ("critico", "advertencia")
    ]
    if cn_res.runoff_q_mm == 0.0:
        warnings.append(
            f"La precipitación del evento ({cn_res.precipitation_mm:.1f} mm) no supera la abstracción inicial "
            f"Ia ({cn_res.initial_abstraction_ia_mm:.1f} mm): la escorrentía directa estimada Q es 0,0 mm."
        )

    run_doc = {
        "id": run_id,
        "field_id": field_id,
        "name": auto_name,
        "rainfall_event_id": rain_ev["id"],
        "rainfall_event_name": rain_ev["name"],
        "model": "event_runoff_nrcs_cn_mfd_v1",
        "processing_version": PROCESSING_VERSION,
        "created_at": store.now_iso(),
        "is_active": True,
        "field_conditions": {
            "soil_group": payload.soil_group,
            "cover_code": payload.cover_code,
            "cover_label": cover_label,
            "cover_percent": payload.cover_percent,
            "compaction_high": payload.compaction_high,
            "antecedent_moisture": payload.antecedent_moisture,
            "lambda_ratio": payload.lambda_ratio,
            "custom_cn_ii": payload.custom_cn_ii,
        },
        "cn_result": cn_res.to_dict(),
        "spatial_summary": spatial_summary,
        "assumptions_and_notes": notes + [
            f"Condición de humedad antecedente: {payload.antecedent_moisture} -> CN efectivo = {cn_res.cn_effective:.1f}.",
            f"Retención potencial máxima S = {cn_res.potential_retention_s_mm:.1f} mm; abstracción inicial Ia = {cn_res.initial_abstraction_ia_mm:.1f} mm (λ = {cn_res.lambda_ratio:.2f}).",
            f"Balance de masa del evento: P ({cn_res.precipitation_mm:.2f} mm) = pérdidas Ia+F ({cn_res.total_retention_losses_mm:.2f} mm) + escorrentía directa Q ({cn_res.runoff_q_mm:.2f} mm).",
        ],
        "warnings": warnings,
        "limitations": LIMITACIONES_FASE2,
    }

    runs = store.list_runoff_runs(field_id)
    for r in runs:
        r["is_active"] = False
    runs.insert(0, run_doc)
    store.save_runoff_runs(field_id, runs)
    load_active_runoff_grids.cache_clear()
    return run_doc


def activate_runoff_run(field_id: str, run_id: str) -> dict:
    runs = store.list_runoff_runs(field_id)
    target = None
    for r in runs:
        if r["id"] == run_id:
            r["is_active"] = True
            target = r
        else:
            r["is_active"] = False
    if target is None:
        raise store.NotFound(f"runoff_run:{run_id}")
    store.save_runoff_runs(field_id, runs)
    load_active_runoff_grids.cache_clear()
    return target


def compare_two_runs(field_id: str, run_a_id: str, run_b_id: str) -> dict:
    runs = store.list_runoff_runs(field_id)
    run_a = next((r for r in runs if r["id"] == run_a_id), None)
    run_b = next((r for r in runs if r["id"] == run_b_id), None)
    if run_a is None or run_b is None:
        raise store.NotFound("No se encontraron ambas corridas para comparar.")
    return compare_runoff_scenarios(run_a, run_b)


@lru_cache(maxsize=8)
def load_active_runoff_grids(field_id: str, run_id: str) -> dict[str, np.ndarray] | None:
    npz_path = store.field_dir(field_id) / "runoff_grids" / f"{run_id}.npz"
    if not npz_path.exists():
        return None
    with np.load(npz_path) as data:
        return {k: data[k] for k in data.files}


def optional_active_runoff(field_id: str) -> tuple[dict, dict[str, np.ndarray]] | None:
    runs = store.list_runoff_runs(field_id)
    if not runs:
        return None
    active = next((r for r in runs if r.get("is_active")), runs[0])
    grids = load_active_runoff_grids(field_id, active["id"])
    if grids is None:
        return None
    return active, grids
