import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';

import type { PanelStatus, Reading, Statistics } from '../lib/api-types';
import type { SummaryTone } from '../lib/summary';
import { buildStatusBar } from '../lib/status-bar';

const TONE_ICON: Record<SummaryTone, string> = {
  ok: '●',
  warning: '▲',
  error: '✕',
  neutral: ''
};

@Component({
  selector: 'app-status-bar',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './status-bar.component.html',
  styleUrl: './status-bar.component.css'
})
export class StatusBarComponent {
  readonly statistics = input<Statistics | null>(null);
  readonly status = input<PanelStatus | null>(null);
  readonly reading = input<Reading | null>(null);
  /** Accessible name of the bar. */
  readonly label = input<string>('Estado y resumen');

  protected readonly open = signal(false);
  protected readonly bar = computed(() => buildStatusBar(this.statistics(), this.status(), this.reading()));
  protected readonly hiddenOnNarrow = computed(() => this.bar().metrics.filter((m) => !m.visibleOnNarrow));

  protected icon(tone: SummaryTone): string {
    return TONE_ICON[tone];
  }

  protected toggle(): void {
    this.open.update((v) => !v);
  }
}
