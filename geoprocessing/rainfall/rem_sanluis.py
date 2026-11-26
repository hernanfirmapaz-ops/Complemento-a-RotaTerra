"""Conector con la Red de Estaciones Meteorológicas de San Luis (REM).

Permite consultar la lista oficial de estaciones de la provincia de San Luis (Universidad
de La Punta · clima.sanluis.gob.ar), encontrar la estación más cercana al lote, descargar
y parsear series diarias en formato CSV (Windows-1252) y calcular la precipitación acumulada
de los 5 días previos para determinar la condición de humedad antecedente (AMC) en lugar
de la estimación satelital/reanálisis regional (~55 km).

Cumple con las reglas de integridad de datos (R2, R4) e Issue #23.
"""

from __future__ import annotations

import csv
import io
import math
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from geoprocessing.satellite.nasa_power_imerg import determine_nrcs_amc
from geoprocessing.supuestos import SUPUESTO_REM_DISTANCIA_MAX_KM

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CACHE_DIR = DATA_DIR / "cache" / "rem_sanluis"
REM_STATIONS_FILE = DATA_DIR / "rem_estaciones.json"

BASE_URL_CSV = "https://clima.sanluis.gob.ar/ObtenerCsv.aspx"

# Catálogo de 14 estaciones meteorológicas de la Red de Estaciones Meteorológicas (REM) de San Luis.
# Fuente oficial: Red de Estaciones Meteorológicas (REM), Universidad de La Punta (ULP), Gobierno de San Luis.
# URL oficial: https://clima.sanluis.gob.ar/Index.aspx
# Fecha de consulta: 2026-11-23.
#
# Nota de verificación:
# - Coordenadas (latitud y longitud): verificadas en el mapa del portal oficial de la REM (https://clima.sanluis.gob.ar/Index.aspx).
# - Cotas de elevación (elevation_m): no se encuentran publicadas explícitamente en el portal web de la REM;
#   se registran como None (a verificar) para evitar datos inventados (Regla 2).
REM_STATIONS: list[dict[str, Any]] = [
    {
        "id": 42,
        "name": "Villa Mercedes",
        "latitude": -33.6786,
        "longitude": -65.5046,
        "elevation_m": None,  # a verificar (no publicado en Index.aspx)
        "operator": "REM - Universidad de La Punta",
    },
    {
        "id": 60,
        "name": "Villa Reynolds",
        "latitude": -33.7255,
        "longitude": -65.3858,
        "elevation_m": None,  # a verificar (no publicado en Index.aspx)
        "operator": "REM - Universidad de La Punta",
    },
    {
        "id": 47,
        "name": "El Trapiche",
        "latitude": -33.1086,
        "longitude": -66.0647,
        "elevation_m": None,  # a verificar (no publicado en Index.aspx)
        "operator": "REM - Universidad de La Punta",
    },
    {
        "id": 13,
        "name": "Justo Daract",
        "latitude": -33.8569,
        "longitude": -65.1822,
        "elevation_m": None,  # a verificar (no publicado en Index.aspx)
        "operator": "REM - Universidad de La Punta",
    },
    {
        "id": 58,
        "name": "Aeropuerto San Luis",
        "latitude": -33.2722,
        "longitude": -66.3578,
        "elevation_m": None,  # a verificar (no publicado en Index.aspx)
        "operator": "REM - Universidad de La Punta",
    },
    {
        "id": 34,
        "name": "La Toma",
        "latitude": -33.0531,
        "longitude": -65.6236,
        "elevation_m": None,  # a verificar (no publicado en Index.aspx)
        "operator": "REM - Universidad de La Punta",
    },
    {
        "id": 25,
        "name": "Merlo",
        "latitude": -32.3425,
        "longitude": -65.0131,
        "elevation_m": None,  # a verificar (no publicado en Index.aspx)
        "operator": "REM - Universidad de La Punta",
    },
    {
        "id": 18,
        "name": "Buena Esperanza",
        "latitude": -34.7572,
        "longitude": -65.2536,
        "elevation_m": None,  # a verificar (no publicado en Index.aspx)
        "operator": "REM - Universidad de La Punta",
    },
    {
        "id": 61,
        "name": "Unión",
        "latitude": -35.1539,
        "longitude": -65.9458,
        "elevation_m": None,  # a verificar (no publicado en Index.aspx)
        "operator": "REM - Universidad de La Punta",
    },
    {
        "id": 72,
        "name": "Fraga",
        "latitude": -33.4933,
        "longitude": -65.7906,
        "elevation_m": None,  # a verificar (no publicado en Index.aspx)
        "operator": "REM - Universidad de La Punta",
    },
    {
        "id": 31,
        "name": "Concarán",
        "latitude": -32.5614,
        "longitude": -65.2428,
        "elevation_m": None,  # a verificar (no publicado en Index.aspx)
        "operator": "REM - Universidad de La Punta",
    },
    {
        "id": 67,
        "name": "Tilisarao",
        "latitude": -32.7333,
        "longitude": -65.2917,
        "elevation_m": None,  # a verificar (no publicado en Index.aspx)
        "operator": "REM - Universidad de La Punta",
    },
    {
        "id": 54,
        "name": "Quines",
        "latitude": -32.2333,
        "longitude": -65.8000,
        "elevation_m": None,  # a verificar (no publicado en Index.aspx)
        "operator": "REM - Universidad de La Punta",
    },
    {
        "id": 49,
        "name": "Nogolí",
        "latitude": -32.9167,
        "longitude": -66.3167,
        "elevation_m": None,  # a verificar (no publicado en Index.aspx)
        "operator": "REM - Universidad de La Punta",
    },
]


