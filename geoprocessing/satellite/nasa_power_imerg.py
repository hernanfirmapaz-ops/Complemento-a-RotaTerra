"""Herramientas 2, 3, 7 y 8: Balance hídrico mensual, Riesgo de anegamiento con lluvia real,
Riesgo de heladas (NASA POWER) y Monitor de vigor NDVI (Sentinel-2 L2A STAC COG / correlación topográfica).
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Literal

import numpy as np

from geoprocessing.dem.terrain import Dem
from geoprocessing.net import client
from geoprocessing.rainfall.nrcs_cn import (
    AntecedentMoisture,
    SoilGroup,
    compute_nrcs_cn,
    lookup_cn_ii,
)
from geoprocessing.supuestos import (
    SUPUESTO_AMC_CRECIMIENTO_HUMEDO_MM,
    SUPUESTO_AMC_CRECIMIENTO_SECO_MM,
    SUPUESTO_AMC_REPOSO_HUMEDO_MM,
    SUPUESTO_AMC_REPOSO_SECO_MM,
    SUPUESTO_FAO56_KC_BARBECHO,
    SUPUESTO_MESES_ESTACION_REPOSO_NORTE,
    SUPUESTO_MESES_ESTACION_REPOSO_SUR,
    SUPUESTO_NDVI_UMBRAL_ALTO_VIGOR,
    SUPUESTO_NDVI_UMBRAL_BAJO_VIGOR,
)

NASA_POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
EARTH_SEARCH_STAC_URL = "https://earth-search.aws.element84.com/v1/search"

# Capacidad de Agua Útil máxima (AU_max, mm en el primer metro de perfil) según Grupo Hidrológico
AVAILABLE_WATER_CAPACITY_MM: dict[str, float] = {
    "A": 90.0,
    "B": 170.0,
    "C": 145.0,
    "D": 115.0,
}

MONTH_NAMES_ES = (
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
)


def fetch_nasa_power_daily_series(
    lon: float,
    lat: float,
    years: int = 3,
) -> tuple[list[dict], str, list[str]]:
    """Consulta la serie diaria de NASA POWER (`PRECTOTCORR`, `T2M_MIN`, `T2M_MAX`, `T2M`) para el lote.

    Si la API de la NASA responde en tiempo real, devuelve los datos satelitales observados/reanálisis
    MERRA-2 (`source = "NASA POWER (MERRA-2 / GEOS, 0.5°)"`).
    Si no hay conexión o la respuesta es insuficiente, no inventa datos: devuelve la serie vacía
    con el motivo, y el llamador informa el dato como descartado.
    """
    end_dt = date.today()
    start_dt = date(end_dt.year - max(1, years) + 1, 1, 1)

    try:
        r = client().get(
            NASA_POWER_DAILY_URL,
            params={
                "parameters": "PRECTOTCORR,T2M_MIN,T2M_MAX,T2M",
                "community": "AG",
                "longitude": round(float(lon), 4),
                "latitude": round(float(lat), 4),
                "start": start_dt.strftime("%Y%m%d"),
                "end": end_dt.strftime("%Y%m%d"),
                "format": "JSON",
            },
            timeout=15.0,
        )
        r.raise_for_status()
        payload = r.json()
        param = payload["properties"]["parameter"]
        p_dict = param["PRECTOTCORR"]
        tmin_dict = param["T2M_MIN"]
        tmax_dict = param["T2M_MAX"]
        tmean_dict = param["T2M"]

        rows: list[dict] = []
        for day_str in sorted(p_dict.keys()):
            p_val = float(p_dict[day_str])
            tmin = float(tmin_dict.get(day_str, -999))
            tmax = float(tmax_dict.get(day_str, -999))
            tmean = float(tmean_dict.get(day_str, -999))
            if p_val < 0 or tmin < -90 or tmax < -90:
                continue
            rows.append({
                "date": f"{day_str[:4]}-{day_str[4:6]}-{day_str[6:8]}",
                "year": int(day_str[:4]),
                "month": int(day_str[4:6]),
                "day_of_year": datetime.strptime(day_str, "%Y%m%d").timetuple().tm_yday,
                "precip_mm": round(p_val, 2),
                "tmin_c": round(tmin, 2),
                "tmax_c": round(tmax, 2),
                "tmean_c": round(tmean if tmean > -90 else 0.5 * (tmin + tmax), 2),
            })
        if len(rows) >= 300:
            return (
                rows,
                "NASA POWER Agroclimatology Archive (MERRA-2 / GPCP · 0.5°)",
                [
                    "Serie diaria descargada de NASA POWER para las coordenadas del lote. "
                    "Resolución espacial ~0,5°: representa la grilla regional, no un pluviómetro de parcela."
                ],
            )
    except Exception:
        pass

    # No se fabrican datos sintéticos en caso de fallo o ausencia de conexión (Anomalía A1).
    return (
        [],
        "NASA POWER (No disponible - sin conexión)",
        [
            "No se pudo descargar la serie climática de NASA POWER. Calidad: descartada por falta de conectividad o datos válidos."
        ],
    )


# ==============================================================================
# 1. Radiación Solar Extraterrestre y Evapotranspiración según FAO-56
# ==============================================================================

def compute_extraterrestrial_radiation_ra(
    latitude_deg: float,
    day_of_year: int,
    return_mj: bool = False,
) -> float | tuple[float, float]:
    """Calcula la radiación solar extraterrestre diaria Ra en equivalente de evaporación [mm/día]

    según FAO Irrigation and Drainage Paper No. 56 (Allen et al. 1998, Capítulo 3, Ecuaciones 21 a 28, págs. 45-47).

    Parámetros:
    - latitude_deg: latitud en grados decimales (negativa para hemisferio sur, ej. -33.3 para San Luis).
    - day_of_year: día juliano del año J (1 a 365 o 366).
    - return_mj: si True, devuelve una tupla (ra_mm_day, ra_mj_m2_day).

    Verificación de referencia:
    - Ejemplo 8 resuelto de FAO-56 (pág. 47): para latitud 20° Sur (-20.0°) y 3 de septiembre (J = 246),
      dr = 0.985, delta = 0.120 rad, omega_s = 1.527 rad, Ra = 32.2 MJ/(m²·día), Ra = 13.1 mm/día.
    """
    phi = math.radians(float(latitude_deg))
    j = int(day_of_year)

    # Distancia relativa inversa Tierra-Sol (dr, FAO-56 Eq. 23, pág. 46)
    dr = 1.0 + 0.033 * math.cos(2.0 * math.pi * j / 365.0)

    # Declinación solar (delta, FAO-56 Eq. 24, pág. 46)
    delta = 0.409 * math.sin((2.0 * math.pi * j / 365.0) - 1.39)

    # Ángulo horario de puesta del sol (omega_s, FAO-56 Eq. 25, pág. 46)
    tan_val = -math.tan(phi) * math.tan(delta)
    if tan_val >= 1.0:
        omega_s = 0.0  # Noche polar
    elif tan_val <= -1.0:
        omega_s = math.pi  # Día polar
    else:
        omega_s = math.acos(tan_val)

    # Constante solar Gsc = 0.0820 MJ / (m^2 * min)
    # Factor (24 * 60 / pi) * Gsc = 37.586 MJ / (m^2 * día) (FAO-56 Eq. 21, pág. 45)
    ra_mj = (
        (24.0 * 60.0 / math.pi)
        * 0.0820
        * dr
        * (omega_s * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(omega_s))
    )
    ra_mj_val = max(0.0, float(ra_mj))

    # Conversión a mm/día (FAO-56 Eq. 20, pág. 45: 1 MJ/(m²·día) = 0.408 mm/día)
    ra_mm_val = 0.408 * ra_mj_val

    if return_mj:
        return round(ra_mm_val, 2), round(ra_mj_val, 2)
    return round(ra_mm_val, 2)


def compute_hargreaves_et0_daily(
    tmean_c: float,
    tmax_c: float,
    tmin_c: float,
    ra_mm_day: float,
) -> float:
    """Calcula la evapotranspiración de referencia diaria ET0 [mm/día] según la

    fórmula de radiación de Hargreaves (FAO-56 Ecuación 52, pág. 64; Hargreaves y Samani 1985):
        ET0 = 0.0023 * (Tmean + 17.8) * (Tmax - Tmin)^0.5 * Ra
    donde Ra se expresa en evaporación equivalente [mm/día].
    """
    dt = max(0.0, float(tmax_c - tmin_c))
    t_mean = float(tmean_c)
    ra = max(0.0, float(ra_mm_day))
    et0 = 0.0023 * (t_mean + 17.8) * math.sqrt(dt) * ra
    return round(max(0.0, float(et0)), 3)


# ==============================================================================
# 2. Coeficientes de Cultivo Kc según FAO-56 (Tabla 12, págs. 110–114)
# ==============================================================================

# Coeficientes Kc por etapa fenológica: inicial (kc_ini), media/floración (kc_mid), final (kc_end)
FAO56_CROP_KC_TABLE: dict[str, dict[str, float]] = {
    "soja": {"kc_ini": 0.40, "kc_mid": 1.15, "kc_end": 0.50},
    "maiz": {"kc_ini": 0.30, "kc_mid": 1.20, "kc_end": 0.60},
    "trigo": {"kc_ini": 0.30, "kc_mid": 1.15, "kc_end": 0.30},
    "cebada": {"kc_ini": 0.30, "kc_mid": 1.15, "kc_end": 0.25},
    "girasol": {"kc_ini": 0.35, "kc_mid": 1.15, "kc_end": 0.35},
    "pastura": {"kc_ini": 0.40, "kc_mid": 1.00, "kc_end": 0.85},
    "barbecho": {"kc_ini": 0.25, "kc_mid": 0.25, "kc_end": 0.25},
}


def get_crop_kc_fao56(crop: str, stage: Literal["ini", "mid", "end"] = "mid") -> float:
    """Devuelve el coeficiente de cultivo Kc de FAO-56 Tabla 12 para un cultivo y etapa."""
    key = crop.lower()
    for k, v in FAO56_CROP_KC_TABLE.items():
        if k in key:
            return v.get(f"kc_{stage}", v["kc_mid"])
    return 1.0 if stage == "mid" else 0.40


def get_crop_kc_monthly(cover_code: str, month: int, latitude_deg: float = -33.3) -> float:
    """Asigna el coeficiente de cultivo Kc mensual según fenología regional y FAO-56 Tabla 12.

    En el Hemisferio Sur (San Luis / región pampeana, lat < 0):
    - Cultivos estivales (soja / maíz / girasol):
        - Nov: inicio / vegetativo temprano (Kc ~ 0.65)
        - Dic - Feb: floración y llenado de grano (Kc_mid = 1.15)
        - Mar: maduración (Kc_end = 0.50)
        - Abr - Oct: barbecho / rastrojo protector invernal (Kc = 0.25, FAO-56 Tabla 12)
    - Cultivos invernales (trigo / cebada):
        - Jun - Jul: implantación y macollaje (Kc_ini = 0.35)
        - Ago - Sep: encañazón y crecimiento activo (Kc ~ 0.80)
        - Oct: floración / espigazón (Kc_mid = 1.15)
        - Nov: llenado y maduración (Kc_end = 0.35)
        - Dic - May: barbecho estival (Kc = 0.25)
    - Pasturas / pastizales:
        - Oct - Mar (estación cálida): Kc = 0.95
        - Abr - Sep (estación fría): Kc = 0.60
    """
    code = cover_code.lower()
    is_south = float(latitude_deg) < 0

    if "trigo" in code or "cebada" in code:
        if is_south:
            if month in (6, 7):
                return 0.35
            if month in (8, 9):
                return 0.80
            if month == 10:
                return 1.15
            if month == 11:
                return 0.35
            return float(SUPUESTO_FAO56_KC_BARBECHO.valor)
        else:
            if month in (12, 1):
                return 0.35
            if month in (2, 3):
                return 0.80
            if month == 4:
                return 1.15
            if month == 5:
                return 0.35
            return float(SUPUESTO_FAO56_KC_BARBECHO.valor)

    if "pastura" in code or "pastizal" in code:
        if is_south:
            return 0.95 if month in (10, 11, 12, 1, 2, 3) else 0.60
        else:
            return 0.95 if month in (4, 5, 6, 7, 8, 9) else 0.60

    if "barbecho" in code or "desnudo" in code:
        return float(SUPUESTO_FAO56_KC_BARBECHO.valor)

    # Cultivo estival (soja / maíz / girasol) por omisión
    if is_south:
        if month in (12, 1, 2):
            return 1.15  # Pleno llenado de grano y máxima área foliar
        if month == 11:
            return 0.65  # Implantación y primeros nudos
        if month == 3:
            return 0.50  # Maduración y caída de hojas
        return float(SUPUESTO_FAO56_KC_BARBECHO.valor)  # Barbecho / descanso invernal
    else:
        if month in (6, 7, 8):
            return 1.15
        if month == 5:
            return 0.65
        if month == 9:
            return 0.50
        return float(SUPUESTO_FAO56_KC_BARBECHO.valor)


# ==============================================================================
# 3. Condición de Humedad Antecedente (AMC) USDA-SCS NEH-4 Tabla 4.2
# ==============================================================================

def determine_nrcs_amc(
    prior_5d_mm: float,
    month: int | None = None,
    season: Literal["growing", "dormant"] | None = None,
    latitude_deg: float | None = None,
) -> AntecedentMoisture:
    """Determina la condición de humedad antecedente AMC (dry / medium / wet) según

    USDA-SCS (1972) National Engineering Handbook, Section 4: Hydrology (NEH-4),
    Tabla 4.2 ("Seasonal rainfall limits for AMC classes", pág. 4.12).

    Diferencia estación de reposo (dormant) y de crecimiento (growing):
    - Estación de reposo (dormant):
        AMC I (Dry): P_5d < 12.7 mm (< 0.5 pulg)
        AMC II (Medium): 12.7 mm <= P_5d <= 27.9 mm (0.5 a 1.1 pulg)
        AMC III (Wet): P_5d > 27.9 mm (> 1.1 pulg)
    - Estación de crecimiento (growing):
        AMC I (Dry): P_5d < 35.6 mm (< 1.4 pulg)
        AMC II (Medium): 35.6 mm <= P_5d <= 53.3 mm (1.4 a 2.1 pulg)
        AMC III (Wet): P_5d > 53.3 mm (> 2.1 pulg)
    """
    p = max(0.0, float(prior_5d_mm))
    st = season
    if st is None:
        if month is not None:
            if latitude_deg is None:
                raise ValueError(
                    "latitude_deg es obligatoria para clasificar la estación (dormant/growing) según el hemisferio."
                )
            is_south = float(latitude_deg) < 0
            meses_reposo = (
                set(SUPUESTO_MESES_ESTACION_REPOSO_SUR.valor)
                if is_south
                else set(SUPUESTO_MESES_ESTACION_REPOSO_NORTE.valor)
            )
            st = "dormant" if month in meses_reposo else "growing"
        else:
            st = "growing"

    if st == "dormant":
        dry_thresh = float(SUPUESTO_AMC_REPOSO_SECO_MM.valor)
        wet_thresh = float(SUPUESTO_AMC_REPOSO_HUMEDO_MM.valor)
    else:
        dry_thresh = float(SUPUESTO_AMC_CRECIMIENTO_SECO_MM.valor)
        wet_thresh = float(SUPUESTO_AMC_CRECIMIENTO_HUMEDO_MM.valor)

    if p < dry_thresh:
        return "dry"
    if p <= wet_thresh:
        return "medium"
    return "wet"


def compute_monthly_water_balance(
    daily_rows: list[dict],
    source_label: str,
    soil_group: SoilGroup = "B",
    cover_code: str = "soja_maiz_sd_buena",
    latitude_deg: float | None = None,
) -> dict:
    """Herramienta 2: Balance hídrico mensual del lote con ET0 y Kc de FAO-56 (Ecuaciones 21-28, 52 y Tabla 12)."""
    if latitude_deg is None:
        raise ValueError("latitude_deg es obligatoria para calcular la radiación extraterrestre FAO-56.")
    lat = float(latitude_deg)
    awc_max = AVAILABLE_WATER_CAPACITY_MM.get(soil_group, 150.0)
    cn_ii, _ = lookup_cn_ii(cover_code, soil_group)

    if not daily_rows:
        return {
            "source": source_label,
            "status": "unavailable",
            "soil_group": soil_group,
            "available_water_capacity_max_mm": awc_max,
            "annual_precipitation_mm": 0.0,
            "annual_et0_mm": 0.0,
            "deficit_months_count": 0,
            "excess_months_count": 0,
            "final_available_water_mm": 0.0,
            "final_available_water_pct": 0.0,
            "months": [],
        }

    # Agrupar los últimos 12 meses disponibles
    by_ym: dict[tuple[int, int], list[dict]] = {}
    for r in daily_rows:
        yr = r.get("year")
        mo = r.get("month")
        if (yr is None or mo is None) and "date" in r:
            try:
                parts = str(r["date"]).split("-")
                yr = yr if yr is not None else int(parts[0])
                mo = mo if mo is not None else int(parts[1])
            except (ValueError, IndexError):
                yr = None
                mo = None
        if yr is not None and mo is not None and 1 <= mo <= 12:
            by_ym.setdefault((yr, mo), []).append(r)

    last_12_keys = sorted(by_ym.keys())[-12:]
    storage_mm = 0.65 * awc_max  # humedad inicial al 65 % de capacidad de campo

    months_out: list[dict] = []
    deficit_months = 0
    excess_months = 0
    total_rain = 0.0
    total_et0 = 0.0
    has_incomplete_month = False

    for yr, mo in last_12_keys:
        days = by_ym[(yr, mo)]

        # Verificar integridad del mes: sin lluvia o temperatura inventada (Auditoría 21/11 / Regla de datos)
        missing_reasons = []
        for d in days:
            if d.get("precip_mm") is None:
                missing_reasons.append("precipitación faltante")
            if d.get("tmean_c") is None or d.get("tmax_c") is None or d.get("tmin_c") is None:
                missing_reasons.append("temperatura faltante")
            doy = d.get("day_of_year")
            if doy is None and "date" in d:
                try:
                    doy = datetime.strptime(str(d["date"]), "%Y-%m-%d").timetuple().tm_yday
                except (ValueError, TypeError):
                    doy = None
            if doy is None:
                missing_reasons.append("fecha / día del año faltante")

        if missing_reasons:
            has_incomplete_month = True
            months_out.append({
                "year": yr,
                "month": mo,
                "label": f"{MONTH_NAMES_ES[mo - 1]} {yr}",
                "calidad": "descartada",
                "motivo": f"Mes incompleto: {', '.join(sorted(set(missing_reasons)))}",
                "precipitation_mm": None,
                "surface_runoff_mm": None,
                "et0_mm": None,
                "kc": round(get_crop_kc_monthly(cover_code, mo, lat), 2),
                "crop_demand_etc_mm": None,
                "available_water_mm": None,
                "available_water_pct": None,
                "deficit_mm": None,
                "excess_drainage_mm": None,
                "status": "Incompleto (descartada)",
            })
            continue

        rain_m = sum(float(d["precip_mm"]) for d in days)
        # Estimar escorrentía superficial de las tormentas fuertes del mes (días con P >= 15 mm)
        runoff_m = sum(
            compute_nrcs_cn(
                float(d["precip_mm"]),
                cn_ii,
                determine_nrcs_amc(d.get("prior_5d_rain_mm", 20.0), month=mo, latitude_deg=lat),
            ).runoff_q_mm
            for d in days
            if float(d["precip_mm"]) >= 15.0
        )
        effective_infiltration = max(0.0, rain_m - runoff_m)

        # Evapotranspiración potencial diaria según FAO-56 (Hargreaves Eq. 52 con Ra diaria Eq. 21-28)
        et0_m = 0.0
        for d in days:
            doy = d.get("day_of_year")
            if doy is None:
                doy = datetime.strptime(str(d["date"]), "%Y-%m-%d").timetuple().tm_yday
            ra = compute_extraterrestrial_radiation_ra(lat, doy)
            et0_m += compute_hargreaves_et0_daily(
                float(d["tmean_c"]),
                float(d["tmax_c"]),
                float(d["tmin_c"]),
                ra,
            )

        kc = get_crop_kc_monthly(cover_code, mo, lat)
        etc_m = et0_m * kc

        supply = storage_mm + effective_infiltration
        if supply >= etc_m:
            deficit = 0.0
            remaining = supply - etc_m
            if remaining > awc_max:
                excess = remaining - awc_max
                storage_mm = awc_max
            else:
                excess = 0.0
                storage_mm = remaining
        else:
            deficit = etc_m - supply
            excess = 0.0
            storage_mm = 0.0

        if deficit >= 15.0:
            deficit_months += 1
        if excess >= 15.0 or runoff_m >= 15.0:
            excess_months += 1

        total_rain += rain_m
        total_et0 += et0_m

        months_out.append({
            "year": yr,
            "month": mo,
            "label": f"{MONTH_NAMES_ES[mo - 1]} {yr}",
            "precipitation_mm": round(rain_m, 1),
            "surface_runoff_mm": round(runoff_m, 1),
            "et0_mm": round(et0_m, 1),
            "kc": round(kc, 2),
            "crop_demand_etc_mm": round(etc_m, 1),
            "available_water_mm": round(storage_mm, 1),
            "available_water_pct": round(100.0 * storage_mm / awc_max, 1),
            "deficit_mm": round(deficit, 1),
            "excess_drainage_mm": round(excess, 1),
            "status": "Déficit" if deficit >= 15.0 else ("Exceso" if (excess + runoff_m) >= 20.0 else "Adecuado"),
        })

    if has_incomplete_month:
        return {
            "source": source_label,
            "status": "unavailable",
            "calidad": "descartada",
            "motivo": "Serie mensual incompleta por datos faltantes de clima (temperatura, precipitación o fecha).",
            "soil_group": soil_group,
            "available_water_capacity_max_mm": awc_max,
            "annual_precipitation_mm": None,
            "annual_et0_mm": None,
            "deficit_months_count": None,
            "excess_months_count": None,
            "final_available_water_mm": None,
            "final_available_water_pct": None,
            "months": months_out,
        }

    return {
        "source": source_label,
        "status": "available",
        "soil_group": soil_group,
        "available_water_capacity_max_mm": awc_max,
        "annual_precipitation_mm": round(total_rain, 1),
        "annual_et0_mm": round(total_et0, 1),
        "deficit_months_count": deficit_months,
        "excess_months_count": excess_months,
        "final_available_water_mm": months_out[-1]["available_water_mm"] if months_out else 0.0,
        "final_available_water_pct": months_out[-1]["available_water_pct"] if months_out else 0.0,
        "months": months_out,
    }


def evaluate_real_date_waterlogging_risk(
    daily_rows: list[dict],
    source_label: str,
    soil_group: SoilGroup,
    cover_code: str,
    field_area_ha: float,
    low_zone_area_ha: float,
    depression_volume_m3: float,
    latitude_deg: float | None = None,
) -> dict:
    """Herramienta 3: Evalúa los eventos reales de tormenta más intensos y su volumen escurrido hacia bajos."""
    if not daily_rows:
        return {
            "source": source_label,
            "status": "unavailable",
            "calidad": "descartada",
            "motivo": "Sin datos climáticos diarios para evaluar escurrimiento histórico.",
            "evaluated_days": 0,
            "significant_storms_count": 0,
            "high_waterlogging_events_count": None,
            "top_historical_events": [],
        }

    cn_ii, _ = lookup_cn_ii(cover_code, soil_group)

    # Calcular para cada día la lluvia del evento (1 a 2 días consecutivos) y la lluvia antecedente de 5 días
    storms: list[dict] = []
    for i in range(5, len(daily_rows)):
        p_day = daily_rows[i].get("precip_mm")
        if p_day is None or p_day < 18.0:
            continue
        prior_slice = [daily_rows[j].get("precip_mm") for j in range(i - 5, i)]
        if any(p is None for p in prior_slice):
            continue
        p_5d_prior = sum(float(p) for p in prior_slice)
        # Condición de humedad antecedente según USDA-SCS NEH-4 Tabla 4.2 (reposo vs. crecimiento):
        mo = daily_rows[i].get("month")
        if mo is None and "date" in daily_rows[i]:
            try:
                mo = int(str(daily_rows[i]["date"]).split("-")[1])
            except (ValueError, IndexError):
                mo = None
        if latitude_deg is not None and mo is not None:
            amc = determine_nrcs_amc(
                prior_5d_mm=p_5d_prior,
                month=mo,
                latitude_deg=latitude_deg,
            )
        else:
            amc = determine_nrcs_amc(
                prior_5d_mm=p_5d_prior,
                season="growing",
            )

        cn_res = compute_nrcs_cn(p_day, cn_ii, amc, 0.2)
        runoff_m3 = (cn_res.runoff_q_mm / 1000.0) * (float(field_area_ha) * 10_000.0)

        # Fracción y porcentaje de llenado del volumen total de bajos en el lote
        dep_vol = float(depression_volume_m3)
        if dep_vol > 0:
            fill_pct = round(100.0 * runoff_m3 / dep_vol, 1)
        else:
            fill_pct = None

        # Auditoría 21/11/2026 punto 2:
        # Se elimina el factor min(1.8, relleno) y los umbrales inventados (25 mm, 8 mm, 0.85, 0.35).
        # Hectáreas solo si vienen del motor 2D (aquí no hay simulación 2D diaria para cada evento).
        storms.append({
            "date": daily_rows[i]["date"],
            "precipitation_mm": round(p_day, 1),
            "prior_5d_rain_mm": round(p_5d_prior, 1),
            "antecedent_moisture_amc": amc,
            "cn_effective": cn_res.cn_effective,
            "runoff_q_mm": cn_res.runoff_q_mm,
            "runoff_volume_m3": round(runoff_m3, 1),
            "depression_fill_pct": fill_pct,
            "estimated_waterlogged_area_ha": None,
            "waterlogging_risk": "descartada",
        })

    storms.sort(key=lambda item: item["precipitation_mm"], reverse=True)
    top_storms = storms[:8]

    return {
        "source": source_label,
        "status": "available",
        "evaluated_days": len(daily_rows),
        "significant_storms_count": len(storms),
        "high_waterlogging_events_count": None,
        "top_historical_events": top_storms,
    }


def evaluate_frost_risk_and_sowing_dates(
    daily_rows: list[dict],
    source_label: str,
) -> dict:
    """Herramienta 8: Riesgo de heladas (Tmin <= 0 °C meteorológica y <= 3 °C agronómica) y fechas seguras."""
    src = "NASA POWER (reanálisis ~55 km)" if "nasa" in source_label.lower() else source_label

    if not daily_rows:
        return {
            "source": src,
            "status": "unavailable",
            "is_satellite_observed": False,
            "calidad": "descartada",
            "motivo": "Sin serie climática diaria para calcular estadísticas de heladas.",
            "mean_meteorological_frost_days_yr": None,
            "mean_agronomic_frost_days_yr": None,
            "median_last_spring_frost_date": None,
            "safe_spring_sowing_start_date": None,
            "median_first_autumn_frost_date": None,
            "frost_free_period_days": None,
            "safe_sowing_windows_by_crop": [],
        }

    by_year: dict[int, list[dict]] = {}
    for r in daily_rows:
        by_year.setdefault(r["year"], []).append(r)

    last_spring_doys: list[int] = []
    first_autumn_doys: list[int] = []
    frost_days_per_year: list[int] = []
    agro_frost_days_per_year: list[int] = []

    for yr, days in by_year.items():
        if len(days) < 300:
            continue
        met_frost = [d for d in days if d["tmin_c"] <= 0.0]
        agr_frost = [d for d in days if d["tmin_c"] <= 3.0]
        frost_days_per_year.append(len(met_frost))
        agro_frost_days_per_year.append(len(agr_frost))

        # En el hemisferio sur:
        # - Heladas tardías (invierno/primavera): doy entre 180 (fin de junio) y 350 (diciembre)
        # - Heladas tempranas (otoño): doy entre 75 (marzo) y 179 (junio)
        spring_candidates = [d["day_of_year"] for d in agr_frost if d["day_of_year"] >= 180]
        autumn_candidates = [d["day_of_year"] for d in agr_frost if 75 <= d["day_of_year"] < 180]
        if spring_candidates:
            last_spring_doys.append(max(spring_candidates))
        if autumn_candidates:
            first_autumn_doys.append(min(autumn_candidates))

    # Auditoría 21/11/2026 punto 3:
    # Si faltan datos suficientes de años completos, null + "descartada", sin valores inventados
    # (eliminados 12.0 / 28.0 días y fechas 265, 280, 115).
    if not frost_days_per_year or not last_spring_doys or not first_autumn_doys:
        return {
            "source": src,
            "status": "unavailable",
            "is_satellite_observed": False,
            "calidad": "descartada",
            "motivo": "Años con datos incompletos (<300 días) para determinar percentiles y medianas de heladas.",
            "mean_meteorological_frost_days_yr": round(float(np.mean(frost_days_per_year)), 1)
            if frost_days_per_year
            else None,
            "mean_agronomic_frost_days_yr": round(float(np.mean(agro_frost_days_per_year)), 1)
            if agro_frost_days_per_year
            else None,
            "median_last_spring_frost_date": None,
            "safe_spring_sowing_start_date": None,
            "median_first_autumn_frost_date": None,
            "frost_free_period_days": None,
            "safe_sowing_windows_by_crop": [],
        }

    med_spring_doy = int(round(float(np.median(last_spring_doys))))
    safe_spring_doy = int(round(float(np.percentile(last_spring_doys, 90)))) + 5
    med_autumn_doy = int(round(float(np.median(first_autumn_doys))))

    def _doy_to_label(doy: int) -> str:
        dt = date(2025, 1, 1) + timedelta(days=max(0, min(364, doy - 1)))
        return f"{dt.day:02d} de {MONTH_NAMES_ES[dt.month - 1]}"

    # Sin piso artificial de 120 días (auditoría punto 3)
    frost_free_days = (365 - safe_spring_doy) + med_autumn_doy

    return {
        "source": src,
        "status": "available",
        "is_satellite_observed": False,
        "mean_meteorological_frost_days_yr": round(float(np.mean(frost_days_per_year)), 1),
        "mean_agronomic_frost_days_yr": round(float(np.mean(agro_frost_days_per_year)), 1),
        "median_last_spring_frost_date": _doy_to_label(med_spring_doy),
        "safe_spring_sowing_start_date": _doy_to_label(safe_spring_doy),
        "median_first_autumn_frost_date": _doy_to_label(med_autumn_doy),
        "frost_free_period_days": int(frost_free_days),
        "safe_sowing_windows_by_crop": [
            {
                "crop": "Maíz Temprano",
                "safe_start": _doy_to_label(safe_spring_doy - 10),
                "note": "Emergencia tolera heladas suaves hasta V4 (ápice bajo tierra); evitar floración en enero seco.",
            },
            {
                "crop": "Soja de 1ª",
                "safe_start": _doy_to_label(safe_spring_doy + 12),
                "note": "Muy sensible a helada tardía en cotiledón expuesto; sembrar tras fecha segura P90.",
            },
            {
                "crop": "Maíz Tardío / Sorgo",
                "safe_start": "25 de Nov al 20 de Dic",
                "note": "Verificar que madurez fisiológica (R6) ocurra antes del " + _doy_to_label(med_autumn_doy),
            },
        ],
    }


def compute_ndvi_vigor_monitor(
    dem: Dem,
    mascara_lote: np.ndarray,
    twi: np.ndarray,
    agronomic_zone_id: np.ndarray,
    bbox_4326: tuple[float, float, float, float],
) -> dict:
    """Herramienta 7: Monitor de vigor (NDVI) consultando Sentinel-2 L2A STAC COG público en AWS
    con enmascaramiento de nubes mediante SCL (Scene Classification Layer).
    """
    import rasterio
    from rasterio.warp import Resampling, reproject

    from geoprocessing.net import http_opener

    oeste, sur, este, norte = bbox_4326
    ndvi_grid: np.ndarray | None = None
    scene_info: dict = {}

    try:
        r = client().post(
            EARTH_SEARCH_STAC_URL,
            json={
                "collections": ["sentinel-2-l2a"],
                "bbox": [oeste, sur, este, norte],
                "limit": 5,
                "query": {"eo:cloud_cover": {"lt": 85}},
            },
            timeout=12.0,
        )
        r.raise_for_status()
        feats = r.json().get("features") or []
        for feat in feats:
            props = feat.get("properties") or {}
            cloud_pct = float(props.get("eo:cloud_cover", 0.0))
            if cloud_pct >= 85.0:
                continue

            assets = feat.get("assets") or {}
            red_href = (assets.get("red") or assets.get("B04") or {}).get("href")
            nir_href = (assets.get("nir") or assets.get("B08") or {}).get("href")
            scl_href = (assets.get("scl") or assets.get("SCL") or {}).get("href")
            if not (red_href and nir_href):
                continue

            alto, ancho = dem.z.shape
            red_utm = np.full((alto, ancho), np.nan, dtype="float32")
            nir_utm = np.full((alto, ancho), np.nan, dtype="float32")
            with rasterio.open(red_href, opener=http_opener) as src_r:
                reproject(
                    source=rasterio.band(src_r, 1),
                    destination=red_utm,
                    src_transform=src_r.transform,
                    src_crs=src_r.crs,
                    dst_transform=dem.transform,
                    dst_crs=dem.crs,
                    dst_nodata=np.nan,
                    resampling=Resampling.nearest,
                )
            with rasterio.open(nir_href, opener=http_opener) as src_n:
                reproject(
                    source=rasterio.band(src_n, 1),
                    destination=nir_utm,
                    src_transform=src_n.transform,
                    src_crs=src_n.crs,
                    dst_transform=dem.transform,
                    dst_crs=dem.crs,
                    dst_nodata=np.nan,
                    resampling=Resampling.nearest,
                )

            scl_utm = None
            if scl_href:
                try:
                    scl_dest = np.zeros((alto, ancho), dtype="uint8")
                    with rasterio.open(scl_href, opener=http_opener) as src_s:
                        reproject(
                            source=rasterio.band(src_s, 1),
                            destination=scl_dest,
                            src_transform=src_s.transform,
                            src_crs=src_s.crs,
                            dst_transform=dem.transform,
                            dst_crs=dem.crs,
                            dst_nodata=0,
                            resampling=Resampling.nearest,
                        )
                    scl_utm = scl_dest
                except Exception:
                    scl_utm = None

            denom = nir_utm + red_utm
            valid_px = np.isfinite(denom) & (denom > 0)
            ndvi_cand = np.where(valid_px, (nir_utm - red_utm) / denom, np.nan).astype("float32")
            ndvi_cand = np.clip(ndvi_cand, -0.2, 0.95)

            # Enmascarar píxeles nubosos usando la banda SCL
            if scl_utm is not None:
                cloud_mask = np.isin(scl_utm, [3, 8, 9, 10, 11])
                ndvi_cand = np.where(~cloud_mask, ndvi_cand, np.nan)

            if np.isfinite(ndvi_cand[mascara_lote]).any():
                ndvi_grid = ndvi_cand
                scene_info = {
                    "source": "ESA Sentinel-2 L2A (COG 10 m vía AWS Element84 Earth Search STAC)",
                    "scene_id": feat.get("id"),
                    "acquisition_date": (props.get("datetime") or "")[:10],
                    "cloud_cover_pct": round(cloud_pct, 1),
                    "is_satellite_observed": True,
                    "status": "available",
                }
                break
    except Exception:
        ndvi_grid = None

    if ndvi_grid is None:
        return {
            "grid": None,
            "summary": {
                "source": "ESA Sentinel-2 L2A (No disponible - sin escenas válidas o conexión)",
                "scene_id": None,
                "acquisition_date": None,
                "cloud_cover_pct": None,
                "is_satellite_observed": False,
                "status": "unavailable",
                "calidad": "descartada",
                "motivo": "No se encontraron escenas Sentinel-2 L2A con cobertura de nubes < 85% para el lote o servicio STAC no disponible.",
                "mean_ndvi_in_field": None,
                "min_ndvi_in_field": None,
                "max_ndvi_in_field": None,
                "low_vigor_area_ha": None,
                "low_vigor_pct": None,
                "moderate_vigor_pct": None,
                "high_vigor_pct": None,
                "weak_zones_explained_by_waterlogging_or_erosion_pct": None,
                "ndvi_by_agronomic_zone": [],
                "supuestos": {
                    "umbral_bajo_vigor": float(SUPUESTO_NDVI_UMBRAL_BAJO_VIGOR.valor),
                    "umbral_alto_vigor": float(SUPUESTO_NDVI_UMBRAL_ALTO_VIGOR.valor),
                },
            },
        }

    in_field = mascara_lote & np.isfinite(ndvi_grid)
    ndvi_f = ndvi_grid[in_field]
    cell_area_ha = (float(dem.pixel) ** 2) / 10_000.0
    total_cells = max(1, int(in_field.sum()))

    u_bajo = float(SUPUESTO_NDVI_UMBRAL_BAJO_VIGOR.valor)
    u_alto = float(SUPUESTO_NDVI_UMBRAL_ALTO_VIGOR.valor)
    low_vigor = in_field & (ndvi_grid < u_bajo)
    mod_vigor = in_field & (ndvi_grid >= u_bajo) & (ndvi_grid < u_alto)
    high_vigor = in_field & (ndvi_grid >= u_alto)

    low_cells = int(low_vigor.sum())
    low_in_wet_bajos = int((low_vigor & (agronomic_zone_id == 4)).sum())
    low_in_erosion_ways = int((low_vigor & (agronomic_zone_id == 3)).sum())
    overlap_hydro_pct = (
        round(100.0 * (low_in_wet_bajos + low_in_erosion_ways) / low_cells, 1)
        if low_cells > 0
        else 0.0
    )

    by_zone = []
    for z_id, label in (
        (1, "Ambiente 1 — Loma"),
        (2, "Ambiente 2 — Media loma"),
        (3, "Ambiente 3 — Vía escurrimiento"),
        (4, "Ambiente 4 — Bajo receptor"),
    ):
        mz = in_field & (agronomic_zone_id == z_id)
        by_zone.append({
            "zone_id": z_id,
            "label": label,
            "mean_ndvi": round(float(ndvi_grid[mz].mean()), 3) if mz.any() else None,
        })

    return {
        "grid": ndvi_grid,
        "summary": {
            **scene_info,
            "mean_ndvi_in_field": round(float(ndvi_f.mean()), 3) if ndvi_f.size else None,
            "min_ndvi_in_field": round(float(ndvi_f.min()), 3) if ndvi_f.size else None,
            "max_ndvi_in_field": round(float(ndvi_f.max()), 3) if ndvi_f.size else None,
            "low_vigor_area_ha": round(low_cells * cell_area_ha, 2) if total_cells else None,
            "low_vigor_pct": round(100.0 * low_cells / total_cells, 1) if total_cells else None,
            "moderate_vigor_pct": round(100.0 * int(mod_vigor.sum()) / total_cells, 1) if total_cells else None,
            "high_vigor_pct": round(100.0 * int(high_vigor.sum()) / total_cells, 1) if total_cells else None,
            "weak_zones_explained_by_waterlogging_or_erosion_pct": overlap_hydro_pct if low_cells > 0 else 0.0,
            "ndvi_by_agronomic_zone": by_zone,
            "supuestos": {
                "umbral_bajo_vigor": u_bajo,
                "umbral_alto_vigor": u_alto,
            },
        },
    }
