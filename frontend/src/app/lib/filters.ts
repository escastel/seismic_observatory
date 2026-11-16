import type { Mode, QueryFilters } from './api-types';

export interface RawFilterInputs {
  mode?: Mode;
  start: string;
  end: string;
  minMag: string;
  countryId: string;
}

export type FilterErrors = Partial<Record<'start' | 'end' | 'minMag' | 'countryId', string>>;

const INPUT_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/;
const COUNTRY_RE = /^[A-Za-z0-9]{1,8}$/;

function common(filters: QueryFilters): URLSearchParams {
  const params = new URLSearchParams();
  params.set('mode', filters.mode);
  if (filters.start !== null) params.set('start', new Date(filters.start).toISOString());
  if (filters.end !== null) params.set('end', new Date(filters.end).toISOString());
  if (filters.minMag !== null && Number.isFinite(filters.minMag)) {
    params.set('min_mag', String(filters.minMag));
  }
  if (filters.countryId) params.set('country_id', filters.countryId);
  if (filters.mode === 'replay' && filters.excludeSynthetic) {
    params.set('exclude_synthetic', 'true');
  }
  return params;
}

export function eventParams(filters: QueryFilters, limit: number, offset: number): URLSearchParams {
  const params = common(filters);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  return params;
}

export function statsParams(filters: QueryFilters): URLSearchParams {
  return common(filters);
}

/** Parses a datetime-local value as UTC (never the browser zone). */
export function parseUtcInput(text: string | null | undefined): number | null {
  const m = INPUT_RE.exec((text ?? '').trim());
  if (!m) return null;
  const [y, mo, d, h, mi] = m.slice(1, 6).map(Number) as number[];
  const s = m[6] === undefined ? 0 : Number(m[6]);
  const ms = Date.UTC(y, mo - 1, d, h, mi, s);
  const back = new Date(ms);
  if (
    back.getUTCFullYear() !== y ||
    back.getUTCMonth() !== mo - 1 ||
    back.getUTCDate() !== d ||
    back.getUTCHours() !== h ||
    back.getUTCMinutes() !== mi
  ) {
    return null;
  }
  return ms;
}

/** Inverse of parseUtcInput: value for a datetime-local input, in UTC. */
export function toUtcInput(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return '';
  const d = new Date(ms);
  if (Number.isNaN(d.getTime())) return '';
  return d.toISOString().slice(0, 16);
}

export function validateFilters(raw: RawFilterInputs): FilterErrors {
  const errors: FilterErrors = {};
  const startText = raw.start.trim();
  const endText = raw.end.trim();
  const start = parseUtcInput(startText);
  const end = parseUtcInput(endText);
  if (startText && start === null) errors.start = 'La fecha de inicio no es válida.';
  if (endText && end === null) errors.end = 'La fecha de fin no es válida.';
  if (start !== null && end !== null && start >= end) {
    errors.start = 'El inicio debe ser anterior al fin.';
  }
  const mag = raw.minMag.trim();
  if (mag !== '' && !Number.isFinite(Number(mag))) {
    errors.minMag = 'La magnitud mínima debe ser un número.';
  }
  const country = raw.countryId.trim();
  if (country !== '' && !COUNTRY_RE.test(country)) {
    errors.countryId = 'El identificador de país debe tener de 1 a 8 caracteres alfanuméricos.';
  }
  return errors;
}