def haversine_distance_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calcula la distancia geodésica en kilómetros entre dos coordenadas WGS84."""
    rad = math.pi / 180.0
    dlat = (lat2 - lat1) * rad
    dlon = (lon2 - lon1) * rad
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return 6371.0 * c


def load_rem_stations() -> list[dict[str, Any]]:
    """Carga el catálogo de estaciones REM locales o recurre al catálogo maestro verificado."""
    if REM_STATIONS_FILE.exists():
        try:
            with open(REM_STATIONS_FILE, encoding="utf-8") as f:
                import json

                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            pass
    return REM_STATIONS


def find_nearest_rem_station(lon: float, lat: float) -> dict[str, Any]:
    """Encuentra la estación REM más cercana a las coordenadas dadas del lote."""
    stations = load_rem_stations()
    best_station = stations[0]
    best_dist = float("inf")

    for s in stations:
        d = haversine_distance_km(lon, lat, float(s["longitude"]), float(s["latitude"]))
        if d < best_dist:
            best_dist = d
            best_station = s

    out = dict(best_station)
    dist_km = round(best_dist, 1)
    out["distance_km"] = dist_km
    out["in_range"] = dist_km <= float(SUPUESTO_REM_DISTANCIA_MAX_KM.valor)
    out["label"] = f"REM {best_station['name']} ({dist_km} km)"
    out["source_citation"] = "Red de Estaciones Meteorológicas – Universidad de La Punta, Gobierno de San Luis"
    return out


def _parse_rem_date(date_str: str) -> str | None:
    """Parsea fechas en formato MM/DD/YYYY HH:MM:SS o YYYY-MM-DD y retorna YYYY-MM-DD."""
    cleaned = date_str.strip().strip('"')
    if not cleaned:
        return None
    # Intento 1: MM/DD/YYYY HH:MM:SS o MM/DD/YYYY
    parts = cleaned.split(" ")[0].split("/")
    if len(parts) == 3:
        try:
            m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{y:04d}-{m:02d}-{d:02d}"
        except ValueError:
            pass
    # Intento 2: YYYY-MM-DD
    parts_iso = cleaned.split(" ")[0].split("-")
    if len(parts_iso) == 3:
        try:
            y, m, d = int(parts_iso[0]), int(parts_iso[1]), int(parts_iso[2])
            return f"{y:04d}-{m:02d}-{d:02d}"
        except ValueError:
            pass
    return None


def parse_rem_csv(content: bytes | str) -> list[dict[str, Any]]:
    """Parsea el contenido CSV exportado por clima.sanluis.gob.ar (Windows-1252 / cp1252).

    Retorna una lista de diccionarios con claves:
    - 'date': str (YYYY-MM-DD)
    - 'precipitation_mm': float | None
    - 'temp_max_c': float | None
    - 'temp_min_c': float | None
    - 'temp_mean_c': float | None
    """
    if isinstance(content, bytes):
        try:
            text = content.decode("cp1252")
        except UnicodeDecodeError:
            text = content.decode("cp1252", errors="replace")
    else:
        text = content

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []

    # Identificar índices de columnas
    header = [h.strip().strip('"').lower() for h in rows[0]]
    idx_fecha = -1
    idx_pp = -1
    idx_tmax = -1
    idx_tmin = -1
    idx_tmed = -1

    for i, col in enumerate(header):
        if "fecha" in col:
            idx_fecha = i
        elif "precip" in col or "lluvia" in col:
            idx_pp = i
        elif "max" in col:
            idx_tmax = i
        elif "min" in col:
            idx_tmin = i
        elif "med" in col:
            idx_tmed = i

    if idx_fecha == -1:
        return []

    records: list[dict[str, Any]] = []
    for row in rows[1:]:
        if not row or len(row) <= idx_fecha:
            continue
        d_str = _parse_rem_date(row[idx_fecha])
        if not d_str:
            continue

        def _to_float(idx: int) -> float | None:
            if idx == -1 or idx >= len(row):
                return None
            val = row[idx].strip().strip('"').replace(",", ".")
            if not val or val == "-" or val.lower() == "s/d" or val.lower() == "null":
                return None
            try:
                return float(val)
            except ValueError:
                return None

        records.append({
            "date": d_str,
            "precipitation_mm": _to_float(idx_pp),
            "temp_max_c": _to_float(idx_tmax),
            "temp_min_c": _to_float(idx_tmin),
            "temp_mean_c": _to_float(idx_tmed),
        })

    # Ordenar por fecha cronológica ascendente
    records.sort(key=lambda x: x["date"])
    return records


def fetch_rem_daily_series(
    station_id: int | str,
    start_date: str,
    end_date: str,
    cache_dir: Path | None = None,
    timeout_sec: int = 15,
) -> list[dict[str, Any]]:
    """Descarga o recupera desde caché la serie diaria de una estación REM para un rango de fechas.

    Formatos de fecha aceptados: YYYY-MM-DD o AAAAMMDD.
    """
    cdir = cache_dir or CACHE_DIR
    cdir.mkdir(parents=True, exist_ok=True)

    # Normalizar a AAAAMMDD para la URL del endpoint ASP.NET
    s_clean = start_date.replace("-", "")
    e_clean = end_date.replace("-", "")
    cache_file = cdir / f"rem_{station_id}_{s_clean}_{e_clean}.csv"

    if cache_file.exists():
        try:
            return parse_rem_csv(cache_file.read_bytes())
        except Exception:
            pass

    # Consulta HTTP
    url = f"{BASE_URL_CSV}?tipo=Mensual&estacion={station_id}&fechaDesde={s_clean}&fechahasta={e_clean}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "RotaTerra-Agro/1.0 (Contacto agrometeorologico)",
                "Accept": "text/csv, application/csv",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            content = resp.read()
            cache_file.write_bytes(content)
            return parse_rem_csv(content)
    except (urllib.error.URLError, TimeoutError, OSError):
        return []


def get_rem_antecedent_rainfall_5d(
    station_id: int | str,
    target_date_str: str,
    latitude_deg: float | None = None,
    records: list[dict[str, Any]] | None = None,
    cache_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Calcula la precipitación acumulada de los 5 días estrictamente previos a target_date.

    Determina la condición de humedad antecedente (AMC) mediante determine_nrcs_amc()
    según USDA-SCS NEH-4 Tabla 4.2 diferenciando estación de reposo y crecimiento según
    el mes calendario y la latitud (hemisferio).

    Si falta el dato de alguno de los 5 días previos o la serie no está disponible,
    retorna None cumpliendo estrictamente la regla de integridad de datos (sin valores inventados).
    """
    try:
        target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    except ValueError:
        return None

    # Determinar los 5 días previos: [d-5, d-4, d-3, d-2, d-1]
    prior_days = [(target_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 6)]
    min_date = prior_days[-1]
    max_date = prior_days[0]

    if records is None:
        records = fetch_rem_daily_series(
            station_id=station_id,
            start_date=min_date,
            end_date=max_date,
            cache_dir=cache_dir,
        )

    if not records:
        return None

    by_date = {r["date"]: r["precipitation_mm"] for r in records}

    total_5d = 0.0
    for day in prior_days:
        pp = by_date.get(day)
        if pp is None:
            # Falta dato en al menos uno de los 5 días previos
            return None
        total_5d += pp

    if latitude_deg is not None:
        lat = float(latitude_deg)
    else:
        stations = load_rem_stations()
        st_match = next((s for s in stations if str(s.get("id")) == str(station_id)), None)
        if st_match is not None and st_match.get("latitude") is not None:
            lat = float(st_match["latitude"])
        else:
            # Sin latitud verificada no se puede clasificar la condición agronómica (reposo vs crecimiento).
            # No inventar valores por omisión -> retorna None para degradar limpiamente a reanálisis regional.
            return None

    amc = determine_nrcs_amc(
        prior_5d_mm=total_5d,
        month=target_dt.month,
        latitude_deg=lat,
    )
    return {
        "station_id": int(station_id),
        "target_date": target_date_str,
        "prior_5d_mm": round(total_5d, 1),
        "antecedent_moisture_amc": amc,
        "days_evaluated": prior_days,
        "quality_flag": "medicion_estacion_rem_oficial",
    }


