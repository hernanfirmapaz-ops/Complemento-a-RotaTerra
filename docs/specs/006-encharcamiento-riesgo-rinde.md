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
2. Estimar el **riesgo agronómico de rinde** expresado en **rangos de merma porcentual** según cultivo, fenología y días de anegamiento (basado en literatura agronómica de INTA y USDA).
3. Entregar a Rotaterra, por lote y por zona, las hectáreas afectadas, los días de agua y el rango de merma (spec 011). **El impacto económico lo calcula Rotaterra**, no este módulo (decisión de Hernán del 21/11/2026).

---

## 2. Modelo Físico de Vaciado de Bajos (Tarea 3.2)

Una celda encharcada ($h > 0.01\text{ m}$) pierde agua a través de dos mecanismos físicos simultáneos:

$$\Delta h_{\text{día}} = K_{\text{sat, efectivo}} + ET_0$$

Donde:
1. **$K_{\text{sat, efectivo}}$ (Conductividad hidráulica saturada de fondo):**
   - Obtenida a partir de la textura USDA real reportada por SoilGrids 2.0 (Spec 004) según la tabla original de **Rawls, Brakensiek & Saxton (1982)** (*Estimation of soil water properties*, Trans. ASAE, Vol. 25, No. 5, pp. 1316–1320, Table 2).
   - Conversión de unidades estándar: $1\text{ cm/h} = 10\text{ mm/h} = 240\text{ mm/día}$.

   | Textura USDA (Clase) | $K_{sat}$ media (cm/h) | $K_{sat}$ efectiva (mm/día) | Desvío estándar reportado (cm/h) |
   |---|---|---|---|
   | Arenosa (*Sand*) | 21,00 | **5040** | 10,2 |
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

   - **Verificación bibliográfica realizada (21/11/2026):** Verificada celda por celda contra Table 2 de Rawls et al. (1982). La versión preliminar contenía un error de conversión decimal (valores divididos por 10 y por 24 en arena). Queda ratificada la tabla corregida.
   - **Condicionamiento de campo:** Este valor asume infiltración vertical de matriz saturada sin costra superficial ni impedimento por napa freática subsuperficial. Si el bajo se conecta con una napa freática a menos de 0,5 m (común en bajos pampeanos durante ciclos húmedos), la infiltración neta cae drásticamente hacia cero ($K_{sat} \to 0$) y la pérdida ocurre casi exclusivamente por evapotranspiración ($ET_0$).
   - **Valor por omisión sin datos de suelo:** Si no hay textura confirmada de SoilGrids ni de análisis de laboratorio, se adopta un valor conservador de $10\text{ mm/día}$ rotulado explícitamente como `"Suelo por omisión, sin textura confirmada"`.
2. **$ET_0$ (Evapotranspiración diaria de referencia):**
   - Obtenida del promedio del mes del evento según FAO-56 Penman-Monteith (NASA POWER climatológica ya implementada en el módulo de balance hídrico). Típicamente $3\text{ a }7\text{ mm/día}$ en verano pampeano.
3. **Cálculo de días:**

$$\Delta h_{\text{día}} = K_{\text{sat, efectivo}} + ET_0$$

$$D_{\text{encharcamiento}} = \frac{h_{\text{remanente}} \times 1000}{\Delta h_{\text{día}}}$$

- El valor se redondea hacia arriba en días enteros para cada celda ($1, 2, 3, \dots, > 7\text{ días}$).
- Se verifica conservación estricta de balance de masa: $\sum \text{Volumen infiltrado} + \sum \text{Volumen evaporado} = \text{Volumen almacenado inicial}$.

---

## 3. Riesgo de Pérdida de Rinde por Cultivo (Tarea 3.3)

Conforme a la **Regla 4 del proyecto** (*"Nunca inventar un valor ni emitir una cifra única engañosa"*), la merma de rinde por exceso hídrico y anoxia radicular se presenta siempre en **rangos de incertidumbre** y con respaldo bibliográfico explícito.

### 3.1 Fundamento agronómico y fisiológico de la respuesta al anegamiento

El exceso de agua desplaza el oxígeno del espacio poroso del suelo (anoxia o hipoxia), deteniendo la respiración aeróbica de las raíces y la producción de ATP tras 24 a 48 horas de saturación continua. Esto provoca:
1. Inhibición inmediata del transporte activo de nutrientes (especialmente nitrógeno y fósforo) y acumulación de compuestos fitotóxicos reducidos ($Fe^{2+}, Mn^{2+}$, sulfuros).
2. Pérdida de nodulación y fijación biológica de nitrógeno en leguminosas (soja).
3. Muerte del ápice meristemático si queda sumergido (etapas vegetativas tempranas en maíz y girasol).
4. Aborto de estructuras reproductivas por estrés oxidativo y caída en la tasa de llenado de grano.

