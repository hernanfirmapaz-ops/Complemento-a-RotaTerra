"""Configuración por variables de entorno (sin secretos en el código)."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = Path(os.environ.get("ROTATERRA_DATA_DIR", REPO_ROOT / "data" / "runs"))
SAMPLE_DIR = REPO_ROOT / "data" / "sample"
WEB_DIST = REPO_ROOT / "apps" / "web" / "dist"

MAX_GEOJSON_BYTES = int(os.environ.get("ROTATERRA_MAX_GEOJSON_MB", "5")) * 1024 * 1024
MAX_DEM_BYTES = int(os.environ.get("ROTATERRA_MAX_DEM_MB", "300")) * 1024 * 1024
DEFAULT_BUFFER_M = 300.0
CORS_ORIGINS = [o for o in os.environ.get("ROTATERRA_CORS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o]
