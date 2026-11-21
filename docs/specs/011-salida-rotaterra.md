# Spec 011 · Salida para Rotaterra (contrato `Observacion`)

**Estado:** implementada (primera versión) · **Fecha:** 21/11/2026 · **Etapa:** 3 (tarea B0)

## 1. Objetivo

Este repositorio es **el módulo de agua y relieve de Rotaterra**. Rotaterra (núcleo en `hernanfirmapaz-ops/N4-4-1.2`) necesita recibir los resultados de cada lote en su contrato común `Observacion`, para combinarlos con clima, NDVI y humedad del suelo y decidir la rotación.

## 2. Endpoint

`GET /api/v1/fields/{field_id}/observaciones?run_id=…`

- Sin `run_id`, usa la corrida activa más reciente del lote.
- Devuelve una lista de `Observacion` con la misma forma que `rotaterra/contrato.py` de N4-4-1.2:

```json
{"lote_id": "…", "fecha": "2026-11-21", "variable": "pendiente_media_pct", "valor": 0.9,
 "unidad": "%", "fuente": "Copernicus GLO-30", "resolucion_m": 30, "calidad": "dudosa", "nota": "…"}
```

- `fuente` con un máximo de 32 caracteres (largo de la columna en la base de N4).
- **Nunca se inventa un valor:** si un resultado no existe todavía, se devuelve `valor: null`, `calidad: "descartada"` y el motivo en `nota`.
- El endpoint **no dispara cálculos ni consultas a internet**: solo lee lo ya calculado.

## 3. Variables (primera versión)

| Variable | Unidad | Origen | Calidad |
|---|---|---|---|
| `superficie_lote_ha` | ha | Polígono del lote | buena |
| `pendiente_media_pct` | % | Relieve (fuente del MDE) | buena con MDT ≤ 5 m; dudosa con 30 m |
| `bajos_area_ha` | ha | Depresiones dentro del lote | según relieve |
| `bajos_volumen_m3` | m³ | Depresiones dentro del lote | según relieve |
| `aporte_externo_ha` | ha | Superficie fuera del lote que drena hacia él | según relieve |
| `arcilla_pct`, `arena_pct`, `limo_pct` | % | Suelo (spec 004) | la del suelo |
| `grupo_hidrologico` | código 1–4 (A–D) | Suelo (spec 004) | la del suelo; la letra va en `nota` |
| `lluvia_evento_mm` | mm | Evento de la corrida | buena si es medida; dudosa si es de diseño |
| `escurrimiento_mm` | mm | Curva Número | según indicador de confianza |
| `coeficiente_escurrimiento_pct` | % | Curva Número | según indicador de confianza |
| `volumen_escurrido_m3` | m³ | Curva Número × superficie | según indicador de confianza |
| `caudal_pico_m3_s` | m³/s | Ruteo | según indicador de confianza |
| `area_encharcada_ha` | ha | Simulación 2D (h > 2 cm) | **descartada** si la corrida no tiene 2D |
| `perdida_suelo_t_ha` | t/ha | USLE por tormenta (herramientas) | dudosa |

**Pendientes (se agregan con la spec 006):** `dias_agua_max`, `area_agua_mas_2_dias_ha`, `riesgo_rinde_min_pct`, `riesgo_rinde_max_pct`. **Pendiente:** `raster_ref` (URI de COG) para los mapas.

## 4. Criterios de aceptación

- [x] Cada observación valida contra el contrato de N4-4-1.2 (mismos campos y tipos; `fuente` ≤ 32 caracteres).
- [x] Lote sin cálculos: todas las variables con `valor: null` y `calidad: "descartada"`, ninguna inventada (test).
- [x] Lote con relieve, hidrología, corrida y herramientas: valores numéricos y fuentes reales (test).
- [x] El área encharcada no se estima con fórmulas aproximadas: sin simulación 2D queda descartada (test).
- [x] Tests sin internet.
- [ ] Rotaterra (N4-4-1.2) consume el endpoint (pendiente del lado de Rotaterra).
