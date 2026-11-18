// Status bar of the panel (010 data-model: StatusBar). Pure logic, no Angular.
// Reuses the 009 summary cards; figures come only from the API, never from the map sample.

import type { PanelStatus, Reading, Statistics } from './api-types';
import { ND, formatUtc } from './format';
import { buildSummaryCards, type SummaryCard, type SummaryCardId } from './summary';

export const REPLAY_LABEL = 'REPRODUCCIÓN';

const NARROW_IDS: SummaryCardId[] = ['total', 'lastIngestion', 'status'];

export interface StatusMetric extends SummaryCard {
  visibleOnNarrow: boolean;
}

export type StatusDetailId =
  | 'lastRead'
  | 'generated'
  | 'lastIngestion'
  | 'lastReplay'
  | 'quarantine'
  | 'unvalued';

export interface StatusDetail {
  id: StatusDetailId;
  label: string;
  value: string;
}

export interface StatusBar {
  metrics: StatusMetric[];
  details: StatusDetail[];
}

function count(n: number | null | undefined): string {
  return typeof n === 'number' && Number.isFinite(n) ? String(n) : ND;
}

export function buildStatusBar(
  statistics: Statistics | null,
  status: PanelStatus | null,
  reading: Reading | null
): StatusBar {
  const replay = statistics?.mode === 'replay' || reading?.filters.mode === 'replay';

  const metrics: StatusMetric[] = buildSummaryCards(statistics, status).map((card) => ({
    ...card,
    badge: replay ? (card.badge ?? REPLAY_LABEL) : card.badge,
    visibleOnNarrow: NARROW_IDS.includes(card.id)
  }));

  const meta = reading?.metadata ?? null;
  const details: StatusDetail[] = [
    { id: 'lastRead', label: 'Última lectura correcta del panel', value: formatUtc(reading?.readAt) },
    { id: 'generated', label: 'Generación de la respuesta (API)', value: formatUtc(meta?.generated ?? statistics?.generated) },
    { id: 'lastIngestion', label: 'Última ingesta', value: formatUtc(meta?.lastIngestion ?? statistics?.lastIngestion) }
  ];

  if (replay) {
    details.push({
      id: 'lastReplay',
      label: 'Última reproducción',
      value: formatUtc(meta?.lastReplayedAt ?? statistics?.lastReplayedAt)
    });
  }

  details.push({
    id: 'quarantine',
    label: 'Eventos en cuarentena',
    value: meta ? `${count(meta.quarantined.total)} (geometría no válida: ${count(meta.quarantined.invalidGeometry)})` : ND
  });
  details.push({
    id: 'unvalued',
    label: 'Eventos sin magnitud',
    value: meta
      ? `${count(meta.nullMagnitude.count)} (${meta.nullMagnitude.excluded ? 'excluidos' : 'incluidos'})`
      : ND
  });

  return { metrics, details };
}
