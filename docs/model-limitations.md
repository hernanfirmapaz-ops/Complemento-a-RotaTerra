# Limitaciones del Modelo y Advertencias Técnicas (SDD §5.2, §6 y §11.2)

Este documento detalla el alcance científico, las hipótesis operativas, las fuentes de incertidumbre y las restricciones físicas aplicables a cada fase de procesamiento y a las 8 herramientas agronómicas complementarias de **Complemento a RotaTerra**.

---

## 1. Fase 0 y Fase 1 — Análisis Topográfico y Acondicionamiento Hidrológico

1. **Resolución espacial (regla de los 30 m):**
   - Con un MDE de 30 m/píxel (Copernicus DEM GLO-30 o MDE-Ar IGN 30 m), un lote de 50 ha comprende ~550 celdas y un lote de 200 ha ~2.200 celdas.
   - Esta escala permite capturar macro-pendientes y laderas principales, pero **no resuelve** microrelieves, surcos de siembra directa, huellas de cosechadora, cunetas internas, bordos ni camellones.
   - Para evaluar obras a nivel de lote o micro-drenajes, es obligatorio incorporar relevamientos con dron RTK o LiDAR (0.05 a 2 m/píxel).
2. **Modelo Digital de Superficie (MDS) vs. Terreno Desnudo (MDT):**
   - Los modelos globales radar (TanDEM-X / Copernicus) registran la superficie reflectante superior. Cortinas forestales, montes nativos, galpones o silos aparecen como promontorios topográficos artificiales salvo que se apliquen algoritmos de remoción de vegetación o quema de líneas de drenaje (*drainage burning*).
3. **Tratamiento estricto de vacíos (`nodata`):**
   - Las celdas sin dato se preservan como `NaN` en todas las transformaciones, cálculos de pendiente y perfiles altimétricos. Los triángulos de la malla 3D adyacentes a `NaN` se omiten para evitar interpolaciones ficticias.
4. **Exageración vertical en visor 3D:**
   - La opción de exageración (1.5×, 2×, 3×, 5×) es estrictamente didáctica para facilitar la visualización de pendientes suaves en llanura pampeana. Todos los cálculos numéricos (pendiente %, pendiente en grados, acumulación y perfiles) se ejecutan sobre elevaciones reales en metros (escala 1×) en coordenadas métricas UTM.
