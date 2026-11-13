import assert from "node:assert/strict";
import test from "node:test";

import { parseGrd } from "./parseGrd.js";
import { buildSurface } from "./src/mesh.js";

test("southern row stays south, and water cells of a matching grid turn blue", () => {
  const terrain = parseGrd("DSAA\n2 2\n0 1\n10 12\n0 8\n1 3\n5 7\n");
  const water = parseGrd("DSAA\n2 2\n0 1\n10 12\n0 1\n0 1\n1 0\n");
  const view = buildSurface(terrain, water);
  const position = view.geometry.getAttribute("position");
  const color = view.geometry.getAttribute("color");
  assert.ok(position.getZ(0) < position.getZ(2));
  assert.ok(position.getX(0) < position.getX(1));
  assert.equal(position.getY(0), 0);
  assert.equal(position.getY(1), 2);
  assert.equal(position.getY(2), 4);
  assert.equal(position.getY(3), 6);
  assert.ok(color.getZ(0) > color.getX(0));
  assert.ok(color.getZ(3) > color.getX(3));
  assert.ok(color.getY(1) > color.getZ(1));
  assert.equal(view.geometry.index.count, 6);
  view.geometry.dispose();
});
