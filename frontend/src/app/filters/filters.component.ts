import { ChangeDetectionStrategy, Component, computed, effect, input, output, signal } from '@angular/core';

import type { Mode, QueryFilters } from '../lib/api-types';
import type { CountryOption } from '../lib/countries';
import { parseUtcInput, toUtcInput, validateFilters, type FilterErrors } from '../lib/filters';

@Component({
  selector: 'app-filters',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './filters.component.html',
  styleUrl: './filters.component.css',
})
export class FiltersComponent {
  readonly filters = input.required<QueryFilters>();
  readonly countries = input<CountryOption[]>([]);

  readonly apply = output<QueryFilters>();
  readonly modeChange = output<Mode>();

  protected readonly mode = signal<Mode>('live');
  protected readonly start = signal('');
  protected readonly end = signal('');
  protected readonly minMag = signal('');
  protected readonly countryId = signal('');
  protected readonly excludeSynthetic = signal(false);
  protected readonly errors = signal<FilterErrors>({});

  protected readonly isReplay = computed(() => this.mode() === 'replay');

  constructor() {
    effect(() => this.load(this.filters()));
  }

  private load(f: QueryFilters): void {
    this.mode.set(f.mode);
    this.start.set(toUtcInput(f.start));
    this.end.set(toUtcInput(f.end));
    this.minMag.set(f.minMag === null ? '' : String(f.minMag));
    this.countryId.set(f.countryId ?? '');
    this.excludeSynthetic.set(f.excludeSynthetic);
    this.errors.set({});
  }

  protected value(event: Event): string {
    return (event.target as HTMLInputElement | HTMLSelectElement).value;
  }

  protected onMode(event: Event): void {
    const next = this.value(event) === 'replay' ? 'replay' : 'live';
    this.mode.set(next);
    this.modeChange.emit(next);
  }

  protected onSubmit(event: Event): void {
    event.preventDefault();
    const errors = validateFilters({
      mode: this.mode(),
      start: this.start(),
      end: this.end(),
      minMag: this.minMag(),
      countryId: this.countryId(),
    });
    this.errors.set(errors);
    if (Object.keys(errors).length > 0) return;
    const mag = this.minMag().trim();
    const country = this.countryId().trim();
    this.apply.emit({
      mode: this.mode(),
      start: parseUtcInput(this.start()),
      end: parseUtcInput(this.end()),
      minMag: mag === '' ? null : Number(mag),
      countryId: country === '' ? null : country,
      excludeSynthetic: this.mode() === 'replay' && this.excludeSynthetic(),
    });
  }

  protected onReset(event: Event): void {
    event.preventDefault();
    const cleared: QueryFilters = { mode: this.mode(), start: null, end: null, minMag: null, countryId: null, excludeSynthetic: false };
    this.load(cleared);
    this.apply.emit(cleared);
  }
}
