# Fuentes de Datos, Jerarquía de Calidad y APIs Externas (SDD §5)

Este documento describe la procedencia, resolución, licencias y mecanismos de ingesta de todos los conjuntos de datos y servicios remotos integrados en **Complemento a RotaTerra**.

---

## 0. Regla de fuentes y tabla por capa (vigente desde el 21/11/2026)

El proyecto usa **cualquier fuente abierta, real y verificable**. Cada dato declara su fuente exacta, resolución, fecha y licencia, y **nunca se atribuye un dato a una fuente que no se consultó**.

Estado: **Integrada** = conectada y en uso · **Planificada** = aprobada, falta conectar · **A verificar** = confirmar que el acceso es real antes de programar.

| Capa | Fuente | Resolución / escala | Licencia | Acceso | Estado |
|---|---|---|---|---|---|
| Relieve | Relevamiento propio (dron RTK, LiDAR, GNSS) | 0,05–2 m | Del productor | Subida de GeoTIFF | Integrada |
| Relieve | ICESat-2 ATL08 (LiDAR orbital de fotones) | Puntual (~11 m huella, 100 m paso) | Dominio público (NASA/NSIDC) | Earthdata / OpenAltimetry API | Planificada (spec 012) |
| Relieve | Google GEM-15 DTM v1 | 15 m | CC BY 4.0 | Google Cloud Storage / COG | Planificada (spec 014) |
| Relieve | IGN · MDT/MDE aerofotogramétrico | 5 m | IGN (citar fuente) | Descarga por hoja / Geoserver IGN | A verificar (cobertura en General Pedernera) |
| Relieve | IGN · MDE-Ar v2.1 | 30 m | IGN (citar fuente) | Descarga por hoja / WCS | Planificada |
| Relieve | Copernicus DEM GLO-30 | 30 m | Copernicus (libre con atribución) | AWS COG / OpenTopography | Integrada |
| Relieve | FABDEM | 30 m | **CC BY-NC-SA 4.0 (no comercial)** | Tiles de data.bris | Planificada |
| Relieve | NASADEM / SRTM | 30 m | Dominio público | OpenTopography | Integrada (respaldo) |
| Suelos | Cartas de suelo INTA (GeoINTA) | 1:100.000 | INTA | WMS/WFS GeoINTA | A verificar (servicio y capas) |
| Suelos | Perfiles SISINTA | Puntual | INTA, abierta | API SISINTA | Planificada |
| Suelos | SoilGrids 2.0 (ISRIC) | 250 m | CC BY 4.0 | API REST `rest.isric.org` | Integrada (spec 004; falta verificación en vivo) |
| Suelos | HYSOGs250m (NASA ORNL DAAC) | 250 m | Libre con cita | Earthdata | Planificada (spec 004) |
| Lluvia | Pluviómetro del productor | Puntual | Del productor | CSV / Carga manual | Integrada |
| Lluvia | Red de Estaciones de San Luis (REM) | Puntual (~60 est.) | Pública provincial (ULP/San Luis) | API / CSV `clima.edu.ar` | Integrada (#23 / PR #100) |
| Lluvia | Estaciones INTA (SIGA) | Puntual | INTA | Portal SIGA / series `.xls` | A verificar |
| Lluvia | SMN · datos abiertos | Puntual | SMN | Portal de datos abiertos | A verificar (lluvia diaria por estación) |
| Lluvia | CHIRPS v3 (v2 discontinúa 12/2026) | 0,05° (~5,3 km), diaria | Dominio público (UCSB CHC) | HTTP / FTP `data.chc.ucsb.edu` | Planificada (#21) |
| Lluvia | NASA GPM IMERG (Early / Final) | 0,1° (~10 km), 30 min / 4 h | Dominio público | GES DISC (Earthdata) | Planificada |
| Lluvia y clima | NASA POWER | ~55 km, diaria | Dominio público | API REST | Integrada |
| Clima y humedad | ERA5-Land (Copernicus) | ~9 km, horaria | Copernicus | Climate Data Store | Planificada |
| Humedad del suelo | SAOCOM 1A/1B (Humedad del perfil) | 50–100 m, penetración 10–50 cm | CONAE (abierta con registro) | Catálogo Abierto CONAE | Planificada (#22) |
| Humedad del suelo | NISAR SME2 (Banda L/S) | ~200 m | Dominio público (NASA/ISRO) | Earthdata | En espera (lanzamiento) |
| Humedad del suelo | NASA SMAP L4 | 9 km | Dominio público | Earthdata | Planificada |
| Agua histórica | JRC Global Surface Water | 30 m, desde 1984 | Copernicus / CC BY 4.0 | Tiles / GEE | Planificada (#41) |
| Agua histórica | MapBiomas Argentina (agua) | 30 m | CC BY-SA | Plataforma MapBiomas | Planificada |
| Agua actual / Inundación | Copernicus GFM (Sentinel-1 SAR) | 20 m | Copernicus Open Access | API REST / WMS CEMS | Planificada (spec 012) |
| Agua actual | OPERA DSWx-HLS | 30 m | Dominio público | PO.DAAC / AWS | Planificada |
| Cobertura del suelo | ESA WorldCover · Dynamic World · MapBiomas | 10–30 m | CC BY 4.0 / CC BY-SA | Tiles / GEE | Planificada |
| Caminos, canales y alcantarillas | OpenStreetMap | Vectorial | ODbL (citar) | Overpass API | Planificada |
| Vigor del cultivo | Sentinel-2 L2A | 10 m | Copernicus | STAC Earth Search (AWS) | Integrada |
| Vigor del cultivo | HLS (Landsat + Sentinel-2) | 30 m | Dominio público | LP DAAC | Planificada |
| Rindes | Estimaciones agrícolas MAGyP | Departamento | Datos abiertos | datos.magyp.gob.ar | Planificada |
| Precios | Bolsa de Cereales de Buenos Aires · Bolsa de Comercio de Rosario | Diaria | Uso con cita | Publicaciones / API | A verificar |
| Napa | Freatímetro del productor · informes INTA San Luis | Puntual | Del productor / INTA | Carga manual | Planificada (#40) |
| **Descarte explícito** | CLMS SSM 1 km (Copernicus Surface Soil Moisture) | 1 km | Copernicus | CDS | **Descartada** (solo Europa continental) |
| **Descarte parcial** | OPERA DSWx-S1 (Sentinel-1 Water) | 30 m | Dominio público | PO.DAAC | **Descartada para intralote** (umbral > 3 ha y 200 m) |

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

---

## 5. Cartografía y Límites Jurisdiccionales Oficiales (IGN)

### 5.1 Límites Vectoriales de Provincias y Departamentos
- **Fuente:** Instituto Geográfico Nacional de la República Argentina (IGN).
- **Servicio WFS:** `https://wms.ign.gob.ar/geoserver/ows`
- **Capas descargadas:**
  - `ign:provincia` (24 jurisdicciones de primer orden)
  - `ign:departamento` (529 departamentos y partidos)
- **Licencia:** Datos Abiertos IGN / IDERA (Ley Nacional de la Carta N° 22.963) · Licencia Creative Commons Atribución 4.0 Internacional (CC-BY 4.0).
- **Cita obligatoria:** `FUENTE: Instituto Geográfico Nacional de la República Argentina`.
- **Fecha de descarga y procesamiento:** 2026-11-23.
- **Script generador:** `scripts/generar_limites_ign.py`
- **Archivos estáticos en repositorio:**
  - `apps/web/public/data/boundaries/provincias.geojson` (167,3 KB, 24 features)
  - `apps/web/public/data/boundaries/departamentos.geojson` (761,8 KB, 529 features)
  - **Peso total combinado:** 929,1 KB (< 1 MB en disco).
- **Uso en la aplicación:** Renderizado vectorial en cliente MapLibre GL sin depender de WMS ráster externo ni latencia de red, permitiendo estilos nítidos por nivel de zoom y geolocalización local rápida (point-in-polygon) para la ficha de ubicación sin consultas adicionales.

---

## 6. Observaciones Satelitales Avanzadas y Validación Empírica

### 6.1 Copernicus Global Flood Monitoring (GFM)
- **Proveedor:** Copernicus Emergency Management Service (CEMS) / European Commission.
- **Sensor:** Sentinel-1 C-SAR (apertura sintética, microondas banda C, 5,4 GHz).
- **Resolución espacial:** 20 m.
- **Licencia:** Libre y gratuita (Copernicus Open Access).
- **Acceso:** API REST OGC y WMS de CEMS (`https://emergency.copernicus.eu/mapping/ems/global-flood-monitoring`).
- **Fecha de consulta:** 2026-11-23.
- **Uso en el sistema (Spec 012):** Detección continua de agua superficial y anegamiento incluso bajo nubosidad persistente durante temporales. Sirve como estándar de verdad de terreno (*ground truth*) satelital para validar la extensión de áreas anegables simuladas en fechas de inundaciones históricas.

### 6.2 ICESat-2 ATL08 (Land and Vegetation Height)
- **Proveedor:** NASA / NSIDC (National Snow and Ice Data Center).
- **Sensor:** ATLAS (Advanced Topographic Laser Altimeter System), lidar de conteo de fotones (532 nm, luz verde).
- **Resolución espacial:** Huella circular de ~11 m de diámetro cada 0,7 m a lo largo de la traza, agrupada en segmentos geodésicos de 100 m.
- **Precisión vertical:** $< 0,10\text{ m}$ en superficies planas o suavemente onduladas.
- **Licencia:** Dominio público (NASA Open Data Policy).
- **Acceso:** NASA Earthdata y OpenAltimetry API (`https://openaltimetry.org/data/api/v1/`).
- **Fecha de consulta:** 2026-11-23.
- **Uso en el sistema (Spec 012):** Perfilado altimétrico independiente de alta precisión para contrastar y validar la cota de modelos digitales regionales (Copernicus GLO-30 y Google GEM-15 DTM) a lo largo de las órbitas que cruzan la región pampeana y San Luis.

### 6.3 CHIRPS v3 (Climate Hazards Center InfraRed Precipitation with Station data)
- **Proveedor:** Climate Hazards Center, University of California Santa Barbara (UCSB CHC).
- **Resolución espacial:** $0.05^\circ \times 0.05^\circ$ (~5,3 km).
- **Resolución temporal:** Diaria (desde 1981 al presente).
- **Licencia:** Dominio público.
- **Acceso:** HTTP / FTP público (`https://data.chc.ucsb.edu/products/CHIRPS-3.0/`).
- **Fecha de consulta:** 2026-11-23.
- **Nota operativa crítica:** La versión CHIRPS v2 se discontinúa definitivamente tras diciembre de 2026. Todas las rutinas de series históricas y cálculo de anomalías pluviométricas de 6 meses (#21 y #42) deben conectarse directamente al catálogo de **CHIRPS v3**.

### 6.4 SAOCOM 1A/1B (Humedad del Suelo en el Perfil)
- **Proveedor:** Comisión Nacional de Actividades Espaciales (CONAE), Argentina.
- **Sensor:** Radar de Apertura Sintética en Banda L (1,27 GHz, longitud de onda 23,6 cm, polarimétrico).
- **Resolución espacial:** 50 m a 100 m.
- **Penetración del suelo:** 10 a 50 cm de profundidad, dependiendo del contenido de humedad y textura.
- **Licencia y términos de uso:** Catálogo Abierto CONAE, gratuito para usuarios registrados con fines de investigación, docencia, planificación agronómica y desarrollo tecnológico no comercial de exportación cerrada.
- **Acceso:** Catálogo CONAE (`https://catalogos.conae.gov.ar/`).
- **Fecha de consulta:** 2026-11-23.
- **Verificación territorial:** Cobertura regular confirmada sobre Villa Mercedes y el departamento General Pedernera (San Luis). Aporta el mapa de agua útil del perfil para condicionar la infiltración previa (#22).

### 6.5 Red de Estaciones Meteorológicas de San Luis (REM)
- **Proveedor:** Universidad de La Punta (ULP) / Ministerio de Ciencia y Tecnología de San Luis.
- **Cobertura:** Más de 60 estaciones telemétricas automáticas en el territorio provincial.
- **Resolución temporal:** Registros horarios y acumulados diarios.
- **Licencia:** Datos públicos abiertos de la provincia de San Luis.
- **Acceso:** Endpoint web directo (`http://clima.edu.ar/ObtenerCsv.aspx?tipo=Mensual&estacion=ID...`, Windows-1252).
- **Fecha de consulta:** 2026-11-23.
- **Estado:** Integrada plenamente en el conector `geoprocessing/climate/rem_sanluis.py` (#23 / PR #100). Prioridad para el cálculo de humedad antecedente (AMC) en lotes ubicados a menos de 40 km de una estación provincial activa.

### 6.6 NISAR SME2 (NASA-ISRO SAR Mission - Soil Moisture)
- **Proveedor:** Misión conjunta NASA / ISRO.
- **Sensor:** Radar Banda L (1,2 GHz) y Banda S polarimétrico.
- **Resolución espacial:** 200 m.
- **Licencia:** Dominio público (Open Science).
- **Acceso:** NASA Earthdata / ASF DAAC.
- **Fecha de consulta:** 2026-11-23.
- **Estado:** En espera operativa (satélite en fase final de integración y lanzamiento programado).

---

## 7. Descarte Técnico de Fuentes Inadecuadas

Para garantizar transparencia científica y evitar desarrollos fallidos, se documenta el descarte de las siguientes fuentes evaluadas:

1. **CLMS SSM 1 km (Copernicus Land Monitoring Service - Surface Soil Moisture):**
   - **Motivo de descarte:** Cobertura territorial nula en Argentina. El producto oficial opera exclusivamente sobre Europa continental y la cuenca mediterránea.
2. **OPERA DSWx-S1 (Sentinel-1 Dynamic Surface Water - JPL / NASA):**
   - **Motivo de descarte para anegamiento intralote:** La especificación técnica del producto satelital establece que fue diseñado para cuerpos de agua $\ge 3\text{ ha}$ y un ancho mínimo de canal $\ge 200\text{ m}$. En campos agrícolas de llanura, los encharcamientos temporarios en bajos y surcos son de escala sub-hectárea, por lo que OPERA DSWx-S1 produce omisiones sistemáticas (falsos negativos). Se reserva exclusivamente OPERA DSWx-HLS para lagunas mayores.


