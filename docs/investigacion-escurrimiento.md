# Investigación: insumos para simular escurrimiento y drenaje a escala de lote en la llanura de San Luis

**Fecha:** 19/11/2026 · **Proyecto:** Complemento a RotaTerra · **Alcance:** lotes de 20–500 ha, Villa Mercedes / General Pedernera

> **Nota (21/11/2026):** esta investigación se escribió cuando regía la regla "solo NASA". Esa regla ya no aplica: el proyecto usa cualquier fuente abierta, real y verificable (regla 4 de `AGENTS.md`). Las menciones a "excepciones" quedan como contexto histórico.

## Conclusión principal

Ningún MDE satelital global alcanza para simular bien el escurrimiento interno de un lote en esta llanura: tienen errores verticales de 1 a 5 m, y la pendiente real ronda el 1%. La base correcta es el **MDE/MDT aerofotogramétrico de 5 m del IGN** (precisión vertical submétrica según el IGN), si cubre el lote. Si no hay cobertura: **MDE-Ar v2.1** (30 m, ~2 m de precisión vertical, IGN) o FABDEM, con resultados declarados como orientativos. Esto requiere una excepción formal a la regla "solo NASA + INTA + productor" de N4-4-1.2.

- **Terreno:** MDT 5 m IGN, después MDE-Ar v2.1 30 m y Copernicus GLO-30 (OpenTopography); NASADEM solo como respaldo NASA. FABDEM es el mejor global sin vegetación, pero su licencia es **CC BY-NC-SA 4.0 (no comercial)**. Acondicionar con *breaching* (Lindsay 2016), no con relleno puro, que en llanura genera falsas "lagunas planas".
- **Física:** onda inercial local (Bates 2010 / de Almeida 2012, como Landlab `OverlandFlow` o LISFLOOD-FP) + Curva Número con valores pampeanos. En siembra directa el CN de la Pampa Ondulada no bajó respecto de labranza convencional (CN 82 en AMC II).
- **Lluvia:** no hay curvas IDF medidas en Villa Mercedes; lo publicado está transpuesto desde Córdoba (DIT, estación Pozo Cavado: 101 mm/día para 100 años).
- **Riesgo dominante:** el anegamiento depende más de la **napa freática** (cuenca El Morro) que de la lámina de un evento. Un simulador solo hortoniano subestima los anegamientos. Hace falta una capa de napa y validar contra OPERA DSWx (30 m).

## Anomalías y riesgos

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| 1 | Error vertical de MDE globales (1–5 m) mayor que el desnivel del lote | D8/D∞ y TWI espurios (NASADEM dio 2,76% contra ~1% real) | MDT 5 m IGN; suavizado; reportar incertidumbre |
| 2 | COP30, AW3D30, SRTM y NASADEM son **DSM** (montes, cortinas, galpones, silos) | Barreras falsas y depresiones falsas detrás de cortinas | FABDEM o MDT IGN; máscara de árboles con HLS/NDVI |
| 3 | Bandeado y speckle en SRTM/NASADEM | Microdepresiones artificiales | Filtro con preservación de bordes + *breaching* |
| 4 | FABDEM no comercial y share-alike | Conflicto legal ante uso comercial | Solo modo "investigación" o licencia de Fathom |
| 5 | Sin pluviógrafos locales publicados | IDF transpuesta, error ±20% | Rótulo "lluvia de diseño regional"; carga de pluviómetro propio |
| 6 | IMERG 0,1° (~10 km); Late sin corrección con pluviómetros | No resuelve la celda convectiva; subestima picos de 30 min | IMERG para el volumen, no para la intensidad pico |
| 7 | Napa somera no observable por satélite a escala lote | Anegamientos freáticos invisibles | Capa de napa del productor; GRACE solo contexto |
| 8 | CN de tablas USDA no calibrado para Ustipsamentes/Haplustoles | Escurrimiento sesgado | Rangos, sensibilidad, calibración con eventos |

## 1. Modelos digitales de elevación

