"""Clasificación textural USDA y grupo hidrológico aproximado por textura (spec 004).

Referencias:
- USDA Soil Survey Manual (2017), triángulo textural de 12 clases.
- Rawls, W. J., Brakensiek, D. L. & Saxton, K. E. (1982). Estimation of soil water properties.
  Transactions of the ASAE 25(5): 1316–1320. Relación textura → grupo hidrológico usada en
  la guía SCS para estimar la Curva Número cuando no hay datos de conductividad.
"""

from __future__ import annotations

# Nombre de la clase en español rioplatense → grupo hidrológico aproximado.
TEXTURE_TO_GROUP: dict[str, str] = {
    "Arenosa": "A",
    "Arenosa franca": "A",
    "Franco arenosa": "A",
    "Franca": "B",
    "Franco limosa": "B",
    "Limosa": "B",
    "Franco arcillo arenosa": "C",
    "Franco arcillosa": "D",
    "Franco arcillo limosa": "D",
    "Arcillo arenosa": "D",
    "Arcillo limosa": "D",
    "Arcillosa": "D",
}


def usda_texture_class(sand_pct: float, silt_pct: float, clay_pct: float) -> str:
    """Devuelve la clase textural USDA para porcentajes de arena, limo y arcilla.

    Los porcentajes se normalizan a 100 antes de clasificar. Las reglas siguen los límites
    del triángulo textural del USDA (Soil Survey Manual).
    """
    total = sand_pct + silt_pct + clay_pct
    if total <= 0:
        raise ValueError("La suma de arena, limo y arcilla debe ser mayor que 0.")
    sand = 100.0 * sand_pct / total
    silt = 100.0 * silt_pct / total
    clay = 100.0 * clay_pct / total

    if silt + 1.5 * clay < 15:
        return "Arenosa"
    if silt + 1.5 * clay >= 15 and silt + 2 * clay < 30:
        return "Arenosa franca"
    if (7 <= clay < 20 and sand > 52 and silt + 2 * clay >= 30) or (clay < 7 and silt < 50 and silt + 2 * clay >= 30):
        return "Franco arenosa"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52:
        return "Franca"
    if (silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12):
        return "Franco limosa"
    if silt >= 80 and clay < 12:
        return "Limosa"
    if 20 <= clay < 35 and silt < 28 and sand > 45:
        return "Franco arcillo arenosa"
    if 27 <= clay < 40 and 20 < sand <= 45:
        return "Franco arcillosa"
    if 27 <= clay < 40 and sand <= 20:
        return "Franco arcillo limosa"
    if clay >= 35 and sand > 45:
        return "Arcillo arenosa"
    if clay >= 40 and silt >= 40:
        return "Arcillo limosa"
    return "Arcillosa"


def hydrologic_group_from_texture(texture_class: str) -> str:
    """Grupo hidrológico aproximado (A–D) a partir de la clase textural."""
    try:
        return TEXTURE_TO_GROUP[texture_class]
    except KeyError as error:
        raise ValueError(f"Clase textural desconocida: {texture_class}") from error
