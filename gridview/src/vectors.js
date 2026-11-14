import * as THREE from "three";

const RADIUS = 6_378_137;
const LIFT = 4;
const WIDTH = { road: 0.007, rail: 0.0045 };

function sample(terrain, lon, lat) {
  const { nx, ny } = terrain;
  const dx = nx === 1 ? 1 : (terrain.xmax - terrain.xmin) / (nx - 1);
  const dy = ny === 1 ? 1 : (terrain.ymax - terrain.ymin) / (ny - 1);
  const col = nx === 1 ? 0 : (lon - terrain.xmin) / dx;
  const row = ny === 1 ? 0 : (lat - terrain.ymin) / dy;
  if (col < -0.5 || row < -0.5 || col > nx - 0.5 || row > ny - 0.5) return null;
  const c = Math.min(nx - 1, Math.max(0, col));
  const r = Math.min(ny - 1, Math.max(0, row));
  const c0 = Math.floor(c);
  const r0 = Math.floor(r);
  const c1 = Math.min(nx - 1, c0 + 1);
  const r1 = Math.min(ny - 1, r0 + 1);
  const tx = c - c0;
  const ty = r - r0;
  const at = (rowIndex, colIndex) => {
    const value = terrain.values[rowIndex * nx + colIndex];
    return Number.isFinite(value) ? value : null;
  };
  const v00 = at(r0, c0);
  const v10 = at(r0, c1);
  const v01 = at(r1, c0);
  const v11 = at(r1, c1);
  if (v00 == null && v10 == null && v01 == null && v11 == null) return null;
  const a = v00 ?? v10 ?? v01 ?? v11;
  const b = v10 ?? a;
  const d = v01 ?? a;
  const e = v11 ?? b ?? d;
  return a * (1 - tx) * (1 - ty) + b * tx * (1 - ty) + d * (1 - tx) * ty + e * tx * ty;
}

function ribbon(points, half) {
  const out = [];
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i];
    const b = points[i + 1];
    const dx = b[0] - a[0];
    const dz = b[2] - a[2];
    const length = Math.hypot(dx, dz);
    if (length < 0.05) continue;
    const ox = (-dz / length) * half;
    const oz = (dx / length) * half;
    out.push(
      a[0] + ox, a[1], a[2] + oz,
      a[0] - ox, a[1], a[2] - oz,
      b[0] + ox, b[1], b[2] + oz,
      a[0] - ox, a[1], a[2] - oz,
      b[0] - ox, b[1], b[2] - oz,
      b[0] + ox, b[1], b[2] + oz,
    );
  }
  return out;
}

// Local meters matching the relief mesh: x east, y up from the lowest sample, z south.
export function buildVectors(terrain, lines) {
  if (!terrain || !lines?.length) return null;
  const midLat = ((terrain.ymin + terrain.ymax) / 2) * (Math.PI / 180);
  const metersLat = (Math.PI / 180) * RADIUS;
  const metersLon = metersLat * Math.max(Math.cos(midLat), 0.01);
  const originLon = (terrain.xmin + terrain.xmax) / 2;
  const originLat = (terrain.ymin + terrain.ymax) / 2;
  const dx = terrain.nx === 1 ? 1 : (terrain.xmax - terrain.xmin) / (terrain.nx - 1);
  const dy = terrain.ny === 1 ? 1 : (terrain.ymax - terrain.ymin) / (terrain.ny - 1);
  const span = Math.max(Math.abs(terrain.xmax - terrain.xmin) * metersLon, Math.abs(terrain.ymax - terrain.ymin) * metersLat, 1);
  const buckets = { road: [], rail: [] };

  for (const item of lines) {
    const bucket = buckets[item.kind];
    if (!bucket) continue;
    const half = span * WIDTH[item.kind] / 2;
    const run = [];
    const flush = () => {
      if (run.length >= 2) bucket.push(...ribbon(run, half));
      run.length = 0;
    };
    const push = (lon, lat) => {
      const height = sample(terrain, lon, lat);
      if (height == null) {
        flush();
        return;
      }
      run.push([(lon - originLon) * metersLon, height - terrain.zmin + LIFT, (originLat - lat) * metersLat]);
    };
    for (let i = 1; i < item.points.length; i++) {
      const [lon0, lat0] = item.points[i - 1];
      const [lon1, lat1] = item.points[i];
      const steps = Math.max(1, Math.ceil(Math.max(Math.abs(lon1 - lon0) / dx, Math.abs(lat1 - lat0) / dy) * 2));
      for (let step = i === 1 ? 0 : 1; step <= steps; step++) {
        const t = step / steps;
        push(lon0 + (lon1 - lon0) * t, lat0 + (lat1 - lat0) * t);
      }
    }
    flush();
  }

  function geometry(values) {
    if (!values.length) return null;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(values), 3));
    return geometry;
  }

  const road = geometry(buckets.road);
  const rail = geometry(buckets.rail);
  if (!road && !rail) return null;
  return { road, rail };
}