| MDE | Resol. | Tipo | Precisión vertical | Artefactos en llanura | Acceso | Licencia | Veredicto |
|---|---|---|---|---|---|---|---|
| **MDE/MDT 5 m IGN** | 5 m | MDE y MDT separados | Submétrica (IGN) | MDT limpio; MDE con objetos | Visor Argenmap / `.img`; algunos sectores por pedido a Ventas IGN | Citar "FUENTE: Instituto Geográfico Nacional de la República Argentina"; no alterar originales; fechar derivados | **Primera opción** si cubre |
| **MDE-Ar v2.1** | 30 m | Híbrido SRTM+ALOS (superficie) | ~2 m; 24.072 puntos de validación | Hereda DSM | Por hoja; Geoserver IGN (WCS) | IGN | Mejor 30 m oficial; datum SRVN16 |
| Copernicus GLO-30/90 | 30/90 m | DSM | RMSE 4,89 m vs LiDAR en zonas inundables (FABDEM 2,62; NASADEM 4,76; SRTM 5,38; AW3D30 5,75) | Árboles y edificios | OpenTopography `COP30`/`COP90`; AWS COG | Copernicus, libre con atribución | Segunda opción operativa |
| FABDEM | 30 m | **DTM** (GLO-30 sin bosques ni edificios) | RMSE 1,18 m en la clase de menor pendiente vs ICESat-2 | No corrige cortinas finas | Tiles 1°×1° (data.bris); no está en OpenTopography | **CC BY-NC-SA 4.0** | Mejor global sin objetos; solo no comercial |
| NASADEM | 30 m | DSM | Pocos metros en llanura | Ruido; pendiente inflada | OpenTopography; LP DAAC | Dominio público | Respaldo "solo NASA" |
| SRTM GL1 | 30 m | DSM | Peor que COP30 y FABDEM | Ídem | OpenTopography | Dominio público | Evitar |
| ALOS AW3D30 | 30 m | DSM óptico | Distribución de errores sesgada | Objetos, nubes rellenadas | OpenTopography | JAXA | Solo como insumo de MDE-Ar |
| ASTER GDEM | 30 m | DSM óptico | La peor | Artefactos de nubes | LP DAAC | Libre | Descartar |

A 30 m, un lote de 25 ha tiene ~280 celdas; con 1–2 m de error sobre 1–3 m de desnivel, las vías internas quedan mal definidas (sirve para contexto de cuenca). El MDT 5 m multiplica por 36 las celdas y deja el error por debajo del desnivel. En el visor, la exageración vertical tiene que ser explícita.

**Supuesto abierto:** no se pudo confirmar si el MDT 5 m cubre General Pedernera. Se consulta en el visor IGN (capa "MDE aerofotogramétrico 5 m"). Plan B: MDE-Ar v2.1 + FABDEM/COP30 o relevamiento con dron del productor (el IGN acepta "MDE/MDT VANT").

### Acceso sin descargar todo

| Vía | Qué ofrece | Notas |
|---|---|---|
| OpenTopography Global DEM API | Recorte por bbox de `COP30`, `COP90`, `NASADEM`, `SRTMGL1`, `AW3D30`, `GEDI_L3`, `EU_DTM` | API key gratuita; para software integrado se pide *enterprise key* |
| OpenTopography Point API | Altura puntual (COP30 por defecto) | Validar contra puntos GNSS |
| Earthdata / LP DAAC (CMR-STAC) | NASADEM, ASTER, SRTM | Earthdata Login |
| AWS Open Data | Copernicus DEM en COG; OPERA DSWx | `rasterio` / GDAL `/vsicurl/` |
| Geoserver IGN | WMS/WFS/WCS en `wms.ign.gob.ar/geoserver`; VANT por WCS en `imagenes.ign.gob.ar` | Verificar si el 5 m está por WCS |

### Acondicionamiento para llanura

