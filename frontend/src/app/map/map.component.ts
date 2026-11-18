import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  OnDestroy,
  output,
  signal,
} from '@angular/core';
import { LeafletDirective } from '@bluehalo/ngx-leaflet';
import * as L from 'leaflet';
import type { FeatureCollection } from 'geojson';

import type { MapEvent, Mode } from '../lib/api-types';
import { depthCategory, isUnvalued, legendItems, markerRadius, partitionDrawable } from '../lib/geo';
import {
  BASE_LAYERS,
  baseLayer,
  depthColor,
  DEFAULT_BASE_LAYER,
  OVERLAY_LAYERS,
  platesDefault,
  sampleLabel,
  type BaseLayerId,
  type Theme,
} from '../lib/map-layers';
import { ThemeService } from '../theme/theme.service';
import type { NoEventsText } from '../lib/alerts';
import { NoEventsPopupComponent } from './no-events-popup.component';

// Optional layers are loaded on demand so they add nothing to the initial weight.
type HeatFactory = (points: Array<[number, number, number]>, options: object) => L.Layer;

// Leaflet plugins attach to the global `L`, which is a different object from the bundled namespace.
function globalLeaflet(): typeof L {
  return (window as unknown as { L: typeof L }).L;
}

@Component({
  selector: 'app-map',
  standalone: true,
  imports: [LeafletDirective, NoEventsPopupComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './map.component.html',
  styleUrl: './map.component.css',
})
export class MapComponent implements OnDestroy {
  readonly events = input<MapEvent[]>([]);
  readonly borders = input<FeatureCollection | null>(null);
  readonly label = input<string | null>(null);
  readonly mode = input<Mode>('live');
  /** Real total of the period (metadata.total), for the sample label. */
  readonly total = input<number>(0);
  readonly theme = input<Theme | null>(null);
  /** Set when the last correct reading has no events; shown as a floating pop-up. */
  readonly noEvents = input<NoEventsText | null>(null);
  readonly eventSelected = output<MapEvent>();
  protected readonly popupDismissed = signal(false);
  /** The legend starts folded on narrow screens, open on wide ones. */
  protected readonly legendOpen = signal(
    typeof window === 'undefined' || !window.matchMedia ? true : !window.matchMedia('(max-width: 760px)').matches,
  );

  private readonly themeService = inject(ThemeService);
  protected readonly currentTheme = computed<Theme>(() => this.theme() ?? this.themeService.theme());

  readonly options: L.MapOptions = {
    center: L.latLng(18, 0),
    zoom: 2,
    minZoom: 2,
    maxZoom: 8,
    preferCanvas: true,
    worldCopyJump: false,
  };

  protected readonly legend = computed(() =>
    legendItems().map((item) => ({ ...item, color: depthColor(item.key, this.currentTheme()) })),
  );
  protected readonly baseLayers = BASE_LAYERS;
  protected readonly overlays = OVERLAY_LAYERS.filter((o) => o.id !== 'circles');

  protected readonly base = signal<BaseLayerId>(DEFAULT_BASE_LAYER);
  protected readonly heatOn = signal(false);
  protected readonly clusterOn = signal(false);
  protected readonly platesOn = signal(false);
  protected readonly notice = signal<string | null>(null);

  protected readonly partition = computed(() => partitionDrawable(this.events()));
  protected readonly drawnCount = computed(() => this.partition().drawable.length);
  protected readonly omittedCount = computed(() => this.partition().omitted);
  protected readonly sample = computed(() => sampleLabel(this.drawnCount(), Math.max(this.total(), this.drawnCount())));
  protected readonly sampleVisible = computed(() => this.heatOn() || this.clusterOn());
  protected readonly attributions = computed(() => {
    const parts = [baseLayer(this.base()).attribution];
    for (const o of OVERLAY_LAYERS) {
      if (!o.attribution) continue;
      if (o.id === 'plates' && this.platesOn()) parts.push(o.attribution);
    }
    parts.push('Fronteras: Natural Earth', 'Datos sísmicos: USGS');
    return parts;
  });

  private readonly map = signal<L.Map | null>(null);
  private readonly eventsLayer = L.layerGroup();
  private readonly heatHolder = L.layerGroup();
  private readonly platesHolder = L.layerGroup();
  private bordersLayer?: L.GeoJSON;
  private tileLayer?: L.TileLayer;
  private platesData: FeatureCollection | null = null;
  private tileErrors = 0;

  constructor() {
    // A new filter without events shows the pop-up again.
    effect(() => {
      const value = this.noEvents();
      if (value) this.popupDismissed.set(false);
    });

    // Base layer: rebuilt when the choice or the theme changes.
    effect(() => {
      const map = this.map();
      const id = this.base();
      const theme = this.currentTheme();
      if (!map) return;
      this.applyBase(map, id, theme);
    });

    // Events: circles, or clusters when the option is on; heat is independent.
    effect(() => {
      const map = this.map();
      const { drawable } = this.partition();
      const cluster = this.clusterOn();
      const theme = this.currentTheme();
      if (!map) return;
      void this.drawEvents(drawable, cluster, theme);
    });

    effect(() => {
      const map = this.map();
      const { drawable } = this.partition();
      const heat = this.heatOn();
      if (!map) return;
      void this.drawHeat(drawable, heat);
    });

    effect(() => {
      const map = this.map();
      const on = this.platesOn();
      if (!map) return;
      void this.drawPlates(on);
    });

    effect(() => {
      const data = this.borders();
      if (!this.map() || !this.bordersLayer) return;
      this.bordersLayer.clearLayers();
      if (data) this.bordersLayer.addData(data);
    });
  }

  onMapReady(map: L.Map): void {
    this.bordersLayer = L.geoJSON(undefined, {
      style: { color: '#64748b', weight: 1, fill: false },
      onEachFeature: (feature, layer) => {
        const name = document.createElement('span');
        name.textContent = feature.properties?.NAME_ES ?? feature.properties?.ADMIN ?? 'Sin nombre';
        layer.bindTooltip(name);
      },
    }).addTo(map);
    this.platesHolder.addTo(map);
    this.heatHolder.addTo(map);
    this.eventsLayer.addTo(map);
    map.attributionControl.setPrefix(false);
    this.map.set(map);
  }

  protected chooseBase(id: BaseLayerId): void {
    this.notice.set(null);
    this.base.set(id);
    this.platesOn.set(platesDefault(id));
  }

  protected toggle(id: string, checked: boolean): void {
    if (id === 'heat') this.heatOn.set(checked);
    else if (id === 'cluster') this.clusterOn.set(checked);
    else if (id === 'plates') this.platesOn.set(checked);
  }

  protected isOn(id: string): boolean {
    return id === 'heat' ? this.heatOn() : id === 'cluster' ? this.clusterOn() : this.platesOn();
  }

  private applyBase(map: L.Map, id: BaseLayerId, theme: Theme): void {
    const def = baseLayer(id);
    this.tileLayer?.remove();
    this.tileErrors = 0;
    let tilesLoaded = 0;
    const layer = L.tileLayer(def.tiles(theme), { maxZoom: def.maxZoom, noWrap: true });
    layer.on('tileload', () => (tilesLoaded += 1));
    layer.on('tileerror', () => {
      this.tileErrors += 1;
      // Only a layer that has not drawn a single tile counts as failed.
      if (this.tileErrors < 3 || tilesLoaded > 0) return;
      if (id !== DEFAULT_BASE_LAYER) {
        this.notice.set(`No se pudo cargar el fondo «${def.label}»; se vuelve al mapa Simple.`);
        this.base.set(DEFAULT_BASE_LAYER);
        this.platesOn.set(false);
      } else {
        this.notice.set('No se pudieron cargar las teselas del mapa; los eventos siguen visibles.');
      }
    });
    layer.addTo(map);
    layer.bringToBack();
    const pane = layer.getContainer();
    if (pane) pane.style.filter = def.filter(theme);
    layer.on('load', () => {
      const c = layer.getContainer();
      if (c) c.style.filter = def.filter(theme);
    });
    this.tileLayer = layer;
  }

  private async drawEvents(drawable: MapEvent[], cluster: boolean, theme: Theme): Promise<void> {
    const mode = this.mode();
    void mode;
    this.eventsLayer.clearLayers();
    let target: L.LayerGroup = this.eventsLayer;
    if (cluster) {
      try {
        await import('leaflet.markercluster');
        const group = (globalLeaflet() as unknown as { markerClusterGroup: (o?: object) => L.LayerGroup }).markerClusterGroup({
          chunkedLoading: true,
        });
        this.eventsLayer.addLayer(group);
        target = group;
      } catch {
        this.notice.set('No se pudo cargar la agrupación; se muestran los círculos.');
      }
    }
    for (const event of drawable) {
      if (event.lat === null || event.lon === null) continue;
      const color = depthColor(depthCategory(event.depthKm).key, theme);
      const marker = L.circleMarker([event.lat, event.lon], {
        radius: markerRadius(event.mag),
        color,
        fillColor: color,
        fillOpacity: 0.75,
        weight: 1,
        dashArray: isUnvalued(event) ? '3 3' : undefined,
      });
      marker.on('click', () => this.eventSelected.emit(event));
      target.addLayer(marker);
    }
  }

  private async drawHeat(drawable: MapEvent[], on: boolean): Promise<void> {
    this.heatHolder.clearLayers();
    if (!on) return;
    try {
      await import('leaflet.heat');
      const factory = (globalLeaflet() as unknown as { heatLayer: HeatFactory }).heatLayer;
      const points = drawable
        .filter((e) => e.lat !== null && e.lon !== null)
        .map((e): [number, number, number] => [
          e.lat as number,
          e.lon as number,
          typeof e.mag === 'number' && Number.isFinite(e.mag) ? Math.min(1, Math.max(0.1, e.mag / 8)) : 0.1,
        ]);
      this.heatHolder.addLayer(factory(points, { radius: 18, blur: 20, maxZoom: 6 }));
    } catch {
      this.notice.set('No se pudo cargar el mapa de calor.');
      this.heatOn.set(false);
    }
  }

  private async drawPlates(on: boolean): Promise<void> {
    this.platesHolder.clearLayers();
    if (!on) return;
    try {
      if (!this.platesData) {
        const response = await fetch('datos/placas.geojson');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        this.platesData = (await response.json()) as FeatureCollection;
      }
      this.platesHolder.addLayer(
        L.geoJSON(this.platesData, { style: { color: '#ff6b6b', weight: 1.5, dashArray: '6 4', fill: false } }),
      );
    } catch {
      this.notice.set('No se pudieron cargar los límites de placas.');
      this.platesOn.set(false);
    }
  }

  ngOnDestroy(): void {
    this.eventsLayer.clearLayers();
    this.heatHolder.clearLayers();
    this.platesHolder.clearLayers();
    this.bordersLayer?.clearLayers();
  }
}
