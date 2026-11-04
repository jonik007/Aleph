"""Command line for a Surfer ASCII terrain grid.

    python -m terrainsurf_loader -o moscow.grd --cells 200 150 -- 55.70 37.50 55.80 37.70
"""

import argparse
import sys
from pathlib import Path

from .grid import surfer_grid


def paired(values):
    if len(values) < 4 or len(values) % 2:
        raise ValueError("Pass corner points as LAT LON pairs, at least two points.")
    return list(zip(values[::2], values[1::2], strict=True))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m terrainsurf_loader",
        description="Sample AWS terrain onto a WGS84 rectangle and write a Surfer ASCII grid (.grd).",
    )
    parser.add_argument("coordinates", nargs="+", type=float, metavar="LAT LON",
                        help="corner points as latitude longitude pairs, at least two")
    parser.add_argument("--cells", nargs=2, type=int, required=True, metavar=("NX", "NY"),
                        help="grid cells along longitude and latitude; the file stores one extra node on each side")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Surfer ASCII grid to write")
    parser.add_argument("--zoom", type=int, help="terrain zoom, 1–14 (default: finest zoom no finer than the cell)")
    parser.add_argument("--workers", type=int, default=8, help="parallel tile downloads, 1–64 (default: 8)")
    parser.add_argument("--cache-dir", type=Path, help="tile cache (default: ~/.cache/terrainsurf)")
    args = parser.parse_args(argv)
    try:
        surfer_grid(paired(args.coordinates), args.cells[0], args.cells[1], args.output, zoom=args.zoom,
                    workers=args.workers, cache_dir=args.cache_dir)
    except ValueError as error:
        print(f"terrainsurf: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"terrainsurf: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
