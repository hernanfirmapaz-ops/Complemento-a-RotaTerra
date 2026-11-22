# Spec 014: Relieve Base Regional (Copernicus GLO-30), Pendiente del Lote por Plano Ajustado y Calibración con Mojones IGN

**Estado:** Borrador para revisión (requiere aprobación de Hernán)  
**Fecha:** 22/11/2026  
**Rama:** `spec/014-relieve-base-copernicus`  
**Issue:** #73 (`[41] Relieve base: reemplazar NASADEM por Copernicus GLO-30 / GEM-15 y pendiente del lote por plano ajustado`)  
**Autor:** Antigravity  

---

## 1. Justificación y Diagnóstico del Problema

### 1.1 El problema de NASADEM y el ruido en celdas de 30 m
El sistema actual ha venido utilizando como respaldo regional modelos digitales de elevación derivados de la misión SRTM (específicamente NASADEM 30 m de febrero de 2000). Evaluaciones sistemáticas globales de modelos digitales de elevación (Meadows, Jones & Reinke 2024, *Int. J. Digital Earth* 17(1), sec. 4) constatan que NASADEM y SRTM presentan importantes errores verticales residuales y ruido de alta frecuencia frente a puntos geodésicos terrestres en áreas llanas y propensas a anegamiento.

Con celdas de 30 m de resolución espacial, un error aleatorio de $\pm 1\text{ m}$ entre celdas contiguas se traduce directamente en una pendiente aparente espuria:
$$\text{Pendiente aparente} = \frac{\Delta z}{\Delta x} = \frac{1\text{ m}}{30\text{ m}} \approx 3,33\%$$

Por esta razón matemática, en zonas típicamente llanas como Villa Mercedes (San Luis), Trenque Lauquen o Pergamino —donde la pendiente real regional del terreno oscila entre 0,2 % y 0,8 %—, el cálculo celular tradicional (método de Horn) arrojaba valores promedio y medianas de 2,5 % a 4,5 % (entre 2 y 8 veces la pendiente real del lote).

**Consecuencias agronómicas y de modelado:**
1. **Sobreestimación severa de la erosión hídrica:** En la ecuación universal de pérdida de suelo (USLE/RUSLE), el factor topográfico $LS$ crece fuertemente con la pendiente ($S$). Una pendiente inflada de 0,5 % a 2,5 % multiplica la tasa calculada de pérdida de suelo ($A$, en $\text{t}/(\text{ha}\cdot\text{año})$) por un factor de 2 a 4, generando falsas alarmas de degradación.
2. **Microcanales artificiales en el solver hidrológico:** El ruido de alta frecuencia celda a celda genera pequeñas depresiones y canales espurios que desconectan el escurrimiento laminar real.
3. **Pérdida de confianza del productor agropecuario:** Informar en la ficha técnica "Pendiente del lote: 2,76 %" en un campo visiblemente plano desacredita la herramienta frente al asesor agronómico.

---

### 1.2 Prueba empírica real (22/11/2026: mojones de nivelación IGN separados por red)
Durante la investigación de campo se contrastaron en la tesela `Copernicus_DSM_COG_10_S34_00_W066_00_DEM` (latitud $-34^\circ$ a $-33^\circ$, longitud $-66^\circ$ a $-65^\circ$, área de Villa Mercedes y cuenca del Río Quinto, San Luis) los modelos digitales disponibles contra mojones geodésicos oficiales de la Red de Nivelación Geométrica del Instituto Geográfico Nacional (IGN), separando el análisis por red geodésica para garantizar datos reproducibles y sin solapes:

| Red IGN (llanura, cota $< 600\text{ m}$ / transecto sur) | $n$ | Fuente | Sesgo (mediana) | NMAD (robusto) | RMSE | LE90 |
|---|---|---|---|---|---|---|
| **Alta precisión** | 44 | **Copernicus GLO-30** | **$+0,50\text{ m}$** | **$1,08\text{ m}$** | **$1,59\text{ m}$** | **$2,42\text{ m}$** |
| **Precisión** | 32 | **Copernicus GLO-30** | **$+0,30\text{ m}$** | **$1,93\text{ m}$** | **$3,83\text{ m}$** | **$2,97\text{ m}$** |
| **Alta precisión + precisión (combinadas)** | 76 | **Copernicus GLO-30** | **$+0,45\text{ m}$** | **$1,15\text{ m}$** | **$2,77\text{ m}$** | **$2,61\text{ m}$** |
| Topográfica ⚠️ *(excluida)* | 45 | Copernicus GLO-30 | $+0,35\text{ m}$ | $3,75\text{ m}$ | $9,40\text{ m}$ | $16,20\text{ m}$ |

