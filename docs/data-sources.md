# Fuentes de datos y jerarquía de calidad (SDD §5)

## 1. Modelos Digitales de Elevación (MDE / MDT)

| Prioridad | Fuente | Resolución nominal | Tipo de superficie | Uso en el sistema | Limitaciones |
|---:|---|---:|---|---|---|
| 1 | Relevamiento propio (Dron RTK / LiDAR / GNSS) subido como GeoTIFF | 0,05 – 2 m | MDT (si fue filtrado) o MDS | Microrelieve, surcos, cunetas, bajos internos y obras | Requiere declarar datum vertical, precisión y fecha |
| 2 | IGN Argentina — MDE aerofotogramétrico (subida GeoTIFF) | 5 m | MDS / MDT según producto | Relieve detallado en zonas con cobertura IGN | Cobertura geográfica parcial |
| 3 | IGN Argentina — MDE-Ar v2.1 / Copernicus DEM GLO-30 | 30 m | MDS (incluye vegetación y construcciones) | Contexto topográfico general y macro-pendientes | **No describe surcos, cunetas ni microdepresiones** |

### Fuente automática incluida en Fase 0: Copernicus DEM GLO-30

- **Proveedor:** Agencia Espacial Europea (ESA) / Airbus Defence and Space / DLR (misión TanDEM-X), distribuido como Cloud Optimized GeoTIFF (COG) en AWS Open Data (`https://copernicus-dem-30m.s3.amazonaws.com`).
- **Lectura:** por ventanas HTTP (`Range`) sin descargar el mosaico completo de 1° × 1°, más lectura del XML oficial del mosaico para extraer las fechas reales de adquisición (`tsxx_startTime` / `tsxx_stopTime`).
- **Datum vertical:** EGM2008 (alturas ortométricas).
- **Precisión vertical declarada:** < 4 m (LE90 absoluto).

## 2. Lote real de muestra (`data/sample/san_luis_parcela_205.geojson`)

- **Fuente:** Dirección Provincial de Catastro y Tierras Fiscales de San Luis (`SanLuis:GIS_PARCELAS_RUR_VV`).
- **Identificación:** Parcela rural `205` (`00-03-30-00-000000-000205`), ~199,1 ha en UTM 20S (`EPSG:32720`).
- **Advertencia:** límite catastral oficial; puede diferir del límite productivo efectivo.
