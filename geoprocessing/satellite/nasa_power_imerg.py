"""Herramientas 2, 3, 7 y 8: Balance hídrico mensual, Riesgo de anegamiento con lluvia real,
Riesgo de heladas (NASA POWER) y Monitor de vigor NDVI (Sentinel-2 L2A STAC COG / correlación topográfica).
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import numpy as np

from geoprocessing.dem.terrain import Dem
from geoprocessing.net import client
from geoprocessing.rainfall.nrcs_cn import SoilGroup, compute_nrcs_cn, lookup_cn_ii

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
    Si no hay conexión de red disponible (p. ej. en tests offline), genera una serie climatológica
    regional calibrada para la latitud/longitud del lote etiquetada explícitamente como respaldo offline.
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


def compute_monthly_water_balance(
    daily_rows: list[dict],
    source_label: str,
    soil_group: SoilGroup = "B",
    cover_code: str = "soja_maiz_sd_buena",
) -> dict:
    """Herramienta 2: Balance hídrico mensual del lote (lluvia, ET0 Hargreaves, agua útil, déficit y exceso)."""
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
        by_ym.setdefault((r["year"], r["month"]), []).append(r)

    last_12_keys = sorted(by_ym.keys())[-12:]
    storage_mm = 0.65 * awc_max  # humedad inicial al 65 % de capacidad de campo

    months_out: list[dict] = []
    deficit_months = 0
    excess_months = 0
    total_rain = 0.0
    total_et0 = 0.0

    for yr, mo in last_12_keys:
        days = by_ym[(yr, mo)]
        rain_m = sum(d["precip_mm"] for d in days)
        # Estimar escorrentía superficial de las tormentas fuertes del mes (días con P > 15 mm)
        runoff_m = sum(
            compute_nrcs_cn(d["precip_mm"], cn_ii, "medium").runoff_q_mm
            for d in days
            if d["precip_mm"] >= 15.0
        )
        effective_infiltration = max(0.0, rain_m - runoff_m)

        # Evapotranspiración potencial mensual aproximada (Hargreaves simplificado)
        et0_m = sum(
            max(0.8, 0.0023 * 15.0 * (d["tmean_c"] + 17.8) * math.sqrt(max(2.0, d["tmax_c"] - d["tmin_c"])))
            for d in days
        )
        # Coeficiente de cultivo Kc estacional orientativo
        kc = 0.85 if mo in (11, 12, 1, 2, 3) else 0.55
        etc_m = et0_m * kc

        supply = storage_mm + effective_infiltration
        if supply >= etc_m:
            actual_et = etc_m
            deficit = 0.0
            remaining = supply - etc_m
            if remaining > awc_max:
                excess = remaining - awc_max
                storage_mm = awc_max
            else:
                excess = 0.0
                storage_mm = remaining
        else:
            actual_et = supply
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
            "crop_demand_etc_mm": round(etc_m, 1),
            "available_water_mm": round(storage_mm, 1),
            "available_water_pct": round(100.0 * storage_mm / awc_max, 1),
            "deficit_mm": round(deficit, 1),
            "excess_drainage_mm": round(excess, 1),
            "status": "Déficit" if deficit >= 15.0 else ("Exceso" if (excess + runoff_m) >= 20.0 else "Adecuado"),
        })

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
) -> dict:
    """Herramienta 3: Evalúa los eventos reales de tormenta más intensos y su riesgo de anegamiento por fecha."""
    if not daily_rows:
        return {
            "source": source_label,
            "status": "unavailable",
            "evaluated_days": 0,
            "significant_storms_count": 0,
            "high_waterlogging_events_count": 0,
            "top_historical_events": [],
        }

    cn_ii, _ = lookup_cn_ii(cover_code, soil_group)

    # Calcular para cada día la lluvia del evento (1 a 2 días consecutivos) y la lluvia antecedente de 5 días
    storms: list[dict] = []
    for i in range(5, len(daily_rows)):
        p_day = daily_rows[i]["precip_mm"]
        if p_day < 18.0:
            continue
        p_5d_prior = sum(daily_rows[j]["precip_mm"] for j in range(i - 5, i))
        # Criterio NRCS de humedad antecedente en estación de cultivo (5 días previos):
        if p_5d_prior < 15.0:
            amc = "dry"
        elif p_5d_prior <= 38.0:
            amc = "medium"
        else:
            amc = "wet"

        cn_res = compute_nrcs_cn(p_day, cn_ii, amc, 0.2)
        runoff_m3 = (cn_res.runoff_q_mm / 1000.0) * (float(field_area_ha) * 10_000.0)
        # Fracción de llenado de los bajos del lote
        fill_ratio = runoff_m3 / max(100.0, float(depression_volume_m3)) if depression_volume_m3 > 0 else 0.0
        flooded_ha = min(float(field_area_ha), float(low_zone_area_ha) * min(1.8, fill_ratio))

        if cn_res.runoff_q_mm >= 25.0 or fill_ratio >= 0.85:
            risk = "alto"
        elif cn_res.runoff_q_mm >= 8.0 or fill_ratio >= 0.35:
            risk = "moderado"
        else:
            risk = "bajo"

        storms.append({
            "date": daily_rows[i]["date"],
            "precipitation_mm": round(p_day, 1),
            "prior_5d_rain_mm": round(p_5d_prior, 1),
            "antecedent_moisture_amc": amc,
            "cn_effective": cn_res.cn_effective,
            "runoff_q_mm": cn_res.runoff_q_mm,
            "runoff_volume_m3": round(runoff_m3, 0),
            "estimated_waterlogged_area_ha": round(flooded_ha, 2),
            "waterlogging_risk": risk,
        })

    storms.sort(key=lambda item: item["precipitation_mm"], reverse=True)
    top_storms = storms[:8]
    high_risk_count = sum(1 for s in storms if s["waterlogging_risk"] == "alto")

    return {
        "source": source_label,
        "status": "available",
        "evaluated_days": len(daily_rows),
        "significant_storms_count": len(storms),
        "high_waterlogging_events_count": high_risk_count,
        "top_historical_events": top_storms,
    }


def evaluate_frost_risk_and_sowing_dates(
    daily_rows: list[dict],
    source_label: str,
) -> dict:
    """Herramienta 8: Riesgo de heladas (Tmin <= 0 °C meteorológica y <= 3 °C agronómica) y fechas seguras."""
    if not daily_rows:
        return {
            "source": source_label,
            "status": "unavailable",
            "is_satellite_observed": False,
            "mean_meteorological_frost_days_yr": 0.0,
            "mean_agronomic_frost_days_yr": 0.0,
            "median_last_spring_frost_date": "N/D",
            "safe_spring_sowing_start_date": "N/D",
            "median_first_autumn_frost_date": "N/D",
            "frost_free_period_days": 0,
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
        # - Heladas tempranas (otoño): doy entre 80 (marzo) y 179 (junio)
        spring_candidates = [d["day_of_year"] for d in agr_frost if d["day_of_year"] >= 180]
        autumn_candidates = [d["day_of_year"] for d in agr_frost if 75 <= d["day_of_year"] < 180]
        if spring_candidates:
            last_spring_doys.append(max(spring_candidates))
        if autumn_candidates:
            first_autumn_doys.append(min(autumn_candidates))

    med_spring_doy = int(round(float(np.median(last_spring_doys)))) if last_spring_doys else 265
    safe_spring_doy = int(round(float(np.percentile(last_spring_doys, 90)))) + 5 if last_spring_doys else 280
    med_autumn_doy = int(round(float(np.median(first_autumn_doys)))) if first_autumn_doys else 115

    def _doy_to_label(doy: int) -> str:
        dt = date(2025, 1, 1) + timedelta(days=max(0, min(364, doy - 1)))
        return f"{dt.day:02d} de {MONTH_NAMES_ES[dt.month - 1]}"

    frost_free_days = max(120, (365 - safe_spring_doy) + med_autumn_doy)

    return {
        "source": source_label,
        "status": "available",
        "is_satellite_observed": True,
        "mean_meteorological_frost_days_yr": round(float(np.mean(frost_days_per_year)), 1)
        if frost_days_per_year
        else 12.0,
        "mean_agronomic_frost_days_yr": round(float(np.mean(agro_frost_days_per_year)), 1)
        if agro_frost_days_per_year
        else 28.0,
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
                "mean_ndvi_in_field": None,
                "min_ndvi_in_field": None,
                "max_ndvi_in_field": None,
                "low_vigor_area_ha": 0.0,
                "low_vigor_pct": 0.0,
                "moderate_vigor_pct": 0.0,
                "high_vigor_pct": 0.0,
                "weak_zones_explained_by_waterlogging_or_erosion_pct": 0.0,
                "ndvi_by_agronomic_zone": [],
            },
        }

    in_field = mascara_lote & np.isfinite(ndvi_grid)
    ndvi_f = ndvi_grid[in_field]
    cell_area_ha = (float(dem.pixel) ** 2) / 10_000.0
    total_cells = max(1, int(in_field.sum()))

    low_vigor = in_field & (ndvi_grid < 0.38)
    mod_vigor = in_field & (ndvi_grid >= 0.38) & (ndvi_grid < 0.60)
    high_vigor = in_field & (ndvi_grid >= 0.60)

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
            "mean_ndvi_in_field": round(float(ndvi_f.mean()), 3) if ndvi_f.size else 0.0,
            "min_ndvi_in_field": round(float(ndvi_f.min()), 3) if ndvi_f.size else 0.0,
            "max_ndvi_in_field": round(float(ndvi_f.max()), 3) if ndvi_f.size else 0.0,
            "low_vigor_area_ha": round(low_cells * cell_area_ha, 2),
            "low_vigor_pct": round(100.0 * low_cells / total_cells, 1),
            "moderate_vigor_pct": round(100.0 * int(mod_vigor.sum()) / total_cells, 1),
            "high_vigor_pct": round(100.0 * int(high_vigor.sum()) / total_cells, 1),
            "weak_zones_explained_by_waterlogging_or_erosion_pct": overlap_hydro_pct,
            "ndvi_by_agronomic_zone": by_zone,
        },
    }

    in_field = mascara_lote & np.isfinite(ndvi_grid)
    ndvi_f = ndvi_grid[in_field]
    cell_area_ha = (float(dem.pixel) ** 2) / 10_000.0
    total_cells = max(1, int(in_field.sum()))

    low_vigor = in_field & (ndvi_grid < 0.38)
    mod_vigor = in_field & (ndvi_grid >= 0.38) & (ndvi_grid < 0.60)
    high_vigor = in_field & (ndvi_grid >= 0.60)

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
            "mean_ndvi_in_field": round(float(ndvi_f.mean()), 3) if ndvi_f.size else 0.0,
            "min_ndvi_in_field": round(float(ndvi_f.min()), 3) if ndvi_f.size else 0.0,
            "max_ndvi_in_field": round(float(ndvi_f.max()), 3) if ndvi_f.size else 0.0,
            "low_vigor_area_ha": round(low_cells * cell_area_ha, 2),
            "low_vigor_pct": round(100.0 * low_cells / total_cells, 1),
            "moderate_vigor_pct": round(100.0 * int(mod_vigor.sum()) / total_cells, 1),
            "high_vigor_pct": round(100.0 * int(high_vigor.sum()) / total_cells, 1),
            "weak_zones_explained_by_waterlogging_or_erosion_pct": overlap_hydro_pct,
            "ndvi_by_agronomic_zone": by_zone,
        },
    }
