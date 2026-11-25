"""Orquestación del procesamiento topográfico de Fase 0 para un lote."""

from __future__ import annotations

import shutil
from functools import lru_cache
from pathlib import Path

import numpy as np

from geoprocessing import PROCESSING_VERSION, supuestos
from geoprocessing.dem import sources
from geoprocessing.dem.prepare import MAX_CELDAS, prepare_dem
from geoprocessing.dem.quality import QualityWarning, build_quality_report, field_mask
from geoprocessing.dem.terrain import Dem, contours_geojson, field_rings_utm, hillshade, mesh, point_info, profile
from geoprocessing.fields import field_utm_geometry
from geoprocessing.hydrology.catchment import resolve_adaptive_margin_steps, trace_upslope_catchment
from geoprocessing.hydrology.flow import d8_direction_and_accumulation
from services.api.app.services import hydrology, store

LIMITACIONES = [
    "Fase 0: solo análisis topográfico. No se calcula escurrimiento, lluvia, profundidad ni velocidad de agua.",
    "La cota de un punto se interpola bilinealmente entre las 4 celdas vecinas del DEM de trabajo.",
    "La pendiente se calcula con el método de Horn sobre la grilla UTM; las celdas de borde o vecinas "
    "de un vacío no tienen pendiente.",
    "La malla 3D puede estar submuestreada para el navegador; los valores consultados usan la resolución completa.",
    "El DEM de trabajo se reproyectó a UTM con interpolación bilineal sin refinar la resolución del original.",
]


def _buffer_bbox_4326(field: dict, buffer_m: float) -> tuple[float, float, float, float]:
    """Caja lon/lat del lote más la zona de aporte, con margen extra para la reproyección."""
    from rasterio.warp import transform_bounds

    g = field_utm_geometry(field["geometry"], field["utm_epsg"])
    caja = g.buffer(buffer_m + 100).bounds
    return transform_bounds(f"EPSG:{field['utm_epsg']}", "EPSG:4326", *caja, densify_pts=21)


SAMPLE_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "lotes"


def _find_sample_dem_backup(field: dict) -> tuple[Path, dict] | None:
    """Busca el recorte real de relieve en data/sample/ para los lotes de ejemplo cuando no hay red."""
    import json
    source_file = field.get("source_file", "")
    name = field.get("name", "")
    if "san_luis_parcela_205" in source_file or "205" in name:
        dem_p = SAMPLE_DIR / "san_luis_parcela_205_dem.tif"
        json_p = SAMPLE_DIR / "san_luis_parcela_205_dem.json"
        if dem_p.exists() and json_p.exists():
            return dem_p, json.loads(json_p.read_text(encoding="utf-8"))
    if "san_luis_piedemonte_492" in source_file or "492" in name or "Piedemonte" in name:
        dem_p = SAMPLE_DIR / "san_luis_piedemonte_492_dem.tif"
        json_p = SAMPLE_DIR / "san_luis_piedemonte_492_dem.json"
        if dem_p.exists() and json_p.exists():
            return dem_p, json.loads(json_p.read_text(encoding="utf-8"))
    return None


