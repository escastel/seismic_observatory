import type { PanelConfig } from './api-types';

export const MIN_REFRESH_MS = 5000;

const DEFAULTS = { refreshMs: 60000, requestTimeoutMs: 15000, staleAfterMs: 900000, skipNgrokWarning: true };

export type ConfigResult = { ok: true; value: PanelConfig } | { ok: false; error: string };

function positiveInt(value: unknown, fallback: number, name: string): number | string {
  if (value === undefined) return fallback;
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) return `${name} debe ser un número positivo`;
  return Math.round(value);
}

/** Validates the parsed public/config.json. `demo` is no longer a valid mode. */
export function parseConfig(raw: unknown): ConfigResult {
  if (typeof raw !== 'object' || raw === null) return { ok: false, error: 'config.json debe ser un objeto' };
  const r = raw as Record<string, unknown>;
  const mode = r['mode'] ?? 'live';
  if (mode !== 'live' && mode !== 'replay') return { ok: false, error: 'mode debe ser "live" o "replay"' };
  if (typeof r['apiUrl'] !== 'string') return { ok: false, error: 'apiUrl es obligatorio' };
  let url: URL;
  try {
    url = new URL(r['apiUrl']);
  } catch {
    return { ok: false, error: 'apiUrl no es una URL válida' };
  }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') return { ok: false, error: 'apiUrl debe ser http o https' };
  const apiUrl = r['apiUrl'].replace(/\/+$/, '').replace(/\/api$/, '');
  const refresh = positiveInt(r['refreshMs'], DEFAULTS.refreshMs, 'refreshMs');
  const timeout = positiveInt(r['requestTimeoutMs'], DEFAULTS.requestTimeoutMs, 'requestTimeoutMs');
  const stale = positiveInt(r['staleAfterMs'], DEFAULTS.staleAfterMs, 'staleAfterMs');
  for (const v of [refresh, timeout, stale]) if (typeof v === 'string') return { ok: false, error: v };
  const skip = r['skipNgrokWarning'];
  if (skip !== undefined && typeof skip !== 'boolean') return { ok: false, error: 'skipNgrokWarning debe ser booleano' };
  return {
    ok: true,
    value: {
      mode,
      apiUrl,
      refreshMs: Math.max(MIN_REFRESH_MS, refresh as number),
      requestTimeoutMs: timeout as number,
      staleAfterMs: stale as number,
      skipNgrokWarning: skip ?? DEFAULTS.skipNgrokWarning
    }
  };
}
