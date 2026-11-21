# Spec 001 · Módulo de escurrimiento y drenaje de lotes

**Estado:** propuesta, pendiente de aprobación de Hernán · **Repositorio:** Complemento a RotaTerra · **Método:** SDD (spec primero, código después; un criterio se tilda solo cuando se verificó con datos reales)

## 1. Objetivo

Simular sobre el terreno real de un lote de 20 a 500 ha en la llanura de San Luis:

1. **Modo evento (horas):** por dónde corre el agua de una tormenta, cuánto infiltra, cuánto sale y dónde se acumula.
2. **Modo estacional (semanas a meses):** cuándo y dónde se anega el lote por lluvia acumulada y napa freática.

El resultado tiene que ayudar a decidir rotaciones y coberturas en Rotaterra.

## 2. Fuera de alcance (esta spec)

Erosión eólica, vista previa 2D en GPU, multiusuario (`organizacion_id`), diseño hidráulico de obras.

## 3. Entradas

| Entrada | Fuente primaria | Respaldo | Obligatoria |
|---|---|---|---|
| Polígono del lote | GeoJSON EPSG:4326 (Rotaterra) | — | Sí |
| Relieve | MDT 5 m IGN | MDE-Ar v2.1 → Copernicus GLO-30 → NASADEM | Sí |
| Suelo (grupo hidrológico, textura) | Carta INTA 1:100.000 + SISINTA | HYSOGs250m (NASA ORNL) | Sí |
| Cobertura | Elegida por el productor; HLS como contexto | — | Sí |
| Lluvia de diseño | IDF DIT regional (INA/CONICET) | — | Modo evento |
| Lluvia real | Pluviómetro del productor | IMERG Late/Final (vía API de N4-4-1.2) | Opcional |
| Humedad antecedente | SMAP L4 (vía API de N4-4-1.2) | Lluvia de los 5 días previos | Sí |
| Napa freática | Freatímetro del productor | GRACE solo como contexto regional | Modo estacional |
| Caminos, canales, alcantarillas | Productor / IGN | — | Opcional |

> [!NOTE]
> **Estado de implementación de la cadena de relieve:**
> - `MDT 5 m IGN`: Pendiente (sin conector automatizado público; requiere descarga manual o WCS del IGN).
> - `MDE-Ar v2.1`: Pendiente (sin endpoint automatizado).
> - `Copernicus DEM GLO-30` (ESA / AWS S3): **Implementado** (fuente principal en línea).
> - `NASADEM` (OpenTopography API): **Implementado** (fuente de respaldo vía API).
> - Respaldo local de relieve (`data/sample/`): **Implementado** para lotes de muestra offline (con metadatos completos y sin inventar relieve sintético en producción). Lotes de usuario sin conexión devuelven error claro `"Sin conexión: no se pudo descargar el relieve"` (HTTP 503).

## 4. Proceso

1. Descargar y recortar el relieve; reproyectar a UTM 20S; registrar fuente, resolución y **datum vertical**.
2. Suavizar con preservación de bordes; quemar caminos y canales.
3. Generar **dos grillas**: (a) acondicionada con *breaching* + relleno remanente para flujo, TWI y SPI; (b) mínimamente tocada para el motor 2D. Los bajos que aparezcan con agua en OPERA DSWx no se acondicionan.
4. Asignar grupo hidrológico → CN por celda (tabla NRCS editable) → ajuste AMC con SMAP.
5. Construir el hietograma (bloques alternos, duración 1–2 × tiempo de concentración) o importar el evento real.
6. Simular el 2D con Manning **por celda** según cobertura.
7. Modo estacional: balance diario lluvia − ETc − percolación, con almacenamiento limitado por la profundidad de napa.
8. Validar contra OPERA DSWx-HLS/S1 cuando haya imágenes del período.

## 5. Salidas

| Salida | Unidad | Formato |
|---|---|---|
| Profundidad máxima de agua | m | COG (`raster_ref`) + resumen por lote |
| Velocidad máxima | m/s | COG |
| Tiempo de llegada a zonas bajas | h | COG |
| Volúmenes: lluvia, infiltración, salida, almacenamiento | m³ y mm | `Observacion` |
| Área anegada (> 2 cm) | ha y % | `Observacion` |
| Hidrograma de salida | L/s vs. tiempo | Serie |
| Días anegados por zona (modo estacional) | días | COG + resumen |

Todo valor escalar se entrega como `Observacion` (contrato de N4-4-1.2) con `unidad`, `fuente`, `resolucion_m`, `calidad` y `nota`. Los rasters agregan el campo opcional `raster_ref` (URI de COG).

