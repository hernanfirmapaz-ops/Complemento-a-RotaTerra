# Spec 013: Agua Fluida, Corriente Animada y Visor 3D Dinámico

**Estado:** Borrador para revisión (requiere aprobación de Hernán)  
**Fecha:** 22/11/2026  
**Rama:** `spec/013-agua-fluida-3d`  
**Issue:** #33 (`[23] Visor 3D · Agua fluida (bordes suaves, shader, corriente animada)`)  
**Autor:** Antigravity  

---

## 1. Justificación y Diagnóstico

En la versión actual del Visor 3D (`TerrainScene3D.tsx` / `TerrainDiorama3D.tsx`), la visualización del encharcamiento y escurrimiento superficial presenta limitaciones estéticas y dinámicas reportadas por Hernán el 21/11/2026:
1. **Representación en bloques discretos:** El agua se visualiza tiñendo directamente los vértices o celdas del terreno a la resolución nativa del Modelo Digital de Elevaciones (30 m en Copernicus GLO-30 o SRTM), generando una apariencia pixelada de "bloques o cuadrados azules" en los bordes de bajos y cubetas.
2. **Color plano e inerte:** No existe diferenciación óptica entre una lámina somera de 3 cm y un bajo profundo de 50 cm; no hay efecto Fresnel, ondulación superficial ni reflejos de luz solar.
3. **Ausencia de movimiento en la corriente:** A pesar de que el motor hidrodinámico calcula velocidades de flujo, la masa de agua permanece estática en pantalla sin indicar la dirección ni la vivacidad del escurrimiento.
4. **Lluvia visual pesada:** Las precipitaciones se grafican como trazos lineales rígidos y continuos que no reflejan la escala de gotas naturales ni se coordinan con la evolución temporal de la tormenta.

La mejora de fondo a nivel agronómico e hidrológico radica en la futura incorporación del MDE-Ar de 5 m del Instituto Geográfico Nacional (IGN). Mientras tanto, esta especificación define las mejoras gráficas y de shaders WebGL (Three.js) para lograr una representación fluida, realista y dinámica del agua, manteniendo la rigurosidad matemática del motor 2D.

---

## 2. Reglas Innegociables de Representación

1. **El suavizado es estrictamente visual:** La interpolación gráfica jamás altera los cómputos hidrológicos. La superficie total anegada (ha), los volúmenes retenidos ($m^3$) y las láminas calculadas provienen sin modificar de la matriz de celdas del solver 2D.
2. **Leyenda de transparencia técnica:** En el visor 3D se mostrará de forma permanente o en el chip de datos la leyenda:  
   > *"Bordes suavizados para visualización; resolución del cálculo: X m"*.
3. **Corte estricto por umbral de encharcamiento:** El agua se corta en el umbral de encharcamiento del motor ($h_{\text{umbral}} = \text{ponding\_threshold\_m}$, leído de la API). Si $h < h_{\text{umbral}}$, no se dibuja agua (`discard` en shader). El desvanecimiento ocurre únicamente por encima: $\alpha = \text{smoothstep}(h_{\text{umbral}}, \, 1,5 \cdot h_{\text{umbral}}, \, h)$, garantizando que la visualización coincida con el límite físico del motor.
4. **Rendimiento garantizado (60 FPS):** La renderización debe sostener 60 cuadros por segundo estables en una computadora portátil estándar (GPU integrada tipo Intel Iris Xe / AMD Radeon Vega) para lotes de hasta 500 ha. Cada PR de implementación incluirá métricas de cuadros por segundo medidas localmente.
5. **Modo Liviano para dispositivos móviles:** Detección de bajo rendimiento o pantalla táctil móvil: desactiva salpicaduras de lluvia, partículas de corriente y mapas normales secundarios, conservando la malla suave y el color por profundidad.
6. **Verificación visual obligatoria:** Cada PR de etapa debe adjuntar capturas o videos comparativos ("Antes vs. Después") en resoluciones de escritorio y móvil.

---

## 3. Arquitectura por Etapas

La implementación se dividirá en 5 etapas progresivas, cada una con su propio Pull Request independiente tras la aprobación de esta especificación.

