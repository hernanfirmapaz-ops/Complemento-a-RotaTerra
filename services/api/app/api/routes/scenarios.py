"""Rutas para el motor de escenarios hidrológicos y comparación lado a lado (SDD-003 §4 / Tarea 2.2)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from services.api.app.schemas import RunoffRunOut, ScenarioComparisonOut
from services.api.app.services import hydrology, store

router = APIRouter(prefix="/fields/{field_id}/scenarios", tags=["scenarios"])


@router.get("/compare", response_model=ScenarioComparisonOut)
def comparar_escenarios(
    field_id: str,
    run_a_id: str | None = Query(None, description="ID de la corrida base A"),
    run_b_id: str | None = Query(None, description="ID de la corrida comparada B"),
    run_a: str | None = Query(None, description="Alias alternativo para ID de corrida base A"),
    run_b: str | None = Query(None, description="Alias alternativo para ID de corrida comparada B"),
):
    """Compara dos escenarios lado a lado reportando diferencias en lluvia, volumen escurrido,
    escurrimiento fuera (%), superficie anegable (ha) y suelo fértil perdido (t/ha),
    junto con un resumen explicativo en lenguaje de campo (SDD-003 §4.1).
    """
    id_a = run_a_id or run_a
    id_b = run_b_id or run_b
    if not id_a or not id_b:
        raise HTTPException(
            status_code=422,
            detail="Se deben proporcionar run_a_id y run_b_id (o run_a y run_b) para realizar la comparación.",
        )
    try:
        store.load_field(field_id)
        return hydrology.compare_two_runs(field_id, id_a, id_b)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/simulate-presets", response_model=list[RunoffRunOut], status_code=201)
def simular_escenarios_estandar(
    field_id: str,
    soil_group: str = Query("B", description="Grupo hidrológico de suelo (A, B, C, D)"),
    cover_code: str = Query("soja_maiz_sd_buena", description="Código de cobertura / manejo"),
):
    """Ejecuta en una llamada los 3 escenarios estándar de diseño:
    - Conservador (30 mm) · Lluvia suave
    - Medio (80 mm) · Tormenta de diseño
    - Crítico (130 mm) · Crecida extraordinaria
    según Tarea 2.2 / SDD-003.
    """
    try:
        store.load_field(field_id)
        return hydrology.execute_standard_scenarios(field_id, soil_group=soil_group, cover_code=cover_code)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
