"""Archivo único de supuestos del modelo agronómico e hidrológico.

Cada supuesto declara: clave, valor, unidad, motivo y si es editable por el usuario.
Regla metodológica (docs/metodologia.md, sección 2):
Todo número que no sea dato con fuente consultada o null, debe ser un
supuesto editable declarado aquí con su justificación explícita.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Supuesto:
    clave: str
    valor: Any
    unidad: str
    motivo: str
    fuente_referencia: str | None = None
    editable: bool = True


# --- Umbrales de Vigor Vegetativo (NDVI Sentinel-2) ---
# En cultivos extensivos de la región pampeana / San Luis:
# NDVI < 0.38 suele corresponder a suelo desnudo, rastrojo o cultivo muy degradado / estresado hídricamente.
# NDVI 0.38 a 0.60 corresponde a vigor vegetativo moderado o cobertura parcial.
# NDVI >= 0.60 corresponde a canopeo cerrado con vigor vegetativo alto.
SUPUESTO_NDVI_UMBRAL_BAJO_VIGOR = Supuesto(
    clave="ndvi_umbral_bajo_vigor",
    valor=0.38,
    unidad="adimensional [-1, 1]",
    motivo="Umbral agronómico de corte inferior para clasificar zonas con cobertura escasa o estrés severo.",
    fuente_referencia="Supuesto empírico regional agronómico (pendiente calibración con índice GNDVI o validación a campo)",
)

SUPUESTO_NDVI_UMBRAL_ALTO_VIGOR = Supuesto(
    clave="ndvi_umbral_alto_vigor",
    valor=0.60,
    unidad="adimensional [-1, 1]",
    motivo="Umbral agronómico de corte superior para canopeo desarrollado y biomasa activa alta.",
    fuente_referencia="Supuesto empírico regional agronómico",
)
