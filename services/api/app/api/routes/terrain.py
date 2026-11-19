"""Rutas de terreno (`/api/v1/fields/{field_id}/terrain`): procesamiento DEM, malla 3D, punto y perfil."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from geoprocessing.dem.prepare import BUFFER_MAX_M, DemPreparationError
from geoprocessing.dem.sources import COPERNICUS_ID, UPLOAD_ID, DemSourceError
from services.api.app.core.config import DEFAULT_BUFFER_M, MAX_DEM_BYTES
from services.api.app.schemas import MeshOut, PointOut, ProfileIn, ProfileOut, TerrainOut
from services.api.app.services import store, terrain

router = APIRouter(prefix="/fields/{field_id}/terrain", tags=["terrain"])

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(nombre: str | None) -> str:
    limpio = _SAFE_NAME.sub("_", Path(nombre or "dem_usuario.tif").name).strip("._")
    if not limpio.lower().endswith((".tif", ".tiff")):
        limpio = f"{limpio or 'dem_usuario'}.tif"
    return limpio


@router.get("", response_model=TerrainOut)
def obtener_terreno(field_id: str):
    try:
        store.load_field(field_id)
        return store.load_terrain(field_id)
    except store.NotFound as error:
        raise HTTPException(
            status_code=404,
            detail="El lote no existe o todavía no tiene un DEM procesado.",
        ) from error


@router.post("/process", response_model=TerrainOut)
async def procesar_terreno(
    field_id: str,
    source_id: str = Form(COPERNICUS_ID),
    buffer_m: float = Form(DEFAULT_BUFFER_M),
    file: UploadFile | None = File(None),
    source_name: str | None = Form(None),
    source_url: str | None = Form(None),
    license: str | None = Form(None),
    surface_type: str | None = Form(None),
    vertical_datum: str | None = Form(None),
    vertical_accuracy_m: str | None = Form(None),
    acquisition_date: str | None = Form(None),
    acquisition_method: str | None = Form(None),
):
    try:
        store.load_field(field_id)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Lote no encontrado.") from error

    if not (0 <= buffer_m <= BUFFER_MAX_M):
        raise HTTPException(
            status_code=422,
            detail=f"La zona de aporte (buffer_m) debe estar entre 0 y {BUFFER_MAX_M:.0f} m.",
        )

    temp_path: Path | None = None
    try:
        if source_id == UPLOAD_ID:
            if file is None:
                raise HTTPException(status_code=422, detail="Seleccioná un archivo GeoTIFF para subir.")
            contenido = await file.read(MAX_DEM_BYTES + 1)
            if len(contenido) > MAX_DEM_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"El GeoTIFF supera el tamaño máximo ({MAX_DEM_BYTES // (1024 * 1024)} MB).",
                )
            if len(contenido) < 8 or contenido[:2] not in (b"II", b"MM"):
                raise HTTPException(
                    status_code=422,
                    detail="El archivo subido no tiene cabecera TIFF válida (debe ser un GeoTIFF).",
                )
            tmp_dir = Path(tempfile.mkdtemp(prefix="rotaterra_dem_"))
            temp_path = tmp_dir / _safe_filename(file.filename)
            temp_path.write_bytes(contenido)

        meta = {
            "source_name": source_name,
            "source_url": source_url,
            "license": license,
            "surface_type": surface_type,
            "vertical_datum": vertical_datum,
            "vertical_accuracy_m": vertical_accuracy_m,
            "acquisition_date": acquisition_date,
            "acquisition_method": acquisition_method,
        }
        return terrain.process_terrain(field_id, source_id, buffer_m, temp_path, meta)
    except (DemSourceError, DemPreparationError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
                temp_path.parent.rmdir()
            except OSError:
                pass


@router.get("/mesh", response_model=MeshOut)
def obtener_malla(
    field_id: str,
    max_size: int = Query(180, ge=16, le=512),
):
    try:
        return terrain.terrain_mesh(field_id, max_size)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Terreno no procesado para este lote.") from error


@router.get("/point", response_model=PointOut)
def consultar_punto(
    field_id: str,
    lon: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
):
    try:
        return terrain.terrain_point(field_id, lon, lat)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Terreno no procesado para este lote.") from error


@router.post("/profile", response_model=ProfileOut)
def calcular_perfil(field_id: str, payload: ProfileIn):
    try:
        return terrain.terrain_profile(field_id, payload.coordinates, payload.step_m)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Terreno no procesado para este lote.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
