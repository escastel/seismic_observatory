import { describe, expect, it } from 'vitest';
import type { MapEvent } from './api-types';
import {
  depthCategory,
  isUnvalued,
  legendItems,
  markerRadius,
  partitionDrawable,
  popupLines,
} from './geo';

function ev(over: Partial<MapEvent> = {}): MapEvent {
  return {
    id: 'e1',
    lon: 10,
    lat: 20,
    depthKm: 10,
    mag: 4,
    magType: 'ml',
    place: 'X',
    time: Date.UTC(2026, 0, 2, 3, 4, 5),
    updated: null,
    countryId: 'ES',
    countryName: 'España',
    continent: 'Europa',
    subregion: 'Sur de Europa',
    replayedAt: Date.UTC(2026, 5, 1, 0, 0, 0),
    synthetic: false,
    ...over,
  };
}

describe('partitionDrawable', () => {
  it('keeps valid events and counts omitted ones', () => {
    const events = [
      ev({ id: 'a' }),
      ev({ id: 'b', lon: null }),
      ev({ id: 'c', lat: null }),
      ev({ id: 'd', lon: NaN }),
      ev({ id: 'e', lat: Infinity }),
      ev({ id: 'f', lon: 180.1 }),
      ev({ id: 'g', lat: -90.5 }),
    ];
    const { drawable, omitted } = partitionDrawable(events);
    expect(drawable.map((e) => e.id)).toEqual(['a']);
    expect(omitted).toBe(6);
  });

  it('accepts the exact bounds and zero', () => {
    const { drawable, omitted } = partitionDrawable([
      ev({ lon: -180, lat: -90 }),
      ev({ lon: 180, lat: 90 }),
      ev({ lon: 0, lat: 0 }),
    ]);
    expect(drawable).toHaveLength(3);
    expect(omitted).toBe(0);
  });

  it('handles an empty list', () => {
    expect(partitionDrawable([])).toEqual({ drawable: [], omitted: 0 });
  });
});

describe('markerRadius', () => {
  it('increases with magnitude', () => {
    expect(markerRadius(6)).toBeGreaterThan(markerRadius(4));
    expect(markerRadius(4)).toBeGreaterThan(markerRadius(2));
  });

  it('is clamped between 3 and 18', () => {
    expect(markerRadius(-5)).toBe(3);
    expect(markerRadius(0)).toBeGreaterThanOrEqual(3);
    expect(markerRadius(10)).toBe(18);
    expect(markerRadius(100)).toBe(18);
  });

  it('uses the minimum radius for null and non-finite', () => {
    expect(markerRadius(null)).toBe(3);
    expect(markerRadius(NaN)).toBe(3);
  });
});

describe('depthCategory', () => {
  it('classifies by depth thresholds', () => {
    expect(depthCategory(0).key).toBe('shallow');
    expect(depthCategory(69.99).key).toBe('shallow');
    expect(depthCategory(70).key).toBe('intermediate');
    expect(depthCategory(299.99).key).toBe('intermediate');
    expect(depthCategory(300).key).toBe('deep');
    expect(depthCategory(650).key).toBe('deep');
  });

  it('maps null to unknown grey', () => {
    const c = depthCategory(null);
    expect(c.key).toBe('unknown');
    expect(c.color).toBe('#64748b');
  });

  it('keeps the palette', () => {
    expect(depthCategory(10).color).toBe('#e8a317');
    expect(depthCategory(100).color).toBe('#e35b37');
    expect(depthCategory(400).color).toBe('#7b3fb6');
  });
});

describe('isUnvalued', () => {
  it('is true when magnitude or depth is null', () => {
    expect(isUnvalued(ev({ mag: null }))).toBe(true);
    expect(isUnvalued(ev({ depthKm: null }))).toBe(true);
  });

  it('is false when both are present, including zero', () => {
    expect(isUnvalued(ev())).toBe(false);
    expect(isUnvalued(ev({ mag: 0, depthKm: 0 }))).toBe(false);
  });
});

describe('popupLines', () => {
  it('lists the live fields as plain text', () => {
    const lines = popupLines(ev(), 'live');
    const text = lines.join('\n');
    expect(text).toContain('e1');
    expect(text).toContain('4,0');
    expect(text).toContain('10,0 km');
    expect(text).toContain('2026-01-02 03:04:05 UTC');
    expect(text).toContain('España');
    expect(text).toContain('Europa');
    expect(text).toContain('Sur de Europa');
    expect(text).not.toContain('Sintético');
    expect(text).not.toContain('Reproducido');
  });

  it('adds replayed_at and synthetic in replay', () => {
    const text = popupLines(ev({ synthetic: true }), 'replay').join('\n');
    expect(text).toContain('Reproducido');
    expect(text).toContain('2026-06-01 00:00:00 UTC');
    expect(text).toContain('Sintético');
    expect(text).toContain('Sí');
  });

  it('shows ND and the no-country label for nulls', () => {
    const text = popupLines(ev({ mag: null, depthKm: null, countryName: null }), 'live').join('\n');
    expect(text).toContain('ND');
    expect(text).toContain('Sin país asignado');
  });

  it('returns text containing markup unchanged', () => {
    const lines = popupLines(ev({ id: '<b>x</b>', countryName: '<b>Peru</b>' }), 'live');
    expect(lines.some((l) => l.includes('<b>x</b>'))).toBe(true);
    expect(lines.some((l) => l.includes('<b>Peru</b>'))).toBe(true);
    lines.forEach((l) => expect(typeof l).toBe('string'));
  });
});

describe('legendItems', () => {
  it('has the four categories including ND with text labels', () => {
    const items = legendItems();
    expect(items.map((i) => i.key)).toEqual(['shallow', 'intermediate', 'deep', 'unknown']);
    items.forEach((i) => expect(i.label.length).toBeGreaterThan(0));
    expect(items[3].label).toContain('ND');
    expect(items[3].color).toBe('#64748b');
  });
});
