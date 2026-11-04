"""Land/water cell masks, without downloading OpenStreetMap."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from watersurf_loader.__main__ import main
from watersurf_loader.grid import cell_mask


def square(west, south, east, north):
    return [[(west, south), (east, south), (east, north), (west, north), (west, south)]]


class MaskTests(unittest.TestCase):
    def test_aligned_water_does_not_spill_into_the_next_cell(self):
        # Cells are 1° squares. The polygon covers exactly the two southwestern cells.
        mask = cell_mask(0, 0, 4, 4, 4, 4, [square(0, 0, 2, 1)])
        self.assertEqual(mask.shape, (4, 4))
        self.assertTrue(np.array_equal(mask[0], [0, 0, 1, 1]))
        self.assertTrue(np.all(mask[1:] == 1))

    def test_polygon_inside_one_cell_marks_that_cell(self):
        mask = cell_mask(0, 0, 4, 4, 4, 4, [square(1.2, 1.2, 1.8, 1.8)])
        self.assertEqual(mask[1, 1], 0)
        self.assertEqual(int(mask.sum()), 16 - 1)

    def test_corner_clip_marks_the_cell_whose_center_stays_dry(self):
        triangle = [[(1.05, 0.7), (1.4, 0.7), (1.05, 1.25), (1.05, 0.7)]]
        mask = cell_mask(0, 0, 4, 4, 4, 4, [triangle])
        self.assertEqual(mask[0, 1], 0)
        self.assertEqual(mask[1, 1], 0)
        self.assertEqual(mask[0, 0], 1)
        self.assertEqual(mask[1, 0], 1)

    def test_island_in_a_lake_stays_land(self):
        lake = [[(1, 1), (5, 1), (5, 5), (1, 5), (1, 1)],
                [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)]]
        mask = cell_mask(0, 0, 6, 6, 6, 6, [lake])
        self.assertTrue(np.array_equal(mask[2:4, 2:4], np.ones((2, 2))))
        self.assertEqual(mask[1, 1], 0)
        self.assertEqual(mask[4, 4], 0)
        self.assertEqual(mask[0, 0], 1)
        self.assertEqual(mask[5, 5], 1)

    def test_grd_uses_one_value_per_cell_at_its_center(self):
        from terrainsurf_loader.grid import write_grd

        values = cell_mask(10, 20, 14, 22, 4, 2, [square(10, 20, 12, 21)])
        with TemporaryDirectory() as directory:
            path = Path(directory) / "water.grd"
            write_grd(path, 10.5, 20.5, 13.5, 21.5, values)
            lines = path.read_text(encoding="ascii").splitlines()
        self.assertEqual(lines[1], "4 2")
        self.assertEqual(lines[2], "10.5000000000 13.5000000000")
        self.assertEqual(lines[3], "20.5000000000 21.5000000000")
        self.assertTrue(lines[5].startswith("0.000000 0.000000 1.000000 1.000000"))
        self.assertTrue(lines[6].startswith("1.000000 1.000000 1.000000 1.000000"))

    def test_cli_rejects_a_single_corner(self):
        self.assertEqual(main(["--cells", "2", "2", "-o", "out.grd", "48.7", "44.5"]), 2)


if __name__ == "__main__":
    unittest.main()
