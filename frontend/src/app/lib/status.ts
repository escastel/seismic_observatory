import type { ApiFailure, Health, PanelStatus, Reading, StatusKey } from './api-types';

const PRIORITY: StatusKey[] = [
  'unreachable',
  'database_unavailable',
  'server_error',
  'invalid_response',
  'invalid_parameters',
  'degraded',
  'stale',
  'empty',
  'ok'
];

/** Human readable age, e.g. "45 s", "12 min", "3 h 5 min", "2 d 4 h". */
export function formatAge(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  if (total < 60) return `${total} s`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ${minutes % 60} min`;
  return `${Math.floor(hours / 24)} d ${hours % 24} h`;
}

function failureKey(failure: ApiFailure): StatusKey {
  return failure.kind;
}

function failureMessage(failure: ApiFailure, hasReading: boolean): string {
  switch (failure.kind) {
    case 'unreachable':
      return hasReading
        ? 'No se puede contactar con el backend. Se muestra la última lectura correcta. Se reintentará en el siguiente refresco.'
        : 'No se puede contactar con el backend y todavía no hay ninguna lectura correcta. Se reintentará en el siguiente refresco.';
    case 'database_unavailable':
      return 'La base de datos no está disponible (503). Esto no significa que no haya eventos.';
    case 'server_error':
      return 'La API ha devuelto un error interno (500).';
    case 'invalid_response':
      return `La respuesta de la API no es válida: ${failure.message}`;
    case 'invalid_parameters':
      return failure.param
        ? `Filtro no válido (${failure.param}): ${failure.message}`
        : `Filtro no válido: ${failure.message}`;
  }
}

/**
 * Derives the panel status from the latest reading, the latest failure and the health.
 * Staleness is measured against `generated` of the response when the latest attempt succeeded
 * (so a skewed browser clock does not matter) and against the local clock otherwise.
 * It applies only to live mode: in replay mode `last_ingestion` describes real data not shown.
 */
export function derivePanelStatus(
  reading: Reading | null,
  failure: ApiFailure | null,
  health: Health | null,
  now: number,
  staleAfterMs: number
): PanelStatus {
  const keys = new Set<StatusKey>();
  const messages = new Map<StatusKey, string>();
  const add = (key: StatusKey, message: string) => {
    keys.add(key);
    messages.set(key, message);
  };

  if (failure) add(failureKey(failure), failureMessage(failure, reading !== null));

  const effectiveHealth = health ?? reading?.health ?? null;
  if (effectiveHealth?.status === 'degraded') {
    add('degraded', 'Sistema degradado: alguna base de datos no está disponible.');
  }

  const lastIngestion = reading?.metadata.lastIngestion ?? effectiveHealth?.lastIngestion ?? null;
  let ingestionAgeMs: number | null = null;
  if (lastIngestion !== null) {
    const reference = !failure && reading ? reading.metadata.generated : now;
    ingestionAgeMs = Math.max(0, reference - lastIngestion);
  }
  const isLive = (reading?.filters.mode ?? 'live') === 'live';
  if (isLive && reading) {
    if (lastIngestion === null) {
      add('stale', 'Datos desactualizados: no consta ninguna consulta correcta a USGS.');
    } else if (ingestionAgeMs !== null && ingestionAgeMs > staleAfterMs) {
      add('stale', `Datos desactualizados: la última consulta correcta a USGS fue hace ${formatAge(ingestionAgeMs)}.`);
    }
  }

  if (!failure && reading && reading.metadata.count === 0 && reading.metadata.total === 0) {
    add('empty', 'Sin eventos para este periodo y estos filtros (la consulta ha funcionado).');
  }

  if (keys.size === 0 && reading) add('ok', 'Datos al día.');

  const ordered = PRIORITY.filter((k) => keys.has(k));
  return {
    keys: ordered,
    messages: ordered.map((k) => messages.get(k) as string),
    ingestionAgeMs,
    showingPreviousReading: failure !== null && reading !== null
  };
}
