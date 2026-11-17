import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import type { PanelStatus, Statistics } from '../lib/api-types';
import { buildSummaryCards, type SummaryTone } from '../lib/summary';

const TONE_ICON: Record<SummaryTone, string> = {
  ok: '✓',
  warning: '⚠',
  error: '✕',
  neutral: '○'
};

@Component({
  selector: 'app-summary',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './summary.component.html',
  styleUrl: './summary.component.css'
})
export class SummaryComponent {
  readonly statistics = input<Statistics | null>(null);
  readonly status = input<PanelStatus | null>(null);

  protected readonly cards = computed(() => buildSummaryCards(this.statistics(), this.status()));

  protected icon(tone: SummaryTone): string {
    return TONE_ICON[tone];
  }
}
