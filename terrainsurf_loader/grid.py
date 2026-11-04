"""Regular longitude/latitude grid of terrain heights in Surfer ASCII (DSAA) form.

Corner points set the bounding rectangle. One lower-left point plus a cell size
builds the same rectangle: each cell is that many ground meters wide and tall at
the latitude halfway between south and north. The grid is uniform in degrees:
X is longitude, Y is latitude, Z is elevation in meters. ``--cells NX NY`` is the
number of cells, so the file stores NX+1 by NY+1 nodes. The first data row is the
south edge (Surfer's ylo). Missing heights use Surfer's blank value, 1.70141e38.

Heights come from AWS Terrain Tiles
(https://github.com/tilezen/joerd/blob/master/docs/attribution.md).
"""

import math
import os
import sys
from pathlib import Path

import numpy as np

from alephgeo import terrain
from alephgeo.common import WORKERS, Client, atomic_path, fetch, write_bytes
from alephgeo.geo import MAX_LATITUDE, MERCATOR_RADIUS
from alephgeo.layers import NODATA, heights

BLANK_TEXT = "1.70141e+38"
TILE = "https://elevation-tiles-prod.s3.amazonaws.com/geotiff/{z}/{x}/{y}.tif"
TILE_SIZE = 512
MAX_CELLS = 10_000
MAX_TILES = 4_096


def bounds(points):
    """Bounding rectangle of (lat, lon) corners. Longitude does not wrap the antimeridian."""
    if len(points) < 2:
        raise ValueError("Pass at least two corner points.")
    lats, lons = [], []
    for lat, lon in points:
        if not (math.isfinite(lat) and math.isfinite(lon)):
            raise ValueError("Coordinates must be finite numbers.")
        lats.append(lat)
        lons.append(lon)
    south, north = min(lats), max(lats)
    west, east = min(lons), max(lons)
    if not south < north or not west < east:
        raise ValueError("Corner points must cover a nonzero area.")
    if south < -MAX_LATITUDE or north > MAX_LATITUDE:
        raise ValueError("Latitudes must stay within −85.0511…85.0511.")
    if west < -180 or east > 180:
        raise ValueError("Longitudes must stay within −180…180.")
    return south, west, north, east


def cells(count, name):
    if type(count) is not int or not 1 <= count <= MAX_CELLS:
        raise ValueError(f"{name} must be a whole number from 1 to {MAX_CELLS}.")
    return count


def region(points, cells_x, cells_y, cell_size=None):
    """Corner points, or one lower-left point expanded by equal ground-meter cells.

    ``cell_size`` is the north-south and east-west length of one cell, in meters,
    at the latitude halfway up the rectangle. Longitude spacing uses that same
    length, so a cell is square there and slightly wider toward the equator.
    """
    cells(cells_x, "cells x")
    cells(cells_y, "cells y")
    if cell_size is None:
        if len(points) < 2:
            raise ValueError("Pass corner points as LAT LON pairs, at least two points.")
        return points
    if len(points) != 1:
        raise ValueError("With a cell size, pass the lower-left corner as one LAT LON pair.")
    if type(cell_size) not in (int, float) or not math.isfinite(cell_size) or cell_size <= 0:
        raise ValueError("cell size must be a positive number of meters.")
    lat, lon = points[0]
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise ValueError("Coordinates must be finite numbers.")
    south = math.radians(lat)
    north = south + cells_y * cell_size / MERCATOR_RADIUS
    cosine = math.cos((south + north) / 2)
    if cosine < 1e-6:
        raise ValueError("The grid reaches too far north or south.")
    east = math.radians(lon) + cells_x * cell_size / (MERCATOR_RADIUS * cosine)
    corners = [(lat, lon), (math.degrees(north), math.degrees(east))]
    bounds(corners)
    return corners


def choose_zoom(west, south, east, north, cells_x, cells_y, limit=14):
    """Coarsest terrain zoom whose pixel is no larger than the smaller cell, capped at 14."""
    lat = math.radians((south + north) / 2)
    cos_lat = max(math.cos(lat), 1e-6)
    meters_x = math.radians(east - west) / cells_x * MERCATOR_RADIUS * cos_lat
    meters_y = math.radians(north - south) / cells_y * MERCATOR_RADIUS
    cell = min(meters_x, meters_y)
    pixel0 = 2 * math.pi * MERCATOR_RADIUS * cos_lat / TILE_SIZE
    zoom = math.ceil(math.log2(pixel0 / cell))
    return min(limit, max(1, zoom))


def axes(west, south, east, north, cells_x, cells_y):
    """Node longitudes and latitudes. Index 0 is the west or south edge."""
    return np.linspace(west, east, cells_x + 1), np.linspace(south, north, cells_y + 1)