def process_terrain(field_id: str, source_id: str, buffer_m: float = 3000.0, upload_path: Path | None = None,
                    upload_meta: dict | None = None, adaptive_catchment: bool = True) -> dict:
    from datetime import date

    field = store.load_field(field_id)
    carpeta = store.field_dir(field_id)
    carpeta_fuente = carpeta / "source"
    if carpeta_fuente.exists():
        shutil.rmtree(carpeta_fuente)
    carpeta_fuente.mkdir(parents=True)

    # Determinar secuencia de pasos de margen adaptativo (Spec 032 §2 / Issue #114)
    if adaptive_catchment:
        margin_steps = resolve_adaptive_margin_steps()
    else:
        margin_steps = [float(buffer_m)]

    fetch_buffer = max(margin_steps[-1], 10000.0) if source_id in (
        sources.COPERNICUS_ID, sources.OPENTOPOGRAPHY_COP30_ID, sources.OPENTOPOGRAPHY_NASADEM_ID
    ) else margin_steps[-1]

    if source_id == sources.COPERNICUS_ID:
        original = carpeta_fuente / "copernicus_glo30_window.tif"
        try:
            info = sources.fetch_copernicus(_buffer_bbox_4326(field, fetch_buffer), original)
        except sources.DemSourceError:
            sample_backup = _find_sample_dem_backup(field)
            if sample_backup:
                dem_path, meta = sample_backup
                shutil.copy(str(dem_path), str(original))
                toma = (
                    date.fromisoformat(meta["acquisition_start"]),
                    date.fromisoformat(meta["acquisition_end"]),
                ) if meta.get("acquisition_start") and meta.get("acquisition_end") else None
                info = sources.copernicus_info(toma)
                info.source_name = meta.get("source_name", info.source_name)
            else:
                raise
    elif source_id == sources.OPENTOPOGRAPHY_COP30_ID:
        original = carpeta_fuente / "opentopography_cop30.tif"
        info = sources.fetch_opentopography(_buffer_bbox_4326(field, fetch_buffer), original, demtype="COP30")
    elif source_id == sources.OPENTOPOGRAPHY_NASADEM_ID:
        original = carpeta_fuente / "opentopography_nasadem.tif"
        info = sources.fetch_opentopography(_buffer_bbox_4326(field, fetch_buffer), original, demtype="NASADEM")
    elif source_id == sources.UPLOAD_ID:
        if upload_path is None:
            raise sources.DemSourceError("Falta el archivo GeoTIFF del DEM.")
        original = carpeta_fuente / upload_path.name
        shutil.move(str(upload_path), original)
        sources.inspect_upload(original)
        info = None  # se completa después de conocer la resolución
    else:
        raise sources.DemSourceError(f"Fuente de DEM desconocida: {source_id}")

    # Evaluación y recorte adaptativo (3 km -> 5 km -> 10 km)
    preparado = None
    dem = None
    mascara = None
    catchment_res = None
    chosen_margin = margin_steps[0]

    for step_m in margin_steps:
        try:
            prep_cand = prepare_dem(
                original,
                field["geometry"],
                field["utm_epsg"],
                step_m,
                carpeta / "dem_utm.tif",
            )
            dem_cand = Dem.open(prep_cand.path)
            masc_cand = field_mask(field["geometry"], field["utm_epsg"], dem_cand.transform, dem_cand.z.shape)

            if not np.isfinite(dem_cand.z[masc_cand]).any():
                break

            d8_code_cand, _, _, _ = d8_direction_and_accumulation(dem_cand.z, dem_cand.pixel)
            c_res = trace_upslope_catchment(
                d8_code=d8_code_cand,
                mascara_lote=masc_cand,
                pixel_size_m=dem_cand.pixel,
                current_margin_km=round(step_m / 1000.0, 1),
                max_margin_km=round(margin_steps[-1] / 1000.0, 1),
            )
            preparado = prep_cand
            dem = dem_cand
            mascara = masc_cand
            catchment_res = c_res
            chosen_margin = step_m

            # Si la cuenca aguas arriba no toca el límite exterior del ráster, queda delimitada
            if not c_res.touches_border:
                break
        except Exception:
            if preparado is not None:
                break
            raise

    if preparado is None or dem is None or mascara is None:
        # Fallback al primer paso directo
        preparado = prepare_dem(original, field["geometry"], field["utm_epsg"], chosen_margin, carpeta / "dem_utm.tif")
        dem = Dem.open(preparado.path)
        mascara = field_mask(field["geometry"], field["utm_epsg"], dem.transform, dem.z.shape)
        d8_code_cand, _, _, _ = d8_direction_and_accumulation(dem.z, dem.pixel)
        catchment_res = trace_upslope_catchment(
            d8_code=d8_code_cand,
            mascara_lote=mascara,
            pixel_size_m=dem.pixel,
            current_margin_km=round(chosen_margin / 1000.0, 1),
            max_margin_km=round(margin_steps[-1] / 1000.0, 1),
        )

    if info is None:
        info = sources.upload_info(upload_meta or {}, round(max(preparado.source_pixel_size_m), 2))

    calidad = build_quality_report(dem.z, dem.transform, dem.crs, mascara, field["area_ha"], info,
                                   preparado.source_pixel_size_m, chosen_margin)

    # Declarar remuestreo fuera del lote si se aplicó para respetar MAX_CELDAS
    if preparado.resampling_outside_field:
        calidad.warnings.append(
            QualityWarning(
                code="remuestreo_fuera_de_lote",
                level="info",
                message=f"Se aplicó remuestreo a {preparado.pixel_size_m:.1f} m fuera del lote para respetar el límite de celdas ({MAX_CELDAS}).",
            )
        )

    # Aviso visible si la cuenca vertiente quedó truncada
    if catchment_res and catchment_res.is_truncated and catchment_res.warning:
        calidad.warnings.append(
            QualityWarning(
                code="cuenca_truncada",
                level="advertencia",
                message=catchment_res.warning,
            )
        )

    terreno = {
        "field_id": field_id,
        "processing_version": PROCESSING_VERSION,
        "processed_at": store.now_iso(),
        "parameters": {
            "source_id": source_id,
            "buffer_m": chosen_margin,
            "resampling": "bilinear",
            "resampling_outside_field": preparado.resampling_outside_field,
            "resampled_resolution_m": preparado.resampled_resolution_m,
            "adaptive_catchment": adaptive_catchment,
            "target_crs": dem.crs,
            "pixel_size_m": preparado.pixel_size_m,
        },
        "source": info.to_dict(),
        "quality": calidad.to_dict(),
        "files": {"original": f"source/{original.name}", "working_dem": "dem_utm.tif"},
        "limitations": LIMITACIONES,
        "catchment": {
            "touches_border": catchment_res.touches_border if catchment_res else False,
            "is_truncated": catchment_res.is_truncated if catchment_res else False,
            "margin_km": catchment_res.margin_km if catchment_res else round(chosen_margin / 1000.0, 1),
            "total_area_ha": catchment_res.total_area_ha if catchment_res else 0.0,
            "external_area_ha": catchment_res.external_area_ha if catchment_res else 0.0,
            "in_field_area_ha": catchment_res.in_field_area_ha if catchment_res else 0.0,
            "warning": catchment_res.warning if catchment_res else None,
        },
    }
    store.save_terrain(field_id, terrain_data := terreno)
    # Invalidar corridas hidrológicas previas si se reprocesó el DEM base
    for fname in ("hydrology.json", "hydrology_grids.npz", "dem_conditioned_utm.tif"):
        p = carpeta / fname
        if p.exists():
            p.unlink()
    _cargar.cache_clear()
    hydrology.load_hydrology_grids.cache_clear()
    return terrain_data


