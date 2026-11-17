import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  computed,
  effect,
  inject,
  input,
  viewChildren
} from '@angular/core';
import type { Chart } from 'chart.js';

import type { ApiFailure, Statistics } from '../lib/api-types';
import { comparisonSummary } from '../lib/chart-data';
import { buildAllChartSeries, type ChartSeries } from '../lib/chart-series';
import { ND, formatNullable, formatUtc } from '../lib/format';
import { ThemeService } from '../theme/theme.service';

const LIMIT_TEXT = 'El periodo supera las 10.000 horas: acota las fechas';

type ChartJs = typeof import('chart.js');

let registered: Promise<ChartJs> | null = null;

/** Lazy, selective Chart.js load: only the bar controller and its scales. */
function loadChartJs(): Promise<ChartJs> {
  registered ??= import('chart.js').then((m) => {
    m.Chart.register(m.BarController, m.BarElement, m.CategoryScale, m.LinearScale, m.Tooltip);
    return m;
  });
  return registered;
}

function cssVar(name: string, fallback: string): string {
  try {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  } catch {
    return fallback;
  }
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
  readonly theme = input<'dark' | 'light'>('dark');

  protected readonly nd = ND;

  private readonly themeService = inject(ThemeService);
  private readonly canvases = viewChildren<ElementRef<HTMLCanvasElement>>('chartCanvas');
  private charts: Chart[] = [];
  private renderToken = 0;

  constructor() {
    effect(() => {
      const series = this.series();
      const canvases = this.canvases().map((c) => c.nativeElement);
      const reduced = this.themeService.reducedMotion();
      this.theme();
      void this.draw(series, canvases, reduced);
    });
    inject(DestroyRef).onDestroy(() => {
      this.renderToken++;
      this.destroyCharts();
    });
  }

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

  protected readonly series = computed<Array<ChartSeries & { aria: string }>>(() => {
    const s = this.statistics();
    if (!s) return [];
    return buildAllChartSeries(s, this.theme()).map((c) => ({
      ...c,
      aria:
        `Gráfico de barras: ${c.title}. Unidad: ${c.unit}. Periodo (UTC): ${c.periodText}. ` +
        `Filtros: ${c.filtersText}. ${c.unvaluedText}. ${c.points.length} barras.`
    }));
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

  private destroyCharts(): void {
    for (const c of this.charts) c.destroy();
    this.charts = [];
  }

  private async draw(
    series: ChartSeries[],
    canvases: HTMLCanvasElement[],
    reduced: boolean
  ): Promise<void> {
    const token = ++this.renderToken;
    this.destroyCharts();
    if (series.length === 0 || canvases.length < series.length) return;

    let lib: ChartJs;
    try {
      lib = await loadChartJs();
    } catch {
      return;
    }
    if (token !== this.renderToken) return;

    const text = cssVar('--text', '#e8eef4');
    const muted = cssVar('--text-muted', '#a9b9c8');
    const grid = cssVar('--border', '#2d4256');

    const created: Chart[] = [];
    series.forEach((s, i) => {
      const horizontal = s.id === 'country';
      const countAxis = {
        beginAtZero: true,
        ticks: { color: muted, precision: 0 },
        grid: { color: grid },
        title: { display: true, text: 'Eventos', color: text }
      };
      const labelAxis = {
        ticks: { color: muted, autoSkip: true, maxRotation: horizontal ? 0 : 60 },
        grid: { display: false }
      };
      created.push(
        new lib.Chart(canvases[i], {
          type: 'bar',
          data: {
            labels: s.points.map((p) => p.label),
            datasets: [
              {
                label: 'Eventos',
                data: s.points.map((p) => p.count),
                backgroundColor: s.colors,
                borderColor: s.colors,
                borderWidth: 1
              }
            ]
          },
          options: {
            indexAxis: horizontal ? 'y' : 'x',
            responsive: true,
            maintainAspectRatio: false,
            animation: reduced ? false : { duration: 300 },
            plugins: { legend: { display: false }, tooltip: { enabled: true } },
            scales: horizontal ? { x: countAxis, y: labelAxis } : { x: labelAxis, y: countAxis }
          }
        })
      );
    });
    this.charts = created;
  }
}