def fit_gumbel_moments(
    annual_maxima_mm: list[float],
    return_periods: list[int] | None = None,
) -> dict[str, float]:
    """Ajusta una distribución de Gumbel (Tipo I / EV1) por el Método de Momentos (Gumbel 1958).

    Dada una serie de máximos diarios anuales de precipitación en milímetros:
    - Media muestral: x_bar = sum(x) / N
    - Desviación estándar muestral (con N - 1 grados de libertad): s = sqrt(sum((x - x_bar)^2) / (N - 1))
    - Parámetro de escala beta = (sqrt(6) / pi) * s
    - Constante de Euler-Mascheroni gamma = 0.5772156649
    - Parámetro de posición mu = x_bar - gamma * beta
    - Para un período de retorno T (años):
        Probabilidad de no excedencia: p = 1 - 1/T
        Variable reducida: y_T = -ln(-ln(p))
        Magnitud estimada: x_T = mu + beta * y_T

    Retorna un diccionario con claves como 'T2', 'T10', 'T25', 'T50' redondeadas a 1 decimal.
    """
    if return_periods is None:
        return_periods = [2, 10, 25, 50]

    valid = [float(x) for x in annual_maxima_mm if x is not None and not math.isnan(x) and x > 0]
    n = len(valid)
    if n < 5:
        raise ValueError(f"Se requieren al menos 5 años de datos para ajuste Gumbel, se recibieron {n}.")

    mean = sum(valid) / n
    variance = sum((x - mean) ** 2 for x in valid) / (n - 1)
    std = math.sqrt(variance)

    euler_gamma = 0.5772156649015329
    beta = (math.sqrt(6.0) / math.pi) * std
    mu = mean - euler_gamma * beta

    out: dict[str, float] = {}
    for t in return_periods:
        if t <= 1:
            continue
        p = 1.0 - 1.0 / t
        y_t = -math.log(-math.log(p))
        x_t = mu + beta * y_t
        out[f"T{t}"] = round(x_t, 1)

    return out


