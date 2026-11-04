"""Command line for a Surfer ASCII land/water grid.

    python -m watersurf_loader -o volgograd-water.grd --cells 200 200 -- 48.6812 44.4745 48.7351 44.5562
"""

import argparse
import sys
from pathlib import Path

from alephgeo.common import DEFAULT_CACHE

from .grid import water_grid


def paired(values):
    if len(values) < 4 or len(values) % 2:
        raise ValueError("Pass corner points as LAT LON pairs, at least two points.")
    return list(zip(values[::2], values[1::2], strict=True))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m watersurf_loader",
        description="Mark each cell of a WGS84 rectangle as land (1) or OSM water (0) and write a Surfer ASCII grid.",
    )
    parser.add_argument("coordinates", nargs="+", type=float, metavar="LAT LON",
                        help="corner points as latitude longitude pairs, at least two")
    parser.add_argument("--cells", nargs=2, type=int, required=True, metavar=("NX", "NY"),
                        help="grid cells along longitude and latitude, the same counts as terrainsurf")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Surfer ASCII grid to write")
    parser.add_argument("--zoom", type=int, help="ignored; accepted so a terrainsurf command can be reused")
    parser.add_argument("--workers", type=int, default=8, help="ignored; the map comes from one regional OSM file")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE,
                        help="OSM cache (default: %(default)s)")
    args = parser.parse_args(argv)
    try:
        water_grid(paired(args.coordinates), args.cells[0], args.cells[1], args.output, cache_dir=args.cache_dir)
    except ValueError as error:
        print(f"watersurf: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"watersurf: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
