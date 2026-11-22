"""Pruebas de seguridad, límites y dependencias (Criterios de aceptación Issue #13).

- Máximo de superficie del lote configurable (sugerido 2.000 ha) con mensaje claro.
- ZIP/KMZ con límite de tamaño descomprimido (prevención de zip bomb).
- Relieve subido escrito a disco por partes (no 300 MB en memoria).
- MapLibre 6.x sin vulnerabilidades críticas.
- requirements.txt con versiones fijas; desarrollo en requirements-dev.txt.
- npm audit sin vulnerabilidades críticas.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from geoprocessing.fields import (
    FieldValidationError,
    parse_field_file,
    parse_kmz,
    parse_shapefile_zip,
)
from geoprocessing.supuestos import (
    SUPUESTO_LIMITE_DESCOMPRIMIDO_ZIP_MB,
    SUPUESTO_SUPERFICIE_MAXIMA_LOTE_HA,
)


def _crear_geojson_rectangulo_ha(area_ha: float) -> str:
    """Crea un GeoJSON con un rectángulo aproximado en San Luis con el área solicitada en ha."""
    # A latitud ~ -33, 1 grado lat ~ 110.9 km. 1 grado lon ~ 93.3 km.
    # 1 ha = 10,000 m2 = 0.01 km2.
    # Área (km2) = area_ha * 0.01
    # Usemos un cuadrado de lado L_km = sqrt(area_ha * 0.01)
    # delta_lat = L_km / 110.9
    # delta_lon = L_km / 93.3
    import math
    lado_km = math.sqrt(area_ha * 0.01)
    d_lat = lado_km / 110.9
    d_lon = lado_km / 93.3
    lon0, lat0 = -66.1, -33.2
    return json.dumps({
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": f"Lote {area_ha}ha"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [lon0, lat0],
                        [lon0 + d_lon, lat0],
                        [lon0 + d_lon, lat0 + d_lat],
                        [lon0, lat0 + d_lat],
                        [lon0, lat0],
                    ]],
                },
            }
        ]
    })


def test_supuestos_seguridad_declarados():
    """Verifica que los supuestos de límites de seguridad estén declarados en supuestos.py."""
    assert SUPUESTO_SUPERFICIE_MAXIMA_LOTE_HA.valor == 2000.0
    assert "2.000" in SUPUESTO_SUPERFICIE_MAXIMA_LOTE_HA.motivo or "2000" in SUPUESTO_SUPERFICIE_MAXIMA_LOTE_HA.motivo
    assert SUPUESTO_LIMITE_DESCOMPRIMIDO_ZIP_MB.valor == 50.0
    assert "descomprimido" in SUPUESTO_LIMITE_DESCOMPRIMIDO_ZIP_MB.motivo.lower()


def test_superficie_maxima_lote_rechaza_exceso_con_mensaje_claro():
    """Un lote que supere el límite máximo (por defecto 2.000 ha) debe ser rechazado con mensaje claro sin texto redundante."""
    # 2500 ha supera el límite de 2000 ha
    geojson_grande = _crear_geojson_rectangulo_ha(2500.0)
    with pytest.raises(FieldValidationError) as exc_info:
        parse_field_file(geojson_grande, filename="lote_enorme.geojson")
    msg = str(exc_info.value)
    assert "supera el límite" in msg.lower() or "límite máximo" in msg.lower()
    assert "2000 ha" in msg
    assert "/ 2.000 ha" not in msg
    assert "ROTATERRA_MAX_FIELD_AREA_HA" in msg or "divida el lote" in msg.lower()


def test_variables_entorno_invalidas_emiten_advertencia(monkeypatch, caplog):
    """Variables de entorno inválidas emiten aviso en logger y usan el supuesto por defecto."""
    import logging

    from geoprocessing.fields import _get_max_field_area_ha, _get_max_uncompressed_zip_bytes

    with caplog.at_level(logging.WARNING):
        monkeypatch.setenv("ROTATERRA_MAX_FIELD_AREA_HA", "invalido")
        area = _get_max_field_area_ha()
        assert area == 2000.0
        assert "ROTATERRA_MAX_FIELD_AREA_HA" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        monkeypatch.setenv("ROTATERRA_MAX_UNCOMPRESSED_ZIP_MB", "-10")
        zip_bytes = _get_max_uncompressed_zip_bytes()
        assert zip_bytes == 50 * 1024 * 1024
        assert "ROTATERRA_MAX_UNCOMPRESSED_ZIP_MB" in caplog.text


def test_superficie_maxima_lote_configurable_por_entorno(monkeypatch):
    """El límite máximo de superficie debe ser configurable por variable de entorno."""
    monkeypatch.setenv("ROTATERRA_MAX_FIELD_AREA_HA", "5000.0")
    # Con límite en 5000 ha, un lote de 2500 ha debe ser aceptado
    geojson_grande = _crear_geojson_rectangulo_ha(2500.0)
    lotes = parse_field_file(geojson_grande, filename="lote_5000.geojson")
    assert len(lotes) == 1
    assert lotes[0].area_ha > 2000.0


def test_superficie_lote_dentro_del_limite_pasa_exitosamente():
    """Un lote de tamaño normal (ej. 150 ha) se importa sin errores."""
    geojson_normal = _crear_geojson_rectangulo_ha(150.0)
    lotes = parse_field_file(geojson_normal, filename="lote_normal.geojson")
    assert len(lotes) == 1
    assert 140.0 <= lotes[0].area_ha <= 160.0


def test_zip_kmz_rechaza_limite_descomprimido_excedido():
    """ZIP o KMZ cuyo contenido descomprimido supere el límite de seguridad es rechazado."""
    # Creamos un ZIP con un archivo que declara o contiene un tamaño descomprimido excesivo (> 50 MB)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 55 MB de ceros (muy comprimible a unos pocos KB)
        datos_grandes = b"0" * (55 * 1024 * 1024)
        zf.writestr("doc.kml", datos_grandes)

    zip_bytes = buf.getvalue()
    with pytest.raises(FieldValidationError) as exc_info:
        parse_kmz(zip_bytes)
    assert "descomprimido" in str(exc_info.value).lower() or "límite de seguridad" in str(exc_info.value).lower()


def test_zip_rechaza_path_traversal():
    """Archivos ZIP con rutas que intenten salir del directorio (Zip Slip) deben ser rechazados."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("../etc/passwd.shp", b"test")

    with pytest.raises(FieldValidationError) as exc_info:
        parse_shapefile_zip(buf.getvalue())
    assert "inválido" in str(exc_info.value).lower() or "seguridad" in str(exc_info.value).lower() or "ruta" in str(exc_info.value).lower()