**Exclusión justificada de la red topográfica secundaria:**
La red topográfica **no debe utilizarse para validación ni calibración**. Dicha red secundaria presenta una dispersión muy elevada ($\text{NMAD} = 3,75\text{ m}$, $\text{LE90} = 16,20\text{ m}$ frente a los $\approx 1\text{ m}$ de las redes principales), evidenciando coordenadas con redondeo grosero o errores históricos de transcripción en los partes de nivelación secundaria. Asimismo, se descartó el mojón topográfico `PF1n(75)n` cuya cota figuraba en $26,226\text{ m}$ en una cota real de terreno de $\approx 500\text{ m}$. Por tanto, la calibración y validación se limita estrictamente a las redes de **alta precisión** y **precisión**.

**Hallazgos clave:**
- **Copernicus GLO-30** presenta un sesgo vertical muy reducido ($+0,45\text{ m}$) y un error robusto típico ($\text{NMAD}$) de $1,15\text{ m}$ en las redes combinadas de alta precisión y precisión ($1,08\text{ m}$ en alta precisión pura), con un $\text{LE90}$ de $2,61\text{ m}$.
- **Métrica estándar:** El $\text{RMSE}$ y el $\text{LE90}$ se ven distorsionados por mojones atípicos (emplazados sobre terraplenes de ferrocarril, puentes o alcantarillas); por ello, la métrica oficial de dispersión vertical en RotaTerra es el **NMAD** (Normalized Median Absolute Deviation, Höhle & Höhle 2009).
- **Datum vertical:** Las cotas IGN están referidas al cero oficial de nivelación nacional (cero de Mar del Plata), mientras que Copernicus GLO-30 está referido al geoide mundial EGM2008. Al no disponerse de un modelo geoidal de transformación oficial milimétrico en la región, **no se fija una cifra a priori** ("< 0,4 m" queda descartado como hecho no documentado) y se declara como **supuesto agronómico** en `geoprocessing/supuestos.py` (`SUPUESTO_DEM_DIFERENCIA_DATUM_VERTICAL_M = None`), absorbiéndose empíricamente en la mediana de residuos ($\delta_{\text{local}}$) durante la calibración local con mojones IGN.

---

### 1.3 Prueba de pendiente: cálculo celular vs. plano ajustado
En la misma zona de San Luis, se evaluó la pendiente en 4 ventanas agronómicas de $\approx 410\text{ ha}$ cada una:

| Ventana | Relieve total | Pendiente píxel (mediana Horn) | Pendiente píxel (p90 Horn) | **Pendiente del plano ajustado (FAO)** |
|---|---|---|---|---|
| Sur Villa Mercedes A ($-65,40;\ -33,85$) | $13,0\text{ m}$ | $0,89\%$ | $3,52\%$ | **$0,37\%$** |
| Sur Villa Mercedes B ($-65,30;\ -33,95$) | $9,8\text{ m}$ | $0,81\%$ | $1,68\%$ | **$0,37\%$** |
| Oeste Villa Mercedes ($-65,60;\ -33,75$) | $13,3\text{ m}$ | $1,94\%$ | $4,25\%$ | **$0,23\%$** |
| Este Villa Mercedes ($-65,25;\ -33,70$) | $40,3\text{ m}$ | $1,74\%$ | $3,94\%$ | **$1,12\%$** |

**Conclusión:** La pendiente celular es entre **2 y 8 veces superior** a la pendiente general del lote. La pendiente regional y el rumbo del potrero deben surgir de un **plano ajustado de mínimos cuadrados**, mientras que el análisis de escurrimiento distribuido celda a celda debe emplear una pendiente celular suavizada mediante filtrado espacial.

---

## 2. Reglas Innegociables de Representación e Integridad de Datos

