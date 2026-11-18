import { describe, expect, it } from 'vitest';
import type { PanelStatus, QueryFilters, Reading } from './api-types';
import { buildAlerts, noEventsText, type AlertsInput } from './alerts';

const T0 = Date.UTC(2026, 10, 1, 0, 0, 0);

const liveFilters: QueryFilters = {
  mode: 'live',
  start: null,
  end: null,
  minMag: null,
  countryId: null,
  excludeSynthetic: false
};

function reading(over: { filters?: Partial<QueryFilters>; events?: number; total?: number } = {}): Reading {
  const total = over.total ?? 3;
  const events = over.events ?? total;
  return {
    readAt: T0,
    filters: { ...liveFilters, ...over.filters },
    events: Array.from({ length: events }, (_, i) => ({ id: String(i) }) as Reading['events'][number]),
    metadata: {
      generated: T0,
      lastIngestion: T0,
      mode: 'live',
      count: events,
      total,
      truncated: false,
      limit: 100,
      offset: 0,
      nextOffset: null,
      period: { start: null, end: null, defaultApplied: true },
      nullMagnitude: { count: 0, excluded: false },
      quarantined: { total: 0, invalidGeometry: 0 },
      label: null,
      lastReplayedAt: null
    },
    statistics: null,
    health: null
  };
}

function status(keys: PanelStatus['keys'], over: Partial<PanelStatus> = {}): PanelStatus {
  return {
    keys,
    messages: keys.map((k) => `msg ${k}`),
    ingestionAgeMs: 1000,
    showingPreviousReading: false,
    ...over
  };
}

function input(over: Partial<AlertsInput> = {}): AlertsInput {
  return {
    status: status(['ok']),
    statsFailure: null,
    reading: reading(),
    countryName: null,
    configError: null,
    countriesUnavailable: false,
    layerNotices: [],
    recovered: false,
    ...over
  };
}

