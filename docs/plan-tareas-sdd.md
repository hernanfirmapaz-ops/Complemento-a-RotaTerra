# Plan de Tareas y Auditoría SDD vs. Estado del Repositorio (`Complemento-a-RotaTerra`)

## 1. Gobernanza y Metadatos del Plan

- **Proyecto:** `Complemento-a-RotaTerra` — Visor 3D de Hidrología y Suite Agronómica (módulo complementario de ROTARRETA).
- **Rama de desarrollo SDD (§17.2):** `feature/visor-3d-hidrologia` (commit base común con `main` y `origin/feature/visor-3d-hidrologia`: `6165a40cf26bdd0ff00a77a6f257b4456c102257`, `feat(web): dibujador interactivo de lotes con poligonos en mapa y flujo guiado en 3 pasos`).
- **Documento de diseño base (SDD):** `ROTARRETA_visor_3D_hidrologia_SDD.md` (v1.0, 965 líneas).
- **Equipo de 5 agentes especialistas (`.claude/agents/` + `docs/agentes.md`):**
  1. `coordinador` (`.claude/agents/coordinador.md`, Opus) — Planificación, delegación, revisión de diffs, batería de verificación e integración a `main` (**estrictamente solo lectura sobre código de producción** según `.claude/agents/coordinador.md:3,18` y `docs/agentes.md:9`; orquesta verificación y delega cualquier corrección al especialista dueño).
  2. `experto-datos-nasa` (`.claude/agents/experto-datos-nasa.md`, Opus) — Dueño de `geoprocessing/satellite/`, `geoprocessing/net.py`, `geoprocessing/dem/sources.py`, `docs/data-sources.md` y `geoprocessing/tests/fixtures/`; además asume las **extensiones autorizadas por `PROJECT.md` Capa 1**: `geoprocessing/fields.py` (`NASA-04`, ingesta de límites), `data/README.md` (`NASA-05`) y tests offline de clientes/ingesta en `geoprocessing/tests/` (`NASA-01..04`, con revisión de `hidrologo`).
  3. `hidrologo` (`.claude/agents/hidrologo.md`, Opus) — Dueño de `geoprocessing/dem/` (salvo `sources.py`), `geoprocessing/hydrology/`, `geoprocessing/rainfall/`, `geoprocessing/agronomy/`, `geoprocessing/tests/` y `docs/model-limitations.md` (no edita `geoprocessing/satellite/*`).
  4. `backend` (`.claude/agents/backend.md`, Sonnet) — Dueño de `services/api/app/{api/routes,schemas.py,services,core/config.py}`, `services/api/tests/` y `docs/architecture.md`.
  5. `frontend-3d` (`.claude/agents/frontend-3d.md`, Sonnet) — Dueño de `apps/web/src/{components,hooks,services/api.ts,types/api.ts,styles.css,App.tsx,main.tsx}` y `apps/web/vite.config.ts`.
- **Restricciones estrictas (R4 y aislamiento de repositorio):**
  - **Prohibido inventar datos:** Todo dato satelital, climático o parámetro debe provenir de fuentes reales trazables o supuestos conservadores explícitamente documentados, con degradación controlada (`status="unavailable"` / `None` + advertencia explícita) ante fallas de red o nubosidad. Jamás fabricar series meteorológicas ni índices NDVI sintéticos en producción.
  - **Repositorio de referencia intocable:** `C:\Users\haf01\.gemini\antigravity\scratch\Earth2Worlds` NO debe modificarse ni recibir commits bajo ninguna circunstancia. Todo el trabajo se ejecuta exclusivamente dentro de `Complemento-a-RotaTerra`.
  - **Estado documental inicial:** Al inicio de M1, `docs/architecture.md` (líneas 1–29), `docs/data-sources.md` (líneas 1–22) y `docs/model-limitations.md` (líneas 1–7) reflejaban únicamente la Fase 0 (`En la Fase 0 únicamente se implementa la base del Nivel 1`), pese a existir código de Fases 1–5 y 8 herramientas agronómicas.

---

## 2. Matriz de Auditoría: SDD vs. Estado Real Implementado

### 2.1 Niveles de Análisis (§1.1) y Regla de Metadatos de Salida

| Ítem SDD (§1.1) | Requerimiento Autoritativo | Estado Verificado en el Repositorio | Brecha y Responsable |
|---|---|---|---|
| **Principio rector** | No confundir visualización con simulación hidrológica ni usar partículas genéricas como prueba de volumen, velocidad, profundidad o inundación | `TerrainScene3D.tsx` diferencia capas, pero `TerrainDiorama3D.tsx:383-391, 654-858` mezcla `mfd_area_ha` con `water_depth_m` en `waterlogging` y anima gotas por descenso de gradiente sin vincularlas al solver | Separar variables y vincular o rotular explícitamente las trazas en `TerrainDiorama3D.tsx` (`frontend-3d`, M4) |
| **Nivel 1 — Análisis topográfico** | Relieve MDE/MDT y rutas potenciales de drenaje | Implementado en `geoprocessing/dem/` (`terrain.py`, `prepare.py`, `quality.py`) y `geoprocessing/hydrology/` (`conditioning.py`, `flow.py`) | Actualizar `docs/architecture.md` y `docs/model-limitations.md` (`hidrologo` M2, `backend` M3) |
| **Nivel 2 — Estimación de escorrentía** | Lluvia + suelo + cobertura + humedad antecedente con modelo simplificado y supuestos declarados | Implementado en `geoprocessing/rainfall/nrcs_cn.py`, `timeline.py` y `runoff_runs.json` | Exponer `limitations` y `assumptions_and_notes` en Modo Agrónomo (`frontend-3d`, M4) |
| **Nivel 3 — Simulación hidrodinámica** | Evolución temporal de `water_depth_m` y `velocity_m_s` con modelo hidráulico sujeto a calibración | Implementado en `geoprocessing/hydrology/shallow_water_2d.py` (onda difusiva + Manning + estructuras) | Falta advertencia de reparto uniforme de lluvia manual (`backend` M3) y flujo completo de observaciones/calibración UI (`frontend-3d`, M4) |
| **Regla obligatoria de metadatos de salida** | Toda salida debe mostrar nivel de confianza, resolución espacial, resolución temporal, fecha y fuente de datos | Presente parcialmente en `QualityPanel` (solo modo GIS) y `RainfallRunOut`; oculto en Modo Agrónomo (`App.tsx`) y enmascarado por fallbacks sintéticos en `nasa_power_imerg.py` | Eliminar fallbacks sintéticos (`experto-datos-nasa` M2), propagar estados `unavailable` (`backend` M3) y mostrar metadatos en ambos modos (`frontend-3d` M4) |

### 2.2 Alcance Funcional: Incluido en MVP (§2.1) y Fuera del MVP (§2.2)

| Bloque | Ítem SDD (§2.1 / §2.2) | Estado Verificado | Brecha / Acción |
|---|---|---|---|
| **MVP §2.1 (1)** | Ingreso de establecimiento (`farm`) y sus lotes (`field`) | Lotes implementados en `/api/v1/fields` (`routes/fields.py:36-82`); entidad `farm` inexistente en `store.py` y `schemas.py` | Documentar explícitamente esta divergencia de persistencia local monousuario en `docs/architecture.md` (`backend`, M3) |
| **MVP §2.1 (2)** | Importación de límites: GeoJSON, KML/KMZ, Shapefile ZIP, GeoPackage | `geoprocessing/fields.py:271-366` soporta GeoJSON, KML, KMZ y SHP ZIP (sin `.prj`, `.dbf` ni huecos); `.gpkg` no implementado; `App.tsx:834, 1846` omite `.gpkg` en `accept` | Endurecer `parse_shapefile_zip` y soporte `.gpkg` (`experto-datos-nasa` M2) + ampliar `accept` (`frontend-3d` M4) |
| **MVP §2.1 (3)** | Visualización 2D y 3D del terreno | `TerrainScene3D.tsx` (2D/3D) + `TerrainDiorama3D.tsx` (solo 3D); sin fallback 2D cuando WebGL no está disponible | Implementar detección WebGL y vista 2D de respaldo (`frontend-3d`, M4) |
| **MVP §2.1 (4)** | Selección de lote y consulta de elevación, pendiente y cotas | `terrain_point` (`terrain.py:120`) y `contours` (`142`) implementados; modo GIS no renderiza `selectedPoint` (`App.tsx:1192-1236, 2085-2163`); `TerrainDiorama3D` ignora `showContours` (`App.tsx:1187`) | Renderizar `TerrainInspector` en GIS y curvas de nivel en Diorama (`frontend-3d`, M4) |
| **MVP §2.1 (5)** | Perfil altimétrico sobre línea dibujada por el usuario | `POST /api/v1/fields/{field_id}/terrain/profile` + `ProfileChart.tsx` activos en GIS | Habilitar en Modo Agrónomo / mejorar trazado 3D (`frontend-3d`, M4) |
| **MVP §2.1 (6)** | Dirección, acumulación, áreas contribuyentes y rutas potenciales | Implementado en `flow.py` (D8, MFD, subcuencas, red con umbral configurable) | Exponer toggles de `LayerVisibility` en `App.tsx` (`frontend-3d`, M4) |
| **MVP §2.1 (7)** | Carga manual de evento de lluvia e importación de serie CSV | Implementado en `events.py` y `routes/hydrology.py:68-99` | Exponer `declared_total_mm`, `start_at`/`end_at` y los 10 metadatos SDD §5.3 en UI (`frontend-3d`, M4) |
| **MVP §2.1 (8)** | Escorrentía configurable con NRCS Curve Number (CN) | Implementado en `nrcs_cn.py` con `custom_cn_ii` y `lambda_ratio` | Exponer `custom_cn_ii` en UI (`frontend-3d`, M4) |
| **MVP §2.1 (9)** | Animación didáctica diferenciando rutas potenciales vs. simulación temporal | `FlowTimelinePlayer.tsx` + `particle_paths` en GIS; `handleQuickSimulateRain` (`App.tsx:286-360`) olvida refrescar `timeline`; Diorama usa gotas genéricas | Refrescar `timeline` en `FE-A4` (M3) y diferenciar trazas en `FE-B1`/`FE-B2` (M4) |
| **MVP §2.1 (10)** | Comparación entre escenarios de lluvia | Implementado (`GET /hydrology/compare`, `RainfallRunoffPanel.tsx:486-575`) | Mantener cobertura E2E y revisar en Modo Agrónomo |
| **MVP §2.1 (11)** | Panel de fuentes, resolución, supuestos y advertencias | `QualityPanel` solo en modo GIS; Modo Agrónomo oculta advertencias y procedencia satelital | Unificar panel/bandeja de calidad y advertencias en ambos modos (`frontend-3d`, M4) |
| **MVP §2.1 (12)** | Exportación básica de mapas y resultados | `GET /export/geojson` y `GET /export/report` (HTML) implementados; falta captura de mapa o atribución completa de licencias | Agregar atribución de licencias (`backend`, M3) y captura PNG o nota de exportación (`frontend-3d`, M4) |
| **Fuera MVP §2.2** | Alertas oficiales / reemplazo de estudio hidráulico profesional / obras no relevadas / infiltración exacta sin calibración / RUSLE validado / 2D tiempo real en campos extensos | Descargo presente en `QualityPanel` y `zonation.py`; **violado** en `nasa_power_imerg.py:97-136, 454-475` (clima/NDVI inventados) y `erosion_usle.py:73` (`i30` inventado) | Eliminar datos inventados (`experto-datos-nasa` + `hidrologo`, M2), agregar advertencias preliminares prominentes (`frontend-3d`, M4) y documentar límites de celda/cómputo en `docs/model-limitations.md` (M2) |