1. **Cumplimiento estricto de `docs/metodologia.md`:** Cada valor numérico en la ficha técnica de relieve tiene exactamente uno de los tres estados:
   - **Dato con fuente:** Fuente consultada con documento + DOI / URL oficial registrado en `docs/data-sources.md`.
   - **Supuesto editable:** Declarado en `geoprocessing/supuestos.py` con justificación agronómica y modificable por el usuario.
   - **Sin dato:** Declarado explícitamente como `null` con calidad `"descartada"` y motivo. Quedan terminantemente prohibidos valores de respaldo inventados o silenciosos.
2. **Prioridad de fuentes de relieve (orden jerárquico):**
   - **Prioridad 1 (Máxima):** Relevamiento propio del usuario (Dron RTK / LiDAR / GNSS en GeoTIFF). Se respetan sus cotas y resolución sin sobrescritura.
   - **Prioridad 2 (Por defecto nacional):** **Copernicus GLO-30** (DSM 30 m, AWS Open Data COG).
   - **Prioridad 3 (Opcional experimental):** GEM-15 (Google, 15 m DTM) únicamente para contraste relativo de pendiente, advirtiendo su sesgo vertical de metros.
   - **Descartados para relieve base:** MDE-Ar 30 (sesgo vertical sistemático no calibrado), NASADEM (obsoleto, año 2000, ruido de $1,5\text{ m}$). FABDEM solo si se habilita uso no comercial (licencia CC BY-NC-SA 4.0).
3. **Eficiencia en ingesta:** Lectura por ventana (*Windowed read* mediante peticiones HTTP `Range` sobre el COG público de AWS), descargando exclusivamente el área del lote más su buffer de entorno sin transferir la tesela completa de 1° × 1°.
4. **Pruebas 100 % aisladas de la red:** Ningún test del pipeline de CI dependerá de internet. Se utilizarán fixtures sintéticos y recortes georreferenciados almacenados localmente.

---

## 3. Fuente Regional por Defecto: Copernicus GLO-30

### 3.1 Especificación técnica y catálogo
- **Identificador de producto:** Copernicus DEM GLO-30 (European Space Agency / Airbus Defence and Space).
- **DOI:** `10.5270/ESA-c5d3d65`.
- **Tipo de superficie:** Modelo Digital de Superficie (DSM), generado a partir de interferometría radar TanDEM-X en banda X (adquisición entre diciembre de 2010 y 2015).
- **Resolución nominal:** 1 segundo de arco ($\approx 30\text{ m}$ en el ecuador; $\approx 25\text{ m}$ en dirección este-oeste en latitudes de $34^\circ\text{ S}$).
- **Datum horizontal:** WGS84 (EPSG:4326).
- **Datum vertical:** Geoide EGM2008 (alturas ortométricas en metros).
- **Precisión vertical declarada por la ESA:** Error lineal al 90 % ($\text{LE90}$) $< 4\text{ m}$ absoluta; precisión relativa $< 2\text{ m}$ ($\text{LE90}$).
- **Licencia:** Libre y abierta con atribución requerida: *«Copernicus DEM: © DLR e.V. 2010-2014 y © Airbus Defence and Space GmbH 2014-2018, provisto bajo COPERNICUS por la Unión Europea y la ESA»*.
- **Acceso:** Bucket público de AWS Open Data (`s3://copernicus-dem-30m/` o endpoint HTTP `https://copernicus-dem-30m.s3.amazonaws.com/`).

### 3.2 Protocolo de lectura por ventana y caché
1. **Determinación de teselas:** Dado el bounding box del lote con su buffer agronómico de cuenca ($B = [\text{lon}_{\min}, \text{lat}_{\min}, \text{lon}_{\max}, \text{lat}_{\max}]$), se identifican las teselas de $1^\circ \times 1^\circ$ necesarias mediante el patrón oficial:
   $$\text{Tile ID} = \{\text{N}|\text{S}\}\text{XX\_00\_}\{\text{E}|\text{W}\}\text{YYY\_00}$$
   Ejemplo: coordenadas $(-33,7^\circ, -65,3^\circ) \implies \text{S34\_00\_W066\_00}$.
