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

# --- Erosión Hídrica USLE / RUSLE ---
SUPUESTO_I30_RATIO_PRECIPITACION = Supuesto(
    clave="i30_ratio_precipitacion",
    valor=0.65,
    unidad="1/h",
    motivo="Relación empírica supuesta para estimar la intensidad máxima en 30 minutos (i30 mm/h) como 0.65 * P (acotada a máx 75 mm/h) cuando no se dispone de pluviograma o estación meteorológica.",
    fuente_referencia="Supuesto empírico declarado (la cita histórica a Lombardi Neto correlacionaba EI30 con índice de Fournier p^2/P, no i30 con P). Editable por el usuario.",
)

SUPUESTO_MATERIA_ORGANICA_PCT = Supuesto(
    clave="materia_organica_pct",
    valor=2.5,
    unidad="%",
    motivo="Contenido medio representativo de materia orgánica en horizonte superficial (0-30 cm) para suelos agrícolas pampeanos cuando no se dispone de análisis de laboratorio o SoilGrids soc.",
    fuente_referencia="Valor típico regional agronómico pampeano (Wischmeier & Smith 1978); editable por el usuario.",
)

SUPUESTO_I30_TOPE_MAX_MM_H = Supuesto(
    clave="i30_tope_max_mm_h",
    valor=75.0,
    unidad="mm/h",
    motivo="Tope superior para la intensidad máxima en 30 minutos (i30) estimada a partir de precipitación acumulada de tormenta.",
    fuente_referencia="Supuesto empírico conservador para clima templado/subhúmedo pampeano; editable por el usuario.",
)

SUPUESTO_USLE_ESTRUCTURA_CODIGO = Supuesto(
    clave="usle_estructura_codigo",
    valor=2,
    unidad="código [1 a 4]",
    motivo="Código de estructura del suelo para el nomograma de Wischmeier & Smith (1978, pág. 13): 1=muy fino granular, 2=fino granular, 3=mediano o grueso, 4=en bloques o masivo.",
    fuente_referencia="USDA Agriculture Handbook 537 (Wischmeier & Smith 1978, pág. 13); editable por el usuario.",
)

SUPUESTO_USLE_PERMEABILIDAD_CODIGO = Supuesto(
    clave="usle_permeabilidad_codigo",
    valor=3,
    unidad="código [1 a 6]",
    motivo="Código de permeabilidad del perfil para el nomograma de Wischmeier & Smith (1978, pág. 13): 1=rápida, 2=moderada a rápida, 3=moderada, 4=moderada a lenta, 5=lenta, 6=muy lenta.",
    fuente_referencia="USDA Agriculture Handbook 537 (Wischmeier & Smith 1978, pág. 13); editable por el usuario.",
)

SUPUESTO_CARCAVAS_UMBRAL_SPI = Supuesto(
    clave="carcavas_umbral_spi",
    valor=2.5,
    unidad="adimensional",
    motivo="Umbral de corte del Índice de Poder de Corriente (Stream Power Index, SPI) para identificar celdas con alta convergencia de flujo y energía erosiva.",
    fuente_referencia="Moore et al. (1991, Hydrological Processes 5:3–30); editable por el usuario.",
)

SUPUESTO_CARCAVAS_UMBRAL_PERDIDA_T_HA = Supuesto(
    clave="carcavas_umbral_perdida_t_ha",
    valor=1.5,
    unidad="t/ha",
    motivo="Pérdida de suelo local mínima en el evento necesaria para activar focos de desprendimiento y formación de cárcavas efímeras.",
    fuente_referencia="Supuesto empírico agronómico conservador; editable por el usuario.",
)

SUPUESTO_USLE_P_CONTOUR_DEFECTO = Supuesto(
    clave="usle_p_contour_defecto",
    valor=0.60,
    unidad="adimensional [0 a 1]",
    motivo="Factor P de cultivo en contorno por defecto cuando no se calcula en función de la pendiente.",
    fuente_referencia="USDA Agriculture Handbook 537 (Wischmeier & Smith 1978, pág. 35, Tabla 14).",
)

