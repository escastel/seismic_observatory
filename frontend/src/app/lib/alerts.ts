// Independent alerts of the panel (010 data-model: Alert). Pure logic, no Angular.

import type { ApiFailure, PanelStatus, QueryFilters, Reading, StatusKey } from './api-types';
import { formatUtc } from './format';

export type AlertKind = 'error' | 'warning' | 'info' | 'success';

export interface Alert {
  id: string;
  kind: AlertKind;
  text: string;
  role: 'alert' | 'status';
  autoDismissMs: number | null;
}

export interface LayerNotice {
  id: string;
  text: string;
}

export interface AlertsInput {
  status: PanelStatus | null;
  statsFailure: ApiFailure | null;
  reading: Reading | null;
  /** Name of the filtered country, when known (used in the "no events" text). */
  countryName: string | null;
  configError: string | null;
  countriesUnavailable: boolean;
  layerNotices: LayerNotice[];
  /** True right after the panel recovers from a failure. */
  recovered: boolean;
}

export const SUCCESS_DISMISS_MS = 8000;

const KIND_RANK: Record<AlertKind, number> = { error: 0, warning: 1, info: 2, success: 3 };

const PRIORITY: string[] = [
  'config',
  'unreachable',
  'database_unavailable',
  'server_error',
  'invalid_response',
  'invalid_parameters',
  'degraded',
  'stale',
  'stats_failed',
  'truncated',
  'countries_unavailable',
  'layer_failed',
  'replay',
  'no_events',
  'recovered'
];

const STATUS_KIND: Record<StatusKey, AlertKind | null> = {
  unreachable: 'error',
  database_unavailable: 'error',
  server_error: 'error',
  invalid_response: 'error',
  invalid_parameters: 'error',
  degraded: 'warning',
  stale: 'warning',
  // The "no events" case is built separately (with the filter conditions).
  empty: null,
  ok: null
};

function make(id: string, kind: AlertKind, text: string): Alert {
  return {
    id,
    kind,
    text,
    role: kind === 'error' ? 'alert' : 'status',
    autoDismissMs: kind === 'success' ? SUCCESS_DISMISS_MS : null
  };
}

function statsFailureText(failure: ApiFailure): string {
  return `Las estadísticas no están disponibles: ${failure.message}. Se muestran los eventos de este filtro.`;
}

export function buildAlerts(input: AlertsInput): Alert[] {
  const found = new Map<string, Alert>();
  const add = (alert: Alert) => {
    if (!found.has(alert.id)) found.set(alert.id, alert);
  };

  if (input.configError) add(make('config', 'error', input.configError));

  const status = input.status;
  if (status) {
    status.keys.forEach((key, index) => {
      const kind = STATUS_KIND[key];
      if (kind) add(make(key, kind, status.messages[index] ?? ''));
    });
  }

  const reading = input.reading;
  const replay = reading?.filters.mode === 'replay';

  if (input.statsFailure) add(make('stats_failed', 'warning', statsFailureText(input.statsFailure)));

  if (reading && reading.events.length < reading.metadata.total) {
    add(
      make(
        'truncated',
        'warning',
        `Se muestran ${reading.events.length} de ${reading.metadata.total} eventos en el mapa y la tabla; las cifras y los gráficos cuentan todos.`
      )
    );
  }

  if (input.countriesUnavailable) {
    add(make('countries_unavailable', 'warning', 'La lista de países no está disponible; el filtro por país no se puede usar ahora.'));
  }

  for (const notice of input.layerNotices) add(make(notice.id || 'layer_failed', 'warning', notice.text));

  if (replay) add(make('replay', 'info', 'Modo reproducción: los datos mostrados son una reproducción, no datos en vivo.'));

  if (reading && !status?.showingPreviousReading && reading.metadata.total === 0) {
    add(make('no_events', 'info', noEventsText(reading.filters, input.countryName).title));
  }

  if (input.recovered) add(make('recovered', 'success', 'Conexión recuperada: los datos vuelven a actualizarse.'));

  const rank = (id: string) => {
    const i = PRIORITY.indexOf(id);
    return i === -1 ? PRIORITY.length : i;
  };
  return [...found.values()].sort((a, b) => KIND_RANK[a.kind] - KIND_RANK[b.kind] || rank(a.id) - rank(b.id));
}

export interface NoEventsText {
  title: string;
  conditions: string[];
  suggestion: string;
}

export const NO_EVENTS_TITLE = 'No hay eventos registrados con las condiciones del filtro';

function magnitudeText(value: number): string {
  return String(value).replace('.', ',');
}

export function noEventsText(filters: QueryFilters, countryName: string | null): NoEventsText {
  const defaultPeriod = filters.start === null && filters.end === null;
  const replay = filters.mode === 'replay';
  const country = filters.countryId === null ? null : countryName?.trim() || filters.countryId;

  let period: string;
  if (defaultPeriod) {
    period = replay ? 'todo el periodo disponible' : 'últimas 24 horas';
  } else {
    period = `${filters.start === null ? 'sin inicio' : formatUtc(filters.start)} – ${filters.end === null ? 'ahora' : formatUtc(filters.end)}`;
  }

  const conditions = [
    `País: ${country ?? 'todos'}`,
    `Periodo (UTC): ${period}`,
    `Magnitud mínima: ${filters.minMag === null ? 'sin mínimo' : magnitudeText(filters.minMag)}`,
    `Modo: ${replay ? 'Reproducción' : 'En vivo'}`
  ];

  const title =
    country !== null && defaultPeriod && !replay
      ? `No hay eventos sísmicos ahora mismo en ${country}`
      : NO_EVENTS_TITLE;

  return {
    title,
    conditions,
    suggestion: 'Amplía el periodo o quita algún filtro para ver eventos.'
  };
}
