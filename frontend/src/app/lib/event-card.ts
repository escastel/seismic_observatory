// Pure content of the event detail card. Everything returned is plain text:
// the template must render it with interpolation, never as HTML.

import type { MapEvent, Mode } from './api-types';
import { ND, countryLabel, formatDepth, formatMagnitude, formatUtc } from './format';

export interface EventCardField {
  key: string;
  label: string;
  value: string;
}

export interface EventCard {
  id: string;
  title: string;
  fields: EventCardField[];
}

function textOrNd(value: string | null | undefined): string {
  return typeof value === 'string' && value.trim() !== '' ? value : ND;
}

function magnitudeWithType(event: MapEvent): string {
  const magnitude = formatMagnitude(event.mag);
  const type = typeof event.magType === 'string' ? event.magType.trim() : '';
  return type === '' ? magnitude : `${magnitude} ${type}`;
}

function syntheticLabel(value: boolean | null | undefined): string {
  if (value === true) return 'Sintético';
  if (value === false) return 'No sintético';
  return ND;
}

export function buildEventCard(event: MapEvent, mode: Mode): EventCard {
  const fields: EventCardField[] = [
    { key: 'id', label: 'ID', value: textOrNd(event.id) },
    { key: 'magnitude', label: 'Magnitud', value: magnitudeWithType(event) },
    { key: 'depth', label: 'Profundidad', value: formatDepth(event.depthKm) },
    { key: 'place', label: 'Lugar', value: textOrNd(event.place) },
    { key: 'time', label: 'Hora UTC', value: formatUtc(event.time) },
    { key: 'country', label: 'País', value: countryLabel(event.countryName) },
    { key: 'continent', label: 'Continente', value: textOrNd(event.continent) },
    { key: 'subregion', label: 'Subregión', value: textOrNd(event.subregion) },
  ];
  if (mode === 'replay') {
    fields.push({ key: 'replayedAt', label: 'Hora de reproducción', value: formatUtc(event.replayedAt) });
    fields.push({ key: 'synthetic', label: 'Sintético', value: syntheticLabel(event.synthetic) });
  }
  return { id: event.id, title: `Evento ${textOrNd(event.id)}`, fields };
}
