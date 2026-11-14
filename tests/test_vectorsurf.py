"""Road and railway filters, without downloading OpenStreetMap."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from vectorsurf_loader.__main__ import main
from vectorsurf_loader.grid import clip_linestring, features_from_osm, wanted


OSM = """<?xml version="1.0" encoding="UTF-8"?>
<osm>
  <node id="1" lat="1" lon="1"/>
  <node id="2" lat="1" lon="3"/>
  <node id="3" lat="3" lon="1"/>
  <way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="primary"/><tag k="name" v="Main"/></way>
  <way id="11"><nd ref="1"/><nd ref="3"/><tag k="highway" v="residential"/></way>
  <way id="12"><nd ref="1"/><nd ref="3"/><tag k="highway" v="primary_link"/></way>
  <way id="13"><nd ref="1"/><nd ref="3"/><tag k="railway" v="rail"/><tag k="name" v="Line"/></way>
  <way id="14"><nd ref="1"/><nd ref="2"/><tag k="railway" v="rail"/><tag k="service" v="yard"/></way>
  <way id="15"><nd ref="2"/><nd ref="3"/><tag k="railway" v="tram"/></way>
</osm>
"""


class FilterTests(unittest.TestCase):
    def test_major_roads_skip_links_and_residential(self):
        self.assertTrue(wanted("road", {"highway": "tertiary"}))
        self.assertFalse(wanted("road", {"highway": "primary_link"}))
        self.assertFalse(wanted("road", {"highway": "residential"}))
        self.assertFalse(wanted("road", {"highway": "footway"}))
        self.assertFalse(wanted("road", {"highway": "primary", "area": "yes"}))

    def test_rail_skips_yards_and_trams(self):
        self.assertTrue(wanted("rail", {"railway": "rail"}))
        self.assertTrue(wanted("rail", {"railway": "light_rail"}))
        self.assertFalse(wanted("rail", {"railway": "rail", "service": "siding"}))
        self.assertFalse(wanted("rail", {"railway": "tram"}))
        self.assertFalse(wanted("rail", {"railway": "abandoned"}))

    def test_line_is_cut_at_the_rectangle(self):
        pieces = clip_linestring([(1, 1), (3, 1), (3, 0)], 0, 0, 2, 2)
        self.assertEqual(len(pieces), 1)
        self.assertAlmostEqual(pieces[0][0][0], 1)
        self.assertAlmostEqual(pieces[0][-1][0], 2)
        self.assertAlmostEqual(pieces[0][-1][1], 1)

    def test_osm_keeps_one_major_road_and_one_railway(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "map.osm"
            path.write_text(OSM, encoding="utf-8")
            roads = features_from_osm(path, "road", 0, 0, 2, 2)
            rails = features_from_osm(path, "rail", 0, 0, 2, 2)
        self.assertEqual(len(roads), 1)
        self.assertEqual(roads[0]["properties"], {"kind": "road", "highway": "primary", "name": "Main"})
        self.assertEqual(roads[0]["geometry"]["coordinates"][-1], [2, 1])
        self.assertEqual(len(rails), 1)
        self.assertEqual(rails[0]["properties"]["railway"], "rail")
        self.assertEqual(rails[0]["properties"]["name"], "Line")

    def test_cli_rejects_a_single_corner(self):
        self.assertEqual(main(["--kind", "road", "--cells", "2", "2", "-o", "out.geojson", "48.7", "44.5"]), 2)

    def test_written_file_is_geojson(self):
        from vectorsurf_loader.grid import vector_geojson

        with TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "map.osm"
            source.write_text(OSM, encoding="utf-8")
            output = folder / "roads.geojson"

            class Maps:
                def export(self, polygon, path, progress):
                    path.write_bytes(source.read_bytes())

            class Fake:
                maps = Maps()

            result = vector_geojson([(0, 0), (2, 2)], "road", output, cache_dir=folder, client=Fake(),
                                     announce=lambda message: None)
            document = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["features"], 1)
        self.assertEqual(document["type"], "FeatureCollection")
        self.assertEqual(document["features"][0]["geometry"]["type"], "LineString")


if __name__ == "__main__":
    unittest.main()
