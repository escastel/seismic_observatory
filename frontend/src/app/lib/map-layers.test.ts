import { describe, expect, it } from 'vitest';
import {
  BASE_LAYERS,
  DEFAULT_BASE_LAYER,
  OVERLAY_LAYERS,
  baseLayer,
  circlesVisible,
  platesDefault,
  sampleLabel,
} from './map-layers';

describe('base layers', () => {
  it('offers simple and satellite, simple by default', () => {
    expect(BASE_LAYERS.map((l) => l.id)).toEqual(['simple', 'satellite']);
    expect(DEFAULT_BASE_LAYER).toBe('simple');
  });

  it('uses the providers from research R2', () => {
    expect(baseLayer('simple').tiles('light')).toContain('tile.openstreetmap.org');
    expect(baseLayer('satellite').tiles('dark')).toContain('s2cloudless-2021_3857');
  });

  it('filters simple only in the dark theme', () => {
    expect(baseLayer('simple').filter('light')).toBe('none');
    expect(baseLayer('simple').filter('dark')).not.toBe('none');
  });

  it('keeps satellite identical in both themes', () => {
    const sat = baseLayer('satellite');
    expect(sat.tiles('dark')).toBe(sat.tiles('light'));
    expect(sat.filter('dark')).toBe(sat.filter('light'));
  });

  it('always carries a non-empty attribution and a max zoom', () => {
    for (const layer of BASE_LAYERS) {
      expect(layer.attribution.length).toBeGreaterThan(0);
      expect(layer.maxZoom).toBeGreaterThan(0);
    }
    expect(baseLayer('simple').attribution).toBe('© OpenStreetMap contributors');
    expect(baseLayer('satellite').attribution).toContain('EOX IT Services GmbH');
  });
});

describe('relief removal', () => {
  it('no longer offers relief nor Esri', () => {
    expect(BASE_LAYERS.some((l) => (l.id as string) === 'relief')).toBe(false);
    expect(BASE_LAYERS.some((l) => l.attribution.includes('Esri'))).toBe(false);
  });
});

describe('overlays', () => {
  it('has circles and plates on by default and the rest optional', () => {
    const defaults = OVERLAY_LAYERS.filter((l) => l.defaultEnabled).map((l) => l.id);
    expect(defaults).toEqual(['circles', 'plates']);
    expect(OVERLAY_LAYERS.map((l) => l.id)).toEqual(['circles', 'heat', 'cluster', 'plates']);
  });

  it('attributes the plates layer to PB2002', () => {
    const plates = OVERLAY_LAYERS.find((l) => l.id === 'plates');
    expect(plates?.attribution).toContain('PB2002');
  });

  it('enables plates by default over both base layers', () => {
    expect(platesDefault('simple')).toBe(true);
    expect(platesDefault('satellite')).toBe(true);
  });

  it('replaces circles with clusters', () => {
    expect(circlesVisible(true)).toBe(false);
    expect(circlesVisible(false)).toBe(true);
  });
});

describe('sampleLabel', () => {
  it('reports a sample when fewer events are drawn than the total', () => {
    expect(sampleLabel(1000, 12345)).toBe('Muestra: 1000 de 12345');
  });

  it('reports all events when drawn equals total', () => {
    expect(sampleLabel(50, 50)).toBe('Todos los eventos del periodo');
    expect(sampleLabel(0, 0)).toBe('Todos los eventos del periodo');
  });
});
