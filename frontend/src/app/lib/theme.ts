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
