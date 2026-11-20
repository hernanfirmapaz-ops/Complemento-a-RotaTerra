"""Eventos de precipitación y validación de series temporales CSV (SDD §4.4, §5.3 y §11.1).

Regla obligatoria SDD §5.3:
    Cada lluvia importada debe incluir `source`, `source_product`, `spatial_resolution`,
    `temporal_resolution`, `valid_time_start`, `valid_time_end`, `downloaded_at`, `units`,
    `quality_flag` y `uncertainty_note`.

Regla obligatoria SDD §4.4:
    No inventar intensidad a partir de la lluvia total. Si solo se dispone del acumulado,
    el sistema puede estimar volumen de escorrentía por evento, pero debe advertir que no
    conoce el patrón temporal ni puede reconstruir con rigor el avance del agua en el tiempo.
"""

from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

EXTREME_INTENSITY_MM_H = 120.0  # umbral de revisión de intensidad horaria equivalente (no se elimina)
TOTAL_MISMATCH_TOLERANCE_MM = 0.5


class RainfallValidationError(ValueError):
    """El evento de lluvia o el archivo CSV no cumple las validaciones del SDD §11.1."""


SOURCE_PRESETS: dict[str, dict[str, str]] = {
    "gauge": {
        "source": "Pluviómetro del establecimiento",
        "source_product": "Registro local de parcela / casco",
        "spatial_resolution": "Puntual (estación local)",
        "temporal_resolution": "Según intervalo de registro (5–60 min) o acumulado",
        "uncertainty_note": "Mejor representatividad local; verificar ubicación, nivelación y ausencia de obstrucciones.",
    },
    "SMN": {
        "source": "Servicio Meteorológico Nacional (SMN Argentina · Referencia de estación)",
        "source_product": "Registro de estación pluviométrica (sin conexión de datos en tiempo real)",
        "spatial_resolution": "Puntual (estación)",
        "temporal_resolution": "Diaria / horaria según planilla",
        "uncertainty_note": "Referencia geográfica de estación; no hay conexión automática en tiempo real.",
    },
    "NASA_POWER": {
        "source": "NASA POWER (MERRA-2 / GPCP · ~55 km)",
        "source_product": "NASA POWER Agroclimatology Daily (PRECTOTCORR)",
        "spatial_resolution": "0,5° (~55 km)",
        "temporal_resolution": "Diaria",
        "uncertainty_note": "Lluvia regional estimada (~55 km), no es la medición de su campo.",
    },
    "IMERG": {
        "source": "NASA GPM IMERG",
        "source_product": "GPM_3IMERG (V07B)",
        "spatial_resolution": "0,1° (~10 km)",
        "temporal_resolution": "30 minutos",
        "uncertainty_note": "Estimación satelital gridded: el píxel es mucho mayor que un lote agrícola; no interpolar a sublote.",
    },
    "CHIRPS": {
        "source": "Climate Hazards Center (UC Santa Barbara)",
        "source_product": "CHIRPS v3",
        "spatial_resolution": "0,05° (~5,5 km)",
        "temporal_resolution": "Diaria",
        "uncertainty_note": "Resolución diaria: útil para contexto histórico, no reconstruye intensidad intradiaria.",
    },
    "ERA5-Land": {
        "source": "Copernicus Climate Data Store (ECMWF)",
        "source_product": "ERA5-Land hourly reanalysis",
        "spatial_resolution": "0,1° (~9 km)",
        "temporal_resolution": "Horaria",
        "uncertainty_note": "Reanálisis regional: no equivale a una observación pluviométrica en el lote.",
    },
    "manual": {
        "source": "Ingreso manual de escenario",
        "source_product": "Valor hipotético / diseño",
        "spatial_resolution": "Uniforme sobre el área de análisis",
        "temporal_resolution": "Acumulado de evento",
        "uncertainty_note": "Escenario exploratorio definido por el usuario para análisis de sensibilidad.",
    },
}


