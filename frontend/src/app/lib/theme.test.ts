import { describe, expect, it } from 'vitest';
import { effectiveTheme, reducedMotion, resolvePreference, resolveTheme } from './theme';

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

describe('resolvePreference', () => {
  it('accepts valid stored values', () => {
    expect(resolvePreference('dark', true)).toBe('dark');
    expect(resolvePreference('light', false)).toBe('light');
    expect(resolvePreference('auto', null)).toBe('auto');
  });

  it('falls back to auto for null or invalid values', () => {
    expect(resolvePreference(null, true)).toBe('auto');
    expect(resolvePreference('purple', false)).toBe('auto');
    expect(resolvePreference('', null)).toBe('auto');
  });
});

describe('effectiveTheme', () => {
  it('lets a manual preference win over the device', () => {
    expect(effectiveTheme('dark', true)).toBe('dark');
    expect(effectiveTheme('light', false)).toBe('light');
  });

  it('follows the device in auto, dark when it expresses nothing', () => {
    expect(effectiveTheme('auto', true)).toBe('light');
    expect(effectiveTheme('auto', false)).toBe('dark');
    expect(effectiveTheme('auto', null)).toBe('dark');
  });
});
