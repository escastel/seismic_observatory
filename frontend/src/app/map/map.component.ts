import { ChangeDetectionStrategy, Component, computed, effect, input, OnDestroy, signal } from '@angular/core';
import { LeafletDirective } from '@bluehalo/ngx-leaflet';
import * as L from 'leaflet';
import type { FeatureCollection } from 'geojson';

import type { MapEvent, Mode } from '../lib/api-types';
import { depthCategory, isUnvalued, legendItems, markerRadius, partitionDrawable, popupLines } from '../lib/geo';

@Component({
  selector: 'app-map',
  standalone: true,
  imports: [LeafletDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './map.component.html',
  styleUrl: './map.component.css',
})
export class MapComponent implements OnDestroy {
  readonly events = input<MapEvent[]>([]);
  readonly borders = input<FeatureCollection | null>(null);
  readonly label = input<string | null>(null);
  readonly mode = input<Mode>('live');

  readonly options: L.MapOptions = {
    center: L.latLng(18, 0),
    zoom: 2,
    minZoom: 2,
    maxZoom: 8,
    preferCanvas: true,
    worldCopyJump: false,
  };

  readonly legend = legendItems();
  protected readonly partition = computed(() => partitionDrawable(this.events()));
  protected readonly drawnCount = computed(() => this.partition().drawable.length);
  protected readonly omittedCount = computed(() => this.partition().omitted);

  private readonly map = signal<L.Map | null>(null);
  private readonly eventsLayer = L.layerGroup();
  private bordersLayer?: L.GeoJSON;

  constructor() {
    effect(() => {
      const map = this.map();
      const { drawable } = this.partition();
      const mode = this.mode();
      if (!map) return;
      const next = L.layerGroup();
      for (const event of drawable) {
        if (event.lat === null || event.lon === null) continue;
        const color = depthCategory(event.depthKm).color;
        const popup = document.createElement('div');
        popup.style.whiteSpace = 'pre-line';
        popup.textContent = popupLines(event, mode).join('\n');
        L.circleMarker([event.lat, event.lon], {
          radius: markerRadius(event.mag),
          color,
          fillColor: color,
          fillOpacity: 0.75,
          weight: 1,
          dashArray: isUnvalued(event) ? '3 3' : undefined,
        })
          .bindPopup(popup)
          .addTo(next);
      }
      this.eventsLayer.clearLayers();
      this.eventsLayer.addLayer(next);
    });

    effect(() => {
      const data = this.borders();
      if (!this.map() || !this.bordersLayer) return;
      this.bordersLayer.clearLayers();
      if (data) this.bordersLayer.addData(data);
    });
  }

  onMapReady(map: L.Map): void {
    const base = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      noWrap: true,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    this.bordersLayer = L.geoJSON(undefined, {
      style: { color: '#334155', weight: 1, fill: false },
      onEachFeature: (feature, layer) => {
        const name = document.createElement('span');
        name.textContent = feature.properties?.NAME_ES ?? feature.properties?.ADMIN ?? 'Sin nombre';
        layer.bindTooltip(name);
      },
    }).addTo(map);
    this.eventsLayer.addTo(map);
    L.control
      .layers({ OpenStreetMap: base }, { 'Países (Natural Earth)': this.bordersLayer, Terremotos: this.eventsLayer })
      .addTo(map);
    map.attributionControl.addAttribution('Fronteras: Natural Earth · Datos reales: USGS');
    this.map.set(map);
  }

  ngOnDestroy(): void {
    this.eventsLayer.clearLayers();
    this.bordersLayer?.clearLayers();
  }
}