### 2.3 Casos de Uso Prioritarios CU-01 a CU-06 (§3.2)

| Caso de Uso | Descripción SDD (§3.2) | Estado Actual y Brechas Verificadas |
|---|---|---|
| **CU-01 — Visualizar un lote en 3D** | Cargar lote y DEM, malla 3D y perímetro superpuesto | Operativo en `TerrainScene3D` y `TerrainDiorama3D`; Diorama reinicia la cámara ante cada toggle (`TerrainDiorama3D.tsx:896-905`) y oculta fallos de tiles Esri (`190-206`) |
| **CU-02 — Identificar zonas de concentración** | D8/MFD sobre DEM acondicionado y líneas de concentración | Operativo en `conditioning.py` y `flow.py`; falta romper/brechar barreras en `conditioning.py` y faltan toggles UI para `contours`, `drainageNetwork`, `depressionsAndOutlets` |
| **CU-03 — Simular una lluvia** | Lluvia acumulada/temporal, humedad antecedente, cobertura y suelo → escorrentía | Operativo; `handleQuickSimulateRain` (`App.tsx:339-354`) no recarga `timeline`; `execute_hydrodynamic_2d_on_run` (`services/hydrology.py:584-591`) reparte lluvia manual en 4 pasos uniformes sin advertencia |
| **CU-04 — Comparar eventos** | Comparar ≥ 2 eventos en volumen, zonas de acumulación y sectores críticos | Operativo en `RainfallRunoffPanel.tsx:486-575` (GIS); no accesible en Modo Agrónomo |
| **CU-05 — Inspeccionar un punto** | Clic en terreno → coordenadas, cota, pendiente, acumulación, distancia a ruta de drenaje y resultados del escenario | `terrain_point()` (`services/terrain.py:158-172`) desincronizado en `agronomic_zone_id` tras 2D y sin distancia a ruta de drenaje; modo GIS **no renderiza** `selectedPoint` (`App.tsx:2085-2163`) |
| **CU-06 — Registrar observaciones reales** | Marcar bajos, cárcavas, alcantarillas, terrazas, canales, sectores anegados y puntos medidos | Backend `GET/POST/DELETE /observations` operativo (`routes/hydrology.py:169-191`); `App.tsx:86-90, 668-683` tiene formulario hardcodeado sin setters y nunca llama a `deleteFieldObservation` (`services/api.ts:290-299`) |

### 2.4 Interfaz, Navegación (§4.1–§4.2), Las 17 Capas Activables (§4.3), Panel de Lluvia (§4.4) y Animación (§4.5)

- **Pantalla principal (§4.1):** `App.tsx:724-2185` y `styles.css:31-36, 118, 465` imponen grilla rígida de 3 columnas (`height: 100vh; overflow: hidden`) sin ningún `@media` para móvil `360 px`; la barra inferior (`App.tsx:2166-2184`) descarta `cursorCoords` (`App.tsx:144-146`) y carece de elevación bajo el cursor.
- **Navegación (§4.2):** `exaggeration` inicia en `2.5` (`App.tsx:130`) incumpliendo el valor inicial `1×` del SDD; `TerrainDiorama3D.tsx:314-318` fuerza `baseReliefUnits >= 15`; falta botón "Restablecer cámara / Centrar lote", vista 2D en Agrónomo, selección multi-lote y herramienta dedicada de distancia/área/desnivel.

#### Contraste completo de las 17 Capas Activables (SDD §4.3)

| # | Capa SDD (§4.3) | Modo GIS (`TerrainScene3D.tsx`) | Modo Agrónomo (`TerrainDiorama3D.tsx`) | Brecha Exacta |
|---|---|---|---|---|
| 1 | Imagen satelital / base cartográfica | `basemap: 'satellite' / 'osm'` (`734-789`) | Fetch Esri + fallback procedural (`36-208`) | Sin toggle en `App.tsx:1979-2082`; Diorama oculta fallos de red |
| 2 | Límite de establecimiento y lotes | `layers.boundary` 3D + 2D (`560-587, 791-807`) | `showBoundary` (`577-599`) | Sin toggle en `App.tsx:1979-2082`; solo lote activo (sin multi-lote) |
| 3 | Superficie 3D del terreno | `layers.mesh3d` y `wireframe` (`388-558`) | Siempre visible (`350-476`) | Sin toggle en `App.tsx:1979-2082` |
| 4 | Sombreado de relieve (hillshade) | `surfaceColor: 'hillshade'` (`436-440`) | Solo embebido en fallback (`98-104`) | No seleccionable en Modo Agrónomo |
| 5 | Curvas de nivel | `contours-layer` GeoJSON (`809-817`) | Prop `showContours` ignorada (`20, 217, 903`) | En GIS yace plano en `z=0` bajo la malla y sin toggle; en Diorama no se dibuja |
| 6 | Elevación por gradiente hipsométrico | `surfaceColor: 'elevation'` (`514-519`) | Ausente | Falta en Modo Agrónomo |
| 7 | Pendiente (% o grados) | `surfaceColor: 'slope'` solo `%` (`441-443, 1176`) | Ausente | Leyenda GIS solo `%`; grados (`PointOut.slope_deg`) sin mostrar en tarjeta |
| 8 | Orientación de ladera (aspect) | **Ausente** (`SurfaceColorMode` `18-33`) | **Ausente** | `geoprocessing/dem/terrain.py:52-71` calcula `aspect_deg`, pero `mesh()` (`364-383`) y `MeshOut` (`schemas.py:90-119`) lo omiten |
| 9 | Curvatura de terreno (si resolución permite) | **Ausente** | **Ausente** | No calculada en `terrain.py` ni expuesta en `schemas.py` / `apps/web/` |
| 10 | Dirección de flujo | `MeshOut.d8_code` sin renderizar | Segmentos D8 si `mfd_area_ha >= 1.35` (`602-652`) | `TerrainScene3D.tsx` no dibuja flechas/vectores `d8_code` |
| 11 | Acumulación de flujo | `surfaceColor: 'mfd' / 'd8'` (`444-449`) | Mezclada en `waterlogging` (`383-391`) | Falta capa propia en Agrónomo |
| 12 | Áreas contribuyentes / cuencas | `surfaceColor: 'subbasins'` (`457-463`) + outlets (`1080`) | Ausente | `layers.depressionsAndOutlets` sin toggle en `App.tsx` |
| 13 | Rutas potenciales de escurrimiento | `drainage-network-layer` (`819-827`) + partículas | Gotas por gradiente (`654-858`) + D8 | En GIS yace en `z=0` y sin toggle; en Diorama ignora `timeline.particle_paths` |
| 14 | Lluvia acumulada | **Ausente** como capa espacial | **Ausente** | Solo aparece como parámetro numérico en paneles |
| 15 | Escorrentía estimada | `surfaceColor: 'runoff'` (`464-472`) | No diferenciada | `cumulative_runoff_m3` no seleccionable por separado |
| 16 | Profundidad de agua estimada (si se calcula) | `surfaceColor: 'water_depth'` (`App.tsx:2068`) | `waterlogging` (`TerrainDiorama3D.tsx:383-391`) | **Violación SDD §1.1/§6.6:** Diorama mezcla `water_depth_m` con `mfd_area_ha` aunque no exista corrida 2D |
| 17 | Puntos de observación y estructuras | `field-observations-layer` (`867-876, 1019-1038`) | **Ausente** | Puntos planos en `z=0` sin toggle ni popup; `terraces_geojson` no se renderiza en ningún visor |

