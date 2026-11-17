import { describe, expect, it } from 'vitest';
import { reducedMotion, resolveTheme } from './theme';

describe('resolveTheme', () => {
  it('uses light only when the device asks for it', () => {
    expect(resolveTheme(true)).toBe('light');
  });

  it('defaults to dark without a preference', () => {
    expect(resolveTheme(false)).toBe('dark');
  });

  it('defaults to dark when the preference cannot be read', () => {
    expect(resolveTheme(null)).toBe('dark');
  });
});

describe('reducedMotion', () => {
  it('is true only when reduce is requested', () => {
    expect(reducedMotion(true)).toBe(true);
    expect(reducedMotion(false)).toBe(false);
    expect(reducedMotion(null)).toBe(false);
  });
});
