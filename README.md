# Complemento a RotaTerra — Visor 3D de Lotes e Hidrología (Fases 0 a 5 · Suite Completa)

Módulo web geoespacial para **RotaTerra** orientado a la visualización 3D del relieve parcelario, control de calidad de Modelos Digitales de Elevación (MDE/MDT), inspección puntual de cota/pendiente, perfiles altimétricos, **hidrología estática** (acondicionamiento selectivo de depresiones, dirección D8, acumulación difusa MFD, índices topográficos **TWI** y **SPI**, curvas de nivel, rutas potenciales de drenaje, puntos de salida y subcuencas), **estimación de escorrentía por evento** (carga manual y CSV temporal de lluvias, modelo **NRCS Curve Number** y comparación de escenarios), **animación temporal por intervalos del hietograma** con partículas 3D, **solver hidrodinámico 2D de onda difusiva con ley de Manning (`water_depth_m` y `velocity_m_s`)** e **integración hidro-agronómica con RotaTerra** (zonificación en 4 ambientes, riesgo de transitabilidad de maquinaria y criterios para rotación trienal).

> **Estado actual:** **Fases 0, 1, 2, 3, 4 y 5 implementadas según el SDD**.  
> - **Fase 0:** importación y validación de lotes en **GeoJSON, KML, KMZ y Shapefile `.zip`** en CRS métrico UTM, descarga por ventana de **Copernicus DEM GLO-30 (30 m)** o subida de **GeoTIFF propio** (Dron/LiDAR/IGN 5 m), informe de calidad y advertencias de escala, escena 3D con **MapLibre GL JS + Three.js**, inspección puntual y perfil altimétrico.  
> - **Fase 1:** acondicionamiento hidrológico selectivo (`fill_small` / `preserve` / `fill_all` + *burn-in* sin alterar el DEM original), sombreado analítico (*hillshade*), curvas de nivel vectoriales, dirección **D8**, acumulación **MFD** (Quinn et al. 1991) con verificación de balance de masa, índices **TWI** (*Topographic Wetness Index*) y **SPI** (*Stream Power Index*), identificación de depresiones/bajos, red de drenaje potencial, puntos de salida y subcuencas.  
> - **Fase 2:** registro manual de lluvias e importación/validación de series temporales CSV (`timestamp,precipitation_mm,interval_minutes,station_id`), metadatos obligatorios de fuente/incertidumbre, parametrización edáfica y de cobertura/manejo (grupos A–D, AMC I/II/III, $\lambda$), cálculo de escorrentía directa **NRCS Curve Number ($S, I_a, F, Q$)** combinada con MFD y comparador lado a lado entre escenarios (CU-04).  
> - **Fase 3:** tránsito temporal por intervalos sobre el hietograma con balance de masa estricto paso a paso, reproductor de línea de tiempo (play/pause/velocidad/slider), partículas 3D vinculadas a las rutas calculadas, registro de observaciones reales de campo y estructuras hidráulicas (CU-06), y exportación de paquete GeoJSON e informe técnico HTML/PDF.  
> - **Fase 4:** solver hidrodinámico 2D de onda difusiva con ley de Manning ($n$ parametrizado por cobertura/rastrojo y apertura de alcantarillas/canales relevados) que resuelve `water_depth_m` y `velocity_m_s` verificando conservación de volumen.  
> - **Fase 5:** clasificación automática del lote en 4 **ambientes hidro-agronómicos** (*Loma bien drenada*, *Media loma*, *Vía de escurrimiento concentrado* y *Bajo receptor anegable*), estimación de días de espera de transitabilidad de maquinaria post-lluvia y criterios multicriterio para el planificador trienal de **RotaTerra**.  
> - **Suite de 8 Herramientas Complementarias RotaTerra (`/api/v1/fields/{id}/hydrology/toolkit/run`)**:
>   1. **Erosión en escurrimiento (USLE/RUSLE + focos de cárcavas)** sobre el relieve UTM + mapa 3D de pérdida de suelo (`t/ha`).
>   2. **Balance hídrico mensual del lote** (12 meses con datos diarios de **NASA POWER**: lluvia, $ET_0$, agua útil, meses de déficit y exceso).
>   3. **Riesgo de anegamiento por fecha con lluvias reales** (tormentas reales con ajuste de humedad antecedente de 5 días previos AMC I/II/III).
>   4. **Curvas de nivel y Terrazas** (trazado automático de terrazas a nivel en el lote y simulación antes vs. después: $\text{m}^3$ de agua frenada, % reducción de escorrentía y toneladas de suelo ahorradas).
>   5. **Calculadora de Siembra y Fertilizante (Tablas INTA)** según cultivo, ambiente del lote y rinde objetivo (`pl/ha`, `sem/m`, `kg/ha`, bolsas comerciales y `N-P2O5-S` / guía MAP, Urea, Yeso).
>   6. **Comparador de Rotaciones Trienales (3 años)** lado a lado (escurrimiento acumulado, erosión USLE en `t/ha` y cobertura entre 2 secuencias).
>   7. **Monitor de Vigor (NDVI)** conectando al catálogo público **STAC de Sentinel-2 L2A (COG 10 m en AWS Element84 Earth Search, sin necesitar Google Earth Engine)** + mapa 3D de NDVI y cruce de zonas débiles con bajos anegables y vías erosivas.
>   8. **Riesgo de Heladas y Fechas Seguras de Siembra** (**NASA POWER `T2M_MIN`**: última helada primaveral, primera otoñal, período libre de heladas y ventana segura por cultivo).