| Paso | Herramienta | Parámetro | Motivo |
|---|---|---|---|
| 1. Reproyección | GDAL | UTM 20S (EPSG:32720) o POSGAR 2007 faja 4 | Celdas métricas |
| 2. Suavizado con preservación de bordes | WhiteboxTools `FeaturePreservingSmoothing` | Filtro 11 celdas, umbral normal 8–15° | Baja el speckle |
| 3. Quema de canales/alcantarillas/caminos | Vectores productor/IGN | −0,5 a −1 m | Los terraplenes son diques reales |
| 4. *Breaching* | WhiteboxTools `BreachDepressionsLeastCost` / RichDEM | Brecha máx. ~0,5–1 m; luego relleno remanente | Lindsay 2016 (Hydrol. Process. 30(6):846–857): modifica menos el terreno |
| 5. Conservar depresiones reales | Mapa de bajos (HLS/DSWx) | No acondicionar bajos con agua observada | Son justo lo que se quiere simular |
| 6. Flujo | D∞ (Tarboton) para TWI/SPI; D8 para red | MFD/D∞ en llanura | D8 genera líneas paralelas falsas |

**Clave:** dos MDE, uno acondicionado (flujo, TWI, SPI) y otro mínimamente tocado (agua somera 2D), para que el 2D pueda llenar las depresiones con agua.

## 2. Suelos

| Fuente | Escala | Contenido | Acceso | Uso |
|---|---|---|---|---|
| Cartas de suelo INTA–Gob. San Luis (Villa Mercedes 2000, Buena Esperanza 1992, etc.) | 1:100.000 | Unidades, series, taxonomía, aptitud | GeoINTA (visor, WMS/WFS); PDF | Capa base |
| Carta de suelos y vegetación de San Luis (Peña Zubiate et al., 1998) | Provincial | Síntesis | INTA/SAGPyA | Contexto |
| SISINTA | Perfiles | ~800 perfiles históricos de San Luis con análisis | Base abierta INTA | Pedotransferencia (Ksat, AU) |
| Mapa INTA de agua útil | Basado en cartas 1:100.000 | AU a 1 y 2 m | INTA Clima y Agua / San Luis | Balance hídrico |
| **HYSOGs250m (ORNL DAAC, NASA)** | ~250 m | Grupo hidrológico A–D | Earthdata, WCS ORNL | **Respaldo NASA del GH** |
| SoilGrids 250 m / HWSD | 250 m / ~1 km | Textura, densidad, MO | API REST | Solo si falta INTA |

A escala 1:100.000 las unidades mezclan médanos y bajos; los autores INTA advierten que no permite cuantificar unidades menores. Desagregar con TWI/posición y NDVI histórico de HLS.

### Grupos hidrológicos esperables (inferencia; validar con SISINTA)

| Suelo / posición | Textura | GH | Ksat orientativa | AU (1 m) | Notas |
|---|---|---|---|---|---|
| Ustipsamentes típicos (médanos, lomas; serie Buena Esperanza) | Arenosa / arenosa franca | **A** (B con costra) | Decenas a >100 mm/h | ~60–90 mm | El sellado superficial con baja MO dispara escurrimiento |
| Haplustoles énticos (planicie eólica) | Franco arenosa | **B** | ~10–40 mm/h | ~100–140 mm | Suelo agrícola dominante del este |
| Haplustoles típicos/énticos francos | Franca / franco limosa | **B–C** | ~5–15 mm/h | ~140–180 mm | Más estructurados |
| Bajos con napa somera, hidrohalomórficos | Variable | **D** (napa <60 cm) | Casi nula al saturarse | — | HYSOGs asigna D con napa <60 cm |

Ksat y AU son rangos genéricos USDA, no mediciones locales: reemplazar con pedotransferencia (Saxton-Rawls) sobre SISINTA.

### Curva Número: evidencia argentina

| Estudio | Sitio | Resultado |
|---|---|---|
| Chagas et al. 2008, Ciencia del Suelo 26(1) | Microcuenca 300 ha, Pampa Ondulada, LC 1994–98 vs SD 1999–2004 | CN AMC II = **82** en ambos; AMC III = 96; AMC I: LC 56 vs SD 68 |
| Ciencia del Suelo 24(2), 2006 | Pampa Ondulada | SD con CN **mayores** que LC |
| Ciencia del Suelo 32(1), 2014 | Pampa Serrana vs Ondulada | CN ~62 vs ~82 |
| Ciencia del Suelo 40(1), 2022 | Microcuenca aforada, Pampa Ondulada | CN asintótico ~82 |

