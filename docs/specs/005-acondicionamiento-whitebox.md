# Spec 005 · Acondicionamiento del relieve para llanura con WhiteboxTools

**Estado:** en implementación · **Fecha:** 21/11/2026 · **Etapa:** 2 (tarea 2.5) · **Mejoras:** S2 · S1

---

## 1. Problema y justificación

En lotes de llanura agrícola (como la planicie de San Luis y Pampa Seca, con pendientes típicas < 1 %):
1. **Ruido e instrumental vertical de DEMs satelitales (1 a 5 m):** crea microdepresiones artificiales (*speckle*) que inflan falsamente la pendiente media (ej. NASADEM marcando 2,7 % en planos de 1 %).
2. **Artefacto de las "lagunas planas" (Priority-Flood puro):** cuando un método de relleno puro encuentra una pequeña obstrucción o montículo falso (huella de arboleda, camino, error del sensor), rellena toda la llanura aguas arriba hasta el nivel del vertedero, creando mesetas de agua estancada inexistentes.
3. **Solución científica (Lindsay 2016):** acondicionar mediante *breaching* (abrir zanja/brecha de mínimo costo a través del obstáculo) en lugar de rellenar el bajo, complementado con un suavizado que conserva bordes (*Feature-Preserving Smoothing*).

---

## 2. Arquitectura de Dos Grillas

Para no desvirtuar la física de inundación:
- **Grilla Acondicionada (`z_conditioned`):** obtenida con suavizado + brecha de mínimo costo. Se utiliza exclusivamente para calcular direcciones de flujo (D8/MFD), acumulación difusa, TWI (*Topographic Wetness Index*), SPI (*Stream Power Index*), pendientes macro y factor LS de USLE.
- **Grilla Base del Motor 2D (`z_raw` / `dem.z`):** conserva la topografía original no modificada (con sus depresiones y bajos reales intactos), permitiendo que el solver hidrodinámico 2D (*shallow water equations*) acumule y encharque agua según la capacidad de almacenamiento real del terreno.

---

## 3. Estrategia de Acondicionamiento (`breach`)

El nuevo modo de acondicionamiento `"breach"` ejecuta secuencialmente:

1. **Suavizado con preservación de bordes (`feature_preserving_smoothing`):**
   - Tamaño de filtro: 11 celdas.
   - Umbral de desviación normal: 12° (rango 8°–15°).
   - Elimina el ruido de alta frecuencia sin redondear los bordes de taludes, terrazas o lomas.
2. **Brecha de depresiones de mínimo costo (`breach_depressions_least_cost`):**
   - Profundidad máxima de brecha: 0,8 m (rango 0,5 a 1,0 m).
   - Longitud máxima de brecha: 50 celdas.
   - Resuelve el paso del flujo tallando el obstáculo mínimo en lugar de inundar el lote aguas arriba.
3. **Relleno residual seguro (`fill_depressions` o `priority_flood_fill`):**
   - Elimina cualquier micro-pozo residual < ε para garantizar continuidad de flujo hacia los bordes.

---

## 4. Modos soportados en `condition_dem`

| Modo | Estrategia | Uso recomendado |
|---|---|---|
| `breach` | Whitebox (Smoothing + LeastCost Breach) | **Llanura agrícola (por omisión si WBT disponible)** |
| `fill_small` | Algoritmo nativo (Priority-Flood en micro-pozos) | Alternativa liviana sin binario externo |
| `preserve` | Topografía base + microgradiente ε | Terrenos sin interferencias |
| `fill_all` | Relleno completo Priority-Flood | Cuencas de montaña |

---

## 5. Criterios de aceptación

- [x] Relieve sintético plano con ruido gaussiano: tras el suavizado con preservación de bordes, la pendiente media se aproxima a la del plano original (diferencia < 20 %).
- [x] Depresión artificial de 0,3 m en plano inclinado: en modo `breach` se resuelve mediante apertura de zanja y no como una laguna plana.
- [x] La grilla del motor hidrodinámico 2D permanece inalterada frente al acondicionamiento hidrológico.
- [x] Tests corren sin internet (binario de Whitebox preinstalado en CI).