```
┌────────────────────────────────────────────────────────────────────────┐
│ Etapa 1: Malla propia de agua 4× e interpolación bilineal              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Etapa 2: Aspecto físico (ShaderMaterial, Fresnel, profundidad, olas)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Etapa 3: Corriente animada (Flow Map de Vlachos y partículas GPU)      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Etapa 4: Reproductor temporal (Timeline uint16 en mm y play/pausa)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Etapa 5: Lluvia ligera natural (Gotas sprite, salpicaduras y apagado)  │
└────────────────────────────────────────────────────────────────────────┘
```

---

### Etapa 1: Bordes Suaves (Malla de Agua Propia)

* **Objetivo:** Eliminar el aspecto dentado de 30 m sin alterar las alturas del terreno.
* **Mecanismo técnico:**
  1. **Malla geométrica desacoplada:** Se genera una `BufferGeometry` independiente para el espejo de agua, situada sobre el terreno y no modificando el sombreado de la tierra.
  2. **Elevación de superficie libre:** Para cada vértice $(x, y)$, la cota de la superficie se define como:
     $$\eta(x, y) = z_{\text{terreno}}(x, y) + h_{\text{agua}}(x, y)$$
  3. **Sobremuestreo bilineal a $4\times$:** Si el terreno tiene una celda de $\Delta x = 30\text{ m}$, la malla de agua interpola cotas y láminas a intervalos de $7,5\text{ m}$ mediante interpolación bilineal de 4 puntos vecinos:
     $$h(u, v) = (1-u)(1-v)h_{0,0} + u(1-v)h_{1,0} + (1-u)v h_{0,1} + uv h_{1,1}$$
  4. **Corte estricto y desvanecimiento de borde (`smoothstep`):** En el fragment shader, el corte y la opacidad $\alpha$ se calculan a partir del umbral de encharcamiento provisto por la API ($h_{\text{umbral}} = \text{ponding\_threshold\_m}$, típicamente $0,02\text{ m}$ a $0,05\text{ m}$):
     - Si $h < h_{\text{umbral}}$: se descarta el fragmento (`discard`), no dibujando agua donde el motor no detectó retención física.
     - Si $h \ge h_{\text{umbral}}$: se desvanece suavemente solo por encima del umbral:
       $$\alpha = \text{smoothstep}(h_{\text{umbral}}, \, 1,5 \cdot h_{\text{umbral}}, \, h)$$
     De este modo, la transición de transparencia inicia en $0$ exactamente en el corte físico del motor y alcanza opacidad plena en $1,5 \times h_{\text{umbral}}$, eliminando bordes abruptos sin invadir zonas secas.
* **Datos requeridos:** Matriz de láminas `water_depth_m` y `ponding_threshold_m` ya provistos por la API.

---

### Etapa 2: Aspecto de Agua (ShaderMaterial Realista)

* **Objetivo:** Proporcionar identidad visual de agua natural con profundidad y brillo sin costo excesivo de cómputo.
* **Mecanismo técnico:**
  1. **Material personalizado:** Reemplazo de materiales estándar por un `ShaderMaterial` de Three.js con soporte para luces direccionales de la escena.
  2. **Gradiente cromático por batimetría (Parámetros visuales declarados):**
     Los cortes de profundidad no están fijos como números mágicos dispersos en el shader, sino que se configuran como parámetros visuales explícitos y calibrables:
     - `WATER_VISUAL_SHALLOW_DEPTH_M = 0.08` (Corte de agua somera: 8 cm).
     - `WATER_VISUAL_DEEP_DEPTH_M = 0.25` (Corte de agua profunda: 25 cm).
     Rampa de color:
     - Aguas someras ($h < \text{WATER\_VISUAL\_SHALLOW\_DEPTH\_M}$): Turquesa claro traslúcido ($\text{RGB}: 82, 185, 195, \alpha \approx 0,45$).
     - Profundidad intermedia ($\text{WATER\_VISUAL\_SHALLOW\_DEPTH\_M} \le h \le \text{WATER\_VISUAL\_DEEP\_DEPTH\_M}$): Azul cerceta medio ($\text{RGB}: 35, 120, 175, \alpha \approx 0,75$).
     - Profundidad máxima ($h > \text{WATER\_VISUAL\_DEEP\_DEPTH\_M}$): Azul ultramar profundo saturado ($\text{RGB}: 15, 60, 120, \alpha \approx 0,92$).
  3. **Aproximación de Fresnel (Schlick 1994):**
     $$R(\theta) = R_0 + (1 - R_0)(1 - \cos \theta)^5, \quad R_0 = \left(\frac{n_1 - n_2}{n_1 + n_2}\right)^2 \approx 0,02 \text{ (para agua)}$$
     - Al observar con ángulo rasante ($\theta \to 90^\circ$), el agua refleja más el cielo y la luz ambiental.
     - Al observar perpendicularmente desde arriba ($\theta \to 0^\circ$), el agua se vuelve transparente, permitiendo apreciar el relieve del fondo.
  4. **Mapa de normales animado:** Superposición de dos muestras de mapas de normales de olas suaves (`Water.js` de Three.js) desplazadas en sentidos levemente divergentes a velocidad constante para simular oleaje impulsado por la brisa.
  5. **Brillo especular:** Reflejo especular según Blinn-Phong enfocado con respecto al sol virtual.
