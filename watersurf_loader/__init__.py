"""Mark each cell of a WGS84 grid as land or OSM water and write a Surfer ASCII file."""

from .grid import water_grid

__all__ = ["water_grid"]
