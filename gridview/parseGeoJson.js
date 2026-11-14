// GeoJSON lines from vectorsurf. Coordinates are [longitude, latitude].

function fail(message) {
  const error = new Error(message);
  error.name = "GridError";
  return error;
}

function line(coordinates) {
  const points = [];
  for (const pair of coordinates ?? []) {
    if (!Array.isArray(pair) || pair.length < 2) continue;
    const lon = Number(pair[0]);
    const lat = Number(pair[1]);
    if (Number.isFinite(lon) && Number.isFinite(lat)) points.push([lon, lat]);
  }
  return points.length >= 2 ? points : null;
}

export function parseGeoJson(text) {
  let data;
  try {
    data = JSON.parse(String(text).replace(/^\uFEFF/, ""));
  } catch {
    throw fail("Файл не JSON.");
  }
  const features = data?.type === "FeatureCollection" ? data.features : data?.type === "Feature" ? [data] : null;
  if (!Array.isArray(features)) throw fail("Нужен GeoJSON с линиями дорог или железных дорог.");
  const lines = [];
  for (const feature of features) {
    const kind = feature?.properties?.kind;
    if (kind !== "road" && kind !== "rail") continue;
    const geometry = feature.geometry;
    const parts = geometry?.type === "LineString" ? [geometry.coordinates]
      : geometry?.type === "MultiLineString" ? geometry.coordinates
        : [];
    for (const coordinates of parts) {
      const points = line(coordinates);
      if (points) lines.push({ kind, name: feature.properties.name || "", points });
    }
  }
  if (!lines.length) throw fail("В файле нет линий дорог или железных дорог.");
  return { lines };
}
