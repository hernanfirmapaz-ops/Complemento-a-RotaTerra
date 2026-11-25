"""Cálculo determinístico del Indicador de Confianza hidrológica (SDD-003 §3 / Regla R4).

Evalúa objetivamente la certeza de la simulación hidrológica y de escorrentía
combinando la precisión del relieve (DEM), la cartografía de suelos y el origen
de los datos de precipitación.
"""

from __future__ import annotations

from typing import Literal

from geoprocessing.supuestos import SUPUESTO_CUENCA_TRUNCADA_PENALIZACION_CONFIANZA


def compute_confidence_indicator(
    source_id: str = "copernicus_glo30",
    resolution_m: float = 30.0,
    mean_slope_pct: float | None = 1.0,
    soil_source: str | None = "default",
    rain_source_type: str = "manual",
    upstream_catchment_truncated: bool = False,
) -> dict:
    """Calcula el índice de confianza (Alto / Medio / Bajo) según SDD-003 §3.1.

    Parámetros:
    - source_id: identificador de la fuente del DEM ('copernicus_glo30', 'nasadem', 'drone', 'lidar', etc.).
    - resolution_m: resolución horizontal en metros (ej. 30.0 para Copernicus, <= 2.0 para dron/LiDAR).
    - mean_slope_pct: pendiente media del lote en porcentaje (0.3% es el umbral crítico de llanura, o None si falta el dato).
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

    res_m = max(0.5, float(resolution_m))

    # 1. Componente Relieve (peso 0.40)
    is_high_res_dem = res_m <= 2.5 or (source_id or "").lower() in ("drone", "lidar", "dron_local", "uploaded_highres")

    if mean_slope_pct is None:
        is_flat_plain = False
        score_relief = 0.40
        relief_note = (
            f"DEM local alta precisión ({res_m:.1f} m) · pendiente sin dato"
            if is_high_res_dem
            else f"Copernicus GLO-30 ({res_m:.0f} m) · pendiente sin dato"
        )
        reasons.append("Pendiente media del lote sin dato; relieve sin confirmación topográfica")
    else:
        slope_pct = max(0.0, float(mean_slope_pct))
        is_flat_plain = slope_pct < 0.3

        if is_high_res_dem:
            score_relief = 0.95
            relief_note = f"DEM local alta precisión ({res_m:.1f} m)"
            reasons.append("Relieve local de alta resolución (error vertical submétrico)")
        elif is_flat_plain:
            score_relief = 0.35
            relief_note = f"Copernicus GLO-30 ({res_m:.0f} m)"
            reasons.append(
                f"Relieve {res_m:.0f} m en llanura extremadamente plana ({slope_pct:.2f}%): "
                "error vertical de ±2 m condiciona la dirección de micro-escurrimientos"
            )
        else:
            score_relief = 0.70
            relief_note = f"Copernicus GLO-30 ({res_m:.0f} m)"
            reasons.append(f"Relieve satelital Copernicus {res_m:.0f} m con pendiente moderada ({slope_pct:.1f}%)")

    # 2. Componente Suelo (peso 0.30)
    # Cada fuente declara exactamente de dónde sale el dato: nunca se atribuye
    # el suelo a una fuente que no se consultó (AGENTS.md, regla de fuentes).
    soil_key = (soil_source or "default").lower()
    soil_info = SOIL_SOURCES.get(soil_key, SOIL_SOURCES["default"])
    score_soil = soil_info["score"]
    soil_note = soil_info["note"]
    reasons.append(soil_info["reason"])

    # 3. Componente Precipitación (peso 0.30)
    rain_key = (rain_source_type or "manual").lower()
    rain_info = RAIN_SOURCES.get(rain_key, RAIN_SOURCES["manual"])
    score_rain = rain_info["score"]
    rain_note = rain_info["note"]
    reasons.append(rain_info["reason"])

    # Ponderación global
    final_score = round(0.40 * score_relief + 0.30 * score_soil + 0.30 * score_rain, 2)

    if upstream_catchment_truncated:
        penalty = float(SUPUESTO_CUENCA_TRUNCADA_PENALIZACION_CONFIANZA.valor)
        final_score = max(0.10, round(final_score - penalty, 2))
        reasons.append("Cuenca de aporte externa truncada al límite de 10 km (caudal y volumen entrante son un piso mínimo)")

    level: Literal["alto", "medio", "bajo"]
    if final_score >= 0.80 and score_relief >= 0.60 and not upstream_catchment_truncated:
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


# Fuentes de suelo reconocidas. Una clave desconocida cae en "default".
SOIL_SOURCES: dict[str, dict] = {
    "local_survey": {"score": 0.90, "note": "Análisis de suelo del lote",
                     "reason": "Suelo validado con análisis físico local"},
    "suelo_analisis_local": {"score": 0.90, "note": "Análisis de suelo del lote",
                             "reason": "Suelo validado con análisis físico local"},
    "inta_detailed": {"score": 0.85, "note": "Carta de suelos INTA de detalle (≤ 1:50.000)",
                      "reason": "Grupo hidrológico derivado de cartografía INTA de detalle"},
    "inta_regional": {"score": 0.65, "note": "Carta de suelos INTA 1:100.000",
                      "reason": "Grupo hidrológico derivado de carta INTA regional (mezcla lomas y bajos)"},
    "soilgrids": {"score": 0.55, "note": "SoilGrids 250 m (ISRIC)",
                  "reason": "Textura estimada por SoilGrids (modelo global, 250 m)"},
    "hysogs": {"score": 0.55, "note": "HYSOGs250m (NASA ORNL DAAC)",
               "reason": "Grupo hidrológico global HYSOGs250m (250 m)"},
    "user_selected": {"score": 0.45, "note": "Grupo hidrológico elegido por el usuario",
                      "reason": "Grupo hidrológico elegido por el usuario, sin confirmar con datos de suelo"},
    "default": {"score": 0.40, "note": "Suelo por omisión, sin confirmar",
                "reason": "No hay fuente de suelos conectada: grupo hidrológico por omisión, sin confirmar"},
}

# Fuentes de lluvia reconocidas. Una clave desconocida cae en "manual".
RAIN_SOURCES: dict[str, dict] = {
    "gauge": {"score": 0.95, "note": "Pluviómetro local de campo",
              "reason": "Precipitación registrada en el lote"},
    "pluviometro": {"score": 0.95, "note": "Pluviómetro local de campo",
                    "reason": "Precipitación registrada en el lote"},
    "local_pluviometer": {"score": 0.95, "note": "Pluviómetro local de campo",
                          "reason": "Precipitación registrada en el lote"},
    "smn": {"score": 0.75, "note": "Estación SMN (serie cargada por el usuario)",
            "reason": "Lluvia medida en una estación SMN, a distancia del lote"},
    "chirps": {"score": 0.55, "note": "CHIRPS (~5 km)",
               "reason": "Lluvia satelital con ajuste por estaciones (~5 km)"},
    "imerg": {"score": 0.55, "note": "NASA GPM IMERG (~10 km)",
              "reason": "Lluvia satelital (~10 km): subestima picos convectivos sobre el lote"},
    "era5-land": {"score": 0.50, "note": "ERA5-Land (~9 km)",
                  "reason": "Reanálisis (~9 km): no es una medición en el lote"},
    "nasa_power": {"score": 0.45, "note": "NASA POWER (~55 km)",
                   "reason": "Reanálisis regional (~55 km) con incertidumbre en tormentas convectivas"},
    "satellite_nasa": {"score": 0.45, "note": "NASA POWER (~55 km)",
                       "reason": "Reanálisis regional (~55 km) con incertidumbre en tormentas convectivas"},
    "gpcp": {"score": 0.45, "note": "NASA POWER (~55 km)",
             "reason": "Reanálisis regional (~55 km) con incertidumbre en tormentas convectivas"},
    "manual": {"score": 0.75, "note": "Tormenta de diseño elegida por el usuario",
               "reason": "Escenario hipotético de lluvia: no es un evento medido"},
    "regional_design": {"score": 0.75, "note": "Tormenta de diseño elegida por el usuario",
                        "reason": "Escenario hipotético de lluvia: no es un evento medido"},
}
