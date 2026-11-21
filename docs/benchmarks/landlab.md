# Benchmark Comparativo: Motor 2D de RotaTerra vs Landlab OverlandFlow

**Fecha:** 21/11/2026  
**Autores / Agentes:** Antigravity (Hidrólogo + Coordinador)  
**Referencia teórica:** Bates et al. (2010) (*J. Hydrol.*), de Almeida et al. (2012) (*Water Resources Research*), Chow (1959), NRCS NEH-4.  
**Script reproducible:** `geoprocessing/benchmarks/landlab_vs_motor.py`  
**Especificación técnica:** `docs/specs/010-motor-inercial.md`  

---

## 1. Objetivo y Metodología

Evaluar la física del solver hidrodinámico 2D de RotaTerra contrastándolo directamente con el componente estándar de la comunidad científica **Landlab `OverlandFlow`** (de Almeida et al. 2012, aproximación inercial de aguas someras en grilla escalonada de enlaces).

Para resolver las diferencias de dispersión lateral observadas en la onda difusiva pura inicial, RotaTerra implementó la formulación local inercial 2D (Bates 2010 / de Almeida 2012) sobre una grilla escalonada Arakawa-C con paso de tiempo adaptativo CFL, limitador de Froude ($Fr \le 1.0$), limitador de Courant y parámetro de difusión transversal $\theta = 0.85$.

### Condiciones experimentales idénticas
1. **Manning $n$:** $0.08$ (superficie agrícola típica con rastrojo/pastura).
2. **Forzante de lluvia efectiva:** idéntica lámina neta $\Delta Q$ generada por el método NRCS-CN distribuida uniformemente en el tiempo, con un evento de tormenta de 15 minutos seguido de 15 minutos de recesión libre ($T_{\text{total}} = 30$ min = 1.800 s).
3. **Umbral de anegamiento:** lámina de agua persistente $h \ge 0.02\text{ m}$ (2 cm).
4. **Dominio evaluado:** celdas interiores del dominio (`inner_mask`), excluyendo el perímetro exterior de 1 celda para desacoplar divergencias de condiciones de borde.
5. **Criterio de aceptación:** Discrepancia en área anegada $< 15\%$ en todos los casos de prueba.

---

## 2. Tabla Comparativa de Resultados

| Caso de prueba | Grilla y resolución | Motor 2D RotaTerra (Área / Prof / Vol) | Landlab OverlandFlow (Área / Prof / Vol) | Dif. Área (%) | Dif. Vol (%) | Criterio (<15%) |
|---|---|---|---|---|---|---|
| **1. Plano inclinado** (pendiente 0,5%) | $30 \times 30$, $\Delta x = 10\text{ m}$ (7,84 ha int.) | **0,000 ha** / 0,0067 m / 429,3 m³ | **0,000 ha** / 0,0067 m / 429,1 m³ | **0,00%** | **0,04%** | ✅ Cumple |
| **2. Bajo cerrado sintético** | $30 \times 30$, $\Delta x = 10\text{ m}$ (7,84 ha int.) | **0,160 ha** / 0,0629 m / 526,8 m³ | **0,160 ha** / 0,0635 m / 527,6 m³ | **0,00%** | **0,15%** | ✅ Cumple |
| **3. Parcela 205 (San Luis)** | $86 \times 58$, $\Delta x = 30,7\text{ m}$ (443,3 ha int.) | **3,487 ha** / 0,0467 m / 15.917,9 m³ | **3,770 ha** / 0,0479 m / 15.946,2 m³ | **7,50%** | **0,18%** | ✅ Cumple |

---

## 3. Análisis Físico y Numérico de la Validación

### Concordancias destacadas
- **Conservación volumétrica rigurosa:** En los tres casos, la diferencia en el volumen final almacenado es inferior al $0.20\%$ (en la Parcela 205 es de apenas **0,18%**: 15.917,9 m³ vs 15.946,2 m³).
- **Exactitud en bajos cerrados:** Coincidencia del **0,00%** en área anegada en el bajo cerrado, con exactamente 16 celdas idénticas (0,16 ha) identificadas por ambos códigos.
- **Relieve real validado:** En el relieve real de la Parcela 205 (443 ha con microtopografía y drenajes naturales), la discrepancia se redujo del 45,0% (difusivo previo) al **7,50%**, cumpliendo con holgura el umbral de aceptación del 15%.

### Conclusión
El motor hidrodinámico 2D de RotaTerra (`solver_mode="inertial"`) replica con fidelidad cuantitativa el modelo de referencia Landlab `OverlandFlow` tanto en volúmenes almacenados como en áreas de anegamiento superficial, operando con aceleración JIT Numba y tiempo de cómputo en torno a 1 segundo para lotes productivos estándar.
