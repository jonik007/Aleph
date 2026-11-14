"""Major roads or railways clipped to the same rectangle as a Surfer grid.

Roads are highway=motorway, trunk, primary, secondary, and tertiary. Link ramps,
residential streets, service tracks, and footways stay out. Railways are
railway=rail and light_rail. Yards, sidings, spurs, trams, and abandoned lines
stay out. Coordinates are WGS84 longitude and latitude. Height is not stored:
the viewer samples it from the relief grid.
"""

import hashlib
import json
import sys
from pathlib import Path

from alephgeo.common import DEFAULT_CACHE, Client, atomic_path
from alephgeo.layers import objects
from terrainsurf_loader.grid import bounds

MAJOR_ROADS = {"motorway", "trunk", "primary", "secondary", "tertiary"}
RAIL_LINES = {"rail", "light_rail"}
YARD_SERVICE = {"yard", "siding", "spur", "crossover"}


def wanted(kind, tags):
    """True when this OSM way is one of the lines ``kind`` keeps."""
    if tags.get("area") == "yes":
        return False
    if kind == "road":
        highway = tags.get("highway", "")
        return highway in MAJOR_ROADS
    railway = tags.get("railway", "")
    return railway in RAIL_LINES and tags.get("service") not in YARD_SERVICE


def clip_segment(x0, y0, x1, y1, west, south, east, north):
    """Liang–Barsky. Endpoints of the piece inside the closed rectangle, or None."""
    dx, dy = x1 - x0, y1 - y0
    u0, u1 = 0.0, 1.0
    for pi, qi in ((-dx, x0 - west), (dx, east - x0), (-dy, y0 - south), (dy, north - y0)):
        if pi == 0:
            if qi < 0:
                return None
            continue
        t = qi / pi
        if pi < 0:
            if t > u1:
                return None
            u0 = max(u0, t)
        else:
            if t < u0:
                return None
            u1 = min(u1, t)
    if u0 > u1:
        return None
    return (x0 + u0 * dx, y0 + u0 * dy), (x0 + u1 * dx, y0 + u1 * dy)


def _same(a, b):
    return abs(a[0] - b[0]) <= 1e-12 and abs(a[1] - b[1]) <= 1e-12


def clip_linestring(points, west, south, east, north):
    """Pieces of a (lon, lat) line that lie inside the rectangle."""
    pieces, current = [], []

    def keep():
        if len(current) >= 2:
            pieces.append(list(current))
        current.clear()

    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if _same((x0, y0), (x1, y1)):
            continue
        clipped = clip_segment(x0, y0, x1, y1, west, south, east, north)
        if clipped is None:
            keep()
            continue
        start, end = clipped
        if current and not _same(current[-1], start):
            keep()
        if not current:
            current.append(start)
        current.append(end)
    keep()
    return pieces


def _round(point):
    return [round(point[0], 7), round(point[1], 7)]


def _properties(kind, tags):
    props = {"kind": kind}
    key = "highway" if kind == "road" else "railway"
    props[key] = tags.get(key, "")
    name = tags.get("name")
    if name:
        props["name"] = name
    return props


def features_from_osm(path, kind, west, south, east, north):
    """Line features whose tags match ``kind``, clipped to the rectangle."""
    nodes = {}
    ways = []
    for element in objects(path):
        if element.tag == "node":
            nodes[int(element.attrib["id"])] = (float(element.attrib["lon"]), float(element.attrib["lat"]))
            continue
        if element.tag != "way":
            continue
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in element.findall("tag")}
        if not wanted(kind, tags):
            continue
        refs = [int(nd.attrib["ref"]) for nd in element.findall("nd")]
        ways.append((tags, refs))
    features = []
    for tags, refs in ways:
        points = [nodes[ref] for ref in refs if ref in nodes]
        pieces = clip_linestring(points, west, south, east, north)
        if not pieces:
            continue
        coordinates = [[_round(point) for point in piece] for piece in pieces]
        geometry = ({"type": "LineString", "coordinates": coordinates[0]} if len(coordinates) == 1
                    else {"type": "MultiLineString", "coordinates": coordinates})
        features.append({"type": "Feature", "properties": _properties(kind, tags), "geometry": geometry})
    return features


def _extract(cache_dir, south, west, north, east, client, announce):
    key = hashlib.sha256(f"{south:.7f},{west:.7f},{north:.7f},{east:.7f}".encode()).hexdigest()[:16]
    path = Path(cache_dir) / "vectors" / f"{key}.osm"
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

    announce("Reading OpenStreetMap lines")
    path.parent.mkdir(parents=True, exist_ok=True)
    client.maps.export(polygon, path, progress)
    return path


def vector_geojson(points, kind, output, *, cache_dir=None, client=None, announce=None):
    """Write a GeoJSON FeatureCollection of ``kind`` lines inside the bounding box of ``points``."""
    if kind not in ("road", "rail"):
        raise ValueError("kind must be road or rail.")
    south, west, north, east = bounds(points)
    announce = announce or (lambda message: print(message, file=sys.stderr))
    cache = Path(cache_dir) if cache_dir else DEFAULT_CACHE
    source = client or Client(cache_dir=cache)
    extract = _extract(cache, south, west, north, east, source, announce)
    features = features_from_osm(extract, kind, west, south, east, north)
    document = {
        "type": "FeatureCollection",
        "name": "roads" if kind == "road" else "rail",
        "attribution": "© OpenStreetMap contributors, ODbL",
        "features": features,
    }
    output = Path(output)
    with atomic_path(output) as temporary:
        temporary.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    label = "major roads" if kind == "road" else "railways"
    announce(f"Wrote {output} ({len(features)} {label})")
    announce("Lines are WGS84 longitude and latitude. © OpenStreetMap contributors, ODbL.")
    return dict(west=west, south=south, east=east, north=north, kind=kind, features=len(features), output=str(output))