2. **Lectura directa HTTP:** Utilización del driver VSI de GDAL/rasterio (`/vsicurl/` o `http_opener`) con las siguientes directivas de entorno para optimizar la latencia:
   ```python
   GDAL_ENV = {
       "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
       "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
       "GDAL_HTTP_MAX_RETRY": "3",
       "GDAL_HTTP_RETRY_DELAY": "2",
   }
   ```
3. **Caché persistente en disco:** Las ventanas descargadas se almacenan localmente en `data/cache/dem/copernicus/{tile_id}_{hash_bbox}.tif`. Si el archivo existe y es válido, se reutiliza sin peticiones a la red.
4. **Mosaico y reproyección:** En caso de que el lote cruce límites de tesela de $1^\circ$, se fusionan las ventanas mediante `rasterio.merge` y se proyecta a la faja UTM correspondiente (WGS84 / UTM zona 19S a 21S) preservando las cotas mediante interpolación bilineal.

---

## 4. Algoritmo de Pendiente y Rumbo del Lote por Plano Ajustado

### 4.1 Formulación matemática (FAO T0231E cap. 6, ec. 117)
Para caracterizar la macro-pendiente y la orientación general de escurrimiento de la unidad productiva, se ajusta un plano de regresión de mínimos cuadrados ordinarios (o ponderado por celda útil) sobre todas las celdas válidas del lote (excluyendo celdas sin dato o exteriores al polígono):

$$Z(X, Y) = a + b \cdot X + c \cdot Y$$

Donde:
- $X, Y$: Coordenadas métricas proyectadas en el sistema de referencia local (UTM / POSGAR 07, metros). Para estabilidad numérica de la regresión, se centran respecto al centroide: $x = X - \bar{X}$, $y = Y - \bar{Y}$.
- $Z$: Cota de elevación del terreno en metros.
- $a$: Cota estimada en el centroide del lote ($\bar{Z}$).
- $b = \frac{\partial Z}{\partial X}$: Gradiente zonal en sentido Oeste-Este (positivo si el terreno asciende hacia el Este).
- $c = \frac{\partial Z}{\partial Y}$: Gradiente zonal en sentido Sur-Norte (positivo si el terreno asciende hacia el Norte).

Resolviendo el sistema lineal normal de mínimos cuadrados $\mathbf{J} \boldsymbol{\beta} = \mathbf{Z}$:
$$\begin{bmatrix} b \\ c \end{bmatrix} = \begin{bmatrix} \sum x_i^2 & \sum x_i y_i \\ \sum x_i y_i & \sum y_i^2 \end{bmatrix}^{-1} \begin{bmatrix} \sum x_i (Z_i - \bar{Z}) \\ \sum y_i (Z_i - \bar{Z}) \end{bmatrix}$$

### 4.2 Métricas derivadas
1. **Magnitud de la pendiente del lote ($S$):**
   $$s = \sqrt{b^2 + c^2} \quad (\text{en m/m}), \qquad S_{\%} = 100 \cdot \sqrt{b^2 + c^2} \quad (\text{en \%})$$
2. **Rumbo o dirección de máximo descenso ($\theta$):**
   El vector de descenso apunta en sentido opuesto al gradiente topográfico: $(-b, -c)$.
   $$\theta = \left(\operatorname{atan2}(-b, -c) \cdot \frac{180^\circ}{\pi} + 360^\circ\right) \pmod{360^\circ}$$
   - $0^\circ$: Desciende hacia el Norte.
   - $90^\circ$: Desciende hacia el Este.
   - $180^\circ$: Desciende hacia el Sur.
   - $270^\circ$: Desciende hacia el Oeste.
3. **Bondad de ajuste del plano ($R^2$):**
   $$R^2 = 1 - \frac{\sum (Z_i - \hat{Z}_i)^2}{\sum (Z_i - \bar{Z})^2}$$
   - Si $R^2 \ge 0,70$: El lote tiene un relieve marcadamente plano u homogéneo, con pendiente dominante unidireccional bien definida.
   - Si $R^2 < 0,70$: El lote presenta ondulaciones complejas, lomas múltiples, bajos diseminados o relieve quebrado; en este caso la ficha informa la tendencia general pero agrega la advertencia: *"Relieve complejo multiescurrimiento (R² < 0,70); verificar zonas individuales"*.

