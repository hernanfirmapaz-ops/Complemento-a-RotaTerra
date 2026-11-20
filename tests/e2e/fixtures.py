"""Synthetic offline raster, vector, and CSV fixtures for E2E tests.

All generated rasters are explicitly tagged ``SYNTHETIC=TRUE`` and are used
strictly inside ``tests/e2e/`` to exercise the public API and geoprocessing
boundaries without network access.
"""

from __future__ import annotations

import io
import json
import sqlite3
import struct
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely import wkb as shapely_wkb
from shapely.geometry import Polygon

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = REPO_ROOT / "tests" / "fixtures" / "lotes"

WGS84_ESRI_WKT = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)

UTM20S_ESRI_WKT = (
    'PROJCS["WGS_1984_UTM_Zone_20S",GEOGCS["GCS_WGS_1984",'
    'DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
    'PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",500000.0],'
    'PARAMETER["False_Northing",10000000.0],PARAMETER["Central_Meridian",-63.0],'
    'PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",0.0],'
    'UNIT["Meter",1.0]]'
)


# ---------------------------------------------------------------------------
# Vector / Boundary Generators
# ---------------------------------------------------------------------------


def synthetic_square_ring(
    lon0: float = -65.70,
    lat0: float = -33.30,
    d_deg: float = 0.01,
) -> list[list[float]]:
    return [
        [lon0, lat0],
        [lon0 + d_deg, lat0],
        [lon0 + d_deg, lat0 + d_deg],
        [lon0, lat0 + d_deg],
        [lon0, lat0],
    ]


def synthetic_square_field_geojson(
    lon0: float = -65.70,
    lat0: float = -33.30,
    d_deg: float = 0.01,
    name: str = "Lote Sintético de Prueba (NO REAL)",
) -> dict:
    """Square polygon (~100 ha at d_deg=0.01) in EPSG:4326."""
    ring = synthetic_square_ring(lon0=lon0, lat0=lat0, d_deg=d_deg)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": name, "synthetic": True},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        ],
    }


def synthetic_square_with_hole_rings(
    lon0: float = -65.70,
    lat0: float = -33.30,
    d_deg: float = 0.01,
) -> list[list[list[float]]]:
    outer = synthetic_square_ring(lon0=lon0, lat0=lat0, d_deg=d_deg)
    # Interior hole: 30%..70% of outer box (approx 16% of total area), reversed winding
    h0_lon, h1_lon = lon0 + 0.3 * d_deg, lon0 + 0.7 * d_deg
    h0_lat, h1_lat = lat0 + 0.3 * d_deg, lat0 + 0.7 * d_deg
    hole = [
        [h0_lon, h0_lat],
        [h0_lon, h1_lat],
        [h1_lon, h1_lat],
        [h1_lon, h0_lat],
        [h0_lon, h0_lat],
    ]
    return [outer, hole]


def make_kml_bytes(
    rings: list[list[list[float]]] | None = None,
    name: str = "Lote KML Prueba",
    multipolygon: bool = False,
) -> bytes:
    if rings is None:
        rings = [synthetic_square_ring()]

    def _coords_str(ring: list[list[float]]) -> str:
        return " ".join(f"{pt[0]},{pt[1]},0" for pt in ring)

    polygons_xml = [
        f"""
        <Polygon>
          <outerBoundaryIs>
            <LinearRing><coordinates>{_coords_str(rings[0])}</coordinates></LinearRing>
          </outerBoundaryIs>
        </Polygon>
        """
    ]
    if multipolygon:
        ring2 = synthetic_square_ring(lon0=-65.685, lat0=-33.30, d_deg=0.005)
        polygons_xml.append(
            f"""
            <Polygon>
              <outerBoundaryIs>
                <LinearRing><coordinates>{_coords_str(ring2)}</coordinates></LinearRing>
              </outerBoundaryIs>
            </Polygon>
            """
        )

    body = (
        f"<MultiGeometry>{''.join(polygons_xml)}</MultiGeometry>"
        if len(polygons_xml) > 1
        else polygons_xml[0]
    )
    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>{name}</name>
      {body}
    </Placemark>
  </Document>
