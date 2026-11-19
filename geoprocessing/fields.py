"""Importación y validación de límites de lotes (SDD §5.1).

Fase 0 admite GeoJSON (Polygon / MultiPolygon, Feature o FeatureCollection).
KML/KMZ, Shapefile ZIP y GeoPackage quedan para una fase siguiente.

Reglas:
- No se reparan geometrías en silencio: si es inválida, se informa el motivo.
- La superficie se calcula en la zona UTM del lote, no en grados.
- No se asume que el límite catastral coincide con el límite productivo.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from shapely.geometry import MultiPolygon, mapping, shape
from shapely.validation import explain_validity

from geoprocessing.crs import WGS84, utm_epsg

ARGENTINA_BBOX = (-73.6, -55.5, -53.5, -21.5)  # oeste, sur, este, norte (aprox. continental)
TOLERANCIA_SUPERFICIE = 0.05  # 5 % de diferencia con la superficie declarada dispara aviso
CLAVES_NOMBRE = ("name", "nombre", "Name", "NOMBRE", "lote", "LOTE")
CLAVES_SUPERFICIE_HA = ("area_ha", "superficie_ha", "sup_ha", "has", "hectareas")
CLAVES_SUPERFICIE_M2 = ("superficie_registrada_m2", "area_m2", "superficie_m2")


class FieldValidationError(ValueError):
    """El archivo o la geometría del lote no son válidos. El mensaje es legible para el usuario."""


@dataclass
class ImportedField:
    name: str
    geometry: dict  # GeoJSON MultiPolygon en EPSG:4326
    properties: dict
    area_ha: float
    declared_area_ha: float | None
    utm_epsg: int
    centroid: tuple[float, float]  # lon, lat
    bbox: tuple[float, float, float, float]  # oeste, sur, este, norte
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _features(data: dict) -> list[dict]:
    tipo = data.get("type")
    if tipo == "FeatureCollection":
        feats = data.get("features") or []
        if not feats:
            raise FieldValidationError("El FeatureCollection no contiene ningún lote")
        return feats
    if tipo == "Feature":
        return [data]
    if tipo in ("Polygon", "MultiPolygon", "Point", "LineString", "MultiPoint", "MultiLineString"):
        return [{"type": "Feature", "properties": {}, "geometry": data}]
    raise FieldValidationError(f"Tipo GeoJSON no reconocido: {tipo!r}")


def _crs_declarado(data: dict) -> str | None:
    """GeoJSON antiguo (2008) podía declarar 'crs'. RFC 7946 exige WGS84 lon/lat."""
    crs = data.get("crs")
    if not crs:
        return None
    nombre = (crs.get("properties") or {}).get("name", "")
    if not nombre or "CRS84" in nombre or nombre.endswith(":4326") or nombre.endswith("::4326"):
        return None
    if "EPSG" in nombre:
        return "EPSG:" + nombre.split(":")[-1]
    raise FieldValidationError(f"CRS declarado no soportado: {nombre!r}")


def _revisar_anillos(geom: dict) -> None:
    poligonos = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    for poligono in poligonos:
        if not poligono:
            raise FieldValidationError("Polígono vacío")
        for anillo in poligono:
            if len(anillo) < 4:
                raise FieldValidationError("Un anillo del polígono tiene menos de 4 vértices")
            if list(anillo[0][:2]) != list(anillo[-1][:2]):
                raise FieldValidationError("Anillo abierto: el primer y el último vértice deben coincidir")


def _superficie_declarada(props: dict) -> float | None:
    for clave in CLAVES_SUPERFICIE_HA:
        if isinstance(props.get(clave), (int, float)) and props[clave] > 0:
            return float(props[clave])
    for clave in CLAVES_SUPERFICIE_M2:
        if isinstance(props.get(clave), (int, float)) and props[clave] > 0:
            return float(props[clave]) / 10_000
    return None


def parse_geojson(contenido: bytes | str | dict, nombre_por_defecto: str = "Lote") -> list[ImportedField]:
    """Lee un GeoJSON y devuelve los lotes validados (uno por Feature)."""
    if isinstance(contenido, (bytes, str)):
        try:
            data = json.loads(contenido)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise FieldValidationError(f"El archivo no es un JSON válido: {error}") from error
    else:
        data = contenido
    if not isinstance(data, dict):
        raise FieldValidationError("El GeoJSON debe ser un objeto JSON")

    crs_origen = _crs_declarado(data)
    lotes = []
    for i, feat in enumerate(_features(data), start=1):
        geom = feat.get("geometry")
        props = dict(feat.get("properties") or {})
        if not geom:
            raise FieldValidationError(f"El elemento {i} no tiene geometría")
        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            raise FieldValidationError(
                f"El elemento {i} es {geom.get('type')}: un lote debe ser Polygon o MultiPolygon")
        _revisar_anillos(geom)
        if crs_origen:
            from rasterio.warp import transform_geom
            geom = transform_geom(crs_origen, WGS84, geom)
        lotes.append(_validar(geom, props, f"{nombre_por_defecto} {i}" if i > 1 else nombre_por_defecto))
    return lotes


def _validar(geom: dict, props: dict, nombre_por_defecto: str) -> ImportedField:
    from rasterio.warp import transform_geom

    try:
        g = shape(geom)
    except Exception as error:  # shapely lanza tipos variados ante coordenadas mal formadas
        raise FieldValidationError(f"Geometría ilegible: {error}") from error
    if g.is_empty:
        raise FieldValidationError("La geometría del lote está vacía")
    if not g.is_valid:
        raise FieldValidationError(
            f"Geometría inválida ({explain_validity(g)}). Corregí el perímetro (¿vértices cruzados o repetidos?)")
    oeste, sur, este, norte = g.bounds
    if not (-180 <= oeste <= 180 and -180 <= este <= 180 and -90 <= sur <= 90 and -90 <= norte <= 90):
        raise FieldValidationError(
            "Coordenadas fuera de rango: el GeoJSON debe estar en grados lon/lat (WGS84). ¿Están invertidas?")

    if g.geom_type == "Polygon":
        g = MultiPolygon([g])
    centro = g.centroid
    epsg = utm_epsg(centro.x, centro.y)
    g_utm = shape(transform_geom(WGS84, f"EPSG:{epsg}", mapping(g)))
    area_ha = g_utm.area / 10_000
    if area_ha <= 0:
        raise FieldValidationError("El lote tiene superficie nula")

    avisos = ["El límite importado puede ser catastral: verificá que coincida con el límite productivo."]
    a_oeste, a_sur, a_este, a_norte = ARGENTINA_BBOX
    if oeste < a_oeste or este > a_este or sur < a_sur or norte > a_norte:
        avisos.append("El lote está fuera del área continental argentina: revisá las coordenadas.")
    declarada = _superficie_declarada(props)
    if declarada and abs(area_ha - declarada) / declarada > TOLERANCIA_SUPERFICIE:
        avisos.append(
            f"La superficie calculada ({area_ha:.1f} ha) difiere más de {TOLERANCIA_SUPERFICIE:.0%} "
            f"de la declarada ({declarada:.1f} ha).")

    nombre = next((str(props[k]) for k in CLAVES_NOMBRE if props.get(k)), nombre_por_defecto)
    return ImportedField(
        name=nombre,
        geometry=mapping(g) | {"coordinates": _listas(mapping(g)["coordinates"])},
        properties=props,
        area_ha=round(area_ha, 3),
        declared_area_ha=round(declarada, 3) if declarada else None,
        utm_epsg=epsg,
        centroid=(round(centro.x, 7), round(centro.y, 7)),
        bbox=(oeste, sur, este, norte),
        warnings=avisos,
    )


def _listas(coords):
    """mapping() de shapely devuelve tuplas; JSON prefiere listas."""
    if isinstance(coords, (list, tuple)) and coords and isinstance(coords[0], (int, float)):
        return [float(c) for c in coords]
    return [_listas(c) for c in coords]


def field_utm_geometry(geometry: dict, epsg: int):
    """Geometría shapely del lote en su zona UTM."""
    from rasterio.warp import transform_geom

    return shape(transform_geom(WGS84, f"EPSG:{epsg}", geometry))