### 4.3 Suavizado de la pendiente celular (para USLE y flujo 2D)
Para evitar que la pendiente píxel a píxel sufra del ruido de $\pm 1\text{ m}$:
- Se aplica un filtro Gaussiano con radio de vecindad de 2 a 3 celdas ($\sigma = 1,0$ a $1,5$ píxeles, equivalente a una ventana de $\approx 60\text{ a }90\text{ m}$) sobre la matriz $Z$ antes de computar el gradiente diferencial de Horn.
- De esta forma, la pendiente celular preserva los cambios de relieve morfométricos reales (taludes, terrazas, lomas) sin disparar gradientes artificiales de $3\%$ en celdas llanas.

---

## 5. Calibración y Corrección Opcional de Sesgo con Mojones IGN

### 5.1 Servicio y datos de referencia
- **Fuente geodésica:** Red de Nivelación de la República Argentina (Instituto Geográfico Nacional).
- **Punto de acceso WFS:** `https://wms.ign.gob.ar/geoserver/ows`
- **Capas consultadas:**
  1. `ign:nivelacion_alta_precision` (Red de alta precisión)
  2. `ign:nivelacion_precision` (Red de precisión)
  *(Nota: `ign:nivelacion_topografica` queda expresamente excluida debido a discrepancias > 10 m frente a Copernicus y MDE-Ar y errores de cota documentados).*
- **Atributos utilizados:** `cota` (cota ortométrica en metros sobre el nivel del mar), `latitud`, `longitud`, `estado` (filtrando únicamente mojones con estado `"Bueno"`, `"Encontrado"`, `"Sin Novedad"` o sin marca de destrucción) y `nomenclatura`.

### 5.2 Algoritmo de calibración zonal
1. **Búsqueda por radio de influencia y supuestos declarados:**
   A partir del centroide del lote, se buscan mojones IGN válidos en un radio inicial $R_1$ (definido por el supuesto editable `SUPUESTO_DEM_RADIO_BUSQUEDA_IGN_R1_KM = 25.0 km` en `geoprocessing/supuestos.py`). Si el número de mojones $n < n_{\min}$ (`SUPUESTO_DEM_MIN_MOJONES_IGN = 3`), se amplía automáticamente a un radio extendido $R_2$ (`SUPUESTO_DEM_RADIO_BUSQUEDA_IGN_R2_KM = 50.0 km`). Si aun así $n < 3$, no se aplica corrección y se declara en la ficha técnica: `"Sin mojones IGN suficientes en 50 km para calibración"`.
2. **Interpolación de elevación DEM:**
   Para cada mojón $j \in \{1, \dots, n\}$ ubicado en $(x_j, y_j)$, se interpola la cota del raster Copernicus mediante interpolación bilineal: $Z_{\text{DEM}, j}$.
3. **Cálculo de residuos:**
   $$\Delta z_j = Z_{\text{DEM}, j} - Z_{\text{IGN}, j}$$
4. **Estimación robusta del sesgo local ($\delta_{\text{local}}$):**
   Debido a que algunos mojones se ubican sobre obras de infraestructura elevadas (vías o estribos de puentes):
   $$\delta_{\text{local}} = \operatorname{mediana}(\{\Delta z_j\}_{j=1}^n)$$
5. **Precisión vertical local informada (NMAD):**
   Siguiendo el estándar internacional para evaluación de modelos digitales de terreno (Höhle & Höhle 2009; Meadows et al. 2024):
   $$\text{NMAD} = 1,4826 \cdot \operatorname{mediana}\left(\left| \Delta z_j - \delta_{\text{local}} \right|\right)$$
6. **Aplicación:** Si el usuario selecciona la opción *"Calibrar con mojones IGN"*, las cotas del DEM se ajustan: $Z_{\text{calibrado}} = Z_{\text{DEM}} - \delta_{\text{local}}$, y la precisión vertical informada en la ficha pasa a ser el $\text{NMAD}$ local calculado.

---

## 6. Ficha Técnica Visible de Relieve en API y Frontend

Toda respuesta de elevación y análisis de terreno en la API (`/api/v1/fields/{id}/terrain`) y en el panel frontal incluirá obligatoriamente el siguiente bloque de metadatos:

