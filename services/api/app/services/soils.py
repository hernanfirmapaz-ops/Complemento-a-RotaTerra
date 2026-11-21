"""Suelo del lote con caché local (spec 004)."""

from __future__ import annotations

import json

from geoprocessing.soils.soilgrids import soil_for_field
from services.api.app.services import store


def get_field_soil(field_id: str, refresh: bool = False) -> dict:
    """Devuelve el suelo del lote. Los resultados válidos se guardan en `soil.json`;
    un resultado sin datos (sin conexión) no se guarda, para reintentar en la próxima consulta."""
    field = store.load_field(field_id)
    ruta = store.field_dir(field_id) / "soil.json"
    if ruta.exists() and not refresh:
        return json.loads(ruta.read_text(encoding="utf-8"))
    suelo = soil_for_field(field["geometry"])
    if suelo["quality"] != "descartada":
        ruta.write_text(json.dumps(suelo, ensure_ascii=False, indent=2), encoding="utf-8")
    return suelo