describe('buildAlerts', () => {
  it('returns no alerts when everything is fine', () => {
    expect(buildAlerts(input())).toEqual([]);
  });

  it('uses role alert only for errors and status for the rest', () => {
    const alerts = buildAlerts(
      input({
        status: status(['unreachable', 'stale']),
        recovered: true,
        reading: reading({ filters: { mode: 'replay' } })
      })
    );
    for (const a of alerts) expect(a.role).toBe(a.kind === 'error' ? 'alert' : 'status');
    expect(alerts.some((a) => a.kind === 'error')).toBe(true);
    expect(alerts.some((a) => a.kind === 'info')).toBe(true);
  });

  it('auto dismisses only the success alert, after 8 s', () => {
    const alerts = buildAlerts(input({ status: status(['unreachable', 'stale']), recovered: true }));
    for (const a of alerts) expect(a.autoDismissMs).toBe(a.kind === 'success' ? 8000 : null);
    expect(alerts.find((a) => a.kind === 'success')).toBeDefined();
  });

  it('keeps the status messages from the panel status', () => {
    const alerts = buildAlerts(input({ status: status(['stale']) }));
    expect(alerts).toHaveLength(1);
    expect(alerts[0]).toMatchObject({ id: 'stale', kind: 'warning', text: 'msg stale' });
  });

  it('orders error, warning, info, success', () => {
    const alerts = buildAlerts(
      input({
        status: status(['stale', 'unreachable']),
        recovered: true,
        reading: reading({ filters: { mode: 'replay' } })
      })
    );
    expect(alerts.map((a) => a.kind)).toEqual(['error', 'warning', 'info', 'success']);
  });

  it('orders alerts of the same kind by status priority', () => {
    const alerts = buildAlerts(input({ status: status(['stale', 'degraded']) }));
    expect(alerts.map((a) => a.id)).toEqual(['degraded', 'stale']);
  });

  it('never duplicates an id', () => {
    const alerts = buildAlerts(
      input({
        status: status(['stale', 'stale']),
        layerNotices: [
          { id: 'layer_failed', text: 'a' },
          { id: 'layer_failed', text: 'b' }
        ]
      })
    );
    const ids = alerts.map((a) => a.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('warns when the map shows fewer events than the total', () => {
    const alerts = buildAlerts(input({ reading: reading({ events: 100, total: 250 }) }));
    const truncated = alerts.find((a) => a.id === 'truncated');
    expect(truncated?.kind).toBe('warning');
    expect(truncated?.text).toContain('100');
    expect(truncated?.text).toContain('250');
    expect(buildAlerts(input({ reading: reading({ events: 5, total: 5 }) })).some((a) => a.id === 'truncated')).toBe(false);
  });

  it('reports a statistics failure as a warning', () => {
    const alerts = buildAlerts(input({ statsFailure: { kind: 'invalid_response', message: 'sin periodo' } }));
    const a = alerts.find((x) => x.id === 'stats_failed');
    expect(a?.kind).toBe('warning');
    expect(a?.text).toContain('sin periodo');
  });

  it('reports replay mode as information', () => {
    const alerts = buildAlerts(input({ reading: reading({ filters: { mode: 'replay' } }) }));
    expect(alerts.find((a) => a.id === 'replay')?.kind).toBe('info');
    expect(buildAlerts(input()).some((a) => a.id === 'replay')).toBe(false);
  });

  it('reports a configuration error as an error', () => {
    const alerts = buildAlerts(input({ configError: 'Falta la URL', status: null, reading: null }));
    expect(alerts).toEqual([expect.objectContaining({ id: 'config', kind: 'error', role: 'alert', text: 'Falta la URL' })]);
  });

  it('reports unavailable countries and layer notices as warnings', () => {
    const alerts = buildAlerts(
      input({ countriesUnavailable: true, layerNotices: [{ id: 'layer_failed', text: 'Fondo no disponible' }] })
    );
    expect(alerts.map((a) => [a.id, a.kind])).toEqual([
      ['countries_unavailable', 'warning'],
      ['layer_failed', 'warning']
    ]);
    expect(alerts.find((a) => a.id === 'layer_failed')?.text).toBe('Fondo no disponible');
  });

  it('shows one information alert for a successful empty reading, naming the country', () => {
    const alerts = buildAlerts(
      input({
        status: status(['empty']),
        reading: reading({ total: 0, filters: { countryId: 'ALB' } }),
        countryName: 'Albania'
      })
    );
    expect(alerts).toHaveLength(1);
    expect(alerts[0]).toMatchObject({ id: 'no_events', kind: 'info' });
    expect(alerts[0].text).toContain('Albania');
  });

  it('does not report no events when the reading shown is a previous one', () => {
    const alerts = buildAlerts(
      input({
        status: status(['unreachable'], { showingPreviousReading: true }),
        reading: reading({ total: 0 })
      })
    );
    expect(alerts.some((a) => a.id === 'no_events')).toBe(false);
  });
});

describe('noEventsText', () => {
  it('names the country with the default live period', () => {
    const t = noEventsText({ ...liveFilters, countryId: 'ALB' }, 'Albania');
    expect(t.title).toBe('No hay eventos sísmicos ahora mismo en Albania');
    expect(t.conditions[0]).toContain('Albania');
  });

  it('uses the generic title when the period is not the default', () => {
    const t = noEventsText({ ...liveFilters, countryId: 'ALB', start: T0, end: T0 + 86_400_000 }, 'Albania');
    expect(t.title).toBe('No hay eventos registrados con las condiciones del filtro');
    expect(t.conditions.join(' ')).toContain('2026-11-01 00:00:00 UTC');
    expect(t.conditions.join(' ')).toContain('2026-11-02 00:00:00 UTC');
  });

  it('uses the generic title without a country filter', () => {
    expect(noEventsText(liveFilters, null).title).toBe('No hay eventos registrados con las condiciones del filtro');
  });

  it('lists country, period, minimum magnitude and mode', () => {
    const t = noEventsText({ ...liveFilters, minMag: 7.5, mode: 'replay' }, null);
    expect(t.conditions).toHaveLength(4);
    expect(t.conditions.join(' | ')).toContain('7,5');
    expect(t.conditions.join(' | ')).toContain('Reproducción');
    expect(t.title).toBe('No hay eventos registrados con las condiciones del filtro');
  });

  it('falls back to the country id when the name is unknown', () => {
    expect(noEventsText({ ...liveFilters, countryId: 'ALB' }, null).title).toContain('ALB');
  });

  it('always gives a suggestion', () => {
    expect(noEventsText(liveFilters, null).suggestion.length).toBeGreaterThan(0);
  });
});
