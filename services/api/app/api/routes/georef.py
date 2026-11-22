"""Rutas de georreferenciación y límites administrativos del IGN."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from services.api.app.services.georef import resolve_ign_location

router = APIRouter(prefix="/georef", tags=["georef"])


class LocationResponse(BaseModel):
    lon: float = Field(..., description="Longitud geográfica en grados decimales")
    lat: float = Field(..., description="Latitud geográfica en grados decimales")
    provincia: str | None = Field(None, description="Nombre de la provincia según IGN")
    departamento: str | None = Field(None, description="Nombre del departamento o partido según IGN")
    municipio: str | None = Field(None, description="Nombre del municipio o gobierno local según IGN")
    formatted: str = Field(..., description="Cadena jerárquica 'Provincia · Departamento · Municipio'")
    fuente: str = Field("Instituto Geográfico Nacional (IGN)", description="Atribución oficial de la capa")


@router.get("/location", response_model=LocationResponse)
def get_location(
    lon: float = Query(..., description="Longitud WGS84 (-180 a 180)", ge=-180, le=180),
    lat: float = Query(..., description="Latitud WGS84 (-90 a 90)", ge=-90, le=90),
):
    """Resuelve la ubicación administrativa oficial 'Provincia · Departamento · Municipio' según IGN."""
    res = resolve_ign_location(lon, lat)
    return LocationResponse(**res)
