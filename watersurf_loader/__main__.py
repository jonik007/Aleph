"""Command line for a Surfer ASCII land/water grid.

    python -m watersurf_loader -o volgograd-water.grd --cells 200 200 -- 48.6812 44.4745 48.7351 44.5562
    python -m watersurf_loader -o volgograd-water.grd --cells 200 200 --cell-size 30 -- 48.6812415415 44.4744959442
"""

import argparse
import sys
from pathlib import Path

from alephgeo.common import DEFAULT_CACHE

from terrainsurf_loader.grid import region

from .grid import water_grid


def paired(values):
    if len(values) < 2 or len(values) % 2:
        raise ValueError("Pass points as LAT LON pairs.")
    return list(zip(values[::2], values[1::2], strict=True))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m watersurf_loader",
        description="Mark each cell of a WGS84 rectangle as land (1) or OSM water (0) and write a Surfer ASCII grid.",
    )
    parser.add_argument("coordinates", nargs="+", type=float, metavar="LAT LON",
                        help="latitude longitude pairs: at least two corners, or one lower-left corner with --cell-size")
    parser.add_argument("--cells", nargs=2, type=int, required=True, metavar=("NX", "NY"),
                        help="grid cells along longitude and latitude, the same counts as terrainsurf")
    parser.add_argument("--cell-size", type=float, metavar="METERS",
                        help="ground meters per cell at mid-latitude; then pass the lower-left corner instead of corners")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Surfer ASCII grid to write")
    parser.add_argument("--zoom", type=int, help="ignored; accepted so a terrainsurf command can be reused")
    parser.add_argument("--workers", type=int, default=8, help="ignored; the map comes from one regional OSM file")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE,
                        help="OSM cache (default: %(default)s)")
    args = parser.parse_args(argv)
    try:
        points = region(paired(args.coordinates), args.cells[0], args.cells[1], args.cell_size)
        water_grid(points, args.cells[0], args.cells[1], args.output, cache_dir=args.cache_dir)
    except ValueError as error:
        print(f"watersurf: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"watersurf: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
