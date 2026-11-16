import { describe, expect, it } from 'vitest';
import type { ApiFailure, Health, Reading } from './api-types';
import { derivePanelStatus, formatAge } from './status';

const MIN = 60_000;
const NOW = 1_800_000_000_000;
const STALE = 15 * MIN;

function reading(over: { lastIngestion?: number | null; generated?: number; count?: number; total?: number; mode?: 'live' | 'replay' } = {}): Reading {
  const mode = over.mode ?? 'live';
  return {
    readAt: NOW,
    filters: { mode, start: null, end: null, minMag: null, countryId: null, excludeSynthetic: false },
    events: [],
    statistics: null,
    health: null,
    metadata: {
      generated: over.generated ?? NOW,
      lastIngestion: over.lastIngestion === undefined ? NOW - MIN : over.lastIngestion,
      mode,
      count: over.count ?? 5,
      total: over.total ?? 5,
      truncated: false,
      limit: 1000,
      offset: 0,
      nextOffset: null,
      period: { start: null, end: null, defaultApplied: true },
      nullMagnitude: { count: 0, excluded: false },
      quarantined: { total: 0, invalidGeometry: 0 },
      label: mode === 'replay' ? 'REPRODUCCIÓN' : null,
      lastReplayedAt: null
    }
  };
}

const okHealth: Health = { status: 'ok', database: 'ok', replayDatabase: 'ok', generated: NOW, lastIngestion: NOW - MIN };
const fail = (kind: ApiFailure['kind'], extra: Partial<ApiFailure> = {}): ApiFailure => ({ kind, message: 'x', ...extra });

describe('derivePanelStatus', () => {
  it('is ok with a recent ingestion', () => {
    const s = derivePanelStatus(reading(), null, okHealth, NOW, STALE);
    expect(s.keys).toEqual(['ok']);
    expect(s.showingPreviousReading).toBe(false);
  });

  it('warns when the last ingestion exceeds the threshold', () => {
    const s = derivePanelStatus(reading({ lastIngestion: NOW - 40 * MIN }), null, okHealth, NOW, STALE);
    expect(s.keys).toContain('stale');
    expect(s.keys).not.toContain('ok');
    expect(s.ingestionAgeMs).toBe(40 * MIN);
  });

  it('measures staleness against generated, not the browser clock, when the read succeeded', () => {
    // Browser clock is one day ahead; the API says the ingestion was 1 min before generation.
    const s = derivePanelStatus(reading(), null, okHealth, NOW + 24 * 60 * MIN, STALE);
    expect(s.keys).toEqual(['ok']);
  });

  it('measures staleness against the local clock when the latest attempt failed', () => {
    const s = derivePanelStatus(reading(), fail('unreachable'), null, NOW + 30 * MIN, STALE);
    expect(s.keys).toEqual(['unreachable', 'stale']);
    expect(s.showingPreviousReading).toBe(true);
  });

  it('reports unreachable with no previous reading and says so', () => {
    const s = derivePanelStatus(null, fail('unreachable'), null, NOW, STALE);
    expect(s.keys).toEqual(['unreachable']);
    expect(s.showingPreviousReading).toBe(false);
    expect(s.messages[0]).toMatch(/todavía no hay/);
  });

  it('keeps 422, 503, degraded and empty distinguishable', () => {
    const r = reading();
    const messages = [
      derivePanelStatus(r, fail('invalid_parameters', { param: 'start', message: 'sin zona' }), null, NOW, STALE),
      derivePanelStatus(r, fail('database_unavailable'), null, NOW, STALE),
      derivePanelStatus(r, null, { ...okHealth, status: 'degraded', database: 'unavailable' }, NOW, STALE),
      derivePanelStatus(reading({ count: 0, total: 0 }), null, okHealth, NOW, STALE)
    ];
    expect(messages.map((m) => m.keys[0])).toEqual(['invalid_parameters', 'database_unavailable', 'degraded', 'empty']);
    expect(new Set(messages.map((m) => m.messages[0])).size).toBe(4);
    expect(messages[0].messages[0]).toContain('start');
  });

  it('treats zero events as valid, not as an error', () => {
    const s = derivePanelStatus(reading({ count: 0, total: 0 }), null, okHealth, NOW, STALE);
    expect(s.keys).toEqual(['empty']);
  });

  it('does not flag staleness in replay mode', () => {
    const s = derivePanelStatus(reading({ mode: 'replay', lastIngestion: NOW - 5 * 60 * MIN }), null, okHealth, NOW, STALE);
    expect(s.keys).not.toContain('stale');
  });

  it('flags staleness when no successful USGS query is recorded', () => {
    const s = derivePanelStatus(reading({ lastIngestion: null }), null, null, NOW, STALE);
    expect(s.keys).toContain('stale');
    expect(s.ingestionAgeMs).toBeNull();
  });

  it('orders keys by priority', () => {
    const s = derivePanelStatus(reading({ lastIngestion: NOW - 40 * MIN }), fail('database_unavailable'), { ...okHealth, status: 'degraded' }, NOW, STALE);
    expect(s.keys).toEqual(['database_unavailable', 'degraded', 'stale']);
  });
});

describe('formatAge', () => {
  it('formats seconds, minutes, hours and days', () => {
    expect(formatAge(45_000)).toBe('45 s');
    expect(formatAge(12 * MIN)).toBe('12 min');
    expect(formatAge(185 * MIN)).toBe('3 h 5 min');
    expect(formatAge(52 * 60 * MIN)).toBe('2 d 4 h');
    expect(formatAge(-5)).toBe('0 s');
  });
});
