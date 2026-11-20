"""Configuración por variables de entorno (sin secretos en el código)."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

# Cargar .env local si existe (sin commitear secretos)
env_file = REPO_ROOT / ".env"
if env_file.exists():
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass

DATA_DIR = Path(os.environ.get("ROTATERRA_DATA_DIR", REPO_ROOT / "data" / "runs"))
SAMPLE_DIR = REPO_ROOT / "tests" / "fixtures" / "lotes"
WEB_DIST = REPO_ROOT / "apps" / "web" / "dist"

MAX_GEOJSON_BYTES = int(os.environ.get("ROTATERRA_MAX_GEOJSON_MB", "5")) * 1024 * 1024
MAX_DEM_BYTES = int(os.environ.get("ROTATERRA_MAX_DEM_MB", "300")) * 1024 * 1024
DEFAULT_BUFFER_M = 300.0
CORS_ORIGINS = [o for o in os.environ.get("ROTATERRA_CORS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o]
OPENTOPOGRAPHY_API_KEY = os.environ.get("OPENTOPOGRAPHY_API_KEY", "")
