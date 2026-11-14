import assert from "node:assert/strict";
import test from "node:test";

import { parseGrd, sameShape } from "./parseGrd.js";

test("reads a south-first DSAA grid and treats the Surfer blank as missing", () => {
  const grid = parseGrd(`DSAA
2 2
10 12
20 23
1 4
1.5 1.70141e+38
3 4
`);
  assert.equal(grid.nx, 2);
  assert.equal(grid.ny, 2);
  assert.deepEqual([...grid.values], [1.5, NaN, 3, 4]);
  assert.equal(grid.zmin, 1.5);
  assert.equal(grid.zmax, 4);
  assert.equal(grid.blanks, 1);
  assert.equal(grid.xmin, 10);
  assert.equal(grid.ymax, 23);
});

test("rejects a file that is not DSAA or has the wrong count", () => {
  assert.throws(() => parseGrd("DSBB\n1 1\n0 1\n0 1\n0 1\n0\n"), /DSAA/);
  assert.throws(() => parseGrd("DSAA\n2 2\n0 1\n0 1\n0 1\n1 2 3\n"), /2 × 2/);
});

test("sameShape compares cell counts", () => {
  const one = parseGrd("DSAA\n1 2\n0 0\n1 2\n0 1\n5\n6\n");
  const two = parseGrd("DSAA\n1 2\n3 3\n4 5\n0 1\n0\n1\n");
  assert.equal(sameShape(one, two), true);
  assert.equal(sameShape(one, parseGrd("DSAA\n2 2\n0 1\n0 1\n0 1\n1 1\n1 1\n")), false);
});
