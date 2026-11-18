export type Theme = 'dark' | 'light';

/**
 * Dark is the default: it is used when the device expresses no preference (`false`)
 * or when the preference cannot be read (`null`).
 */
export function resolveTheme(prefersLight: boolean | null): Theme {
  return prefersLight === true ? 'light' : 'dark';
}

/** `true` only when the device explicitly asks for reduced motion. */
export function reducedMotion(prefersReduce: boolean | null): boolean {
  return prefersReduce === true;
}

export type ThemePreference = 'auto' | 'dark' | 'light';

/** A stored value that is not a valid preference (or missing) means `'auto'`. */
export function resolvePreference(stored: string | null, _deviceLight: boolean | null): ThemePreference {
  return stored === 'dark' || stored === 'light' ? stored : 'auto';
}

/** A manual preference wins; in `auto` the device decides (dark when it expresses nothing). */
export function effectiveTheme(preference: ThemePreference, deviceLight: boolean | null): Theme {
  return preference === 'auto' ? resolveTheme(deviceLight) : preference;
}
