// Pure display formatting for the panel. Missing or non-finite values show "ND";
// 0 is a valid value and is shown as 0.

export const ND = 'ND';
export const NO_COUNTRY_LABEL = 'Sin país asignado';
export const ABSENT_TEXT = 'Sin dato';

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function decimal(value: number, digits: number): string {
  const fixed = value.toFixed(digits);
  // Avoid "-0.0" for tiny negatives that round to zero.
  const normalized = Number(fixed) === 0 ? (0).toFixed(digits) : fixed;
  return normalized.replace('.', ',');
}

export function formatNullable(
  value: number | null | undefined,
  digits = 1,
  unit = '',
): string {
  if (!isFiniteNumber(value)) return ND;
  return unit ? `${decimal(value, digits)} ${unit}` : decimal(value, digits);
}

export function formatMagnitude(value: number | null | undefined): string {
  return formatNullable(value, 1);
}

export function formatDepth(value: number | null | undefined): string {
  return formatNullable(value, 1, 'km');
}

function pad(n: number, width = 2): string {
  return String(n).padStart(width, '0');
}

export function formatUtc(ms: number | null | undefined): string {
  if (!isFiniteNumber(ms)) return ND;
  const date = new Date(ms);
  if (Number.isNaN(date.getTime())) return ND;
  const day = `${pad(date.getUTCFullYear(), 4)}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
  const time = `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())}`;
  return `${day} ${time} UTC`;
}

export function countryLabel(name: string | null | undefined): string {
  return typeof name === 'string' && name.trim() !== '' ? name : NO_COUNTRY_LABEL;
}

export function textOrAbsent(value: string | null | undefined): string {
  return typeof value === 'string' && value.trim() !== '' ? value : ABSENT_TEXT;
}
