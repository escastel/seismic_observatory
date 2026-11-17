// Types of the 006 query API contract (adapted) and of the panel state.
// Instants are Unix milliseconds UTC; `null` means "no value" and is shown as ND.

export type Mode = 'live' | 'replay';

export interface PanelConfig {
  mode: Mode;
  apiUrl: string;
  refreshMs: number;
  requestTimeoutMs: number;
  staleAfterMs: number;
  skipNgrokWarning: boolean;
}

export interface QueryFilters {
  mode: Mode;
  start: number | null;
  end: number | null;
  minMag: number | null;
  countryId: string | null;
  excludeSynthetic: boolean;
}

export interface Period {
  start: number | null;
  end: number | null;
  defaultApplied: boolean;
}

export interface EventsMetadata {
  generated: number;
  lastIngestion: number | null;
  mode: Mode;
  count: number;
  total: number;
  truncated: boolean;
  limit: number;
  offset: number;
  nextOffset: number | null;
  period: Period;
  nullMagnitude: { count: number; excluded: boolean };
  quarantined: { total: number; invalidGeometry: number };
  label: string | null;
  lastReplayedAt: number | null;
}

export interface MapEvent {
  id: string;
  lon: number | null;
  lat: number | null;
  depthKm: number | null;
  mag: number | null;
  magType: string | null;
  place: string | null;
  time: number | null;
  updated: number | null;
  countryId: string | null;
  countryName: string | null;
  continent: string | null;
  subregion: string | null;
  replayedAt: number | null;
  synthetic: boolean | null;
}

export interface EventsPage {
  metadata: EventsMetadata;
  events: MapEvent[];
}

export interface Statistics {
  mode: Mode;
  generated: number;
  lastIngestion: number | null;
  label: string | null;
  lastReplayedAt: number | null;
  scope: string;
  mapTruncated: boolean;
  period: { start: number; end: number; defaultApplied: boolean };
  filters: { minMag: number | null; countryId: string | null; excludeSynthetic: boolean };
  unit: string;
  total: number;
  hourly: { window: string; items: Array<{ start: number; count: number }> };
  byCountry: { items: Array<{ countryId: string | null; countryName: string; count: number }> };
  magnitudeDistribution: { unit: string; items: Array<{ from: number; to: number; count: number }>; unvalued: number };
  depthDistribution: { unit: string; items: Array<{ label: string; from: number | null; to: number | null; count: number }>; unvalued: number };
  comparison: {
    recent: { start: number; end: number; count: number };
    baseline: { year: number; events: number; days: number; dailyMean: number };
    ratio: number | 'ND';
    filtersApplied: string[];
    warning: string;
  };
}

export interface Health {
  status: 'ok' | 'degraded';
  database: string;
  replayDatabase: string;
  generated: number;
  lastIngestion: number | null;
}

export type FailureKind =
  | 'invalid_parameters'
  | 'database_unavailable'
  | 'server_error'
  | 'unreachable'
  | 'invalid_response';

export interface ApiFailure {
  kind: FailureKind;
  message: string;
  /** Parameter reported by a 422, when known. */
  param?: string;
}

export interface Reading {
  readAt: number;
  filters: QueryFilters;
  events: MapEvent[];
  metadata: EventsMetadata;
  statistics: Statistics | null;
  health: Health | null;
}

export type StatusKey =
  | 'ok'
  | 'stale'
  | 'degraded'
  | 'unreachable'
  | 'database_unavailable'
  | 'invalid_parameters'
  | 'server_error'
  | 'invalid_response'
  | 'empty';

export interface PanelStatus {
  keys: StatusKey[];
  /** Spanish messages, most important first. */
  messages: string[];
  /** Age of last_ingestion in ms, or null if unknown. */
  ingestionAgeMs: number | null;
  /** True when the reading shown is not the latest attempt. */
  showingPreviousReading: boolean;
}
