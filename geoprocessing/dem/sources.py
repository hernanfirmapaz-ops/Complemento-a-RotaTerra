"""Fuentes de DEM y sus metadatos obligatorios (SDD §5.2).

Toda fuente registra: nombre, URL, licencia, tipo de superficie (DTM/DSM), resolución nominal,
datum vertical, precisión vertical declarada y fecha/período de adquisición. Si un dato no se conoce
se guarda como None y se advierte: no se inventa.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import numpy as np

COPERNICUS_ID = "copernicus_glo30"
UPLOAD_ID = "upload"
OPENTOPOGRAPHY_COP30_ID = "opentopography_cop30"
OPENTOPOGRAPHY_NASADEM_ID = "opentopography_nasadem"

_COP_URL_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"  # AWS Open Data (archivos de la ESA tal cual)
_COP_INVALIDO = -32767
_ALTURA_MIN, _ALTURA_MAX = -500, 9000
_GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",  # no listar la carpeta del bucket al abrir el COG
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "3",
    "GDAL_HTTP_RETRY_DELAY": "2",
}


class DemSourceError(RuntimeError):
    """La fuente de DEM no respondió, no cubre el área o el archivo es ilegible."""


@dataclass
class DemSourceInfo:
    source_id: str
    source_name: str
    source_url: str | None
    license: str | None
    surface_type: str  # "DTM" (terreno desnudo), "DSM" (superficie), "desconocido"
    nominal_resolution_m: float | None
    vertical_datum: str | None
    vertical_accuracy_m: float | None
    vertical_accuracy_note: str | None
    acquisition_start: str | None
    acquisition_end: str | None
    acquisition_method: str | None
    vertical_nmad_local_m: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def copernicus_info(toma: tuple[date, date] | None) -> DemSourceInfo:
    return DemSourceInfo(
        source_id=COPERNICUS_ID,
        source_name="Copernicus DEM GLO-30 (ESA)",
        source_url="https://registry.opendata.aws/copernicus-dem/",
        license=("Copernicus DEM: uso libre con atribución. © DLR e.V. 2010-2014 y © Airbus Defence and Space "
                 "GmbH 2014-2018, provisto bajo COPERNICUS por la Unión Europea y la ESA."),
        surface_type="DSM",
        nominal_resolution_m=30.0,
        vertical_datum="EGM2008 (alturas ortométricas)",
        vertical_accuracy_m=4.0,
        vertical_accuracy_note="LE90 global < 4 m según ESA. Dispersión local NMAD ≈ 1,15 m en San Luis contra red IGN (Spec 014, tabla §1, n = 76, tesela S34 W066).",
        acquisition_start=toma[0].isoformat() if toma else None,
        acquisition_end=toma[1].isoformat() if toma else None,
        acquisition_method="Interferometría radar TanDEM-X",
        vertical_nmad_local_m=1.15,
    )


# ---------- Copernicus GLO-30: mosaicos de 1° × 1° ----------

def copernicus_tile(lat: float, lon: float) -> str:
    """Mosaico que contiene el punto, por su esquina suroeste: (-33.7, -65.3) -> 'S34_00_W066_00'."""
    sur, oeste = math.floor(lat), math.floor(lon)
    return f"{'N' if sur >= 0 else 'S'}{abs(sur):02d}_00_{'E' if oeste >= 0 else 'W'}{abs(oeste):03d}_00"


def copernicus_tiles(bbox: tuple[float, float, float, float]) -> list[str]:
    oeste, sur, este, norte = bbox
    return [copernicus_tile(lat + 0.5, lon + 0.5)
            for lat in range(math.floor(sur), math.floor(norte) + 1)
            for lon in range(math.floor(oeste), math.floor(este) + 1)]


def _carpeta(nombre: str) -> str:
    return f"Copernicus_DSM_COG_10_{nombre}_DEM"


def copernicus_tif_url(nombre: str) -> str:
    return f"{_COP_URL_BASE}/{_carpeta(nombre)}/{_carpeta(nombre)}.tif"


def copernicus_xml_url(nombre: str) -> str:
    return f"{_COP_URL_BASE}/{_carpeta(nombre)}/Copernicus_DSM_10_{nombre}.xml"


def parse_acquisition_period(xml: str) -> tuple[date, date] | None:
    """Primer y último día de toma TanDEM-X del mosaico según el XML de la ESA (None si no figura)."""
    fechas = []
    for etiqueta in ("tsxx_startTime", "tsxx_stopTime"):
        hallado = re.search(rf"<(?:\w+:)?{etiqueta}>\s*(\d{{4}}-\d{{2}}-\d{{2}})", xml)
        if hallado is None:
            return None
        fechas.append(date.fromisoformat(hallado.group(1)))
    return fechas[0], fechas[1]


def fetch_copernicus(bbox: tuple[float, float, float, float], destino: Path) -> DemSourceInfo:
    """Descarga solo la ventana necesaria de los COG de Copernicus y la guarda como GeoTIFF original.

    El archivo guardado conserva la grilla y el CRS del producto (EPSG:4326, 1 segundo de arco):
    es el "original" que nunca se modifica (SDD §6.2).
    """
    import httpx
    import rasterio
    from rasterio.errors import RasterioIOError
    from rasterio.merge import merge

    from geoprocessing.net import client, http_opener

    oeste, sur, este, norte = bbox
    periodos: list[tuple[date, date]] = []
    cliente = client()
    with rasterio.Env(**_GDAL_ENV):
        fuentes = []
        conexion_fallo = False
        try:
            for nombre in copernicus_tiles(bbox):
                try:
                    fuentes.append(rasterio.open(copernicus_tif_url(nombre), opener=http_opener))
                except (RasterioIOError, FileNotFoundError) as error:
                    err_str = str(error)
                    if any(s in err_str.lower() for s in ("connect", "network", "timeout", "offline", "unreachable")):
                        conexion_fallo = True
                        break
                    continue  # en el mar no hay mosaico
                except httpx.HTTPError as error:
                    raise DemSourceError("Sin conexión: no se pudo descargar el relieve") from error
                except Exception as error:
                    raise DemSourceError("Sin conexión: no se pudo descargar el relieve") from error
                try:
                    r = cliente.get(copernicus_xml_url(nombre))
                    if r.status_code == 200 and (p := parse_acquisition_period(r.text)):
                        periodos.append(p)
                except httpx.HTTPError:
                    pass  # sin XML no se inventa fecha: queda None
            if conexion_fallo or not fuentes:
                raise DemSourceError("Sin conexión: no se pudo descargar el relieve")
            rx = min(abs(f.transform.a) for f in fuentes)
            ry = min(abs(f.transform.e) for f in fuentes)
            x0, y0 = fuentes[0].transform.c, fuentes[0].transform.f
            limites = (x0 + (math.floor((oeste - x0) / rx) - 1) * rx,
                       y0 - (math.ceil((y0 - sur) / ry) + 1) * ry,
                       x0 + (math.ceil((este - x0) / rx) + 1) * rx,
                       y0 - (math.floor((y0 - norte) / ry) - 1) * ry)
            datos, transformada = merge(fuentes, bounds=limites, res=(rx, ry), nodata=np.nan, dtype="float32")
            crs = fuentes[0].crs
        except RasterioIOError as error:
            raise DemSourceError(f"No se pudo leer Copernicus GLO-30: {error}") from error
        finally:
            for f in fuentes:
                f.close()

    alturas = datos[0]
    alturas[(alturas == _COP_INVALIDO) | (alturas < _ALTURA_MIN) | (alturas > _ALTURA_MAX)] = np.nan
    destino.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(destino, "w", driver="GTiff", height=alturas.shape[0], width=alturas.shape[1], count=1,
                       dtype="float32", crs=crs, transform=transformada, nodata=np.nan, compress="deflate") as dst:
        dst.write(alturas, 1)
        dst.update_tags(SOURCE="Copernicus DEM GLO-30", SOURCE_URL=_COP_URL_BASE)

    toma = (min(p[0] for p in periodos), max(p[1] for p in periodos)) if periodos else None
    return copernicus_info(toma)


# ---------- OpenTopography: Copernicus GLO-30 / NASADEM ----------

def opentopography_info(demtype: str = "COP30") -> DemSourceInfo:
    dem_u = demtype.upper()
    if dem_u == "NASADEM":
        return DemSourceInfo(
            source_id=OPENTOPOGRAPHY_NASADEM_ID,
            source_name="NASADEM Merged DEM Global 1 arcsecond (NASA / OpenTopography)",
            source_url="https://doi.org/10.5069/G93T9FD9",
            license="Dominio público (NASA / USGS). Accedido vía OpenTopography.",
            surface_type="DSM",
            nominal_resolution_m=30.0,
            vertical_datum="EGM96",
            vertical_accuracy_m=5.0,
            vertical_accuracy_note="Precisión vertical absoluta estimada ~5 m en llanura.",
            acquisition_start="2000-02-11",
            acquisition_end="2000-02-22",
            acquisition_method="SRTM re-procesado con ALOS PRISM y GDEM",
        )
    return DemSourceInfo(
        source_id=OPENTOPOGRAPHY_COP30_ID,
        source_name="Copernicus DEM GLO-30 (OpenTopography)",
        source_url="https://doi.org/10.5069/G9028PQB",
        license="Copernicus DEM: uso libre con atribución (ESA). Accedido vía OpenTopography.",
        surface_type="DSM",
        nominal_resolution_m=30.0,
        vertical_datum="EGM2008 (alturas ortométricas)",
        vertical_accuracy_m=4.0,
        vertical_accuracy_note="LE90 global < 4 m (ESA). Precisión vertical empírica ±1,15 m (NMAD) en San Luis contra red IGN (Spec 014, tabla §1, n = 76, tesela S34 W066).",
        acquisition_start="2010-12-12",
        acquisition_end="2015-01-16",
        acquisition_method="Interferometría radar TanDEM-X",
        vertical_nmad_local_m=1.15,
    )


def fetch_opentopography(
    bbox: tuple[float, float, float, float],
    destino: Path,
    demtype: str = "COP30",
    api_key: str | None = None,
) -> DemSourceInfo:
    """Descarga el DEM desde la API Global de OpenTopography recortado al bbox."""
    import os

    import httpx
    import rasterio

    from geoprocessing.net import client

    key = api_key or os.environ.get("OPENTOPOGRAPHY_API_KEY")
    if not key:
        raise DemSourceError("Se requiere una API key de OpenTopography (OPENTOPOGRAPHY_API_KEY).")

    oeste, sur, este, norte = bbox
    url = "https://portal.opentopography.org/API/globaldem"
    params = {
        "demtype": demtype,
        "south": f"{sur:.6f}",
        "north": f"{norte:.6f}",
        "west": f"{oeste:.6f}",
        "east": f"{este:.6f}",
        "outputFormat": "GTiff",
        "API_Key": key,
    }

    try:
        with client(timeout=60.0) as cl:
            r = cl.get(url, params=params)
            if r.status_code != 200:
                raise DemSourceError(
                    f"OpenTopography respondió HTTP {r.status_code}: {r.text[:200]}"
                )
            content = r.content
    except httpx.HTTPError as err:
        raise DemSourceError(f"Error de conexión con OpenTopography: {err}") from err

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(content)

    try:
        with rasterio.open(destino) as src:
            if src.count < 1 or src.crs is None:
                raise DemSourceError("El archivo recibido de OpenTopography no es un ráster georreferenciado válido.")
    except Exception as err:
        raise DemSourceError(f"No se pudo leer el DEM de OpenTopography: {err}") from err

    return opentopography_info(demtype)


# ---------- GeoTIFF subido por el usuario ----------

def inspect_upload(ruta: Path) -> dict:
    """Abre el GeoTIFF subido y verifica que sea un ráster georreferenciado de una banda."""
    import rasterio
    from rasterio.errors import RasterioIOError

    try:
        with rasterio.open(ruta) as src:
            if src.crs is None:
                raise DemSourceError("El GeoTIFF no tiene sistema de referencia (CRS): no se puede georreferenciar.")
            if src.count < 1:
                raise DemSourceError("El ráster no tiene bandas.")
            if src.driver not in ("GTiff", "COG"):
                raise DemSourceError(f"Formato {src.driver} no admitido: subí un GeoTIFF.")
            unidad = src.crs.linear_units if not src.crs.is_geographic else "grados"
            return {"crs": src.crs.to_string(), "width": src.width, "height": src.height,
                    "res": src.res, "nodata": src.nodata, "units": unidad, "bands": src.count}
    except RasterioIOError as error:
        raise DemSourceError(f"El archivo no es un GeoTIFF legible: {error}") from error


def upload_info(meta: dict, res_m: float | None) -> DemSourceInfo:
    """Metadatos declarados por el usuario para un DEM propio (dron, LiDAR, IGN 5 m, etc.)."""
    def _num(v):
        try:
            return float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None

    surface = (meta.get("surface_type") or "desconocido").upper()
    return DemSourceInfo(
        source_id=UPLOAD_ID,
        source_name=meta.get("source_name") or "DEM subido por el usuario",
        source_url=meta.get("source_url") or None,
        license=meta.get("license") or None,
        surface_type=surface if surface in ("DTM", "DSM") else "desconocido",
        nominal_resolution_m=res_m,
        vertical_datum=meta.get("vertical_datum") or None,
        vertical_accuracy_m=_num(meta.get("vertical_accuracy_m")),
        vertical_accuracy_note="Declarada por el usuario." if _num(meta.get("vertical_accuracy_m")) else None,
        acquisition_start=meta.get("acquisition_date") or None,
        acquisition_end=meta.get("acquisition_date") or None,
        acquisition_method=meta.get("acquisition_method") or None,
    )
