import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

import { MapEvent, Mode } from '../lib/api-types';
import { countryLabel, formatDepth, formatMagnitude, formatUtc, textOrAbsent } from '../lib/format';

@Component({
  selector: 'app-table',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './table.component.html',
  styleUrl: './table.component.css',
})
export class TableComponent {
  readonly events = input<MapEvent[]>([]);
  readonly total = input<number>(0);
  readonly nextOffset = input<number | null>(null);
  readonly loadingMore = input<boolean>(false);
  readonly label = input<string | null>(null);
  readonly mode = input<Mode>('live');
  readonly truncated = input<boolean>(false);

  readonly loadMore = output<void>();

  readonly isReplay = computed(() => this.mode() === 'replay');
  readonly shown = computed(() => this.events().length);
  readonly incomplete = computed(() => this.truncated() || this.shown() < this.total());
  readonly canLoadMore = computed(() => this.nextOffset() !== null && !this.loadingMore());

  readonly formatUtc = formatUtc;
  readonly formatMagnitude = formatMagnitude;
  readonly formatDepth = formatDepth;
  readonly countryLabel = countryLabel;
  readonly textOrAbsent = textOrAbsent;

  syntheticText(value: boolean | null): string {
    if (value === null) return 'Sin dato';
    return value ? 'Sí' : 'No';
  }

  onLoadMore(): void {
    if (this.canLoadMore()) this.loadMore.emit();
  }
}
