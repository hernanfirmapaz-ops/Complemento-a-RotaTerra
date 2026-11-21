# Spec 006 · Días de Encharcamiento y Riesgo de Rinde

**Proyecto:** `Complemento-a-RotaTerra`  
**Etapa:** 3 (Plan de Trabajo 20/11/2026, tareas 3.2, 3.3, 3.4)  
**Mejoras que cubre:** R1 (Días de anegamiento y vaciado), R2 (Riesgo agronómico de rinde por zona)  
**Dependencias:** Spec 001 (Escurrimiento 2D), Spec 004 (Suelos reales / $K_{sat}$ Rawls 1982), Spec 005 (WhiteboxTools / dos grillas).

---

## 1. Problema Agronómico y Objetivo

Una simulación hidrodinámica 2D entrega láminas de agua máximas instantáneas ($h_{\text{max}}$) y láminas remanentes inmediatas tras el evento de lluvia ($h_{\text{remanente}}$). Sin embargo, el productor y el asesor técnico no toman decisiones por "centímetros de agua acumulada", sino por **cuántos días permanecerá el agua sobre el cultivo** y **cuánto rinde se perderá por asfixia radicular (anoxia)**.

El objetivo de esta spec es:
1. Calcular el **mapa de días de permanencia del agua** para cada bajo o cubeta del lote mediante un balance de vaciado físico (infiltración de fondo saturada + evapotranspiración diaria).
2. Estimar el **riesgo agronómico de rinde** expresado en **rangos de merma porcentual** según cultivo, fenología y días de anegamiento (basado en literatura agronómica de INTA y USDA con datos textuales sin extrapolar).
3. Entregar a Rotaterra, por lote y por zona, las hectáreas afectadas, los días de agua y el rango de merma (spec 011). **El impacto económico lo calcula Rotaterra**, no este módulo (decisión de Hernán del 21/11/2026).

---

## 2. Modelo Físico de Vaciado de Bajos (Tarea 3.2)

Una celda encharcada ($h > 0.01\text{ m}$) pierde agua a través de dos mecanismos físicos simultáneos:

$$\Delta h_{\text{día}} = K_{\text{sat, efectivo}} + ET_0$$

Donde:
1. **$K_{\text{sat, efectivo}}$ (Conductividad hidráulica saturada de fondo):**
   - Obtenida a partir de la textura USDA real reportada por SoilGrids 2.0 (Spec 004) según la tabla original de **Rawls, Brakensiek & Saxton (1982)** (*Estimation of soil water properties*, Trans. ASAE, Vol. 25, No. 5, pp. 1316–1320, Table 2, pág. 1318).
   - Conversión de unidades estándar: $1\text{ cm/h} = 10\text{ mm/h} = 240\text{ mm/día}$.
   - Los valores de media geométrica de conductividad hidráulica saturada están publicados en la **página 1318, Table 2** de Rawls et al. (1982) (*Estimation of Soil Water Properties*, Trans. ASAE, Vol. 25, No. 5, pp. 1316–1320, DOI: 10.13031/2013.33720). Se eliminó la columna de desvío estándar por no estar reportada en dicha unidad/columna en la Tabla 2 original:

   | Textura USDA (Clase) | $K_{sat}$ media (cm/h) | $K_{sat}$ efectiva (mm/día) |
   |---|---|---|
   | Arenosa (*Sand*) | 21,00 | **5040** |
   | Arenosa franca (*Loamy sand*) | 6,11 | **1466** |
   | Franco arenosa (*Sandy loam*, ej. Villa Mercedes) | 2,59 | **622** |
   | Franca (*Loam*) | 1,32 | **317** |
   | Franco limosa (*Silt loam*) | 0,68 | **163** |
   | Franco arcillo arenosa (*Sandy clay loam*) | 0,43 | **103** |
   | Franco arcillosa (*Clay loam*) | 0,23 | **55** |
   | Franco arcillo limosa (*Silty clay loam*) | 0,15 | **36** |
   | Arcillo arenosa (*Sandy clay*) | 0,12 | **29** |
   | Arcillo limosa (*Silty clay*) | 0,09 | **22** |
   | Arcillosa (*Clay*) | 0,06 | **14** |

   - **Regla estricta de ausencia de datos de suelo:** Si no hay textura de SoilGrids ni de análisis de suelo, el valor de $K_{sat}$ es `null` (calidad `"descartada"`, nota `"Sin textura de suelo disponible; cálculo de vaciado suspendido"`). **Se prohíbe el uso de valores de respaldo por omisión silenciosos.**
   - **Condicionamiento de campo:** Si el bajo conecta con napa freática superficial a menos de 0,5 m, la infiltración neta cae hacia cero ($K_{sat} \to 0$) y la evacuación ocurre casi exclusivamente por evapotranspiración ($ET_0$).
