# Fuentes de Datos, Jerarquía de Calidad y APIs Externas (SDD §5)

Este documento describe la procedencia, resolución, licencias y mecanismos de ingesta de todos los conjuntos de datos y servicios remotos integrados en **Complemento a RotaTerra**.

---

## 0. Regla de fuentes y tabla por capa (vigente desde el 21/11/2026)

El proyecto usa **cualquier fuente abierta, real y verificable**. Cada dato declara su fuente exacta, resolución, fecha y licencia, y **nunca se atribuye un dato a una fuente que no se consultó**.

Estado: **Integrada** = conectada y en uso · **Planificada** = aprobada, falta conectar · **A verificar** = confirmar que el acceso es real antes de programar.

| Capa | Fuente | Resolución / escala | Licencia | Acceso | Estado |
|---|---|---|---|---|---|
| Relieve | Relevamiento propio (dron RTK, LiDAR, GNSS) | 0,05–2 m | Del productor | Subida de GeoTIFF | Integrada |
| Relieve | IGN · MDT/MDE aerofotogramétrico | 5 m | IGN (citar fuente) | Descarga por hoja / Geoserver IGN | A verificar (cobertura en General Pedernera) |
| Relieve | IGN · MDE-Ar v2.1 | 30 m | IGN (citar fuente) | Descarga por hoja / WCS | Planificada |
| Relieve | Copernicus DEM GLO-30 | 30 m | Copernicus (libre con atribución) | AWS COG / OpenTopography | Integrada |
| Relieve | FABDEM | 30 m | **CC BY-NC-SA 4.0 (no comercial)** | Tiles de data.bris | Planificada |
| Relieve | NASADEM / SRTM | 30 m | Dominio público | OpenTopography | Integrada (respaldo) |
| Suelos | Cartas de suelo INTA (GeoINTA) | 1:100.000 | INTA | WMS/WFS GeoINTA | A verificar (servicio y capas) |
| Suelos | Perfiles SISINTA | Puntual | INTA, abierta | API SISINTA | Planificada |
| Suelos | SoilGrids 2.0 (ISRIC) | 250 m | CC BY 4.0 | API REST `rest.isric.org` | Integrada (spec 004; falta verificación en vivo) |
| Suelos | HYSOGs250m (NASA ORNL DAAC) | 250 m | Libre con cita | Earthdata | Planificada (spec 004) |
| Lluvia | Pluviómetro del productor | Puntual | Del productor | CSV | Integrada |
| Lluvia | Estaciones INTA (SIGA) | Puntual | INTA | Portal SIGA | A verificar |
| Lluvia | SMN · datos abiertos | Puntual | SMN | Portal de datos abiertos | A verificar (lluvia diaria por estación) |
| Lluvia | CHIRPS | ~5 km, diaria | Dominio público | UCSB CHC | Planificada |
| Lluvia | NASA GPM IMERG | ~10 km, 30 min | Dominio público | GES DISC (Earthdata) | Planificada |
| Lluvia y clima | NASA POWER | ~55 km, diaria | Dominio público | API REST | Integrada |
| Clima y humedad | ERA5-Land (Copernicus) | ~9 km, horaria | Copernicus | Climate Data Store | Planificada |
| Humedad del suelo | NASA SMAP L4 | 9 km | Dominio público | Earthdata | Planificada |
| Agua histórica | JRC Global Surface Water | 30 m, desde 1984 | Copernicus / CC BY 4.0 | Tiles / GEE | Planificada |
| Agua histórica | MapBiomas Argentina (agua) | 30 m | CC BY-SA | Plataforma MapBiomas | Planificada |
| Agua actual | OPERA DSWx-HLS / DSWx-S1 | 30 m | Dominio público | PO.DAAC / AWS | Planificada |
| Cobertura del suelo | ESA WorldCover · Dynamic World · MapBiomas | 10–30 m | CC BY 4.0 / CC BY-SA | Tiles / GEE | Planificada |
| Caminos, canales y alcantarillas | OpenStreetMap | Vectorial | ODbL (citar) | Overpass API | Planificada |
| Vigor del cultivo | Sentinel-2 L2A | 10 m | Copernicus | STAC Earth Search (AWS) | Integrada |
| Vigor del cultivo | HLS (Landsat + Sentinel-2) | 30 m | Dominio público | LP DAAC | Planificada |
| Rindes | Estimaciones agrícolas MAGyP | Departamento | Datos abiertos | datos.magyp.gob.ar | Planificada |
| Precios | Bolsa de Cereales de Buenos Aires · Bolsa de Comercio de Rosario | Diaria | Uso con cita | Publicaciones / API | A verificar |
| Napa | Freatímetro del productor · informes INTA San Luis | Puntual | Del productor / INTA | Carga manual | Planificada |

**Orden de integración acordado:** suelos (spec 004) → relieve IGN → lluvia de estaciones (INTA SIGA / SMN, tras verificar el acceso) → caminos de OpenStreetMap → agua histórica (JRC / MapBiomas).

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
  - Conforme a la **Regla de datos**, si no se encuentran escenas válidas libres de nubes en la ventana temporal, el sistema no sintetiza índices artificiales y reporta `status: "unavailable"` y `calidad: "descartada"` con `mean_ndvi_in_field: null`.
  - **Umbrales de vigor:** Los límites 0,38 (bajo vigor) y 0,60 (alto vigor) se declaran formalmente como supuestos agronómicos regionales en `geoprocessing/supuestos.py`.

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
  - Balance hídrico mensual.
  - Análisis de volumen de escurrimiento hacia bajos en fechas históricas (sin factores inventados ni umbrales sin fuente; informa volumen y % llenado de bajos; hectáreas solo si vienen de simulación 2D).
  - Estadísticas agroclimáticas de fechas de heladas (percentiles sin piso artificial ni rellenos sintéticos).
- **Naturaleza del dato:** Reanálisis asimilado de modelos globales (MERRA-2 / GEOS), no es una observación satelital directa (`is_satellite_observed: False`). Etiquetado con calidad `descartada` si no existen años completos suficientes (mínimo 300 días).

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
