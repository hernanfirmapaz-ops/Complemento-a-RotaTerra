"""Orquestación del procesamiento topográfico de Fase 0 para un lote."""

from __future__ import annotations

import shutil
from functools import lru_cache
from pathlib import Path

import numpy as np

from geoprocessing import PROCESSING_VERSION
from geoprocessing.dem import sources
from geoprocessing.dem.prepare import prepare_dem
from geoprocessing.dem.quality import build_quality_report, field_mask
from geoprocessing.dem.terrain import Dem, contours_geojson, field_rings_utm, hillshade, mesh, point_info, profile
from geoprocessing.fields import field_utm_geometry
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


def process_terrain(field_id: str, source_id: str, buffer_m: float, upload_path: Path | None,
                    upload_meta: dict) -> dict:
    field = store.load_field(field_id)
    carpeta = store.field_dir(field_id)
    carpeta_fuente = carpeta / "source"
    if carpeta_fuente.exists():
        shutil.rmtree(carpeta_fuente)
    carpeta_fuente.mkdir(parents=True)

    if source_id == sources.COPERNICUS_ID:
        original = carpeta_fuente / "copernicus_glo30_window.tif"
        info = sources.fetch_copernicus(_buffer_bbox_4326(field, buffer_m), original)
    elif source_id == sources.UPLOAD_ID:
        if upload_path is None:
            raise sources.DemSourceError("Falta el archivo GeoTIFF del DEM.")
        original = carpeta_fuente / upload_path.name
        shutil.move(str(upload_path), original)
        sources.inspect_upload(original)
        info = None  # se completa después de conocer la resolución
    else:
        raise sources.DemSourceError(f"Fuente de DEM desconocida: {source_id}")

    preparado = prepare_dem(original, field["geometry"], field["utm_epsg"], buffer_m, carpeta / "dem_utm.tif")
    if info is None:
        info = sources.upload_info(upload_meta, round(max(preparado.source_pixel_size_m), 2))

    dem = Dem.open(preparado.path)
    mascara = field_mask(field["geometry"], field["utm_epsg"], dem.transform, dem.z.shape)
    calidad = build_quality_report(dem.z, dem.transform, dem.crs, mascara, field["area_ha"], info,
                                   preparado.source_pixel_size_m, buffer_m)
    terreno = {
        "field_id": field_id,
        "processing_version": PROCESSING_VERSION,
        "processed_at": store.now_iso(),
        "parameters": {"source_id": source_id, "buffer_m": buffer_m, "resampling": "bilinear",
                       "target_crs": dem.crs, "pixel_size_m": preparado.pixel_size_m},
        "source": info.to_dict(),
        "quality": calidad.to_dict(),
        "files": {"original": f"source/{original.name}", "working_dem": "dem_utm.tif"},
        "limitations": LIMITACIONES,
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
    if active_run := hydrology.optional_active_runoff(field_id):
        _, r_grids = active_run
        extra["runoff_load_mm"] = r_grids["runoff_load_mm"]
        extra["cumulative_runoff_m3"] = r_grids["cumulative_runoff_m3"]
    return mesh(dem, mascara, anillos, max_size, extra_grids=extra or None)


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
