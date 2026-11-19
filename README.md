# Complemento a RotaTerra — Visor 3D de Lotes e Hidrología (Fase 0 + Fase 1)

Módulo web geoespacial para **RotaTerra** orientado a la visualización 3D del relieve parcelario, control de calidad de Modelos Digitales de Elevación (MDE/MDT), inspección puntual de cota/pendiente, perfiles altimétricos e **hidrología estática** (acondicionamiento selectivo de depresiones, dirección D8, acumulación difusa MFD, curvas de nivel, rutas potenciales de drenaje, puntos de salida y subcuencas).

> **Estado actual:** **Fase 0 + Fase 1 — Análisis topográfico e hidrología estática** (SDD §14).  
> - **Fase 0:** importación y validación de lotes GeoJSON en CRS métrico UTM, descarga por ventana de **Copernicus DEM GLO-30 (30 m)** o subida de **GeoTIFF propio** (Dron/LiDAR/IGN 5 m), informe de calidad y advertencias de escala, escena 3D con **MapLibre GL JS + Three.js**, inspección puntual y perfil altimétrico.  
> - **Fase 1:** acondicionamiento hidrológico selectivo (`fill_small` / `preserve` / `fill_all` + *burn-in* sin alterar el DEM original), sombreado analítico (*hillshade*), curvas de nivel vectoriales, dirección **D8**, acumulación **MFD** (Quinn et al. 1991) con verificación de balance de masa, identificación de depresiones/bajos con volumen y profundidad, red de drenaje potencial con umbral configurable, puntos de salida del lote y subcuencas.  
> - **Pendiente para Fases 2 a 4:** eventos de lluvia, escorrentía NRCS-CN, hietogramas y simulación hidrodinámica 2D.

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
```

---

## Documentación técnica

- [Arquitectura de Fase 0](docs/architecture.md)
- [Fuentes de datos y jerarquía de DEM](docs/data-sources.md)
- [Limitaciones del modelo y advertencias de escala](docs/model-limitations.md)
- [Informe de decisiones técnicas — Fase 0](docs/decisiones-fase0.md)
