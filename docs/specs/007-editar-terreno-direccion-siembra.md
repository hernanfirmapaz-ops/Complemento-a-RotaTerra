# Spec 007 · Edición de Terreno, Dirección de Siembra y Puntos de Desborde

**Proyecto:** `Complemento-a-RotaTerra`  
**Etapa:** 3 (Plan de Trabajo 20/11/2026, tareas 3.5, 3.6, 3.7)  
**Mejoras que cubre:** S2 (Micro-obras y edición de terreno), S1 (Puntos de desborde de bajos), S3 (Dirección de siembra)  
**Dependencias:** Spec 001 (Motor 2D), Spec 003 (Comparador lado a lado), Spec 005 (WhiteboxTools / Grilla de solera `z_bed`).

---

## 1. Problema y Propuesta de Valor ("Si hago esta zanja, salvo X ha")

El valor más concreto para un productor agropecuario es simular intervenciones antes de mover tierra:
- *"¿Dónde me conviene trazar una zanja de alivio para desagotar este bajo hacia el canal?"*
- *"¿Hacia dónde va a desbordar esta laguna si llueven 80 mm más?"*
- *"¿Qué diferencia hace sembrar a favor de la pendiente vs. cruzado / en contorno?"*

Esta spec define los modelos matemáticos y la interfaz para:
1. **Editar el terreno localmente** trazando micro-obras (zanjas, terraplenes, bordos, alcantarillas) sobre la grilla `z_bed` y correr la simulación comparativa de inmediato.
2. **Modelar la anisotropía del flujo según la dirección de siembra** (surcos paralelos vs perpendiculares a la pendiente).
3. **Calcular la cota de rebalse y punto de desborde (*spill point*)** de cada depresión topográfica.

---

## 2. Edición Interactiva de Micro-Obras (Tarea 3.5)

### 2.1 Tipos de intervención sobre la grilla topográfica `z_bed`
Las intervenciones se aplican sobre una copia editable de `z_bed` (manteniendo el DEM satelital original intacto como referencia base):

| Tipo de obra | Geometría de entrada | Parámetros | Modificación en la grilla (`z_bed`, $n$) |
|---|---|---|---|
| **Zanja / Canal de drenaje** | `LineString` (trazado por el usuario) | Ancho $w$ (m, def: 2m), profundidad $d$ (m, def: 0,40m), talud | Rebaje controlado: $z_{\text{celda}} \leftarrow \min(z_{\text{celda}}, z_{\text{solera}})$. Asigna rugosidad de canal: $n = 0,025$ |
| **Bordo / Terraplén / Camino** | `LineString` | Ancho $w$ (m, def: 4m), sobreelevación $h$ (m, def: 0,35m) | Elevación local: $z_{\text{celda}} \leftarrow z_{\text{celda}} + h$. Barrera al flujo laminar |
| **Alcantarilla / Cruce de camino** | `Point` (par de celdas conectadas) | Diámetro $\phi$ (m, def: 0,60m) o cota solera | Conexión hidráulica directa en el solver entre las dos celdas separadas por el bordo |

### 2.2 Flujo comparativo ("Antes vs Después")
1. El usuario dibuja una o más obras sobre el mapa/visor 3D.
2. Presiona "Simular con obra".
3. El comparador de escenarios (Spec 003) muestra en pantalla dividida:
   - **Lado A (Sin obra):** Área anegada original, lámina máxima y volumen retenido.
   - **Lado B (Con obra):** Área anegada reducida, volumen drenado y **hectáreas salvadas ($\Delta \text{ha}$)**.

---

## 3. Dirección de Siembra y Micro-Relieve de Surcos (Tarea 3.6)

En siembra directa, los surcos de siembra (con espaciamientos típicos de 35 cm, 42 cm o 52 cm para soja/maíz y 17,5 cm para trigo) generan un micro-bordo de 3 a 8 cm de desnivel relativo. Este micro-relieve produce **anisotropía hidráulica**:
- El agua fluye con facilidad a lo largo de los entresurcos.
- El flujo perpendicular a la siembra queda embalsado en micro-terrazas sucesivas hasta superar la cresta del camellón.

### 3.1 Modelo de anisotropía por ángulo de flujo vs azimut de siembra
Sea $\alpha_{\text{siembra}}$ el ángulo azimut de las líneas de siembra (0° a 360°, editable por el usuario o trazado en pantalla):
Para cada dirección de flujo $k$ (entre la celda y su vecina D8 con azimut $\theta_k$):

$$\Delta \theta_k = |\theta_k - \alpha_{\text{siembra}}| \pmod{180^\circ}$$

La rugosidad efectiva de Manning $n_{\text{eff}, k}$ en esa dirección se modula según:

$$n_{\text{eff}, k} = n_{\text{base}} \times \left(1.0 + \beta \times \sin^2(\Delta \theta_k)\right)$$

Donde:
- $\Delta \theta_k \approx 0^\circ$ (flujo paralelo al surco): $n_{\text{eff}} = n_{\text{base}}$ (resistencia normal, escurrimiento libre por el entresurco).
- $\Delta \theta_k \approx 90^\circ$ (flujo cruzado perpendicular): $n_{\text{eff}} = n_{\text{base}} \times (1.0 + \beta)$ con $\beta \approx 1,0 \text{ a } 1,5$ (resistencia duplicada por choque contra los camellones de siembra).
- Para pendientes bajas ($< 0,5\%$), el camellón retiene una micro-lámina adicional de $1\text{ a }2\text{ cm}$ antes de franquear el surco.

---

## 4. Puntos de Desborde (*Spill Points*) de Bajos (Tarea 3.7)

Para cada bajo o cubeta cerrada identificada por el algoritmo de acondicionamiento:
1. **Cota de rebalse ($z_{\text{spill}}$):** cota mínima de la divisoria de aguas (*pour point*) que rodea al bajo.
2. **Capacidad de almacenamiento antes del desborde ($V_{\text{max}}$ en m³):**

$$V_{\text{max}} = \sum_{z_{\text{celda}} < z_{\text{spill}}} (z_{\text{spill}} - z_{\text{celda}}) \times \text{área}_{\text{celda}}$$

3. **Lluvia requerida para desbordar:** lámina neta de lluvia $\Delta Q_{\text{spill}} = V_{\text{max}} / A_{\text{cuenca\_contribuyente}}$.
4. **Ruta de desborde:** trazado vectorial descendente desde el *spill point* hacia el receptor exterior o bajo siguiente.

---

## 5. Criterios de Aceptación Técnicos

1. **Edición de terreno:**
   - [ ] Trazar una zanja en un bajo cerrado resuelve el anegamiento y reduce el volumen retenido $> 50\%$ en la simulación 2D.
   - [ ] Trazar un bordo detiene el flujo laminar aguas arriba y genera retención controlada.
2. **Dirección de siembra:**
   - [ ] Test comparativo: siembra en contorno ($\Delta \theta = 90^\circ$) reduce la velocidad máxima superficial en al menos $20\%$ respecto a siembra a favor de la pendiente ($\Delta \theta = 0^\circ$).
3. **Puntos de desborde:**
   - [ ] Detección correcta del *pour point* en un bajo sintético, con volumen antes de rebalse calculado con error $< 5\%$.
   - [ ] Salida GeoJSON del punto de desborde y su línea de derrame posterior.
