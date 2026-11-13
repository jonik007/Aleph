"""Surfer grid of land and water on the same cell centers as terrainsurf.

Each value is one cell, written at the cell center. 1 is land and 0 is water.
A cell is water when an OpenStreetMap water polygon meets its interior: the
cell center lies in the water, or a water or island edge crosses the cell.
Holes in a water polygon, such as islands, stay land when the whole cell sits
in the hole.

Water polygons are natural=water, water=*, and landuse=reservoir, including
the Volga's mapped channel. A waterway centerline has no width and does not
mark cells.
"""

import hashlib
import math
import sys
from pathlib import Path

import numpy as np

from alephgeo.common import DEFAULT_CACHE, Client
from alephgeo.geo import within
from alephgeo.layers import osm
from terrainsurf_loader.grid import bounds, cell_grid, cells, write_grd

# Shrink a cell when testing an edge, so a shoreline that only lies on the grid line
# does not paint the neighboring dry cell.
_EDGE = 1e-9


def _segment_meets_rectangle(x0, y0, x1, y1, left, bottom, right, top):
    """Liang–Barsky: the segment meets the closed rectangle."""
    dx, dy = x1 - x0, y1 - y0
    u0, u1 = 0.0, 1.0
    for pi, qi in ((-dx, x0 - left), (dx, right - x0), (-dy, y0 - bottom), (dy, top - y0)):
        if pi == 0:
            if qi < 0:
                return False
            continue
        t = qi / pi
        if pi < 0:
            if t > u1:
                return False
            u0 = max(u0, t)
        else:
            if t < u0:
                return False
            u1 = min(u1, t)
    return u0 <= u1


def edge_cells(rings, west, south, dx, dy, width, height):
    """Cells whose interior is crossed by a ring edge. Rings are (lon, lat) lists."""
    hit = np.zeros((height, width), bool)
    for ring in rings:
        if len(ring) < 2:
            continue
        points = ring if ring[0] == ring[-1] else [*ring, ring[0]]
        for (lon0, lat0), (lon1, lat1) in zip(points, points[1:]):
            x0, y0 = (lon0 - west) / dx, (lat0 - south) / dy
            x1, y1 = (lon1 - west) / dx, (lat1 - south) / dy
            if x0 == x1 and y0 == y1:
                continue
            j0 = max(0, math.floor(min(x0, x1)))
            j1 = min(width - 1, math.floor(max(x0, x1)))
            i0 = max(0, math.floor(min(y0, y1)))
            i1 = min(height - 1, math.floor(max(y0, y1)))
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    if _segment_meets_rectangle(x0, y0, x1, y1, j + _EDGE, i + _EDGE, j + 1 - _EDGE, i + 1 - _EDGE):
                        hit[i, j] = True
    return hit


def _overlaps(ring, west, south, east, north):
    lons = [point[0] for point in ring]
    lats = [point[1] for point in ring]
    return max(lons) >= west and min(lons) <= east and max(lats) >= south and min(lats) <= north


def cell_mask(west, south, east, north, cells_x, cells_y, polygons):
    """0 where a water polygon meets the cell, 1 on land. Row 0 is the south row."""
    longitudes, latitudes, _ = cell_grid(west, south, east, north, cells_x, cells_y)
    dx = (east - west) / cells_x
    dy = (north - south) / cells_y
    latitude, longitude = np.meshgrid(latitudes, longitudes, indexing="ij")
    water = np.zeros((cells_y, cells_x), bool)
    for rings in polygons:
        outer = rings[0]
        if len(outer) < 4 or not _overlaps(outer, west, south, east, north):
            continue
        # within() takes (lat, lon). OSM rings are (lon, lat).
        inside = within([(lat, lon) for lon, lat in outer], latitude, longitude)
        for hole in rings[1:]:
            if len(hole) < 4:
                continue
            inside &= ~within([(lat, lon) for lon, lat in hole], latitude, longitude)
        water |= inside
        water |= edge_cells(rings, west, south, dx, dy, cells_x, cells_y)
    return np.where(water, 0.0, 1.0)


def water_polygons(path):
    """Water polygons from a map.osm extract: each item is [outer, hole, ...]."""
    polygons = []
    for item in osm(path)["features"]:
        if item["properties"].get("kind") != "water":
            continue
        geometry = item["geometry"]
        coordinates = geometry["coordinates"]
        if geometry["type"] == "Polygon":
            polygons.append(coordinates)
        elif geometry["type"] == "MultiPolygon":
            polygons.extend(coordinates)
    return polygons


def _extract(cache_dir, south, west, north, east, client, announce):
    key = hashlib.sha256(f"{south:.7f},{west:.7f},{north:.7f},{east:.7f}".encode()).hexdigest()[:16]
    path = Path(cache_dir) / "water" / f"{key}.osm"
    if path.is_file() and path.stat().st_size > 0:
        announce(f"Using cached OSM extract {path}")
        return path
    polygon = [(south, west), (south, east), (north, east), (north, west)]

    shown = set()

    def progress(phase, done=0, total=None, unit=None):
        if unit == "bytes" and total:
            line = f"{phase}: {done / 1_000_000:.0f} / {total / 1_000_000:.0f} MB"
        elif done == 0:
            line = str(phase)
        else:
            return
        if line not in shown:
            shown.add(line)
            announce(line)

    announce("Reading OpenStreetMap water")
    path.parent.mkdir(parents=True, exist_ok=True)
    client.maps.export(polygon, path, progress)
    return path


def water_grid(points, cells_x, cells_y, output, *, cache_dir=None, client=None, announce=None):
    """Write a Surfer grid of land (1) and water (0) for the bounding box of ``points``."""
    south, west, north, east = bounds(points)
    cells_x, cells_y = cells(cells_x, "cells x"), cells(cells_y, "cells y")
    announce = announce or (lambda message: print(message, file=sys.stderr))
    cache = Path(cache_dir) if cache_dir else DEFAULT_CACHE
    source = client or Client(cache_dir=cache)
    extract = _extract(cache, south, west, north, east, source, announce)
    polygons = water_polygons(extract)
    values = cell_mask(west, south, east, north, cells_x, cells_y, polygons)
    _, _, header = cell_grid(west, south, east, north, cells_x, cells_y)
    write_grd(output, *header, values)
    wet = int(np.count_nonzero(values == 0))
    dry = values.size - wet
    announce(f"Wrote {output} ({cells_x} × {cells_y} cells, {wet} water, {dry} land)")
    announce("0 = water, 1 = land, one value per cell at its center.")
    announce("Water polygons: © OpenStreetMap contributors, ODbL.")
    return dict(west=west, south=south, east=east, north=north, cells=(cells_x, cells_y), water=wet, land=dry,
                polygons=len(polygons), output=str(output))
