"""Rutas de hidrología estática (Fase 1) y eventos de lluvia + escorrentía NRCS-CN (Fase 2)."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from geoprocessing.rainfall.events import RainfallValidationError
from services.api.app.schemas import (
    HydrologyOut,
    HydrologyRunIn,
    RainfallEventManualIn,
    RainfallEventOut,
    RunoffRunIn,
    RunoffRunOut,
    ScenarioComparisonOut,
)
from services.api.app.services import hydrology, store

router = APIRouter(prefix="/fields/{field_id}/hydrology", tags=["hydrology"])


@router.get("/catalog")
def obtener_catalogo_hidrologico(field_id: str):
    return hydrology.get_hydrology_catalog()


@router.get("", response_model=HydrologyOut)
def obtener_hidrologia_estatica(field_id: str):
    try:
        store.load_field(field_id)
        return store.load_hydrology(field_id)
    except store.NotFound as error:
        raise HTTPException(
            status_code=404,
            detail="El lote no existe o todavía no tiene una corrida de hidrología estática.",
        ) from error


@router.post("/static", response_model=HydrologyOut)
def ejecutar_hidrologia_estatica(field_id: str, payload: HydrologyRunIn | None = None):
    try:
        store.load_field(field_id)
        store.load_terrain(field_id)
    except store.NotFound as error:
        raise HTTPException(
            status_code=404,
            detail="Primero debés cargar el lote y procesar su Modelo Digital de Elevación.",
        ) from error
    params = payload or HydrologyRunIn()
    return hydrology.run_static_hydrology(field_id, params)


@router.get("/rainfall-events", response_model=list[RainfallEventOut])
def listar_eventos_lluvia(field_id: str):
    try:
        store.load_field(field_id)
        return store.list_rainfall_events(field_id)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Lote no encontrado.") from error


@router.post("/rainfall-events", response_model=RainfallEventOut, status_code=201)
def crear_evento_lluvia_manual(field_id: str, payload: RainfallEventManualIn):
    try:
        return hydrology.create_manual_rainfall_event(field_id, payload)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Lote no encontrado.") from error


@router.post("/rainfall-events/import-csv", response_model=RainfallEventOut, status_code=201)
async def importar_evento_lluvia_csv(
    field_id: str,
    file: UploadFile = File(...),
    name: str = Form("Tormenta CSV"),
    source_type: str = Form("gauge"),
    declared_total_mm: float | None = Form(None),
):
    contenido = await file.read(2 * 1024 * 1024)
    try:
        return hydrology.import_csv_rainfall_event(
            field_id=field_id,
            csv_bytes=contenido,
            name=name,
            source_type=source_type,
            declared_total_mm=declared_total_mm,
        )
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Lote no encontrado.") from error
    except RainfallValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/rainfall-events/sample", response_model=RainfallEventOut, status_code=201)
def cargar_evento_lluvia_muestra(field_id: str):
    try:
        return hydrology.load_sample_rainfall_event(field_id)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Lote no encontrado.") from error


@router.get("/runoff-runs", response_model=list[RunoffRunOut])
def listar_corridas_escorrentia(field_id: str):
    try:
        store.load_field(field_id)
        return store.list_runoff_runs(field_id)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Lote no encontrado.") from error


@router.post("/runoff-runs", response_model=RunoffRunOut, status_code=201)
def ejecutar_corrida_escorrentia(field_id: str, payload: RunoffRunIn):
    try:
        return hydrology.execute_runoff_run(field_id, payload)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail=f"Recurso no encontrado: {error}") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/runoff-runs/{run_id}/activate", response_model=RunoffRunOut)
def activar_corrida_escorrentia(field_id: str, run_id: str):
    try:
        return hydrology.activate_runoff_run(field_id, run_id)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Corrida de escorrentía no encontrada.") from error


@router.get("/compare", response_model=ScenarioComparisonOut)
def comparar_escenarios_escorrentia(
    field_id: str,
    run_a: str = Query(..., description="ID de la corrida base A"),
    run_b: str = Query(..., description="ID de la corrida comparada B"),
):
    try:
        return hydrology.compare_two_runs(field_id, run_a, run_b)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
