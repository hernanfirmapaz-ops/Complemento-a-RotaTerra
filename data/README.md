# Datos de muestra (`data/sample/`)

## `san_luis_parcela_205.geojson`

- **Tipo de dato:** límite parcelario real (no sintético).
- **Identificación:** Parcela rural `205`, nomenclatura catastral `00-03-30-00-000000-000205`, partida inmobiliaria `05-1397`, plano de mensura `03-11-2001`.
- **Fuente:** Dirección Provincial de Catastro y Tierras Fiscales de la Provincia de San Luis (geoservicio WFS público, capa `SanLuis:GIS_PARCELAS_RUR_VV`).
- **CRS:** `EPSG:4326` (WGS84, grados decimales `lon, lat`).
- **Superficie registrada en catastro:** `1.993.424 m²` (`199,34 ha`).
- **Superficie calculada en UTM 20S (`EPSG:32720`):** ~`199,1 ha`.
- **Advertencia operativa (SDD §5.1):** es un límite catastral oficial; en un establecimiento real debe verificarse si coincide con el límite productivo efectivo (alambrados internos, caminos, bajos no cultivados).

## Carpeta `data/runs/`

Se genera en tiempo de ejecución (ignorada por Git). Cada lote importado guarda en `data/runs/<field_id>/`:
- `field.json`: geometría validada y metadatos.
- `source/`: archivo DEM original tal cual fue descargado o subido (nunca se modifica, SDD §6.2).
- `dem_utm.tif`: DEM derivado reproyectado a la zona UTM del lote más su zona de aporte.
- `terrain.json`: metadatos de la fuente, parámetros de la corrida e informe de calidad.
