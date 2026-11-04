"""Surfer grid geometry and ASCII layout, without downloading tiles."""

import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from alephgeo.layers import NODATA
from terrainsurf_loader.__main__ import main
from terrainsurf_loader.grid import axes, bounds, choose_zoom, region, sample_grid, tiles_for, write_grd


def ramp(tx, ty):
    columns = tx * 512 + np.arange(512)
    rows = ty * 512 + np.arange(512)
    return columns[np.newaxis, :] + 2 * rows[:, np.newaxis]


def lonlat(x, y, world):
    """Inverse of the sampler's pixel-center mapping."""
    fx, fy = x + 0.5, y + 0.5
    lon = fx / world * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * fy / world))))
    return lon, lat


class GridTests(unittest.TestCase):
    def test_bounds_use_the_extent_of_unordered_corners(self):
        south, west, north, east = bounds([(55.8, 37.7), (55.7, 37.5), (55.75, 37.6)])
        self.assertEqual((south, west, north, east), (55.7, 37.5, 55.8, 37.7))

    def test_nodes_include_both_edges(self):
        lons, lats = axes(10, 20, 12, 23, 2, 3)
        self.assertEqual(lons.tolist(), [10, 11, 12])
        self.assertEqual(lats.tolist(), [20, 21, 22, 23])

    def test_zoom_tracks_cell_size_and_stops_at_14(self):
        # About 2 m cells hit the tile limit. A 0.03° cell is near a 3 km sample. A hemisphere stays coarse.
        self.assertEqual(choose_zoom(0, 0, 0.001, 0.001, 50, 50), 14)
        self.assertEqual(choose_zoom(0, 0, 0.03, 0.03, 1, 1), 5)
        self.assertEqual(choose_zoom(-180, -80, 180, 80, 2, 2), 1)

    def test_sample_grid_follows_both_axes(self):
        lons = np.linspace(37.5, 37.7, 4)
        lats = np.linspace(55.7, 55.8, 3)
        values = sample_grid(lons, lats, 8, ramp)
        self.assertEqual(values.shape, (3, 4))
        self.assertTrue(np.isfinite(values).all())

    def test_bilinear_sample_on_a_ramp(self):
        world = 512 * 2
        lon, lat = lonlat(600.25, 400.5, world)
        values = sample_grid(np.array([lon]), np.array([lat]), 1, ramp)
        self.assertAlmostEqual(values[0, 0], 1401.25, places=5)

    def test_missing_pixel_is_blank_when_it_has_weight(self):
        def hole(tx, ty):
            values = np.full((512, 512), 10.0)
            if (tx, ty) == (1, 0):
                values[400, 88] = NODATA
            return values

        world = 512 * 2
        lon, lat = lonlat(600.0, 400.0, world)
        values = sample_grid(np.array([lon]), np.array([lat]), 1, hole)
        self.assertTrue(math.isnan(values[0, 0]))

    def test_grd_writes_south_row_first_and_blanks_gaps(self):
        values = np.array([[1.0, 2.5], [np.nan, 4.0], [5.5, 6.0]])
        with TemporaryDirectory() as directory:
            path = Path(directory) / "relief.grd"
            zmin, zmax = write_grd(path, 10, 20, 12, 23, values)
            lines = path.read_text(encoding="ascii").splitlines()
        self.assertEqual(zmin, 1)
        self.assertEqual(zmax, 6)
        self.assertEqual(lines[:5], ["DSAA", "2 3", "10.0000000000 12.0000000000", "20.0000000000 23.0000000000",
                                     "1.000000 6.000000"])
        self.assertEqual(lines[5], "1.000000 2.500000")
        self.assertEqual(lines[6], "1.70141e+38 4.000000")
        self.assertEqual(lines[7], "5.500000 6.000000")

    def test_tile_list_covers_the_sample_window(self):
        tiles = tiles_for(37.5, 55.7, 37.7, 55.8, 10)
        self.assertGreaterEqual(len(tiles), 1)
        self.assertTrue(all(0 <= x < 1024 and 0 <= y < 1024 for x, y in tiles))

    def test_fine_zoom_over_the_whole_world_is_refused(self):
        with self.assertRaisesRegex(ValueError, "terrain tiles"):
            tiles_for(-180, -80, 180, 80, 14)

    def test_lower_left_and_cell_size_are_square_at_mid_latitude(self):
        # The same southwest corner and 30 m cells used for the 6 km Volgograd square.
        points = region([(48.6812415415, 44.4744959442)], 200, 200, 30)
        south, west, north, east = bounds(points)
        self.assertAlmostEqual(south, 48.6812415415)
        self.assertAlmostEqual(west, 44.4744959442)
        self.assertAlmostEqual(north, 48.7351404585, places=7)
        self.assertAlmostEqual(east, 44.5561740558, places=7)
        lat = math.radians((south + north) / 2)
        radius = 6_378_137
        meters_x = math.radians(east - west) / 200 * radius * math.cos(lat)
        meters_y = math.radians(north - south) / 200 * radius
        self.assertAlmostEqual(meters_x, 30, places=6)
        self.assertAlmostEqual(meters_y, 30, places=6)

    def test_cell_size_rejects_corners_and_a_nonpositive_length(self):
        with self.assertRaisesRegex(ValueError, "lower-left"):
            region([(55.7, 37.5), (55.8, 37.7)], 2, 2, 30)
        with self.assertRaisesRegex(ValueError, "positive"):
            region([(55.7, 37.5)], 2, 2, 0)

    def test_cli_rejects_a_single_corner(self):
        self.assertEqual(main(["--cells", "2", "2", "-o", "out.grd", "55.7", "37.5"]), 2)

    def test_cli_rejects_cell_size_with_two_corners(self):
        self.assertEqual(main(["--cells", "2", "2", "--cell-size", "30", "-o", "out.grd", "55.7", "37.5", "55.8", "37.7"]), 2)


if __name__ == "__main__":
    unittest.main()
