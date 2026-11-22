"""Offline E2E fixtures: loopback-aware socket guard, MockTransport, and FileStore isolation."""

from __future__ import annotations

import json
import math
import socket
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from geoprocessing import net as geonet
from services.api.app.core import config
from services.api.app.main import app
from services.api.app.services import hydrology, store, terrain
from tests.e2e.fixtures import (
    build_copernicus_mock_cog_bytes,
    build_sentinel2_mock_cog_bytes,
    synthetic_square_field_geojson,
    write_sloped_plane_dem,
)

ALLOWED_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", ""}
AF_UNIX = getattr(socket, "AF_UNIX", None)

# Session-cached mock raster bytes so tests execute rapidly
_COG_CACHE: dict[str, bytes] = {}


def _get_cached_bytes(key: str) -> bytes:
    if key not in _COG_CACHE:
        if key.startswith("COP:"):
            _COG_CACHE[key] = build_copernicus_mock_cog_bytes(key.split(":", 1)[1])
        elif key == "S2:B04":
            _COG_CACHE[key] = build_sentinel2_mock_cog_bytes("B04")
        elif key == "S2:B08":
            _COG_CACHE[key] = build_sentinel2_mock_cog_bytes("B08")
        elif key == "S2:SCL":
            _COG_CACHE[key] = build_sentinel2_mock_cog_bytes("SCL")
        elif key == "S2:B04_CLOUDY":
            _COG_CACHE[key] = build_sentinel2_mock_cog_bytes("B04", cloudy=True)
        elif key == "S2:B08_CLOUDY":
            _COG_CACHE[key] = build_sentinel2_mock_cog_bytes("B08", cloudy=True)
        elif key == "S2:SCL_CLOUDY":
            _COG_CACHE[key] = build_sentinel2_mock_cog_bytes("SCL", cloudy=True)
        elif key == "S2:B04_PARTIAL":
            _COG_CACHE[key] = build_sentinel2_mock_cog_bytes("B04", partial_cloud=True)
        elif key == "S2:B08_PARTIAL":
            _COG_CACHE[key] = build_sentinel2_mock_cog_bytes("B08", partial_cloud=True)
        elif key == "S2:SCL_PARTIAL":
            _COG_CACHE[key] = build_sentinel2_mock_cog_bytes("SCL", partial_cloud=True)
    return _COG_CACHE[key]


def _extract_host(address) -> str | None:
    if isinstance(address, tuple) and len(address) >= 1:
        return str(address[0])
    if isinstance(address, str):
        return address
    return None


@pytest.fixture(autouse=True)
def offline_socket_and_gdal_guard(monkeypatch: pytest.MonkeyPatch):
    """Fail immediately on any non-loopback network connection or DNS lookup."""
    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_create_connection = socket.create_connection
    orig_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self, address):
        if AF_UNIX is not None and self.family == AF_UNIX:
            return orig_connect(self, address)
        host = _extract_host(address)
        if host not in ALLOWED_LOOPBACK_HOSTS:
            raise AssertionError(f"Offline E2E guard blocked socket.connect({address!r})")
        return orig_connect(self, address)

    def guarded_connect_ex(self, address):
        if AF_UNIX is not None and self.family == AF_UNIX:
            return orig_connect_ex(self, address)
        host = _extract_host(address)
        if host not in ALLOWED_LOOPBACK_HOSTS:
            raise AssertionError(f"Offline E2E guard blocked socket.connect_ex({address!r})")
        return orig_connect_ex(self, address)

    def guarded_create_connection(address, *args, **kwargs):
        host = _extract_host(address)
        if host not in ALLOWED_LOOPBACK_HOSTS:
            raise AssertionError(f"Offline E2E guard blocked socket.create_connection({address!r})")
        return orig_create_connection(address, *args, **kwargs)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host not in ALLOWED_LOOPBACK_HOSTS and host is not None:
            raise AssertionError(f"Offline E2E guard blocked socket.getaddrinfo({host!r})")
        return orig_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)

    monkeypatch.setenv("GDAL_HTTP_ENABLED", "NO")
    monkeypatch.setenv("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", "")
    monkeypatch.setenv("GDAL_HTTP_MAX_RETRY", "0")


class MockNetworkController:
    """Mutable controller for switching mocked NASA/STAC/Copernicus fault modes inside a test."""

    def __init__(self) -> None:
        self.nasa_mode: str = "ok"  # ok | down | timeout | bad_json | fill_999
        self.stac_mode: str = "ok"  # ok | down | empty | cloudy | partial_cloud
        self.copernicus_mode: str = "ok"  # ok | 404 | xml_missing
        self.requests: list[tuple[str, str]] = []


