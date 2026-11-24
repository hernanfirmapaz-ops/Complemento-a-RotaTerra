# Spec 015: Incertidumbre del Relieve (Propagación Monte Carlo Espacialmente Correlacionada y Rangos P10–P50–P90)

**Estado:** Borrador para revisión (requiere aprobación de Hernán)  
**Fecha:** 23/11/2026  
**Rama:** `spec/015-incertidumbre-relieve-montecarlo`  
**Issue:** #101 (`[55] Incertidumbre del relieve: resultados con rango P10–P90 (Monte Carlo sobre el DEM)`)  
**Autor:** Antigravity  

---

## 1. Justificación y Diagnóstico del Problema

### 1.1 El error vertical en llanuras frente al desnivel del lote
En la auditoría altimétrica regional (Spec 014 §1.2), la comparación empírica de **Copernicus DEM GLO-30** contra mojones de nivelación geométrica de alta precisión del Instituto Geográfico Nacional (IGN) en San Luis (tesela S34 W066) reveló una dispersión estocástica vertical:
$$\text{NMAD} \approx 0,95\text{ m}\ (n = 44,\ \text{alta precisión}) \quad \text{a} \quad 1,15\text{ m}\ (n = 76,\ \text{alta precisión + precisión})$$

En lotes agropecuarios de la llanura pampeana y planicie medanosa (e.g. 100 a 500 ha), el desnivel topográfico total a lo largo de 1 a 2 km suele ser de apenas $1,0$ a $3,0\text{ m}$. Por lo tanto:
$$\text{Error estocástico del sensor} \approx \text{Desnivel total del campo}$$

### 1.2 Por qué un único valor determinista es engañoso
Hoy el sistema informa un único valor exacto (por ejemplo: *"Superficie anegable: 14,2 ha (11,8 %)"* o *"Erosión hídrica: 4,3 t/(ha·año)"*). 
- Un desplazamiento aleatorio de apenas $\pm 0,5\text{ m}$ en una celda de cresta o borde puede duplicar o disipar por completo un área de encharcamiento simulada.
- Informar cifras puntuales sin intervalo de confianza genera falsas certezas y puede llevar a decisiones agronómicas erróneas (e.g. obras de desagüe innecesarias o desestimación de bajos reales).

**Objetivo metodológico:** Reemplazar el reporte determinista por un enfoque de **propagación estocástica de incertidumbre**, informando rangos percentilares **P10 – P50 – P90** y un mapa ráster de **probabilidad espacial de anegamiento**.

---

## 2. Marco Metodológico: Simulación Monte Carlo Espacialmente Correlacionada

### 2.1 Modelo de error espacialmente autocorrelacionado
El ruido de un DEM satelital no es ruido blanco independiente celda a celda; presenta una marcada correlación espacial generada por el proceso de correlación interferométrica radar o filtrado espectral del sensor. Agregar ruido gaussiano puro celda a celda generaría un micro-relieve artificial con pozos y picos espurios ("efecto sal y pimienta").

Siguiendo el método estocástico de simulación de error de relieve desarrollado por **Lindsay & Creed (2006)** (*"Distinguishing actual and artefact depressions in digital elevation data"*, *Computers & Geosciences*, 32(8), 1192–1204, DOI: 10.1016/j.cageo.2005.11.002; complementado por Lindsay & Creed 2005, *Hydrological Processes*, 19(16), 3113–3126):

1. **Generación de campo aleatorio:**
   Se genera un campo de ruido blanco gaussiano independiente $\eta \sim \mathcal{N}(0, 1)$ con las dimensiones espaciales de la grilla del lote $(M \times N)$.
2. **Filtrado espacial por convolución gaussiana (autocorrelación):**
   Se convoluciona $\eta$ con un kernel gaussiano 2D $K(r)$ cuya desviación espacial responde a la **longitud de correlación espacial** $L_{\text{corr}}$:
   $$K(r) = \frac{1}{2\pi \sigma_k^2} \exp\left(-\frac{r^2}{2\sigma_k^2}\right), \quad \sigma_k = \frac{L_{\text{corr}}}{2}$$
   Donde $L_{\text{corr}} = 80\text{ m}$ por defecto (orden de 2 a 3 celdas de 30 m, supuesto calibrable en `supuestos.py`).
3. **Escalado a la dispersión de la fuente:**
   El campo filtrado se normaliza a media cero y desviación unitaria, y se multiplica por la dispersión vertical robusta de la fuente activa ($\text{NMAD}_{\text{fuente}}$):
   $$\epsilon_k(x, y) = \text{NMAD}_{\text{fuente}} \cdot \frac{\eta * K}{\text{std}(\eta * K)}$$
   - Para Copernicus GLO-30: $\text{NMAD} = 1,15\text{ m}$ (`SUPUESTO_DEPRESION_ACCURACY_NMAD_M.valor`).
   - Para Fusión GEM-15: $\text{NMAD} = 0,91\text{ m}$.
   - Para Dron RTK propio: error declarado por el usuario (e.g. $0,05\text{ m}$).
4. **Ensamble de realizaciones del terreno:**
   Para cada realización $k \in \{1, \dots, N_{\text{sim}}\}$:
   $$z_k(x, y) = z_{\text{base}}(x, y) + \epsilon_k(x, y)$$

---

## 3. Flujo de Ejecución y Métricas de Salida