La siembra directa no necesariamente baja el CN. Los estudios son de suelos limosos de la Pampa Ondulada: tomarlos como **cota superior** para los arenosos de San Luis.

### CN por defecto (AMC II, NRCS TR-55/NEH-630 ajustada)

| Cobertura / manejo | A | B | C | D |
|---|---|---|---|---|
| Suelo desnudo / barbecho limpio | 77 | 86 | 91 | 94 |
| Hileras, SD con buen rastrojo (>30%) | 64 | 75 | 82 | 85 |
| Hileras, SD con poco rastrojo | 67 | 78 | 85 | 89 |
| Granos finos (trigo/centeno) | 62 | 73 | 81 | 84 |
| Pastura perenne buena (alfalfa, pasto llorón) | 39 | 61 | 74 | 80 |
| Pastizal/monte natural (caldenal) bueno | 30–36 | 55–60 | 70–73 | 77–79 |

Editables por el usuario, con banda de sensibilidad ±5. AMC I/III con 5 días previos de lluvia (IMERG/POWER) y SMAP L4.

## 3. Lluvia de diseño y eventos

| Dato | Valor | Fuente / límite |
|---|---|---|
| Lluvia media anual Villa Mercedes | 606,6 mm (1903–2008) | INTA San Luis |
| Tendencia | +22% (566 → 688 mm/año); días >50 mm ×1,5 | Santoni et al. 2010 |
| Estacionalidad | Verano 41–45%, primavera 32–38% | INTA San Luis |
| Máx. diaria, Pozo Cavado (cuenca media río Quinto) | T5 60; T10 70; T20 79; T50 92; **T100 101**; T200 110 mm; PMP 303 mm | Caamaño Nelli & Colladon (INA/CONICET), 1954–1989, n = 20 |
| Modelo i-d-T | DIT: ln i = A·Φy − B·δy + C; δy = (ln d)^q, q = 5/3; d 5–1440 min; T 2–200 años | Transpuesto desde Río Cuarto: sin pluviografía en San Luis |
| Precisión de la regionalización | ±20% (T 5–50 años) | Catalini et al. 2014 (84 pluviómetros, 0 pluviógrafos) |
| Evento extremo | ~120 mm en 1 h 20 min, Villa Mercedes, nov. 2013 | Agencia de Noticias San Luis (periodístico) |

**Recomendación:** DIT con parámetros de Río Cuarto escalados a Pozo Cavado; hietograma de bloques alternos con duración 1–2 × tiempo de concentración (30 min–3 h para 20–500 ha); T = 2, 10, 25, 100 años con rótulo "IDF regional transpuesta, error ±20%". El evento de 2013 sirve como tormenta de estrés.

### IMERG

| Aspecto | Realidad | Uso |
|---|---|---|
| Resolución | 0,1° (~10 km), 30 min | Una celda ≈ 10.000 ha |
| Picos | Subestima intensidades convectivas de 30 min | Volumen del evento, redistribuido con DIT o pluviómetro |
| Latencia | Early ~4 h; Late ~14 h; Final ~3,5 meses | Early/Late para ayer; Final para validar |
| Riesgo | Late sin corrección con pluviómetros | `calidad = dudosa` |

## 4. Erosión (USLE/RUSLE)

| Factor | Valor / fuente | Comentario |
|---|---|---|
| **R** | Regresión INTA (Gaitán et al. 2017): R = 0,2266 · PMA^1,1289 → con PMA 607–688 mm, R ≈ 315–362 (≈ 3.150–3.600 MJ·mm·ha⁻¹·h⁻¹·año⁻¹; **cálculo propio**) | Rojas & Conde (1985) referencia histórica; La Pampa 280–530 (Fournier) |
| **K** | Wischmeier con perfiles SISINTA | Arenas finas con MO <1% → K alto; lotes con C orgánico <0,5% los más erosionados |
| **LS** | Desde el MDT (Desmet & Govers / RUSLE) | Con MDE 30 m ruidoso sale inflado |
| **C** | Por rotación/cobertura; desnudo = 1 | Umbral de cobertura superado con 62,5–78% de centeno (INTA San Luis) |
| **P** | Tablas USDA (≈0,5–0,9) | Con pendiente <1% las terrazas aportan poco: mostrarlo como resultado |

