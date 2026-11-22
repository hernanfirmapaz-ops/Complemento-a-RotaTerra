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
import os
import zipfile
from dataclasses import asdict, dataclass, field

from shapely.geometry import MultiPolygon, mapping, shape
from shapely.validation import explain_validity

from geoprocessing.crs import WGS84, utm_epsg
from geoprocessing.supuestos import (
    SUPUESTO_LIMITE_DESCOMPRIMIDO_ZIP_MB,
    SUPUESTO_SUPERFICIE_MAXIMA_LOTE_HA,
)

ARGENTINA_BBOX = (-73.6, -55.5, -53.5, -21.5)  # oeste, sur, este, norte (aprox. continental)
TOLERANCIA_SUPERFICIE = 0.05  # 5 % de diferencia con la superficie declarada dispara aviso
CLAVES_NOMBRE = ("name", "nombre", "Name", "NOMBRE", "lote", "LOTE")
CLAVES_SUPERFICIE_HA = ("area_ha", "superficie_ha", "sup_ha", "has", "hectareas")
CLAVES_SUPERFICIE_M2 = ("superficie_registrada_m2", "area_m2", "superficie_m2")


class FieldValidationError(ValueError):
    """El archivo o la geometría del lote no son válidos. El mensaje es legible para el usuario."""


def _get_max_field_area_ha() -> float:
    env_val = os.environ.get("ROTATERRA_MAX_FIELD_AREA_HA")
    if env_val:
        try:
            return float(env_val)
        except ValueError:
            pass
    return float(SUPUESTO_SUPERFICIE_MAXIMA_LOTE_HA.valor)


def _get_max_uncompressed_zip_bytes() -> int:
    env_val = os.environ.get("ROTATERRA_MAX_UNCOMPRESSED_ZIP_MB")
    if env_val:
        try:
            return int(float(env_val)) * 1024 * 1024
        except ValueError:
            pass
    return int(SUPUESTO_LIMITE_DESCOMPRIMIDO_ZIP_MB.valor * 1024 * 1024)


def _validate_zip_archive(zf: zipfile.ZipFile) -> None:
    max_bytes = _get_max_uncompressed_zip_bytes()
    max_mb = max_bytes // (1024 * 1024)
    total_uncompressed = 0
    for info in zf.infolist():
        # Detección de path traversal / zip slip
        norm = info.filename.replace("\\", "/")
        if norm.startswith("/") or ".." in norm.split("/"):
            raise FieldValidationError(
                f"El archivo ZIP contiene una ruta con posible escape de directorio ({info.filename}) no permitida por seguridad."
            )
        total_uncompressed += info.file_size
        if total_uncompressed > max_bytes:
            raise FieldValidationError(
                f"El contenido descomprimido del archivo supera el límite de seguridad permitido "
                f"({max_mb} MB). Operación rechazada para prevenir desbordes de memoria o ataques zip bomb."
            )


def _safe_read_zip_entry(zf: zipfile.ZipFile, name: str) -> bytes:
    max_bytes = _get_max_uncompressed_zip_bytes()
    with zf.open(name, "r") as f:
        chunks = []
        read_bytes = 0
        while chunk := f.read(64 * 1024):
            read_bytes += len(chunk)
            if read_bytes > max_bytes:
                max_mb = max_bytes // (1024 * 1024)
                raise FieldValidationError(
                    f"El contenido descomprimido de '{name}' supera el límite de seguridad ({max_mb} MB)."
                )
            chunks.append(chunk)
        return b"".join(chunks)


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
    max_area_ha = _get_max_field_area_ha()
    if area_ha > max_area_ha:
        raise FieldValidationError(
            f"La superficie del lote '{nombre}' ({area_ha:.1f} ha) supera el límite máximo permitido "
            f"({max_area_ha:.0f} ha / 2.000 ha). Divida el lote en sectores menores o configure "
            f"la variable de entorno ROTATERRA_MAX_FIELD_AREA_HA si necesita procesar áreas mayores."
        )

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


def _parse_kml_coordinates(coord_text: str) -> list[list[float]]:
    ring: list[list[float]] = []
    for token in coord_text.replace("\n", " ").replace("\t", " ").split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lon, lat = float(parts[0]), float(parts[1])
        except ValueError as err:
            raise FieldValidationError(f"Coordenada KML inválida: '{token}'") from err
        ring.append([lon, lat])
    if len(ring) >= 3 and ring[0][:2] != ring[-1][:2]:
        ring.append(list(ring[0]))
    return ring


