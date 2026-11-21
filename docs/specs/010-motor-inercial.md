# Spec 010: Formulación Inercial Local 2D (Bates 2010 / de Almeida 2012)

**Estado:** Aprobada e implementada  
**Fecha:** 21/11/2026  
**Rama:** `feat/motor-inercial`  
**Referencias científicas:**
1. Bates, P. D., Horritt, M. S., & Fewtrell, T. J. (2010). *A simple inertial formulation of the shallow water equations for efficient two-dimensional flood inundation modelling*. Journal of Hydrology, 387(1-2), 33-45.
2. de Almeida, G. A., Bates, P., Freer, J. E., & Souvignet, M. (2012). *Improving the stability of a simple formulation of the 1D and 2D shallow water equations*. Water Resources Research, 48(5), W05528.
3. Adams, J. M., Gasparini, N. M., Hobley, D. E. J., Tucker, G. E., Hutton, E. W. H., Nudurupati, S. S., & Istanbulluoglu, E. (2017). *The Landlab v1. 0 OverlandFlow component: a Python library for computing shallow water flow over topography*. Geoscientific Model Development, 10(4), 1645-1663.

---

## 1. Justificación y Motivación

En el benchmark inicial de validación hidrodinámica (`docs/benchmarks/landlab.md`), el solver de onda difusiva 2D centrado en celdas (D8) de RotaTerra mostró coincidencia volumétrica estricta con Landlab `OverlandFlow` (diferencia de volumen final almacenado de apenas 1,18% en la Parcela 205 de San Luis). No obstante, en área anegada ($h \ge 2\text{ cm}$) sobre relieve real de baja pendiente, la onda difusiva pura difirió en un 45,0% (2,07 ha frente a 3,77 ha).

### Causas físicas y numéricas identificadas:
1. **Ausencia del término inercial local $\partial q / \partial t$:** En la onda difusiva, la velocidad se equilibra de forma instantánea con el gradiente de energía ($v \propto S_f^{1/2}$), sin considerar la inercia del fluido al acelerar o desacelerar. En terrenos casi planos con microrugosidades, esto provoca un drenaje prematuro de láminas delgadas superficiales (2 a 3 cm).
2. **Topología de enlace (links ortogonales escalonados vs D8 centrado en celdas):** Landlab resuelve el flujo en las caras o enlaces ortogonales entre celdas (malla escalonada tipo Arakawa-C), lo que permite dispersión bidimensional continua en $X$ e $Y$ sin preferenciar artificialmente diagonales de máxima pendiente.
3. **Ponderación espacial estabilizadora (de Almeida et al. 2012):** La formulación de de Almeida et al. (2012) introduce un factor $\theta \in [0.7, 0.9]$ (típicamente $\theta = 0.8$) en el término inercial que promedia el caudal con los enlaces paralelos vecinos, amortiguando oscilaciones espaciales en frentes de onda lentos sobre suelo rugoso.

Para alcanzar el criterio de convergencia con la literatura ($< 15\%$ de discrepancia en área en todos los casos de prueba, alcanzando $2,50\%$ en Parcela 205) manteniendo total soberanía de código (cero dependencias externas pesadas en producción y ejecución Numba ultrarrápida), se implementa la formulación inercial local nativa.

---

## 2. Ecuaciones Gobernantes

El modelo simplifica las ecuaciones bidimensionales completas de Saint-Venant (aguas someras) despreciando únicamente los términos de aceleración convectiva advectiva ($\mathbf{u} \cdot \nabla \mathbf{u}$), reteniendo la aceleración local, el gradiente de superficie libre del agua y la fricción por fondo según Manning.

### 2.1 Ecuación de momento en enlaces (Links)
Para cada enlace ortogonal (horizontal en $X$ o vertical en $Y$) que conecta dos celdas adyacentes:

$$q^{t+\Delta t} = \frac{q_{\text{mean}} - g \, h_{\text{flow}} \, \Delta t \, S_w}{1 + g \, \Delta t \, n^2 \, \frac{|q|}{h_{\text{flow}}^{7/3}}}$$

donde:
- $q$: caudal específico por unidad de ancho en el enlace [$\text{m}^2/\text{s}$].
- $g$: aceleración de la gravedad ($9.80665\text{ m}/\text{s}^2$).
- $\Delta t$: sub-paso temporal adaptativo [$\text{s}$].
- $n$: rugosidad de Manning de la celda [$\text{s}/\text{m}^{1/3}$].
- $S_w$: pendiente de la superficie libre del agua entre las dos celdas conectadas:
  $$S_{w, x} = \frac{\eta(r, c+1) - \eta(r, c)}{\Delta x}, \quad \eta = z + h$$
- $h_{\text{flow}}$: profundidad efectiva de paso de flujo en el enlace, evaluada según Bates et al. (2010):
  $$h_{\text{flow}} = \max\left( \max(\eta_{\text{tail}}, \eta_{\text{head}}) - \max(z_{\text{tail}}, z_{\text{head}}), \, h_{\text{init}} \right)$$
  con $h_{\text{init}} = 10^{-5}\text{ m}$. Si $h_{\text{flow}} \le h_{\text{init}}$, el enlace se considera seco y $q = 0$.

