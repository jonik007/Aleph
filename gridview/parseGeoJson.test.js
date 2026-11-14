import assert from "node:assert/strict";
import test from "node:test";

import { parseGeoJson } from "./parseGeoJson.js";

test("reads road and rail lines and skips anything else", () => {
  const parsed = parseGeoJson(JSON.stringify({
    type: "FeatureCollection",
    features: [
      { type: "Feature", properties: { kind: "road", name: "Main" }, geometry: { type: "LineString", coordinates: [[44.5, 48.7], [44.6, 48.71]] } },
      { type: "Feature", properties: { kind: "rail" }, geometry: { type: "MultiLineString", coordinates: [[[44.4, 48.7], [44.4, 48.8]], [[0, 0]]] } },
      { type: "Feature", properties: { kind: "water" }, geometry: { type: "LineString", coordinates: [[0, 0], [1, 1]] } },
    ],
  }));
  assert.equal(parsed.lines.length, 2);
  assert.equal(parsed.lines[0].kind, "road");
  assert.equal(parsed.lines[0].name, "Main");
  assert.equal(parsed.lines[1].kind, "rail");
  assert.equal(parsed.lines[1].points.length, 2);
});

test("rejects a file without lines", () => {
  assert.throws(() => parseGeoJson('{"type":"FeatureCollection","features":[]}'), /линий/);
  assert.throws(() => parseGeoJson("not json"), /JSON/);
});
