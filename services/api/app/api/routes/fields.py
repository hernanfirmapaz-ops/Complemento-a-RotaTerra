"""Rutas de lotes (`/api/v1/fields`): importación GeoJSON, listado, consulta y lote de prueba real."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from geoprocessing.fields import FieldValidationError, parse_field_file
from services.api.app.core.config import MAX_GEOJSON_BYTES, SAMPLE_DIR
from services.api.app.schemas import FieldImportOut, FieldOut
from services.api.app.services import store

router = APIRouter(prefix="/fields", tags=["fields"])


def _guardar_lotes(contenido: bytes | str, nombre_base: str, origen: str | None) -> list[dict]:
    try:
        importados = parse_field_file(contenido, filename=origen, nombre_por_defecto=nombre_base)
    except FieldValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    creados = []
    for lote in importados:
        registro = lote.to_dict() | {
            "id": store.new_id(),
            "created_at": store.now_iso(),
            "source_file": origen,
            "has_terrain": False,
        }
        store.save_field(registro)
        creados.append(registro)
    return creados


@router.get("", response_model=list[FieldOut])
def listar_lotes():
    return store.list_fields()


@router.post("/import", response_model=FieldImportOut, status_code=201)
async def importar_lotes(
    file: UploadFile = File(...),
    default_name: str = Form("Lote"),
):
    contenido = await file.read(MAX_GEOJSON_BYTES + 1)
    if len(contenido) > MAX_GEOJSON_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo GeoJSON supera el tamaño máximo ({MAX_GEOJSON_BYTES // (1024 * 1024)} MB).",
        )
    if not contenido.strip():
        raise HTTPException(status_code=422, detail="El archivo está vacío.")
    nombre = (default_name or Path(file.filename or "Lote").stem).strip() or "Lote"
    creados = _guardar_lotes(contenido, nombre, file.filename)
    return {"fields": creados}


@router.post("/sample", response_model=FieldImportOut, status_code=201)
def cargar_lote_de_prueba():
    """Importa el lote real de prueba documentado en `data/sample/san_luis_parcela_205.geojson`."""
    ruta = SAMPLE_DIR / "san_luis_parcela_205.geojson"
    if not ruta.exists():
        raise HTTPException(status_code=404, detail="No se encontró el archivo de lote de prueba en data/sample.")
    # Si ya existe un lote con la misma nomenclatura catastral, devolverlo sin duplicar
    for existente in store.list_fields():
        if existente.get("source_file") == ruta.name:
            return {"fields": [existente]}
    creados = _guardar_lotes(ruta.read_bytes(), "Parcela Rural 205 (San Luis)", ruta.name)
    return {"fields": creados}


@router.get("/{field_id}", response_model=FieldOut)
def obtener_lote(field_id: str):
    try:
        return store.load_field(field_id)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Lote no encontrado.") from error