</kml>"""
    return kml.encode("utf-8")


def make_kmz_bytes(
    rings: list[list[list[float]]] | None = None,
    name: str = "Lote KMZ Prueba",
    multipolygon: bool = True,
) -> bytes:
    kml_data = make_kml_bytes(rings=rings, name=name, multipolygon=multipolygon)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", kml_data)
    return buf.getvalue()


def _build_dbf_bytes(field_name: str, values: list[str]) -> bytes:
    num_records = len(values)
    header_len = 32 + 32 + 1  # header + 1 field descriptor + 0x0D
    record_len = 1 + 48  # delete flag + 48 char value
    header = struct.pack(
        "<BBBBIHH20x",
        3,  # dBase III
        26, 11, 19,  # YY MM DD
        num_records,
        header_len,
        record_len,
    )
    name_bytes = field_name.encode("ascii")[:11].ljust(11, b"\x00")
    field_desc = struct.pack(
        "<11sc4xBB14x",
        name_bytes,
        b"C",
        48,
        0,
    )
    buf = bytearray()
    buf.extend(header)
    buf.extend(field_desc)
    buf.append(0x0D)
    for val in values:
        buf.append(0x20)
        encoded = val.encode("utf-8")[:48].ljust(48, b" ")
        buf.extend(encoded)
    buf.append(0x1A)
    return bytes(buf)


def make_shapefile_zip_bytes(
    rings: list[list[list[float]]] | None = None,
    prj_wkt: str | None = WGS84_ESRI_WKT,
    dbf_name: str | None = "Lote SHP Prueba",
    include_shp: bool = True,
    include_dbf: bool = True,
    include_prj: bool = True,
    stem: str = "lote",
) -> bytes:
    """Create a binary ESRI Polygon Shapefile ZIP in pure Python."""
    if rings is None:
        rings = [synthetic_square_ring()]

    flat_pts: list[list[float]] = []
    parts: list[int] = []
    for ring in rings:
        parts.append(len(flat_pts))
        flat_pts.extend(ring)

    xs = [p[0] for p in flat_pts]
    ys = [p[1] for p in flat_pts]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)

    num_parts = len(parts)
    num_points = len(flat_pts)
    rec_content = bytearray()
    rec_content.extend(struct.pack("<i4d2i", 5, xmin, ymin, xmax, ymax, num_parts, num_points))
    rec_content.extend(struct.pack(f"<{num_parts}i", *parts))
    for x, y in flat_pts:
        rec_content.extend(struct.pack("<2d", float(x), float(y)))

    rec_content_words = len(rec_content) // 2
    rec_header = struct.pack(">ii", 1, rec_content_words)
    total_shp_bytes = 100 + len(rec_header) + len(rec_content)

    shp_header = struct.pack(
        ">iiiiiii",
        9994, 0, 0, 0, 0, 0, total_shp_bytes // 2,
    ) + struct.pack(
        "<ii8d",
        1000, 5, xmin, ymin, xmax, ymax, 0.0, 0.0, 0.0, 0.0,
    )
    shp_bytes = shp_header + rec_header + bytes(rec_content)

    shx_header = struct.pack(
        ">iiiiiii",
        9994, 0, 0, 0, 0, 0, (100 + 8) // 2,
    ) + struct.pack(
        "<ii8d",
        1000, 5, xmin, ymin, xmax, ymax, 0.0, 0.0, 0.0, 0.0,
    )
    shx_bytes = shx_header + struct.pack(">ii", 50, rec_content_words)

    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if include_shp:
            zf.writestr(f"{stem}.shp", shp_bytes)
            zf.writestr(f"{stem}.shx", shx_bytes)
        if include_dbf and dbf_name is not None:
            zf.writestr(f"{stem}.dbf", _build_dbf_bytes("name", [dbf_name]))
        if include_prj and prj_wkt is not None:
            zf.writestr(f"{stem}.prj", prj_wkt.encode("utf-8"))
    return zbuf.getvalue()


def make_geopackage_bytes(
    rings: list[list[list[float]]] | None = None,
    name: str = "Lote GPKG Prueba",
) -> bytes:
    """Create a minimal OGC GeoPackage 1.2 SQLite binary with EPSG:4326 polygon."""
    if rings is None:
        rings = [synthetic_square_ring()]
    poly = Polygon(rings[0], rings[1:] if len(rings) > 1 else None)
    wkb_bytes = shapely_wkb.dumps(poly)
    minx, miny, maxx, maxy = poly.bounds
    # GPB header: magic 'GP', version 0, flags 0x01 (little endian, no envelope)
    gpb = b"GP\x00\x01" + struct.pack("<i", 4326) + wkb_bytes

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as tf:
        tmp_path = Path(tf.name)
    try:
        conn = sqlite3.connect(str(tmp_path))
        try:
            conn.execute("PRAGMA application_id = 0x47504B47;")
            conn.execute(
                """CREATE TABLE gpkg_spatial_ref_sys (
                    srs_name TEXT NOT NULL, srs_id INTEGER NOT NULL PRIMARY KEY,
                    organization TEXT NOT NULL, organization_coordsys_id INTEGER NOT NULL,
                    definition TEXT NOT NULL, description TEXT)"""
            )
            conn.execute(
                "INSERT INTO gpkg_spatial_ref_sys VALUES ('WGS 84', 4326, 'EPSG', 4326, ?, 'WGS84')",
                (WGS84_ESRI_WKT,),
            )
            conn.execute(
                """CREATE TABLE gpkg_contents (
                    table_name TEXT NOT NULL PRIMARY KEY, data_type TEXT NOT NULL,
                    identifier TEXT UNIQUE, description TEXT DEFAULT '',
                    last_change DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    min_x DOUBLE, min_y DOUBLE, max_x DOUBLE, max_y DOUBLE, srs_id INTEGER)"""
            )
            conn.execute(
                "INSERT INTO gpkg_contents (table_name, data_type, identifier, min_x, min_y, max_x, max_y, srs_id) "
                "VALUES ('lotes', 'features', 'lotes', ?, ?, ?, ?, 4326)",
                (minx, miny, maxx, maxy),
            )
            conn.execute(
                """CREATE TABLE gpkg_geometry_columns (
                    table_name TEXT NOT NULL, column_name TEXT NOT NULL,
                    geometry_type_name TEXT NOT NULL, srs_id INTEGER NOT NULL,
                    z TINYINT NOT NULL, m TINYINT NOT NULL,
                    PRIMARY KEY (table_name, column_name))"""
            )
            conn.execute(
                "INSERT INTO gpkg_geometry_columns VALUES ('lotes', 'geom', 'POLYGON', 4326, 0, 0)"
            )
            conn.execute(
                "CREATE TABLE lotes (fid INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, geom BLOB)"
            )
            conn.execute("INSERT INTO lotes (name, geom) VALUES (?, ?)", (name, gpb))
            conn.commit()
        finally:
            conn.close()
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# DEM GeoTIFF Generators
# ---------------------------------------------------------------------------


def _write_tif(
    path: Path,
    z: np.ndarray,
    epsg: int,
    x_origin: float,
    y_origin: float,
    pixel_m: float,
    description: str,
    nodata=np.nan,
    tiled: bool = False,
) -> Path:
    transform = from_origin(x_origin, y_origin, pixel_m, pixel_m)
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict = {
        "driver": "GTiff",
        "height": z.shape[0],
        "width": z.shape[1],
        "count": 1,
        "dtype": str(z.dtype),
        "crs": f"EPSG:{epsg}",
        "transform": transform,
        "nodata": nodata,
        "compress": "deflate",
    }
    if tiled:
        kwargs.update({"tiled": True, "blockxsize": 256, "blockysize": 256})
    with rasterio.open(path, "w", **kwargs) as dst:
        dst.write(z, 1)
        dst.update_tags(SYNTHETIC="TRUE", DESCRIPTION=description)
    return path


def write_sloped_plane_dem(
    path: Path,
    epsg: int = 32720,
    x_origin: float = 248_000.0,
    y_origin: float = 6_313_900.0,
    pixel_m: float = 20.0,
    width: int = 110,
    height: int = 110,
    z0: float = 500.0,
    slope_east: float = 0.03,
    slope_south: float = 0.04,
) -> Path:
    cols = np.arange(width, dtype="float64")
    rows = np.arange(height, dtype="float64")
    cc, rr = np.meshgrid(cols, rows)
    z = (z0 + slope_east * (cc * pixel_m) + slope_south * (rr * pixel_m)).astype("float32")
    return _write_tif(path, z, epsg, x_origin, y_origin, pixel_m, "Synthetic inclined plane DEM")


def write_sloped_with_micro_depression_dem(
    path: Path,
    epsg: int = 32720,
    x_origin: float = 248_000.0,
    y_origin: float = 6_313_900.0,
    pixel_m: float = 20.0,
    width: int = 110,
    height: int = 110,
) -> Path:
    """Gentle inclined plane with a micro-pit (~0.30 m deep) and a larger closed bowl (~2.5 m)."""
    cols = np.arange(width, dtype="float64")
    rows = np.arange(height, dtype="float64")
    cc, rr = np.meshgrid(cols, rows)
    x = x_origin + (cc + 0.5) * pixel_m
    y = y_origin - (rr + 0.5) * pixel_m
    z = 500.0 + 0.006 * (x - x_origin) + 0.008 * (y_origin - y)

    # Small micro-depression inside synthetic square (centered at 248_900, 6_312_700, radius 32 m)
    r_small = np.hypot(x - 248_900.0, y - 6_312_700.0)
    z -= np.where(r_small < 32.0, 0.50 * (1.0 - (r_small / 32.0) ** 2), 0.0)

    # Larger depression inside synthetic square (centered at 249_100, 6_312_500, radius 100 m)
    r_big = np.hypot(x - 249_100.0, y - 6_312_500.0)
    z -= np.where(r_big < 100.0, 2.8 * (1.0 - (r_big / 100.0) ** 2), 0.0)

    return _write_tif(path, z.astype("float32"), epsg, x_origin, y_origin, pixel_m, "Synthetic sloped + depressions")


def write_ridge_berm_dem(
    path: Path,
    epsg: int = 32720,
    x_origin: float = 248_000.0,
    y_origin: float = 6_313_900.0,
    pixel_m: float = 20.0,
    width: int = 110,
    height: int = 110,
) -> Path:
    """Sloped plane with an east-west berm ridge at y=6_312_600 for burn_lines testing."""
    cols = np.arange(width, dtype="float64")
    rows = np.arange(height, dtype="float64")
    cc, rr = np.meshgrid(cols, rows)
    x = x_origin + (cc + 0.5) * pixel_m
    y = y_origin - (rr + 0.5) * pixel_m
    z = 500.0 + 0.01 * (x - x_origin) + 0.03 * (y_origin - y)
    # Berm along y ~ 6_312_600
    berm = np.exp(-((y - 6_312_600.0) / 35.0) ** 2) * 0.6
    z += berm
    return _write_tif(path, z.astype("float32"), epsg, x_origin, y_origin, pixel_m, "Synthetic sloped + berm")


def write_closed_depression_dem(
    path: Path,
    epsg: int = 32720,
    x_origin: float = 248_000.0,
    y_origin: float = 6_313_900.0,
    pixel_m: float = 20.0,
    width: int = 110,
    height: int = 110,
    z_min: float = 480.0,
    curvature: float = 2e-5,
) -> Path:
    cols = np.arange(width, dtype="float64") - (width - 1) / 2
    rows = np.arange(height, dtype="float64") - (height - 1) / 2
    cc, rr = np.meshgrid(cols * pixel_m, rows * pixel_m)
    z = (z_min + curvature * (cc**2 + rr**2)).astype("float32")
    return _write_tif(path, z, epsg, x_origin, y_origin, pixel_m, "Synthetic parabolic bowl DEM")


def write_flat_dem(
    path: Path,
    epsg: int = 32720,
    x_origin: float = 248_000.0,
    y_origin: float = 6_313_900.0,
    pixel_m: float = 20.0,
    width: int = 110,
    height: int = 110,
    z_val: float = 500.0,
) -> Path:
    z = np.full((height, width), z_val, dtype="float32")
    return _write_tif(path, z, epsg, x_origin, y_origin, pixel_m, "Synthetic flat DEM")


def write_1x1_dem(
    path: Path,
    epsg: int = 32720,
    x_origin: float = 248_900.0,
    y_origin: float = 6_312_700.0,
    pixel_m: float = 100.0,
) -> Path:
    z = np.array([[500.0]], dtype="float32")
    return _write_tif(path, z, epsg, x_origin, y_origin, pixel_m, "Synthetic 1x1 degenerate DEM")


def write_nodata_patch_dem(
    path: Path,
    epsg: int = 32720,
    x_origin: float = 248_000.0,
    y_origin: float = 6_313_900.0,
    pixel_m: float = 20.0,
    width: int = 110,
    height: int = 110,
    nodata_top_fraction: float = 0.62,
) -> Path:
    """Inclined plane with >50% NaN in the upper/northern portion of the field."""
    cols = np.arange(width, dtype="float64")
    rows = np.arange(height, dtype="float64")
    cc, rr = np.meshgrid(cols, rows)
    z = (500.0 + 0.03 * (cc * pixel_m) + 0.04 * (rr * pixel_m)).astype("float32")
    cutoff = int(round(height * nodata_top_fraction))
    z[:cutoff, :] = np.nan
    return _write_tif(path, z, epsg, x_origin, y_origin, pixel_m, "Synthetic nodata-patch DEM")


def write_non_overlapping_dem(path: Path) -> Path:
    """Valid EPSG:32720 GeoTIFF far from San Luis / synthetic square."""
    z = np.full((30, 30), 100.0, dtype="float32")
    return _write_tif(path, z, 32720, 600_000.0, 6_000_000.0, 30.0, "Non-overlapping DEM")


def write_san_luis_parcela_205_dem(path: Path, pixel_m: float = 30.0) -> Path:
    """EPSG:32720 DEM covering San Luis Parcela 205 + >=1000 m buffer."""
    x_origin, y_origin = 247_200.0, 6_314_200.0
    width = int(round((250_400.0 - x_origin) / pixel_m))
    height = int(round((y_origin - 6_310_100.0) / pixel_m))
    cc, rr = np.meshgrid(np.arange(width, dtype="float64"), np.arange(height, dtype="float64"))
    x = x_origin + (cc + 0.5) * pixel_m
    y = y_origin - (rr + 0.5) * pixel_m
    z = 540.0 + 0.012 * (x - x_origin) + 0.008 * (y_origin - y)
    # Shallow closed depression (~0.6 m deep) centered at (248_800, 6_312_190) inside Parcela 205
    r = np.hypot(x - 248_800.0, y - 6_312_190.0)
    z -= np.where(r < 120.0, 0.9 * (1.0 - (r / 120.0) ** 2), 0.0)
    return _write_tif(path, z.astype("float32"), 32720, x_origin, y_origin, pixel_m, "Parcela 205 DEM")


def write_san_luis_piedemonte_492_dem(path: Path, pixel_m: float = 30.0) -> Path:
    """EPSG:32719 (Zone 19S!) DEM covering Piedemonte El Trapiche #492 + >=1000 m buffer."""
    x_origin, y_origin = 773_700.0, 6_329_400.0
    width = int(round((777_000.0 - x_origin) / pixel_m))
    height = int(round((y_origin - 6_324_400.0) / pixel_m))
    cc, rr = np.meshgrid(np.arange(width, dtype="float64"), np.arange(height, dtype="float64"))
    x = x_origin + (cc + 0.5) * pixel_m
    y = y_origin - (rr + 0.5) * pixel_m
    # Steeper piedemonte slope + diagonal thalweg / gully
    z = 820.0 + 0.045 * (777_000.0 - x) + 0.030 * (y - 6_324_400.0)
    channel_dist = np.abs((y - 6_326_900.0) - 0.5 * (x - 775_500.0))
    z -= np.exp(-(channel_dist / 90.0) ** 2) * 3.5
    return _write_tif(path, z.astype("float32"), 32719, x_origin, y_origin, pixel_m, "Piedemonte 492 DEM (19S)")


