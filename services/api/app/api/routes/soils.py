"""Ruta de suelos del lote (spec 004)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from services.api.app.schemas import SoilOut
from services.api.app.services import soils, store

router = APIRouter(prefix="/fields/{field_id}/soil", tags=["soils"])


@router.get("", response_model=SoilOut)
def obtener_suelo(field_id: str, refresh: bool = Query(False, description="Volver a consultar la fuente")):
    """Textura y grupo hidrológico del lote con su fuente real. Sin datos: grupo `null` y calidad `descartada`."""
    try:
        return soils.get_field_soil(field_id, refresh=refresh)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
