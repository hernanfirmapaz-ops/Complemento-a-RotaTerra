"""Genera archivos GeoJSON simplificados y livianos de provincias y departamentos de Argentina

a partir del servicio WFS oficial del Instituto Geográfico Nacional (IGN).
Fuente oficial: https://wms.ign.gob.ar/geoserver/ows
Capas:
  - ign:provincia (24 jurisdicciones de primer orden)
  - ign:departamento (529 departamentos / partidos)
Licencia IGN: Creative Commons Atribución (CC-BY 4.0 / IDERA · Ley 22.963).
Cita obligatoria: "FUENTE: Instituto Geográfico Nacional de la República Argentina"
Fecha de descarga y procesamiento: 2026-11-23.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any

import shapely.geometry
from shapely.validation import make_valid

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "apps" / "web" / "public" / "data" / "boundaries"
CACHE_DIR = REPO_ROOT / ".cache" / "ign_wfs"

IGN_WFS_BASE = "https://wms.ign.gob.ar/geoserver/ows"

# Tolerancias geodésicas en grados WGS84 (~111 km por grado en latitud):
# Provincias: ~0.007° (~700 m)
# Departamentos: ~0.0048° (~500 m en continente, mayor en islas subantárticas/Antártida)
TOLERANCIA_PROVINCIAS_DEG = 0.007
TOLERANCIA_DEPARTAMENTOS_DEG = 0.0048
COORD_DECIMALS = 4


def fetch_wfs_geojson(type_name: str, timeout_sec: int = 180) -> dict[str, Any]:
    """Descarga WFS oficial con caché local en .cache/ign_wfs para no saturar el servicio."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{type_name.replace(':', '_')}.json"
    if cache_file.exists():
        print(f"Leyendo {type_name} desde caché local: {cache_file}")
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    url = (
        f"{IGN_WFS_BASE}?service=WFS&version=1.1.0"
        f"&request=GetFeature&typeName={type_name}&outputFormat=application/json"
    )
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "RotaTerra-Agro/1.0 (Descarga cartografia oficial IGN)"},
    )
    print(f"Descargando WFS {type_name} desde {IGN_WFS_BASE}...")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        content = resp.read()
    print(f"Descargado {type_name}: {len(content) / 1024:.1f} KB en {time.time() - t0:.2f}s")
    data = json.loads(content.decode("utf-8"))
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def round_coordinates(geom: Any, decimals: int = 4) -> Any:
    if isinstance(geom, (list, tuple)):
        if len(geom) == 2 and isinstance(geom[0], (int, float)) and isinstance(geom[1], (int, float)):
            return [round(float(geom[0]), decimals), round(float(geom[1]), decimals)]
        return [round_coordinates(c, decimals) for c in geom]
    return geom


def simplify_geometry(
    poly: shapely.geometry.base.BaseGeometry,
    base_tolerance: float,
) -> shapely.geometry.base.BaseGeometry:
    miny = poly.bounds[1]
    if miny < -60:  # Sector Antártico
        simp = poly.simplify(0.08, preserve_topology=True)
        min_area = 0.02
    elif miny < -50:  # Islas del Atlántico Sur
        simp = poly.simplify(0.03, preserve_topology=True)
        min_area = 0.005
    else:  # Territorio continental
        simp = poly.simplify(base_tolerance, preserve_topology=True)
        min_area = 0.0003

    if simp.geom_type == "MultiPolygon":
        parts = [p for p in simp.geoms if p.area > min_area]
        if not parts:
            parts = [max(simp.geoms, key=lambda p: p.area)]
        return shapely.geometry.MultiPolygon(parts) if len(parts) > 1 else parts[0]
    return simp


