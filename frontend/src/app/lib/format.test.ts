import { describe, expect, it } from 'vitest';
import {
  countryLabel,
  formatDepth,
  formatMagnitude,
  formatNullable,
  formatUtc,
  textOrAbsent,
} from './format';

const MISSING = [null, undefined, Number.NaN, Infinity, -Infinity];

describe('formatMagnitude and formatDepth', () => {
  it.each(MISSING)('shows ND for %s', (value) => {
    expect(formatMagnitude(value as number | null | undefined)).toBe('ND');
    expect(formatDepth(value as number | null | undefined)).toBe('ND');
  });

  it('treats 0 as a valid value', () => {
    expect(formatMagnitude(0)).toBe('0,0');
    expect(formatDepth(0)).toBe('0,0 km');
  });

  it('formats regular values with a decimal comma', () => {
    expect(formatMagnitude(4.56)).toBe('4,6');
    expect(formatDepth(12.5)).toBe('12,5 km');
  });

  it('keeps negative values (depth above sea level)', () => {
    expect(formatDepth(-1.2)).toBe('-1,2 km');
    expect(formatMagnitude(-0.01)).toBe('0,0');
  });
});

describe('formatNullable', () => {
  it('honours digits and unit', () => {
    expect(formatNullable(3.14159, 2, 'm')).toBe('3,14 m');
    expect(formatNullable(7, 0)).toBe('7');
    expect(formatNullable(null, 2, 'm')).toBe('ND');
  });
});

describe('formatUtc', () => {
  it('formats epoch ms as UTC', () => {
    expect(formatUtc(0)).toBe('1970-01-01 00:00:00 UTC');
    expect(formatUtc(Date.UTC(2026, 10, 16, 8, 5, 9))).toBe('2026-11-16 08:05:09 UTC');
  });

  it.each(MISSING)('shows ND for %s', (value) => {
    expect(formatUtc(value as number | null | undefined)).toBe('ND');
  });

  it('shows ND for out-of-range dates', () => {
    expect(formatUtc(8.64e15 + 1)).toBe('ND');
  });
});

describe('countryLabel', () => {
  it('returns the name when present', () => {
    expect(countryLabel('Chile')).toBe('Chile');
  });

  it('labels missing countries', () => {
    expect(countryLabel(null)).toBe('Sin país asignado');
    expect(countryLabel(undefined)).toBe('Sin país asignado');
    expect(countryLabel('  ')).toBe('Sin país asignado');
  });
});

describe('textOrAbsent', () => {
  it('returns the text when present', () => {
    expect(textOrAbsent('South America')).toBe('South America');
  });

  it('returns an absence text for null, undefined or blank', () => {
    const absent = textOrAbsent(null);
    expect(absent).not.toBe('');
    expect(textOrAbsent(undefined)).toBe(absent);
    expect(textOrAbsent('')).toBe(absent);
  });
});
