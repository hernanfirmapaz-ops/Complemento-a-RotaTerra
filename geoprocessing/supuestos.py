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

# --- Límites de Seguridad y Procesamiento ---
SUPUESTO_SUPERFICIE_MAXIMA_LOTE_HA = Supuesto(
    clave="superficie_maxima_lote_ha",
    valor=2000.0,
    unidad="ha",
    motivo="Límite máximo de superficie por lote (2.000 ha) para prevenir desbordes de memoria y tiempo de procesamiento. Configurable mediante ROTATERRA_MAX_FIELD_AREA_HA.",
    fuente_referencia="Criterio de robustez de API (auditoría 21/11/2026, punto 9)",
)

SUPUESTO_LIMITE_DESCOMPRIMIDO_ZIP_MB = Supuesto(
    clave="limite_descomprimido_zip_mb",
    valor=50.0,
    unidad="MB",
    motivo="Límite máximo de tamaño descomprimido (50 MB) para archivos ZIP/KMZ para prevenir ataques de descompresión (zip bombs). Configurable mediante ROTATERRA_MAX_UNCOMPRESSED_ZIP_MB.",
    fuente_referencia="Criterio de seguridad de API (auditoría 21/11/2026, punto 9)",
)

