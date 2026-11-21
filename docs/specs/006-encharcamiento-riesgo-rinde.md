# Spec 006 · Días de Encharcamiento, Riesgo de Rinde e Impacto Económico

**Proyecto:** `Complemento-a-RotaTerra`  
**Etapa:** 3 (Plan de Trabajo 20/11/2026, tareas 3.2, 3.3, 3.4)  
**Mejoras que cubre:** R1 (Días de anegamiento y vaciado), R2 (Riesgo agronómico y económico de rinde)  
**Dependencias:** Spec 001 (Escurrimiento 2D), Spec 004 (Suelos reales / $K_{sat}$ Rawls 1982), Spec 005 (WhiteboxTools / dos grillas).

---

## 1. Problema Agronómico y Objetivo

Una simulación hidrodinámica 2D entrega láminas de agua máximas instantáneas ($h_{\text{max}}$) y láminas remanentes inmediatas tras el evento de lluvia ($h_{\text{remanente}}$). Sin embargo, el productor y el asesor técnico no toman decisiones por "centímetros de agua acumulada", sino por **cuántos días permanecerá el agua sobre el cultivo** y **cuánto rinde se perderá por asfixia radicular (anoxia)**.

El objetivo de esta spec es:
1. Calcular el **mapa de días de permanencia del agua** para cada bajo o cubeta del lote mediante un balance de vaciado físico (infiltración de fondo saturada + evapotranspiración diaria).
2. Estimar el **riesgo agronómico de rinde** expresado en **rangos de merma porcentual** según cultivo, fenología y días de anegamiento (basado en literatura agronómica de INTA y USDA).
3. Traducir el riesgo a un **impacto económico estimado en rango** ($\text{ha} \times \text{rinde} \times \text{precio}$), con parámetros editables por el usuario.

---

## 2. Modelo Físico de Vaciado de Bajos (Tarea 3.2)

Una celda encharcada ($h > 0.01\text{ m}$) pierde agua a través de dos mecanismos físicos simultáneos:

$$\Delta h_{\text{día}} = K_{\text{sat, efectivo}} + ET_0$$

Donde:
1. **$K_{\text{sat, efectivo}}$ (Conductividad hidráulica saturada de fondo):**
   - Obtenida a partir de la textura USDA real reportada por SoilGrids 2.0 (Spec 004) según la tabla de Rawls et al. (1982):
     - Arena: $210\text{ mm/día}$
     - Franco arenosa (ej. Villa Mercedes): $62\text{ mm/día}$
     - Franco: $31\text{ mm/día}$
     - Franco limosa: $16\text{ mm/día}$
     - Franco arcillo arenosa: $10\text{ mm/día}$
     - Franco arcillosa: $5,5\text{ mm/día}$
     - Franco arcillo limosa: $3,6\text{ mm/día}$
     - Arcillosa: $1,4\text{ mm/día}$
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

### 3.1 Tablas de referencia agronómica (INTA Marcos Juárez / Oliverio et al. 2018 / USDA-ARS)

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

## 4. Impacto Económico en Rango (Tarea 3.4)

El impacto económico estimado calcula las pérdidas potenciales sobre la superficie afectada:

$$\text{Pérdida Mínima (USD)} = \sum_{z} \text{ha}_z \times \text{Rinde Base (t/ha)} \times \text{Merma Mínima}_z \times \text{Precio Pizarra (USD/t)}$$

$$\text{Pérdida Máxima (USD)} = \sum_{z} \text{ha}_z \times \text{Rinde Base (t/ha)} \times \text{Merma Máxima}_z \times \text{Precio Pizarra (USD/t)}$$

- **Valores por omisión pampeanos orientativos:**
  - Soja: Rinde base $3,0\text{ t/ha}$, Precio pizarra $280\text{ USD/t}$.
  - Maíz: Rinde base $8,0\text{ t/ha}$, Precio pizarra $160\text{ USD/t}$.
  - Trigo: Rinde base $3,5\text{ t/ha}$, Precio pizarra $210\text{ USD/t}$.
- **Edición en pantalla:** El productor puede editar en tiempo real el rinde proyectado de su lote y el precio esperado para que el cálculo refleje su costo de oportunidad real.
- **Formato de visualización:** Nunca una cifra aislada. Ejemplo visible:  
  *Pérdida estimada en bajos:* **USD 3.200 a USD 6.400** (sobre 8,4 ha afectadas con > 2 días de anegamiento).

---

## 5. Criterios de Aceptación Técnicos

1. **Balance de vaciado:**
   - [ ] Test unitario que valida que el vaciado por infiltración y $ET_0$ consume exactamente el volumen almacenado ($h_{\text{final}} \to 0$).
   - [ ] Cálculo de días determinístico y sin división por cero cuando la infiltración es muy baja.
2. **Estimación agronómica:**
   - [ ] Tests de rango de merma para Soja, Maíz, Trigo y Girasol sin números mágicos hardcodeados sin cita bibliográfica.
   - [ ] Rango devuelto siempre como tupla `(min_pct, max_pct)` y `(min_usd, max_usd)`.
3. **Interfaz:**
   - [ ] Capa de visualización "Días de anegamiento" en el visor con paleta discreta (1 día, 2 días, 3-4 días, $\ge 5$ días).
   - [ ] Tarjeta de resumen económico editable en Paso 3 (Resultado).
   - [ ] Sin incremento en el presupuesto de botones de la primera pantalla.
