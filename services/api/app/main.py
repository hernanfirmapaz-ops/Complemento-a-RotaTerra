"""Punto de entrada FastAPI — Visor 3D de lotes y análisis topográfico (Fase 0)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from geoprocessing import PROCESSING_VERSION
from services.api.app.api.routes import fields, georef, hydrology, observaciones, scenarios, soils, terrain
from services.api.app.core.config import CORS_ORIGINS, WEB_DIST

app = FastAPI(
    title="RotaTerra — Visor 3D e Hidrología (Fases 0 a 5 · Suite Completa)",
    description=(
        "Módulo geoespacial para visualización 3D de lotes agrícolas (GeoJSON/KML/KMZ/Shapefile), "
        "control de calidad de DEM, inspección de cota/pendiente, perfiles altimétricos, hidrología "
        "estática (D8, MFD, TWI, SPI, depresiones, red de drenaje y subcuencas), estimación de "
        "escorrentía por evento (NRCS Curve Number + comparación de escenarios), animación temporal "
        "por hietograma, solver hidrodinámico 2D de onda difusiva (Manning) y zonificación de "
        "ambientes hidro-agronómicos y transitabilidad para RotaTerra."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fields.router, prefix="/api/v1")
app.include_router(terrain.router, prefix="/api/v1")
app.include_router(hydrology.router, prefix="/api/v1")
app.include_router(scenarios.router, prefix="/api/v1")
app.include_router(soils.router, prefix="/api/v1")
app.include_router(observaciones.router, prefix="/api/v1")
app.include_router(georef.router, prefix="/api/v1")
app.include_router(scenarios.router, prefix="/api")


@app.get("/api/v1/health")
def health():
    return {
        "status": "ok",
        "phase": "fase-5-suite-completa-rotaterra",
        "processing_version": PROCESSING_VERSION,
    }


if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")