## 6. Reglas de calidad

- **Nunca inventar un valor.** Si falta un dato: `valor: null` + `calidad: "descartada"` + motivo en `nota`.
- Relieve de 30 m → `calidad: "dudosa"`; MDT 5 m → `"buena"`.
- La lluvia de diseño siempre lleva el rótulo "IDF regional transpuesta, error ±20%".
- El CN se muestra con una banda de sensibilidad de ±5.
- El balance de masa del 2D cierra con error menor al 1% del volumen llovido.

## 7. Textos de limitación (fijos en la interfaz)

1. "El relieve de 30 m tiene errores de 1–3 m: las vías de agua internas del lote son orientativas."
2. "La lluvia de diseño es regional (transpuesta desde Córdoba), con error ±20%."
3. "IMERG (~10 km) no ve la tormenta puntual sobre su campo."
4. "El modelo de tormenta no incluye el ascenso de napa; en años húmedos el anegamiento real puede ser mucho mayor."
5. "El CN se basa en estudios de la Pampa Ondulada; en suelos arenosos con costra el escurrimiento puede diferir."

## 8. Criterios de aceptación

- [ ] Lote de prueba (-33,70; -65,30) con relieve descargado, fuente y datum declarados.
- [ ] Pendiente media del lote cercana al 1% (no el 2,76% de NASADEM sin tratar).
- [ ] Sin red, ningún módulo devuelve números sintéticos: solo `null` + `descartada`.
- [ ] Manning variable por celda verificado con un lote de dos coberturas.
- [ ] Balance de masa del 2D con error < 1% en 3 eventos (T2, T10, T100).
- [x] Resultado del 2D comparado con Landlab `OverlandFlow` sobre el mismo terreno (ver `docs/benchmarks/landlab.md` y `docs/specs/010-motor-inercial.md`). Cumple el criterio (<15% dif en área) en los 3 casos: plano inclinado (0,00% dif), bajo cerrado (0,00% dif en área, 0,15% en vol) y Parcela 205 (relieve real 443 ha: 7,50% dif en área, 0,18% en vol) mediante la formulación local inercial 2D (Bates 2010 / de Almeida 2012) con grilla escalonada Arakawa-C y $\theta = 0.85$.
- [ ] Índice F informado contra OPERA DSWx en al menos un anegamiento histórico.
- [ ] Los 5 textos de limitación visibles en la interfaz.
- [ ] `python -m pytest -q` y `npm run build` en verde, sin tests que dependan de internet.

## 9. Decisiones pendientes (Hernán)

| # | Decisión | Recomendación |
|---|---|---|
| D1 | Fuentes de datos | **Resuelta (21/11/2026):** el proyecto usa cualquier fuente abierta, real y verificable. Ver regla 4 de `AGENTS.md` y `docs/data-sources.md` |
| D2 | Complemento consume la API de N4-4-1.2 o duplica conectores | Consumir la API (`/clima`, `/lluvia`, `/humedad-suelo`) |
| D3 | Reemplazar el motor 2D por inercial local / Landlab | **Implementado y Validado (21/11/2026):** implementada la formulación inercial local 2D (Bates 2010 / de Almeida 2012) sobre grilla escalonada (`solver_mode="inertial"`). Supera el benchmark con Landlab en todos los casos (<7,5% dif en área, <0,2% en vol). Ver `docs/specs/010-motor-inercial.md`. |
| D4 | Vida del PR #2 (agentes) en GitHub | Cerrar o mergear según cómo se trabaje con Antigravity |

## 10. Orden de implementación

| Fase | Entregable | Agente líder |
|---|---|---|
| 0 | Cobertura MDT 5 m IGN; API key OpenTopography; eliminar respaldo sintético (A1) | Experto datos NASA + coordinador |
| 1 | Relieve multi-fuente, suavizado, *breaching*, dos grillas | Hidrólogo + backend |
| 2 | Suelos (INTA + HYSOGs) → CN por celda + AMC con SMAP | Hidrólogo + experto datos |
| 3 | IDF DIT + hietograma; importación IMERG / pluviómetro | Hidrólogo |
| 4 | Manning por celda; comparación con Landlab | Hidrólogo + backend |
| 5 | Visor: capas, hidrograma, textos de limitación | Frontend 3D |
| 6 | Validación OPERA DSWx | Experto datos NASA |
| 7 | Modo estacional con napa | Hidrólogo |