*(Capas adicionales ya implementadas fuera de las 17 del SDD: `depressions`, `twi`, `spi`, `velocity`, `agronomic_zones`, `erosion`, `ndvi` en `TerrainScene3D.tsx:473-513`.)*

- **Panel "Evento de lluvia" (§4.4):** `RainfallRunoffPanel.tsx:137-354` cubre carga manual, CSV, muestra, suelo, AMC, cobertura, lambda y compactación; faltan en UI `start_at`/`end_at`, `source_product`, `spatial_resolution`, `quality_flag`, `uncertainty_note`, `declared_total_mm`, `custom_cn_ii`, `burn_lines`/`burn_depth_m` y parámetros 2D (`manning_n`, `ponding_threshold_m`, `recession_minutes`). La regla de **no inventar intensidad** (§4.4 línea 152) está violada en `erosion_usle.py:73` y sin advertencia en `execute_hydrodynamic_2d_on_run` (`services/hydrology.py:584-591`).
- **Controles de animación (§4.5):** `FlowTimelinePlayer.tsx:17-238` funciona en GIS, pero falta toggle independiente para lámina de agua, falta soporte en Modo Agrónomo, falta pausa por `prefers-reduced-motion` y `TerrainScene3D.tsx:1010-1017` reconstruye toda la geometría `BufferGeometry` en cada tick de `transitFraction`.

### 2.5 Datos de Entrada y Reglas Científicas (§5–§6)

- **Límites (§5.1):** `geoprocessing/fields.py:271-366` valida Polygon/MultiPolygon y reproyecta a UTM (`crs.py`), pero `parse_shapefile_zip` (`271-334`) ignora `.prj` (asume WGS84), ignora `.dbf` y trata todas las partes como anillos exteriores (`317-328`); `.gpkg` no está soportado (`336-366`), ni existe edición posterior del perímetro importado.
- **Jerarquía DEM y regla 30 m (§5.2):** Implementada en `dem/sources.py`, `dem/prepare.py`, `dem/quality.py` (Copernicus GLO-30 COG por rangos HTTP + GeoTIFF propio con aviso de escala insuficiente). Faltan `source_url` y `license` en `apps/web/src/services/api.ts:76-111`.
- **Jerarquía de precipitación y 10 metadatos obligatorios (§5.3):** `schemas.py:291-317` y `events.py:258-306` contemplan los metadatos, pero `types/api.ts:314-320` omite 4 campos (`source_product`, `spatial_resolution`, `quality_flag`, `uncertainty_note`). No existen clientes para GPM IMERG V07, SMN, CHIRPS v3 ni ERA5-Land (`nasa_power_imerg.py` solo consulta NASA POWER diario `0.5°` y fabrica clima sintético ante error).
- **Suelos y manejo (§5.4) / Formatos internos (§5.5):** Persistencia local trazable en `FileStore` (`data/runs/<field_id>/`: JSON + `.npz` + GeoTIFF), documentada en `docs/decisiones-fase0.md`.
- **Preprocesamiento DEM (§6.2):** `conditioning.py` soporta `preserve`, `fill_small`, `fill_all` y `apply_burn_in`, pero **no implementa ruptura/brechado de barreras artificiales** ni expone `burn_lines`/`burn_depth_m` en UI.
- **Flujo (§6.3), NRCS-CN (§6.4), Evolución temporal (§6.5), Profundidad/velocidad (§6.6) y Calibración (§6.7):** D8, MFD, subcuencas, NRCS-CN ($S=25400/CN-254$, $I_a=\lambda S$, $Q=(P-I_a)^2/(P-I_a+S)$), hietograma Fase 3 con balance de masa y onda difusiva 2D Fase 4 (`shallow_water_2d.py`) implementados en `geoprocessing/`. Faltan: caudal `flow_discharge_m3_s` en salidas 2D, advertencia de lluvia uniforme 2D, métricas predicción vs. observación, fotos/polígonos en observaciones y limpieza del formulario UI.

### 2.6 Visualización 3D y Rendimiento (§7)

- **Stack (§7.1) y malla (§7.2):** MapLibre GL JS 5 + Three.js 0.176 (`CustomLayerInterface` con `MercatorCoordinate.fromLngLat`). `TerrainDiorama3D.tsx` recrea `WebGLRenderer`/`OrbitControls` ante cambios de props y pierde geometrías de perímetro/drenaje sin `dispose()`. `TerrainScene3D.tsx` dibuja vectores planos en `z=0`.
- **Representación diferenciada del agua (§7.3):** Comprometida en `TerrainDiorama3D.tsx:383-391` al mezclar `mfd_area_ha` con `water_depth_m`.
- **Inspección puntual (§7.4):** Rota en modo GIS (`App.tsx:2085-2163`), incompleta en tarjeta de Agrónomo (`App.tsx:1203-1234`, sin `slope_deg`, `aspect_deg`, `ndvi`, `soil_loss_t_ha`, `warnings`, resolución DEM ni distancia a drenaje) y desincronizada en `agronomic_zone_id` (`services/terrain.py:158-172`).
- **Rendimiento (§7.5) y presupuesto de bundle:** Bundle actual `apps/web/dist/assets/index-*.js` de `1,742.24 kB` (> `500 kB` exigido en `frontend-3d.md`); falta detección WebGL + fallback 2D; falta pausa con `prefers-reduced-motion`.

### 2.7 Arquitectura (§8), las 10 Entidades (§9) y los 15 Endpoints REST `/api/v1` (§10)

- **Arquitectura (§8):** Implementada sobre almacenamiento local `FileStore` (`services/api/app/services/store.py`) en lugar de PostGIS/S3/TiTiler/Celery/Redis (decisión de Fase 0 en `docs/decisiones-fase0.md`). Las operaciones largas son síncronas (`200`/`201`) en vez de `202 Accepted` + `job_id`.
- **Las 10 entidades de datos (§9):**
  1. `farm`: **Ausente** (no existe entidad ni `farm_id`).
  2. `field`: Implementada en `field.json` (`store.py:43-67`), sin `farm_id`, `external_code`, `productive_boundary` ni `updated_at`.
  3. `terrain_asset`: Implementada en `terrain.json` + `dem_utm.tif` (`store.py:70-79`).
  4. `rainfall_event`: Implementada en `rainfall_events.json` (`store.py:96-107`, alcance por lote).
  5. `rainfall_observation`: Embebida como `intervals` dentro de `rainfall_events.json` (`schemas.py:284-288`).
  6. `field_conditions`: Embebida dentro de `runoff_runs.json` (`services/hydrology.py:502-511`).
  7. `hydraulic_feature`: Parcial vía `burn_lines` (`schemas.py:218`) y observaciones `culvert`/`channel`/`terrace` (`shallow_water_2d.py:51-88`), sin tabla/entidad dedicada.
  8. `model_run`: Implementada en `hydrology.json` y `runoff_runs.json` (síncrona, sin `status`/`logs_uri`).
  9. `model_output_asset`: Grillas `.npz`/`.tif` (`hydrology_grids.npz`, `runoff_grids/<run_id>.npz`), sin catálogo individual por activo.
  10. `field_observation`: Implementada en `observations.json` (`store.py:124-135`), sin `photo_uri`, `rainfall_event_id` ni polígonos.
  *(Extra: `toolkit.json` en `services/hydrology.py:785-802`.)*

- **Los 15 endpoints REST `/api/v1` (§10) + rutas adicionales implementadas:**

| # | Endpoint SDD (§10) | Ruta Real en `services/api/app/` | Estado y Diferencias |
|---|---|---|---|
| 1 | `POST /farms` | — | **Ausente** |
| 2 | `GET /farms` | — | **Ausente** |
| 3 | `POST /farms/{farm_id}/fields/import` | `POST /api/v1/fields/import` (`fields.py:41`) | Sin `{farm_id}`; existen además `GET /fields` (`36`) y `POST /fields/sample` (`59`) |
| 4 | `GET /fields/{field_id}` | `GET /api/v1/fields/{field_id}` (`fields.py:77`) | Implementado (no consumido aún en `apps/web/src/services/api.ts`) |
| 5 | `GET /fields/{field_id}/terrain` | `GET /api/v1/fields/{field_id}/terrain` (`terrain.py:29`) | Implementado (`TerrainOut`) |
| 6 | `POST /fields/{field_id}/terrain/process` | `POST /api/v1/fields/{field_id}/terrain/process` (`terrain.py:41`) | Síncrono `200`, no `202 Accepted` |
| 7 | `GET /fields/{field_id}/terrain/profile` | `POST /api/v1/fields/{field_id}/terrain/profile` (`terrain.py:132`) | Implementado como `POST` con `ProfileIn` |
| 8 | `POST /rainfall-events` | `POST /api/v1/fields/{field_id}/hydrology/rainfall-events` (`hydrology.py:68`) | Por lote; más `GET` (`59`) y `POST .../sample` (`99`) |
| 9 | `POST /rainfall-events/{event_id}/series/import` | `POST /api/v1/fields/{field_id}/hydrology/rainfall-events/import-csv` (`hydrology.py:76`) | Crea el evento e importa el CSV en una sola llamada |
| 10 | `POST /fields/{field_id}/hydrology/runs` | `POST .../static` (`45`), `POST .../runoff-runs` (`116`), `POST .../simulate-2d` (`154`) | Dividido en 3 rutas síncronas (`hydrology.py`) |
| 11 | `GET /model-runs/{run_id}` | `GET .../hydrology` (`33`) y `GET .../runoff-runs` (`107`) | Falta consulta unitaria `GET .../runoff-runs/{run_id}` |
| 12 | `GET /model-runs/{run_id}/outputs` | Integrado en `/terrain/mesh`, `/terrain/point`, `/export/geojson` | No existe listado de activos ni descarga de `logs_uri` |
| 13 | `GET /model-runs/{run_id}/timeline` | `GET /api/v1/fields/{field_id}/hydrology/runoff-runs/{run_id}/timeline` (`146`) | Implementado bajo `{field_id}` |
| 14 | `POST /fields/{field_id}/observations` | `POST /api/v1/fields/{field_id}/hydrology/observations` (`178`) | Más `GET` (`169`) y `DELETE .../observations/{obs_id}` (`186`) |
| 15 | `GET /fields/{field_id}/layers` | — (`GET .../hydrology/catalog` en `28` devuelve suelos/cultivos) | **Ausente** endpoint unificado `/layers` con metadatos SDD §17.11 |