* **Datos requeridos:** Parámetros de iluminación solar ya existentes en la escena 3D.

---

### Etapa 3: Corriente que se Mueve (Flow Map y Partículas GPU)

* **Objetivo:** Mostrar con dinamismo el sentido y la velocidad por donde escurre el agua durante la tormenta.
* **Mecanismo técnico:**
  1. **Técnica de *Flow Map* (Vlachos, Valve SIGGRAPH 2010):**
     - La textura de normales no se traslada uniformemente, sino en función del vector velocidad local $(u, v)$.
     - Para evitar el estiramiento y distorsión infinita de las coordenadas de textura, se emplean dos capas temporales desfasadas en medio período ($\Delta \phi = 0,5$):
       $$\text{uv}_1 = \text{uv} + (u, v) \cdot \text{fract}(t)$$
       $$\text{uv}_2 = \text{uv} + (u, v) \cdot \text{fract}(t + 0,5)$$
     - La normal final se obtiene interpolando ambas con un peso triangular simétrico:
       $$w(t) = 1 - |2 \cdot \text{fract}(t) - 1|$$
       $$N_{\text{final}} = \text{normalize}\left( w(t) \cdot N(\text{uv}_1) + (1 - w(t)) \cdot N(\text{uv}_2) \right)$$
  2. **Partículas instanciadas en GPU (`InstancedMesh`):**
     - Pequeñas partículas (burbujas/espuma) arrastradas a lo largo de las trayectorias de flujo.
     - Densidad proporcional al caudal unitario $q = v \cdot h$; mayor presencia en cañadones y vías de evacuación rápida.
     - Reubicación cíclica (respawn) cuando la partícula sale del lote o ingresa en una zona de estancamiento.
* **Extensión de API requerida:**
  - El backend actualmente expone el escalar de módulo de velocidad `velocity_m_s`.
  - Se requiere agregar en la respuesta de la simulación las componentes vectoriales en grilla:
    - `velocity_u_m_s`: componente en eje X (Oeste → Este) [m/s].
    - `velocity_v_m_s`: componente en eje Y (Sur → Norte) [m/s].

---

### Etapa 4: El Agua Avanza en el Tiempo (Timeline Playback)

* **Objetivo:** Permitir al productor o asesor agronómico observar cómo el agua se acumula, avanza y drena a lo largo del evento meteorológico.
* **Mecanismo técnico:**
  1. **Interpolación de cuadros:** Dado el cuadro $k$ en el instante $t_k$ y el cuadro $k+1$ en $t_{k+1}$, la lámina en un instante intermedio se interpola suavemente:
     $$h(t) = (1 - \tau) h_k + \tau h_{k+1}, \quad \tau = \frac{t - t_k}{t_{k+1} - t_k}$$
  2. **Controles de reproducción:**
     - Barra de tiempo interactiva integrada (`FlowTimelinePlayer`).
     - Botón Play / Pausa.
     - Selector de velocidad ($0,5\times, 1\times, 2\times, 5\times$).
     - Arrastre manual (scrubbing) con actualización instantánea de la malla de agua.
  3. **Optimización de transferencia (formato binario uint16 en mm):**
     - Se adopta estrictamente el formato **`uint16` en milímetros (mm)** para la transmisión de las mallas de lámina por celda de cada cuadro.
     - Cada celda almacena la profundidad como un entero sin signo de 16 bits ($0$ a $65535\text{ mm}$, que cubre de $0$ a $65,535\text{ m}$ con resolución métrica de $1\text{ mm}$).
     - El cliente decodifica directamente a metros mediante:
       $$h_{\text{metros}} = \frac{\text{valor\_uint16}}{1000.0}$$
     - Ocupa exactamente 2 bytes por celda (un cuadro de $200 \times 200$ celdas pesa apenas 80 KB frente a >1 MB en JSON), permitiendo carga directa a texturas WebGL de 16 bits (`gl.R16UI` o `DataTexture`) sin pérdida de precisión.