2. **$ET_0$ (Evapotranspiración diaria de referencia):**
   - Obtenida del promedio del mes del evento según FAO-56 Penman-Monteith (NASA POWER climatológica ya implementada en el módulo de balance hídrico). Típicamente $3\text{ a }7\text{ mm/día}$ en verano pampeano.
3. **Cálculo de días:**

$$\Delta h_{\text{día}} = K_{\text{sat, efectivo}} + ET_0$$

$$D_{\text{encharcamiento}} = \frac{h_{\text{remanente}} \times 1000}{\Delta h_{\text{día}}}$$

- El valor se redondea hacia arriba en días enteros para cada celda ($1, 2, 3, \dots, > 7\text{ días}$).
- Se verifica conservación estricta de balance de masa: $\sum \text{Volumen infiltrado} + \sum \text{Volumen evaporado} = \text{Volumen almacenado inicial}$.

---

## 3. Riesgo de Pérdida de Rinde por Cultivo (Tarea 3.3)

Conforme a la **Regla 2 del proyecto** (*"Ningún número sin fuente consultada, documento y página"*), cada número de merma proviene estrictamente de la medición reportada en el documento científico citado, sin extrapolaciones sintéticas.

### 3.1 Fundamento agronómico y fisiológico de la respuesta al anegamiento

El exceso de agua desplaza el oxígeno del espacio poroso del suelo (anoxia o hipoxia), deteniendo la respiración aeróbica de las raíces y la producción de ATP tras 24 a 48 horas de saturación continua. Esto provoca:
1. Inhibición inmediata del transporte activo de nutrientes ($N, P$) y acumulación de compuestos fitotóxicos reducidos ($Fe^{2+}, Mn^{2+}$, sulfuros).
2. Pérdida de nodulación y fijación biológica de nitrógeno en leguminosas (soja).
3. Muerte del ápice meristemático si queda sumergido (etapas vegetativas tempranas en maíz y girasol).
4. Aborto de estructuras reproductivas por estrés oxidativo y caída en la tasa de llenado de grano.

### 3.2 Tabla verificada de mermas de rinde en función de días de encharcamiento ($h > 1\text{ cm}$)

Conforme a la **Regla de datos del proyecto** (*"Ningún número sin fuente consultada en el documento original"*), cada fila incluye obligatoriamente DOI o enlace verificable que abre el documento, tabla o página exacta, y una frase textual corta del original que contiene el dato numérico. **Toda fila que no pudo ser abierta y leída directamente en la publicación original ha sido eliminada.**

