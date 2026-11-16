import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import type { ApiFailure, Statistics } from '../lib/api-types';
import {
  MAX_HOURLY_BARS,
  barWidthPercent,
  comparisonSummary,
  countryBars,
  depthDistributionBars,
  hourlyBars,
  magnitudeDistributionBars
} from '../lib/chart-data';
import { ND, formatNullable, formatUtc } from '../lib/format';

interface Row {
  label: string;
  count: number;
  width: number;
}

const LIMIT_TEXT = 'El periodo supera las 10.000 horas: acota las fechas';

function withWidths(items: Array<{ label: string; count: number }>, max: number): Row[] {
  return items.map((i) => ({ label: i.label, count: i.count, width: barWidthPercent(i.count, max) }));
}

function maxOf(items: Array<{ count: number }>): number {
  return items.reduce((m, i) => Math.max(m, i.count), 0);
}

@Component({
  selector: 'app-charts',
  standalone: true,
  templateUrl: './charts.component.html',
  styleUrl: './charts.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ChartsComponent {
  readonly statistics = input<Statistics | null>(null);
  readonly statsFailure = input<ApiFailure | null>(null);
  readonly label = input<string | null>(null);

  protected readonly maxHourlyBars = MAX_HOURLY_BARS;
  protected readonly nd = ND;

  protected readonly failureText = computed<string | null>(() => {
    const f = this.statsFailure();
    if (!f) return null;
    if (f.kind === 'invalid_parameters') {
      return /hora|ventana|10\.?000|hours|windows/i.test(f.message) ? LIMIT_TEXT : f.message;
    }
    return f.message;
  });

  protected readonly meta = computed(() => {
    const s = this.statistics();
    if (!s) return null;
    const f = s.filters;
    return {
      period: `${formatUtc(s.period.start)} a ${formatUtc(s.period.end)}`,
      minMag: f.minMag === null ? 'sin filtro' : formatNullable(f.minMag, 1),
      country: f.countryId === null ? 'sin filtro' : f.countryId,
      synthetic: f.excludeSynthetic ? 'sí' : 'no',
      unit: s.unit,
      total: s.total,
      scope: s.scope
    };
  });

  protected readonly hourly = computed(() => {
    const s = this.statistics();
    if (!s) return null;
    const h = hourlyBars(s);
    const all = s.hourly?.items ?? [];
    const max = maxOf(h.bars);
    return {
      rows: withWidths(h.bars, max),
      hidden: h.hiddenWindows,
      window: s.hourly?.window ?? ND,
      table: all.map((i) => ({ start: formatUtc(i.start), count: i.count })),
      aria: `Gráfico de barras de eventos por hora UTC: ${h.bars.length} ventanas dibujadas, total ${h.total} eventos.`
    };
  });

  protected readonly countries = computed(() => {
    const s = this.statistics();
    if (!s) return null;
    const c = countryBars(s);
    const max = maxOf(c.bars);
    return {
      rows: withWidths(c.bars, max),
      others: c.others,
      table: c.allRows,
      aria: `Gráfico de barras de eventos por país: ${c.allRows.length} filas, incluida «Sin país asignado» si hay eventos sin país.`
    };
  });

  protected readonly magnitude = computed(() => {
    const s = this.statistics();
    if (!s) return null;
    const m = magnitudeDistributionBars(s);
    return {
      rows: withWidths(m.bars, maxOf(m.bars)),
      unvalued: m.unvalued,
      unit: s.magnitudeDistribution?.unit ?? ND,
      aria: `Gráfico de barras de la distribución de magnitud en ${m.bars.length} intervalos; ${m.unvalued} registros sin valor (ND).`
    };
  });

  protected readonly depth = computed(() => {
    const s = this.statistics();
    if (!s) return null;
    const d = depthDistributionBars(s);
    return {
      rows: withWidths(d.bars, maxOf(d.bars)),
      unvalued: d.unvalued,
      unit: s.depthDistribution?.unit ?? ND,
      aria: `Gráfico de barras de la distribución de profundidad en ${d.bars.length} intervalos; ${d.unvalued} registros sin valor (ND).`
    };
  });

  protected readonly comparison = computed(() => {
    const s = this.statistics();
    if (!s) return null;
    const c = comparisonSummary(s);
    return {
      ...c,
      recentPeriod: `${formatUtc(s.comparison.recent.start)} a ${formatUtc(s.comparison.recent.end)}`,
      dailyMeanText: formatNullable(c.dailyMean, 2),
      filtersApplied: s.comparison.filtersApplied ?? []
    };
  });
}
