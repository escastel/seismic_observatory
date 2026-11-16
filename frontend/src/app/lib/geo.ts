// Pure map logic: coordinate validation, marker size, depth categories and popup text.
// No Angular or Leaflet imports; popup lines are plain strings (never HTML).

import type { MapEvent, Mode } from './api-types';
import { countryLabel, formatDepth, formatMagnitude, formatUtc, ND, textOrAbsent } from './format';

export const MIN_RADIUS = 3;
export const MAX_RADIUS = 18;

export type DepthKey = 'shallow' | 'intermediate' | 'deep' | 'unknown';

export interface DepthCategory {
  key: DepthKey;
  color: string;
  label: string;
}

export interface LegendItem extends DepthCategory {
  /** True when the marker is drawn with a dashed border. */
  dashed: boolean;
}

const SHALLOW: DepthCategory = { key: 'shallow', color: '#e8a317', label: 'Superficial (< 70 km)' };
const INTERMEDIATE: DepthCategory = {
  key: 'intermediate',
  color: '#e35b37',
  label: 'Intermedia (70 a 299,99 km)',
};
const DEEP: DepthCategory = { key: 'deep', color: '#7b3fb6', label: 'Profunda (≥ 300 km)' };
const UNKNOWN: DepthCategory = { key: 'unknown', color: '#64748b', label: 'ND (sin profundidad)' };

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function isDrawable(event: MapEvent): boolean {
  const { lon, lat } = event;
  return (
    isFiniteNumber(lon) && isFiniteNumber(lat) && lon >= -180 && lon <= 180 && lat >= -90 && lat <= 90
  );
}

export function partitionDrawable(events: MapEvent[]): { drawable: MapEvent[]; omitted: number } {
  const drawable = events.filter(isDrawable);
  return { drawable, omitted: events.length - drawable.length };
}

export function markerRadius(mag: number | null | undefined): number {
  if (!isFiniteNumber(mag)) return MIN_RADIUS;
  const radius = 2 + mag * 2;
  return Math.min(MAX_RADIUS, Math.max(MIN_RADIUS, radius));
}

export function depthCategory(depthKm: number | null | undefined): DepthCategory {
  if (!isFiniteNumber(depthKm)) return { ...UNKNOWN };
  if (depthKm < 70) return { ...SHALLOW };
  if (depthKm < 300) return { ...INTERMEDIATE };
  return { ...DEEP };
}

/** True when magnitude or depth is missing: the marker gets a dashed border. */
export function isUnvalued(event: MapEvent): boolean {
  return !isFiniteNumber(event.mag) || !isFiniteNumber(event.depthKm);
}

function syntheticText(value: boolean | null | undefined): string {
  if (value === true) return 'Sí';
  if (value === false) return 'No';
  return ND;
}

export function popupLines(event: MapEvent, mode: Mode): string[] {
  const lines = [
    `ID: ${event.id}`,
    `Magnitud: ${formatMagnitude(event.mag)}`,
    `Profundidad: ${formatDepth(event.depthKm)}`,
    `Hora: ${formatUtc(event.time)}`,
    `País: ${countryLabel(event.countryName)}`,
    `Continente: ${textOrAbsent(event.continent)}`,
    `Subregión: ${textOrAbsent(event.subregion)}`,
  ];
  if (mode === 'replay') {
    lines.push(`Reproducido: ${formatUtc(event.replayedAt)}`);
    lines.push(`Sintético: ${syntheticText(event.synthetic)}`);
  }
  return lines;
}

export function legendItems(): LegendItem[] {
  return [
    { ...SHALLOW, dashed: false },
    { ...INTERMEDIATE, dashed: false },
    { ...DEEP, dashed: false },
    { ...UNKNOWN, dashed: true },
  ];
}
