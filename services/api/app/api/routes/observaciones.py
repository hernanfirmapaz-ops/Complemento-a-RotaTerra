"""Salida para Rotaterra en el contrato `Observacion` (spec 011)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from services.api.app.schemas import ObservacionOut
from services.api.app.services import observaciones, store

router = APIRouter(prefix="/fields/{field_id}/observaciones", tags=["rotaterra"])


@router.get("", response_model=list[ObservacionOut])
def listar_observaciones(
    field_id: str,
    run_id: str | None = Query(None, description="Corrida a usar; sin valor, la activa más reciente"),
):
    """Resultados de agua, relieve, suelo y erosión del lote para Rotaterra. Solo lee lo ya calculado."""
    try:
        return observaciones.observaciones_del_lote(field_id, run_id=run_id)
    except store.NotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
