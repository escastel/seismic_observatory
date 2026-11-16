import { describe, expect, it } from 'vitest';
import type { QueryFilters } from './api-types';
import {
  eventParams,
  parseUtcInput,
  statsParams,
  toUtcInput,
  validateFilters,
} from './filters';

const base: QueryFilters = {
  mode: 'live',
  start: null,
  end: null,
  minMag: null,
  countryId: null,
  excludeSynthetic: false,
};

describe('parseUtcInput / toUtcInput', () => {
  it('interprets the value as UTC', () => {
    expect(parseUtcInput('2026-11-16T10:30')).toBe(Date.UTC(2026, 10, 16, 10, 30));
  });
  it('returns null for empty or invalid text', () => {
    expect(parseUtcInput('')).toBeNull();
    expect(parseUtcInput('hola')).toBeNull();
    expect(parseUtcInput('2026-13-40T10:30')).toBeNull();
    expect(parseUtcInput('2026-02-30T10:30')).toBeNull();
  });
  it('round-trips', () => {
    expect(toUtcInput(parseUtcInput('2026-11-16T10:30'))).toBe('2026-11-16T10:30');
    expect(toUtcInput(null)).toBe('');
  });
});

describe('params', () => {
  it('sends mode, ISO Z dates and min_mag 0', () => {
    const p = eventParams(
      { ...base, start: Date.UTC(2026, 10, 16, 10, 30), end: Date.UTC(2026, 10, 17), minMag: 0 },
      50,
      100,
    );
    expect(p.get('mode')).toBe('live');
    expect(p.get('start')).toBe('2026-11-16T10:30:00.000Z');
    expect(p.get('end')).toBe('2026-11-17T00:00:00.000Z');
    expect(p.get('min_mag')).toBe('0');
    expect(p.get('limit')).toBe('50');
    expect(p.get('offset')).toBe('100');
  });
  it('omits empty filters', () => {
    const p = statsParams(base);
    expect([...p.keys()]).toEqual(['mode']);
  });
  it('sends exclude_synthetic only in replay', () => {
    expect(statsParams({ ...base, excludeSynthetic: true }).has('exclude_synthetic')).toBe(false);
    const p = statsParams({ ...base, mode: 'replay', excludeSynthetic: true });
    expect(p.get('exclude_synthetic')).toBe('true');
    expect(p.get('mode')).toBe('replay');
  });
  it('stats has no limit, offset or format', () => {
    const p = statsParams({ ...base, countryId: 'ESP', minMag: 4.5 });
    expect(p.has('limit')).toBe(false);
    expect(p.has('offset')).toBe(false);
    expect(p.has('format')).toBe(false);
    expect(p.get('country_id')).toBe('ESP');
  });
});

describe('validateFilters', () => {
  const ok = { start: '', end: '', minMag: '', countryId: '' };
  it('accepts empty inputs', () => {
    expect(validateFilters(ok)).toEqual({});
  });
  it('requires start before end', () => {
    expect(
      validateFilters({ ...ok, start: '2026-11-16T10:30', end: '2026-11-16T10:30' }).start,
    ).toBeTruthy();
    expect(
      validateFilters({ ...ok, start: '2026-11-17T00:00', end: '2026-11-16T00:00' }).start,
    ).toBeTruthy();
    expect(validateFilters({ ...ok, start: '2026-11-16T00:00', end: '2026-11-17T00:00' })).toEqual(
      {},
    );
  });
  it('validates min_mag', () => {
    expect(validateFilters({ ...ok, minMag: 'abc' }).minMag).toBeTruthy();
    expect(validateFilters({ ...ok, minMag: 'Infinity' }).minMag).toBeTruthy();
    expect(validateFilters({ ...ok, minMag: '0' })).toEqual({});
    expect(validateFilters({ ...ok, minMag: '4.5' })).toEqual({});
  });
  it('validates country id', () => {
    expect(validateFilters({ ...ok, countryId: 'ESP' })).toEqual({});
    expect(validateFilters({ ...ok, countryId: 'ES P' }).countryId).toBeTruthy();
    expect(validateFilters({ ...ok, countryId: 'ABCDEFGHI' }).countryId).toBeTruthy();
  });
});
