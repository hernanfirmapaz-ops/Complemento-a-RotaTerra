"""Rutas de hidrología estática (`/api/v1/fields/{field_id}/hydrology`) — Fase 1."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.api.app.schemas import HydrologyOut, HydrologyRunIn
from services.api.app.services import hydrology, store

router = APIRouter(prefix="/fields/{field_id}/hydrology", tags=["hydrology"])


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
