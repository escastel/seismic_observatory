import { describe, expect, it } from 'vitest';
import type { MapEvent } from './api-types';
import { buildEventCard } from './event-card';

function makeEvent(overrides: Partial<MapEvent> = {}): MapEvent {
  return {
    id: 'us7000abcd',
    lon: -70.1,
    lat: -33.4,
    depthKm: 35.2,
    mag: 4.5,
    magType: 'ml',
    place: '10 km N de Santiago',
    time: Date.UTC(2026, 10, 15, 12, 30, 5),
    updated: null,
    countryId: 'CL',
    countryName: 'Chile',
    continent: 'América',
    subregion: 'Sudamérica',
    replayedAt: null,
    synthetic: null,
    ...overrides,
  };
}

function value(card: ReturnType<typeof buildEventCard>, key: string): string | undefined {
  return card.fields.find((f) => f.key === key)?.value;
}

describe('buildEventCard', () => {
  it('shows every live field without replay rows', () => {
    const card = buildEventCard(makeEvent(), 'live');
    expect(card.fields.map((f) => f.key)).toEqual([
      'id', 'magnitude', 'depth', 'place', 'time', 'country', 'continent', 'subregion',
    ]);
    expect(value(card, 'magnitude')).toBe('4,5 ml');
    expect(value(card, 'depth')).toBe('35,2 km');
    expect(value(card, 'time')).toBe('2026-11-15 12:30:05 UTC');
    expect(value(card, 'country')).toBe('Chile');
  });

  it('shows ND for missing values', () => {
    const card = buildEventCard(
      makeEvent({ mag: null, magType: null, depthKm: null, place: null, time: null, continent: null, subregion: null }),
      'live',
    );
    for (const key of ['magnitude', 'depth', 'place', 'time', 'continent', 'subregion']) {
      expect(value(card, key)).toBe('ND');
    }
  });

  it('uses the no-country label when the country is null or blank', () => {
    expect(value(buildEventCard(makeEvent({ countryName: null }), 'live'), 'country')).toBe('Sin país asignado');
    expect(value(buildEventCard(makeEvent({ countryName: '  ' }), 'live'), 'country')).toBe('Sin país asignado');
  });

  it('keeps negative magnitude and depth with their value, and zero as zero', () => {
    const negative = buildEventCard(makeEvent({ mag: -0.4, depthKm: -1.2 }), 'live');
    expect(value(negative, 'magnitude')).toBe('-0,4 ml');
    expect(value(negative, 'depth')).toBe('-1,2 km');
    const zero = buildEventCard(makeEvent({ mag: 0, depthKm: 0 }), 'live');
    expect(value(zero, 'magnitude')).toBe('0,0 ml');
    expect(value(zero, 'depth')).toBe('0,0 km');
  });

  it('returns text with markup unchanged', () => {
    const place = '<img src=x onerror=alert(1)> & "quotes"';
    const card = buildEventCard(makeEvent({ place, countryName: '<b>Chile</b>' }), 'live');
    expect(value(card, 'place')).toBe(place);
    expect(value(card, 'country')).toBe('<b>Chile</b>');
  });

  it('adds replay time and synthetic flag only in replay mode', () => {
    const replayedAt = Date.UTC(2026, 10, 16, 8, 0, 0);
    const card = buildEventCard(makeEvent({ replayedAt, synthetic: true }), 'replay');
    expect(value(card, 'replayedAt')).toBe('2026-11-16 08:00:00 UTC');
    expect(value(card, 'synthetic')).toBe('Sintético');
    expect(value(buildEventCard(makeEvent({ synthetic: false }), 'replay'), 'synthetic')).toBe('No sintético');
    const missing = buildEventCard(makeEvent(), 'replay');
    expect(value(missing, 'replayedAt')).toBe('ND');
    expect(value(missing, 'synthetic')).toBe('ND');
  });
});
