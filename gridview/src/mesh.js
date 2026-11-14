import * as THREE from "three";

const RADIUS = 6_378_137;
const MAX_EDGE = 700;
const WATER = [0.15, 0.4, 0.66];
const SAND = [0.76, 0.68, 0.46];

function axisIndexes(count) {
  const stride = Math.max(1, Math.ceil(count / MAX_EDGE));
  const index = [];
  for (let i = 0; i < count; i += stride) index.push(i);
  if (index[index.length - 1] !== count - 1) index.push(count - 1);
  return index;
}

function mix(start, end, t) {
  return start.map((channel, i) => channel + (end[i] - channel) * t);
}

function elevationColor(z, zmin, zmax) {
  if (z < 0) {
    const depth = zmin < 0 ? Math.min(1, z / zmin) : 1;
    return mix([0.47, 0.7, 0.78], [0.1, 0.28, 0.48], depth);
  }
  const t = Math.min(1, z / Math.max(zmax, 1));
  const stops = [
    [0, [0.27, 0.46, 0.26]],
    [0.22, [0.55, 0.62, 0.3]],
    [0.5, [0.7, 0.52, 0.3]],
    [0.78, [0.52, 0.48, 0.44]],
    [1, [0.94, 0.93, 0.9]],
  ];
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i][0]) {
      const local = (t - stops[i - 1][0]) / (stops[i][0] - stops[i - 1][0]);
      return mix(stops[i - 1][1], stops[i][1], local);
    }
  }
  return stops.at(-1)[1];
}

// One mesh in local meters: x east, y up from the lowest sample, z south.
// North is -Z so that a camera looking north keeps east on the right of the screen.
// A water grid of the same size paints 0-cells blue. Without relief, water is a flat map.
export function buildSurface(terrain, water) {
  const source = terrain ?? water;
  const cols = axisIndexes(source.nx);
  const rows = axisIndexes(source.ny);
  const nx = cols.length;
  const ny = rows.length;
  const lat = ((source.ymin + source.ymax) / 2) * (Math.PI / 180);
  const metersLat = (Math.PI / 180) * RADIUS;
  const metersLon = metersLat * Math.max(Math.cos(lat), 0.01);
  const lonAt = (col) => (source.nx === 1 ? source.xmin : source.xmin + ((source.xmax - source.xmin) * col) / (source.nx - 1));
  const latAt = (row) => (source.ny === 1 ? source.ymin : source.ymin + ((source.ymax - source.ymin) * row) / (source.ny - 1));
  const easting = cols.map((col) => lonAt(col) * metersLon);
  const northing = rows.map((row) => latAt(row) * metersLat);
  const xMid = (easting[0] + easting.at(-1)) / 2;
  const zMid = (northing[0] + northing.at(-1)) / 2;
  const overlay = Boolean(terrain && water && water.nx === terrain.nx && water.ny === terrain.ny);

  const positions = new Float32Array(nx * ny * 3);
  const colors = new Float32Array(nx * ny * 3);
  const drawn = new Uint8Array(nx * ny);
  for (let j = 0; j < ny; j++) {
    for (let i = 0; i < nx; i++) {
      const cell = rows[j] * source.nx + cols[i];
      const slot = j * nx + i;
      const height = source.values[cell];
      const wet = overlay
        ? water.values[rows[j] * water.nx + cols[i]] === 0
        : !terrain && height === 0;
      positions[slot * 3] = easting[i] - xMid;
      positions[slot * 3 + 1] = terrain && Number.isFinite(height) ? height - terrain.zmin : 0;
      positions[slot * 3 + 2] = zMid - northing[j];
      const color = wet ? WATER : terrain && Number.isFinite(height) ? elevationColor(height, terrain.zmin, terrain.zmax) : SAND;
      colors[slot * 3] = color[0];
      colors[slot * 3 + 1] = color[1];
      colors[slot * 3 + 2] = color[2];
      drawn[slot] = Number.isFinite(height) ? 1 : 0;
    }
  }

  const indices = [];
  for (let j = 0; j < ny - 1; j++) {
    for (let i = 0; i < nx - 1; i++) {
      const a = j * nx + i;
      const b = a + 1;
      const c = a + nx;
      const d = c + 1;
      if (drawn[a] && drawn[b] && drawn[c] && drawn[d]) indices.push(a, c, b, b, c, d);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  if (indices.length) geometry.setIndex(indices);
  geometry.computeVertexNormals();
  const width = Math.max(Math.abs(easting.at(-1) - easting[0]), 1);
  const depth = Math.max(Math.abs(northing.at(-1) - northing[0]), 1);
  return { geometry, width, depth, thinned: nx !== source.nx || ny !== source.ny, shown: [nx, ny] };
}