@lru_cache(maxsize=8)
def _cargar(field_id: str, processed_at: str):
    """DEM y máscara del lote en memoria (se invalida al reprocesar)."""
    field = store.load_field(field_id)
    dem = Dem.open(store.field_dir(field_id) / "dem_utm.tif")
    mascara = field_mask(field["geometry"], field["utm_epsg"], dem.transform, dem.z.shape)
    return field, dem, mascara


def _contexto(field_id: str):
    terreno = store.load_terrain(field_id)
    field, dem, mascara = _cargar(field_id, terreno["processed_at"])
    return terreno, field, dem, mascara


def _avisos_basicos(terreno: dict) -> list[str]:
    return [w["message"] for w in terreno["quality"]["warnings"] if w["level"] in ("critico", "advertencia")]


def terrain_mesh(field_id: str, max_size: int) -> dict:
    _, field, dem, mascara = _contexto(field_id)
    anillos = field_rings_utm(field_utm_geometry(field["geometry"], field["utm_epsg"]))
    extra: dict[str, np.ndarray] = {}
    if grids := hydrology.optional_hydrology_grids(field_id):
        extra.update({
            "sink_depth_m": grids["sink_depth_m"],
            "mfd_area_ha": (grids["mfd_area_m2"] / 10_000.0).astype("float32"),
            "d8_area_ha": (grids["d8_area_m2"] / 10_000.0).astype("float32"),
            "d8_code": grids["d8_code"],
            "subbasin_id": grids["subbasin_id"],
        })
        if "twi" in grids:
            extra["twi"] = grids["twi"]
        if "spi" in grids:
            extra["spi"] = grids["spi"]
        if "agronomic_zone_id" in grids:
            extra["agronomic_zone_id"] = grids["agronomic_zone_id"]
        if "soil_loss_t_ha" in grids:
            extra["soil_loss_t_ha"] = grids["soil_loss_t_ha"]
        if "ndvi" in grids and grids["ndvi"] is not None and getattr(grids["ndvi"], "ndim", 0) == 2:
            extra["ndvi"] = grids["ndvi"]
    active_run = hydrology.optional_active_runoff(field_id)
    if active_run:
        run_doc, r_grids = active_run
        extra["runoff_load_mm"] = r_grids["runoff_load_mm"]
        extra["cumulative_runoff_m3"] = r_grids["cumulative_runoff_m3"]
        if "water_depth_m" in r_grids:
            extra["water_depth_m"] = r_grids["water_depth_m"]
        if "velocity_m_s" in r_grids:
            extra["velocity_m_s"] = r_grids["velocity_m_s"]
        if "agronomic_zone_id" in r_grids:
            extra["agronomic_zone_id"] = r_grids["agronomic_zone_id"]
    res = mesh(dem, mascara, anillos, max_size, extra_grids=extra or None)
    if active_run:
        run_doc, _ = active_run
        h2d = run_doc.get("hydrodynamic_2d_summary") or {}
        if "ponding_threshold_m" in h2d and h2d["ponding_threshold_m"] is not None:
            res["ponding_threshold_m"] = float(h2d["ponding_threshold_m"])
        else:
            res["ponding_threshold_m"] = float(supuestos.UMBRAL_ENCHARCAMIENTO_MOTOR_M.valor)
    else:
        res["ponding_threshold_m"] = float(supuestos.UMBRAL_ENCHARCAMIENTO_MOTOR_M.valor)
    return res