def load_rem_annual_maxima_station(station_id: int | str) -> list[dict[str, Any]] | None:
    """Carga los máximos diarios anuales de precipitación para una estación REM.

    Actualmente solo la estación 42 (Villa Mercedes) cuenta con la serie histórica
    empírica (2008-2025) verificada y descargada.
    Para otras estaciones retorna None (sin datos inventados).
    """
    st_id = str(station_id).strip()
    candidates = [
        Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "rainfall" / f"rem_maximos_anuales_villa_mercedes_estacion{st_id}.csv",
        DATA_DIR / "rem_sanluis" / f"rem_maximos_anuales_estacion{st_id}.csv",
        DATA_DIR / "cache" / "rem_sanluis" / f"rem_maximos_anuales_estacion{st_id}.csv",
    ]
    target_path = None
    for c in candidates:
        if c.exists():
            target_path = c
            break

    if target_path is None:
        return None

    try:
        content = target_path.read_bytes().decode("cp1252")
    except Exception:
        return None

    rows = []
    reader = csv.reader(io.StringIO(content))
    for r in reader:
        if not r or r[0].startswith("#") or "anio" in r[0].lower() or "año" in r[0].lower():
            continue
        try:
            anio = int(r[0].strip())
            fecha = r[1].strip() if len(r) > 1 else ""
            pp = float(r[2].strip().replace(",", ".")) if len(r) > 2 else float(r[1].strip().replace(",", "."))
            rows.append({"anio": anio, "fecha": fecha, "precipitacion_mm": pp})
        except (ValueError, IndexError):
            continue

    return rows if rows else None


