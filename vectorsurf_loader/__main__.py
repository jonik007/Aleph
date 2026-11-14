"""Command line for major roads or railways as GeoJSON.

    python -m vectorsurf_loader -o roads.geojson --kind road --cells 400 400 --cell-size 30 -- 48.6542920830 44.4336568884
    python -m vectorsurf_loader -o rail.geojson --kind rail --cells 400 400 -- 48.6543 44.4337 48.7620 44.5970
"""

import argparse
import sys
from pathlib import Path

from alephgeo.common import DEFAULT_CACHE

from terrainsurf_loader.grid import region

from .grid import vector_geojson


def paired(values):
    if len(values) < 2 or len(values) % 2:
        raise ValueError("Pass points as LAT LON pairs.")
    return list(zip(values[::2], values[1::2], strict=True))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m vectorsurf_loader",
        description="Write major roads or railways inside a WGS84 rectangle as GeoJSON. "
                    "The rectangle is the same as terrainsurf: corner points, or one lower-left corner with a cell size.",
    )
    parser.add_argument("coordinates", nargs="+", type=float, metavar="LAT LON",
                        help="latitude longitude pairs: at least two corners, or one lower-left corner with --cell-size")
    parser.add_argument("--cells", nargs=2, type=int, required=True, metavar=("NX", "NY"),
                        help="grid cells along longitude and latitude; with --cell-size they set the rectangle")
    parser.add_argument("--cell-size", type=float, metavar="METERS",
                        help="ground meters per cell at mid-latitude; then pass the lower-left corner instead of corners")
    parser.add_argument("--kind", required=True, choices=("road", "rail"),
                        help="road: motorway, trunk, primary, secondary, tertiary; rail: railway=rail and light_rail")
    parser.add_argument("-o", "--output", type=Path, required=True, help="GeoJSON file to write")
    parser.add_argument("--zoom", type=int, help="ignored; accepted so a terrainsurf command can be reused")
    parser.add_argument("--workers", type=int, default=8, help="ignored; the map comes from one regional OSM file")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE,
                        help="OSM cache (default: %(default)s)")
    args = parser.parse_args(argv)
    try:
        points = region(paired(args.coordinates), args.cells[0], args.cells[1], args.cell_size)
        vector_geojson(points, args.kind, args.output, cache_dir=args.cache_dir)
    except ValueError as error:
        print(f"vectorsurf: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"vectorsurf: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
