"""Cálculo determinístico del Indicador de Confianza hidrológica (SDD-003 §3 / Regla R4).

Evalúa objetivamente la certeza de la simulación hidrológica y de escorrentía
combinando la precisión del relieve (DEM), la cartografía de suelos y el origen
de los datos de precipitación.
"""

from __future__ import annotations

from typing import Literal


def compute_confidence_indicator(
    source_id: str = "copernicus_glo30",
    resolution_m: float = 30.0,
    mean_slope_pct: float = 1.0,
    soil_source: str = "inta_regional",
    rain_source_type: str = "regional_design",
) -> dict:
    """Calcula el índice de confianza (Alto / Medio / Bajo) según SDD-003 §3.1.

    Parámetros:
    - source_id: identificador de la fuente del DEM ('copernicus_glo30', 'nasadem', 'drone', 'lidar', etc.).
    - resolution_m: resolución horizontal en metros (ej. 30.0 para Copernicus, <= 2.0 para dron/LiDAR).
    - mean_slope_pct: pendiente media del lote en porcentaje (0.3% es el umbral crítico de llanura).
    - soil_source: fuente del suelo ('local_survey', 'inta_detailed', 'inta_regional', 'default').
    - rain_source_type: origen de la lluvia ('gauge', 'regional_design', 'satellite_nasa').

    Retorna un diccionario con:
    - level: 'alto' | 'medio' | 'bajo'
    - score: float entre 0.0 y 1.0
    - reasons: list[str] con motivos técnicos concretos sin tecnicismos oscuros
    - relief_note: str
    - soil_note: str
    - rain_note: str
    """
    reasons: list[str] = []

    # 1. Componente Relieve (peso 0.40)
    is_high_res_dem = resolution_m <= 2.5 or source_id.lower() in ("drone", "lidar", "dron_local", "uploaded_highres")
    is_flat_plain = mean_slope_pct < 0.3

    if is_high_res_dem:
        score_relief = 0.95
        relief_note = f"DEM local alta precisión ({resolution_m:.1f} m)"
        reasons.append("Relieve local de alta resolución (error vertical submétrico)")
    elif is_flat_plain:
        score_relief = 0.35
        relief_note = f"Copernicus GLO-30 ({resolution_m:.0f} m)"
        reasons.append(
            f"Relieve {resolution_m:.0f} m en llanura extremadamente plana ({mean_slope_pct:.2f}%): "
            "error vertical de ±2 m condiciona la dirección de micro-escurrimientos"
        )
    else:
        score_relief = 0.70
        relief_note = f"Copernicus GLO-30 ({resolution_m:.0f} m)"
        reasons.append(f"Relieve satelital Copernicus {resolution_m:.0f} m con pendiente moderada ({mean_slope_pct:.1f}%)")

    # 2. Componente Suelo (peso 0.30)
    soil_lower = soil_source.lower()
    if soil_lower in ("local_survey", "inta_detailed", "suelo_analisis_local"):
        score_soil = 0.90
        soil_note = "Cartografía INTA 1:50.000 / Análisis físico de suelo"
        reasons.append("Suelo validado con análisis local o cartografía de detalle")
    elif soil_lower in ("default", "unconfirmed", "omision"):
        score_soil = 0.40
        soil_note = "Parámetro por omisión sin confirmación"
        reasons.append("Parámetro de suelo por omisión sin confirmación edafológica en campo")
    else:
        score_soil = 0.65
        soil_note = "Carta INTA 1:100.000 / HYSOGs250m"
        reasons.append("Suelo grupo hidrológico inferido por carta INTA regional")

    # 3. Componente Precipitación (peso 0.30)
    rain_lower = rain_source_type.lower()
    if rain_lower in ("gauge", "pluviometro", "local_pluviometer"):
        score_rain = 0.95
        rain_note = "Pluviómetro local de campo"
        reasons.append("Precipitación registrada in situ con serie temporal continua")
    elif rain_lower in ("satellite_nasa", "nasa_power", "satellite", "gpcp"):
        score_rain = 0.45
        rain_note = "NASA POWER (~55 km)"
        reasons.append("Dato satelital global (~55 km) con incertidumbre espacial en tormentas convectivas")
    else:
        score_rain = 0.75
        rain_note = "Diseño regional IDF INA"
        reasons.append("Curva IDF regional transpuesta (error típico ±20%)")

    # Ponderación global
    final_score = round(0.40 * score_relief + 0.30 * score_soil + 0.30 * score_rain, 2)

    level: Literal["alto", "medio", "bajo"]
    if final_score >= 0.80 and score_relief >= 0.60:
        level = "alto"
    elif final_score >= 0.55 and not (is_flat_plain and not is_high_res_dem):
        level = "medio"
    else:
        level = "bajo"

    return {
        "level": level,
        "score": final_score,
        "reasons": reasons,
        "relief_note": relief_note,
        "soil_note": soil_note,
        "rain_note": rain_note,
    }
