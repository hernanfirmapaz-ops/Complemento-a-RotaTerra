# Datos, Muestras y Persistencia (`data/`)

Este directorio contiene las muestras de prueba y la estructura de almacenamiento en disco utilizada por **Complemento a RotaTerra**.

---

## 1. Lotes de Muestra Catastrales (`data/sample/`)

### `san_luis_parcela_205.geojson`
- **Tipo de dato:** Límite parcelario real oficial (no sintético).
- **Identificación catastral:** Parcela rural `205`, nomenclatura `00-03-30-00-000000-000205`, partida inmobiliaria `05-1397`, plano de mensura `03-11-2001`.
- **Fuente:** Dirección Provincial de Catastro y Tierras Fiscales de San Luis (servicio público WFS, capa `SanLuis:GIS_PARCELAS_RUR_VV`).
- **Sistema de coordenadas:** `EPSG:4326` (WGS84 lat/lon).
- **Superficie catastral:** `1.993.424 m²` (~`199,34 ha`).
- **Superficie calculada en proyección UTM huso 20S (`EPSG:32720`):** ~`199,1 ha`.
- **Uso:** Utilizado en las baterías de tests automatizados unitarios, de integración y E2E para verificar cálculos de pendientes, perfiles, hidrología estática, simulación hidrodinámica 2D y el toolkit agronómico sin requerir conexión a internet.

---

## 2. Almacenamiento Dinámico por Corrida (`data/runs/`)

La carpeta `data/runs/` almacena el estado de los lotes creados en tiempo de ejecución. Está expresamente excluida del control de versiones mediante `.gitignore`.

Para cada lote se genera un subdirectorio `data/runs/<field_id>/` con la siguiente estructura:
- `field.json`: Definición vectorial del lote en GeoJSON, bounding box y metadatos.
- `source/`: Archivo ráster MDE original descargado o cargado por el usuario (inalterable).
- `dem_utm.tif`: MDE reproyectado y recortado en la zona UTM métrica correspondiente.
- `terrain.json`: Métricas de cota mínima, máxima, media, histograma de pendientes y control de calidad.
- `hydrology.json`: Resultados de acondicionamiento, flujos D8/MFD y redes de drenaje.
- `hydrology_grids.npz`: Capas ráster comprimidas NumPy (`flow_accum_mfd`, `twi`, `spi`, `soil_loss_t_ha`, `agronomic_zone_id`, `ndvi`).
- `toolkit.json`: Métricas calculadas por las 8 herramientas agronómicas complementarias.
- `observations.json`: Registro de observaciones georreferenciadas a campo.

---

## 3. Manejo Seguro de Credenciales y Claves de API

- **Regla de oro:** Jamás se almacenan credenciales ni claves de API en el código fuente ni en el historial de Git.
- **Variables de entorno:** Las claves como `OPENTOPOGRAPHY_API_KEY` se configuran exclusivamente en el archivo local `.env` (ignorado por `.gitignore`).
- **Degradación controlada (R4):** Si una clave de API externa falta o un servicio remoto se encuentra inactivo, el sistema degrada gracefully reportando advertencias descriptivas sin generar datos artificiales.
