// Chips summarising the applied filters (010, data-model: FilterChip). Plain text, no HTML.
import type { QueryFilters } from './api-types';
import { formatUtc } from './format';

export interface FilterChip {
  id: 'mode' | 'period' | 'minMag' | 'country';
  label: string;
}

export function filterChips(filters: QueryFilters, countryName?: string | null): FilterChip[] {
  const mode = filters.mode === 'replay' ? 'Modo: reproducción' : 'Modo: en vivo';

  let period: string;
  if (filters.start === null && filters.end === null) {
    period = 'Periodo: por defecto';
  } else {
    const from = filters.start === null ? 'inicio' : formatUtc(filters.start);
    const to = filters.end === null ? 'ahora' : formatUtc(filters.end);
    period = `Periodo: ${from} a ${to}`;
  }

  const minMag =
    filters.minMag === null ? 'Sin mínimo de magnitud' : `Magnitud mínima: ${filters.minMag}`;

  let country = 'Todos los países';
  if (filters.countryId !== null) {
    const name = countryName?.trim();
    country = `País: ${name ? name : filters.countryId}`;
  }

  return [
    { id: 'mode', label: mode },
    { id: 'period', label: period },
    { id: 'minMag', label: minMag },
    { id: 'country', label: country },
  ];
}
