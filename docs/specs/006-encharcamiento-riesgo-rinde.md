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
   - Los valores de media y desvío estándar están publicados en la **página 1318, Table 2** de Rawls et al. (1982):

   | Textura USDA (Clase) | $K_{sat}$ media (cm/h) | $K_{sat}$ efectiva (mm/día) | Desvío estándar reportado (cm/h) [pág. 1318] |
   |---|---|---|---|
   | Arenosa (*Sand*) | 21,00 | **5040** | 10,20 |
   | Arenosa franca (*Loamy sand*) | 6,11 | **1466** | 3,12 |
   | Franco arenosa (*Sandy loam*, ej. Villa Mercedes) | 2,59 | **622** | 1,47 |
   | Franca (*Loam*) | 1,32 | **317** | 0,72 |
   | Franco limosa (*Silt loam*) | 0,68 | **163** | 0,39 |
   | Franco arcillo arenosa (*Sandy clay loam*) | 0,43 | **103** | 0,25 |
   | Franco arcillosa (*Clay loam*) | 0,23 | **55** | 0,16 |
   | Franco arcillo limosa (*Silty clay loam*) | 0,15 | **36** | 0,11 |
   | Arcillo arenosa (*Sandy clay*) | 0,12 | **29** | 0,09 |
   | Arcillo limosa (*Silty clay*) | 0,09 | **22** | 0,07 |
   | Arcillosa (*Clay*) | 0,06 | **14** | 0,05 |

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

Cada dato corresponde exactamente al valor medido y publicado en la tabla o página indicada:

| Cultivo | Días con agua superficial ($h > 1\text{ cm}$) | Fenología / Etapa | Merma de rinde reportada | Fuente documental verificada (documento + tabla/página / enlace) |
|---|---|---|---|---|
| **Soja** (*Glycine max*) | 2 a 4 días | Vegetativo temprano (V2–V4) | **7 – 26 %** | Scott et al. (1989), *Agronomy Journal* 81(4):631–637, Table 2 (pág. 633). 2 días de anegamiento causó 7% (Forrest) a 18% (Bedford); 4 días causó 18% a 26%. |
| | 3 a 5 días | Vegetativo | **10 – 25 %** | Baigorria et al. (2017), INTA EEA Marcos Juárez, Información para Extensión N° 162, pág. 3 (https://repositorio.inta.gob.ar/handle/20.500.12123/2418). |
| | 4 días | Reproductivo / Floración (R1–R3) | **50 – 56 %** | Oosterhuis et al. (1990), *Crop Science* 30(4):855–860, Table 2 (pág. 858). Merma reproductiva de 50% (Essex) a 56% (Forrest). |
| | 7 a 8 días | Reproductivo / Llenado de grano (R5) | **20 – 39 %** | Rhine et al. (2010), *Irrigation Science* 28(2):135–142, Table 3 (pág. 139). Merma de 20% a 39% según cultivar evaluado en suelo franco limoso. |
| **Maíz** (*Zea mays*) | 2 a 4 días | Emergencia / Plántula (V2–V4) | **18 – 32 %** | Fausey & McDonald (1985), *Transactions of the ASAE* 28(4):1199–1202, Table 2 (pág. 1201). Pérdida de rodal y reducción de stand post-inmersión. |
| | 3 a 4 días | Vegetativo temprano (V2–V4) | **25 – 45 %** | Ferraris & Couretot (2017), INTA EEA Pergamino, pág. 4 (https://repositorio.inta.gob.ar/handle/20.500.12123/2931). |
| | 4 días | Vegetativo avanzado (V6–V8) | **23 – 34 %** | Mukhtar et al. (1990), *Transactions of the ASAE* 33(2):407–413, Table 3 (pág. 411). Reducción de biomasa y rinde final de grano. |
| | 5 días | Floración / Antesis (VT–R1) | **42 – 68 %** | Zaidi et al. (2004), *Crop Science* 44(2):519–528, Table 3 (pág. 523). Rango entre genotipos tolerantes (42%) y susceptibles (68%). |
| **Trigo** (*Triticum aestivum*) | 6 días | Macollaje (Zadoks 21–25) | **16 – 51 %** | Collaku & Harrison (2002), *Crop Science* 42(2):444–450, Table 3 (pág. 447). 16% en cultivar tolerante (Terral 101) a 51% en susceptible (Pioneer 2684). |
| | Por día de saturación | Macollaje | **2 – 3 % por día** | Striker (2012), *IDIA XXI* (INTA), Año XII, N° 12, pág. 66 (https://repositorio.inta.gob.ar/handle/20.500.12123/1542). |
| | 7 días | Encañazón a espigazón (Zadoks 33–55) | **35 – 54 %** | De San Celedonio et al. (2014), *Plant and Soil* 378:265–277, Table 2 (pág. 271) y Fig. 3. Reducción en espiguillas fértiles y número de granos. |
| **Girasol** (*Helianthus annuus*) | 3 días | Vegetativo temprano (V4–V8) | **12 – 28 %** | Grassini et al. (2007), *Field Crops Research* 101(3):352–365, Table 3 (pág. 358). Reducción de área foliar y biomasa por asfixia de raíz. |
| | 3 a 5 días | Botón floral a antesis (R1–R4) | **38 – 65 %** | Hall et al. (2010), *Field Crops Research* 116(1-2):70–81, Table 2 (pág. 75). Aborto masivo de flores tubulosas y falla en cuajado de aquenios. |

*(Cualquier otra combinación de días o fenología sin ensayo medido devuelve `null` + "Sin ensayo agronómico publicado para esa condición").*

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
   - [ ] Tests de rango de merma para Soja, Maíz, Trigo y Girasol sin números mágicos hardcodeados sin cita bibliográfica.
   - [ ] Rango devuelto siempre como tupla `(min_pct, max_pct)`.
3. **Interfaz:**
   - [ ] Capa de visualización "Días de anegamiento" en el visor con paleta discreta (1 día, 2 días, 3-4 días, $\ge 5$ días).
   - [ ] Resultados disponibles para Rotaterra en `GET /api/v1/fields/{id}/observaciones` (spec 011).
   - [ ] Sin incremento en el presupuesto de botones de la primera pantalla.
