import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

import type { NoEventsText } from '../lib/alerts';

/**
 * Floating, non-modal notice shown over the map when a reading has no events.
 * It is aria-hidden: the alerts zone announces the same message.
 */
@Component({
  selector: 'app-no-events-popup',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './no-events-popup.component.html',
  styleUrl: './no-events-popup.component.css'
})
export class NoEventsPopupComponent {
  readonly text = input.required<NoEventsText>();
  readonly dismissed = output<void>();

  close(): void {
    this.dismissed.emit();
  }
}
