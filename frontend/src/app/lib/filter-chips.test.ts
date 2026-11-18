import { describe, expect, it } from 'vitest';
import type { QueryFilters } from './api-types';
import { filterChips } from './filter-chips';

const base: QueryFilters = {
  mode: 'live',
  start: null,
  end: null,
  minMag: null,
  countryId: null,
  excludeSynthetic: false,
};

const label = (f: QueryFilters, name?: string | null, id?: string) =>
  filterChips(f, name).find((c) => c.id === id)?.label;

describe('filterChips', () => {
  it('returns four chips with the no-filter texts', () => {
    const chips = filterChips(base);
    expect(chips.map((c) => c.id)).toEqual(['mode', 'period', 'minMag', 'country']);
    expect(label(base, null, 'minMag')).toBe('Sin mínimo de magnitud');
    expect(label(base, null, 'country')).toBe('Todos los países');
    expect(label(base, null, 'mode')).toBe('Modo: en vivo');
  });

  it('shows replay mode, minimum magnitude and country name', () => {
    const f = { ...base, mode: 'replay' as const, minMag: 4.5, countryId: 'AL' };
    expect(label(f, 'Albania', 'mode')).toBe('Modo: reproducción');
    expect(label(f, 'Albania', 'minMag')).toBe('Magnitud mínima: 4.5');
    expect(label(f, 'Albania', 'country')).toBe('País: Albania');
  });

  it('falls back to the country id without a name', () => {
    expect(label({ ...base, countryId: 'AL' }, null, 'country')).toBe('País: AL');
  });

  it('formats the period in UTC', () => {
    const f = { ...base, start: Date.UTC(2025, 0, 1), end: Date.UTC(2025, 11, 31, 23, 59) };
    expect(label(f, null, 'period')).toBe('Periodo: 2025-01-01 00:00:00 UTC a 2025-12-31 23:59:00 UTC');
    expect(label({ ...base, start: Date.UTC(2025, 0, 1) }, null, 'period')).toBe(
      'Periodo: 2025-01-01 00:00:00 UTC a ahora',
    );
  });

  it('never emits HTML', () => {
    const chips = filterChips({ ...base, countryId: 'X' }, '<b>Evil</b>');
    expect(chips.every((c) => typeof c.label === 'string')).toBe(true);
    expect(chips[3].label).toBe('País: <b>Evil</b>');
  });
});
