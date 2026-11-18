import { ChangeDetectionStrategy, Component, OnInit, computed, effect, inject, signal } from '@angular/core';
import type { FeatureCollection } from 'geojson';
import { ObservatoryService } from './data/observatory.service';
import { FiltersComponent } from './filters/filters.component';
import { MapComponent } from './map/map.component';
import { AlertsComponent } from './alerts/alerts.component';
import { StatusBarComponent } from './status-bar/status-bar.component';
import { TableComponent } from './table/table.component';
import { ChartsComponent } from './charts/charts.component';
import { EventCardComponent } from './event-card/event-card.component';
import { LogoComponent } from './brand/logo.component';
import { ThemeService } from './theme/theme.service';
import type { MapEvent, Mode, QueryFilters } from './lib/api-types';
import { buildCountryCatalog } from './lib/countries';
import { filterChips } from './lib/filter-chips';
import { buildAlerts, noEventsText, type Alert, type LayerNotice, type NoEventsText } from './lib/alerts';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    FiltersComponent,
    MapComponent,
    AlertsComponent,
    StatusBarComponent,
    TableComponent,
    ChartsComponent,
    EventCardComponent,
    LogoComponent,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AppComponent implements OnInit {
  protected readonly service = inject(ObservatoryService);
  protected readonly themeService = inject(ThemeService);
  protected readonly borders = signal<FeatureCollection | null>(null);
  protected readonly bordersError = signal(false);
  protected readonly countries = computed(() => buildCountryCatalog(this.borders()));
  protected readonly selectedEvent = signal<MapEvent | null>(null);

  protected readonly events = computed(() => this.service.reading()?.events ?? []);
  protected readonly metadata = computed(() => this.service.reading()?.metadata ?? null);
  protected readonly mode = computed<Mode>(() => this.service.filters().mode);

  /** Problems reported by the map layers, by id. */
  private readonly layerNotices = signal<LayerNotice[]>([]);
  /** True for a few seconds after the panel recovers from a failure. */
  private readonly recovered = signal(false);
  private hadFailure = false;

  protected readonly alerts = computed<Alert[]>(() => {
    const reading = this.service.reading();
    const id = reading?.filters.countryId ?? null;
    const name = id === null ? null : (this.countries().find((c) => c.id === id)?.name ?? null);
    return buildAlerts({
      status: this.service.status(),
      statsFailure: this.service.statsFailure(),
      reading,
      countryName: name,
      configError: this.service.configError(),
      countriesUnavailable: this.bordersError(),
      layerNotices: this.layerNotices(),
      recovered: this.recovered()
    });
  });

  constructor() {
    effect(() => {
      const failed = this.service.failure() !== null;
      if (this.hadFailure && !failed) {
        this.recovered.set(true);
        setTimeout(() => this.recovered.set(false), 9000);
      }
      if (failed) this.recovered.set(false);
      this.hadFailure = failed;
    });
  }

  protected layerNotice(notice: LayerNotice | null): void {
    if (notice === null) this.layerNotices.set([]);
    else this.layerNotices.update((list) => [...list.filter((n) => n.id !== notice.id), notice]);
  }

  /** Chips for the filters of the last correct reading (the applied ones, not the form's). */
  protected readonly chips = computed(() => {
    const filters = this.service.reading()?.filters ?? this.service.filters();
    const name = filters.countryId === null ? null : (this.countries().find((c) => c.id === filters.countryId)?.name ?? null);
    return filterChips(filters, name);
  });

  /** Conditions of the filter when the last correct reading has no events (any filter, any mode). */
  protected readonly noEvents = computed<NoEventsText | null>(() => {
    const reading = this.service.reading();
    if (!reading || this.service.status().showingPreviousReading || reading.metadata.total !== 0) return null;
    const id = reading.filters.countryId;
    const name = id === null ? null : (this.countries().find((c) => c.id === id)?.name ?? null);
    return noEventsText(reading.filters, name);
  });

  async ngOnInit(): Promise<void> {
    void this.loadBorders();
    await this.service.start();
  }

  private async loadBorders(): Promise<void> {
    try {
      const response = await fetch('datos/paises.geojson');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      this.borders.set((await response.json()) as FeatureCollection);
    } catch {
      this.bordersError.set(true);
    }
  }

  protected apply(filters: QueryFilters): void {
    void this.service.applyFilters(filters);
  }

  protected changeMode(mode: Mode): void {
    void this.service.setMode(mode);
  }

  protected openCard(event: MapEvent): void {
    this.selectedEvent.set(event);
  }

  protected closeCard(): void {
    this.selectedEvent.set(null);
  }
}
