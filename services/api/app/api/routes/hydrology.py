"""Rutas de hidrología estática (Fase 1) y eventos de lluvia + escorrentía NRCS-CN (Fase 2)."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from geoprocessing.rainfall.events import RainfallValidationError
from services.api.app.schemas import (
    AgronomicToolkitIn,
    AgronomicToolkitOut,
    CatalogOut,
    FieldObservationIn,
    FieldObservationOut,
    Hydrodynamic2DIn,
    HydrologyOut,
    HydrologyRunIn,
    RainfallEventManualIn,
    RainfallEventOut,
    RunoffRunIn,
    RunoffRunOut,
    RunoffTimelineOut,
    ScenarioComparisonOut,
)
from services.api.app.services import hydrology, store

router = APIRouter(prefix="/fields/{field_id}/hydrology", tags=["hydrology"])


@router.get("/catalog", response_model=CatalogOut)
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


@router.get("/runoff-runs/{run_id}/timeline", response_model=RunoffTimelineOut)
def obtener_linea_de_tiempo_escorrentia(field_id: str, run_id: str):
    try:
        return hydrology.get_runoff_timeline(field_id, run_id)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail=f"Recurso no encontrado: {error}") from error


@router.post("/runoff-runs/{run_id}/simulate-2d", response_model=RunoffRunOut)
def ejecutar_solver_hidrodinamico_2d(
    field_id: str,
    run_id: str,
    payload: Hydrodynamic2DIn | None = None,
):
    try:
        params = payload or Hydrodynamic2DIn()
        return hydrology.execute_hydrodynamic_2d_on_run(field_id, run_id, params)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail=f"Recurso no encontrado: {error}") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/observations", response_model=list[FieldObservationOut])
def listar_observaciones_campo(field_id: str):
    try:
        store.load_field(field_id)
        return store.list_observations(field_id)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Lote no encontrado.") from error


@router.post("/observations", response_model=FieldObservationOut, status_code=201)
def registrar_observacion_campo(field_id: str, payload: FieldObservationIn):
    try:
        return hydrology.create_field_observation(field_id, payload)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Lote no encontrado.") from error


@router.delete("/observations/{obs_id}", status_code=204)
def eliminar_observacion_campo(field_id: str, obs_id: str):
    try:
        hydrology.delete_field_observation(field_id, obs_id)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Observación no encontrada.") from error


@router.get("/export/geojson")
def exportar_paquete_geojson(field_id: str):
    try:
        pkg = hydrology.export_analysis_geojson(field_id)
        return JSONResponse(
            content=pkg,
            headers={
                "Content-Disposition": f'attachment; filename="rotaterra_hidrologia_{field_id[:8]}.geojson"'
            },
        )
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Lote no encontrado.") from error


@router.get("/export/report", response_class=HTMLResponse)
def exportar_informe_tecnico_html(field_id: str):
    try:
        html_doc = hydrology.export_technical_report_html(field_id)
        return HTMLResponse(content=html_doc)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail="Lote no encontrado.") from error


@router.get("/toolkit", response_model=AgronomicToolkitOut)
def obtener_toolkit_agronomico(field_id: str):
    try:
        store.load_field(field_id)
        return hydrology.load_agronomic_toolkit(field_id)
    except store.NotFound as error:
        raise HTTPException(
            status_code=404,
            detail="Todavía no se ejecutó el paquete de herramientas agronómicas para este lote.",
        ) from error


@router.post("/toolkit/run", response_model=AgronomicToolkitOut)
def ejecutar_toolkit_agronomico(
    field_id: str,
    payload: AgronomicToolkitIn | None = None,
):
    try:
        params = payload or AgronomicToolkitIn()
        return hydrology.run_agronomic_toolkit(field_id, params)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail=f"Recurso no encontrado: {error}") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
