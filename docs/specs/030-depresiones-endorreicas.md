# Spec 030: Depresiones Endorreicas Reales de la Planicie Medanosa (Acondicionamiento "Preservar Depresiones" vs. Breaching)

**Estado:** Borrador para revisión (requiere aprobación de Hernán)  
**Fecha:** 23/11/2026  
**Rama:** `spec/030-depresiones-endorreicas`  
**Issue:** #47 (`[30] Depresiones endorreicas reales: no vaciar las cubetas de deflación de la planicie medanosa`)  
**Autor:** Antigravity  

---

## 1. Justificación Geológica y Geomorfológica

### 1.1 Evidencia de campo: Hoja Geológica 3366-IV Villa Mercedes (SEGEMAR)
El diagnóstico territorial surge del relevamiento oficial de la **Hoja Geológica 3366-IV Villa Mercedes** (Costa et al. 2005, Instituto de Geología y Recursos Minerales, Servicio Geológico Minero Argentino - SEGEMAR, Boletín 348, sección 4 "Geomorfología", pp. 71–74; disponible en el [Repositorio Institucional SEGEMAR](https://repositorio.segemar.gov.ar/handle/308849217/194) con descarga directa del texto del informe en [Villa Mercedes.pdf (Secuencia 10)](https://repositorio.segemar.gov.ar/bitstream/handle/308849217/194/Villa%20Mercedes.pdf?sequence=10&isAllowed=y)):

| Evidencia geomorfológica | Cita y página (Costa et al. 2005, Boletín 348) | Impacto en el modelo hidrológico |
|---|---|---|
| **Drenaje desintegrado y endorreico:** Desde la latitud de Villa Mercedes hacia el sur, la planicie medanosa carece de red fluvial continua; los escurrimientos son efímeros y drenan a cubetas cerradas de deflación eólica de hasta 150 m de longitud. | p. 72: *"La unidad se caracteriza por presentar morfologías de médanos con diverso grado de preservación, así como por la falta de una red de drenaje integrada la que, cuando está desarrollada, es de carácter efímero y de tipo endorreica. Se destacan en algunos sectores la concentración de depresiones de hasta 150 metros de longitud, con lagunas temporarias, cuyo origen se vincula a cubetas de deflación."* | **Crítico:** Las depresiones no son artefactos del DEM sino geoformas cerradas reales donde el escurrimiento converge y se acumula. |
| **Lagunas permanentes y nivel freático:** Al sur de Villa Mercedes, los cuerpos de agua (Sayapé, Nasau, Capellán, Soven, Las Encadenadas, Los Pocitos) son permanentes y dependen fundamentalmente del nivel freático. | p. 74: *"Entre las lagunas más importantes se pueden mencionar las de Sayapé, Nasau, Capellán, Soven, Las Encadenadas y Los Pocitos... Estas lagunas son permanentes y sus superficies no presentan variaciones estacionales, por lo que se infiere que las mismas están vinculadas fundamentalmente con el nivel freático, más que con el régimen de lluvias."* | El anegamiento persistente no se explica solo por balance lluvia-infiltración celda a celda; confirma la necesidad de integrar la profundidad de napa (#40). |
| **Micro-relieve eólico (lomas longitudinales):** Cordones y lomas alargadas N-S de no más de 1,5 m de altura relativa, con longitudes de onda de 250 a 300 m. | p. 74: *"En la zona sur se pueden reconocer lomas alargadas con orientación N-S, con alturas relativas que no superan 1,5 m y longitudes de onda comprendidas entre 250 m a 300 m aproximadamente, con las crestas romas suavizadas por el laboreo agrícola."* | **Límite instrumental del DEM 30 m:** El error vertical NMAD empírico ($\approx 1,15\text{ m}$, Spec 014 §1) de Copernicus GLO-30 tiene el mismo orden de magnitud que la altura de las lomas (hasta 1,5 m). El umbral de 1,5 m se adopta como supuesto metodológico declarado. |
| **Pendiente regional ESE:** Caída regional suave desde cotas de 800 m (norte de Fraga) a 300 m (borde oriental). | p. 72: *"En conjunto presenta una pendiente regional orientada al ESE, que varía desde los 800 m al norte de Fraga, hasta 300m en el borde este de la hoja."* | La pendiente regional plana ($\approx 0,2\% - 0,4\%$) favorece la acumulación centrípeta en cubetas locales. |

---

## 2. El Problema del Acondicionamiento "Breach" en Llanuras Endorreicas

### 2.1 Por qué el "Breaching" tradicional falsea el anegamiento
En geomorfometría hidrológica clásica (desarrollada predominantemente para cuencas montañosas o con redes fluviales exorreicas integradas), los algoritmos de acondicionamiento digital del terreno asumen que **toda depresión en el DEM es un obstáculo espurio** causado por errores del sensor o vegetación.

El algoritmo estándar implementado en WhiteboxTools (`breach_depressions_least_cost`):
1. Detecta los bordes de la cubeta cerrada.
2. Traza una trinchera artificial de corte (*carving*) a través del umbral de menor cota topográfica.
3. Forza un canal de drenaje continuo hasta evacuar el agua fuera de la cuenca o al borde del dominio.

**Efecto perjudicial en la planicie medanosa:**
- Al aplicar `breach` indiscriminado sobre un lote de Villa Mercedes, Buena Esperanza o Justo Daract, el modelo abre zanjas ficticias a través de los cordones de dunas longitudinales de 1,5 m.
- Las cubetas de deflación naturales se vacían completamente en la simulación.
- El modelo informa **cero encharcamiento** o áreas anegadas subestimadas en más del 80 %, justamente en los bajos que el productor sabe que se inundan periódicamente.

---

## 3. Solución Metodológica: Modo "Preservar Depresiones"

### 3.1 Algoritmo de dos etapas
Se establece un acondicionamiento selectivo gobernado por la física del paisaje:

```mermaid
flowchart TD
    A["DEM suavizado (feature_preserving o moving_plane)"] --> B{"Pendiente regional del lote"}
    B -->|"< 1.0 % (Llanura / Planicie)"| C["Modo PRESERVAR DEPRESIONES (por defecto)"]
    B -->|">= 1.0 % (Relieve ondulado / Sierras)"| D["Modo BREACHING (por defecto)"]
    
    C --> E["Paso 1: Detección y filtrado de pozos espurios chicos"]
    E --> F["fill_depressions con max_depth = 0.20 m y max_area = 1800 m²"]
    F --> G["Paso 2: Depresiones reales remanentes"]
    G --> H["Identificación de celdas sumidero (sinks) y umbral de derrame (spill elevation)"]
    H --> I["Conservar sumideros: el flujo converge hacia el fondo de la cubeta"]
    I --> J["Cálculo de encharcamiento acumulativo (ponded volume & area)"]
    
    D --> K["Whitebox breach_depressions_least_cost"]
```

### 3.2 Criterios de discriminación de pozos (Supuestos calibrables)
Para no confundir errores de cuantización celda a celda con cubetas reales:
1. **Pozo espurio (ruido digital a rellenar):**
   - Profundidad $\le \text{SUPUESTO\_DEPRESION\_MAX\_FILL\_DEPTH\_M}$ ($0,20\text{ m}$).
   - Área $\le \text{SUPUESTO\_DEPRESION\_MAX\_FILL\_AREA\_M2}$ ($1800\text{ m}^2$, equivalente a $\le 2$ celdas de 30 m).
   - Justificación: Ruido de alta frecuencia inherente al filtrado espacial del interferograma SAR / DSM.
2. **Cubeta de deflación real (a preservar):**
   - Extensión $\ge 1800\text{ m}^2$ y profundidad $> 0,20\text{ m}$.
   - Se mantiene intacta la topografía de la cubeta; el algoritmo de acumulación de flujo (MFD/D8) direcciona el escurrimiento hacia el punto de cota mínima interior.

---

## 4. Parámetros en `geoprocessing/supuestos.py`

| Constante | Valor | Unidad | Fuente / Justificación | Editable |
|---|---|---|---|---|
| `SUPUESTO_CONDICIONAMIENTO_MODO_DEFAULT_LLANURA` | `"preservar_depresiones"` | string | Hoja SEGEMAR 3366-IV (Costa et al. 2005, p. 72). | Sí |
| `SUPUESTO_CONDICIONAMIENTO_UMBRAL_PENDIENTE_LLANURA` | `1.0` | % | Pendiente umbral entre planicie medanosa y piedemonte. | Sí |
| `SUPUESTO_DEPRESION_MAX_FILL_DEPTH_M` | `0.20` | m | Desnivel máximo de ruido espurio que se rellena automáticamente. | Sí |
| `SUPUESTO_DEPRESION_MAX_FILL_AREA_M2` | `1800` | $\text{m}^2$ | Área máxima de micro-pozos espurios ($\le 2$ celdas de 30 m). | Sí |

---

## 5. Salidas en API y Ficha Técnica

En el esquema de respuesta del análisis hidrológico (`HydrologyAnalysisResponse` / `QualityReport`):
```json
{
  "acondicionamiento_dem": {
    "modo_aplicado": "preservar_depresiones",
    "motivo": "Pendiente del lote (0.37%) inferior al umbral de llanura (1.0%); paisaje con cubetas de deflación endorreicas (Hoja SEGEMAR 3366-IV)",
    "depresiones_preservadas_n": 3,
    "volumen_almacenamiento_endorreico_m3": 14250.0,
    "superficie_cubetas_ha": 4.85
  }
}
```

En la sección "Límites del modelo" (`docs/model-limitations.md` / `QualityReport.warnings`):
- *"Relieve regional de 30 m (Copernicus GLO-30): El modelo digital satelital presenta una dispersión vertical típica NMAD ≈ 1,15 m frente a nivelación geométrica IGN en San Luis (Spec 014 §1), magnitud del mismo orden que las lomas arenosas longitudinales descriptas para la planicie medanosa ("alturas relativas que no superan 1,5 m", Costa et al. 2005, p. 74). En lotes con micro-ondulaciones inferiores a este umbral instrumental de 1,5 m (supuesto metodológico declarado), se recomienda verificar con relevamiento altimétrico propio de alta precisión (RTK/dron)."*

---

## 6. Validación Empírica con Historial de Agua JRC (#41)

Para validar la superioridad del modo "preservar depresiones" sobre "breach":
1. Se toma el lote de prueba de San Luis (`data/sample/san_luis_parcela_205.geojson`).
2. Se descarga la máscara de ocurrencia de agua superficial histórica de JRC Global Surface Water (1984–2024, #41).
3. Se calcula el Índice de Jaccard (Intersection over Union, IoU):
$$\text{IoU} = \frac{\text{Área Anillada Simulación} \cap \text{Ocurrencia Agua JRC}}{\text{Área Anillada Simulación} \cup \text{Ocurrencia Agua JRC}}$$
4. **Criterio de éxito:** El modo "preservar depresiones" debe alcanzar un $\text{IoU}$ al menos 3 veces superior al modo `breach` en la planicie medanosa.

---

## 7. Plan de Pruebas Automatizadas

1. **Test unitario sintético (`test_conditioning_endorheic_sink`):**
   - Grilla sintética de $20 \times 20$ celdas plana ($z = 100\text{ m}$) con una cubeta central de $4 \times 4$ celdas y $1\text{ m}$ de profundidad ($z = 99\text{ m}$).
   - Con modo `"preservar_depresiones"`: el DEM conserva la cota $99\text{ m}$ en el centro y el flujo superficial acumula volumen allí.
   - Con modo `"breach"`: el borde se corta y el centro drena hacia el borde.
2. **Test de micro-pozo espurio (`test_conditioning_spurious_pit_filled`):**
   - Una única celda aislada de $0,15\text{ m}$ de profundidad ($\le 0,20\text{ m}$) se rellena a nivel circundante.
3. **Test de trazabilidad de metadatos:**
   - La respuesta API devuelve `modo_aplicado: "preservar_depresiones"` y cita la Hoja SEGEMAR 3366-IV en el motivo.
