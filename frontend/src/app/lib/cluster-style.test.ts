import { describe, expect, it } from 'vitest';
import { HEAT_GRADIENT, HEAT_OPTIONS, clusterStyle, haloRadius } from './cluster-style';

describe('clusterStyle', () => {
  it.each([
    [2, 34, 1],
    [9, 34, 1],
    [10, 44, 2],
    [49, 44, 2],
    [50, 54, 3],
    [199, 54, 3],
    [200, 64, 4],
    [5000, 64, 4],
  ])('count %i gives size %i and level %i', (count, size, level) => {
    expect(clusterStyle(count)).toEqual({ size, level });
  });
});

describe('heat constants', () => {
  it('has the agreed gradient and options', () => {
    expect(HEAT_GRADIENT).toEqual({
      0.2: '#ffe066',
      0.4: '#ffb347',
      0.6: '#ff7a3d',
      0.8: '#e03b2e',
      1.0: '#8b0f1c',
    });
    expect(HEAT_OPTIONS).toEqual({ radius: 30, blur: 20, minOpacity: 0.45, maxZoom: 6 });
  });
});

describe('haloRadius', () => {
  it('is larger than the marker radius and grows with it', () => {
    expect(haloRadius(6)).toBeGreaterThan(6);
    expect(haloRadius(10)).toBeGreaterThan(haloRadius(6));
  });
});