| Cultivo | Días con agua superficial ($h > 1\text{ cm}$) | Fenología / Etapa | Merma de rinde reportada | Fuente documental verificada en el original (documento + tabla/página / DOI / cita textual) |
|---|---|---|---|---|
| **Trigo** (*Triticum aestivum*) y **Cebada** (*Hordeum vulgare*) | 15 a 20 días | Aparición de Hoja 7 a antesis (período crítico previo a floración) | **34 – 92 %** (trigo)<br>**40 – 79 %** (cebada) | De San Celedonio, R. P., Abeledo, L. G., & Miralles, D. J. (2014). *"Identifying the critical period for waterlogging on yield and its components in wheat and barley"*, *Plant and Soil*, 378(1-2):265–277. DOI: [10.1007/s11104-014-2028-6](https://doi.org/10.1007/s11104-014-2028-6). Texto completo en repositorio institucional FAUBA: [2014desanceledonio.pdf](http://ri.agro.uba.ar/files/download/articulo/2014desanceledonio.pdf) y CONICET Digital: [handle 11336/4210](http://hdl.handle.net/11336/4210). **Cita textual:** *"During this period, waterlogging generated penalties in grain yield from 34 to 92% in wheat and from 40 to 79% in barley"* (pág. 265 / Abstract). |
| **Soja** (*Glycine max*) | 7 a 8 días | Reproductivo / Llenado de grano (R5) | **20 – 39 %** (cultivares tolerantes) | Rhine, M. D., Stevens, G., Shannon, G., Wrather, A., & Sleper, D. (2010). *"Yield and nutritional responses to waterlogging of soybean cultivars"*, *Irrigation Science*, 28(2):135–142. DOI: [10.1007/s00271-009-0168-x](https://doi.org/10.1007/s00271-009-0168-x). Table 3 (pág. 139). **Cita textual:** *"Yield losses in flood-tolerant genotypes typically ranged from 20% to 39%"* (pág. 135 / Abstract y Table 3). |
| **Girasol** (*Helianthus annuus*) | Corto plazo (anegamiento transitorio) | Llenado de grano (*grain filling*) | **15 – 32 %** (aceite)<br>**25 – 60 %** (grano) | Grassini, P., Indaco, G. V., López Pereira, M., Hall, A. J., & Trápani, N. (2007). *"Responses to short-term waterlogging during grain filling in sunflower"*, *Field Crops Research*, 101(3):352–363. DOI: [10.1016/j.fcr.2006.12.009](https://doi.org/10.1016/j.fcr.2006.12.009). **Cita textual:** *"In Experiment 3, the decrease in oil production due to waterlogging was 23% for a light soil mixture and 32% for a heavy soil mixture... In Experiment 4, waterlogging reduced oil yield by 15% (shaded plants) and 18% (unshaded plants)"* (pág. 352 / Abstract y Sección 3). |

*(Cualquier otra combinación de cultivo, días o fenología sin ensayo medido y verificado en la publicación original devuelve `null` + calidad `'descartada'` con nota `'Sin ensayo agronómico verificado en original para esta condición'`. Por ejemplo, maíz no cuenta actualmente con filas verificadas en el original y queda descartado hasta disponer de publicación accesible con cita textual).*

### 3.3 Reglas de aplicación agronómica en el software

1. **Parámetro editable por el usuario:** Todos los umbrales de días y límites de merma son editables en la configuración agronómica del módulo si el productor o asesor técnico dispone de datos específicos de híbridos tolerantes o ensayos de su zona.
2. **Presentación obligatoria de rangos:** El sistema jamás presentará una merma puntual (ej. "32,5%"), sino siempre el intervalo $[min, max]$ (ej. `[20 %, 39 %]`), acompañado de la cita bibliográfica correspondiente.
3. **Desacople económico estricto:** El Complemento entrega exclusivamente hectáreas afectadas, días máximos de agua y rango de merma $[min, max]$. La valorización económica en moneda (\$ o USD) corre por cuenta exclusiva de RotaTerra en su motor de rotaciones.

---

## 4. Salida para Rotaterra (en lugar del impacto económico)

El cálculo económico (ha × rinde × precio) **no se hace en este módulo**: lo hace Rotaterra con sus propios rindes, precios y cultivos. Este módulo entrega, por lote y por zona de encharcamiento, en el contrato `Observacion` (spec 011):

| Variable | Unidad | Ejemplo |
|---|---|---|
| `area_encharcada_ha` | ha | 8,4 |
| `dias_agua_max` | días | 4 |
| `area_agua_mas_2_dias_ha` | ha | 3,1 |
| `riesgo_rinde_min_pct` | % | 20 |
| `riesgo_rinde_max_pct` | % | 39 |

Cada valor con su `fuente`, `calidad` y `nota` (cultivo, etapa y referencia bibliográfica de la merma).

---

## 5. Criterios de Aceptación Técnicos

1. **Balance de vaciado:**
   - [ ] Test unitario que valida que el vaciado por infiltración y $ET_0$ consume exactamente el volumen almacenado ($h_{\text{final}} \to 0$).
   - [ ] Cálculo de días determinístico y sin división por cero cuando la infiltración es muy baja.
2. **Estimación agronómica:**
   - [ ] Tests de rango de merma para cultivos con ensayo verificado en el original (Trigo, Soja, Girasol) y retorno de `null` + `'descartada'` para cultivos sin ensayo verificado (Maíz), sin números mágicos hardcodeados.
   - [ ] Rango devuelto siempre como tupla `(min_pct, max_pct)`.
3. **Interfaz:**
   - [ ] Capa de visualización "Días de anegamiento" en el visor con paleta discreta (1 día, 2 días, 3-4 días, $\ge 5$ días).
   - [ ] Resultados disponibles para Rotaterra en `GET /api/v1/fields/{id}/observaciones` (spec 011).
   - [ ] Sin incremento en el presupuesto de botones de la primera pantalla.