SUPUESTO_USLE_P_TERRAZAS = Supuesto(
    clave="usle_p_terrazas",
    valor=0.50,
    unidad="adimensional [0 a 1]",
    motivo="Factor P reductor por terrazas de absorción o de gradiente con desagüe protegido.",
    fuente_referencia="USDA Agriculture Handbook 537 (Wischmeier & Smith 1978, pág. 39, Tabla 15; orden de magnitud estimado).",
)

# Factores C de cobertura y manejo (orden de magnitud estimado a partir de USDA AH 537 Tabla 5; editable):
SUPUESTOS_USLE_C_FACTOR: dict[str, Supuesto] = {
    "soja_maiz_sd_buena": Supuesto(
        clave="usle_c_soja_maiz_sd_buena",
        valor=0.09,
        unidad="adimensional [0 a 1]",
        motivo="Siembra directa continua con más de 30% de cobertura de rastrojo en superficie.",
        fuente_referencia="Orden de magnitud estimado a partir de USDA AH 537 Tabla 5 (Wischmeier & Smith 1978); no es un valor de tabla directa ya que AH 537 define C por etapa fenológica. Cita regional: Behrends Kraemer et al. (2018), Cienc. Suelo 36(1): 124 (San Pedro).",
    ),
    "soja_maiz_convencional": Supuesto(
        clave="usle_c_soja_maiz_convencional",
        valor=0.34,
        unidad="adimensional [0 a 1]",
        motivo="Labranza convencional o reducida con escasa cobertura residual (<15%).",
        fuente_referencia="Orden de magnitud estimado a partir de USDA AH 537 Tabla 5 (Wischmeier & Smith 1978, pág. 21); no es un valor de tabla directa. Cita regional: Behrends Kraemer et al. (2018), Cienc. Suelo 36(1): 124.",
    ),
    "trigo_cereal_invierno_sd": Supuesto(
        clave="usle_c_trigo_cereal_invierno_sd",
        valor=0.06,
        unidad="adimensional [0 a 1]",
        motivo="Cereal de grano fino en siembra directa con alta densidad de tallos y rápida cobertura de canopeo.",
        fuente_referencia="Orden de magnitud estimado a partir de USDA AH 537 Tabla 5 (Wischmeier & Smith 1978, pág. 23); no es un valor de tabla directa.",
    ),
    "cultivo_cobertura_vicia_centeno": Supuesto(
        clave="usle_c_cultivo_cobertura_vicia_centeno",
        valor=0.03,
        unidad="adimensional [0 a 1]",
        motivo="Cultivo de servicios multiespecie (gramínea + leguminosa) con canopeo denso cerrado (>80% cobertura).",
        fuente_referencia="Orden de magnitud estimado a partir de USDA AH 537 Tabla 5-C (Wischmeier & Smith 1978); no es un valor de tabla directa.",
    ),
    "pastura_pradera_buena": Supuesto(
        clave="usle_c_pastura_pradera_buena",
        valor=0.015,
        unidad="adimensional [0 a 1]",
        motivo="Pastura perenne bien manejada con cobertura vegetal continua (>90%).",
        fuente_referencia="Orden de magnitud estimado a partir de USDA AH 537 Tabla 5-C (Wischmeier & Smith 1978); Cita regional: Behrends Kraemer et al. (2018), Cienc. Suelo 36(1): 124 miden C=0.07 ganadero.",
    ),
    "pastura_sobrepastoreada": Supuesto(
        clave="usle_c_pastura_sobrepastoreada",
        valor=0.18,
        unidad="adimensional [0 a 1]",
        motivo="Pastura degradada o con sobrepastoreo y parches de suelo desnudo.",
        fuente_referencia="Orden de magnitud estimado a partir de USDA AH 537 Tabla 5 (Wischmeier & Smith 1978); no es un valor de tabla directa.",
    ),
    "barbecho_con_rastrojo": Supuesto(
        clave="usle_c_barbecho_con_rastrojo",
        valor=0.14,
        unidad="adimensional [0 a 1]",
        motivo="Barbecho químico con rastrojo intacto del cultivo anterior.",
        fuente_referencia="Orden de magnitud estimado a partir de USDA AH 537 Tabla 5 (Wischmeier & Smith 1978); no es un valor de tabla directa.",
    ),
    "barbecho_suelo_desnudo": Supuesto(
        clave="usle_c_barbecho_suelo_desnudo",
        valor=0.55,
        unidad="adimensional [0 a 1]",
        motivo="Suelo laboreado o pulverizado sin cobertura protectora ni rugosidad residual.",
        fuente_referencia="Orden de magnitud estimado a partir de USDA AH 537 Tabla 5 (Wischmeier & Smith 1978, pág. 20); no es un valor de tabla directa.",
    ),
}

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