def _byte_range_response(request: httpx.Request, data: bytes) -> httpx.Response:
    size = len(data)
    if request.method == "HEAD":
        return httpx.Response(
            200,
            headers={
                "Content-Length": str(size),
                "Accept-Ranges": "bytes",
                "Content-Type": "image/tiff",
            },
        )
    rng = request.headers.get("range") or request.headers.get("Range")
    if rng and rng.startswith("bytes="):
        spec = rng.split("=", 1)[1]
        start_s, end_s = spec.split("-", 1)
        start = int(start_s)
        end = min(int(end_s) if end_s else size - 1, size - 1)
        chunk = data[start : end + 1]
        return httpx.Response(
            206,
            content=chunk,
            headers={
                "Content-Range": f"bytes {start}-{end}/{size}",
                "Content-Length": str(len(chunk)),
                "Accept-Ranges": "bytes",
            },
        )
    return httpx.Response(200, content=data, headers={"Content-Length": str(size)})


def _build_nasa_power_payload(start_str: str, end_str: str, lat: float, lon: float, fill_999: bool) -> dict:
    try:
        d_start = datetime.strptime(start_str, "%Y%m%d").date()
        d_end = datetime.strptime(end_str, "%Y%m%d").date()
    except ValueError:
        d_end = date(2025, 12, 31)
        d_start = date(2023, 1, 1)

    if (d_end - d_start).days > 1500:
        d_start = d_end - timedelta(days=1095)

    p_map: dict[str, float] = {}
    tmin_map: dict[str, float] = {}
    tmax_map: dict[str, float] = {}
    tmean_map: dict[str, float] = {}

    rng = np.random.default_rng(abs(int(round(lon * 1000)) ^ int(round(lat * 1000))) + 42)
    cur = d_start
    while cur <= d_end:
        key = cur.strftime("%Y%m%d")
        if fill_999:
            p_map[key] = -999.0
            tmin_map[key] = -999.0
            tmax_map[key] = -999.0
            tmean_map[key] = -999.0
        else:
            doy = cur.timetuple().tm_yday
            # Southern hemisphere seasonal cycle: warm Jan (doy~15), cold Jul (doy~195)
            seasonal = math.cos(2.0 * math.pi * (doy - 15) / 365.25)
            tmean = 16.5 + 8.5 * seasonal
            tmin = tmean - 7.5 + float(rng.normal(0.0, 2.2))
            tmax = tmean + 8.0 + float(rng.normal(0.0, 2.0))
            # Force realistic frosts in winter & convective storms in warm season
            if cur.month in (6, 7, 8) and cur.day in (5, 12, 19, 25):
                tmin = -1.8
            elif cur.month in (5, 9) and cur.day == 15:
                tmin = 2.1
            if cur.month in (1, 2, 3, 11, 12) and cur.day in (10, 22):
                precip = 42.0 + float(rng.uniform(0.0, 35.0))
            elif cur.month in (1, 2, 3, 10, 11, 12) and cur.day in (8, 9):
                precip = 20.0
            elif cur.month in (4, 5, 10) and cur.day == 14:
                precip = 22.0
            else:
                precip = 0.0
            p_map[key] = round(precip, 2)
            tmin_map[key] = round(tmin, 2)
            tmax_map[key] = round(tmax, 2)
            tmean_map[key] = round(0.5 * (tmin + tmax), 2)
        cur += timedelta(days=1)

    return {
        "type": "Feature",
        "properties": {
            "parameter": {
                "PRECTOTCORR": p_map,
                "T2M_MIN": tmin_map,
                "T2M_MAX": tmax_map,
                "T2M": tmean_map,
            }
        },
    }


