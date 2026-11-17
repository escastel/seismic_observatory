import { describe, expect, it } from 'vitest';
import { parseConfig } from './config';

const base = { mode: 'live', apiUrl: 'https://example.ngrok-free.dev' };

describe('parseConfig', () => {
  it('accepts a minimal config and fills defaults', () => {
    const r = parseConfig(base);
    expect(r.ok && r.value).toMatchObject({ mode: 'live', refreshMs: 60000, requestTimeoutMs: 15000, staleAfterMs: 900000, skipNgrokWarning: true });
  });

  it('removes trailing slash and /api from apiUrl', () => {
    for (const url of ['https://x.dev/', 'https://x.dev/api', 'https://x.dev/api/']) {
      const r = parseConfig({ ...base, apiUrl: url });
      expect(r.ok && r.value.apiUrl).toBe('https://x.dev');
    }
  });

  it('rejects the retired demo mode and unknown modes', () => {
    expect(parseConfig({ ...base, mode: 'demo' }).ok).toBe(false);
    expect(parseConfig({ ...base, mode: 'api' }).ok).toBe(false);
  });

  it('accepts replay as initial mode', () => {
    const r = parseConfig({ ...base, mode: 'replay' });
    expect(r.ok && r.value.mode).toBe('replay');
  });

  it('rejects missing or invalid apiUrl and non-http schemes', () => {
    expect(parseConfig({ mode: 'live' }).ok).toBe(false);
    expect(parseConfig({ ...base, apiUrl: 'not a url' }).ok).toBe(false);
    expect(parseConfig({ ...base, apiUrl: 'file:///etc/passwd' }).ok).toBe(false);
  });

  it('applies a floor to the refresh interval', () => {
    const r = parseConfig({ ...base, refreshMs: 100 });
    expect(r.ok && r.value.refreshMs).toBe(5000);
  });

  it('rejects non numeric intervals and non object input', () => {
    expect(parseConfig({ ...base, staleAfterMs: 'soon' }).ok).toBe(false);
    expect(parseConfig({ ...base, refreshMs: -1 }).ok).toBe(false);
    expect(parseConfig(null).ok).toBe(false);
    expect(parseConfig('x').ok).toBe(false);
  });
});