# --- Umbral de Encharcamiento Hidrodinámico 2D y Visualización 3D (Spec 013) ---
UMBRAL_ENCHARCAMIENTO_MOTOR_M = Supuesto(
    clave="umbral_encharcamiento_motor_m",
    valor=0.05,
    unidad="m",
    motivo="Umbral hidrológico mínimo de lámina de agua acumulada (5 cm) para considerar que una celda está encharcada / anegada en el solver 2D y la zonificación agronómica.",
    fuente_referencia="Modelo hidrodinámico 2D RotaTerra (shallow_water_2d.py / zonation.py)",
    editable=True,
)

# --- Relieve Base y Calibración Geodésica con Mojones IGN (Spec 014) ---
SUPUESTO_DEM_RADIO_BUSQUEDA_IGN_R1_KM = Supuesto(
    clave="dem_radio_busqueda_ign_r1_km",
    valor=25.0,
    unidad="km",
    motivo="Radio de búsqueda inicial de mojones de nivelación geométrica IGN alrededor del centroide del lote para calibración local de sesgo vertical.",
    fuente_referencia="Criterio geodésico zonal (Spec 014); editable por el usuario.",
    editable=True,
)

SUPUESTO_DEM_RADIO_BUSQUEDA_IGN_R2_KM = Supuesto(
    clave="dem_radio_busqueda_ign_r2_km",
    valor=50.0,
    unidad="km",
    motivo="Radio de búsqueda extendido de mojones de nivelación IGN si en R1 se encuentran menos del mínimo de mojones requeridos.",
    fuente_referencia="Criterio geodésico zonal (Spec 014); editable por el usuario.",
    editable=True,
)

SUPUESTO_DEM_MIN_MOJONES_IGN = Supuesto(
    clave="dem_min_mojones_ign",
    valor=3,
    unidad="mojones",
    motivo="Cantidad mínima de mojones de nivelación IGN dentro del radio de búsqueda para habilitar la estimación de sesgo local y calibración.",
    fuente_referencia="Criterio estadístico robusto de muestra mínima (Spec 014); editable por el usuario.",
    editable=True,
)

SUPUESTO_DEM_DIFERENCIA_DATUM_VERTICAL_M = Supuesto(
    clave="dem_diferencia_datum_vertical_m",
    valor=None,
    unidad="m",
    motivo="Diferencia teórica entre el cero oficial de nivelación nacional (Mar del Plata) y el geoide EGM2008. Al no disponerse de un modelo geoidal oficial milimétrico unificado de transformación en la región, no se fija un valor numérico a priori y la discrepancia se absorbe empíricamente en la mediana de residuos de calibración con mojones locales.",
    fuente_referencia="Supuesto metodológico (Spec 014 / docs/metodologia.md); no inventar cifra sin modelo de transformación oficial.",
    editable=False,
)

SUPUESTO_DEM_DISCREPANCIA_UMBRAL_M = Supuesto(
    clave="dem_discrepancia_umbral_m",
    valor=2.5,
    unidad="m",
    motivo="Umbral de discrepancia vertical absoluta entre GEM-15 DTM y Copernicus GLO-30 (|GEM − COP|) a partir del cual una celda se etiqueta como 'relieve incierto' en la capa de calidad dem_fuente. Diferencias superiores suelen indicar vegetación arbórea densa (contraste DSM vs DTM), discontinuidades de correlación o subsidencia local.",
    fuente_referencia="Decisión metodológica Spec 014 (Fusión Copernicus GLO-30 + GEM-15 DTM); Claude 22/11/2026 en Issue #73.",
    editable=True,
)


