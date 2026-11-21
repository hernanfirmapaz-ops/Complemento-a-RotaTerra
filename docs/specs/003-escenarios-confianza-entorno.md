# Spec 003 · Escenarios, confianza y entorno del lote

**Estado:** propuesta para aprobación de Hernán · **Repositorio:** Complemento a RotaTerra · **Etapa:** 2 · **Método:** SDD (spec primero, código después; verificación con datos reales).

---

## 1. Objetivo y Alcance

Esta especificación cubre los tres pilares de la **Etapa 2** del plan de trabajo:

1. **Entorno del lote (300–500 m):**
   - El agua no se detiene en el alambre del campo. Los lotes vecinos situados aguas arriba drenan hacia el lote del productor, aportando caudales significativos que causan anegamiento y cárcavas inesperadas.
   - Se procesa un área buffer configurable (300 m por omisión, ampliable a 500 m) alrededor del polígono catastral.
   - Se cuantifica el volumen de agua entrante desde la cuenca vecina (`external_runoff_inflow_m3`) y se visibiliza su trayectoria en el visor 3D.

2. **Indicador de confianza (Alto / Medio / Bajo):**
   - Regla 4 del plan: *Nunca inventar un valor; app honesta y transparente*.
   - Se calcula un índice objetivo de confianza para cada simulación, basado en la precisión del relieve (Copernicus 30 m vs IGN 5 m), la certeza del tipo de suelo (relevado vs carta general INTA) y el origen de la precipitación (pluviómetro vs diseño regional IDF transpuesta vs NASA POWER ~55 km).
   - Se expone en la interfaz mediante un indicador sobrio que explica las razones técnicas en un clic.

3. **Comparar escenarios lado a lado:**
   - Permite al productor y agrónomo comparar dos escenarios (por ejemplo: *Siembra Directa continua* vs *Labranza convencional*, o *Tormenta de 80 mm* vs *Temporal de 130 mm*).
   - Muestra las diferencias concretas en hectáreas anegadas ($\Delta$ ha), agua escurrida fuera ($\Delta$ % y $\Delta$ m³) y suelo fértil perdido ($\Delta$ t/ha).

---

## 2. Entorno del Lote (`feat/entorno-lote`)

### 2.1 Modelo Hidrológico del Buffer
- Cuando se procesa el terreno para un lote, la ventana de recorte se expande con un margen perimetral `buffer_m` (300 m por defecto, configurable entre 100 y 1000 m).
- El enrutamiento MFD y el balance 2D se calculan sobre la grilla total (lote + buffer).
- **Balance de masa en el perímetro:**
  - Toda celda que se encuentre dentro del polígono del lote y reciba flujo proveniente de celdas situadas fuera del polígono acumula volumen de escorrentía externa:
    $$\text{Inflow Externo} = \sum_{c \in \text{lote}} \sum_{p \in \text{vecinos}(c) \setminus \text{lote}} Q_{p \to c}$$
  - Este valor se reporta en `spatial_summary.external_runoff_inflow_m3`.
- **Salida:**
  - El volumen total de agua disponible en el lote se desglosa en:
    $$\text{Agua total en lote} = \text{Lluvia propia neta} + \text{Aporte cuenca externa}$$

### 2.2 Visualización 3D
- En `TerrainDiorama3D`, la zona del lote propio se renderiza con textura satelital y opacidad al 100%, con límite de alambre destacado.
- La zona del buffer (entorno) se renderiza con una sutil atenuación tonal para enfatizar el lote propio pero permitiendo ver claramente las vaguadas y cañadones que entran desde afuera.

---

## 3. Indicador de Confianza (`feat/indicador-confianza`)

### 3.1 Cálculo del Nivel de Confianza
El nivel de confianza se determina a partir de 3 componentes:

1. **Confianza del Relieve ($C_{\text{relieve}}$):**
   - **Alta:** DEM LiDAR o dron local ($\le 2$ m de resolución).
   - **Media:** Copernicus GLO-30 en terrenos con pendiente media $> 0.5\%$.
   - **Baja:** Copernicus GLO-30 o NASADEM en llanuras extremadamente planas (pendiente media $< 0.3\%$), donde el error vertical de $\pm 2$ m condiciona la dirección de micro-escurrimientos.

2. **Confianza del Suelo ($C_{\text{suelo}}$):**
   - **Alta:** Cartografía INTA de detalle 1:50.000 o análisis físico de suelo local.
   - **Media:** Carta INTA 1:100.000 / HYSOGs250m regional.
   - **Baja:** Parámetro por omisión sin confirmación edafológica en zona de médanos o salitrales.