# ---------------------------------------------------------------------------
# In-memory Mock Copernicus & Sentinel-2 COG Generators
# ---------------------------------------------------------------------------


def build_copernicus_mock_cog_bytes(tile_name: str) -> bytes:
    """Build deterministic EPSG:4326 Copernicus-like 1-arcsec COG bytes for San Luis tiles."""
    res_deg = 1.0 / 3600.0  # ~30 m at lat -33
    if tile_name == "S34_00_W066_00":
        west, south, east, north = -66.0, -33.35, -65.65, -33.10
    elif tile_name == "S34_00_W067_00":
        west, south, east, north = -66.15, -33.35, -66.0, -33.10
    else:
        raise KeyError(f"Unknown Copernicus mock tile: {tile_name}")

    width = int(round((east - west) / res_deg))
    height = int(round((north - south) / res_deg))
    cc, rr = np.meshgrid(np.arange(width, dtype="float32"), np.arange(height, dtype="float32"))
    # Realistic sloping relief + small depression inside Parcela 205
    lon = west + (cc + 0.5) * res_deg
    lat = north - (rr + 0.5) * res_deg
    z = (600.0 + 180.0 * (lon - west) + 120.0 * (lat - south)).astype("float32")
    # Small depression near (-65.697, -33.300)
    dist_deg = np.hypot(lon + 65.697, lat + 33.300)
    z -= np.where(dist_deg < 0.0012, 1.2 * (1.0 - (dist_deg / 0.0012) ** 2), 0.0).astype("float32")

    transform = from_origin(west, north, res_deg, res_deg)
    with rasterio.io.MemoryFile() as mem:
        with mem.open(
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=transform,
            nodata=-32767.0,
            tiled=True,
            blockxsize=256,
            blockysize=256,
            compress="deflate",
        ) as dst:
            dst.write(z, 1)
        return bytes(mem.getbuffer())


