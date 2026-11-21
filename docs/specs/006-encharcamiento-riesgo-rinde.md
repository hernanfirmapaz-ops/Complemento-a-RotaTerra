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
   - Obtenida a partir de la textura USDA real reportada por SoilGrids 2.0 (Spec 004) según la tabla de Rawls et al. (1982):
     - Arenosa: $5040\text{ mm/día}$ (21,0 cm/h)
     - Arenosa franca: $1466\text{ mm/día}$ (6,11 cm/h)
     - Franco arenosa (ej. Villa Mercedes): $622\text{ mm/día}$ (2,59 cm/h)
     - Franca: $317\text{ mm/día}$ (1,32 cm/h)
     - Franco limosa: $163\text{ mm/día}$ (0,68 cm/h)
     - Franco arcillo arenosa: $103\text{ mm/día}$ (0,43 cm/h)
     - Franco arcillosa: $55\text{ mm/día}$ (0,23 cm/h)
     - Franco arcillo limosa: $36\text{ mm/día}$ (0,15 cm/h)
     - Arcillo arenosa: $29\text{ mm/día}$ (0,12 cm/h)
     - Arcillo limosa: $22\text{ mm/día}$ (0,09 cm/h)
     - Arcillosa: $14\text{ mm/día}$ (0,06 cm/h)
   - **Corrección (21/11/2026):** la versión anterior de esta tabla tenía valores unas 10 veces menores que los de Rawls et al. (1982), y 24 veces menor en arena. Los valores de arriba convierten la tabla original (cm/h × 240 = mm/día). Verificar contra la publicación antes de programar.
   - **Límite:** la Ksat de textura es la del suelo sin costra ni compactación. En bajos con napa somera la infiltración real es casi nula; el vaciado lo domina la evaporación y la napa (ver spec 001, modo estacional).
   - Si no hay textura real disponible, se usa el valor conservador por defecto ($10\text{ mm/día}$) con la etiqueta `"Suelo por omisión, sin confirmar"`.
2. **$ET_0$ (Evapotranspiración diaria de referencia):**
   - Obtenida del promedio del mes del evento según FAO-56 Penman-Monteith (NASA POWER climatológica ya implementada en el módulo de balance hídrico). Típicamente $3\text{ a }7\text{ mm/día}$ en verano pampeano.
3. **Cálculo de días:**

$$D_{\text{encharcamiento}} = \frac{h_{\text{remanente}} \times 1000}{\Delta h_{\text{día}}}$$

- El valor se redondea hacia arriba en días enteros para cada celda ($1, 2, 3, \dots, > 7\text{ días}$).
- Se verifica conservación estricta de balance de masa: $\sum \text{Volumen infiltrado} + \sum \text{Volumen evaporado} = \text{Volumen almacenado inicial}$.

---

## 3. Riesgo de Pérdida de Rinde por Cultivo (Tarea 3.3)

Conforme a la **Regla 4 del proyecto** (*"Nunca inventar un valor ni emitir una cifra única engañosa"*), la merma de rinde se presenta siempre en **rangos de incertidumbre** y con la fuente técnica a la vista.

### 3.1 Tablas de referencia agronómica

> **Bloqueada hasta verificar (pedido del 21/11/2026, tarea A2):** la atribución original ("INTA Marcos Juárez / Oliverio et al. 2018 / USDA-ARS") no pudo confirmarse, y el orden de tolerancia del maíz contradice material técnico del INTA. Cada valor necesita su cita exacta; los que no la tengan se eliminan.

| Cultivo | Días con agua ($h > 1\text{ cm}$) | Merma estimada en floración/reproductivo (Rango) | Merma estimada en vegetativo temprano (Rango) | Tolerancia relativa |
|---|---|---|---|---|
| **Soja** | 1 – 2 días | **5 – 15 %** | **0 – 10 %** | Moderada |
| | 3 – 4 días | **20 – 45 %** | **15 – 30 %** | |
| | $\ge 5$ días | **50 – 100 %** | **40 – 80 %** | (Muerte de plántula / clorosis) |
| **Maíz** | 1 – 2 días | **10 – 25 %** | **5 – 15 %** | Sensible |
| | 3 – 4 días | **35 – 65 %** | **25 – 50 %** | |
| | $\ge 5$ días | **70 – 100 %** | **60 – 100 %** | (Muerte radicular severa) |
| **Trigo** | 1 – 3 días | **5 – 15 %** | **0 – 5 %** | Mayor tolerancia en frío |
| | 4 – 6 días | **20 – 40 %** | **10 – 25 %** | |
| | $\ge 7$ días | **45 – 80 %** | **30 – 60 %** | |
| **Girasol** | 1 – 2 días | **15 – 35 %** | **10 – 25 %** | Muy sensible a la hipoxia |
| | $\ge 3$ días | **50 – 100 %** | **40 – 90 %** | |

### 3.2 Parámetros editables
El usuario en la interfaz debe poder:
- Seleccionar el cultivo (Soja, Maíz, Trigo, Girasol).
- Modificar los umbrales de días o mermas porcentuales si cuenta con ensayos de su zona o híbridos/variedades con tolerancia específica.

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