```json
{
  "dem_source": {
    "id": "copernicus_glo30",
    "name": "Copernicus DEM GLO-30 (ESA)",
    "surface_type": "DSM",
    "nominal_resolution_m": 30.0,
    "vertical_datum": "EGM2008 (alturas ortométricas)",
    "declared_accuracy_le90_m": 4.0,
    "local_calibration": {
      "calibrated_with_ign": true,
      "ign_points_count": 121,
      "bias_median_m": 0.27,
      "nmad_accuracy_m": 1.12,
      "radius_km": 25.0
    },
    "license": "Copernicus open access (© DLR e.V. / Airbus DS / ESA)",
    "disclaimer": "Relieve regional satelital (±1–2 m de precisión relativa). No apto para diseño de microrrelieve de surcos ni nivelación milimétrica."
  },
  "field_macro_topography": {
    "slope_fitted_plane_pct": 0.37,
    "aspect_descent_deg": 142.5,
    "aspect_cardinal": "SE",
    "plane_r2": 0.88,
    "cellular_slope_smoothed_median_pct": 0.42,
    "cellular_slope_raw_horn_median_pct": 1.84,
    "elevation_min_m": 508.2,
    "elevation_max_m": 521.2,
    "elevation_centroid_m": 514.8
  }
}
```

**Texto visible en la interfaz de usuario (Visor 3D y Ficha de Lote):**
- **Insignia de relieve:** `Copernicus GLO-30 (30 m) · Precisión vertical regional: ±1,1 m (NMAD)`
- **Pendiente del lote:** `0,4 % hacia el SE (plano ajustado R² = 0,88)`
- **Aviso permanente:** *"Relieve regional satelital. Para replanteo de curvas de nivel u obras de drenaje se requiere relevamiento propio con dron RTK o GNSS."*

---

## 7. Plan de Validación y Comparativa NASADEM vs. Copernicus

Durante la implementación en código del PR correspondiente, se generará una tabla comparativa sobre **3 lotes de prueba agronómicos reales** representativos de las principales regiones productivas:

1. **Lote 1 (San Luis - Llanura Medanosa / Pedemonte):** Piedemonte El Trapiche / Villa Mercedes (~222 ha).
2. **Lote 2 (Córdoba / Pampa Ondulada):** Marcos Juárez / Pergamino (~300 ha).
3. **Lote 3 (Buenos Aires - Pampa Deprimida):** Cuenca del Salado / Castelli (~500 ha).

**Variables a contrastar en el PR:**
- Pendiente informada del lote: Plano ajustado (%) vs. Mediana celular NASADEM (%) vs. Mediana celular Copernicus (%).
- Área total anegada temporalmente (ha) bajo tormenta de diseño crítica (80 mm).
- Pérdida calculada de suelo USLE ($A$, $\text{t}/(\text{ha}\cdot\text{año})$).
- Cantidad de depresiones endorreicas detectadas (comparando falsas cubetas generadas por ruido de NASADEM).

---

## 8. Estrategia de Pruebas Automatizadas (100 % Offline)

Todas las pruebas del conjunto de tests deben ejecutarse sin acceso a internet:
1. **Fixture de raster sintético (`test_slope_aspect_fitted_plane`):**
   - Se crea un array 2D de dimensiones conocidas ($100 \times 100$ píxeles de $\Delta x = \Delta y = 30\text{ m}$) con un plano matemático exacto:
     $$Z(x, y) = 500,0 + 0,005 \cdot x - 0,003 \cdot y$$
   - Se verifica que la función de plano ajustado recupere con tolerancia $< 10^{-6}$:
     - $b = 0,005$
     - $c = -0,003$
     - Pendiente $s = \sqrt{0,005^2 + (-0,003)^2} = \sqrt{0,000034} \approx 0,00583095 \implies 0,583\%$
     - Rumbo $\theta = (\operatorname{atan2}(-0,005, 0,003) \cdot 180 / \pi + 360) \pmod{360} = 300,96^\circ$
     - $R^2 = 1,0000$
2. **Fixture georreferenciado real (`copernicus_vm_crop.tif`):**
   - Recorte local de la tesela de Villa Mercedes guardado en `geoprocessing/tests/fixtures/dem/`.
