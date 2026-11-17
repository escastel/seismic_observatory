// Pure catalogue of map base layers and optional overlays (no Leaflet, no Angular).
// Sources and attributions: specs/009-dashboard-visual-redesign/research.md R2, R3, R6.

export type Theme = 'dark' | 'light';

export type BaseLayerId = 'simple' | 'relief' | 'satellite';
export type OverlayLayerId = 'circles' | 'heat' | 'cluster' | 'plates';

export interface BaseLayer {
  readonly id: BaseLayerId;
  readonly label: string;
  readonly attribution: string;
  readonly maxZoom: number;
  /** Tile URL template for the theme. */
  tiles(theme: Theme): string;
  /** CSS filter applied to the tile pane for the theme ('none' when not needed). */
  filter(theme: Theme): string;
}

export interface OverlayLayer {
  readonly id: OverlayLayerId;
  readonly label: string;
  readonly defaultEnabled: boolean;
  /** Attribution text, or null when the overlay needs none. */
  readonly attribution: string | null;
  /** Whether the overlay draws only the API sample and shows the sample label. */
  readonly usesSample: boolean;
}

const OSM_TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const RELIEF_TILES =
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}';
const SATELLITE_TILES =
  'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2021_3857/default/g/{z}/{y}/{x}.jpg';

export const BASE_LAYERS: readonly BaseLayer[] = [
  {
    id: 'simple',
    label: 'Simple',
    attribution: '© OpenStreetMap contributors',
    maxZoom: 19,
    tiles: () => OSM_TILES,
    filter: (theme) =>
      theme === 'dark' ? 'invert(1) hue-rotate(180deg) brightness(0.85) contrast(0.9)' : 'none',
  },
  {
    id: 'relief',
    label: 'Relieve',
    attribution: 'Tiles © Esri — Source: Esri',
    maxZoom: 13,
    tiles: () => RELIEF_TILES,
    filter: (theme) =>
      theme === 'dark'
        ? 'grayscale(1) invert(1) brightness(0.7) sepia(0.3) hue-rotate(180deg) saturate(1.5)'
        : 'none',
  },
  {
    id: 'satellite',
    label: 'Satélite',
    attribution:
      'Sentinel-2 cloudless — https://s2maps.eu by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2021)',
    maxZoom: 13,
    tiles: () => SATELLITE_TILES,
    filter: () => 'none',
  },
];

export const OVERLAY_LAYERS: readonly OverlayLayer[] = [
  { id: 'circles', label: 'Círculos por magnitud', defaultEnabled: true, attribution: null, usesSample: false },
  { id: 'heat', label: 'Mapa de calor', defaultEnabled: false, attribution: null, usesSample: true },
  { id: 'cluster', label: 'Agrupar eventos', defaultEnabled: false, attribution: null, usesSample: true },
  {
    id: 'plates',
    label: 'Límites de placas',
    defaultEnabled: false,
    attribution: 'Límites de placas: PB2002 (P. Bird, 2003); datos de H. Ahlenius, Nordpil',
    usesSample: false,
  },
];

/**
 * Depth colours per theme (same values as the --depth-* tokens in styles.css).
 * Each pair keeps at least 3:1 contrast against the surface of its theme.
 */
const DEPTH_COLORS: Record<Theme, Record<'shallow' | 'intermediate' | 'deep' | 'unknown', string>> = {
  dark: { shallow: '#f2b84b', intermediate: '#f0714d', deep: '#a97be0', unknown: '#8a9bad' },
  light: { shallow: '#b87800', intermediate: '#c2410c', deep: '#6d28b0', unknown: '#5b6b7b' },
};

export function depthColor(key: 'shallow' | 'intermediate' | 'deep' | 'unknown', theme: Theme): string {
  return DEPTH_COLORS[theme][key];
}

export const DEFAULT_BASE_LAYER: BaseLayerId = 'simple';

export function baseLayer(id: BaseLayerId): BaseLayer {
  return BASE_LAYERS.find((layer) => layer.id === id) ?? BASE_LAYERS[0];
}

/** Plates are on by default only with the relief base layer (ui-contract §2). */
export function platesDefault(base: BaseLayerId): boolean {
  return base === 'relief';
}

/** Cluster replaces the individual circles; heat combines with either. */
export function circlesVisible(clusterEnabled: boolean): boolean {
  return !clusterEnabled;
}

/** Sample label for heat and cluster: how many events are drawn out of the real total. */
export function sampleLabel(drawn: number, total: number): string {
  return drawn < total ? `Muestra: ${drawn} de ${total}` : 'Todos los eventos del periodo';
}
