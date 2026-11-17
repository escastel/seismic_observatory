// Pure description of the four dashboard charts: title, unit, period, filters,
// unvalued text, theme colors and complete table rows. No Angular or Chart.js.

import type { Statistics } from './api-types';
import {
  countryBars,
  depthDistributionBars,
  hourlyBars,
  magnitudeDistributionBars,
  MAX_HOURLY_BARS,
} from './chart-data';
import { depthCategory } from './geo';
import { depthColor } from './map-layers';
import { formatMagnitude, formatUtc, ND } from './format';

export type ChartTheme = 'dark' | 'light';
export type ChartId = 'hourly' | 'country' | 'magnitude' | 'depth';

export const REPLAY_LABEL = 'REPRODUCCIÓN';
export const OTHERS_LABEL = 'Otros países';
export const UNVALUED_ROW_LABEL = 'Sin valor (ND)';

export interface SeriesPoint {
  label: string;
  count: number;
}

export interface ChartSeries {
  id: ChartId;
  title: string;
  unit: string;
  periodText: string;
  filtersText: string;
  unvaluedText: string;
  points: SeriesPoint[];
  /** One color per point. */
  colors: string[];
  table: SeriesPoint[];
  /** "REPRODUCCIÓN" in replay mode, null otherwise. */
  label: string | null;
  /** Hourly only: notice about windows not drawn. */
  notice: string | null;
}

const THEME_COLORS: Record<ChartTheme, { primary: string; muted: string }> = {
  dark: { primary: '#5eb0ef', muted: '#94a3b8' },
  light: { primary: '#1d6fb8', muted: '#64748b' },
};

function periodText(stats: Statistics): string {
  return `${formatUtc(stats.period.start)} a ${formatUtc(stats.period.end)}`;
}

function filtersText(stats: Statistics): string {
  const f = stats.filters;
  const parts: string[] = [];
  if (f.minMag !== null && f.minMag !== undefined) {
    parts.push(`magnitud mínima ${formatMagnitude(f.minMag)}`);
  }
  if (f.countryId) parts.push(`país ${f.countryId}`);
  if (f.excludeSynthetic) parts.push('sin eventos sintéticos');
  return parts.length > 0 ? parts.join(', ') : 'Sin filtros';
}

function unvaluedCount(count: number, what: string): string {
  return count === 0 ? `Sin registros sin ${what}` : `${count} registros sin ${what} (${ND})`;
}

function allHourRows(stats: Statistics): SeriesPoint[] {
  return (stats.hourly?.items ?? []).map((i) => {
    const one = hourlyBars({ ...stats, hourly: { ...stats.hourly, items: [i] } });
    return { label: one.bars[0].label, count: i.count };
  });
}

export function buildChartSeries(id: ChartId, stats: Statistics, theme: ChartTheme): ChartSeries {
  const palette = THEME_COLORS[theme];
  const base = {
    id,
    unit: 'eventos',
    periodText: periodText(stats),
    filtersText: filtersText(stats),
    label: stats.mode === 'replay' ? REPLAY_LABEL : null,
    notice: null as string | null,
  };

  if (id === 'hourly') {
    const h = hourlyBars(stats);
    return {
      ...base,
      title: 'Eventos por hora UTC',
      unvaluedText: 'Sin registros sin valor: cada evento tiene hora',
      points: h.bars.map((b) => ({ label: b.label, count: b.count })),
      colors: h.bars.map(() => palette.primary),
      table: allHourRows(stats),
      notice:
        h.hiddenWindows > 0
          ? `Se dibujan las últimas ${MAX_HOURLY_BARS} horas; ${h.hiddenWindows} horas anteriores solo aparecen en la tabla`
          : null,
    };
  }

  if (id === 'country') {
    const c = countryBars(stats);
    const points: SeriesPoint[] = c.bars.map((b) => ({ label: b.label, count: b.count }));
    const colors = c.bars.map((b) => (b.isUnassigned ? palette.muted : palette.primary));
    if (c.others) {
      points.push({ label: `${OTHERS_LABEL} (${c.others.countries})`, count: c.others.count });
      colors.push(palette.muted);
    }
    return {
      ...base,
      title: 'Eventos por país',
      unvaluedText: 'Los eventos sin país figuran como «Sin país asignado»',
      points,
      colors,
      table: c.allRows.map((r) => ({ label: r.label, count: r.count })),
    };
  }

  if (id === 'magnitude') {
    const m = magnitudeDistributionBars(stats);
    return {
      ...base,
      title: 'Distribución de magnitud',
      unit: `eventos por intervalo de magnitud (${stats.magnitudeDistribution?.unit ?? 'Mw'})`,
      unvaluedText: unvaluedCount(m.unvalued, 'magnitud'),
      points: m.bars,
      colors: m.bars.map(() => palette.primary),
      table: [...m.bars, { label: UNVALUED_ROW_LABEL, count: m.unvalued }],
    };
  }

  const d = depthDistributionBars(stats);
  const items = stats.depthDistribution?.items ?? [];
  return {
    ...base,
    title: 'Distribución de profundidad',
    unit: 'eventos por intervalo de profundidad (km)',
    unvaluedText: unvaluedCount(d.unvalued, 'profundidad'),
    points: d.bars,
    colors: items.map((i) => {
      const ref = i.from ?? (i.to !== null && i.to !== undefined ? i.to - 1 : null);
      return depthColor(depthCategory(ref).key, theme);
    }),
    table: [...d.bars, { label: UNVALUED_ROW_LABEL, count: d.unvalued }],
  };
}

export function buildAllChartSeries(stats: Statistics, theme: ChartTheme): ChartSeries[] {
  return (['hourly', 'country', 'magnitude', 'depth'] as ChartId[]).map((id) =>
    buildChartSeries(id, stats, theme),
  );
}
