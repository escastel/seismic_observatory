import { Injectable, OnDestroy, signal } from '@angular/core';
import { reducedMotion, resolveTheme, type Theme } from '../lib/theme';

function query(q: string): MediaQueryList | null {
  try {
    return typeof matchMedia === 'function' ? matchMedia(q) : null;
  } catch {
    return null;
  }
}

/** Follows the device preferences live (no reload, no loss of the current reading). */
@Injectable({ providedIn: 'root' })
export class ThemeService implements OnDestroy {
  private readonly lightQuery = query('(prefers-color-scheme: light)');
  private readonly motionQuery = query('(prefers-reduced-motion: reduce)');

  readonly theme = signal<Theme>(resolveTheme(this.lightQuery ? this.lightQuery.matches : null));
  readonly reducedMotion = signal<boolean>(reducedMotion(this.motionQuery ? this.motionQuery.matches : null));

  private readonly onLight = (e: MediaQueryListEvent): void => this.theme.set(resolveTheme(e.matches));
  private readonly onMotion = (e: MediaQueryListEvent): void => this.reducedMotion.set(reducedMotion(e.matches));

  constructor() {
    this.lightQuery?.addEventListener('change', this.onLight);
    this.motionQuery?.addEventListener('change', this.onMotion);
  }

  ngOnDestroy(): void {
    this.lightQuery?.removeEventListener('change', this.onLight);
    this.motionQuery?.removeEventListener('change', this.onMotion);
  }
}