def project(lon, lat, world):
    """Web Mercator pixel position of the tile edge, origin at the northwest of the world."""
    lon = np.asanyarray(lon, dtype=np.float64)
    lat = np.asanyarray(lat, dtype=np.float64)
    fx = (lon + 180.0) / 360.0 * world
    fy = (1.0 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2.0 * world
    return fx, fy


def _windows(lons, lats, zoom):
    """Continuous pixel-center indexes for every node, and the bilinear weights."""
    world = TILE_SIZE << zoom
    fx, fy = project(lons[np.newaxis, :], lats[:, np.newaxis], world)
    # Pixel 0 is centered half a pixel inside the northwest corner of its tile.
    x, y = np.broadcast_arrays(fx - 0.5, fy - 0.5)
    x = np.array(x, dtype=np.float64, copy=True)
    y = np.array(y, dtype=np.float64, copy=True)
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    return world, x0, y0, x - x0, y - y0


def tiles_for(west, south, east, north, zoom):
    """Tiles touched by bilinear samples of a rectangle, with longitude wrapped."""
    world = TILE_SIZE << zoom
    span = 1 << zoom
    fx, fy = project([west, east, west, east], [south, south, north, north], world)
    cols = np.floor(fx - 0.5).astype(np.int64)
    rows = np.floor(fy - 0.5).astype(np.int64)
    col0, col1 = int(cols.min()), int(cols.max()) + 1
    row0, row1 = int(rows.min()), int(rows.max()) + 1
    y0, y1 = max(0, row0 // TILE_SIZE), min(span - 1, row1 // TILE_SIZE)
    rows_n = y1 - y0 + 1 if y1 >= y0 else 0
    cols_n = min(span, col1 // TILE_SIZE - col0 // TILE_SIZE + 1)
    if cols_n * rows_n > MAX_TILES:
        raise ValueError(f"This area needs {cols_n * rows_n} terrain tiles at zoom {zoom}. "
                         "Use a smaller rectangle or a lower zoom.")
    tiles = set()
    for tile_x in range(col0 // TILE_SIZE, col1 // TILE_SIZE + 1):
        wrapped = tile_x % span
        for tile_y in range(y0, y1 + 1):
            tiles.add((wrapped, tile_y))
    return tiles


def sample_grid(lons, lats, zoom, array):
    """Bilinear heights. ``array(tile_x, tile_y)`` returns a 512×512 array, or None where the tile is missing."""
    world, x0, y0, wx, wy = _windows(lons, lats, zoom)

    def gather(cols, rows):
        wrapped = np.mod(cols, world)
        valid = (rows >= 0) & (rows < world)
        tile_x = np.zeros(cols.shape, np.int64)
        tile_y = np.zeros(cols.shape, np.int64)
        local_x = np.zeros(cols.shape, np.int64)
        local_y = np.zeros(cols.shape, np.int64)
        tile_x[valid] = wrapped[valid] // TILE_SIZE
        tile_y[valid] = rows[valid] // TILE_SIZE
        local_x[valid] = wrapped[valid] % TILE_SIZE
        local_y[valid] = rows[valid] % TILE_SIZE
        out = np.full(cols.shape, np.nan, np.float64)
        if not np.any(valid):
            return out
        pairs = np.unique(np.stack((tile_x[valid], tile_y[valid]), axis=1), axis=0)
        for ux, uy in pairs:
            values = array(int(ux), int(uy))
            mask = valid & (tile_x == ux) & (tile_y == uy)
            if values is None:
                continue
            sampled = values[local_y[mask], local_x[mask]]
            out[mask] = sampled
        missing = ~np.isfinite(out) | (out <= NODATA / 2)
        out[missing] = np.nan
        return out

    v00 = gather(x0, y0)
    v10 = gather(x0 + 1, y0)
    v01 = gather(x0, y0 + 1)
    v11 = gather(x0 + 1, y0 + 1)
    # A sample that lands on a pixel center has zero weight on the other side, so that side may be absent.
    need10 = wx > 0
    need01 = wy > 0
    good = (np.isfinite(v00) & ~(need10 & ~np.isfinite(v10)) & ~(need01 & ~np.isfinite(v01))
            & ~((need10 & need01) & ~np.isfinite(v11)))
    mixed = (np.nan_to_num(v00) * (1 - wx) * (1 - wy) + np.nan_to_num(v10) * wx * (1 - wy)
             + np.nan_to_num(v01) * (1 - wx) * wy + np.nan_to_num(v11) * wx * wy)
    return np.where(good, mixed, np.nan)


def write_grd(path, west, south, east, north, values):
    """Write DSAA. Row 0 of ``values`` is the southern edge, column 0 the western edge."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError("No elevation values fell on this grid.")
    zmin, zmax = float(finite.min()), float(finite.max())
    ny, nx = values.shape

    def row_text(row):
        parts = []
        for value in row:
            parts.append(f"{value:.6f}" if math.isfinite(value) else BLANK_TEXT)
        return " ".join(parts)

    path = Path(path)
    with atomic_path(path) as temporary, temporary.open("w", encoding="ascii", newline="\n") as stream:
        stream.write(f"DSAA\n{nx} {ny}\n{west:.10f} {east:.10f}\n{south:.10f} {north:.10f}\n{zmin:.6f} {zmax:.6f}\n")
        for row in values.tolist():
            stream.write(row_text(row))
            stream.write("\n")
    return zmin, zmax


class TileCache:
    """Download GeoTIFF terrain tiles once and decode them on demand."""

    def __init__(self, zoom, cache_dir, client, workers):
        self.zoom = zoom
        self.cache_dir = Path(cache_dir)
        self.client = client
        self.workers = workers
        self.memory = {}

    def path(self, x, y):
        return self.cache_dir / str(self.zoom) / str(x) / f"{y}.tif"

    def readable(self, path, x, y):
        if not path.is_file() or path.stat().st_size < 64:
            return False
        try:
            with path.open("rb") as stream:
                terrain.validate(terrain.TIFF(stream), dict(x=x, y=y, zoom=self.zoom))
            return True
        except (OSError, ValueError):
            return False

    def ensure(self, tiles, announce):
        missing = []
        for x, y in sorted(tiles):
            path = self.path(x, y)
            if self.readable(path, x, y):
                continue
            path.unlink(missing_ok=True)
            missing.append((x, y))
        if not missing:
            announce(f"Terrain zoom {self.zoom}, {len(tiles)} cached tiles")
            return
        announce(f"Downloading {len(missing)} of {len(tiles)} terrain tiles at zoom {self.zoom}")
        addresses = [TILE.format(z=self.zoom, x=x, y=y) for x, y in missing]
        for (x, y), data in zip(missing, fetch(self.client, addresses, self.workers, missing_ok=True)):
            if not data:
                continue
            path = self.path(x, y)
            write_bytes(path, data)
            if not self.readable(path, x, y):
                path.unlink(missing_ok=True)

    def array(self, x, y):
        key = (x, y)
        if key not in self.memory:
            path = self.path(x, y)
            decoded = None
            if path.is_file():
                try:
                    image = heights(path)
                    try:
                        decoded = np.array(image, dtype=np.float64, copy=True)
                    finally:
                        image.close()
                except (OSError, ValueError):
                    path.unlink(missing_ok=True)
                    decoded = None
                if decoded is None or decoded.shape != (TILE_SIZE, TILE_SIZE):
                    path.unlink(missing_ok=True)
                    decoded = None
            self.memory[key] = decoded
        return self.memory[key]


def default_cache():
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "terrainsurf"


def surfer_grid(points, cells_x, cells_y, output, *, zoom=None, cache_dir=None, workers=WORKERS, client=None,
                announce=None):
    """Sample ``points``' bounding box and write a Surfer ASCII grid. Returns a short summary."""
    south, west, north, east = bounds(points)
    cells_x, cells_y = cells(cells_x, "cells x"), cells(cells_y, "cells y")
    if zoom is None:
        zoom = choose_zoom(west, south, east, north, cells_x, cells_y)
    elif type(zoom) is not int or not 1 <= zoom <= 14:
        raise ValueError("zoom must be a whole number from 1 to 14.")
    if type(workers) is not int or not 1 <= workers <= 64:
        raise ValueError("workers must be a whole number from 1 to 64.")
    announce = announce or (lambda message: print(message, file=sys.stderr))
    lons, lats = axes(west, south, east, north, cells_x, cells_y)
    tiles = tiles_for(west, south, east, north, zoom)
    cache = TileCache(zoom, cache_dir or default_cache(), client or Client(), workers)
    cache.ensure(tiles, announce)
    values = sample_grid(lons, lats, zoom, cache.array)
    zmin, zmax = write_grd(output, west, south, east, north, values)
    blanks = int(np.isnan(values).sum())
    ny, nx = values.shape
    announce(f"Wrote {output} ({nx} × {ny} nodes, {zmin:.1f}…{zmax:.1f} m)")
    if blanks:
        announce(f"{blanks} nodes have no elevation and are blank in the grid.")
    announce("Heights: AWS Terrain Tiles. Credit the sources in the Tilezen joerd attribution.")
    return dict(zoom=zoom, west=west, south=south, east=east, north=north, nodes=(nx, ny), zmin=zmin, zmax=zmax,
                blanks=blanks, tiles=len(tiles), output=str(output))
