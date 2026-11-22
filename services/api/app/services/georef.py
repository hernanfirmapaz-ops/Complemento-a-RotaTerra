"""Servicio de georreferenciación y límites administrativos oficiales del IGN.

Resuelve la jerarquía administrativa "Provincia · Departamento · Municipio"
para un punto de coordenadas geográficas (longitud, latitud) utilizando
las capas oficiales del Instituto Geográfico Nacional (IGN Argentina)
mediante consultas WFS y caché en memoria de la API.
En pruebas unitarias se inyecta el fixture GeoJSON sin realizar llamadas de red.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from shapely.geometry import Point, shape

logger = logging.getLogger(__name__)

# Caché en memoria para la API de producción: (round(lon, 4), round(lat, 4)) -> dict
_LOCATION_CACHE: dict[tuple[float, float], dict[str, Any]] = {}

# Fixture de pruebas para entorno offline / unit tests
_TEST_FIXTURE_GEOMETRIES: list[dict[str, Any]] | None = None


def set_test_fixture(geometries: list[dict[str, Any]] | None) -> None:
    """Configura o limpia las geometrías de fixture para pruebas offline."""
    global _TEST_FIXTURE_GEOMETRIES
    _TEST_FIXTURE_GEOMETRIES = geometries


def set_test_fixture_file(path: Path | str) -> None:
    """Carga y parsea un archivo GeoJSON de fixture para su uso en pruebas."""
    p = Path(path)
    if not p.exists():
        set_test_fixture(None)
        return
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    geoms: list[dict[str, Any]] = []
    for feat in data.get("features", []):
        geom = shape(feat["geometry"])
        props = feat.get("properties", {})
        tipo = props.get("_tipo_limite")
        if not tipo:
            obj = (props.get("objeto") or "").lower()
            if "provincia" in obj or props.get("gna") == "Provincia":
                tipo = "provincia"
            elif "departamento" in obj or props.get("gna") == "Departamento":
                tipo = "departamento"
            else:
                tipo = "municipio"
        geoms.append({
            "geometry": geom,
            "tipo": tipo,
            "nam": props.get("nam") or props.get("nombre") or props.get("fna"),
            "fna": props.get("fna") or props.get("nam"),
            "properties": props,
        })
    set_test_fixture(geoms)


def clear_cache() -> None:
    """Limpia la caché en memoria de la API."""
    _LOCATION_CACHE.clear()


def _query_wfs_point(layer: str, lon: float, lat: float, timeout_sec: float = 1.0) -> dict[str, Any] | None:
    """Consulta una capa WFS del IGN con un bounding box pequeño y verifica contención puntual."""
    delta = 0.01
    bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"
    url = (
        "https://wms.ign.gob.ar/geoserver/ows?"
        f"service=WFS&version=1.0.0&request=GetFeature&typeName={layer}&outputFormat=application/json&bbox={bbox}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RotaTerra-Georef/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode())
            feats = data.get("features", [])
            pt = Point(lon, lat)
            for f in feats:
                s = shape(f["geometry"])
                if s.contains(pt):
                    return f.get("properties")
            # Si ningún polígono contiene el punto, devolver None (no feats[0])
            return None
    except Exception as exc:
        logger.debug("Error consultando capa WFS IGN %s: %s", layer, exc)
    return None


def resolve_ign_location(lon: float, lat: float) -> dict[str, Any]:
    """Resuelve la provincia, departamento y municipio para una coordenada geográfica dada."""
    cache_key = (round(lon, 4), round(lat, 4))
    if _TEST_FIXTURE_GEOMETRIES is None and cache_key in _LOCATION_CACHE:
        return _LOCATION_CACHE[cache_key]

    pt = Point(lon, lat)
    prov_name: str | None = None
    depto_name: str | None = None
    muni_name: str | None = None

    # Modo pruebas con fixture
    if _TEST_FIXTURE_GEOMETRIES is not None:
        for item in _TEST_FIXTURE_GEOMETRIES:
            geom = item["geometry"]
            if geom.contains(pt):
                tipo = item["tipo"]
                nam = item["nam"]
                if tipo == "provincia" and not prov_name:
                    prov_name = nam
                elif tipo == "departamento" and not depto_name:
                    depto_name = nam
                elif tipo == "municipio" and not muni_name:
                    muni_name = nam
    else:
        # Modo producción: WFS oficial IGN
        p_props = _query_wfs_point("ign:provincia", lon, lat)
        if p_props:
            prov_name = p_props.get("nam") or p_props.get("fna")

        d_props = _query_wfs_point("ign:departamento", lon, lat)
        if d_props:
            depto_name = d_props.get("nam") or d_props.get("fna")

        m_props = _query_wfs_point("ign:gobiernoslocales_2022", lon, lat)
        if m_props:
            muni_name = m_props.get("nam") or m_props.get("fna")

    parts: list[str] = []
    if prov_name:
        parts.append(prov_name)
    if depto_name:
        parts.append(depto_name)
    if muni_name and muni_name != depto_name:
        parts.append(muni_name)

    if parts:
        formatted = " · ".join(parts)
    else:
        formatted = f"Argentina ({lat:.4f}°, {lon:.4f}°)"

    result = {
        "lon": round(lon, 6),
        "lat": round(lat, 6),
        "provincia": prov_name,
        "departamento": depto_name,
        "municipio": muni_name,
        "formatted": formatted,
        "fuente": "Instituto Geográfico Nacional (IGN)",
    }

    if _TEST_FIXTURE_GEOMETRIES is None:
        _LOCATION_CACHE[cache_key] = result

    return result
