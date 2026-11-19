"""Acceso HTTP a COG remotos usando el almacén de certificados del sistema operativo.

Motivo: en equipos con antivirus que inspeccionan TLS (p. ej. Avast Web Shield) el curl interno de GDAL
rechaza la cadena de certificados aunque Windows la considere válida. Se lee el COG por rangos HTTP
con httpx + truststore (que valida contra el almacén del sistema) y se lo entrega a rasterio mediante
su parámetro `opener`. La verificación TLS nunca se desactiva.
"""

from __future__ import annotations

import io
import ssl
import threading

import httpx

BLOQUE = 512 * 1024  # bytes por pedido de rango
MAX_BLOQUES = 256  # caché en memoria por archivo (~128 MB como máximo)

_cliente: httpx.Client | None = None
_lock = threading.Lock()


def ssl_context() -> ssl.SSLContext | bool:
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:  # sin truststore se usa el bundle de certifi (verificación activa igual)
        return True


def client() -> httpx.Client:
    global _cliente
    with _lock:
        if _cliente is None:
            _cliente = httpx.Client(verify=ssl_context(), timeout=60, follow_redirects=True,
                                    headers={"User-Agent": "Complemento-a-RotaTerra/fase0"})
        return _cliente


class HttpRangeFile(io.RawIOBase):
    """Archivo remoto de solo lectura, con seek y lectura por rangos HTTP cacheados en bloques."""

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        r = client().head(url)
        if r.status_code == 404:
            raise FileNotFoundError(url)
        r.raise_for_status()
        self.size = int(r.headers["content-length"])
        self.pos = 0
        self._bloques: dict[int, bytes] = {}

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        self.pos = max(0, base + offset)
        return self.pos

    def _bloque(self, i: int) -> bytes:
        if i not in self._bloques:
            if len(self._bloques) >= MAX_BLOQUES:
                self._bloques.pop(next(iter(self._bloques)))
            inicio = i * BLOQUE
            fin = min(inicio + BLOQUE, self.size) - 1
            r = client().get(self.url, headers={"Range": f"bytes={inicio}-{fin}"})
            r.raise_for_status()
            self._bloques[i] = r.content
        return self._bloques[i]

    def readinto(self, buffer) -> int:
        n = min(len(buffer), self.size - self.pos)
        if n <= 0:
            return 0
        copiado = 0
        while copiado < n:
            i, desde = divmod(self.pos, BLOQUE)
            datos = self._bloque(i)[desde:desde + n - copiado]
            buffer[copiado:copiado + len(datos)] = datos
            copiado += len(datos)
            self.pos += len(datos)
        return n


def http_opener(path: str, mode: str = "rb"):
    """Opener para rasterio.open(url, opener=http_opener)."""
    if "r" not in mode:
        raise ValueError("Solo lectura")
    return io.BufferedReader(HttpRangeFile(path), buffer_size=64 * 1024)