---

## Estructura del repositorio

```text
Complemento-a-RotaTerra/
├── apps/
│   └── web/                  # Frontend React 19 + TypeScript + Vite + MapLibre GL JS + Three.js
├── services/
│   └── api/                  # API REST FastAPI (/api/v1) + tests de integración
├── geoprocessing/            # Librería geoespacial Python (CRS UTM, lotes, DEM, calidad, terreno)
│   ├── dem/
│   └── tests/                # Fixtures de DEM sintéticos etiquetados y tests unitarios
├── data/
│   └── sample/               # Lote real de muestra (Catastro San Luis, Parcela Rural 205)
└── docs/
    ├── architecture.md
    ├── data-sources.md
    ├── model-limitations.md
    └── decisiones-fase0.md   # Informe de decisiones técnicas de Fase 0
```

---

## Requisitos

- **Python 3.11+** (probado con Python 3.14 en Windows)
- **Node.js 20+** y **npm**

---

## Instalación y ejecución local

### 1. Backend (FastAPI + Geoprocesamiento)

En PowerShell, desde la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000 --reload
```

La API queda disponible en `http://127.0.0.1:8000/api/v1/health` y la documentación interactiva OpenAPI en `http://127.0.0.1:8000/docs`.

### 2. Frontend (React + MapLibre + Three.js)

En otra terminal PowerShell:

```powershell
cd apps\web
npm install
npm run dev
```

Abrir `http://localhost:5173` en el navegador. Vite redirige automáticamente `/api/*` a `http://127.0.0.1:8000`.

---

## Ejecución de pruebas automatizadas

```powershell
# Tests unitarios de geoprocesamiento y tests de integración de la API (usa DEM sintéticos etiquetados)
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe -m pytest -v geoprocessing/tests services/api/tests

# Verificación de tipos y build de producción del frontend
cd apps\web
npm run build
cd ..

# Linter de código Python con Ruff
python -m ruff check .

# Opcional: pre-commit para revisión automática antes de cada commit
pip install pre-commit
pre-commit install
```

---

## Documentación técnica

- [Arquitectura de Fase 0](docs/architecture.md)
- [Fuentes de datos y jerarquía de DEM](docs/data-sources.md)
- [Limitaciones del modelo y advertencias de escala](docs/model-limitations.md)
- [Informe de decisiones técnicas — Fase 0](docs/decisiones-fase0.md)
