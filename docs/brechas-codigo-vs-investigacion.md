# Brechas: código actual de Complemento a RotaTerra vs. investigación

**Fecha:** 19/11/2026 · **Base:** `main` de `hernanfirmapaz-ops/Complemento-a-RotaTerra` (21 tests verdes, build web OK) contra `01-investigacion-escurrimiento.md`.

## Anomalías críticas (resolver primero)

| # | Hallazgo | Dónde | Riesgo | Acción |
|---|---|---|---|---|
| A1 | **Respaldo climático sintético con números aleatorios.** Sin conexión a NASA POWER, genera lluvia y temperaturas con `numpy.random` y las etiqueta "Serie Climatológica Regional Calibrada" | `geoprocessing/satellite/nasa_power_imerg.py` (≈ líneas 100–137) | Viola la regla de N4-4-1.2 "nunca inventar un valor". El nombre sugiere datos calibrados que no existen | Eliminar del camino productivo. Sin red → `valor: null` + `calidad: "descartada"` + motivo. Mover el generador a `tests/fixtures` |
| A2 | **Manning uniforme en la simulación 2D.** Existe la tabla `MANNING_N_BY_COVER`, pero el solver recibe un único `manning_n` y llena la grilla con ese valor | `geoprocessing/hydrology/shallow_water_2d.py` (`n_grid = np.full(...)`) | No representa la mezcla de coberturas del lote | Aceptar grilla de Manning por celda desde la capa de cobertura |
| A3 | **Única fuente de relieve: Copernicus GLO-30 (DSM).** Incluye cortinas forestales, galpones y silos | `geoprocessing/dem/sources.py` | Barreras y depresiones falsas en llanura | Sumar MDT 5 m IGN → MDE-Ar v2.1 → COP30 → NASADEM |
| A4 | **Sin módulo de napa freática** (solo menciones en textos de zonificación) | `geoprocessing/agronomy/zonation.py` | En Villa Mercedes el anegamiento es mayormente freático: el simulador lo subestima | Modo estacional con profundidad de napa del productor |

## Matriz de cumplimiento

| Tema | Recomendación de la investigación | Estado actual | Brecha |
|---|---|---|---|
| Fuente de relieve | MDT 5 m IGN; respaldos MDE-Ar v2.1, COP30, NASADEM | Solo COP30 (AWS) | **Alta** |
| Datum vertical | Declararlo siempre (SRVN16 / EGM2008 / EGM96) | `quality.py` avisa si falta | Baja: cargar el datum correcto por fuente |
| Suavizado previo | Feature-preserving smoothing | No existe | Media |
| Acondicionamiento | *Breaching* de menor costo + relleno remanente; conservar bajos reales | Priority-Flood + ε con modo `fill_small` (umbral de profundidad y área) + quema de líneas | Media: falta *breaching*. El umbral de relleno pequeño va en la dirección correcta |
| Dos MDE (acondicionado / mínimamente tocado) | Uno para flujo, otro para el 2D | El servicio llama a `condition_dem`; no está claro qué grilla recibe el 2D | **Verificar** |
| Dirección de flujo | D∞ para TWI/SPI, D8 para red | D8 + MFD (Quinn 1991) | Baja: MFD es aceptable |
| Motor 2D | Inercial local (Bates 2010 / de Almeida 2012) o Landlab `OverlandFlow` | Onda difusiva + Manning con tope de Froude ≤ 1,2 | Media: validar contra Landlab o LISFLOOD-FP antes de reemplazar |
| Curva Número | Tabla NRCS, CN editable, banda ±5, aviso de calibración pampeana (CN 82 en SD) | Tabla TR-55 + ajustes + AMC I/III | Media: banda de sensibilidad, aviso y AMC desde SMAP |
| Grupo hidrológico | Carta INTA + SISINTA; respaldo HYSOGs250m (NASA) | No hay fuente de suelos | **Alta** |
| Lluvia de diseño | IDF DIT regional (INA/CONICET), bloques alternos, T2–T100, rótulo ±20% | Lámina de diseño manual (`design_storm_mm`) + CSV | **Alta** |
| Lluvia real | Pluviómetro del productor; IMERG para el volumen | CSV validado; IMERG solo mencionado | Media: conector IMERG (reusar N4) |
| Erosión R anual | R = 0,2266·PMA^1,1289 (INTA, Gaitán 2017) | EI30 por tormenta | Media: sumar R anual para la comparación de rotaciones |
| Factor K | Wischmeier sobre perfiles SISINTA | Sin fuente de suelos | Alta (depende de suelos) |
| Erosión eólica | Índice RWEQ simplificado (fase posterior) | No existe | Baja (fase 8) |
| Validación de anegamientos | OPERA DSWx-HLS/S1, índice F | No existe | Media |
| Contrato de datos | `Observacion` de N4-4-1.2 + `raster_ref` | Schemas propios | Media: alinear para integrarse con Rotaterra |
| Advertencias en la UI | 5 textos fijos de limitación | Avisos de calidad del MDE | Media |

## Lo que ya está bien

| Tema | Detalle |
|---|---|
| Metadatos obligatorios del MDE | Fuente, datum, precisión vertical y fecha (`dem/sources.py`, `dem/quality.py`) |
| Catálogo de depresiones | Profundidad, área y volumen por depresión |
| Estructuras hidráulicas | Alcantarillas y canales sobre el terreno |
| Balance de masa en CN | Verifica P = Ia + F + Q |
| Validación de CSV de lluvia | Zona horaria, intervalos y metadatos |
| Tests | 21 tests sin red, en verde |
