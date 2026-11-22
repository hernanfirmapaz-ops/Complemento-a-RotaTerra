"""Orquestación del análisis topográfico e hidrología estática de Fase 1 (SDD §6.2–6.3 y §14 Fase 1)."""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import rasterio

from geoprocessing import PROCESSING_VERSION
from geoprocessing.agronomy.erosion_usle import (
    compute_usle_erosion_and_gullies,
    design_and_simulate_contour_terraces,
)
from geoprocessing.agronomy.seeding_and_rotation import (
    calculate_seeding_and_fertilizer,
    compare_triennial_rotations,
)
from geoprocessing.agronomy.zonation import ZONE_CATALOG, classify_hydro_agronomic_zones
from geoprocessing.dem.quality import field_mask
from geoprocessing.dem.terrain import Dem, contours_geojson, slope_aspect
from geoprocessing.hydrology.conditioning import condition_dem, is_whitebox_available
from geoprocessing.hydrology.confidence import compute_confidence_indicator
from geoprocessing.hydrology.flow import (
    CODE_TO_LABEL,
    d8_direction_and_accumulation,
    default_stream_threshold_ha,
    extract_drainage_network_and_basins,
    mfd_accumulation,
)
from geoprocessing.hydrology.indices import compute_twi_and_spi
from geoprocessing.hydrology.shallow_water_2d import (
    MANNING_N_BY_COVER,
    run_2d_diffusive_wave_simulation,
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
from geoprocessing.rainfall.timeline import (
    extract_3d_flow_particle_paths,
    simulate_temporal_runoff,
)
from geoprocessing.satellite.nasa_power_imerg import (
    compute_monthly_water_balance,
    compute_ndvi_vigor_monitor,
    evaluate_frost_risk_and_sowing_dates,
    evaluate_real_date_waterlogging_risk,
    fetch_nasa_power_daily_series,
)
from services.api.app.core.config import SAMPLE_DIR
from services.api.app.schemas import (
    AgronomicToolkitIn,
    FieldObservationIn,
    Hydrodynamic2DIn,
    HydrologyRunIn,
    RainfallEventManualIn,
    RunoffRunIn,
)
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

    modo_efectivo = params.conditioning_mode
    aviso_modo: str | None = None
    if modo_efectivo == "breach" and not is_whitebox_available():
        modo_efectivo = "fill_small"
        aviso_modo = (
            "WhiteboxTools no está instalado: en lugar de abrir brechas se rellenaron solo las "
            "depresiones chicas ('fill_small'), conservando los bajos reales."
        )

    z_cond, sink_depth_m, dep_id_grid, depressions = condition_dem(
        dem=dem,
        mascara_lote=mascara,
        mode=modo_efectivo,
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
            CONDITIONING_MODE=modo_efectivo,
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

    # Calcular índices topográficos TWI y SPI + Zonificación hidro-agronómica inicial (Fase 5)
    pct_grid, _, _ = slope_aspect(dem.z, dem.pixel, dem.pixel)
    twi_grid, spi_grid = compute_twi_and_spi(mfd_area_m2, pct_grid, dem.pixel)
    agro_zone_grid, agro_zonation = classify_hydro_agronomic_zones(
        z=dem.z,
        slope_pct=pct_grid,
        sink_depth_m=sink_depth_m,
        twi=twi_grid,
        spi=spi_grid,
        mascara_lote=mascara,
        pixel_size_m=dem.pixel,
    )

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
        twi=twi_grid,
        spi=spi_grid,
        agronomic_zone_id=agro_zone_grid,
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

    pendiente_pct, _, _ = slope_aspect(dem.z, dem.pixel, dem.pixel)
    pendiente_lote = pendiente_pct[mascara & np.isfinite(pendiente_pct)]
    mean_slope_in_field_pct = round(float(pendiente_lote.mean()), 3) if pendiente_lote.size else None

    summary = {
        "mean_slope_in_field_pct": mean_slope_in_field_pct,
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
    if aviso_modo:
        avisos.append(aviso_modo)
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
        "agronomic_zonation": agro_zonation,
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
    twi_v = float(grids["twi"][row, col]) if "twi" in grids else np.nan
    spi_v = float(grids["spi"][row, col]) if "spi" in grids else np.nan
    zone_id = int(grids["agronomic_zone_id"][row, col]) if "agronomic_zone_id" in grids else 0
    loss_v = float(grids["soil_loss_t_ha"][row, col]) if "soil_loss_t_ha" in grids else np.nan
    ndvi_v = float(grids["ndvi"][row, col]) if "ndvi" in grids else np.nan
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
        "twi": round(twi_v, 2) if np.isfinite(twi_v) else None,
        "spi": round(spi_v, 3) if np.isfinite(spi_v) else None,
        "agronomic_zone_id": zone_id if zone_id > 0 else None,
        "agronomic_zone_label": ZONE_CATALOG[zone_id]["label"] if zone_id in ZONE_CATALOG else None,
        "soil_loss_t_ha": round(loss_v, 3) if np.isfinite(loss_v) else None,
        "ndvi": round(ndvi_v, 3) if np.isfinite(ndvi_v) else None,
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

    # Indicador de confianza hidrológica (SDD-003 §3)
    terreno_src = terreno.get("source") or {}
    dem_source_id = terreno_src.get("source_id", "copernicus_glo30")
    dem_res_m = float(terreno_src.get("nominal_resolution_m", 30.0))
    # Pendiente media real del lote (antes se leía de una clave inexistente y quedaba siempre en 1,0 %)
    pct_run, _, _ = slope_aspect(dem.z, dem.pixel, dem.pixel)
    pendiente_guardada = hydro.get("summary", {}).get("mean_slope_in_field_pct")
    if pendiente_guardada is None:
        pct_run_lote = pct_run[mascara & np.isfinite(pct_run)]
        pendiente_guardada = float(pct_run_lote.mean()) if pct_run_lote.size else None
    mean_slope_val = float(pendiente_guardada) if pendiente_guardada is not None else 1.0
    rain_type = rain_ev.get("source_type", "regional_design")
    confidence_obj = compute_confidence_indicator(
        source_id=dem_source_id,
        resolution_m=dem_res_m,
        mean_slope_pct=mean_slope_val,
        soil_source=payload.soil_source or "default",
        rain_source_type=rain_type,
    )

    # Textura del suelo si está disponible (SoilGrids 2.0 ya consultado) para cálculo de K por Wischmeier
    sand_p, silt_p, clay_p = None, None, None
    try:
        ruta_suelo = store.field_dir(field_id) / "soil.json"
        if ruta_suelo.exists():
            s_info = json.loads(ruta_suelo.read_text(encoding="utf-8"))
            if s_info and s_info.get("quality") != "descartada":
                sand_p = s_info.get("sand_pct")
                silt_p = s_info.get("silt_pct")
                clay_p = s_info.get("clay_pct")
    except Exception:
        pass

    # Erosión hídrica USLE real para el evento y condiciones del lote
    spi_grid = grids.get("spi")
    if spi_grid is None:
        _, spi_grid = compute_twi_and_spi(dem.z, pct_run, grids["mfd_area_m2"], mascara, dem.pixel)
    _, erosion_summary = compute_usle_erosion_and_gullies(
        mfd_area_m2=grids["mfd_area_m2"],
        slope_pct=pct_run,
        spi=spi_grid,
        mascara_lote=mascara,
        pixel_size_m=dem.pixel,
        precipitation_mm=rain_ev["total_mm"],
        runoff_q_mm=cn_res.runoff_q_mm,
        soil_group=payload.soil_group,
        cover_code=payload.cover_code,
        sand_pct=sand_p,
        silt_pct=silt_p,
        clay_pct=clay_p,
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
        "erosion_summary": erosion_summary,
        "ls_mean_in_field": erosion_summary.get("ls_mean_in_field"),
        "confidence": confidence_obj,
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


def execute_standard_scenarios(
    field_id: str,
    soil_group: str = "B",
    cover_code: str = "soja_maiz_sd_buena",
    soil_source: str | None = None,
) -> list[dict]:
    """Ejecuta los 3 escenarios estándar de diseño (Conservador, Medio, Crítico)
    para el lote según Tarea 2.2 / SDD-003.
    """
    store.load_field(field_id)
    presets = [
        {"name": "Conservador (30 mm) · Lluvia suave", "mm": 30.0, "amc": "dry"},
        {"name": "Medio (80 mm) · Tormenta de diseño", "mm": 80.0, "amc": "medium"},
        {"name": "Crítico (130 mm) · Crecida extraordinaria", "mm": 130.0, "amc": "wet"},
    ]
    results = []
    for p in presets:
        ev = create_manual_rainfall_event(
            field_id,
            RainfallEventManualIn(
                name=p["name"],
                total_mm=p["mm"],
                source_type="manual",
            ),
        )
        run = execute_runoff_run(
            field_id,
            RunoffRunIn(
                name=p["name"],
                rainfall_event_id=ev["id"],
                soil_group=soil_group,
                cover_code=cover_code,
                antecedent_moisture=p["amc"],
                soil_source=soil_source,
            ),
        )
        results.append(run)
    # Dejar activo por omisión el escenario de diseño central (Medio 80 mm)
    if len(results) >= 2:
        activate_runoff_run(field_id, results[1]["id"])
        results[1]["is_active"] = True
        results[2]["is_active"] = False
    return results


def execute_hydrodynamic_2d_on_run(
    field_id: str,
    run_id: str,
    params: Hydrodynamic2DIn,
) -> dict:
    """Fase 4 + Fase 5: ejecuta el solver 2D de onda difusiva con ley de Manning sobre un escenario
    de escorrentía y actualiza la zonificación hidro-agronómica de RotaTerra.
    """
    field = store.load_field(field_id)
    carpeta = store.field_dir(field_id)
    runs = store.list_runoff_runs(field_id)
    target = next((r for r in runs if r["id"] == run_id), None)
    if target is None:
        raise store.NotFound(f"runoff_run:{run_id}")

    events = store.list_rainfall_events(field_id)
    rain_ev = next((e for e in events if e["id"] == target["rainfall_event_id"]), None)
    if rain_ev is None:
        raise store.NotFound(f"rainfall_event:{target['rainfall_event_id']}")

    hydro = store.load_hydrology(field_id)
    grids = load_hydrology_grids(field_id, hydro["processed_at"])
    dem = Dem.open(carpeta / "dem_utm.tif")
    mascara = field_mask(field["geometry"], field["utm_epsg"], dem.transform, dem.z.shape)

    # Si el evento tiene serie temporal CSV se usan sus intervalos reales; si es acumulado manual
    # se divide en 4 pasos uniformes de 15 min declarando explícitamente el supuesto para el solver 2D
    if rain_ev.get("has_time_series") and rain_ev.get("intervals"):
        intervals = rain_ev["intervals"]
    else:
        q_step = float(rain_ev["total_mm"]) / 4.0
        intervals = [
            {"timestamp": f"Paso {i + 1}", "precipitation_mm": q_step, "interval_minutes": 15}
            for i in range(4)
        ]
        uniform_warn = "El evento de lluvia es manual sin hietograma detallado: la lluvia se aplica de forma uniforme en 4 pasos."
        target.setdefault("warnings", [])
        if uniform_warn not in target["warnings"]:
            target["warnings"].append(uniform_warn)

    cover_code = target["field_conditions"].get("cover_code", "soja_maiz_sd_buena")
    manning_n = (
        float(params.manning_n)
        if params.manning_n is not None
        else MANNING_N_BY_COVER.get(cover_code, 0.10)
    )
    observations = store.list_observations(field_id)

    sim2d = run_2d_diffusive_wave_simulation(
        dem=dem,
        z_cond=grids["z_cond"],
        mascara_lote=mascara,
        intervals=intervals,
        cn_ii_base=target["cn_result"]["cn_ii_base"],
        antecedent_moisture=target["field_conditions"]["antecedent_moisture"],
        lambda_ratio=target["field_conditions"]["lambda_ratio"],
        manning_n=manning_n,
        ponding_threshold_m=params.ponding_threshold_m,
        observations=observations,
        recession_minutes=params.recession_minutes,
    )

    pct_grid, _, _ = slope_aspect(dem.z, dem.pixel, dem.pixel)
    twi_grid = grids["twi"] if "twi" in grids else compute_twi_and_spi(grids["mfd_area_m2"], pct_grid, dem.pixel)[0]
    spi_grid = grids["spi"] if "spi" in grids else compute_twi_and_spi(grids["mfd_area_m2"], pct_grid, dem.pixel)[1]

    agro_zone_grid, agro_zonation = classify_hydro_agronomic_zones(
        z=dem.z,
        slope_pct=pct_grid,
        sink_depth_m=grids["sink_depth_m"],
        twi=twi_grid,
        spi=spi_grid,
        mascara_lote=mascara,
        pixel_size_m=dem.pixel,
        max_water_depth_m=sim2d["max_water_depth_m"],
        ponding_threshold_m=params.ponding_threshold_m,
        soil_group=target["field_conditions"].get("soil_group", "B"),
    )

    # Guardar water_depth_m y velocity_m_s en el archivo .npz de la corrida
    run_npz = carpeta / "runoff_grids" / f"{run_id}.npz"
    existing_arrays = {}
    if run_npz.exists():
        with np.load(run_npz) as data:
            existing_arrays = {k: data[k] for k in data.files}
    existing_arrays["water_depth_m"] = sim2d["max_water_depth_m"]
    existing_arrays["final_water_depth_m"] = sim2d["final_water_depth_m"]
    existing_arrays["velocity_m_s"] = sim2d["max_velocity_m_s"]
    existing_arrays["agronomic_zone_id"] = agro_zone_grid
    np.savez_compressed(run_npz, **existing_arrays)

    for r in runs:
        r["is_active"] = (r["id"] == run_id)
    target["hydrodynamic_2d_summary"] = sim2d["summary"]
    target["agronomic_zonation"] = agro_zonation
    store.save_runoff_runs(field_id, runs)
    load_active_runoff_grids.cache_clear()
    return target


def run_agronomic_toolkit(field_id: str, params: AgronomicToolkitIn) -> dict:
    """Ejecuta el paquete de las 8 herramientas complementarias sobre el lote:
    1. Erosión en escurrimiento (USLE + cárcavas)
    2. Balance hídrico mensual del lote (NASA POWER + Agua útil)
    3. Riesgo de anegamiento por fecha con lluvia real
    4. Curvas de nivel y Terrazas (trazado y simulación de freno de agua/erosión)
    5. Calculadora de Siembra y Fertilizante (Tablas INTA)
    6. Comparador de Rotaciones Trienales (3 años lado a lado)
    7. Monitor de Vigor (NDVI Sentinel-2 STAC COG / correlación topográfica)
    8. Riesgo de Heladas y Fechas Seguras de Siembra (NASA POWER T2M_MIN)
    """
    import json

    field = store.load_field(field_id)
    store.load_terrain(field_id)
    carpeta = store.field_dir(field_id)

    if not (carpeta / "hydrology.json").exists() or not (carpeta / "hydrology_grids.npz").exists():
        run_static_hydrology(field_id, HydrologyRunIn())

    hydro = store.load_hydrology(field_id)
    grids = dict(load_hydrology_grids(field_id, hydro["processed_at"]))
    dem = Dem.open(carpeta / "dem_utm.tif")
    mascara = field_mask(field["geometry"], field["utm_epsg"], dem.transform, dem.z.shape)
    pct_grid, _, _ = slope_aspect(dem.z, dem.pixel, dem.pixel)
    twi_grid = grids["twi"] if "twi" in grids else compute_twi_and_spi(grids["mfd_area_m2"], pct_grid, dem.pixel)[0]
    spi_grid = grids["spi"] if "spi" in grids else compute_twi_and_spi(grids["mfd_area_m2"], pct_grid, dem.pixel)[1]
    zone_grid = grids.get("agronomic_zone_id")
    if zone_grid is None:
        zone_grid, _ = classify_hydro_agronomic_zones(
            dem.z, pct_grid, grids["sink_depth_m"], twi_grid, spi_grid, mascara, dem.pixel
        )

    cn_ii, _ = lookup_cn_ii(params.cover_code, params.soil_group)
    cn_storm = compute_nrcs_cn(params.storm_precipitation_mm, cn_ii, "medium", 0.2)

    sand_p, silt_p, clay_p = None, None, None
    try:
        ruta_suelo = store.field_dir(field_id) / "soil.json"
        if ruta_suelo.exists():
            s_info = json.loads(ruta_suelo.read_text(encoding="utf-8"))
            if s_info and s_info.get("quality") != "descartada":
                sand_p = s_info.get("sand_pct")
                silt_p = s_info.get("silt_pct")
                clay_p = s_info.get("clay_pct")
    except Exception:
        pass

    # 1. Erosión USLE en escurrimiento y focos de cárcavas
    soil_loss_grid, erosion_summary = compute_usle_erosion_and_gullies(
        mfd_area_m2=grids["mfd_area_m2"],
        slope_pct=pct_grid,
        spi=spi_grid,
        mascara_lote=mascara,
        pixel_size_m=dem.pixel,
        precipitation_mm=params.storm_precipitation_mm,
        runoff_q_mm=cn_storm.runoff_q_mm,
        soil_group=params.soil_group,
        cover_code=params.cover_code,
        sand_pct=sand_p,
        silt_pct=silt_p,
        clay_pct=clay_p,
    )

    # 4. Curvas de nivel y Terrazas (simulación antes vs. después)
    terraces_sim = design_and_simulate_contour_terraces(
        dem=dem,
        mascara_lote=mascara,
        mfd_area_m2=grids["mfd_area_m2"],
        slope_pct=pct_grid,
        spi=spi_grid,
        precipitation_mm=params.storm_precipitation_mm,
        runoff_q_mm=cn_storm.runoff_q_mm,
        soil_group=params.soil_group,
        cover_code=params.cover_code,
        sand_pct=sand_p,
        silt_pct=silt_p,
        clay_pct=clay_p,
    )

    # 5. Calculadora de Siembra y Fertilizante (Tablas INTA)
    seeding_calc = calculate_seeding_and_fertilizer(
        crop_code=params.crop_code,
        field_area_ha=field["area_ha"],
        soil_group=params.soil_group,
        environment_zone=params.environment_zone,
        target_yield_t_ha=params.target_yield_t_ha,
    )

    # 6. Comparador de Rotaciones Trienales (Secuencia A vs. Secuencia B)
    rotation_comp = compare_triennial_rotations(
        sequence_a_name=params.sequence_a_name,
        sequence_a_crops=params.sequence_a_crops,
        sequence_b_name=params.sequence_b_name,
        sequence_b_crops=params.sequence_b_crops,
        soil_group=params.soil_group,
        design_storm_mm=params.storm_precipitation_mm,
        mfd_area_m2=grids["mfd_area_m2"],
        slope_pct=pct_grid,
        spi=spi_grid,
        mascara_lote=mascara,
        pixel_size_m=dem.pixel,
        sand_pct=sand_p,
        silt_pct=silt_p,
        clay_pct=clay_p,
    )

    # 2, 3 y 8. Clima diario NASA POWER -> Balance hídrico mensual, Riesgo de anegamiento real y Heladas
    lon_c, lat_c = field["centroid"]
    daily_series, climate_source, climate_warnings = fetch_nasa_power_daily_series(lon_c, lat_c, years=3)

    water_balance = compute_monthly_water_balance(
        daily_rows=daily_series,
        source_label=climate_source,
        soil_group=params.soil_group,
        cover_code=params.cover_code,
    )

    low_zone_cells = int((mascara & (zone_grid == 4)).sum())
    low_zone_ha = (low_zone_cells * (dem.pixel ** 2)) / 10_000.0
    real_waterlogging = evaluate_real_date_waterlogging_risk(
        daily_rows=daily_series,
        source_label=climate_source,
        soil_group=params.soil_group,
        cover_code=params.cover_code,
        field_area_ha=field["area_ha"],
        low_zone_area_ha=float(low_zone_ha),
        depression_volume_m3=hydro["summary"]["total_depression_volume_in_field_m3"],
    )

    frost_risk = evaluate_frost_risk_and_sowing_dates(
        daily_rows=daily_series,
        source_label=climate_source,
    )

    # 7. Monitor de Vigor (NDVI Sentinel-2 L2A STAC COG / correlación topográfica)
    ndvi_res = compute_ndvi_vigor_monitor(
        dem=dem,
        mascara_lote=mascara,
        twi=twi_grid,
        agronomic_zone_id=zone_grid,
        bbox_4326=tuple(field["bbox"]),
    )

    # Guardar grillas soil_loss_t_ha y ndvi dentro de hydrology_grids.npz para visualización 3D
    # Nota API-01: hydrology.json permanece inalterado por el toolkit; no reescribir hydrology.json.
    grids["soil_loss_t_ha"] = soil_loss_grid
    if ndvi_res["grid"] is not None:
        grids["ndvi"] = ndvi_res["grid"]
    elif "ndvi" in grids:
        del grids["ndvi"]
    np.savez_compressed(carpeta / "hydrology_grids.npz", **grids)
    load_hydrology_grids.cache_clear()

    all_warnings = list(climate_warnings)
    if not daily_series:
        all_warnings.append("NASA POWER no disponible: balance hídrico y riesgo climático en modo degradado.")
    if ndvi_res["summary"].get("status") == "unavailable":
        all_warnings.append("Sentinel-2 STAC no disponible o nubosidad excesiva: monitor de vigor en modo degradado.")

    toolkit_doc = {
        "field_id": field_id,
        "processed_at": hydro["processed_at"],
        "parameters": params.model_dump(),
        "erosion_usle": erosion_summary,
        "water_balance_monthly": water_balance,
        "real_waterlogging_by_date": real_waterlogging,
        "contour_terraces": terraces_sim,
        "seeding_calculator_inta": seeding_calc,
        "rotation_comparator_3yr": rotation_comp,
        "ndvi_vigor_monitor": ndvi_res["summary"],
        "frost_risk_sowing": frost_risk,
        "warnings": all_warnings,
    }
    (carpeta / "toolkit.json").write_text(
        json.dumps(toolkit_doc, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return toolkit_doc


def load_agronomic_toolkit(field_id: str) -> dict:
    import json

    ruta = store.field_dir(field_id) / "toolkit.json"
    if not ruta.exists():
        raise store.NotFound(f"toolkit:{field_id}")
    return json.loads(ruta.read_text(encoding="utf-8"))


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


LIMITACIONES_FASE3 = [
    "Fase 3 (Animación temporal simplificada por intervalos): particiona el hietograma mediante NRCS-CN "
    "incremental y un reservorio de tránsito superficial con balance de masa exacto por intervalo.",
    "Las partículas 3D representan trayectorias topográficas y volumen en tránsito por intervalo; "
    "NO representan velocidad hidrodinámica local en m/s ni altura de inundación 2D (Saint-Venant).",
]

OBSERVATION_LABELS: dict[str, str] = {
    "ponding": "Bajo / Anegamiento observado",
    "erosion": "Cárcava / Surco de erosión",
    "culvert": "Alcantarilla / Obra de paso",
    "channel": "Canal / Cuneta de drenaje",
    "terrace": "Terraza / Bordo de contención",
    "water_depth": "Marca / Medición de nivel de agua",
}


def get_runoff_timeline(field_id: str, run_id: str) -> dict:
    field = store.load_field(field_id)
    carpeta = store.field_dir(field_id)
    runs = store.list_runoff_runs(field_id)
    run_doc = next((r for r in runs if r["id"] == run_id), None)
    if run_doc is None:
        raise store.NotFound(f"runoff_run:{run_id}")

    events = store.list_rainfall_events(field_id)
    rain_ev = next((e for e in events if e["id"] == run_doc["rainfall_event_id"]), None)
    if rain_ev is None:
        raise store.NotFound(f"rainfall_event:{run_doc['rainfall_event_id']}")

    hydro = store.load_hydrology(field_id)
    grids = load_hydrology_grids(field_id, hydro["processed_at"])
    dem = Dem.open(carpeta / "dem_utm.tif")
    mascara = field_mask(field["geometry"], field["utm_epsg"], dem.transform, dem.z.shape)

    particle_paths = extract_3d_flow_particle_paths(
        dem=dem,
        d8_code=grids["d8_code"],
        mfd_area_m2=grids["mfd_area_m2"],
        max_paths=45,
    )

    if not rain_ev.get("has_time_series") or not rain_ev.get("intervals"):
        return {
            "run_id": run_doc["id"],
            "run_name": run_doc["name"],
            "rainfall_event_id": rain_ev["id"],
            "rainfall_event_name": rain_ev["name"],
            "has_time_series": False,
            "interval_minutes": None,
            "total_steps": 0,
            "rainfall_steps": 0,
            "recession_steps": 0,
            "routing_coefficient_k": None,
            "peak_step_index": None,
            "peak_transit_lamina_mm": None,
            "peak_transit_volume_m3": None,
            "max_mass_balance_error_mm": None,
            "frames": [],
            "particle_paths": particle_paths,
            "warnings": [
                "El evento de lluvia de este escenario solo tiene precipitación total acumulada (sin hietograma CSV). "
                "Conforme a SDD §4.4, no se inventa una distribución temporal; las partículas muestran únicamente "
                "las trayectorias potenciales de drenaje topográfico."
            ],
            "limitations": LIMITACIONES_FASE3,
        }

    from geoprocessing.dem.terrain import slope_aspect

    pct, _, _ = slope_aspect(dem.z, dem.pixel, dem.pixel)
    pct_in_field = pct[mascara & np.isfinite(pct)]
    mean_slope = float(pct_in_field.mean()) if pct_in_field.size else 1.5

    sim = simulate_temporal_runoff(
        intervals=rain_ev["intervals"],
        cn_ii_base=run_doc["cn_result"]["cn_ii_base"],
        antecedent_moisture=run_doc["field_conditions"]["antecedent_moisture"],
        lambda_ratio=run_doc["field_conditions"]["lambda_ratio"],
        mfd_area_m2=grids["mfd_area_m2"],
        mascara_lote=mascara,
        pixel_size_m=dem.pixel,
        mean_slope_pct=mean_slope,
        depression_volume_in_field_m3=hydro["summary"]["total_depression_volume_in_field_m3"],
        external_inflow_ha=hydro["summary"]["external_inflow_ha"],
    )

    return {
        "run_id": run_doc["id"],
        "run_name": run_doc["name"],
        "rainfall_event_id": rain_ev["id"],
        "rainfall_event_name": rain_ev["name"],
        "has_time_series": True,
        "interval_minutes": sim["interval_minutes"],
        "total_steps": sim["total_steps"],
        "rainfall_steps": sim["rainfall_steps"],
        "recession_steps": sim["recession_steps"],
        "routing_coefficient_k": sim["routing_coefficient_k"],
        "peak_step_index": sim["peak_step_index"],
        "peak_transit_lamina_mm": sim["peak_transit_lamina_mm"],
        "peak_transit_volume_m3": sim["peak_transit_volume_m3"],
        "max_mass_balance_error_mm": sim["max_mass_balance_error_mm"],
        "frames": sim["frames"],
        "particle_paths": particle_paths,
        "warnings": list(rain_ev.get("warnings", [])),
        "limitations": LIMITACIONES_FASE3,
    }


def create_field_observation(field_id: str, payload: FieldObservationIn) -> dict:
    store.load_field(field_id)
    carpeta = store.field_dir(field_id)
    elev_m = None
    if (carpeta / "dem_utm.tif").exists():
        from geoprocessing.dem.terrain import point_info

        dem = Dem.open(carpeta / "dem_utm.tif")
        pt = point_info(dem, payload.lon, payload.lat)
        elev_m = pt["elevation_m"]

    now = store.now_iso()
    item = {
        "id": store.new_id(),
        "field_id": field_id,
        "observation_type": payload.observation_type,
        "label": OBSERVATION_LABELS.get(payload.observation_type, payload.observation_type),
        "lon": round(float(payload.lon), 7),
        "lat": round(float(payload.lat), 7),
        "elevation_m": elev_m,
        "notes": payload.notes.strip(),
        "value": payload.value,
        "units": payload.units.strip() if payload.units else None,
        "observed_at": payload.observed_at or now,
        "created_at": now,
    }
    items = store.list_observations(field_id)
    items.insert(0, item)
    store.save_observations(field_id, items)
    return item


def delete_field_observation(field_id: str, obs_id: str) -> None:
    store.load_field(field_id)
    items = store.list_observations(field_id)
    filtered = [it for it in items if it["id"] != obs_id]
    if len(filtered) == len(items):
        raise store.NotFound(f"observation:{obs_id}")
    store.save_observations(field_id, filtered)


def export_analysis_geojson(field_id: str) -> dict:
    """Empaqueta límite del lote, red de drenaje, curvas de nivel, salidas, depresiones y observaciones."""
    field = store.load_field(field_id)
    carpeta = store.field_dir(field_id)
    terreno = store.load_terrain(field_id) if (carpeta / "terrain.json").exists() else None
    hydro = store.load_hydrology(field_id) if (carpeta / "hydrology.json").exists() else None
    runs = store.list_runoff_runs(field_id)
    active_run = next((r for r in runs if r.get("is_active")), runs[0] if runs else None)
    observations = store.list_observations(field_id)

    features: list[dict] = [
        {
            "type": "Feature",
            "properties": {
                "layer": "field_boundary",
                "name": field["name"],
                "area_ha": field["area_ha"],
                "utm_epsg": field["utm_epsg"],
            },
            "geometry": field["geometry"],
        }
    ]

    if hydro:
        for feat in hydro["drainage_network"].get("features", []):
            features.append({
                "type": "Feature",
                "properties": {"layer": "potential_drainage_network", **feat.get("properties", {})},
                "geometry": feat["geometry"],
            })
        for feat in hydro["contours"].get("features", []):
            features.append({
                "type": "Feature",
                "properties": {"layer": "contour_line", **feat.get("properties", {})},
                "geometry": feat["geometry"],
            })
        for dep in hydro.get("depressions", []):
            if dep.get("in_field"):
                features.append({
                    "type": "Feature",
                    "properties": {"layer": "depression", **dep},
                    "geometry": {"type": "Point", "coordinates": [dep["centroid_lon"], dep["centroid_lat"]]},
                })
        for out in hydro.get("outlets", []):
            features.append({
                "type": "Feature",
                "properties": {"layer": "subbasin_outlet", **out},
                "geometry": {"type": "Point", "coordinates": [out["lon"], out["lat"]]},
            })

    for obs in observations:
        features.append({
            "type": "Feature",
            "properties": {"layer": "field_observation", **obs},
            "geometry": {"type": "Point", "coordinates": [obs["lon"], obs["lat"]]},
        })

    return {
        "type": "FeatureCollection",
        "rotaterra_metadata": {
            "exported_at": store.now_iso(),
            "processing_version": PROCESSING_VERSION,
            "field_id": field["id"],
            "field_name": field["name"],
            "area_ha": field["area_ha"],
            "calculation_crs": f"EPSG:{field['utm_epsg']}",
            "dem_source": terreno["source"] if terreno else None,
            "dem_quality": terreno["quality"] if terreno else None,
            "hydrology_parameters": hydro["parameters"] if hydro else None,
            "active_runoff_scenario": {
                "name": active_run["name"],
                "cn_result": active_run["cn_result"],
                "spatial_summary": active_run["spatial_summary"],
            } if active_run else None,
            "limitations": (terreno.get("limitations", []) if terreno else []) + LIMITACIONES_FASE2 + LIMITACIONES_FASE3,
        },
        "features": features,
    }


def export_technical_report_html(field_id: str) -> str:
    """Genera un informe técnico HTML reproducible con metadatos, calidad del DEM, hidrología y limitaciones."""
    import html

    field = store.load_field(field_id)
    carpeta = store.field_dir(field_id)
    terreno = store.load_terrain(field_id) if (carpeta / "terrain.json").exists() else None
    hydro = store.load_hydrology(field_id) if (carpeta / "hydrology.json").exists() else None
    runs = store.list_runoff_runs(field_id)
    observations = store.list_observations(field_id)

    def esc(v):
        return html.escape(str(v if v is not None else "s/d"))

    runs_rows = "".join(
        f"<tr><td>{esc(r['name'])}</td><td>{esc(r['rainfall_event_name'])}</td>"
        f"<td>{r['cn_result']['precipitation_mm']:.1f} mm</td>"
        f"<td>{r['cn_result']['cn_effective']:.1f}</td>"
        f"<td>{r['cn_result']['initial_abstraction_ia_mm']:.1f} mm</td>"
        f"<td><strong>{r['cn_result']['runoff_q_mm']:.2f} mm</strong></td>"
        f"<td>{r['spatial_summary']['field_runoff_generated_m3']:.0f} m³</td>"
        f"<td>{r['spatial_summary']['net_outflow_potential_m3']:.0f} m³</td></tr>"
        for r in runs
    ) or "<tr><td colspan='8'>Sin escenarios de escorrentía ejecutados.</td></tr>"

    obs_rows = "".join(
        f"<tr><td>{esc(o['label'])}</td><td>{o['lat']:.5f}°, {o['lon']:.5f}°</td>"
        f"<td>{esc(o['elevation_m'])} m</td><td>{esc(o['value'])} {esc(o['units'] or '')}</td>"
        f"<td>{esc(o['notes'])}</td></tr>"
        for o in observations
    ) or "<tr><td colspan='5'>Sin observaciones de campo registradas.</td></tr>"

    warnings_items = []
    if terreno:
        warnings_items.extend(w["message"] for w in terreno["quality"]["warnings"])
    if hydro:
        warnings_items.extend(hydro.get("warnings", []))
    warnings_html = "".join(f"<li>{esc(w)}</li>" for w in dict.fromkeys(warnings_items))

    return f"""<!doctype html>
<html lang="es-AR">
<head>
<meta charset="utf-8" />
<title>Informe Técnico Hidrológico — {esc(field['name'])}</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; color: #0f172a; margin: 28px; line-height: 1.45; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 4px; color: #065f46; }}
  h2 {{ font-size: 1.05rem; margin-top: 22px; border-bottom: 2px solid #cbd5e1; padding-bottom: 4px; }}
  .meta {{ font-size: 0.85rem; color: #475569; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 0.84rem; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }}
  th {{ background: #f1f5f9; }}
  .warn {{ background: #fffbeb; border-left: 4px solid #f59e0b; padding: 10px 14px; font-size: 0.84rem; margin-top: 12px; }}
</style>
</head>
<body>
  <h1>RotaTerra — Informe Técnico Topográfico e Hidrológico por Lote</h1>
  <div class="meta">
    Lote: <strong>{esc(field['name'])}</strong> · Superficie UTM: <strong>{field['area_ha']:.2f} ha</strong>
    · CRS métrico de cálculo: <strong>EPSG:{field['utm_epsg']}</strong>
    · Versión de motor: <code>{esc(PROCESSING_VERSION)}</code>
    · Generado: {esc(store.now_iso())}
  </div>

  <h2>1. Fuente y Calidad del Modelo Digital de Elevación (MDE)</h2>
  {f'''<table>
    <tr><th>Fuente</th><td>{esc(terreno['source']['source_name'])} ({esc(terreno['source']['surface_type'])})</td>
        <th>Resolución</th><td>{terreno['quality']['pixel_size_m']:.1f} m/píxel ({terreno['quality']['cells_in_field']} celdas en lote)</td></tr>
    <tr><th>Datum vertical</th><td>{esc(terreno['source']['vertical_datum'])}</td>
        <th>Precisión vertical declarada</th><td>±{esc(terreno['source']['vertical_accuracy_m'])} m</td></tr>
    <tr><th>Período de adquisición</th><td>{esc(terreno['source']['acquisition_start'])} a {esc(terreno['source']['acquisition_end'])}</td>
        <th>Rango de cotas en lote</th><td>{esc(terreno['quality']['elevation_field']['min'])} – {esc(terreno['quality']['elevation_field']['max'])} m s.n.m. (Δ {esc(terreno['quality']['elevation_field']['range'])} m)</td></tr>
  </table>''' if terreno else '<p>Sin MDE procesado.</p>'}

  <h2>2. Hidrología Estática (Acondicionamiento, D8, MFD, Depresiones y Cuencas)</h2>
  {f'''<table>
    <tr><th>Modo acondicionamiento</th><td>{esc(hydro['parameters']['conditioning_mode'])}</td>
        <th>Umbral red de drenaje</th><td>{esc(hydro['parameters']['stream_threshold_ha'])} ha ({esc(hydro['parameters']['routing_basis'])})</td></tr>
    <tr><th>Depresiones en lote</th><td>{hydro['summary']['depressions_in_field_count']} ({hydro['summary']['total_depression_area_in_field_ha']:.2f} ha · {hydro['summary']['total_depression_volume_in_field_m3']:.0f} m³)</td>
        <th>Aporte externo al lote</th><td>{hydro['summary']['external_inflow_ha']:.2f} ha</td></tr>
    <tr><th>Área contribuyente máx. MFD</th><td>{hydro['summary']['max_mfd_area_in_field_ha']:.2f} ha</td>
        <th>Error balance masa MFD</th><td>{hydro['summary']['mfd_mass_balance_error']:.6f}</td></tr>
  </table>''' if hydro else '<p>Sin corrida de hidrología estática.</p>'}

  <h2>3. Escenarios de Lluvia y Escorrentía Estimada (NRCS Curve Number + MFD)</h2>
  <table>
    <thead>
      <tr><th>Escenario</th><th>Evento lluvia</th><th>P</th><th>CN ef.</th><th>Ia</th><th>Escorrentía Q</th><th>Vol. generado lote</th><th>Salida neta pot.</th></tr>
    </thead>
    <tbody>{runs_rows}</tbody>
  </table>

  <h2>4. Observaciones Reales de Campo y Estructuras Relevadas (CU-06)</h2>
  <table>
    <thead>
      <tr><th>Tipo</th><th>Coordenadas</th><th>Cota DEM</th><th>Medición</th><th>Notas</th></tr>
    </thead>
    <tbody>{obs_rows}</tbody>
  </table>

  <div class="warn">
    <strong>Advertencias técnicas, supuestos y limitaciones obligatorias (SDD §1.1, §5.2 y §6.4):</strong>
    <ul>
      {warnings_html}
      <li>La escorrentía directa Q (mm) y la carga acumulada MFD no representan profundidad física de inundación ni reemplazan un estudio hidráulico 2D calibrado con mediciones locales.</li>
    </ul>
  </div>
</body>
</html>"""


def get_field_daily_rainfall(field_id: str, target_date: str | None = None) -> dict:
    """Obtiene el contexto climático diario estimado (NASA POWER ~55 km) para el lote,
    informando la estación SMN más cercana únicamente como referencia geográfica.
    """
    from geoprocessing.rainfall.daily_national import get_field_daily_rainfall_context

    field = store.load_field(field_id)
    lon, lat = field["centroid"]
    return get_field_daily_rainfall_context(lon, lat, target_date=target_date)


def simulate_field_daily_rainfall(
    field_id: str,
    date_str: str,
    soil_group: str = "B",
    cover_code: str = "soja_maiz_sd_buena",
    cover_percent: float | None = 60.0,
    compaction_high: bool = False,
    soil_source: str | None = None,
) -> dict:
    """Simula la escorrentía y respuesta hidrológica para la lluvia diaria estimada (NASA POWER ~55 km),
    con humedad antecedente regional y estación SMN como referencia geográfica.
    """
    from geoprocessing.rainfall.daily_national import get_field_daily_rainfall_context

    field = store.load_field(field_id)
    lon, lat = field["centroid"]
    ctx = get_field_daily_rainfall_context(lon, lat, target_date=date_str)

    if not ctx.get("selected_day"):
        raise ValueError(
            f"No se encontraron registros de precipitación diaria para la fecha '{date_str}'."
        )

    day = ctx["selected_day"]
    smn = ctx["nearest_smn_station"]
    p_mm = float(day["precipitation_mm"])

    now = store.now_iso()
    event_name = (
        f"Día {day['date']} · {p_mm:.1f} mm (NASA POWER · Ref. SMN {smn['name']} a {smn['distance_km']} km)"
    )

    meta, warnings = build_event_metadata(
        source_type="NASA_POWER",
        total_mm=max(0.1, p_mm),
        start_at=f"{day['date']}T00:00:00Z",
        end_at=f"{day['date']}T23:59:59Z",
        has_time_series=False,
        interval_minutes=None,
        custom_source_product="NASA POWER (MERRA-2 / GPCP · ~55 km)",
        custom_spatial_resolution="0,5° (~55 km)",
        quality_flag="modelo_reanalisis_regional",
        custom_uncertainty_note=(
            f"Lluvia regional estimada (~55 km), no es la medición de su campo. "
            f"Estación SMN más cercana (referencia, sin datos conectados): {smn['name']} ({smn['distance_km']} km). "
            f"Humedad antecedente 5d: {day['prior_5d_rain_mm']:.1f} mm ({day['antecedent_moisture_amc']})."
        ),
    )

    event = {
        "id": store.new_id(),
        "field_id": field_id,
        "name": event_name,
        "total_mm": round(p_mm, 2),
        "source_type": "NASA_POWER",
        "start_at": f"{day['date']}T00:00:00Z",
        "end_at": f"{day['date']}T23:59:59Z",
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

    # Crear y ejecutar la corrida de escorrentía con la humedad antecedente real del día
    runoff_payload = RunoffRunIn(
        name=f"Lluvia diaria {day['date']} ({p_mm:.1f} mm · AMC {day['antecedent_moisture_amc'].upper()})",
        rainfall_event_id=event["id"],
        soil_group=soil_group,
        cover_code=cover_code,
        cover_percent=cover_percent,
        compaction_high=compaction_high,
        antecedent_moisture=day["antecedent_moisture_amc"],
        lambda_ratio=0.2,
        soil_source=soil_source,
    )
    runoff_res = execute_runoff_run(field_id, runoff_payload)

    return {
        "context": ctx,
        "event": event,
        "runoff_run": runoff_res,
    }
