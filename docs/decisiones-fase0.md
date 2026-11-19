# Informe de decisiones técnicas — Fase 0 (`feature/visor-3d-hidrologia`)

Este documento resume las decisiones tomadas al inspeccionar el repositorio original **Earth2Worlds / RotaTerra** y construir la **Fase 0** del *Visor 3D de lotes y simulación de escurrimiento superficial*, conforme al punto **§17.1** del SDD.

---

## 1. Alineación con el stack existente de Earth2Worlds / RotaTerra

| Componente | Hallazgo en `Earth2Worlds` | Decisión en `Complemento-a-RotaTerra` (Fase 0) | Justificación |
|---|---|---|---|
| Backend API | Python + **FastAPI** + Pydantic v2 + Uvicorn (`app/main.py`, `rotaterra/api.py`) | **FastAPI** bajo `/api/v1` (`services/api/app/main.py`) | Mantiene el mismo lenguaje, servidor ASGI y estilo de contratos Pydantic v2 del proyecto principal |
| Geoprocesamiento Python | `rasterio`, `numpy`, `shapely`, `httpx` ya usados en `rotaterra/fuentes/copdem.py` y `nasadem.py` | Librería dedicada `geoprocessing/` sobre `rasterio` + `shapely` + `numpy` | Reutiliza las mismas librerías binarias ya probadas en Windows con Python 3.14, sin exigir compilaciones externas en Fase 0 |
| Acceso a Copernicus GLO-30 | `rotaterra/fuentes/copdem.py` consulta los COG de AWS Open Data y el XML de la ESA | `geoprocessing/dem/sources.py` + `geoprocessing/net.py` (`HttpRangeFile` con `httpx` + `truststore`) | Se conserva la fuente oficial de 30 m sin credenciales y se añade lectura por rangos HTTP validada contra el almacén de certificados de Windows (compatible con inspección TLS de antivirus locales sin desactivar SSL) |
| Frontend | Prototipo `frontend/` en **React 19 + TypeScript + Vite** (con Leaflet 2D) | **React 19 + TypeScript + Vite** en `apps/web/` reemplazando Leaflet por **MapLibre GL JS + Three.js** | Sigue exactamente la recomendación del SDD §7.1 y §8.1 para combinar mapa base 2D/3D con malla local Three.js |
| Persistencia e infraestructura | SQLite local (`earth2worlds.db`); la máquina de desarrollo no tiene Docker ni PostgreSQL/PostGIS instalados | Persistencia trazable en disco (`data/runs/<field_id>/`) con archivos JSON y GeoTIFF separados (`source/` inmutable + `dem_utm.tif` derivado) | Permite ejecutar y verificar toda la Fase 0 localmente sin dependencias externas pesadas; la capa `services/api/app/services/store.py` encapsula la lectura/escritura para migrar a PostGIS en Fase 1–2 |

---

## 2. Decisiones geoespaciales clave (SDD §6.1 y §6.2)

1. **Reproyección obligatoria a CRS métrico (UTM):**
   - Cada lote importado determina automáticamente su huso UTM WGS84 (`EPSG:32719`, `32720`, `32721`, etc.) a partir de su centroide (`geoprocessing/crs.py`).
   - La superficie en hectáreas, el buffer de aporte externo (`buffer_m`, por defecto 300 m), el tamaño de celda del DEM de trabajo, la pendiente (método de Horn 3×3) y las distancias del perfil altimétrico se calculan **exclusivamente en metros UTM**, nunca en grados.
2. **Inmutabilidad del DEM original y no sobre-muestreo:**
   - El recorte original descargado o el GeoTIFF subido por el usuario se guarda intacto en `data/runs/<field_id>/source/`.
   - El DEM de trabajo (`dem_utm.tif`) se reproyecta con resolución igual al lado mayor del píxel original redondeado a `0,1 m` (`max(px, py)`), de modo que nunca inventa una resolución más fina que la fuente.
3. **Georreferenciación exacta entre MapLibre y Three.js:**
   - En lugar de posicionar una caja aproximada, cada vértice `(lon, lat, z)` de la malla del DEM y del perímetro densificado del lote se transforma con `MercatorCoordinate.fromLngLat` respecto de un punto de anclaje local en el centro del lote. Esto evita errores de precisión `Float32` en WebGL y garantiza que el relieve 3D y el borde del lote calcen sin desplazamientos sobre la imagen satelital de MapLibre.
4. **Anti-*z-fighting* del perímetro parcelario:**
   - El borde del lote se densifica a medio píxel del DEM, toma la cota bilineal del terreno en cada punto y se dibuja en 3D con un desplazamiento vertical mínimo (`max(1.5 m, 2 % del desnivel)`), además de su contorno 2D en MapLibre.

---

## 3. Verificación y pruebas automatizadas

- **Datos reales documentados:** `data/sample/san_luis_parcela_205.geojson` (Parcela Rural 205, Catastro de San Luis, ~199,1 ha en `EPSG:32720`) + recorte real de Copernicus DEM GLO-30.
- **Datos sintéticos etiquetados para tests (`SYNTHETIC=TRUE`):** `geoprocessing/tests/fixtures/synthetic_dem.py` genera un plano inclinado con pendiente analítica exacta (`3 %` E + `4 %` S = `5,00 %`) y un cuenco parabólico cerrado.
- **Suite `pytest` (`7 passed`):**
  - `test_utm_epsg_argentina`
  - `test_parse_valid_sample_parcel`
  - `test_reject_invalid_geometries`
  - `test_slope_aspect_on_synthetic_inclined_plane`
  - `test_profile_and_point_on_synthetic_bowl`
  - `test_quality_report_flags_low_resolution_and_nodata`
  - `test_health_and_full_phase0_flow`

---

## 4. Próximos pasos recomendados para iniciar la Fase 1

1. Incorporar acondicionamiento hidrológico del DEM en `geoprocessing/hydrology/` conservando el DEM original y permitiendo elegir entre preservar depresiones reales, rellenar micro-sumideros espurios o aplicar *burn-in* de líneas de drenaje (SDD §6.2).
2. Implementar dirección de flujo **D8** y acumulación **MFD** con umbral de red de drenaje configurable (SDD §6.3) y validación sobre los fixtures sintéticos (plano inclinado y cuenco).
3. Exponer las nuevas capas activables (pendiente, orientación, hillshade, dirección D8, acumulación MFD y depresiones) en el panel de capas de `apps/web`.
