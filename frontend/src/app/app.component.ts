import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import type { FeatureCollection } from 'geojson';
import { ObservatoryService } from './data/observatory.service';
import { FiltersComponent } from './filters/filters.component';
import { MapComponent } from './map/map.component';
import { StatusComponent } from './status/status.component';
import { TableComponent } from './table/table.component';
import { ChartsComponent } from './charts/charts.component';
import type { Mode, QueryFilters } from './lib/api-types';
import { buildCountryCatalog } from './lib/countries';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [FiltersComponent, MapComponent, StatusComponent, TableComponent, ChartsComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AppComponent implements OnInit {
  protected readonly service = inject(ObservatoryService);
  protected readonly borders = signal<FeatureCollection | null>(null);
  protected readonly bordersError = signal(false);
  protected readonly countries = computed(() => buildCountryCatalog(this.borders()));

  protected readonly events = computed(() => this.service.reading()?.events ?? []);
  protected readonly metadata = computed(() => this.service.reading()?.metadata ?? null);
  protected readonly mode = computed<Mode>(() => this.service.filters().mode);

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
}