@pytest.fixture(autouse=True)
def mock_external_network(monkeypatch: pytest.MonkeyPatch) -> MockNetworkController:
    """Wire httpx.MockTransport onto geoprocessing.net._cliente & client()."""
    ctrl = MockNetworkController()
    if geonet._cliente is not None:
        try:
            geonet._cliente.close()
        except Exception:
            pass
    monkeypatch.setattr(geonet, "_cliente", None)

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        ctrl.requests.append((request.method, url_str))

        # 1. Copernicus GLO-30 COG + ESA XML
        if url_str.startswith("https://copernicus-dem-30m.s3.amazonaws.com/"):
            if ctrl.copernicus_mode == "404":
                return httpx.Response(404)
            if url_str.endswith(".xml"):
                if ctrl.copernicus_mode == "xml_missing":
                    return httpx.Response(404)
                xml = (
                    "<DEM><tsxx_startTime>2011-01-15T00:00:00Z</tsxx_startTime>"
                    "<tsxx_stopTime>2014-12-20T00:00:00Z</tsxx_stopTime></DEM>"
                )
                return httpx.Response(200, text=xml, headers={"Content-Type": "application/xml"})
            if "S34_00_W066_00" in url_str:
                return _byte_range_response(request, _get_cached_bytes("COP:S34_00_W066_00"))
            if "S34_00_W067_00" in url_str:
                return _byte_range_response(request, _get_cached_bytes("COP:S34_00_W067_00"))
            return httpx.Response(404)

        # 2. NASA POWER daily JSON
        if url_str.startswith("https://power.larc.nasa.gov/api/temporal/daily/point"):
            if ctrl.nasa_mode == "down":
                return httpx.Response(503, json={"error": "NASA POWER unavailable"})
            if ctrl.nasa_mode == "timeout":
                raise httpx.ConnectTimeout("Simulated NASA POWER timeout", request=request)
            if ctrl.nasa_mode == "bad_json":
                return httpx.Response(200, text="NOT_JSON{{{", headers={"Content-Type": "application/json"})
            params = request.url.params
            payload = _build_nasa_power_payload(
                start_str=params.get("start", "20230101"),
                end_str=params.get("end", "20251231"),
                lat=float(params.get("latitude", -33.3)),
                lon=float(params.get("longitude", -65.7)),
                fill_999=(ctrl.nasa_mode == "fill_999"),
            )
            return httpx.Response(200, json=payload)

        # 3. Element84 Sentinel-2 L2A STAC search
        if url_str.startswith("https://earth-search.aws.element84.com/v1/search"):
            if ctrl.stac_mode == "down":
                return httpx.Response(503, json={"error": "STAC unavailable"})
            if ctrl.stac_mode == "empty":
                return httpx.Response(200, json={"type": "FeatureCollection", "features": []})
            cloud_pct = 99.5 if ctrl.stac_mode == "cloudy" else (48.0 if ctrl.stac_mode == "partial_cloud" else 4.2)
            return httpx.Response(
                200,
                json={
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "id": "S2A_MSIL2A_20260115_MOCK_SAN_LUIS",
                            "properties": {
                                "datetime": "2026-01-15T14:20:00Z",
                                "eo:cloud_cover": cloud_pct,
                            },
                            "assets": {
                                "red": {"href": "https://mock-sentinel.local/B04.tif"},
                                "nir": {"href": "https://mock-sentinel.local/B08.tif"},
                                "scl": {"href": "https://mock-sentinel.local/SCL.tif"},
                            },
                        }
                    ],
                },
            )

        # 4. Sentinel-2 mock COG assets
        if url_str.startswith("https://mock-sentinel.local/"):
            suffix = ""
            if ctrl.stac_mode == "cloudy":
                suffix = "_CLOUDY"
            elif ctrl.stac_mode == "partial_cloud":
                suffix = "_PARTIAL"
            if url_str.endswith("B04.tif"):
                return _byte_range_response(request, _get_cached_bytes(f"S2:B04{suffix}"))
            if url_str.endswith("B08.tif"):
                return _byte_range_response(request, _get_cached_bytes(f"S2:B08{suffix}"))
            if url_str.endswith("SCL.tif"):
                return _byte_range_response(request, _get_cached_bytes(f"S2:SCL{suffix}"))
            return httpx.Response(404)

        raise AssertionError(f"Unexpected outbound HTTP request in offline E2E test: {request.method} {url_str}")

    mock_client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    monkeypatch.setattr(geonet, "_cliente", mock_client)
    monkeypatch.setattr(geonet, "client", lambda: mock_client)

    yield ctrl

    mock_client.close()
    monkeypatch.setattr(geonet, "_cliente", None)


def _clear_service_caches() -> None:
    terrain._cargar.cache_clear()
    hydrology.load_hydrology_grids.cache_clear()
    hydrology.load_active_runoff_grids.cache_clear()


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolated FastAPI TestClient writing only into tmp_path/runs."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ROTATERRA_DATA_DIR", str(runs_dir))
    monkeypatch.setattr(config, "DATA_DIR", runs_dir)
    monkeypatch.setattr(store, "DATA_DIR", runs_dir)
    _clear_service_caches()

    with TestClient(app) as client:
        yield client

    _clear_service_caches()


@pytest.fixture()
def field_with_sloped_dem(api_client: TestClient, tmp_path: Path) -> tuple[str, dict]:
    """Helper fixture: imports synthetic square field and uploads a 20m sloped plane DEM."""
    geojson_bytes = json.dumps(synthetic_square_field_geojson()).encode("utf-8")
    r_imp = api_client.post(
        "/api/v1/fields/import",
        files={"file": ("lote.geojson", geojson_bytes, "application/geo+json")},
        data={"default_name": "Lote Plano Inclinado"},
    )
    assert r_imp.status_code == 201, r_imp.text
    field = r_imp.json()["fields"][0]
    field_id = field["id"]

    dem_path = write_sloped_plane_dem(tmp_path / "sloped_20m.tif", pixel_m=20.0, width=110, height=110)
    with dem_path.open("rb") as fh:
        r_ter = api_client.post(
            f"/api/v1/fields/{field_id}/terrain/process",
            files={"file": ("sloped_20m.tif", fh, "image/tiff")},
            data={
                "source_id": "upload",
                "buffer_m": "200",
                "source_name": "DEM Sintético Plano 20m",
                "surface_type": "DTM",
                "vertical_datum": "SRVN16",
                "vertical_accuracy_m": "0.1",
                "acquisition_date": "2026-01-10",
                "acquisition_method": "Levantamiento sintético E2E",
            },
        )
    assert r_ter.status_code == 200, r_ter.text

    # Perfil de suelo de referencia para USLE
    (store.field_dir(field_id) / "soil.json").write_text(
        json.dumps({
            "soil_group": "B",
            "texture_class": "franco",
            "sand_pct": 40.0,
            "silt_pct": 40.0,
            "clay_pct": 20.0,
            "quality": "confiable",
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return field_id, field
