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
    fuente_referencia="Valor típico regional agronómico pampeano / INTA (Wischmeier & Smith 1978); editable por el usuario.",
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

# Factores C de cobertura y manejo (Wischmeier & Smith 1978, USDA AH 537, Capítulo 3, Tablas 5 y 5-C):
SUPUESTOS_USLE_C_FACTOR: dict[str, Supuesto] = {
    "soja_maiz_sd_buena": Supuesto(
        clave="usle_c_soja_maiz_sd_buena",
        valor=0.09,
        unidad="adimensional [0 a 1]",
        motivo="Siembra directa continua con más de 30% de cobertura de rastrojo en superficie.",
        fuente_referencia="USDA AH 537 Tabla 5-C (Wischmeier & Smith 1978); adaptaciones INTA Castelar / Pergamino para SD.",
    ),
    "soja_maiz_convencional": Supuesto(
        clave="usle_c_soja_maiz_convencional",
        valor=0.34,
        unidad="adimensional [0 a 1]",
        motivo="Labranza convencional o reducida con escasa cobertura residual (<15%).",
        fuente_referencia="USDA AH 537 Tabla 5 (Wischmeier & Smith 1978, pág. 21).",
    ),
    "trigo_cereal_invierno_sd": Supuesto(
        clave="usle_c_trigo_cereal_invierno_sd",
        valor=0.06,
        unidad="adimensional [0 a 1]",
        motivo="Cereal de grano fino en siembra directa con alta densidad de tallos y rápida cobertura de canopeo.",
        fuente_referencia="USDA AH 537 Tabla 5 (Wischmeier & Smith 1978, pág. 23).",
    ),
    "cultivo_cobertura_vicia_centeno": Supuesto(
        clave="usle_c_cultivo_cobertura_vicia_centeno",
        valor=0.03,
        unidad="adimensional [0 a 1]",
        motivo="Cultivo de servicios multiespecie (gramínea + leguminosa) con canopeo denso cerrado (>80% cobertura).",
        fuente_referencia="USDA AH 537 Tabla 5-C (Wischmeier & Smith 1978); Guías técnicas INTA.",
    ),
    "pastura_pradera_buena": Supuesto(
        clave="usle_c_pastura_pradera_buena",
        valor=0.015,
        unidad="adimensional [0 a 1]",
        motivo="Pastura perenne bien manejada con cobertura vegetal continua (>90%).",
        fuente_referencia="USDA AH 537 Tabla 5-C (Wischmeier & Smith 1978).",
    ),
    "pastura_sobrepastoreada": Supuesto(
        clave="usle_c_pastura_sobrepastoreada",
        valor=0.18,
        unidad="adimensional [0 a 1]",
        motivo="Pastura degradada o con sobrepastoreo y parches de suelo desnudo.",
        fuente_referencia="USDA AH 537 Tabla 5 (Wischmeier & Smith 1978).",
    ),
    "barbecho_con_rastrojo": Supuesto(
        clave="usle_c_barbecho_con_rastrojo",
        valor=0.14,
        unidad="adimensional [0 a 1]",
        motivo="Barbecho químico con rastrojo intacto del cultivo anterior.",
        fuente_referencia="USDA AH 537 Tabla 5 (Wischmeier & Smith 1978).",
    ),
    "barbecho_suelo_desnudo": Supuesto(
        clave="usle_c_barbecho_suelo_desnudo",
        valor=0.55,
        unidad="adimensional [0 a 1]",
        motivo="Suelo laboreado o pulverizado sin cobertura protectora ni rugosidad residual.",
        fuente_referencia="USDA AH 537 Tabla 5 (Wischmeier & Smith 1978, pág. 20).",
    ),
}