def parse_kml(kml_bytes: bytes | str, nombre_por_defecto: str = "Lote KML") -> list[ImportedField]:
    """Extrae polígonos de lotes desde un documento KML (OGC KML 2.2)."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(kml_bytes if isinstance(kml_bytes, bytes) else kml_bytes.encode("utf-8"))
    except ET.ParseError as err:
        raise FieldValidationError(f"El archivo KML no es un XML válido: {err}") from err

    def _local(tag: str) -> str:
        return tag.split("}", 1)[-1] if "}" in tag else tag

    features: list[dict] = []
    for pm in root.iter():
        if _local(pm.tag) != "Placemark":
            continue
        pm_name = None
        polys_coords: list[list[list[list[float]]]] = []
        for child in pm.iter():
            ltag = _local(child.tag)
            if ltag == "name" and pm_name is None and child.text and child.text.strip():
                pm_name = child.text.strip()
            elif ltag == "Polygon":
                rings: list[list[list[float]]] = []
                for sub in child.iter():
                    if _local(sub.tag) == "coordinates" and sub.text:
                        ring = _parse_kml_coordinates(sub.text)
                        if ring:
                            rings.append(ring)
                if rings:
                    polys_coords.append(rings)
        if polys_coords:
            geom = (
                {"type": "Polygon", "coordinates": polys_coords[0]}
                if len(polys_coords) == 1
                else {"type": "MultiPolygon", "coordinates": polys_coords}
            )
            features.append({
                "type": "Feature",
                "properties": {"name": pm_name or nombre_por_defecto, "source_format": "KML"},
                "geometry": geom,
            })

    if not features:
        raise FieldValidationError("El archivo KML no contiene ningún Placemark con geometría Polygon.")
    return parse_geojson({"type": "FeatureCollection", "features": features}, nombre_por_defecto)


def parse_kmz(kmz_bytes: bytes, nombre_por_defecto: str = "Lote KMZ") -> list[ImportedField]:
    """Extrae el primer documento `.kml` dentro de un archivo comprimido `.kmz`."""
    import io
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(kmz_bytes)) as zf:
            _validate_zip_archive(zf)
            kml_name = next((n for n in zf.namelist() if n.lower().endswith(".kml")), None)
            if kml_name is None:
                raise FieldValidationError("El archivo KMZ no contiene ningún documento .kml interno.")
            return parse_kml(_safe_read_zip_entry(zf, kml_name), nombre_por_defecto)
    except zipfile.BadZipFile as err:
        raise FieldValidationError("El archivo KMZ está dañado o no es un ZIP válido.") from err


def parse_shapefile_zip(zip_bytes: bytes, nombre_por_defecto: str = "Lote SHP") -> list[ImportedField]:
    """Lee polígonos (tipo 5, 15, 25) desde un Shapefile comprimido (.zip con .shp)."""
    import io
    import struct
    import zipfile

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as err:
        raise FieldValidationError("El archivo ZIP del Shapefile no es válido.") from err

    prj_wkt = None
    record_names: list[str] = []
    with zf:
        _validate_zip_archive(zf)
        shp_name = next((n for n in zf.namelist() if n.lower().endswith(".shp")), None)
        if shp_name is None:
            raise FieldValidationError("El ZIP no contiene ningún archivo .shp.")
        shp = _safe_read_zip_entry(zf, shp_name)
        prj_name = next((n for n in zf.namelist() if n.lower().endswith(".prj")), None)
        if prj_name:
            try:
                prj_wkt = _safe_read_zip_entry(zf, prj_name).decode("utf-8", errors="ignore").strip()
            except Exception:
                prj_wkt = None
        dbf_name_file = next((n for n in zf.namelist() if n.lower().endswith(".dbf")), None)
        if dbf_name_file:
            try:
                dbf_bytes = _safe_read_zip_entry(zf, dbf_name_file)
                if len(dbf_bytes) >= 32:
                    num_records, header_len, record_len = struct.unpack("<IHH", dbf_bytes[4:12])
                    for r_i in range(num_records):
                        offset = header_len + r_i * record_len
                        if offset + record_len <= len(dbf_bytes):
                            raw_val = dbf_bytes[offset + 1:offset + record_len]
                            val_str = raw_val.decode("utf-8", errors="ignore").replace("\x00", "").strip()
                            if val_str:
                                record_names.append(val_str)
            except Exception:
                pass

    if len(shp) < 100:
        raise FieldValidationError("El archivo .shp está truncado.")
    file_code = struct.unpack(">i", shp[0:4])[0]
    if file_code != 9994:
        raise FieldValidationError("Cabecera de archivo .shp inválida.")

    pos = 100
    features: list[dict] = []
    rec_idx = 0
    while pos + 8 <= len(shp):
        rec_num, content_len_words = struct.unpack(">ii", shp[pos:pos + 8])
        pos += 8
        rec_bytes = content_len_words * 2
        rec = shp[pos:pos + rec_bytes]
        pos += rec_bytes
        if len(rec) < 4:
            break
        shape_type = struct.unpack("<i", rec[0:4])[0]
        if shape_type == 0:
            continue
        if shape_type not in (5, 15, 25):  # Polygon, PolygonZ, PolygonM
            raise FieldValidationError(
                f"El registro #{rec_num} del Shapefile tiene tipo {shape_type}; solo se admiten polígonos."
            )
        num_parts, num_points = struct.unpack("<ii", rec[36:44])
        parts = list(struct.unpack(f"<{num_parts}i", rec[44:44 + 4 * num_parts]))
        pts_offset = 44 + 4 * num_parts
        coords_flat = struct.unpack(f"<{2 * num_points}d", rec[pts_offset:pts_offset + 16 * num_points])
        pts = [[coords_flat[2 * i], coords_flat[2 * i + 1]] for i in range(num_points)]
        if prj_wkt:
            try:
                from rasterio.crs import CRS
                from rasterio.warp import transform
                src_crs = CRS.from_user_input(prj_wkt)
                if not src_crs.is_geographic:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    lons, lats = transform(src_crs, "EPSG:4326", xs, ys)
                    pts = [[lons[i], lats[i]] for i in range(num_points)]
            except Exception:
                pass
        rings: list[list[list[float]]] = []
        for p_i, start_idx in enumerate(parts):
            end_idx = parts[p_i + 1] if p_i + 1 < num_parts else num_points
            ring = pts[start_idx:end_idx]
            if len(ring) >= 3 and ring[0][:2] != ring[-1][:2]:
                ring.append(list(ring[0]))
            rings.append(ring)
        feature_name = record_names[rec_idx] if rec_idx < len(record_names) else f"{nombre_por_defecto} {rec_idx + 1}"
        features.append({
            "type": "Feature",
            "properties": {"name": feature_name, "source_format": "Shapefile"},
            "geometry": {"type": "Polygon", "coordinates": rings},
        })
        rec_idx += 1

    if not features:
        raise FieldValidationError("El Shapefile no contiene polígonos.")
    return parse_geojson({"type": "FeatureCollection", "features": features}, nombre_por_defecto)


def parse_field_file(
    contenido: bytes | str,
    filename: str | None = None,
    nombre_por_defecto: str = "Lote",
) -> list[ImportedField]:
    """Detecta el formato del archivo de lote (GeoJSON, KML, KMZ o Shapefile ZIP) y devuelve los lotes validados."""
    fname = (filename or "").lower()
    raw = contenido.encode("utf-8") if isinstance(contenido, str) else contenido

    if fname.endswith(".kmz"):
        return parse_kmz(raw, nombre_por_defecto)
    if fname.endswith(".zip") or raw[:2] == b"PK":
        # Un ZIP puede ser un KMZ o un Shapefile comprimido
        import io
        import zipfile

        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                _validate_zip_archive(zf)
                names = [n.lower() for n in zf.namelist()]
                if any(n.endswith(".kml") for n in names):
                    return parse_kmz(raw, nombre_por_defecto)
                if any(n.endswith(".shp") for n in names):
                    return parse_shapefile_zip(raw, nombre_por_defecto)
        except zipfile.BadZipFile as err:
            raise FieldValidationError("El archivo ZIP/KMZ no es válido.") from err
        raise FieldValidationError("El archivo ZIP debe contener un Shapefile (.shp) o un documento KML (.kml).")

    if fname.endswith(".kml") or raw.lstrip().startswith(b"<"):
        return parse_kml(raw, nombre_por_defecto)

    return parse_geojson(raw, nombre_por_defecto)
