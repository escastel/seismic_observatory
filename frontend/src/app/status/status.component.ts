import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import type { ApiFailure, PanelStatus, QueryFilters, Reading, StatusKey } from '../lib/api-types';
import { formatUtc } from '../lib/format';

interface StatusMessage {
  text: string;
  prefix: string;
  urgent: boolean;
}

const INFO_KEYS: StatusKey[] = ['ok', 'empty'];

@Component({
  selector: 'app-status',
  standalone: true,
  templateUrl: './status.component.html',
  styleUrl: './status.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class StatusComponent {
  readonly reading = input<Reading | null>(null);
  readonly status = input.required<PanelStatus>();
  readonly label = input<string | null>(null);
  readonly loading = input<boolean>(false);
  readonly statsFailure = input<ApiFailure | null>(null);
  readonly filters = input.required<QueryFilters>();

  protected readonly formatUtc = formatUtc;

  protected readonly messages = computed<StatusMessage[]>(() => {
    const { keys, messages } = this.status();
    return messages.map((text, i) => {
      const key = keys[i];
      return {
        text,
        prefix: key !== undefined && INFO_KEYS.includes(key) ? 'Información:' : 'Aviso:',
        urgent: key === 'unreachable'
      };
    });
  });

  protected readonly modeText = computed(() => {
    const mode = this.reading()?.metadata.mode ?? this.filters().mode;
    return mode === 'replay' ? 'Reproducción' : 'Tiempo real';
  });

  protected readonly isReplay = computed(
    () => (this.reading()?.metadata.mode ?? this.filters().mode) === 'replay'
  );

  protected readonly periodText = computed(() => {
    const period = this.reading()?.metadata.period;
    if (!period) return null;
    const from = period.start === null ? 'sin inicio' : formatUtc(period.start);
    const to = period.end === null ? 'sin fin (hasta ahora)' : formatUtc(period.end);
    const range = `${from} a ${to}`;
    return period.defaultApplied ? `${range} (últimas 24 h, periodo por defecto)` : range;
  });
}