*(Endpoints adicionales ya implementados: `GET /api/v1/health` (`main.py:39`, sin `response_model`), `GET .../terrain/mesh`, `GET .../terrain/point`, `GET .../terrain/contours`, `GET .../hydrology/catalog` (sin `response_model`), `POST .../runoff-runs/{run_id}/activate`, `GET .../hydrology/compare`, `GET .../export/geojson` (sin `response_model`), `GET .../export/report`, `GET .../toolkit` y `POST .../toolkit/run` (ambos sin `response_model`).)*

### 2.8 Validación (§11), Seguridad (§12), Rendimiento (§13), Fases 0–5 (§14), 11 Criterios MVP (§15) y 15 Lineamientos (§17)

- **Validación (§11):** CSV lluvia (§11.1) y calidad DEM (§11.2) implementados (`events.py`, `quality.py`). En validación hidrológica (§11.3) faltan tests dedicados de barrera/terraplén + alcantarilla, flujo entrante externo, comparación contra observaciones reales y eliminación de llamadas HTTP reales en `test_phase4_5_advanced.py:171` y `test_api_phase0.py:249`.
- **Seguridad (§12):** Validación de archivos, ausencia de shell con input de usuario, secretos fuera de código y `PROCESSING_VERSION` presentes; faltan `.env*` en `.gitignore` (cubierto en M1), atribución de licencias en exportaciones, `logs_uri` y aclaración de alcance monousuario local (sin auth multi-tenant).
- **Rendimiento (§13):** Ejecución síncrona con `@lru_cache(8)`, sin benchmark documentado de 3 escenarios (lote pequeño, varios lotes, cuenca amplia) ni fallback 2D sin WebGL.
- **Fases 0–5 (§14):**
  - *Fase 0:* Completa en código; docs desactualizados.
  - *Fase 1:* Backend casi completo (falta brechar barreras y `aspect`/curvatura en malla); faltan toggles UI.
  - *Fase 2:* Implementada; faltan fuentes satelitales/SMN de lluvia y metadatos completos en UI.
  - *Fase 3:* Implementada; `handleQuickSimulateRain` no refresca `timeline`; Diorama ignora `particle_paths`.
  - *Fase 4:* Onda difusiva 2D implementada; falta advertencia de lluvia uniforme 2D, CRUD de observaciones en UI, métricas de calibración y pruebas de sensibilidad.
  - *Fase 5:* `zonation.py` implementada; falta vínculo con historia productiva y fenología de cultivo (limitación a documentar).
- **11 Criterios Globales MVP (§15):**
  - Cumplidos en modo GIS (salvo detalles menores): #1, #2, #5, #6, #7, #8, #10 (afectado por bug de `processed_at` en `services/hydrology.py:780-783`) y #11.
  - Incumplimiento parcial o roto: **#3** (sin fallback 2D sin WebGL), **#4** (`selectedPoint` roto en GIS; sin perfil en Agrónomo) y **#9** (Diorama mezcla `mfd_area_ha` y `water_depth_m` y oculta advertencias §6.4).
- **15 Lineamientos de Desarrollo (§17):** Destacan las brechas en §17.4 (sin datos reales inventados), §17.5 (descomponer `App.tsx` de 2.196 líneas en componentes pequeños), §17.6 (contratos TS/Pydantic sincronizados), §17.9 (tests offline de fórmulas/flujo), §17.11–§17.13 (metadatos visibles y degradación explícita sin sustitución silenciosa), §17.14 (fallback 2D) y §17.15 (documentación local actualizada).

### 2.9 Suite de las 8 Herramientas Agronómicas Complementarias

| # | Herramienta Agronómica | Módulo y Funciones Backend | Estado Actual y Brechas (R4 / Científicas / UI) |
|---|---|---|---|
| **1** | **Erosión hídrica (USLE/RUSLE + cárcavas)** | `geoprocessing/agronomy/erosion_usle.py`: `compute_ls_factor_grid`, `estimate_storm_erosivity_r`, `compute_usle_erosion_and_gullies` | **Brechas:** línea `73` inventa `i30 = min(75.0, 0.65 * p)` violando SDD §4.4; `delivery_ratio` (`117`) sin cita bibliográfica; sin test de valor de referencia; UI omite advertencia de carácter preliminar (SDD §2.2). |
| **2** | **Balance hídrico mensual (NASA POWER + Agua útil)** | `geoprocessing/satellite/nasa_power_imerg.py`: `fetch_nasa_power_daily_series`, `compute_monthly_water_balance` | **Brechas R4:** línea `45` fija `end_dt = date(2025, 12, 31)`; líneas `97-136` fabrican clima aleatorio (`rng.normal`/`rng.gamma`) en fallos; línea `176` fija `Ra = 15.0` y `180` `kc = 0.85/0.55`; UI recorta a 6 u 8 meses en vez de 12; `types/api.ts` omite `soil_group`, `surface_runoff_mm`, `crop_demand_etc_mm`. |
| **3** | **Riesgo de anegamiento por fecha real** | `geoprocessing/satellite/nasa_power_imerg.py`: `evaluate_real_date_waterlogging_risk` | **Brechas:** hereda datos climáticos sintéticos y techo `2025-12-31`; `types/api.ts` omite `cn_effective` y `runoff_volume_m3`. |
| **4** | **Curvas de nivel y Terrazas a nivel** | `geoprocessing/agronomy/erosion_usle.py`: `design_and_simulate_contour_terraces` | **Brechas:** `terraces_geojson` devuelto por el backend no se renderiza ni en `TerrainDiorama3D` ni en `TerrainScene3D`; faltan tests de referencia para VI/HI y retención. |
| **5** | **Calculadora de Siembra y Fertilizante (INTA)** | `geoprocessing/agronomy/seeding_and_rotation.py`: `calculate_seeding_and_fertilizer` | **Brechas:** Modo Agrónomo no permite editar `target_yield_t_ha`; faltan tests de referencia/límite; aclarar unidades en docstring (ej. `240_0000` = 2.400.000 pl/ha en trigo/vicia). |
| **6** | **Comparador de Rotaciones Trienales (3 años)** | `geoprocessing/agronomy/seeding_and_rotation.py`: `compare_triennial_rotations` | **Brechas:** `AgronomicToolkitIn` en `types/api.ts:514-521` omite `sequence_a_name`, `sequence_a_crops`, `sequence_b_name`, `sequence_b_crops`; UI carece de selector de rotaciones y tabla anual (`years`). |
| **7** | **Monitor de Vigor Vegetativo (NDVI Sentinel-2 STAC)** | `geoprocessing/satellite/nasa_power_imerg.py`: `compute_ndvi_vigor_monitor` | **Brechas R4:** líneas `454-475` fabrican `synthetic-ecohydro-proxy` desde TWI; líneas `418-443` omiten offset ESA PB04.00 (`-1000` / `BOA_ADD_OFFSET`) y máscara `SCL`; Diorama no re-texturiza al cambiar `ndvi`; UI oculta `is_satellite_observed`, `scene_id` y `cloud_cover_pct`. |
| **8** | **Riesgo de Heladas y Fechas Seguras de Siembra** | `geoprocessing/satellite/nasa_power_imerg.py`: `evaluate_frost_risk_and_sowing_dates` | **Brechas:** hereda clima sintético y techo `2025-12-31`; líneas `334-351` devuelven días/DOY fijos (`12.0`/`28.0`, `265/280/115`) si faltan datos; sin test offline con percentiles conocidos. |

---

## 3. Cadena de Dependencias entre Especialistas

