# Fuentes de Datos, Jerarquía de Calidad y APIs Externas (SDD §5)

Este documento describe la procedencia, resolución, licencias y mecanismos de ingesta de todos los conjuntos de datos y servicios remotos integrados en **Complemento a RotaTerra**.

---

## 1. Modelos Digitales de Elevación (MDE / MDT / MDS)

| Prioridad | Fuente | Resolución nominal | Tipo de superficie | Proveedor / Acceso | Uso en el sistema | Limitaciones |
|---:|---|---:|---|---|---|---|
| **1** | Relevamiento propio (Dron RTK / LiDAR / GNSS) | 0.05 – 2 m | MDT (filtrado) o MDS | Subida de archivo GeoTIFF por el usuario (`POST /api/v1/fields/{id}/dem/upload`) | Microrelieve, surcos de siembra, cunetas, terrazas y obras | Requiere declarar datum vertical (EGM96/EGM2008/POSGAR), fecha y precisión. |
| **2** | OpenTopography Global Datasets | 30 m | MDS / DTM según producto | API REST OpenTopography (`https://portal.opentopography.org/API/globaldem`) con clave en `.env` | Descarga de alta velocidad para SRTM GL1, NASADEM, ALOS World 3D (AW3D30) y Copernicus GLO-30 | Sujeto a cuotas y límites de extensión por llamada. |
| **3** | Copernicus DEM GLO-30 COG | 30 m (1 arc-sec) | MDS (superficie reflectante) | AWS Open Data (`s3://copernicus-dem-30m/`) vía HTTP Range requests | Ingesta automática por defecto al crear o dibujar un lote | Resolución de 30 m; no resuelve micro-depresiones ni surcos. |
| **4** | IGN Argentina — MDE-Ar v2.1 | 30 m | MDS | Instituto Geográfico Nacional (GeoTIFF) | Contexto topográfico nacional alternativo | Cobertura nacional estándar. |

### Mecanismo de descarga sin duplicación de Copernicus GLO-30 COG:
- Acceso directo por ventanas HTTP `Range` sobre el Cloud Optimized GeoTIFF oficial de 1° × 1° en AWS S3 sin transferir el mosaico completo.
- Inspección del XML de metadatos oficial (`DEM_Coverage.xml`) para extraer las fechas exactas de adquisición del satélite TanDEM-X (`tsxx_startTime` y `tsxx_stopTime`).
- Validación de certificados TLS mediante el almacén del sistema operativo (`truststore` / SSL estándar).

---

## 2. Imágenes Ópticas y Texturas Satelitales

### 2.1 Textura 3D para Diorama e Inspección
- **Proveedor:** Esri World Imagery (ArcGIS Online REST Services).
- **Endpoint:** `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`
- **Resolución:** Sub-métrica a 15 m según nivel de zoom (`z=14..18`).
- **Uso:** Mapeo de textura de alta resolución proyectada ortogonalmente sobre la geometría del bloque isométrico 3D.
- **Respaldo:** En caso de corte de conexión o fallo de tiles, el visor genera un mapa de sombreado analítico con gradiente hipsométrico procedural informando el estado sin interrumpir la experiencia.

### 2.2 Monitor de Vigor de Cultivos (NDVI Sentinel-2 L2A)
- **Proveedor:** Misión Sentinel-2 (Agencia Espacial Europea / Copernicus), catálogo STAC `Earth Search` de Element84 en AWS.
- **Endpoint STAC:** `https://earth-search.aws.element84.com/v1`
- **Producto:** L2A (reflectancia en superficie corregida atmosféricamente, BOA).
- **Bandas descargadas:**
  - `B04` (Rojo, ~665 nm, resolución nativa 10 m).
  - `B08` (Infrarrojo cercano NIR, ~842 nm, resolución nativa 10 m).
  - `SCL` (Scene Classification Layer, resolución nativa 20 m).
- **Control de Calidad y Filtrado de Nubes:**
  - Las celdas catalogadas como nube de alta probabilidad (`SCL=9`), nube de media probabilidad (`SCL=8`), sombra de nube (`SCL=3`), cirros (`SCL=10`) o nieve/hielo (`SCL=11`) se enmascaran rigurosamente con `np.nan`.
  - Se descartan escenas con cobertura de nubes declarada $\ge 85\%$.
  - Remuestreo por vecino más cercano (`Resampling.nearest`) para evitar contaminación espectral de bordes de nube sobre píxeles de vegetación limpia.
  - Conforme a la **Regla R4**, si no se encuentran escenas válidas libres de nubes en la ventana temporal, el sistema no sintetiza índices artificiales y reporta `status: "unavailable"`.

---

## 3. Datos Meteorológicos y Agroclimáticos

### 3.1 NASA POWER Agroclimatology API
- **Endpoint:** `https://power.larc.nasa.gov/api/temporal/daily/point`
- **Parámetros consultados:**
  - `PRECTOTCORR`: Precipitación diaria corregida por sesgo (mm/día).
  - `T2M_MAX`: Temperatura máxima diaria del aire a 2 m (°C).
  - `T2M_MIN`: Temperatura mínima diaria del aire a 2 m (°C).
  - `ALLSKY_SFC_SW_DWN`: Radiación solar global incidente en superficie ($MJ/m^2/\text{día}$).
- **Resolución espacial:** $0.5^\circ \times 0.5^\circ$ (~50 km en latitudes medias pampeanas).
- **Serie temporal:** 1990 hasta la fecha actual en tiempo real (`date.today()`).
- **Aplicaciones:**
  - Balance hídrico mensual FAO-56.
  - Análisis de riesgo de anegamiento en fechas históricas recientes.
  - Estadísticas de fechas de primeras y últimas heladas (percentiles P10, P50, P90).

### 3.2 NASA GPM IMERG (Precipitación Global Multi-Satelital)
- **Producto:** IMERG Final Run / Late Run (GPM_3IMERGDF).
- **Resolución espacial:** $0.1^\circ \times 0.1^\circ$ (~10 km).
- **Uso:** Validación y complemento de eventos de lluvia extremos en ausencia de pluviómetros convencionales.

---

## 4. Datos Catastrales y Parámetros Agronómicos

### 4.1 Lote de Muestra Catastral Oficial
- **Archivo:** `data/sample/san_luis_parcela_205.geojson`
- **Fuente:** Dirección Provincial de Catastro y Tierras Fiscales de San Luis (`SanLuis:GIS_PARCELAS_RUR_VV`).
- **Nomenclatura catastral:** `00-03-30-00-000000-000205`, Parcela Rural `205`, ~199.1 ha en UTM 20S (`EPSG:32720`).
- **Uso:** Lote patrón de prueba para suites de test E2E offline y validación geométrica.

### 4.2 Parámetros de Suelo y Cobertura (NRCS / INTA)
- **Grupos Hidrológicos:** A, B, C y D basados en el Sistema de Cartas de Suelos del INTA y el Manual de Hidrología del USDA-NRCS (NEH-4).
- **Tablas de Número de Curva ($CN_{II}$):** Parametrizadas para labranza convencional, siembra directa (buena condición) y pasturas permanentes.
- **Erodabilidad $K$ y Cobertura $C$ (USLE):** Coeficientes calibrados para la región pampeana argentina (INTA Castelar / INTA Pergamino).