### 2.2 Ponderación espacial de de Almeida et al. (2012)
Para evitar inestabilidades en frentes de avance sobre terreno irregular con fricción alta:

$$q_{\text{mean}, x}(r, c) = \theta \, q_x(r, c) + \frac{1 - \theta}{2} \left[ q_x(r-1, c) + q_x(r+1, c) \right]$$

$$q_{\text{mean}, y}(r, c) = \theta \, q_y(r, c) + \frac{1 - \theta}{2} \left[ q_y(r, c-1) + q_y(r, c+1) \right]$$

con $\theta = 0.8$ en el interior del dominio. En los bordes donde falta un enlace paralelo vecino, se pondera con el enlace disponible:
$$q_{\text{mean}} = \theta \, q + (1 - \theta) \, q_{\text{vecino}}$$

### 2.3 Limitadores de flujo para estabilidad física
Para garantizar monotonicidad y evitar oscilaciones en frentes secos/húmedos o inversiones de lámina en un solo sub-paso:
1. **Limitador de Froude ($Fr \le 1.0$):**
   $$|q| \le h_{\text{flow}} \sqrt{g \, h_{\text{flow}}}$$
2. **Limitador de Courant en enlaces:**
   $$|q| \le \frac{\Delta x}{\Delta t} \frac{h_{\text{flow}}}{4}$$

### 2.4 Ecuación de conservación de masa en nodos (Celdas)
En cada celda centrada $(r, c)$, la profundidad física $h$ se actualiza a partir de la divergencia de caudales en sus 4 caras ortogonales y la tasa de lluvia neta efectiva $R$ [$\text{m}/\text{s}$]:

$$\Delta h(r, c) = R \, \Delta t - \frac{\Delta t}{\Delta x} \left[ q_x(r, c) - q_x(r, c-1) \right] - \frac{\Delta t}{\Delta y} \left[ q_y(r, c) - q_y(r-1, c) \right]$$

$$h^{t+\Delta t}(r, c) = \max\left(0, \, h^t(r, c) + \Delta h(r, c)\right)$$

### 2.5 Criterio de estabilidad y paso temporal adaptativo CFL
El sub-paso temporal $\Delta t$ se calcula dinámicamente según la condición Courant-Friedrichs-Lewy para ondas de gravedad en aguas someras (Bates et al. 2010):

$$\Delta t = \min\left( \alpha \frac{\Delta x}{\sqrt{g \, \max(h, h_{\text{init}})}}, \, \Delta t_{\text{max}}, \, \Delta t_{\text{intervalo}} \right)$$

con $\alpha = 0.7$ y $\Delta t_{\text{max}} = 10.0\text{ s}$.

---

## 3. Condiciones de Borde

1. **Borde cerrado (cuenca endorreica o lote con terraplén perimetral):**
   Los caudales en enlaces perimetrales exteriores se anulan idénticamente:
   $$q_x(r, 0) = 0, \quad q_x(r, W-1) = 0, \quad q_y(0, c) = 0, \quad q_y(H-1, c) = 0$$
2. **Borde abierto (drenaje libre hacia el exterior):**
   Los enlaces perimetrales permiten evacuar caudal hacia el exterior según la pendiente hidráulica saliente, registrando el volumen exportado en `domain_boundary_outflow_m3`.

---

## 4. Resultados del Benchmark contra Landlab OverlandFlow

Evaluado sobre las mismas grillas y forzantes NRCS-CN que `geoprocessing/benchmarks/landlab_vs_motor.py`:

| Caso de prueba | Grilla / Escala | Landlab OverlandFlow | Motor Inercial Nativo | Diferencia Área (%) | Diferencia Vol (%) | Estado (<15%) |
|---|---|---|---|---|---|---|
| **1. Plano inclinado** | $30 \times 30$, $\Delta x = 10\text{ m}$ (7,84 ha int.) | 6,440 ha / 429,1 m³ | 6,460 ha / 435,1 m³ | **0,31%** | **1,37%** | ✅ CUMPLE |
| **2. Bajo cerrado** | $30 \times 30$, $\Delta x = 10\text{ m}$ (7,84 ha int.) | 6,280 ha / 527,6 m³ | 5,720 ha / 564,3 m³ | **8,92%** | **6,51%** | ✅ CUMPLE |
| **3. Parcela 205 (San Luis)** | $86 \times 58$, $\Delta x = 30,7\text{ m}$ (443,3 ha int.) | 3,770 ha / 15.946,2 m³ | 3,676 ha / 15.950,5 m³ | **2,50%** | **0,03%** | ✅ CUMPLE |

**Conclusión:** La formulación inercial reduce la discrepancia en relieve real de 45,0% a apenas **2,50%** en área y **0,03%** en volumen, cumpliendo con holgura el criterio de equivalencia científica estipulado.
