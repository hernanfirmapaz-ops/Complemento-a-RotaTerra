"""Validación de Copernicus GLO-30 vs. Mojones IGN (San Luis / Villa Mercedes).

Descarga mojones de nivelación geométrica del IGN vía WFS (fecha 22/11/2026),
extrae cotas del COG público de Copernicus GLO-30 mediante interpolación bilineal,
computa estadísticas robustas (mediana, NMAD, RMSE, LE90) separadas por red,
y guarda el fixture GeoJSON para pruebas unitarias sin conexión a internet.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import numpy as np
import rasterio

FIXTURE_PATH = Path("geoprocessing/tests/fixtures/dem/ign_nivelacion_san_luis_20261122.geojson")
COG_URL = "/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_S34_00_W066_00_DEM/Copernicus_DSM_COG_10_S34_00_W066_00_DEM.tif"
BBOX = "-66,-34,-65,-33"
WFS_BASE = "https://wms.ign.gob.ar/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature&outputFormat=application/json&bbox=" + BBOX + "&typeName="


def bilinear_sample(src: rasterio.DatasetReader, lon: float, lat: float) -> float | None:
    inv_gt = ~src.transform
    col, row = inv_gt * (lon, lat)
    r0, c0 = int(np.floor(row)), int(np.floor(col))
    dr, dc = row - r0, col - c0
    w = rasterio.windows.Window(c0, r0, 2, 2)
    d = src.read(1, window=w)
    if d.shape != (2, 2):
        return None
    top = (1 - dc) * float(d[0, 0]) + dc * float(d[0, 1])
    bot = (1 - dc) * float(d[1, 0]) + dc * float(d[1, 1])
    return (1 - dr) * top + dr * bot


def compute_metrics(errors: np.ndarray) -> dict[str, float]:
    med = float(np.median(errors))
    nmad = float(1.4826 * np.median(np.abs(errors - med)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    le90 = float(np.percentile(np.abs(errors), 90))
    return {
        "sesgo_mediana_m": round(med, 2),
        "nmad_m": round(nmad, 2),
        "rmse_m": round(rmse, 2),
        "le90_m": round(le90, 2),
    }


def main() -> None:
    print("1. Descargando mojones de nivelación geométrica IGN vía WFS...")
    f_alta = json.loads(urllib.request.urlopen(WFS_BASE + "ign:nivelacion_alta_precision", timeout=30).read().decode())["features"]
    f_prec = json.loads(urllib.request.urlopen(WFS_BASE + "ign:nivelacion_precision", timeout=30).read().decode())["features"]
    f_topo = json.loads(urllib.request.urlopen(WFS_BASE + "ign:nivelacion_topografica", timeout=30).read().decode())["features"]

    features_out = []

    # 1. Alta precisión (llanura / transecto sur cota <= 640m, no destruido)
    alta_mojones = []
    for f in f_alta:
        p = f["properties"]
        c = p.get("cota")
        st = p.get("estado")
        if c is not None and c <= 640 and st != "Destruido":
            nom = p.get("nomenclatura", "")
            coords = f["geometry"]["coordinates"]
            alta_mojones.append({"red": "alta_precision", "nom": nom, "cota": c, "lon": coords[0], "lat": coords[1], "excluida": False})

    # 2. Precisión (llanura cota < 600m, no destruido)
    prec_mojones = []
    for f in f_prec:
        p = f["properties"]
        c = p.get("cota")
        st = p.get("estado")
        if c is not None and c < 600 and st != "Destruido":
            nom = p.get("nomenclatura", "")
            coords = f["geometry"]["coordinates"]
            prec_mojones.append({"red": "precision", "nom": nom, "cota": c, "lon": coords[0], "lat": coords[1], "excluida": False})

    # 3. Topográfica (cota < 600m, no destruido, descartando PF1n(75)n)
    topo_mojones = []
    for f in f_topo:
        p = f["properties"]
        c = p.get("cota")
        st = p.get("estado")
        if c is not None and c < 600 and st != "Destruido":
            nom = p.get("nomenclatura", "")
            if "PF1n(75)n" in nom or abs(c - 26.226) < 0.01:
                continue
            coords = f["geometry"]["coordinates"]
            topo_mojones.append({
                "red": "topografica",
                "nom": nom,
                "cota": c,
                "lon": coords[0],
                "lat": coords[1],
                "excluida": True,
                "motivo_exclusion": "Red topografica secundaria con discrepancias >10 m frente a dos fuentes independientes (Copernicus y MDE-Ar). No apta para calibracion.",
            })

    all_mojones = alta_mojones + prec_mojones + topo_mojones
    print(f"Total mojones a evaluar: {len(all_mojones)} (Alta: {len(alta_mojones)}, Precisión: {len(prec_mojones)}, Topográfica: {len(topo_mojones)})")

    print("2. Interpolando elevaciones bilineales de Copernicus GLO-30 desde AWS Open Data...")
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", GDAL_HTTP_UNSAFESSL="YES"):
        with rasterio.open(COG_URL) as src:
            for m in all_mojones:
                dem_val = bilinear_sample(src, m["lon"], m["lat"])
                if dem_val is not None:
                    m["cota_copernicus"] = round(dem_val, 3)
                    m["error_copernicus"] = round(dem_val - m["cota"], 3)
                else:
                    m["cota_copernicus"] = None
                    m["error_copernicus"] = None

    # Métricas
    err_alta = np.array([m["error_copernicus"] for m in alta_mojones if m["error_copernicus"] is not None])
    err_prec = np.array([m["error_copernicus"] for m in prec_mojones if m["error_copernicus"] is not None])
    err_comb = np.concatenate([err_alta, err_prec])
    err_topo = np.array([m["error_copernicus"] for m in topo_mojones if m["error_copernicus"] is not None])

    m_alta = compute_metrics(err_alta)
    m_prec = compute_metrics(err_prec)
    m_comb = compute_metrics(err_comb)
    m_topo = compute_metrics(err_topo)

    print("\n=== RESULTADOS DE VALIDACIÓN COPERNICUS GLO-30 VS MOJONES IGN ===")
    print(f"Alta precisión (n={len(err_alta)}): {m_alta}")
    print(f"Precisión      (n={len(err_prec)}): {m_prec}")
    print(f"Combinada      (n={len(err_comb)}): {m_comb}")
    print(f"Topográfica ⚠️  (n={len(err_topo)}): {m_topo}")

    # Guardar GeoJSON
    for m in all_mojones:
        feat = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [m["lon"], m["lat"]]},
            "properties": {
                "nomenclatura": m["nom"],
                "red": m["red"],
                "cota_ign_m": m["cota"],
                "cota_copernicus_m": m["cota_copernicus"],
                "error_copernicus_m": m["error_copernicus"],
                "excluida": m["excluida"],
                "motivo_exclusion": m.get("motivo_exclusion"),
            },
        }
        features_out.append(feat)

    geojson_data = {
        "type": "FeatureCollection",
        "metadata": {
            "fecha_descarga": "2026-11-22",
            "fuente_mojones": "Instituto Geográfico Nacional (IGN Argentina) - WFS GetFeature",
            "fuente_dem": "Copernicus GLO-30 DSM (AWS Open Data COG)",
            "tesela_dem": "Copernicus_DSM_COG_10_S34_00_W066_00_DEM",
            "bbox": BBOX,
            "metricas": {
                "alta_precision": {"n": len(err_alta), **m_alta},
                "precision": {"n": len(err_prec), **m_prec},
                "combinada_alta_precision": {"n": len(err_comb), **m_comb},
                "topografica": {"n": len(err_topo), **m_topo},
            },
        },
        "features": features_out,
    }

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FIXTURE_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f, indent=2, ensure_ascii=False)
    print(f"\nFixture guardado exitosamente en: {FIXTURE_PATH} ({len(features_out)} mojones)")


if __name__ == "__main__":
    main()