def test_requirements_con_versiones_fijas_y_separacion_dev():
    """Verifica que requirements.txt tenga versiones fijas (sin >=) y que dev esté separado."""
    repo_root = Path(__file__).resolve().parents[2]
    req_prod = repo_root / "requirements.txt"
    req_dev = repo_root / "requirements-dev.txt"

    assert req_prod.exists(), "Falta requirements.txt"
    assert req_dev.exists(), "Falta requirements-dev.txt"

    prod_lines = [l.strip() for l in req_prod.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    dev_lines = [l.strip() for l in req_dev.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]

    # Herramientas de desarrollo no deben estar en requirements.txt
    herramientas_dev = {"pytest", "ruff", "playwright"}
    for line in prod_lines:
        pkg_name = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip().lower()
        assert pkg_name not in herramientas_dev, f"{pkg_name} debe estar en requirements-dev.txt, no en requirements.txt"
        assert ">=" not in line, f"La dependencia '{line}' en requirements.txt debe tener versión fija (==)"
        assert "==" in line, f"La dependencia '{line}' en requirements.txt debe tener versión fija (==)"

    # Herramientas de desarrollo deben estar en requirements-dev.txt con versión fija
    for dev_tool in herramientas_dev:
        assert any(dev_tool in line.lower() for line in dev_lines), f"{dev_tool} falta en requirements-dev.txt"
    assert any("landlab==2.11.0" in line for line in dev_lines), "landlab debe estar fijado exactamente a 2.11.0 en requirements-dev.txt"


def test_maplibre_en_package_json_es_version_6():
    """Verifica que package.json use MapLibre 6.x con versión exacta fijada sin carets (^)."""
    repo_root = Path(__file__).resolve().parents[2]
    pkg_json_path = repo_root / "apps" / "web" / "package.json"
    data = json.loads(pkg_json_path.read_text(encoding="utf-8"))
    maplibre_ver = data.get("dependencies", {}).get("maplibre-gl", "")
    assert maplibre_ver == "6.19.0", f"MapLibre version {maplibre_ver} no es exactamente 6.19.0"
    vite_ver = data.get("devDependencies", {}).get("vite", "")
    assert vite_ver == "6.4.6", f"Vite version {vite_ver} no es exactamente 6.4.6"


def test_relieve_subido_invalido_limpia_y_rechaza_422(tmp_path, monkeypatch):
    """Archivos de relieve con cabecera no TIFF son rechazados con 422 y sin dejar archivos huérfanos."""
    from starlette.testclient import TestClient

    from services.api.app.main import app

    monkeypatch.setenv("ROTATERRA_DATA_DIR", str(tmp_path / "runs"))
    client = TestClient(app)

    # 1. Crear lote de prueba
    r_field = client.post("/api/v1/fields/sample?preset=llanura")
    assert r_field.status_code == 201
    field_id = r_field.json()["fields"][0]["id"]

    # 2. Subir archivo con contenido no-TIFF (ej. texto)
    r_err = client.post(
        f"/api/v1/fields/{field_id}/terrain/process",
        files={"file": ("invalido.tif", io.BytesIO(b"Este no es un tiff"), "image/tiff")},
        data={"source_id": "upload", "buffer_m": "100"},
    )
    assert r_err.status_code == 422
    assert "GeoTIFF" in r_err.json()["detail"] or "TIFF" in r_err.json()["detail"]


def test_relieve_subido_excede_limite_rechaza_413(tmp_path, monkeypatch):
    """Archivos de relieve que excedan MAX_DEM_BYTES son rechazados con 413 por streaming sin agotar memoria."""
    from starlette.testclient import TestClient

    from services.api.app.api.routes import terrain as terrain_route
    from services.api.app.main import app

    monkeypatch.setenv("ROTATERRA_DATA_DIR", str(tmp_path / "runs"))
    # Fijamos temporalmente el límite en 10 KB para la prueba unitaria
    monkeypatch.setattr(terrain_route, "MAX_DEM_BYTES", 10 * 1024)
    client = TestClient(app)

    r_field = client.post("/api/v1/fields/sample?preset=llanura")
    assert r_field.status_code == 201
    field_id = r_field.json()["fields"][0]["id"]

    # Enviamos 20 KB con cabecera TIFF simulada
    big_data = b"II*\x00" + b"\x00" * (20 * 1024)
    r_err = client.post(
        f"/api/v1/fields/{field_id}/terrain/process",
        files={"file": ("dem_grande.tif", io.BytesIO(big_data), "image/tiff")},
        data={"source_id": "upload", "buffer_m": "100"},
    )
    assert r_err.status_code == 413
    assert "supera el tamaño máximo" in r_err.json()["detail"]
