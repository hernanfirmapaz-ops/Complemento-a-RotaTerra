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
from services.api.app.schemas import HydrologyRunIn
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
