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

/** Short value for the bar; the full text stays in `detail` and in the «Detalles» panel. */
function compactCard(card: SummaryCard, statistics: Statistics | null): SummaryCard {
  const period = statistics?.period;
  if (card.id === 'lastIngestion') {
    const match = /\d{2}:\d{2}:\d{2}/.exec(card.value);
    return match ? { ...card, value: match[0], detail: `${card.value.slice(0, 10)} · ${card.detail}` } : card;
  }
  if (card.id === 'period' && period) {
    const short = (ms: number) => formatUtc(ms).slice(5, 16);
    const value = period.defaultApplied
      ? statistics?.mode === 'replay' ? 'Todo el periodo' : 'Últimas 24 h'
      : `${short(period.start)} → ${short(period.end)}`;
    return { ...card, value, detail: `${card.value}. ${card.detail}` };
  }
  if (card.id === 'unvalued') {
    const [mag, depth] = card.value.split(' magnitud · ');
    return depth !== undefined
      ? { ...card, value: `${mag} · ${depth.replace(' profundidad', '')}`, detail: `magnitud · profundidad. ${card.detail}` }
      : card;
  }
  return card;
}

export function buildStatusBar(
  statistics: Statistics | null,
  status: PanelStatus | null,
  reading: Reading | null
): StatusBar {
  const replay = statistics?.mode === 'replay' || reading?.filters.mode === 'replay';

  const metrics: StatusMetric[] = buildSummaryCards(statistics, status).map((card) => ({
    ...compactCard(card, statistics),
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
