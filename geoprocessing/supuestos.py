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

# --- Balance Hídrico y Evapotranspiración FAO-56 ---
SUPUESTO_FAO56_KC_BARBECHO = Supuesto(
    clave="fao56_kc_barbecho",
    valor=0.25,
    unidad="adimensional",
    motivo="Coeficiente de cultivo Kc para suelo en descanso, rastrojo o barbecho invernal.",
    fuente_referencia="FAO-56 (Allen et al. 1998, Tabla 12, pág. 114); editable por el usuario.",
)

SUPUESTO_MESES_ESTACION_REPOSO_SUR = Supuesto(
    clave="meses_estacion_reposo_sur",
    valor=(5, 6, 7, 8, 9),
    unidad="meses calendario [1..12]",
    motivo="Meses de la estación de reposo / latencia (mayo a septiembre) en el hemisferio sur templado para clasificar la condición de humedad antecedente (AMC).",
    fuente_referencia="Criterio agronómico estacional templado hemisferio sur adaptado a USDA-SCS (1972, NEH-4 Tabla 4.2, pág. 4.12); editable por el usuario.",
)

SUPUESTO_MESES_ESTACION_REPOSO_NORTE = Supuesto(
    clave="meses_estacion_reposo_norte",
    valor=(11, 12, 1, 2, 3),
    unidad="meses calendario [1..12]",
    motivo="Meses de la estación de reposo / latencia (noviembre a marzo) en el hemisferio norte templado para clasificar la condición de humedad antecedente (AMC).",
    fuente_referencia="USDA-SCS (1972, NEH-4 Tabla 4.2, pág. 4.12); editable por el usuario.",
)


# --- Condición de Humedad Antecedente (AMC) USDA-SCS NEH-4 Tabla 4.2 ---
SUPUESTO_AMC_REPOSO_SECO_MM = Supuesto(
    clave="amc_reposo_seco_mm",
    valor=12.7,
    unidad="mm",
    motivo="Umbral superior de lluvia acumulada en 5 días para condición seca (AMC I) en estación de reposo (dormant, < 0.5 pulg).",
    fuente_referencia="USDA-SCS (1972) National Engineering Handbook, Section 4: Hydrology (NEH-4), Tabla 4.2 (pág. 4.12); editable por el usuario.",
)

SUPUESTO_AMC_REPOSO_HUMEDO_MM = Supuesto(
    clave="amc_reposo_humedo_mm",
    valor=27.9,
    unidad="mm",
    motivo="Umbral inferior de lluvia acumulada en 5 días para condición húmeda (AMC III) en estación de reposo (dormant, > 1.1 pulg).",
    fuente_referencia="USDA-SCS (1972) National Engineering Handbook, Section 4: Hydrology (NEH-4), Tabla 4.2 (pág. 4.12); editable por el usuario.",
)

SUPUESTO_AMC_CRECIMIENTO_SECO_MM = Supuesto(
    clave="amc_crecimiento_seco_mm",
    valor=35.6,
    unidad="mm",
    motivo="Umbral superior de lluvia acumulada en 5 días para condición seca (AMC I) en estación de crecimiento (growing, < 1.4 pulg).",
    fuente_referencia="USDA-SCS (1972) National Engineering Handbook, Section 4: Hydrology (NEH-4), Tabla 4.2 (pág. 4.12); editable por el usuario.",
)

SUPUESTO_AMC_CRECIMIENTO_HUMEDO_MM = Supuesto(
    clave="amc_crecimiento_humedo_mm",
    valor=53.3,
    unidad="mm",
    motivo="Umbral inferior de lluvia acumulada en 5 días para condición húmeda (AMC III) en estación de crecimiento (growing, > 2.1 pulg).",
    fuente_referencia="USDA-SCS (1972) National Engineering Handbook, Section 4: Hydrology (NEH-4), Tabla 4.2 (pág. 4.12); editable por el usuario.",
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