5. **Algoritmos de enrutamiento de flujo (D8 y MFD):**
   - El algoritmo D8 (O'Callaghan & Mark 1984) fuerza la descarga hacia una única celda descendente, ideal para delimitar cauces encauzados definidos.
   - El algoritmo multidireccional MFD (Quinn et al. 1991, Freeman 1991) distribuye el flujo proporcionalmente a la pendiente hacia todas las celdas más bajas, representando con mayor realismo la dispersión laminar en lomas y medias lomas.
   - Las depresiones cerradas se tratan mediante llenado hidrológico (Wang & Liu 2006) o forzado de descarga si se dispone de capas vectoriales de alcantarillas (*culvert burning*).

---

## 2. Fase 2 — Estimación de Escorrentía y Lluvia de Diseño (Nivel 2)

1. **Método de la Curva de Número (NRCS-CN, USDA 1986):**
   - Modelo conceptual simplificado para estimar volumen de escorrentía directa $Q$ a partir de la precipitación total $P$:
     $$Q = \frac{(P - I_a)^2}{P - I_a + S} \quad \text{para } P > I_a$$
     $$S = \frac{25400}{CN} - 254 \quad (\text{mm}), \quad I_a = \lambda \cdot S$$
   - Por defecto se adopta la relación estándar $\lambda = 0.20$ (o $\lambda = 0.05$ según parametrización moderna).
2. **Condición de Humedad Antecedente (AMC I, II, III):**
   - El CN de catálogo corresponde a humedad media (AMC II). Para suelos secos o saturados, se aplican las correcciones estándar de Sobhani (1975) / Hawkins et al. (1985).
3. **Distribución espacial uniforme de la precipitación:**
   - En tormentas convectivas estivales pueden existir gradientes pluviométricos severos dentro de un mismo establecimiento. El modelo asume precipitación uniforme sobre la máscara del lote salvo que se cargue una grilla raster de radar meteorológico o red de pluviómetros distribuidos.

---

## 3. Fase 3 y Fase 4 — Simulación Hidrodinámica 2D (Nivel 3)

1. **Ecuación de onda difusiva 2D:**
   - El módulo hidrodinámico resuelve la simplificación de onda difusiva de las ecuaciones de Saint-Venant 2D, considerando balance de masa y fricción de fondo (Manning), omitiendo términos de aceleración convectiva e inercial.
2. **Coeficiente de rugosidad de Manning ($n$):**
   - Se parametriza por cobertura vegetal y suelo (valores típicos $0.035$ a $0.150\,\text{s/m}^{1/3}$). Debe calibrarse frente a marcas de agua o eventos observados.
3. **Condición de estabilidad CFL y paso de tiempo:**
   - El avance temporal está acotado por la condición Courant-Friedrichs-Lewy ($\Delta t \le \Delta x / \sqrt{g h}$). Para preservar estabilidad numérica sin sobrecargar el procesador, se emplean mallas UTM con paso de celda adaptativo y un máximo de 10.000 nodos por lote.

---

## 4. Fase 5 — Suite Agronómica Complementaria (8 Herramientas)

### 4.1 Herramienta 1: Erosión Hídrica USLE / RUSLE y Cárcevas
- **Modelo:** Wischmeier & Smith (1978), Renard et al. (1997).
- **Factor topográfico LS 2D:** Desmet & Govers (1996) / Moore & Burch (1986). La longitud de pendiente está acotada a un valor conservador máximo de 180 m en ausencia de terrazas.
- **Erosividad de tormenta ($EI_{30}$):** Si no se ingresa la intensidad máxima en 30 minutos ($I_{30}$), se emplea la correlación empírica pampeana conservadora $I_{30} \approx \min(75, 0.65 \cdot P)$ (Lombardi Neto et al. 1980; Bertoni & Lombardi Neto 1990).
- **Sediment Delivery Ratio (SDR):** Basado en relación empírica con escorrentía superficial (Williams & Berndt 1977, USDA SCS-TP-149). Proporciona estimaciones comparativas para toma de decisiones, no mediciones gravimétricas de sedimentos transportados.

### 4.2 Herramienta 2: Balance Hídrico Mensual y Evapotranspiración ($ET_0$)
- **Modelo de $ET_0$:** Ecuación de Hargreaves-Samani (1985), recomendada por FAO-56 (Allen et al. 1998) ante disponibilidad exclusiva de temperaturas extremas diarias ($T_{\max}, T_{\min}$) y radiación solar astronómica extraterrestre $R_a(\text{latitud}, \text{doy})$.
- **Capacidad de Almacenaje de Agua Útil (AWC):** Estimada a partir de los grupos hidrológicos de suelo y profundidad radicular efectiva. No sustituye mediciones in-situ con sonda de neutrones o sensores capacitivos TDR.

### 4.3 Herramienta 3: Riesgo de Anegamiento en Fechas Reales
- **Criterio:** Cruce entre precipitaciones acumuladas de 3, 5 y 10 días (NASA POWER / IMERG) con el Índice Topográfico de Humedad (TWI) y el área de aporte MFD.
- **Limitación:** Evalúa acumulación superficial por escorrentía topográfica; no modela la fluctuación freática de la napa freática regional salvo que se carguen lecturas de freatímetros locales.

### 4.4 Herramienta 4: Diseño y Simulación de Terrazas a Nivel
- **Criterio de diseño:** Intervalo vertical (VI) y espaciamiento horizontal (HI) según directrices de conservación de suelos INTA / USDA-NRCS ($VI \approx 0.30 \cdot (S/3 + 2)$).
- **Hipótesis de cálculo:** Supone lomos de terraza correctamente compactados y mantenidos a cota uniforme, sin roturas ni desbordes localizados.

### 4.5 Herramienta 5: Calculadora de Siembra y Fertilización (Funciones de Rotaterra)
- **Delimitación de alcance:** La calculadora de dosis de semilla, densidad y fertilización N-P-S corresponde al dominio productivo y económico de **Rotaterra** (funciones de Rotaterra). Se encuentra excluida de la interfaz de usuario del Complemento a RotaTerra.
- **Parámetros:** Tablas agronómicas de recomendación de densidades y coeficientes de logro según ambiente topográfico (loma, media loma, bajo) del INTA Manfredi / Pergamino.
- **Ajuste requerido:** El poder germinativo (PG) y el peso de mil granos (PMG) deben ajustarse con el marbete del lote comercial de semilla a sembrar.

### 4.6 Herramienta 6: Comparador de Rotaciones Trienales (Funciones de Rotaterra)
- **Delimitación de alcance:** La comparación económica y de márgenes de rotaciones de cultivos pertenece al sistema central **Rotaterra** (funciones de Rotaterra / alcance de Rotaterra). Queda fuera de la interfaz del Complemento a RotaTerra, el cual se restringe a procesos físicos de escurrimiento, suelo y erosión.
- **Enfoque:** Evaluación multianual del impacto de secuencias de cultivos (coberturas invernales, gramíneas de verano, leguminosas) sobre el número de curva ponderado ($CN$) y la tasa de pérdida de suelo anualizada.
- **Limitación:** Es una herramienta comparativa de escenarios de manejo; no modela dinámica microbiológica ni ciclado biogeoquímico de nutrientes a largo plazo.

### 4.7 Herramienta 7: Monitor de Vigor Satelital (NDVI Sentinel-2 STAC)
- **Fuente:** Imágenes ópticas Sentinel-2 L2A procesadas en reflectancia de superficie (BOA).
- **Filtrado de calidad:** Aplicación estricta de la máscara de clasificación de escena (SCL) para descartar nubes, sombras de nubes y cirros.
- **Resolución:** Píxel de 10 m en bandas roja (B04) e infrarroja cercana (B08). Si la escena supera el 85% de nubosidad o la API STAC no está accesible, el sistema degrada de manera transparente reportando `status: "unavailable"` sin inventar datos sintéticos (Regla R4).

### 4.8 Herramienta 8: Ventanas de Siembra y Riesgo Histórico de Heladas
- **Base climática:** Serie histórica diaria 1990–presente obtenida de NASA POWER agrometeorology.
- **Métricas:** Percentiles (P10, P50, P90) de fecha de primera helada otoñal y última helada primaveral ($T_{\min} \le 0^\circ\text{C}$ meteorológica / $3^\circ\text{C}$ agronómica en casilla).
- **Advertencia:** Los datos corresponden a celdas de reanálisis de $0.5^\circ \times 0.5^\circ$. Los bajos topográficos con inversión térmica pueden registrar heladas más severas y tardías que el valor medio de la celda de reanálisis.
