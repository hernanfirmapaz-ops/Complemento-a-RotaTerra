"""Persistencia en disco de Fase 0 (sin base de datos).

data/runs/<field_id>/
    field.json          lote validado + metadatos
    source/<archivo>    DEM original (descargado o subido): nunca se modifica
    dem_utm.tif         DEM de trabajo derivado (UTM, recortado al lote + aporte)
    terrain.json        fuente, parámetros, informe de calidad y versión de procesamiento

PostGIS reemplaza a field.json / terrain.json en la Fase 1–2 (SDD §8–9).
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from services.api.app.core.config import DATA_DIR

_ID = re.compile(r"^[0-9a-f]{32}$")


class NotFound(LookupError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex


def field_dir(field_id: str) -> Path:
    if not _ID.match(field_id):  # evita rutas arbitrarias (../) armadas con el id
        raise NotFound(field_id)
    return DATA_DIR / field_id


def save_field(data: dict) -> dict:
    carpeta = field_dir(data["id"])
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "field.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def load_field(field_id: str) -> dict:
    ruta = field_dir(field_id) / "field.json"
    if not ruta.exists():
        raise NotFound(field_id)
    data = json.loads(ruta.read_text(encoding="utf-8"))
    data["has_terrain"] = (field_dir(field_id) / "terrain.json").exists()
    data["has_hydrology"] = (field_dir(field_id) / "hydrology.json").exists()
    return data


def list_fields() -> list[dict]:
    if not DATA_DIR.exists():
        return []
    lotes = []
    for carpeta in DATA_DIR.iterdir():
        if carpeta.is_dir() and _ID.match(carpeta.name) and (carpeta / "field.json").exists():
            lotes.append(load_field(carpeta.name))
    return sorted(lotes, key=lambda f: f["created_at"], reverse=True)


def save_terrain(field_id: str, data: dict) -> None:
    (field_dir(field_id) / "terrain.json").write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                                     encoding="utf-8")


def load_terrain(field_id: str) -> dict:
    ruta = field_dir(field_id) / "terrain.json"
    if not ruta.exists():
        raise NotFound(f"terrain:{field_id}")
    return json.loads(ruta.read_text(encoding="utf-8"))


def save_hydrology(field_id: str, data: dict) -> None:
    (field_dir(field_id) / "hydrology.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def load_hydrology(field_id: str) -> dict:
    ruta = field_dir(field_id) / "hydrology.json"
    if not ruta.exists():
        raise NotFound(f"hydrology:{field_id}")
    return json.loads(ruta.read_text(encoding="utf-8"))


def list_rainfall_events(field_id: str) -> list[dict]:
    ruta = field_dir(field_id) / "rainfall_events.json"
    if not ruta.exists():
        return []
    return json.loads(ruta.read_text(encoding="utf-8"))


def save_rainfall_events(field_id: str, events: list[dict]) -> None:
    (field_dir(field_id) / "rainfall_events.json").write_text(
        json.dumps(events, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def list_runoff_runs(field_id: str) -> list[dict]:
    ruta = field_dir(field_id) / "runoff_runs.json"
    if not ruta.exists():
        return []
    return json.loads(ruta.read_text(encoding="utf-8"))


def save_runoff_runs(field_id: str, runs: list[dict]) -> None:
    (field_dir(field_id) / "runoff_runs.json").write_text(
        json.dumps(runs, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def list_observations(field_id: str) -> list[dict]:
    ruta = field_dir(field_id) / "observations.json"
    if not ruta.exists():
        return []
    return json.loads(ruta.read_text(encoding="utf-8"))


def save_observations(field_id: str, items: list[dict]) -> None:
    (field_dir(field_id) / "observations.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