```text
Responsable / Coordinador (planifica y aprueba contratos; solo lectura en producción)
   │
   ▼
[M2] experto-datos-nasa (NASA-01..05)
   │  Entrega: datos recortados, unidades SI, metadatos completos,
   │           degradación explícita (status="unavailable"/None, CERO datos inventados),
   │           Ra FAO-56/degradación en nasa_power_imerg.py, extensiones Capa 1
   │           (fields.py, data/README.md, tests de cliente revisados por hidrologo)
   │           y docs/data-sources.md.
   ▼
[M2] hidrologo (HID-01..04)
   │  Entrega: núcleo científico puro en geoprocessing/agronomy/ (Ra FAO-56, ET0, Kc/AWC,
   │           percentiles de heladas; sin editar geoprocessing/satellite/*), USLE sin i30
   │           inventado, citas bibliográficas, tests 3-en-1 offline y docs/model-limitations.md.
   ▼
[M3] backend (API-01..06)  ◄──►  [M3] frontend-3d Fase A (FE-A1..A4: contratos y hooks)
   │  Entrega: schemas.py completos (response_model en todas las rutas),
   │           bugfixes servicios/caché/advertencias, /layers, TestClient offline
   │           y docs/architecture.md; FE sincroniza types/api.ts, api.ts y hooks/.
   ▼
[M4] frontend-3d Fase B (FE-B1..B7: Visores 3D, 17 capas, UI Producción, 360px, <500 kB)
   │  Entrega: TerrainDiorama3D y TerrainScene3D estabilizados, fallback 2D sin WebGL,
   │           inspección puntual, CRUD observaciones, cero hardcodes demo, tests UI.
   ▼
[M5] coordinador + Validación E2E / Tier 5 (REL-01..03)
      Entrega: 100% tests offline + E2E + build verde (delegando correcciones a dueños),
               Earth2Worlds intacto, tabla de ejecución final actualizada, merge a main y push.
```

---

## 4. Plan de Tareas Detallado por Capa, Hito y Prioridad

### Bloque 1 — `experto-datos-nasa` (Milestone 2: Capa de Datos Satelitales, Clima y Límites)

*(Nota de alcance: conforme a `PROJECT.md` Capa 1, `NASA-04` (`geoprocessing/fields.py`), `NASA-05` (`data/README.md`) y los tests offline de clientes/ingesta en `geoprocessing/tests/` (`NASA-01..04`) constituyen extensiones autorizadas sobre `.claude/agents/experto-datos-nasa.md:16-22`, con revisión de `hidrologo` sobre los tests en `geoprocessing/tests/`.)*

| ID | Tarea y Archivos Afectados | Dep. | Criterios de Aceptación (AC) Verificables | Definición de Terminado (DoD) |
|---|---|---|---|---|
| **NASA-01** | **Eliminar clima sintético, dinamizar fechas y reemplazar `Ra=15.0` / fallbacks duros en NASA POWER**<br>`geoprocessing/satellite/nasa_power_imerg.py:33-373`, `geoprocessing/tests/fixtures/`, `geoprocessing/tests/` *(tests de cliente con revisión de `hidrologo`)* | M1 | `end_dt = date.today() - timedelta(days=3)`; eliminar generación RNG (`97-136`); ante error HTTP/red o serie vacía devolver `rows=[]`, `status="unavailable"`, `is_observed=False`, `warnings` explícitos y caché local con TTL por coordenada/rango; reemplazar `Ra=15.0` (`176`) por radiación extraterrestre astronómica FAO-56 $R_a(\text{lat}, \text{doy})$ y eliminar valores duros de heladas (`12.0`/`28.0` días, DOY `265/280/115` en `334-351`) devolviendo `status="unavailable"` ante `daily_rows` vacía o insuficiente (manteniendo adquisición y firmas compatibles en `nasa_power_imerg.py` o delegando al cálculo puro que extraerá `HID-01`). | Fixtures JSON reales en `geoprocessing/tests/fixtures/`; tests offline en `geoprocessing/tests/` (revisados por `hidrologo`) para respuesta válida, vacía (`daily_rows=[]`), HTTP 500/timeout y fill values `-999`. |
| **NASA-02** | **Sentinel-2 L2A STAC: offset PB04.00, máscara SCL y cero NDVI sintético**<br>`geoprocessing/satellite/nasa_power_imerg.py:376-523`, `geoprocessing/tests/` *(tests de cliente con revisión de `hidrologo`)* | M1 | Leer asset `scl` (clases válidas 4, 5, 6, 7; rechazar si `qa_valid_pct < umbral`), aplicar offset ESA PB04.00 (`-1000` / `BOA_ADD_OFFSET` sobre DN válido) antes de `(B08-B04)/(B08+B04)` y eliminar `synthetic-ecohydro-proxy` (`454-475`), devolviendo `grid=None`, `status="unavailable"`, `is_satellite_observed=False` ante fallo o 100% nubes. | Test offline con STAC/COG mockeado y raster mínimo verificando NDVI exacto con PB04.00, enmascarado SCL y degradación controlada sin proxy sintético. |
| **NASA-03** | **Cliente HTTP resiliente con timeouts y backoff acotado**<br>`geoprocessing/net.py:33-99`, `geoprocessing/tests/` *(tests de cliente con revisión de `hidrologo`)* | M1 | Configurar `httpx.Timeout(connect=10.0, read=25.0, ...)`, reintentos acotados con backoff exponencial en 429/502/503/timeout para GET idempotentes, preservando validación TLS `truststore`. | Tests con `httpx.MockTransport` validando reintento exitoso en 503 y fallo controlado tras agotar reintentos. |
| **NASA-04** | **Endurecer importación de límites (`.zip` SHP con `.prj`/`.dbf`/huecos y `.gpkg`)**<br>`geoprocessing/fields.py:271-366`, `geoprocessing/tests/` *(extensión autorizada `PROJECT.md` Capa 1; tests con revisión de `hidrologo`)* | M1 | Leer `.prj` para reproyectar a WGS84, leer atributos de nombre/superficie desde `.dbf`, distinguir anillos exteriores vs. huecos por orientación/contención y soportar GeoPackage `.gpkg` (o documentar límite explícito si faltan drivers). | Tests unitarios offline para `.kmz`, `.zip` (SHP UTM + `.dbf` + polígono con hueco) y `.gpkg`. |
| **NASA-05** | **Actualizar documentación de fuentes y muestras**<br>`docs/data-sources.md`, `data/README.md` *(extensión autorizada `PROJECT.md` Capa 1 para `data/README.md`)* | NASA-01..04 | Documentar catálogo completo (versión, resolución, latencia, licencia, limitaciones, cita) para Copernicus GLO-30, IGN MDE-Ar 5m/30m, NASA POWER, Sentinel-2 L2A STAC, alcance pendiente de GPM IMERG/SMN/CHIRPS/ERA5-Land, y fichas de `san_luis_piedemonte_492.geojson` y `evento_tormenta_pluvio.csv`. | `docs/data-sources.md` y `data/README.md` revisados sin datos de prueba sin documentar. |

### Bloque 2 — `hidrologo` (Milestone 2: Núcleo Científico, Citas y Tests 3-en-1 Offline)

| ID | Tarea y Archivos Afectados | Dep. | Criterios de Aceptación (AC) Verificables | Definición de Terminado (DoD) |
|---|---|---|---|---|
| **HID-01** | **Validación y extracción científica pura de $R_a(\text{lat}, \text{doy})$ FAO-56, balance hídrico y heladas**<br>`geoprocessing/agronomy/` (nuevo `geoprocessing/agronomy/climate_balance.py`), `geoprocessing/tests/`, `docs/model-limitations.md` *(sin editar la capa satelital)* | NASA-01 | Desacoplar/validar en `geoprocessing/agronomy/` las funciones puras científicas de radiación extraterrestre astronómica $R_a(\text{lat}, \text{doy})$ según FAO-56 (Allen et al., 1998, Ec. 21–28), $ET_0$ Hargreaves-Samani, balance hídrico $K_c$/AWC (con citas bibliográficas) y percentiles de heladas (`np.median`/`np.percentile`) devolviendo `status="unavailable"` ante `daily_rows=[]` o serie insuficiente, manteniendo intacta la frontera con `experto-datos-nasa` en `nasa_power_imerg.py`. | Módulo puro en `geoprocessing/agronomy/`, test 3 partes en `geoprocessing/tests/` (valor de referencia FAO-56 en San Luis enero/julio, caso límite `daily_rows=[]`, propiedad física $ET_0 \ge 0$ y estacionalidad) y limitaciones documentadas en `docs/model-limitations.md`. |
| **HID-02** | **Auditoría USLE: eliminar `i30` inventado y citar `delivery_ratio`**<br>`geoprocessing/agronomy/erosion_usle.py:68-166` | M1 | Eliminar `i30 = min(75.0, 0.65 * p)` (`line 73`): exigir `max_intensity_mm_h` real o etiquetar explícitamente supuesto conservador/índice relativo documentado (SDD §4.4); citar referencia bibliográfica de `delivery_ratio` (`line 117`) o sustituir por formulación citada y añadir nota de índice preliminar. | Test 3 partes (valor calculado a mano, caso límite `P=0` / pendiente `0`, monotonía con pendiente y factor C). |
| **HID-03** | **Citas bibliográficas, brechado/aspect/curvatura y batería offline 3-en-1**<br>`geoprocessing/{dem,hydrology,rainfall,agronomy}/*.py`, `geoprocessing/tests/` | NASA-01..04, HID-01..02 | Verificar citas en docstrings (Horn 1981, Wang & Liu / Barnes 2014, Quinn 1991, Beven & Kirkby 1979, Moore 1991, NRCS TR-55, Chow 1959, INTA/IPNI); evaluar exposición de `aspect_deg`/curvatura en grillas si resolución permite y brechado de barreras; añadir tests SDD §11.3 faltantes (flujo entrante externo, `apply_burn_in`, estructuras 2D, `seeding_and_rotation.py`, `zonation.py`). | `python -m pytest geoprocessing/tests -q` pasa 100% offline en `< 5 s`. |
| **HID-04** | **Actualizar `docs/model-limitations.md` para Fases 0–5 y 8 herramientas**<br>`docs/model-limitations.md` | HID-01..03 | Documentar rangos de validez, supuestos y limitaciones explícitas de D8/MFD, NRCS-CN, hietograma Fase 3, onda difusiva 2D Fase 4 (CFL, Manning, borde libre, tope de celdas), zonificación Fase 5, USLE, terrazas, balance hídrico FAO-56, NDVI y heladas. | Documento completo y consistente con los docstrings de `geoprocessing/`. |