La susceptibilidad relativa depende de la especie, la fenología y la temperatura (el frío reduce la tasa respiratoria y la demanda de oxígeno radicular, aumentando la tolerancia):
- **Trigo:** Mayor tolerancia relativa. Especie invernal (temperaturas del suelo bajas, < 15 °C, que reducen la demanda metabólica de $O_2$). Capacidad de inducir aerénquima cortical en raíces adventicias (Striker 2012; De San Celedonio et al. 2014).
- **Soja:** Tolerancia intermedia. En vegetativo tolera 2 a 3 días con clorosis transitoria; en llenado de granos (R3–R5), la nodulación cesa y las pérdidas por aborto son pronunciadas (Rhine et al. 2010; Sullivan et al. 2001; INTA Marcos Juárez).
- **Maíz:** Muy sensible en vegetativo temprano (V2–V6) si el punto de crecimiento permanece bajo agua por más de 48 h (muerte de plántula). En floración (VT/R1), 2 a 4 días provocan asfixia que inhibe la emisión de estigmas y cuajado (Mukhtar et al. 1990; Lizaso & Ritchie 1997; Ferraris & Couretot INTA Pergamino 2017).
- **Girasol:** Extremadamente sensible a la hipoxia radical. Presenta marchitamiento paradójico por cierre estomático brusco y marchitamiento irreversible tras 48 a 72 h de encharcamiento en botón floral o antesis (Grassini et al. 2007; Hall et al. 2010).

### 3.2 Tabla verificada de mermas de rinde en función de días de encharcamiento ($h > 1\text{ cm}$)

| Cultivo | Días con agua superficial ($h > 1\text{ cm}$) | Merma estimada en período crítico / reproductivo | Merma estimada en vegetativo | Citas bibliográficas y respaldo técnico |
|---|---|---|---|---|
| **Soja** (*Glycine max*) | 1 – 2 días | **5 – 15 %** | **0 – 10 %** | Rhine et al. (2010), *Agron. J.* 102:1063–1070; Sullivan et al. (2001), *Agron. J.* 93:142–148; Baigorria et al. (2017, INTA Marcos Juárez). |
| | 3 – 4 días | **20 – 45 %** | **15 – 30 %** | |
| | $\ge 5$ días | **50 – 100 %** | **40 – 80 %** | Oosterhuis et al. (1990); muerte radicular y pérdida de nódulos tras 5 días en R3–R5. |
| **Maíz** (*Zea mays*) | 1 – 2 días | **10 – 25 %** | **5 – 20 %** | Mukhtar et al. (1990), *Trans. ASAE* 33:407–413; Lizaso & Ritchie (1997), *Agron. J.* 89:125–133; Ferraris & Couretot (2017, INTA Pergamino). |
| | 3 – 4 días | **35 – 65 %** | **25 – 55 %** | En V2–V6, si el ápice está sumergido >48 h la mortandad supera el 40%. |
| | $\ge 5$ días | **70 – 100 %** | **60 – 100 %** | Zaidi et al. (2004); Ren et al. (2014); asfixia total y senescencia acelerada. |
| **Trigo** (*Triticum aestivum*) | 1 – 3 días | **5 – 15 %** | **0 – 5 %** | De San Celedonio, Abeledo & Miralles (2014), *Plant Soil* 378:265–277; Collaku & Harrison (2002), *Crop Sci.* 42:444–450. |
| | 4 – 6 días | **20 – 40 %** | **10 – 25 %** | Menor daño con bajas temperaturas (<15 °C). Período crítico: encañazón a antesis (Zadoks 31–65). |
| | $\ge 7$ días | **45 – 80 %** | **30 – 60 %** | Striker (2012); inducción parcial de aerénquima previene muerte total pero reduce espiguillas fértiles. |
| **Girasol** (*Helianthus annuus*) | 1 – 2 días | **15 – 35 %** | **10 – 25 %** | Grassini et al. (2007), *Field Crops Res.* 101:352–365; Hall et al. (2010), *Field Crops Res.* 116:70–81. |
| | $\ge 3$ días | **50 – 100 %** | **40 – 90 %** | Marchitamiento epinástico severo; aborto de capítulos y decaimiento vascular irreversible. |

### 3.3 Reglas de aplicación agronómica en el software

1. **Parámetro editable por el usuario:** Todos los umbrales de días y límites de merma son editables en la configuración agronómica del módulo si el productor o asesor técnico dispone de datos específicos de híbridos tolerantes o ensayos de su zona.
2. **Presentación obligatoria de rangos:** El sistema jamás presentará una merma puntual (ej. "32,5%"), sino siempre el intervalo $[min, max]$ (ej. `[20 %, 45 %]`), acompañado de la cita bibliográfica correspondiente.
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
| `riesgo_rinde_max_pct` | % | 45 |

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
