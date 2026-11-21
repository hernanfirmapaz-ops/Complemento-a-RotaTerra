"""Conector a SoilGrids 2.0 (ISRIC) para textura del suelo del lote (spec 004).

Fuente: ISRIC World Soil Information, SoilGrids 2.0 (Poggio et al., 2021, SOIL 7: 217–240).
Licencia: CC BY 4.0. Resolución nominal: 250 m.

Nunca inventa valores: si la API no responde o no trae datos, devuelve `soil_group = None`,
`soil_source = "default"` y `quality = "descartada"` con el motivo.
"""

from __future__ import annotations

import httpx
from shapely.geometry import Point, shape

from geoprocessing.net import client
from geoprocessing.soils.texture import hydrologic_group_from_texture, usda_texture_class

SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
DEPTHS = (("0-5cm", 5.0), ("5-15cm", 10.0), ("15-30cm", 15.0))
PROPERTIES = ("clay", "sand", "silt")
SOURCE_LABEL = "SoilGrids 2.0 (ISRIC) · 250 m · 0–30 cm"
LICENSE = "CC BY 4.0"
MAX_POINTS = 3  # la API pública limita los pedidos por minuto

LIMITATIONS = [
    "SoilGrids es un modelo global de 250 m: no distingue lomas y bajos dentro del lote.",
    "El grupo hidrológico por textura no considera la napa: un bajo con napa somera se comporta como grupo D.",
    "El sellado superficial de suelos arenosos con poca materia orgánica puede aumentar el escurrimiento.",
]


def sample_points(geometry: dict, max_points: int = MAX_POINTS) -> list[tuple[float, float]]:
    """Centroide y puntos interiores del lote (lon, lat), todos dentro del polígono."""
    geom = shape(geometry)
    puntos: list[tuple[float, float]] = []
    interior = geom.representative_point()
    centro = geom.centroid if geom.contains(geom.centroid) else interior
    puntos.append((centro.x, centro.y))
    minx, miny, maxx, maxy = geom.bounds
    candidatos = [
        ((minx + centro.x) / 2, (miny + centro.y) / 2),
        ((maxx + centro.x) / 2, (maxy + centro.y) / 2),
        ((minx + centro.x) / 2, (maxy + centro.y) / 2),
        ((maxx + centro.x) / 2, (miny + centro.y) / 2),
    ]
    for lon, lat in candidatos:
        if len(puntos) >= max_points:
            break
        if geom.contains(Point(lon, lat)):
            puntos.append((lon, lat))
    if len(puntos) < max_points and (interior.x, interior.y) not in puntos:
        puntos.append((interior.x, interior.y))
    return puntos[:max_points]


def _weighted_percent(layer: dict) -> float | None:
    """Promedio 0–30 cm ponderado por espesor, en %, a partir de una capa de SoilGrids."""
    d_factor = float(layer.get("unit_measure", {}).get("d_factor", 10) or 10)
    total, peso = 0.0, 0.0
    por_prof = {d.get("label"): d.get("values", {}).get("mean") for d in layer.get("depths", [])}
    for etiqueta, espesor in DEPTHS:
        valor = por_prof.get(etiqueta)
        if valor is None:
            continue
        # SoilGrids entrega g/kg multiplicado por d_factor; g/kg / 10 = %
        total += (float(valor) / d_factor) / 10.0 * espesor
        peso += espesor
    return total / peso if peso else None


def query_point(lon: float, lat: float, http: httpx.Client | None = None) -> dict[str, float] | None:
    """Arena, limo y arcilla (%) 0–30 cm en un punto. `None` si no hay datos."""
    params: list[tuple[str, str | float]] = [("lon", round(lon, 5)), ("lat", round(lat, 5)), ("value", "mean")]
    params += [("property", p) for p in PROPERTIES]
    params += [("depth", d) for d, _ in DEPTHS]
    respuesta = (http or client()).get(SOILGRIDS_URL, params=params, timeout=30.0)
    respuesta.raise_for_status()
    capas = respuesta.json().get("properties", {}).get("layers", [])
    valores: dict[str, float] = {}
    for capa in capas:
        nombre = capa.get("name")
        if nombre in PROPERTIES:
            pct = _weighted_percent(capa)
            if pct is not None:
                valores[nombre] = pct
    if set(valores) != set(PROPERTIES) or sum(valores.values()) <= 0:
        return None
    return valores


def _sin_dato(motivo: str, puntos: int = 0) -> dict:
    return {
        "soil_group": None,
        "texture_class": None,
        "clay_pct": None,
        "sand_pct": None,
        "silt_pct": None,
        "soil_source": "default",
        "source_label": "Sin fuente de suelos disponible",
        "resolution_m": None,
        "license": None,
        "points_used": puntos,
        "quality": "descartada",
        "notes": [motivo],
    }


def soil_for_field(geometry: dict, http: httpx.Client | None = None) -> dict:
    """Textura y grupo hidrológico del lote según SoilGrids, promediando hasta 3 puntos interiores."""
    muestras: list[dict[str, float]] = []
    errores: list[str] = []
    for lon, lat in sample_points(geometry):
        try:
            valores = query_point(lon, lat, http=http)
        except (httpx.HTTPError, ValueError) as error:
            errores.append(f"{type(error).__name__}")
            continue
        if valores:
            muestras.append(valores)

    if not muestras:
        motivo = "No se pudo consultar SoilGrids (sin conexión o sin datos para el lote)."
        if errores:
            motivo += f" Detalle: {', '.join(sorted(set(errores)))}."
        return _sin_dato(motivo)

    prom = {p: sum(m[p] for m in muestras) / len(muestras) for p in PROPERTIES}
    textura = usda_texture_class(prom["sand"], prom["silt"], prom["clay"])
    grupo = hydrologic_group_from_texture(textura)
    return {
        "soil_group": grupo,
        "texture_class": textura,
        "clay_pct": round(prom["clay"], 1),
        "sand_pct": round(prom["sand"], 1),
        "silt_pct": round(prom["silt"], 1),
        "soil_source": "soilgrids",
        "source_label": SOURCE_LABEL,
        "resolution_m": 250,
        "license": LICENSE,
        "points_used": len(muestras),
        "quality": "dudosa" if len(muestras) < 2 else "buena",
        "notes": [
            f"Grupo hidrológico {grupo} aproximado por textura ({textura}), Rawls et al. 1982.",
            *LIMITATIONS,
        ],
    }