### Bloque 3 — `backend` (Milestone 3: Servicios, Contratos Pydantic, Bugfixes y Tests API Offline)

| ID | Tarea y Archivos Afectados | Dep. | Criterios de Aceptación (AC) Verificables | Definición de Terminado (DoD) |
|---|---|---|---|---|
| **API-01** | **Corregir mutación de `hydrology.json` (`processed_at`) en Toolkit**<br>`services/api/app/services/hydrology.py:780-783` | HID-03 | `run_agronomic_toolkit()` no debe mutar ni reescribir `hydrology.json`; usar invalidación de caché limpia por clave compuesta `(field_id, hydro_processed_at, toolkit_processed_at)`. | Test que verifica que `hydrology.json["processed_at"]` permanece inalterado antes y después de `POST /toolkit/run`. |
| **API-02** | **Sincronizar `terrain_point` post-simulación 2D**<br>`services/api/app/services/terrain.py:139-140, 158-172` | M1 | `terrain_point()` debe leer `agronomic_zone_id` y `agronomic_zone_label` desde los grids de la corrida activa cuando exista simulación 2D (igual que `terrain_mesh()`), y reportar distancia a ruta de drenaje (CU-05) si está disponible. | Test que confirma coincidencia exacta entre `terrain_point` y `terrain_mesh` en la misma coordenada tras `simulate-2d`. |
| **API-03** | **Advertencia en lluvia manual 2D y degradación controlada de clima/NDVI**<br>`services/api/app/services/hydrology.py:584-591, 740-802` | NASA-01..02, HID-01..02 | Cuando `rain_ev` no tenga `intervals`, añadir advertencia explícita en `target["warnings"]` indicando el reparto uniforme en 4 pasos de 15 min (SDD §4.4); propagar estados `unavailable` y `grid=None` sin `NaN` en JSON ni excepciones 500. | Tests `TestClient` verificando advertencia explícita en 2D manual y respuestas HTTP 200 válidas en modo degradado ante fallo de NASA/STAC. |
| **API-04** | **Completar `schemas.py`, `response_model` en rutas y endpoint `/layers`**<br>`services/api/app/schemas.py`, `services/api/app/api/routes/{hydrology,terrain}.py`, `services/api/app/main.py` | API-01..03 | Definir `HealthOut`, `CatalogOut`, `LayersCatalogOut`, `Hydrodynamic2DSummaryOut`, `AgronomicZonationOut`, `AgronomicToolkitOut` en `schemas.py`; reemplazar `dict \| None` por `AgronomicZonationOut \| None` en `HydrologyOut.agronomic_zonation` (`schemas.py:279`) y por `Hydrodynamic2DSummaryOut \| None` / `AgronomicZonationOut \| None` en `RunoffRunOut.{hydrodynamic_2d_summary, agronomic_zonation}` (`schemas.py:373-374`); asignar `response_model` a `/health`, `/catalog`, `/toolkit`, `/toolkit/run` y `/export/geojson`; implementar `GET /api/v1/fields/{field_id}/layers` (SDD §10/§17.11) y `GET .../runoff-runs/{run_id}` con atribución de licencias (SDD §12). | OpenAPI schema generado sin dicts sin tipar en rutas nuevas/modificadas; contrato revisado con `frontend-3d`. |
| **API-05** | **Suite `TestClient` offline integral para Fases 0–5 y códigos de error**<br>`services/api/tests/` | API-04 | Mockear llamadas externas (`nasa_power_imerg`, DEM remoto) mediante transporte/monkeypatch offline; cubrir flujo completo Fases 0–5 + 8 herramientas, errores `400/404/413/422` en español y escenarios degradados. | `python -m pytest -q` desde la raíz pasa completo (código 0) sin acceso a internet. |
| **API-06** | **Actualizar `docs/architecture.md` para Fases 0–5 y suite agronómica**<br>`docs/architecture.md` | API-04..05 | Documentar arquitectura real (`FileStore`, `.npz`, FastAPI `/api/v1`, 8 herramientas, separación `geoprocessing/` → `services/api/` → `apps/web/` y brechas asumidas respecto a PostGIS/Celery de SDD §8–§10). | `docs/architecture.md` actualizado y revisado por `coordinador`. |

### Bloque 4 — `frontend-3d` Fase A (Milestone 3: Integración API, Contratos y Estado Compartido)

| ID | Tarea y Archivos Afectados | Dep. | Criterios de Aceptación (AC) Verificables | Definición de Terminado (DoD) |
|---|---|---|---|---|
| **FE-A1** | **Sincronización estricta de contratos (`types/api.ts` y `services/api.ts`)**<br>`apps/web/src/types/api.ts`, `apps/web/src/services/api.ts` | API-04 | Eliminar `type str = string` (`types/api.ts:44`); agregar `ProfileIn`, `Hydrodynamic2DIn`, `CatalogOut`, `LayersCatalogOut`; completar parámetros omitidos (`burn_lines`, `burn_depth_m`, `source_product`, `spatial_resolution`, `quality_flag`, `uncertainty_note`, `observed_at`, `sequence_a_*`, `sequence_b_*`, `step_m`, `sourceUrl`, `license`, `declaredTotalMm`); espejar 100% de `AgronomicToolkitOut` (incluyendo estados `unavailable`/nullable); agregar `getHealth()`, `getField()`, `getTerrainContours()`, `getHydrologyCatalog()`, `getFieldLayers()`. | `npm run typecheck` termina con código 0; paridad 1:1 verificada contra `schemas.py`. |
| **FE-A2** | **Extraer hooks compartidos y unificar estado desde `App.tsx`**<br>`apps/web/src/App.tsx:69-695` → `apps/web/src/hooks/{useFieldWorkspace,useHydrologyState,useAgronomicToolkit,useObservations}.ts` | FE-A1 | Extraer ~35 `useState` y flujos asíncronos fuera de `App.tsx`; unificar `quickSoilGroup`/`quickCover`/`quickRainMm` con `RainfallRunoffPanel` y `AgronomicToolkitPanel` en una única fuente de verdad entre modo GIS y Modo Agrónomo. | `App.tsx` reducido a composición/layout; cambios de suelo/cobertura/lluvia sincronizados entre ambos modos; `typecheck` en verde. |
| **FE-A3** | **Consumir catálogo dinámico del backend (`/hydrology/catalog`)**<br>`apps/web/src/App.tsx:925-946, 1590-1600`, `RainfallRunoffPanel.tsx:28-61`, `AgronomicToolkitPanel.tsx:64-72` | FE-A1, FE-A2 | Obtener `GET /api/v1/fields/{field_id}/hydrology/catalog` al cargar el workspace y poblar coberturas, grupos de suelo, AMC, fuentes de lluvia y cultivos INTA desde el backend. | Cero listas duplicadas de cultivos/coberturas hardcodeadas en componentes JSX. |
| **FE-A4** | **Corregir refresco de `timeline` y propagación de errores/procedencia**<br>`apps/web/src/App.tsx:286-360, 442-695` | FE-A2 | `handleQuickSimulateRain` debe llamar a `getRunoffTimeline` y actualizar `timeline`/`timelineStep`; reemplazar `.catch(() => null)` silenciosos por advertencias visibles; propagar `warnings`, `limitations`, `source` e `is_satellite_observed` al estado de UI. | Lluvia rápida actualiza de inmediato el timeline; fallos de NASA/Sentinel-2 se reflejan explícitamente en estado de UI. |

### Bloque 5 — `frontend-3d` Fase B (Milestone 4: Visores 3D, 17 Capas, UI Producción y Rendimiento)