3. **Confianza de la Precipitación ($C_{\text{lluvia}}$):**
   - **Alta:** Pluviómetro local registrado en el campo con serie temporal horaria.
   - **Media:** Curva IDF regional (INA/CONICET transpuesta) para tormenta de diseño.
   - **Baja:** Datos satelitales globales de baja resolución espacial (~55 km NASA POWER / GPCP) para tormentas convectivas puntuales.

### 3.2 Resultado y Exposición
- Se devuelve un objeto estructurado:
  ```json
  {
    "level": "medio",
    "score": 0.68,
    "reasons": [
      "Relieve Copernicus 30 m (error vertical ±2 m en llanura)",
      "Curva IDF regional transpuesta (error típico ±20%)",
      "Suelo grupo B inferido por carta INTA regional"
    ],
    "relief_note": "Copernicus GLO-30 (30 m)",
    "soil_note": "Carta INTA 1:100.000",
    "rain_note": "Diseño regional IDF INA"
  }
  ```
- En la interfaz: aparece un chip sutil en el encabezado del Paso 3:
  `[ Indicador de confianza: Medio · DEM 30 m ]`
  Al hacer clic, abre un desplegable técnico con los 3 motivos explicados sin tecnicismos oscuros.

---

## 4. Comparar Escenarios (`feat/comparar-escenarios`)

### 4.1 Contrato del Endpoint de Comparación
`GET /api/fields/{id}/scenarios/compare?run_a_id={id}&run_b_id={id}`

**Respuesta (`ScenarioComparisonOut`):**
```json
{
  "run_a_id": "...",
  "run_a_name": "80 mm · Siembra Directa continua",
  "run_b_id": "...",
  "run_b_name": "80 mm · Convencional con labranza",
  "delta_precipitation_mm": 0.0,
  "delta_runoff_volume_m3": -12450.0,
  "delta_runoff_pct": -14.2,
  "delta_ponded_area_ha": -2.8,
  "delta_soil_loss_t_ha": -5.3,
  "summary_text": "La Siembra Directa retiene 12.450 m³ más de agua en el suelo y reduce la pérdida de suelo en 5,3 t/ha respecto a la labranza convencional."
}
```

### 4.2 Interfaz Comparativa (SDD-002)
- En el Paso 3 (Resultado), se incorpora una acción secundaria: `"Comparar con otro manejo o lluvia"`.
- Al activarse, se despliega una vista en 2 columnas (o panel comparativo) con:
  - Selector del escenario de referencia (Run A) y del escenario a comparar (Run B).
  - Tarjetas de delta con cifras tabulares:
    - $\Delta$ Superficie anegable: `-2,8 ha`
    - $\Delta$ Escurrimiento fuera: `-14 %`
    - $\Delta$ Pérdida de suelo USLE: `-5,3 t/ha`
  - Resumen agronómico accionable en lenguaje de campo.

---

## 5. Criterios de Aceptación Técnicos

1. **Entorno del Lote:**
   - [ ] Procesamiento de lote con buffer de 300 m y 500 m funcional en backend y CLI.
   - [ ] `external_runoff_inflow_m3` cuantificado y probado en tests offline.
   - [ ] Atenuación visual del buffer en el visor 3D para destacar los límites del lote.

2. **Indicador de Confianza:**
   - [ ] Función de cálculo de confianza determinística y documentada.
   - [ ] Pruebas unitarias que verifican nivel `bajo` en pendientes $< 0.3\%$ con DEM 30 m y nivel `medio`/`alto` en condiciones favorables.
   - [ ] Componente visual de confianza integrado en el Paso 3 sin romper el presupuesto de botones.

3. **Comparador de Escenarios:**
   - [ ] Endpoint `/scenarios/compare` con cálculo de deltas verificado en `pytest`.
   - [ ] Interfaz comparativa integrada en el frontend, responsiva y sin desborde a 360 px.
   - [ ] 0 emojis en los nuevos textos e interfaces.
   - [ ] 100% de la suite de tests en verde (`pytest -q` y `npm run build`).

---

## 6. Plan de Ejecución de Tareas (Etapa 2)

| Tarea | Rama | Descripción | Criterio de Término |
|---|---|---|---|
| **2.1** | `docs/spec-003` | Escribir y validar la Spec 003 | Spec aprobada |
| **2.2** | `feat/entorno-lote` | Cuantificación de escorrentía entrante y buffer 300–500 m | `inflow_m3` verificado con tests |
| **2.3** | `feat/indicador-confianza` | Cálculo y visualización del indicador de confianza | Chip visible con justificación |
| **2.4** | `feat/comparar-escenarios` | Comparador numérico y visual de escenarios | Deltas en ha, % y t/ha |
