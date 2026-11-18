import { Injectable, OnDestroy, computed, signal } from '@angular/core';
import { effectiveTheme, reducedMotion, resolvePreference, type Theme, type ThemePreference } from '../lib/theme';

export const THEME_STORAGE_KEY = 'seismic-theme';
const THEME_COLOR: Record<Theme, string> = { dark: '#0b1520', light: '#eef3f6' };

function query(q: string): MediaQueryList | null {
  try {
    return typeof matchMedia === 'function' ? matchMedia(q) : null;
  } catch {
    return null;
  }
}

function readStored(): string | null {
  try {
    return localStorage.getItem(THEME_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStored(value: ThemePreference): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, value);
  } catch {
    // Storage may be blocked (private window, site data blocked): the theme still changes.
  }
}

/**
 * Theme preference: manual (remembered in the browser) or, in `auto`, the device's, followed live.
 * Changing it never reloads the page nor loses the current reading.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService implements OnDestroy {
  private readonly lightQuery = query('(prefers-color-scheme: light)');
  private readonly motionQuery = query('(prefers-reduced-motion: reduce)');
  private readonly deviceLight = signal<boolean | null>(this.lightQuery ? this.lightQuery.matches : null);

  readonly preference = signal<ThemePreference>(resolvePreference(readStored(), this.deviceLight()));
  readonly theme = computed<Theme>(() => effectiveTheme(this.preference(), this.deviceLight()));
  readonly reducedMotion = signal<boolean>(reducedMotion(this.motionQuery ? this.motionQuery.matches : null));

  private readonly onLight = (e: MediaQueryListEvent): void => {
    // Only counts while no manual choice is stored (`theme` ignores it otherwise).
    this.deviceLight.set(e.matches);
    this.apply();
  };
  private readonly onMotion = (e: MediaQueryListEvent): void => this.reducedMotion.set(reducedMotion(e.matches));

  constructor() {
    this.lightQuery?.addEventListener('change', this.onLight);
    this.motionQuery?.addEventListener('change', this.onMotion);
    this.apply();
  }

  /** Switches between dark and light and remembers the choice. */
  toggle(): void {
    const next: ThemePreference = this.theme() === 'dark' ? 'light' : 'dark';
    this.preference.set(next);
    writeStored(next);
    this.apply();
  }

  /** `data-theme` only with a manual choice, so without one the page follows the device with no script. */
  private apply(): void {
    if (typeof document === 'undefined') return;
    const root = document.documentElement;
    const preference = this.preference();
    if (preference === 'auto') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', preference);
    const metas = document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]');
    metas.forEach((meta) => {
      if (!meta.dataset['auto']) meta.dataset['auto'] = meta.content;
      meta.content = preference === 'auto' ? meta.dataset['auto'] : THEME_COLOR[this.theme()];
    });
  }

  ngOnDestroy(): void {
    this.lightQuery?.removeEventListener('change', this.onLight);
    this.motionQuery?.removeEventListener('change', this.onMotion);
  }
}