Evidencia local: en El Morro los suelos agrícolas pierden 2 a 7 veces más sedimento que la vegetación natural; el centeno de cobertura redujo 75% la erosión hídrica y 88% la eólica cerca de Villa Mercedes (2021–2023, INTA-UNSL); cultivos de cobertura con soja y maní: −50 a −70%.

**Erosión eólica:** 64% de San Luis es susceptible (Peña Zubiate et al. 1985). Incluirla en una fase posterior como **índice de riesgo** con RWEQ simplificado (viento MERRA-2/POWER, fracción erodible por textura, rugosidad, cobertura HLS).

## 5. Motor hidrológico

| Herramienta | Qué hace | Validación | Uso |
|---|---|---|---|
| **Landlab `OverlandFlow`** | Inercial local (de Almeida 2012), Δt adaptativo, θ 0,8–0,9 | Adams et al. 2017, GMD | **Motor de referencia** |
| LISFLOOD-FP | Inercial, adaptativo, DG2 | Benchmarks UK EA (Neal et al. 2012) | Benchmark offline |
| HEC-RAS 2D | SWE completo / difusiva | Estándar de industria | Referencia comparativa |
| WhiteboxTools | *Breaching*, D∞, TWI, SPI, LS | Amplio uso | Preprocesamiento |
| RichDEM | Priority-flood, *breaching* | Barnes et al. | Alternativa liviana |
| pysheds | D8/D∞, cuencas | Amplio uso | Red de drenaje |
| TauDEM | D∞, MPI | Referencia D∞ | Si hace falta escala |

Bates et al. (2010): el Δt estable escala con 1/Δx, no (1/Δx)², pasos 1–3 órdenes mayores que los difusivos; de Almeida (2012) agrega θ. Δt ≈ 0,2–0,7 × CFL. Para 500 ha a 5 m (200.000 celdas), segundos a minutos por evento en Python/Numba.

**GPU (fase 2):** mismo esquema en WebGL2/WebGPU. Las "tuberías virtuales" (Mei et al. 2007) son rápidas pero **no están validadas**: usarlas solo como vista previa.

**Acoplamiento:** lluvia neta CN distribuida con el hietograma como fuente del 2D; Manning por cobertura (barbecho 0,03–0,05; rastrojo SD 0,05–0,15; pastura 0,15–0,25); la napa limita el almacenamiento.

### Validación

| Fuente | Resol./frecuencia | Uso |
|---|---|---|
| **OPERA DSWx-HLS** | 30 m, desde abril 2023, latencia ~3 días | Agua superficial abierta y parcial |
| **OPERA DSWx-S1** | 30 m, 6–12 días, ve a través de nubes (DOI 10.5067/OPDSWS1-L3V1) | Postormenta; solo cuerpos >3 ha y >200 m de ancho |
| HLS NDWI/MNDWI | 30 m | Respaldo |
| MODIS MOD09/MCD43 | 250–500 m | Series regionales desde 2000 |
| Productor | Puntos/polígonos | Verdad de campo |

Métricas: índice F = A∩B / A∪B, sesgo de área, aciertos en bajos conocidos.

## 6. Napa y anegamiento regional

| Hecho | Dato | Fuente |
|---|---|---|
| Ascenso freático por agricultura | Napa de 12–6 m a 4–0 m de profundidad | Houspanossian et al. 2023, *Science* 380:1344–1348 |
| Inundaciones lentas Pampa Occidental | Sobre todo 2000–2003; MODIS + GRACE | Kuppel et al. 2015, *WRR* |
| 1997–2003 | 27% de la Pampa occidental; napa +2,3 m | IAI / Jobbágy |
| Cuenca El Morro | Anegamiento y salinización; napa más somera en primavera; sin relación directa con la lluvia mensual | INTA San Luis 2017 |
| Emergencia El Morro | ~370.000 ha; RN 7 y RN 8 anegadas en 2008 | La Nación (periodístico) |
| Villa Mercedes urbano | Napa a 0,5 m (2016) → 2,5 m (2017) tras bombeo | San Luis Agua |

