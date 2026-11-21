# Spec 004 · Suelos reales del lote

**Estado:** implementada parcialmente (SoilGrids) · **Fecha:** 21/11/2026 · **Etapa:** 2 (tarea 2.6)

## 1. Objetivo

Reemplazar el grupo hidrológico fijo ("B por omisión") por un dato de suelo **real y con su fuente**, para que la Curva Número, la infiltración y el indicador de confianza reflejen el suelo del lote.

## 2. Fuentes y orden de respaldo

| Orden | Fuente | Resolución | Licencia | Estado |
|---|---|---|---|---|
| 1 | Análisis de suelo del productor | Puntual | Del productor | Pendiente (carga manual) |
| 2 | Cartas de suelo INTA (GeoINTA, WMS/WFS) | 1:100.000 | INTA | **A verificar:** confirmar URL del servicio y nombre de las capas de San Luis |
| 3 | **SoilGrids 2.0 (ISRIC)** | 250 m | CC BY 4.0 | **Implementada** |
| 4 | HYSOGs250m (NASA ORNL DAAC) | 250 m | Libre con cita | Pendiente (requiere Earthdata) |
| — | Sin fuente disponible | — | — | "Suelo por omisión, sin confirmar" (nunca inventado) |

## 3. Proceso (SoilGrids)

1. Hasta 3 puntos dentro del lote: el centroide y dos puntos interiores.
2. Por punto, se consulta `https://rest.isric.org/soilgrids/v2.0/properties/query` con `clay`, `sand` y `silt`, profundidades `0-5cm`, `5-15cm` y `15-30cm`, valor `mean`.
3. Se convierten las unidades (g/kg → %) y se promedia 0–30 cm ponderando por espesor (5, 10 y 15 cm).
4. Se promedian los puntos válidos y se clasifica la textura con el triángulo USDA.
5. Grupo hidrológico aproximado por textura (Rawls et al., 1982; USDA SCS):

| Textura USDA | Grupo |
|---|---|
| Arenosa, arenosa franca, franco arenosa | A |
| Franca, franco limosa, limosa | B |
| Franco arcillo arenosa | C |
| Franco arcillosa, franco arcillo limosa, arcillo arenosa, arcillo limosa, arcillosa | D |

6. El resultado se guarda en `soil.json` del lote para no repetir consultas (SoilGrids limita la cantidad de pedidos por minuto).

## 4. Salida (`GET /api/v1/fields/{id}/soil`)

| Campo | Ejemplo |
|---|---|
| `soil_group` | `"A"` o `null` |
| `texture_class` | `"Franco arenosa"` |
| `clay_pct`, `sand_pct`, `silt_pct` | `9,8` · `71,2` · `19,0` |
| `soil_source` | `"soilgrids"` o `"default"` |
| `source_label` | `"SoilGrids 2.0 (ISRIC) · 250 m · 0–30 cm"` |
| `resolution_m` | `250` |
| `license` | `"CC BY 4.0"` |
| `points_used` | `3` |
| `quality` | `"buena"`, `"dudosa"` o `"descartada"` |
| `notes` | Limitaciones |

## 5. Limitaciones (se muestran al usuario)

- SoilGrids es un **modelo global** de 250 m: no distingue lomas y bajos dentro del lote.
- El grupo por textura **no considera la napa**: un bajo con napa somera se comporta como grupo D aunque la textura sea arenosa.
- El sellado superficial de suelos arenosos con poca materia orgánica puede aumentar el escurrimiento.

## 6. Criterios de aceptación

- [x] Clasificación de textura USDA verificada con casos de referencia (test).
- [x] Grupo hidrológico por textura según la tabla del punto 3.5 (test).
- [x] Sin conexión: `soil_group = null`, `soil_source = "default"`, `quality = "descartada"` y motivo (test).
- [x] Tests sin internet (`httpx.MockTransport`).
- [x] La simulación usa el grupo y la fuente reales cuando están disponibles, y el indicador de confianza deja de decir "por omisión".
- [x] **Verificado en vivo** contra la API de SoilGrids para un lote de Villa Mercedes (ver Sección 7).
- [ ] INTA (GeoINTA) conectado tras confirmar el servicio (ver Sección 8).
- [ ] HYSOGs250m como respaldo (ver Sección 8).

---

## 7. Verificación en vivo (21/11/2026)

- **Lote de prueba:** Área rural al sur de Villa Mercedes, San Luis (`lat: -33.75, lon: -65.40`).
  *(Nota técnica: en el casco urbano `-33.68, -65.45`, SoilGrids enmascara el área urbanizada devolviendo capas sin datos (`mean: None`), lo cual activa correctamente el fallback honesto `soil_source="default"` sin inventar valores).*
- **Respuesta de la API SoilGrids 2.0 (`GET /api/v1/fields/{id}/soil`):**
  - `soil_group`: `"A"`
  - `texture_class`: `"Franco arenosa"`
  - `clay_pct`: `12.2%`
  - `sand_pct`: `66.1%`
  - `silt_pct`: `21.7%`
  - `soil_source`: `"soilgrids"`
  - `source_label`: `"SoilGrids 2.0 (ISRIC) · 250 m · 0–30 cm"`
  - `points_used`: `3`
  - `quality`: `"buena"`

---

## 8. Pendientes de investigación y conexión futura (no programar todavía)

1. **Suelos INTA (GeoINTA / INTA Digital GEO):**
   - Confirmar previamente la disponibilidad de los servicios WMS/WFS para San Luis (capas temáticas de cartas de suelo escala 1:50.000 / 1:100.000).
   - Verificar si el endpoint GEO INTA provee atributos de textura analítica o solo unidades cartográficas taxonómicas que requieran tabla de conversión local.
2. **HYSOGs250m como respaldo secundario:**
   - Base global raster (250 m) de Grupos Hidrológicos de Suelo generada por Ross et al. (2018) disponible vía Oak Ridge National Laboratory (ORNL) DAAC / NASA Earthdata.
   - Requiere token Earthdata o almacenamiento de teselas locales; se implementará como contingencia cuando SoilGrids no tenga cobertura o esté fuera de servicio.


