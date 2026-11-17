// Summary cards of the header (009 data-model: SummaryCard). Pure logic, no Angular.
// Figures come only from `Statistics` and the panel status, never from the map sample.

import type { PanelStatus, StatusKey, Statistics } from './api-types';
import { ND, formatUtc } from './format';
import { formatAge } from './status';

export type SummaryCardId = 'total' | 'lastIngestion' | 'status' | 'period' | 'unvalued';
export type SummaryTone = 'ok' | 'warning' | 'error' | 'neutral';

export interface SummaryCard {
  id: SummaryCardId;
  label: string;
  value: string;
  unit: string;
  detail: string;
  /** Status card only: drives icon and colour; the text always carries the meaning. */
  tone: SummaryTone;
  /** "REPRODUCCIÓN" in replay mode, otherwise null. */
  badge: string | null;
}

const STATUS_TEXT: Record<StatusKey, { text: string; tone: SummaryTone }> = {
  ok: { text: 'Al día', tone: 'ok' },
  stale: { text: 'Desactualizado', tone: 'warning' },
  degraded: { text: 'Degradado', tone: 'warning' },
  empty: { text: 'Sin eventos', tone: 'neutral' },
  unreachable: { text: 'Backend inaccesible', tone: 'error' },
  database_unavailable: { text: 'Base de datos no disponible', tone: 'error' },
  server_error: { text: 'Error del servidor', tone: 'error' },
  invalid_response: { text: 'Respuesta no válida', tone: 'error' },
  invalid_parameters: { text: 'Filtro no válido', tone: 'error' }
};

export function filtersText(statistics: Statistics | null): string {
  if (!statistics) return ND;
  const parts: string[] = [];
  const f = statistics.filters;
  if (f.minMag !== null) parts.push(`magnitud mínima ${String(f.minMag).replace('.', ',')}`);
  if (f.countryId !== null) parts.push(`país ${f.countryId}`);
  if (f.excludeSynthetic) parts.push('sin sintéticos');
  return parts.length > 0 ? parts.join(', ') : 'Sin filtros';
}

function count(n: number | null | undefined): string {
  return typeof n === 'number' && Number.isFinite(n) ? String(n) : ND;
}

export function buildSummaryCards(statistics: Statistics | null, status: PanelStatus | null): SummaryCard[] {
  const filters = filtersText(statistics);
  const replay = statistics?.mode === 'replay';
  const badge = replay ? (statistics?.label ?? 'REPRODUCCIÓN') : null;

  const key = status?.keys[0] ?? null;
  const statusInfo = key ? STATUS_TEXT[key] : null;
  const age = status?.ingestionAgeMs;
  const statusDetail =
    status && status.messages.length > 0
      ? status.messages[0]
      : ND;
  const lastIngestionDetail =
    replay
      ? 'Reproducción: la última ingesta real no corresponde a los datos mostrados'
      : typeof age === 'number' ? `Hace ${formatAge(age)}` : ND;

  const period = statistics?.period;
  const periodValue = period ? `${formatUtc(period.start)} – ${formatUtc(period.end)}` : ND;

  const mag = statistics?.magnitudeDistribution.unvalued;
  const depth = statistics?.depthDistribution.unvalued;
  const unvaluedValue = statistics ? `${count(mag)} magnitud · ${count(depth)} profundidad` : ND;

  return [
    {
      id: 'total',
      label: 'Eventos',
      value: statistics ? count(statistics.total) : ND,
      unit: statistics?.unit || 'eventos',
      detail: filters,
      tone: 'neutral',
      badge
    },
    {
      id: 'lastIngestion',
      label: 'Última ingesta',
      value: formatUtc(statistics?.lastIngestion),
      unit: 'UTC',
      detail: statistics ? lastIngestionDetail : ND,
      tone: 'neutral',
      badge
    },
    {
      id: 'status',
      label: 'Estado',
      value: statusInfo ? statusInfo.text : ND,
      unit: '',
      detail: statusDetail,
      tone: statusInfo ? statusInfo.tone : 'neutral',
      badge
    },
    {
      id: 'period',
      label: 'Periodo',
      value: periodValue,
      unit: 'UTC',
      detail: period
        ? `Inicio inclusivo, fin exclusivo${period.defaultApplied ? '; periodo por defecto' : ''}. ${filters}`
        : ND,
      tone: 'neutral',
      badge
    },
    {
      id: 'unvalued',
      label: 'Sin valor',
      value: unvaluedValue,
      unit: 'eventos',
      detail: statistics
        ? `Sin magnitud: ${count(mag)}. Sin profundidad: ${count(depth)}. ${filters}`
        : ND,
      tone: 'neutral',
      badge
    }
  ];
}