Para cada realización $z_k$:
1. Se aplica el suavizado espacial correspondiente (`smooth_dem_whitebox` o `moving_plane_slope`).
2. Se condiciona el drenaje en modo `"preservar_depresiones"` (Spec 030).
3. Se resuelve la acumulación de flujo, la depresión y el encharcamiento para la lluvia asignada.
4. Se computa el factor $LS$ y la pérdida de suelo USLE ($A_k$).

### 3.1 Métricas percentilares P10 – P50 – P90
Para cada indicador escalar $X \in \{\text{Superficie Anegable (ha)},\ \text{Porcentaje Anegable (\%)},\ \text{Pérdida USLE (t/(ha}\cdot\text{año))}\}$:
- **P10:** Escenario conservador / optimista (10 % de las realizaciones por debajo).
- **P50:** Mediana probabilística más probable.
- **P90:** Escenario desfavorable / máximo riesgo (90 % de las realizaciones por debajo).

### 3.2 Mapa de Probabilidad Espacial de Anegamiento
Para cada celda $(i, j)$ del lote, la probabilidad de anegamiento se calcula como la frecuencia relativa de inundación sobre el ensamble:
$$P_{\text{anegamiento}}(i, j) = \frac{1}{N_{\text{sim}}} \sum_{k=1}^{N_{\text{sim}}} \mathbf{1}_{\text{anegado}, k}(i, j) \in [0.0, 1.0]$$

**Interpretación agronómica:**
- **$P \ge 0,80$ (Alta certeza):** Bajo estructural indiscutible; el agua se acumulará con casi cualquier configuración de error del DEM. Zona prioritaria para manejo diferencial, pasturas hidrófilas o exclusión de siembra.
- **$0,20 < P < 0,80$ (Certeza moderada / marginal):** Bordes de cubetas y sectores deprimidos sensibles al microrelieve; anegamiento dependiente de eventos intensos.
- **$P \le 0,20$ (Baja probabilidad):** Encharcamiento solo bajo artefactos extremos; zona mayoritariamente segura.

---

## 4. Parámetros en `geoprocessing/supuestos.py`

| Constante | Valor | Unidad | Fuente / Justificación | Editable |
|---|---|---|---|---|
| `SUPUESTO_MONTECARLO_HABILITADO` | `True` | boolean | Habilita cálculo de rangos e incertidumbre. | Sí |
| `SUPUESTO_MONTECARLO_N_REALIZACIONES` | `30` | entero | Compromiso óptimo entre convergencia estadística y tiempo de CPU ($N=30$). | Sí |
| `SUPUESTO_MONTECARLO_N_REALIZACIONES_RAPIDO` | `10` | entero | Modo rápido para previsualización interactiva en frontend. | Sí |
| `SUPUESTO_MONTECARLO_LONGITUD_CORRELACION_M` | `80.0` | m | Correlación espacial típica del error interferométrico satelital (Lindsay & Creed 2006); supuesto calibrable. | Sí |

---

## 5. Salidas en API y Esquemas de Datos

### 5.1 Enriquecimiento de `PondedAreaMetrics` y `HydrologyAnalysisResponse`
```json
{
  "superficie_anegable": {
    "hectareas": 14.2,
    "porcentaje_lote": 11.8,
    "rango_p10_p90": {
      "p10_hectareas": 9.4,
      "p50_hectareas": 13.8,
      "p90_hectareas": 18.6,
      "p10_porcentaje": 7.8,
      "p50_porcentaje": 11.5,
      "p90_porcentaje": 15.5,
      "incertidumbre_relativa_pct": 33.3
    }
  },
  "erosion_usle": {
    "perdida_promedio_t_ha_ano": 4.1,
    "rango_p10_p90": {
      "p10_t_ha_ano": 2.8,
      "p50_t_ha_ano": 3.9,
      "p90_t_ha_ano": 5.7
    }
  },
  "capas_raster": {
    "probabilidad_anegamiento_url": "/api/v1/fields/123/layers/inundation_probability.png"
  }
}
```

---

## 6. Rendimiento y Presupuesto Computacional

- **Vectorización NumPy puro:** La generación del campo correlacionado se realiza mediante FFT 2D vectorizada (`np.fft.rfft2` / `irfft2`) en $< 5\text{ ms}$ por realización para grillas de $100 \times 100$.
- **Tiempo límite:**
  - Lotes $\le 300\text{ ha}$ ($N = 30$): tiempo total de análisis $< 2,5\text{ s}$.
  - Modo interactivo rápido ($N = 10$): $< 0,8\text{ s}$.

---

## 7. Plan de Pruebas Automatizadas

1. **Test de convergencia y forma de perturbación (`test_montecarlo_spatial_autocorrelation`):**
   - Comprueba que la media del campo generado sea $0,0 \pm 0,05\text{ m}$ y su desviación estándar coincida con el NMAD configurado.
   - Verifica que el semivariograma empírico a distancia 0 sea 0 y crezca continuamente hasta el alcance configurado ($L_{\text{corr}} = 80\text{ m}$).
2. **Test de orden monótono (`test_montecarlo_percentiles_order`):**
   - Afirma estrictamente: $P_{10} \le P_{50} \le P_{90}$.
3. **Test de degradación en DEM de alta precisión (Dron RTK):**
   - Con $\text{NMAD} = 0,05\text{ m}$, el rango $P_{90} - P_{10}$ converge a valores casi despreciables ($< 5\%$ del valor medio).