* **Datos requeridos:** Cuadros temporales generados por el solver inercial 2D (Spec 010) cada 5 o 10 minutos de simulación.

---

### Etapa 5: Lluvia Ligera y Realista (Gotas Sprite y Salpicadura)

* **Objetivo:** Reflejar con fidelidad la precipitación sobre el campo sin recargar la pantalla ni obstruir el relieve.
* **Especificaciones conforme al ajuste de Hernán (21/11/2026):**
  1. **Geometría de gotas (Sprites redondos):**
     - Se descartan las líneas verticales alargadas.
     - Se implementa mediante `THREE.Points` o `InstancedMesh` con textura de sprite circular suave (punto con brillo tenue y desvanecimiento radial).
     - Tamaño adaptativo en pantalla: de **2 a 4 píxeles** según la distancia euclidiana a la cámara.
  2. **Aspecto y estiramiento mínimo:**
     - Sin estelas largas: en caso de aplicar estiramiento por velocidad de caída, la relación de aspecto no superará **$1,5\times$** el ancho de la gota.
  3. **Salpicadura al impacto (Splash):**
     - Al alcanzar la cota de la superficie del terreno o del agua, se genera una animación de anillo concéntrico fino que se expande radialmente y se desvanece por completo en $\approx 0,3\text{ s}$.
     - Se desactiva automáticamente en el Modo Liviano.
  4. **Densidad sincronizada con la intensidad de lluvia:**
     - La cantidad de partículas emitidas por segundo se modula en tiempo real según la tasa de precipitación (mm/h) del cuadro temporal activo (Etapa 4).
     - Tope estricto de partículas activas simultáneas para garantizar 60 FPS sin importar el zoom.
  5. **Apagado automático:**
     - Al completarse el intervalo de lluvia del evento meteorológico (fase de recesión e infiltración), la emisión de gotas se detiene por completo sin requerir intervención del usuario.

---

## 4. Estrategia de Entrega y Verificación

Cada etapa se ejecutará de forma modular:

| Etapa | Alcance del PR | Requisitos de Verificación |
|---|---|---|
| **Etapa 1** | Malla 4×, cota + lámina, corte en umbral de motor y desvanecimiento `smoothstep`, leyenda técnica. | Tests de interpolación bilineal; medición $\ge 60\text{ FPS}$ en 500 ha; capturas antes/después del borde. |
| **Etapa 2** | `ShaderMaterial`, gradiente batimétrico con parámetros declarados, Fresnel, normales animadas. | Inspección visual en desktop y mobile; verificación de degradado según profundidad. |
| **Etapa 3** | Componentes $u, v$ en API, flow map cíclico y partículas de corriente. | Endpoint con `velocity_u_m_s` y `velocity_v_m_s`; prueba de partículas GPU sin fugas de memoria. |
| **Etapa 4** | Endpoint binario uint16 (mm), buffer dinámico en cliente y controles de timeline. | Prueba de descarga binaria ligera; reproducción suave sin caídas de framerate. |
| **Etapa 5** | Sprite circular de gotas, salpicaduras de impacto, apagado automático. | Medición de consumo de CPU/GPU con lluvia activa; apagado verificado al fin de tormenta. |

---

## 5. Referencias Técnicas y Bibliográficas

1. **Vlachos, Alex (Valve Corporation, 2010):** *Water Flow in Portal 2*. SIGGRAPH 2010 Course on Advances in Real-Time Rendering in 3D Graphics and Games.  
2. **Three.js Examples:** `three/examples/jsm/objects/Water.js` (Simulación de ondas de superficie plana, reflectividad Fresnel y perturbación de normales).  
3. **Schlick, Christophe (1994):** *An Inexpensive BRDF Model for Physically-Based Rendering*. Computer Graphics Forum, 13(3): 233–246.  
4. **Instituto Geográfico Nacional (IGN):** Modelo Digital de Elevaciones de la República Argentina (MDE-Ar 5 m).