def terrain_point(field_id: str, lon: float, lat: float) -> dict:
    terreno, _, dem, mascara = _contexto(field_id)
    info = point_info(dem, lon, lat, mascara)
    avisos = []
    if not info["inside_dem"]:
        avisos.append("El punto está fuera del área procesada (lote + zona de aporte).")
    elif info["elevation_m"] is None:
        avisos.append("Sin dato de elevación en este punto (vacío del DEM o borde).")
    else:
        r, c = info["row"], info["col"]
        alto, ancho = dem.z.shape
        r0, r1, c0, c1 = max(r - 1, 0), min(r + 2, alto), max(c - 1, 0), min(c + 2, ancho)
        hs = hillshade(dem.z[r0:r1, c0:c1], dem.pixel, dem.pixel)[r - r0, c - c0]
        info["hillshade"] = round(float(hs), 3) if np.isfinite(hs) else None
        if grids := hydrology.optional_hydrology_grids(field_id):
            info.update(hydrology.point_hydrology_attrs(grids, r, c))
        if active_run := hydrology.optional_active_runoff(field_id):
            run_doc, r_grids = active_run
            load_v = float(r_grids["runoff_load_mm"][r, c])
            vol_v = float(r_grids["cumulative_runoff_m3"][r, c])
            info["runoff_generated_q_mm"] = run_doc["cn_result"]["runoff_q_mm"]
            info["runoff_load_mm"] = round(load_v, 2) if np.isfinite(load_v) else None
            info["cumulative_runoff_m3"] = round(vol_v, 2) if np.isfinite(vol_v) else None
            if "water_depth_m" in r_grids:
                wd = float(r_grids["water_depth_m"][r, c])
                info["water_depth_m"] = round(wd, 3) if np.isfinite(wd) else None
            if "velocity_m_s" in r_grids:
                vel = float(r_grids["velocity_m_s"][r, c])
                info["velocity_m_s"] = round(vel, 3) if np.isfinite(vel) else None
    return info | {"pixel_size_m": dem.pixel, "crs": dem.crs, "source_name": terreno["source"]["source_name"],
                   "warnings": avisos}


def terrain_contours(field_id: str, interval_m: float | None = None) -> dict:
    _, _, dem, _ = _contexto(field_id)
    return contours_geojson(dem, interval_m=interval_m)


def terrain_profile(field_id: str, coords: list[tuple[float, float]], step_m: float | None) -> dict:
    terreno, _, dem, _ = _contexto(field_id)
    resultado = profile(dem, [list(c) for c in coords], step_m)
    avisos = _avisos_basicos(terreno)
    s = resultado["summary"]
    if s["valid_samples"] < s["samples"]:
        avisos.append(f"{s['samples'] - s['valid_samples']} muestras sin dato (fuera del área o vacíos del DEM).")
    if s["length_m"] < 3 * dem.pixel:
        avisos.append("La línea es más corta que 3 píxeles del DEM: el perfil no es representativo.")
    return resultado | {"pixel_size_m": dem.pixel, "source_name": terreno["source"]["source_name"],
                        "warnings": avisos}


def has_finite(values) -> bool:
    return bool(np.isfinite(np.asarray(values, dtype=float)).any())