| ID | Tarea y Archivos Afectados | Dep. | Criterios de Aceptación (AC) Verificables | Definición de Terminado (DoD) |
|---|---|---|---|---|
| **FE-B1** | **Estabilizar `TerrainDiorama3D`: cámara persistente, curvas, terrazas y textura honesta**<br>`apps/web/src/components/TerrainDiorama3D.tsx`, `App.tsx:1180-1190` | FE-A4 | Separar inicialización de `WebGLRenderer`/`Scene`/`OrbitControls` (`[]`) de la actualización de malla/capas; conservar cámara al cambiar overlays/exageración/play; respetar `exaggeration=1` real; renderizar `showContours`, `terraces_geojson` y observaciones; re-generar textura al actualizar `ndvi`; liberar (`dispose`) geometrías/materiales de borde y drenaje; mostrar aviso explícito si falla Esri (sin textura falsa silenciosa); eliminar mezcla de `mfd_area_ha` con `water_depth_m` en `waterlogging`. | Orbitar o alternar capas nunca reinicia la cámara; `showContours` dibuja curvas; fallo de mapa base muestra aviso visible; cero fugas WebGL. |
| **FE-B2** | **Corregir `TerrainScene3D`: draping 3D, partículas in-place, capas y fallback 2D**<br>`apps/web/src/components/TerrainScene3D.tsx` | FE-A4 | Quitar `transitFraction` del array de dependencias de `rebuild()` (`1016`) actualizando `BufferAttribute` in-place; elevar/drapear sobre la cota 3D `contours`, `drainage-network`, `terraces_geojson`, `hydro-points`, `observations`, `profile-line` y `selected-point` (no `z=0`); añadir capa de dirección (`d8_code`), lluvia acumulada y `aspect` (si backend entrega); agregar botón Restablecer cámara / Centrar lote; implementar detección WebGL + visor 2D Canvas/SVG de respaldo (SDD §7.5, §17.14). | Reproducción temporal fluida sin realocar malla; vectores alineados al relieve 3D; sin WebGL se activa visor 2D interactivo. |
| **FE-B3** | **Exponer las 17 capas SDD §4.3, default `1×` y soporte multi-lote**<br>`apps/web/src/App.tsx`, nuevo `apps/web/src/components/TerrainLayerControls.tsx` | FE-B1, FE-B2 | Establecer `exaggeration` inicial en `1` (SDD §4.2) con banner visible también en Agrónomo cuando sea `!= 1`; exponer toggles para `basemap`, `mesh3d`, `wireframe`, `boundary`, `contours`, `drainageNetwork`, `depressionsAndOutlets`, `observations`, `terraces` y todas las variables de superficie; permitir seleccionar múltiples lotes en vista GIS (SDD §4.2). | Todas las capas implementadas de SDD §4.3 son activables; carga inicial en `1×`; `TerrainLayerControls` modularizado según SDD §17.5. |
| **FE-B4** | **Corregir inspección puntual GIS, perfil, CRUD de observaciones y parámetros avanzados**<br>`apps/web/src/App.tsx`, `HydrologyPanel.tsx`, `RainfallRunoffPanel.tsx`, `AgronomicToolkitPanel.tsx`, nuevo `TerrainInspector.tsx` | FE-A2, FE-A3, FE-B2 | Renderizar `TerrainInspector` (`selectedPoint`) en GIS y Agrónomo con todos los campos SDD §7.4; conectar inputs `obsDraftType`/`obsDraftNotes`/`obsDraftVal`, listado de observaciones y `deleteFieldObservation`; agregar `.gpkg` en `accept`; exponer `burn_lines`/`burn_depth_m`, `start_at`/`end_at`/`declared_total_mm`/`custom_cn_ii` + metadatos §5.3, `manning_n`/`ponding_threshold_m`/`recession_minutes`, `target_yield_t_ha`, secuencias A/B y los 12 meses de balance hídrico. | Clic en mapa GIS en modo `inspect` abre `TerrainInspector`; crear y eliminar observaciones persiste en backend; todos los parámetros son configurables. |
| **FE-B5** | **Eliminar hardcodes demo y visibilizar procedencia, advertencias y estados degradados**<br>`apps/web/src/App.tsx`, `AgronomicToolkitPanel.tsx` | FE-A3, FE-A4, FE-B4 | Eliminar `'📍 Provincia de San Luis, Argentina'` (`App.tsx:1107`, derivar de `field.properties` o `centroid`); eliminar fallbacks falsos `'3.9'`, `'8000'`, `3.5`, `1.3`, `12.0` (`703, 1050-1080`, usar valor real o `'—'`); mostrar `toolkit.warnings`, `is_satellite_observed`, fuente completa + fecha/resolución, `limitations`/`assumptions_and_notes` y advertencia preliminar USLE; mostrar 12 meses en balance hídrico y `cursorCoords` en barra inferior. | Cero strings o KPIs inventados; estados `unavailable` de NASA/Sentinel-2 visibles y claros en español rioplatense. |
| **FE-B6** | **CSS Mobile-First `360 px`, accesibilidad y Code-Splitting Vite (`< 500 kB`)**<br>`apps/web/src/styles.css`, `apps/web/vite.config.ts`, `apps/web/src/App.tsx` | FE-B1..B5 | Reemplazar layout rígido `100vh` por `@media` responsive (`360 px` móvil con paneles colapsables y cero scroll horizontal); asegurar áreas táctiles `>= 44 px`, contraste AA, `:focus-visible` y `@media (prefers-reduced-motion: reduce)`; cargar con `React.lazy` + `Suspense` los visores 3D y `PolygonMapDrawer`, configurando `manualChunks` (`three`, `maplibre-gl`) en `vite.config.ts`. | `npm run build` genera todos los chunks JS `< 500 kB`; cero desbordamiento horizontal en `360×800`. |
| **FE-B7** | **Tests automatizados frontend y verificación end-to-end local en app real**<br>`apps/web/package.json`, `apps/web/src/**/*.test.ts(x)` | FE-B6 | Incorporar suite de tests (Vitest) para contratos, hooks, renderizado de estados `unavailable`/degradados, `TerrainInspector` y CRUD de observaciones; verificar `npm run dev` contra FastAPI local con `data/sample/` en escritorio (`1440 px`) y móvil (`360 px`). | `npm run typecheck`, `npm run build`, tests frontend y recorrido real en navegador pasan sin errores en consola. |

### Bloque 6 — `coordinador` y Cierre de Entrega (Milestone 5: E2E, Tier 5 Adversarial y Git Delivery a `main`)

*(Nota de rol: conforme a `.claude/agents/coordinador.md:3,18` y `docs/agentes.md:9`, `coordinador` es **estrictamente solo lectura** sobre el código de producción; ejecuta verificación/E2E y **delega** cualquier corrección requerida al especialista dueño: `experto-datos-nasa`, `hidrologo`, `backend`, `frontend-3d` o `test_writer`.)*

| ID | Tarea y Responsables | Dep. | Criterios de Aceptación (AC) Verificables | Definición de Terminado (DoD) |
|---|---|---|---|---|
| **REL-01** | **Ejecución completa E2E (Tiers 1–4) y endurecimiento adversarial (Tier 5)**<br>`tests/e2e/` *(solo ejecución/verificación; delegación a especialistas ante defectos)* | API-05, FE-B7, Track E2E | Ejecutar suite completa offline (`python -m pytest -q` desde la raíz incluyendo `tests/e2e/`), validar `npm run typecheck` y `npm run build` en `apps/web/`, y **delegar** al especialista dueño (`experto-datos-nasa`, `hidrologo`, `backend`, `frontend-3d` o `test_writer`) la corrección de cualquier defecto detectado en Tier 5 sin atajos ni mocks falsos. | 100% de tests unitarios, API, frontend y E2E en verde (código de salida 0) sin acceso a internet. |
| **REL-02** | **Auditoría final de documentación, R4 y aislamiento de `Earth2Worlds`**<br>`docs/plan-tareas-sdd.md`, `docs/*.md` *(revisión de lectura; actualización delegada al especialista dueño si aplica)*, `C:\Users\haf01\.gemini\antigravity\scratch\Earth2Worlds` *(auditoría solo lectura)* | REL-01, NASA-05, HID-04, API-06 | Actualizar Tabla Viva en `docs/plan-tareas-sdd.md` con estado real ejecutado; confirmar que `docs/{agentes,architecture,data-sources,model-limitations}.md` reflejan el código final; verificar `git status` limpio en `Earth2Worlds` (sin commits nuevos ni archivos modificados) y cero datos inventados. | Reporte de verificación verificable con hashes, salidas exactas y evidencia de no modificación en `Earth2Worlds`. |
| **REL-03** | **Integración limpia en Git y entrega en `origin/main`**<br>Ramas `feature/visor-3d-hidrologia` → `main` | REL-01, REL-02 | Revisar diff completo (`feature/visor-3d-hidrologia` vs `main`), realizar merge limpio (sin `--force`, sin tests fallando) hacia `main`, verificar árbol limpio y ejecutar `git push origin main` (y actualizar rama de trabajo si aplica). | `git status --short` vacío, `main` sincronizado con `origin/main` en GitHub y reporte final emitido según formato de `coordinador.md`. |

---

## 5. Matriz Viva de Registro de Ejecución

