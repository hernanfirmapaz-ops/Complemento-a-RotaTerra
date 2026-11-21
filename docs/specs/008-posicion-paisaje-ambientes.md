# Spec 008 · Posición en el Paisaje, Zonificación Topográfica y Exportación de Capas

**Proyecto:** `Complemento-a-RotaTerra`  
**Etapa:** 3 (Plan de Trabajo 20/11/2026, tareas 3.8, 3.9)  
**Mejoras que cubre:** R5 (Posición en el paisaje: loma, media loma, bajo), R6 (Ambientes topográficos exportables), I2 (Exportación estándar GIS y maquinaria)  
**Dependencias:** Spec 001 (Topografía y ruteo MFD), Spec 005 (WhiteboxTools / TWI / curvatura).

---

## 1. Problema Agronómico y Objetivo

Para la agricultura de precisión (ambientación de siembra variable, fertilización diferenciada y manejo hídrico), el productor necesita dividir el lote en **ambientes topográficos objetivos** que reflejen la dinámica del agua:
- **Loma:** zonas altas y secas con menor retención de humedad, ideales para densidades de siembra moderadas.
- **Media loma:** laderas de tránsito bien drenadas con potencial de rinde estable.
- **Bajo:** zonas receptoras de agua y sedimentos con alto potencial en años secos y riesgo severo de anegamiento en años húmedos.

El objetivo de esta spec es:
1. Clasificar geomorfológicamente cada píxel del lote en **Loma, Media Loma o Bajo**, garantizando que la suma de hectáreas sea exactamente igual al área del lote.
2. Permitir la **exportación multiformato (Shapefile ZIP, GeoJSON, GeoTIFF y CSV)** compatible con software GIS (QGIS, ArcGIS) y monitores de maquinaria agrícola (John Deere Operations Center, Climate FieldView, Trimble).

---

## 2. Clasificación Geomorfológica de Posición en el Paisaje (Tarea 3.8)

Se utiliza una combinación robusta de tres descriptores topográficos invariantes calculados sobre el DEM UTM métrico:

### 2.1 Descriptores
1. **Índice de Posición Topográfica (TPI - Topographic Position Index):**

$$\text{TPI}_R = z_0 - \bar{z}_R$$

Donde $\bar{z}_R$ es la elevación promedio en un radio circular $R$ (con dos escalas: $R_1 = 50\text{ m}$ para micro-relieve y $R_2 = 250\text{ m}$ para mesorrelieve).
- $\text{TPI} > +0,5 \sigma$: Crestas / Lomas.
- $-0,5 \sigma \le \text{TPI} \le +0,5 \sigma$: Pendiente media / Plano.
- $\text{TPI} < -0,5 \sigma$: Bajos / Vaguadas.

2. **Índice de Humedad Topográfica (TWI):**

$$\text{TWI} = \ln\left(\frac{A_{\text{contribuyente}}}{\tan \beta + 0,001}\right)$$

Valores altos de TWI ($\ge 8,5$) corresponden a zonas de acumulación y convergencia de flujo.

3. **Curvatura de superficie:**
   - Curvatura de plano (convergencia/divergencia lateral) y curvatura de perfil (aceleración/deceleración).

### 2.2 Reglas de asignación a las 3 clases
Para cada celda dentro del lote:
- **Bajo:** $\text{TWI} \ge 8,5$ O $\text{TPI} < -0,6$ O celda que presentó anegamiento en la simulación 2D.
- **Loma:** $\text{TPI} > +0,6$ Y $\text{TWI} < 6,5$ (sectores convexos y divergentes).
- **Media Loma:** Todas las celdas restantes (zonas de pendiente de tránsito).

### 2.3 Post-procesamiento y consistencia
- Filtro de mayoría (área mínima mapeable de $0,1\text{ ha} = 10\text{ celdas}$) para eliminar píxeles aislados y generar polígonos agrícolas operativos.
- **Consistencia de superficie estricta:**

$$\text{Área}_{\text{Loma}} + \text{Área}_{\text{Media\_Loma}} + \text{Área}_{\text{Bajo}} = \text{Área Total del Lote}$$

---

## 3. Exportación de Capas para Monitores y GIS (Tarea 3.9)

### 3.1 Formatos exportables

| Capa | Formatos | Contenido |
|---|---|---|
| **Ambientes Topográficos** | Shapefile ZIP (`.shp`, `.shx`, `.dbf`, `.prj`), GeoJSON | Polígonos disueltos con atributos: `ambiente` (Loma/Media Loma/Bajo), `area_ha`, `twi_medio`, `pendiente_pct` |
| **Red de Drenaje y Desbordes** | Shapefile ZIP, GeoJSON | Líneas vectoriales con atributos: `orden`, `area_contrib_ha`, `tipo` (vaguada principal, red secundaria, ruta desborde) |
| **Lámina de Anegamiento Máximo** | GeoTIFF (Float32, UTM), GeoJSON | Raster métrico de profundidad máxima de agua ($h_{\text{max}}$) y contornos vectoriales de áreas > 2 cm |
| **Resumen del Evento** | CSV | Tabla con balance hídrico, hectáreas por ambiente y métricas de rinde |

### 3.2 Compatibilidad de maquinaria
- El `.prj` del Shapefile se codifica en WGS 84 (EPSG:4326) o UTM local estándar para compatibilidad directa con pantallas de monitores de siembra y pulverización.
- Nombres de campos en `.dbf` limitados a 10 caracteres alfanuméricos en mayúsculas (ej. `AMBIENTE`, `AREA_HA`, `PEND_PCT`).

---

## 4. Criterios de Aceptación Técnicos

1. **Zonificación:**
   - [ ] Test unitario que valida que la suma de hectáreas de los 3 ambientes coincide con el área del polígono dentro del $0,01\%$.
   - [ ] No existen celdas sin clasificar (`null` o `NaN`) dentro del perímetro del lote.
2. **Exportación:**
   - [ ] Endpoint `GET /api/v1/fields/{id}/export/environments?format=shp` devuelve un archivo ZIP con los 4 componentes requeridos (`.shp`, `.shx`, `.dbf`, `.prj`).
   - [ ] Validación con `geopandas`/`fiona` de que los archivos generados abren sin errores de sintaxis ni geometrías inválidas.