def build_sentinel2_mock_cog_bytes(
    band: str,
    cloudy: bool = False,
    partial_cloud: bool = False,
) -> bytes:
    """Build deterministic EPSG:4326 Sentinel-2 L2A COG bytes covering San Luis & synthetic square."""
    west, south, east, north = -66.15, -33.35, -65.65, -33.10
    res_deg = 0.0005  # ~50 m, fast
    width = int(round((east - west) / res_deg))
    height = int(round((north - south) / res_deg))
    cc, rr = np.meshgrid(np.arange(width, dtype="float32"), np.arange(height, dtype="float32"))

    transform = from_origin(west, north, res_deg, res_deg)
    cloud_strip = (rr.astype(int) // 4) % 2 == 0
    if band.upper() == "SCL":
        arr = np.full((height, width), 4, dtype="uint8")  # 4 = vegetation
        if cloudy:
            arr[:, :] = 9  # 9 = cloud high probability
        elif partial_cloud:
            arr = np.where(cloud_strip, 9, 4).astype("uint8")
        dtype = "uint8"
        nodata = 0
    else:
        # Spatial gradient across low / moderate / high vigor
        frac_x = cc / max(1, width - 1)
        if band.upper() == "B04":
            arr = (2400.0 - 1100.0 * frac_x).astype("float32")
            if cloudy:
                arr[:, :] = 8000.0
            elif partial_cloud:
                arr = np.where(cloud_strip, 8000.0, 1300.0).astype("float32")
        else:  # B08
            arr = (3200.0 + 2400.0 * frac_x).astype("float32")
            if cloudy:
                arr[:, :] = 8100.0
            elif partial_cloud:
                arr = np.where(cloud_strip, 8100.0, 5200.0).astype("float32")
        dtype = "float32"
        nodata = np.nan

    with rasterio.io.MemoryFile() as mem:
        with mem.open(
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype=dtype,
            crs="EPSG:4326",
            transform=transform,
            nodata=nodata,
            tiled=True,
            blockxsize=256,
            blockysize=256,
            compress="deflate",
        ) as dst:
            dst.write(arr, 1)
        return bytes(mem.getbuffer())


# ---------------------------------------------------------------------------
# CSV Rainfall Builders
# ---------------------------------------------------------------------------


def make_csv_bytes(rows: list[tuple[str, float, int, str]]) -> bytes:
    lines = ["timestamp,precipitation_mm,interval_minutes,station_id"]
    for ts, p, iv, st in rows:
        lines.append(f"{ts},{p},{iv},{st}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def make_early_peak_csv_bytes() -> bytes:
    return make_csv_bytes([
        ("2026-11-18T14:00:00-03:00", 30.0, 15, "PLUV-01"),
        ("2026-11-18T14:15:00-03:00", 25.0, 15, "PLUV-01"),
        ("2026-11-18T14:30:00-03:00", 12.0, 15, "PLUV-01"),
        ("2026-11-18T14:45:00-03:00", 6.0, 15, "PLUV-01"),
        ("2026-11-18T15:00:00-03:00", 4.0, 15, "PLUV-01"),
        ("2026-11-18T15:15:00-03:00", 3.0, 15, "PLUV-01"),
    ])


def make_late_peak_csv_bytes() -> bytes:
    return make_csv_bytes([
        ("2026-11-18T14:00:00-03:00", 3.0, 15, "PLUV-01"),
        ("2026-11-18T14:15:00-03:00", 4.0, 15, "PLUV-01"),
        ("2026-11-18T14:30:00-03:00", 6.0, 15, "PLUV-01"),
        ("2026-11-18T14:45:00-03:00", 12.0, 15, "PLUV-01"),
        ("2026-11-18T15:00:00-03:00", 25.0, 15, "PLUV-01"),
        ("2026-11-18T15:15:00-03:00", 30.0, 15, "PLUV-01"),
    ])


def make_multipeak_csv_bytes() -> bytes:
    from datetime import datetime, timedelta, timezone

    tz = timezone(timedelta(hours=-3))
    start = datetime(2026, 11, 18, 10, 0, tzinfo=tz)
    pattern = [
        1.0, 4.0, 12.0, 18.0, 10.0, 4.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 8.0,
        16.0, 22.0, 14.0, 7.0, 3.0, 1.0, 0.0, 0.0,
    ]
    rows = [
        ((start + timedelta(minutes=15 * i)).isoformat(), p, 15, "PLUV-01")
        for i, p in enumerate(pattern)
    ]
    return make_csv_bytes(rows)