| ID | Hito | Especialista | Descripción Resumida | Estado | Evidencia / Commit |
|---|---|---|---|---|---|
| **M1-01** | M1 | `coordinador` | Checkout limpio en rama `feature/visor-3d-hidrologia` (`6165a40`) y verificación de `.gitignore` | **Completada** | Rama activa + `.gitignore` validado |
| **M1-02** | M1 | `coordinador` | Instalación verbatim (SHA256 idéntico) de 5 specs en `.claude/agents/*.md` y `docs/agentes.md` | **Completada** | Hashes SHA256 verificados 1:1 |
| **M1-03** | M1 | `coordinador` | Auditoría SDD vs. código y creación de `docs/plan-tareas-sdd.md` | **Completada** | Documento presente en `docs/plan-tareas-sdd.md` |
| **NASA-01** | M2 | `experto-datos-nasa` | Eliminar clima sintético, dinamizar `end_dt`, caché y $R_a$/degradación en `nasa_power_imerg.py` | **Completada** | Commit `87a93e2` (cero RNG sintético, `date.today()`, degradación controlada) |
| **NASA-02** | M2 | `experto-datos-nasa` | Sentinel-2 PB04.00 + máscara SCL + eliminar proxy NDVI sintético | **Completada** | Commit `87a93e2` (SCL `[3,8,9,10,11]`, `Resampling.nearest`, cero proxy sintético) |
| **NASA-03** | M2 | `experto-datos-nasa` | Timeouts y backoff acotado en `geoprocessing/net.py` | **Completada** | Timeouts 10s/25s y backoff exponencial verificados en suite offline |
| **NASA-04** | M2 | `experto-datos-nasa` | Endurecer `.zip` SHP (`.prj`/`.dbf`/huecos) y `.gpkg` en `fields.py` | **Completada** | Commit `87a93e2` (resolución de `dbf_name_file` y `rec_idx`) |
| **NASA-05** | M2 | `experto-datos-nasa` | Actualizar `docs/data-sources.md` y `data/README.md` | **Completada** | Documentación exhaustiva en `docs/data-sources.md` y `data/README.md` |
| **HID-01** | M2 | `hidrologo` | Extracción y validación pura ($R_a$ FAO-56, $ET_0$, $K_c$/AWC, heladas) en `geoprocessing/agronomy/` + tests + `docs/model-limitations.md` | **Completada** | Módulo de balance hídrico, test 3 partes y limitaciones en `docs/model-limitations.md` |
| **HID-02** | M2 | `hidrologo` | Eliminar `i30` inventado y citar `delivery_ratio` en `erosion_usle.py` | **Completada** | Supuesto conservador pampeano documentado y cita de Williams & Berndt (1977) |
| **HID-03** | M2 | `hidrologo` | Auditoría de citas y tests 3-en-1 offline en `geoprocessing/tests/` | **Completada** | 156/156 tests pasando en verde (100%) |
| **HID-04** | M2 | `hidrologo` | Actualizar `docs/model-limitations.md` (Fases 0–5 y 8 herramientas) | **Completada** | Cobertura completa de Fases 0 a 5 y 8 herramientas en `docs/model-limitations.md` |
| **API-01** | M3 | `backend` | Corregir corrupción de `processed_at` en `hydrology.json` desde toolkit | **Completada** | Inalterabilidad estricta de `hydrology.json` verificada en `test_e2e_t1_f8_05` |
| **API-02** | M3 | `backend` | Sincronizar `agronomic_zone_id` en `terrain_point` post-2D | **Completada** | Sincronización de zonificación y atributos de punto en `services/terrain.py` |
| **API-03** | M3 | `backend` | Advertencia de reparto uniforme 2D y manejo de estados `unavailable` | **Completada** | Advertencias explícitas en `warnings` y degradación elegante sin crash |
| **API-04** | M3 | `backend` | Completar `schemas.py`, `response_model` y endpoint `/layers` | **Completada** | Commit `87a93e2` (Pydantic v2 + validaciones CN + `CatalogOut`/`HealthOut`) |
| **API-05** | M3 | `backend` | Suite `TestClient` offline Fases 0–5, toolkit y códigos HTTP | **Completada** | Tests E2E completos en `tests/e2e/test_tier1_features.py` |
| **API-06** | M3 | `backend` | Actualizar `docs/architecture.md` para Fases 0–5 | **Completada** | Diagrama C4/Mermaid y detalle de componentes en `docs/architecture.md` |
| **FE-A1** | M3 | `frontend-3d` | Sincronizar 100% `types/api.ts` y `services/api.ts` con `schemas.py` | **Completada** | Commit `87a93e2` (paridad 1:1 verificada con AST / test `f10_04`) |
| **FE-A2** | M3 | `frontend-3d` | Extraer hooks compartidos desde `App.tsx` y unificar estado | **Completada** | Estado reactivo unificado entre Modo Agrónomo y GIS |
| **FE-A3** | M3 | `frontend-3d` | Consumir catálogo dinámico desde `GET .../hydrology/catalog` | **Completada** | Servicios de catálogo y health check tipados en `services/api.ts` |
| **FE-A4** | M3 | `frontend-3d` | Refresco de `timeline` en lluvia rápida y propagación de advertencias/procedencia | **Completada** | Propagación de metadatos de procedencia y avisos de calidad |
| **FE-B1** | M4 | `frontend-3d` | Estabilizar `TerrainDiorama3D` (cámara, curvas, terrazas, textura honesta, `dispose`) | **Completada** | Commit `7054c9e` y renderizado de diorama isométrico con Esri World Imagery |
| **FE-B2** | M4 | `frontend-3d` | Estabilizar `TerrainScene3D` (draping 3D, partículas in-place, fallback 2D sin WebGL) | **Completada** | Capas 2D/3D sincronizadas, partículas animadas fluidas en MapLibre/Three.js |
| **FE-B3** | M4 | `frontend-3d` | Exponer las 17 capas SDD §4.3, default `1×` y soporte multi-lote | **Completada** | Toggles interactivos de capas y ajuste de escala vertical |
| **FE-B4** | M4 | `frontend-3d` | Inspección puntual GIS (`TerrainInspector`), CRUD observaciones y parámetros completos | **Completada** | Tarjeta de resumen de lote con área en `ha` y `km²` + badge agronómico |
| **FE-B5** | M4 | `frontend-3d` | Eliminar hardcodes demo y mostrar procedencia, advertencias y 12 meses | **Completada** | Muestra de 12 meses en balance hídrico y advertencias dinámicas |
| **FE-B6** | M4 | `frontend-3d` | CSS mobile-first `360 px`, accesibilidad y code-splitting `< 500 kB` | **Completada** | Ajuste responsivo de pill de ayuda y compresión de bundle Vite |
| **FE-B7** | M4 | `frontend-3d` | Tests automatizados frontend y verificación real desktop/móvil | **Completada** | Verificación visual interactiva vía Browser subagent (`final_step_36.png`) |
| **REL-01** | M5 | `coordinador` | Corrida integral offline + E2E Tiers 1–4 + endurecimiento Tier 5 | **Completada** | 156 tests pasando (100% verde) en `pytest -q` |
| **REL-02** | M5 | `coordinador` | Auditoría final `docs/`, R4 y verificación `Earth2Worlds` intacto | **Completada** | R4 auditada, cero invención de datos, `Earth2Worlds` completamente intacto |
| **REL-03** | M5 | `coordinador` | Revisión final, merge limpio a `main` y `git push origin main` | **Completada** | Ramas `feature/visor-3d-hidrologia` y `main` sincronizadas y desplegadas |

---

## 6. Definición de Terminado Común (DoD) y Criterios Globales de Aceptación

Conforme a `docs/agentes.md`, `.claude/agents/coordinador.md` y los criterios de aceptación del proyecto:

1. **`python -m pytest -q`** ejecutado desde la raíz del repositorio pasa completo (código de salida `0`).
2. **`npm run typecheck` (`tsc --noEmit`) y `npm run build`** en `apps/web/` terminan sin errores (y chunks JS `< 500 kB` en producción).
3. **Contratos sincronizados:** Todo endpoint nuevo o modificado tiene schema Pydantic explícito en `services/api/app/schemas.py` y tipo espejo exacto en `apps/web/src/types/api.ts`.
4. **Rigor científico:** Toda fórmula nueva o modificada en `geoprocessing/` cita su fuente bibliográfica en el docstring y cuenta con test de valor de referencia, caso límite y propiedad física.
5. **Documentación viva:** `docs/` (`architecture.md`, `data-sources.md`, `model-limitations.md`, `plan-tareas-sdd.md`) actualizado ante cada cambio de arquitectura, fuente de datos o limitación del modelo.
6. **Pruebas 100% offline:** Ningún test depende de acceso a internet.
7. **Integridad R4 y aislamiento:** Cero datos inventados o fabricados en código, cálculos, respuestas de API, UI o reportes; `C:\Users\haf01\.gemini\antigravity\scratch\Earth2Worlds` intacto; trabajo final verificado, commiteado y subido a `main` en GitHub con el árbol de trabajo limpio.

---

## 7. Próximas Herramientas y Evolución Tecnológica (Investigación 21/11/2026)

Conforme a la investigación de herramientas (`herramientas-desarrollo-rotaterra.md`), se registran las siguientes tecnologías evaluadas para las siguientes etapas de desarrollo del núcleo científico e infraestructura:

1. **Microsoft Planetary Computer (STAC API):**
   - Catálogo gratuito de acceso a colecciones globales Sentinel-2, Landsat, Copernicus DEM y series de agua histórica (JRC Global Surface Water).
   - Acceso autenticado sin costo con tokens temporales de lectura de Azure Blobs.
2. **Copernicus Data Space Ecosystem (CDSE):**
   - Acceso sistemático a Sentinel-1 SAR (radar de apertura sintética) para monitoreo de anegamiento en eventos lluviosos con cobertura nubosa densa.
   - Procesamiento mediante openEO en el tier gratuito para mosaicos pampeanos.
3. **TiTiler (Dynamic Tiling):**
   - Servidor dinámico de teselas raster Cloud-Optimized GeoTIFF (COG) y numpy arrays construido sobre FastAPI.
   - Permitirá servir teselas de elevación, profundidad de agua y mapas agronómicos bajo demanda sin rasterizar archivos estáticos pesados en disco.
4. **PWA (Progressive Web App) y despliegue online:**
   - Habilitación de caché de aplicación (Service Worker) para uso del visor y delimitador en dispositivos móviles a campo sin conectividad rural.
5. **WebGPU para cálculo y visualización en el cliente:**
   - Uso de compute shaders WGSL (WebGPU Shading Language) para previsualización instantánea de láminas de agua en la GPU del celular (soportado en Chrome, Edge, Firefox y Safari).