3. **Fixture de mojones IGN y script de validación reproducible:**
   - Script de descarga y cálculo reproducible: `scripts/validar_copernicus_ign.py`.
   - GeoJSON offline descargado el 22/11/2026: `geoprocessing/tests/fixtures/dem/ign_nivelacion_san_luis_20261122.geojson`.
   - Test offline: `geoprocessing/tests/test_dem_copernicus_ign.py`, que recalcula sin internet la mediana de residuos ($+0,41\text{ a }+0,50\text{ m}$ en alta precisión), el $\text{NMAD}$ ($1,08\text{ m}$), $\text{RMSE}$ ($1,59\text{ m}$) y $\text{LE90}$ ($2,42\text{ m}$), y comprueba la exclusión documentada de la red topográfica secundaria.
4. **Aislamiento de red:** Verificación de que el test falla si intenta conectar con sockets externos.

---

## 9. Alcance y Fuera de Alcance

### Alcance
- Definición de Copernicus GLO-30 como fuente regional por omisión para toda Argentina.
- Lectura por ventana vía peticiones HTTP `Range` sobre el COG público de AWS en `geoprocessing/dem/sources.py`.
- Algoritmo de ajuste de plano de mínimos cuadrados para pendiente y rumbo del lote (`geoprocessing/dem/terrain.py`).
- Suavizado espacial de la matriz de pendientes celulares para el solver hidrológico y USLE.
- Módulo de calibración con mojones de nivelación del IGN y cálculo de $\text{NMAD}$.
- Actualización de `docs/data-sources.md` con las citas y precisiones correspondientes.
- Fixtures offline y suite de pruebas unitarias en `geoprocessing/tests/`.

### Fuera de alcance
- Descarga masiva o almacenamiento de teselas enteras en el repositorio.
- Reemplazo de datos subidos por el usuario (si el usuario sube un GeoTIFF con dron, ese archivo tiene prioridad absoluta).
- MDE-Ar de 5 m de fotogrametría aérea (se considerará en una spec futura cuando esté disponible de forma homogénea).

---

## 10. Criterios de Aceptación Medibles

1. **Spec aprobada por Hernán:** Formalizada en `docs/specs/014-relieve-base-copernicus.md`.
2. **Lectura por ventana operativa:** `fetch_copernicus(bbox)` lee exclusivamente los bytes de la ventana requerida del COG de AWS y los almacena en caché local.
3. **Plano ajustado exacto en tests:** Prueba unitaria con plano sintético recupera la pendiente y rumbo con error relativo inferior al $0,001\%$.
4. **Calibración IGN con NMAD:** Módulo calcula la mediana de residuos y el $\text{NMAD}$ contra el fixture de mojones reproduciendo las métricas geodésicas reportadas.
5. **No hay valores inventados:** Toda constante o umbral proviene de `geoprocessing/supuestos.py` o de la literatura citada.
6. **Tests 100 % en verde sin internet:** `pytest` pasa en modo offline.

---

## 11. Referencias Bibliográficas

1. **FAO (1989):** *Surface Irrigation: Systems and Practice*, FAO Irrigation and Drainage Paper 45 (T0231E), cap. 6 "Land levelling", sección 6.3 "Plane method" (eq. 117). Food and Agriculture Organization of the United Nations, Roma. URL: `https://www.fao.org/3/t0231e/t0231e08.htm`.
2. **Höhle, J., & Höhle, M. (2009):** «Accuracy assessment of digital elevation models by means of robust statistical methods». *ISPRS Journal of Photogrammetry and Remote Sensing*, 64(4), 398-406. DOI: `10.1016/j.isprsjprs.2009.02.003`.
3. **Meadows, M. E., Jones, S. D., & Reinke, K. (2024):** «Vertical accuracy assessment of freely available global DEMs (FABDEM, Copernicus DEM, NASADEM, AW3D30 and SRTM) in flood-prone environments». *International Journal of Digital Earth*, 17(1), 2308734. DOI: `10.1080/17538947.2024.2308734`.
4. **European Space Agency & Airbus Defence and Space (2020):** *Copernicus Digital Elevation Model Product Handbook*, versión 4.0. DOI: `10.5270/ESA-c5d3d65`.
5. **Instituto Geográfico Nacional (IGN Argentina):** *Red de Nivelación de la República Argentina*. Capas WFS oficiales de nivelación geométrica de alta precisión y precisión. URL: `https://wms.ign.gob.ar/geoserver/ows`.