def simplify_geojson(
    fc: dict[str, Any],
    tolerance: float,
    decimals: int = 4,
    prop_extractor: Any = None,
) -> dict[str, Any]:
    features_out: list[dict[str, Any]] = []

    for f in fc.get("features", []):
        geom_raw = f.get("geometry")
        if not geom_raw:
            continue
        try:
            poly = shapely.geometry.shape(geom_raw)
            if not poly.is_valid:
                poly = make_valid(poly)
            simp = simplify_geometry(poly, tolerance)
            if simp.is_empty:
                continue

            geo_dict = shapely.geometry.mapping(simp)
            geo_dict["coordinates"] = round_coordinates(geo_dict["coordinates"], decimals)

            props = prop_extractor(f["properties"]) if prop_extractor else f.get("properties", {})

            features_out.append(
                {
                    "type": "Feature",
                    "properties": props,
                    "geometry": geo_dict,
                }
            )
        except Exception as e:
            print(f"Advertencia al simplificar feature {f.get('id')}: {e}")

    return {
        "type": "FeatureCollection",
        "metadata": {
            "fuente": "Instituto Geográfico Nacional de la República Argentina (IGN)",
            "url_wfs": IGN_WFS_BASE,
            "licencia": "Datos Abiertos IGN / IDERA (Ley 22.963) · CC-BY 4.0",
            "cita": "FUENTE: Instituto Geográfico Nacional de la República Argentina",
            "fecha_descarga": "2026-11-23",
            "tolerancia_grados": tolerance,
        },
        "features": features_out,
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Provincias
    provincias_raw = fetch_wfs_geojson("ign:provincia")
    provincias_map: dict[str, str] = {}
    for f in provincias_raw.get("features", []):
        p = f.get("properties", {})
        in1 = str(p.get("in1", "")).zfill(2)
        nam = p.get("nam", "")
        if in1 and nam:
            provincias_map[in1] = nam

    def extract_prov_props(props: dict[str, Any]) -> dict[str, Any]:
        return {
            "nombre": props.get("nam", ""),
            "in1": str(props.get("in1", "")).zfill(2),
        }

    prov_simplified = simplify_geojson(
        provincias_raw,
        tolerance=TOLERANCIA_PROVINCIAS_DEG,
        decimals=COORD_DECIMALS,
        prop_extractor=extract_prov_props,
    )
    prov_file = OUTPUT_DIR / "provincias.geojson"
    with open(prov_file, "w", encoding="utf-8") as f:
        json.dump(prov_simplified, f, ensure_ascii=False, separators=(",", ":"))

    prov_size_kb = prov_file.stat().st_size / 1024
    print(f"Provincias guardado en {prov_file}: {prov_size_kb:.1f} KB ({len(prov_simplified['features'])} features)")

    # 2. Departamentos
    deptos_raw = fetch_wfs_geojson("ign:departamento")

    def extract_depto_props(props: dict[str, Any]) -> dict[str, Any]:
        in1 = str(props.get("in1", "")).zfill(5)
        prov_code = in1[:2]
        prov_name = provincias_map.get(prov_code, "")
        return {
            "nombre": props.get("nam", ""),
            "provincia": prov_name,
            "in1": in1,
        }

    deptos_simplified = simplify_geojson(
        deptos_raw,
        tolerance=TOLERANCIA_DEPARTAMENTOS_DEG,
        decimals=COORD_DECIMALS,
        prop_extractor=extract_depto_props,
    )
    depto_file = OUTPUT_DIR / "departamentos.geojson"
    with open(depto_file, "w", encoding="utf-8") as f:
        json.dump(deptos_simplified, f, ensure_ascii=False, separators=(",", ":"))

    depto_size_kb = depto_file.stat().st_size / 1024
    print(
        f"Departamentos guardado en {depto_file}: {depto_size_kb:.1f} KB ({len(deptos_simplified['features'])} features)"
    )

    total_kb = prov_size_kb + depto_size_kb
    print(f"TOTAL combinado: {total_kb:.1f} KB ({total_kb / 1024:.2f} MB)")
    if total_kb <= 1024:
        print(f"OBJETIVO CUMPLIDO: {total_kb:.1f} KB es menor que 1024 KB (1 MB)!")
    else:
        raise ValueError(f"Peso combinado {total_kb:.1f} KB supera el límite de 1024 KB (1 MB).")


if __name__ == "__main__":
    main()