Dos modos: **evento** (2D + CN, horas) y **estacional** (balance diario con napa). GRACE (~300 km) solo como tendencia regional. Profundidad de napa del productor como entrada de primera clase.

## 7. Datos NASA adicionales

| Producto | Resol. | Latencia | Acceso | Uso |
|---|---|---|---|---|
| OPERA DSWx-HLS | 30 m | días | PO.DAAC / AWS / CMR-STAC | Validación |
| OPERA DSWx-S1 | 30 m | días | PO.DAAC / AWS | Agua bajo nubes |
| HYSOGs250m | ~250 m | Estático | ORNL DAAC | Grupo hidrológico |
| OPERA DIST-ALERT-HLS | 30 m | días | LP DAAC | Suelo desnudo / factor C |
| OPERA RTC-S1 | 30 m | días | ASF DAAC | Retrodispersión |
| ICESat-2 ATL08 | Trazas, segmentos 20 m | semanas | NSIDC | Control vertical del MDE |
| GEDI L3 | 1 km | Estático | OpenTopography | Altura de dosel |

## 8. Fuente por capa

| Capa | Primaria | Respaldo | ¿Excepción a "solo NASA"? | `calidad` |
|---|---|---|---|---|
| Terreno | MDT 5 m IGN | MDE-Ar v2.1 → COP30 → NASADEM | **Sí: IGN**; COP30 (ESA) | buena / dudosa |
| Terreno sin objetos | FABDEM | — | Sí, no comercial | dudosa |
| Grupo hidrológico | Carta INTA + SISINTA | HYSOGs250m | No | dudosa |
| Ksat / AU | Pedotransferencia SISINTA; mapa AU INTA | SoilGrids | SoilGrids: sí | dudosa |
| CN | NRCS + calibración pampeana | — | No | dudosa |
| Lluvia de diseño | DIT regional | — | **Sí: INA/CONICET** | dudosa |
| Lluvia de evento | Pluviómetro productor | IMERG | No | buena / dudosa |
| Humedad antecedente | SMAP L4 | 5 días IMERG/POWER | No | buena |
| Napa | Freatímetro productor | GRACE (contexto) | No | según fuente |
| Validación | OPERA DSWx | HLS MNDWI | No | buena |
| Erosión R | Fórmula INTA | — | No | dudosa |
| Viento | MERRA-2 / POWER | — | No | buena |

**Contrato:** mantener `Observacion` y agregar `raster_ref` (URI de COG) para rasters. Ejemplo: `variable="elevacion_mdt"`, `unidad="m (SRVN16)"`, `fuente="IGN MDT 5m"`, `resolucion_m=5`. Registrar siempre el **datum vertical**: SRVN16 (IGN) ≠ EGM2008 (COP30) ≠ EGM96 (NASADEM/SRTM); mezclarlos produce escalones de varios metros.

**Excepciones a documentar:** IGN; ESA Copernicus DEM; FABDEM (solo no comercial, apagado por defecto); INA/CONICET/UNC (DIT); SoilGrids/ISRIC (solo si falta INTA).

## Caveats

- Cobertura del MDT 5 m IGN en General Pedernera **no verificada**.
- Ksat, AU y CN por GH son rangos genéricos USDA/NRCS. El R es cálculo propio con fórmula INTA.
- El Morro (370.000 ha) y el evento de 120 mm/80 min vienen de fuentes periodísticas.
- Latencias de IMERG y valores de Manning: confirmar en la documentación vigente antes de fijarlos en código.

## Fuentes principales