@dataclass
class RainfallInterval:
    timestamp: str
    precipitation_mm: float
    interval_minutes: int
    station_id: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CsvSeriesReport:
    intervals: list[RainfallInterval]
    total_mm: float
    interval_minutes: int
    start_at: str
    end_at: str
    max_interval_mm: float
    max_intensity_mm_h: float
    gaps_detected: int
    extreme_intervals_count: int
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_iso_tz(value: str, line_no: int) -> datetime:
    txt = value.strip()
    if txt.endswith("Z"):
        txt = txt[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError as err:
        raise RainfallValidationError(
            f"Línea {line_no}: timestamp inválido '{value}'. Usá formato ISO-8601 con zona horaria "
            "(ej. 2026-11-18T14:00:00-03:00)."
        ) from err
    if dt.tzinfo is None:
        raise RainfallValidationError(
            f"Línea {line_no}: el timestamp '{value}' no incluye zona horaria (ej. -03:00 o Z)."
        )
    return dt


def parse_rainfall_csv(
    content: bytes | str,
    declared_total_mm: float | None = None,
) -> CsvSeriesReport:
    """Valida e importa una serie temporal de precipitación en CSV (SDD §11.1)."""
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as err:
            raise RainfallValidationError(f"El CSV debe estar codificado en UTF-8: {err}") from err
    else:
        text = content

    reader = csv.DictReader(io.StringIO(text.strip()))
    if not reader.fieldnames:
        raise RainfallValidationError("El archivo CSV está vacío o no tiene encabezados.")

    headers = {h.strip() for h in reader.fieldnames if h}
    required = {"timestamp", "precipitation_mm", "interval_minutes"}
    missing = required - headers
    if missing:
        raise RainfallValidationError(
            f"Faltan columnas obligatorias en el CSV: {', '.join(sorted(missing))}. "
            "Formato esperado: timestamp,precipitation_mm,interval_minutes,station_id"
        )

    parsed_rows: list[tuple[datetime, RainfallInterval]] = []
    seen_timestamps: set[datetime] = set()

    for idx, row in enumerate(reader, start=2):
        if not row or all((v is None or not str(v).strip()) for v in row.values()):
            continue
        dt = _parse_iso_tz(str(row.get("timestamp", "")), idx)
        if dt in seen_timestamps:
            raise RainfallValidationError(f"Línea {idx}: timestamp duplicado '{row.get('timestamp')}'.")
        seen_timestamps.add(dt)

        try:
            p_mm = float(str(row.get("precipitation_mm", "")).strip())
        except ValueError as err:
            raise RainfallValidationError(
                f"Línea {idx}: 'precipitation_mm' no es numérico ('{row.get('precipitation_mm')}')."
            ) from err
        if p_mm < 0 or not (p_mm < 2000):
            raise RainfallValidationError(
                f"Línea {idx}: precipitación inválida ({p_mm} mm). Debe ser numérica y no negativa."
            )

        try:
            int_min = int(float(str(row.get("interval_minutes", "")).strip()))
        except ValueError as err:
            raise RainfallValidationError(
                f"Línea {idx}: 'interval_minutes' debe ser un entero positivo."
            ) from err
        if int_min <= 0 or int_min > 1440:
            raise RainfallValidationError(
                f"Línea {idx}: 'interval_minutes' ({int_min}) fuera de rango (1..1440 min)."
            )

        station = (str(row.get("station_id") or "").strip()) or None
        parsed_rows.append((
            dt,
            RainfallInterval(
                timestamp=dt.isoformat(),
                precipitation_mm=round(p_mm, 3),
                interval_minutes=int_min,
                station_id=station,
            ),
        ))

    if not parsed_rows:
        raise RainfallValidationError("El archivo CSV no contiene registros de precipitación.")

    parsed_rows.sort(key=lambda item: item[0])
    intervals = [item[1] for item in parsed_rows]
    dts = [item[0] for item in parsed_rows]

    unique_intervals = {iv.interval_minutes for iv in intervals}
    if len(unique_intervals) > 1:
        raise RainfallValidationError(
            f"Intervalos incoherentes en el CSV: se mezclaron pasos de {sorted(unique_intervals)} minutos."
        )
    step_min = intervals[0].interval_minutes

    warnings: list[str] = []
    gaps = 0
    for i in range(1, len(dts)):
        delta_min = (dts[i] - dts[i - 1]).total_seconds() / 60.0
        if abs(delta_min - step_min) > 0.1:
            gaps += 1

    if gaps > 0:
        warnings.append(
            f"Se detectaron {gaps} huecos temporales en la serie respecto del intervalo de {step_min} min. "
            "No se rellenaron ni inventaron valores faltantes."
        )

    extreme_count = 0
    max_iv_mm = 0.0
    max_int_mm_h = 0.0
    for iv in intervals:
        if iv.precipitation_mm > max_iv_mm:
            max_iv_mm = iv.precipitation_mm
        intensity = iv.precipitation_mm * (60.0 / iv.interval_minutes)
        if intensity > max_int_mm_h:
            max_int_mm_h = intensity
        if intensity >= EXTREME_INTENSITY_MM_H:
            extreme_count += 1

    if extreme_count > 0:
        warnings.append(
            f"Se identificaron {extreme_count} intervalos con intensidad equivalente >= "
            f"{EXTREME_INTENSITY_MM_H:.0f} mm/h (máx. {max_int_mm_h:.1f} mm/h). "
            "Revisar posibles errores de lectura; los valores se conservaron sin eliminarlos."
        )

    total_csv = round(sum(iv.precipitation_mm for iv in intervals), 2)
    if declared_total_mm is not None and abs(total_csv - declared_total_mm) > TOTAL_MISMATCH_TOLERANCE_MM:
        warnings.append(
            f"La suma de los intervalos del CSV ({total_csv:.2f} mm) difiere del acumulado declarado "
            f"({declared_total_mm:.2f} mm). Se utiliza la suma verificada de la serie ({total_csv:.2f} mm)."
        )

    return CsvSeriesReport(
        intervals=intervals,
        total_mm=total_csv,
        interval_minutes=step_min,
        start_at=dts[0].isoformat(),
        end_at=dts[-1].isoformat(),
        max_interval_mm=round(max_iv_mm, 2),
        max_intensity_mm_h=round(max_int_mm_h, 2),
        gaps_detected=gaps,
        extreme_intervals_count=extreme_count,
        warnings=warnings,
    )


def build_event_metadata(
    source_type: str,
    total_mm: float,
    start_at: str | None,
    end_at: str | None,
    has_time_series: bool,
    interval_minutes: int | None,
    custom_source_product: str | None = None,
    custom_spatial_resolution: str | None = None,
    quality_flag: str | None = None,
    custom_uncertainty_note: str | None = None,
) -> tuple[dict, list[str]]:
    """Construye el bloque completo de metadatos exigido por SDD §5.3 y las advertencias asociadas."""
    preset = SOURCE_PRESETS.get(source_type, SOURCE_PRESETS["manual"])
    now_str = datetime.now(timezone.utc).isoformat(timespec="seconds")
    t_res = (
        f"Serie temporal cada {interval_minutes} min"
        if has_time_series and interval_minutes
        else "Acumulado total de evento (sin desagregación temporal)"
    )

    warnings: list[str] = []
    if not has_time_series:
        warnings.append(
            "Solo se dispone de la lluvia acumulada del evento: no se inventa intensidad intradiaria "
            "ni se reconstruye la evolución temporal de la lámina de agua (SDD §4.4)."
        )
    if source_type in ("IMERG", "CHIRPS", "ERA5-Land", "SMN", "NASA_POWER"):
        warnings.append(
            f"Fuente regional ({preset['source']} · {custom_spatial_resolution or preset['spatial_resolution']}): "
            "no representa variaciones sublote ni equivale a un pluviómetro dentro de la parcela (SDD §5.3)."
        )

    if quality_flag:
        flag = quality_flag
    elif source_type == "gauge":
        flag = "observado_local"
    elif source_type == "NASA_POWER":
        flag = "modelo_reanalisis_regional"
    elif source_type == "IMERG":
        flag = "satelital_estimado"
    else:
        flag = "estimado_o_escenario"

    metadata = {
        "source": preset["source"],
        "source_type": source_type,
        "source_product": custom_source_product or preset["source_product"],
        "spatial_resolution": custom_spatial_resolution or preset["spatial_resolution"],
        "temporal_resolution": t_res,
        "valid_time_start": start_at or now_str,
        "valid_time_end": end_at or start_at or now_str,
        "downloaded_at": now_str,
        "units": "mm",
        "quality_flag": flag,
        "uncertainty_note": custom_uncertainty_note or preset["uncertainty_note"],
        "total_mm": round(float(total_mm), 2),
        "has_time_series": has_time_series,
    }
    return metadata, warnings
