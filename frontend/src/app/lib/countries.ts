export interface CountryOption {
  id: string;
  name: string;
}

const VALID_ID = /^[A-Za-z0-9]{1,8}$/;

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value.trim() : null;
}

/** Builds the country selector catalog from the countries GeoJSON. Never throws. */
export function buildCountryCatalog(geojson: unknown): CountryOption[] {
  if (typeof geojson !== 'object' || geojson === null) return [];
  const features = (geojson as { features?: unknown }).features;
  if (!Array.isArray(features)) return [];

  const byId = new Map<string, CountryOption>();
  for (const feature of features) {
    if (typeof feature !== 'object' || feature === null) continue;
    const props = (feature as { properties?: unknown }).properties;
    if (typeof props !== 'object' || props === null) continue;
    const p = props as Record<string, unknown>;
    const rawId = typeof p['ADM0_A3'] === 'string' ? p['ADM0_A3'].trim() : '';
    if (!VALID_ID.test(rawId) || byId.has(rawId)) continue;
    byId.set(rawId, {
      id: rawId,
      name: text(p['NAME_ES']) ?? text(p['ADMIN']) ?? rawId,
    });
  }
  return [...byId.values()].sort(
    (a, b) => a.name.localeCompare(b.name, 'es') || a.id.localeCompare(b.id),
  );
}
