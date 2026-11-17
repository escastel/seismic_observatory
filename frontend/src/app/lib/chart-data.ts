// Pure reshaping of the Statistics delivered by the API for the charts.
// Nothing is recomputed from events: only rows already delivered are sliced,
// relabelled or summed for drawing. Totals are never changed.

import { NO_COUNTRY_LABEL, ND } from './format';
import type { Statistics } from './api-types';

export const MAX_HOURLY_BARS = 168;

export interface HourBar {
  start: number;
  label: string;
  count: number;
}

export interface HourlyBars {
  bars: HourBar[];
  hiddenWindows: number;
  total: number;
}

export interface CountryBar {
  countryId: string | null;
  label: string;
  count: number;
  isUnassigned: boolean;
}

export interface CountryBars {
  bars: CountryBar[];
  others: { count: number; countries: number } | null;
  allRows: CountryBar[];
}

export interface DistributionBar {
  label: string;
  count: number;
}

export interface DistributionBars {
  bars: DistributionBar[];
  unvalued: number;
  total: number;
}

export interface ComparisonSummary {
  recentCount: number;
  dailyMean: number;
  baselineYear: number;
  baselineDays: number;
  ratioText: string;
  warning: string;
}

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

function hourLabel(startMs: number): string {
  const d = new Date(startMs);
  if (Number.isNaN(d.getTime())) return ND;
  return `${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())} ${pad2(d.getUTCHours())}:00`;
}

function sum(values: number[]): number {
  return values.reduce((acc, v) => acc + v, 0);
}

export function hourlyBars(stats: Statistics): HourlyBars {
  const items = stats.hourly?.items ?? [];
  const hidden = Math.max(0, items.length - MAX_HOURLY_BARS);
  const shown = hidden > 0 ? items.slice(items.length - MAX_HOURLY_BARS) : items;
  return {
    bars: shown.map((i) => ({ start: i.start, label: hourLabel(i.start), count: i.count })),
    hiddenWindows: hidden,
    total: stats.total,
  };
}

export function countryBars(stats: Statistics, maxNamed = 15): CountryBars {
  const rows: CountryBar[] = (stats.byCountry?.items ?? []).map((i) => {
    const unassigned = i.countryId === null;
    return {
      countryId: i.countryId,
      label: unassigned ? NO_COUNTRY_LABEL : i.countryName,
      count: i.count,
      isUnassigned: unassigned,
    };
  });
  const sorted = [...rows].sort((a, b) => b.count - a.count);
  const limit = Math.max(0, maxNamed);
  const top = sorted.slice(0, limit);
  const rest = sorted.slice(limit);
  const unassignedInRest = rest.find((r) => r.isUnassigned);
  if (unassignedInRest) {
    top.push(unassignedInRest);
    rest.splice(rest.indexOf(unassignedInRest), 1);
  }
  top.sort((a, b) => b.count - a.count);
  return {
    bars: top,
    others: rest.length > 0 ? { count: sum(rest.map((r) => r.count)), countries: rest.length } : null,
    allRows: rows,
  };
}

function bound(n: number): string {
  return String(n).replace('.', ',');
}

export function magnitudeDistributionBars(stats: Statistics): DistributionBars {
  const d = stats.magnitudeDistribution;
  return {
    bars: (d?.items ?? []).map((i) => ({ label: `${bound(i.from)}–${bound(i.to)}`, count: i.count })),
    unvalued: d?.unvalued ?? 0,
    total: stats.total,
  };
}

export function depthDistributionBars(stats: Statistics): DistributionBars {
  const d = stats.depthDistribution;
  return {
    bars: (d?.items ?? []).map((i) => ({ label: i.label, count: i.count })),
    unvalued: d?.unvalued ?? 0,
    total: stats.total,
  };
}

export function barWidthPercent(count: number, max: number): number {
  if (!Number.isFinite(count) || !Number.isFinite(max) || max <= 0 || count <= 0) return 0;
  return Math.min(100, (count / max) * 100);
}

export function comparisonSummary(stats: Statistics): ComparisonSummary {
  const c = stats.comparison;
  const ratioText =
    c.ratio === 'ND' || typeof c.ratio !== 'number' || !Number.isFinite(c.ratio)
      ? ND
      : c.ratio.toFixed(2).replace('.', ',');
  return {
    recentCount: c.recent.count,
    dailyMean: c.baseline.dailyMean,
    baselineYear: c.baseline.year,
    baselineDays: c.baseline.days,
    ratioText,
    warning: c.warning,
  };
}