def get_rem_return_periods_for_station(
    station_id: int | str,
    distance_km: float = 0.0,
) -> dict[str, Any] | None:
    """Calcula las recurrencias T2..T50 para una estación REM si posee serie histórica observada.

    Si no se dispone de la serie histórica empírica de la estación, retorna None ("sin datos").
    """
    rows = load_rem_annual_maxima_station(station_id)
    if not rows:
        return None

    stations = load_rem_stations()
    st_match = next((s for s in stations if str(s.get("id")) == str(station_id)), None)
    st_name = st_match["name"] if st_match else f"Estación {station_id}"

    series_pp = [r["precipitacion_mm"] for r in rows]
    milimetros = fit_gumbel_moments(series_pp, return_periods=[2, 10, 25, 50])

    return {
        "station_id": int(station_id),
        "station_name": st_name,
        "distance_km": round(distance_km, 1),
        "method": "Gumbel (Método de Momentos)",
        "milimetros": milimetros,
        "source_citation": (
            f"Red de Estaciones Meteorológicas (REM) – Universidad de La Punta. "
            f"Ajuste Gumbel sobre serie observada de {len(series_pp)} años ({rows[0]['anio']}–{rows[-1]['anio']}). "
            f"Descarga oficial: 2026-11-25."
        ),
    }


def get_rem_return_periods(lon: float, lat: float) -> dict[str, Any] | None:
    """Determina los períodos de retorno REM para las coordenadas del lote si hay estación cercana con serie observada.

    Si la estación más cercana no está en rango (< 40 km) o no posee serie anual descargada, retorna None.
    """
    nearest = find_nearest_rem_station(lon, lat)
    if not nearest.get("in_range"):
        return None

    st_id = nearest["id"]
    return get_rem_return_periods_for_station(st_id, distance_km=nearest["distance_km"])