- IGN, Modelos Digitales de Elevación: https://www.ign.gob.ar/NuestrasActividades/Geodesia/ModeloDigitalElevaciones/Introduccion
- IGN, preguntas frecuentes MDE: https://www.ign.gob.ar/NuestrasActividades/Geodesia/ModeloDigitalElevaciones/faq
- Geoserver IGN imágenes: https://imagenes.ign.gob.ar/geoserver/ows?service=wms&version=1.3.0&request=GetCapabilities
- OpenTopography, Copernicus 30 m actualizado: https://opentopography.org/news/updated-copernicus-30m-DEM-available
- OpenTopography, API keys: https://opentopography.org/blog/introducing-api-keys-access-opentopography-global-datasets
- OpenTopography, desarrolladores: https://opentopography.org/developers
- Comparación de MDE en llanuras (Remote Sensing 2026): https://doi.org/10.3390/rs18101511
- FABDEM (datos): https://data.bris.ac.uk/data/dataset/s5hqmjcdj8yo2ibzi9b4ew3sn
- WhiteboxTools, análisis hidrológico: https://jblindsay.github.io/wbt_book/available_tools/hydrological_analysis.html
- HYSOGs250m (ORNL DAAC): https://daac.ornl.gov/SOILS/guides/Global_Hydrologic_Soil_Group.html
- Chagas et al., CN en Pampa Ondulada (Ciencia del Suelo 2006): https://www.scielo.org.ar/scielo.php?script=sci_arttext&pid=S1850-20672006000200009&lang=es
- Ciencia del Suelo 2014, Pampa Serrana vs Ondulada: https://www.scielo.org.ar/scielo.php?pid=S1850-20672014000100012&script=sci_arttext
- Ciencia del Suelo 2022, microcuenca aforada: https://www.scielo.org.ar/pdf/cds/v40n1/1850-2067-cds-40-01-49.pdf
- Caamaño Nelli & Colladon, lluvias de diseño (INA): https://repositorio.ina.gob.ar/server/api/core/bitstreams/f87050ee-6918-4e5b-ba93-a3044d32d330/content
- IV Taller de Regionalización de Precipitaciones Máximas (2014): https://www.facet.unt.edu.ar/dcyoc/wp-content/uploads/sites/23/2015/04/Pag.001-068.-IV-Taller-sobre-Regionalizaci%C3%B3n-de-Precipitaciones-M%C3%A1ximas-2014.pdf
- Lluvias de Villa Mercedes (INTA): https://produccion-animal.com.ar/clima_y_ambientacion/59-lluvias.pdf
- Erosión eólica en San Luis: https://www.produccion-animal.com.ar/suelos_ganaderos/37-erosion_eolica_san_luis.pdf
- Centeno contra la erosión (San Luis): https://www.argentina.gob.ar/noticias/san-luis-incorporan-centeno-para-controlar-la-erosion
- Landlab OverlandFlow (Adams et al. 2017, GMD): https://ui.adsabs.harvard.edu/abs/2017GMD....10.1645A/abstract
- Bates et al. 2010, formulación inercial: https://ui.adsabs.harvard.edu/abs/2010JHyd..387...33B/abstract
- de Almeida et al. 2012: https://agupubs.onlinelibrary.wiley.com/doi/pdfdirect/10.1029/2011WR011570
- Manual LISFLOOD-FP: https://www.bristol.ac.uk/media-library/sites/geography/migrated/documents/lisflood-manual-v5.9.6.pdf
- Productos OPERA (JPL): https://www.jpl.nasa.gov/go/opera/products/
- OPERA DSWx-S1 (catálogo): https://developers.google.com/earth-engine/datasets/catalog/OPERA_DSWX_L3_V1_S1
- Napa en El Morro (INTA): https://repositorio.inta.gob.ar/xmlui/handle/20.500.12123/1179?show=full
- IAI, alimentos e inundaciones: https://iai.int/en/alimentos-e-inundaciones/
- Emergencia hídrica Villa Mercedes (La Nación): https://www.lanacion.com.ar/sociedad/un-desequilibrio-hidrico-pone-en-emergencia-a-villa-mercedes-en-san-luis-nid1941440/
