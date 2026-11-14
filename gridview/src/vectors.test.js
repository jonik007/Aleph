import assert from "node:assert/strict";
import test from "node:test";

import { parseGrd } from "../parseGrd.js";
import { buildVectors } from "./vectors.js";

test("a road draped on relief rises toward the north and stays east of the origin", () => {
  const terrain = parseGrd("DSAA\n2 2\n0 1\n10 12\n0 8\n1 3\n5 7\n");
  const lines = [{ kind: "road", name: "", points: [[0.2, 10.2], [0.8, 11.8]] }];
  const view = buildVectors(terrain, lines);
  const position = view.road.getAttribute("position");
  assert.ok(position.count >= 6);
  let westX = Infinity;
  let eastX = -Infinity;
  let southY = Infinity;
  let northY = -Infinity;
  let southZ = -Infinity;
  let northZ = Infinity;
  for (let i = 0; i < position.count; i++) {
    westX = Math.min(westX, position.getX(i));
    eastX = Math.max(eastX, position.getX(i));
    const y = position.getY(i);
    const z = position.getZ(i);
    if (z > 0) southY = Math.min(southY, y);
    if (z < 0) northY = Math.max(northY, y);
    southZ = Math.max(southZ, z);
    northZ = Math.min(northZ, z);
  }
  assert.ok(eastX > westX);
  assert.ok(northZ < 0 && southZ > 0);
  assert.ok(northY > southY);
  view.road.dispose();
});
