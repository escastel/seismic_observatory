import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  effect,
  inject,
  input,
  output,
  viewChild,
} from '@angular/core';
import type { MapEvent, Mode } from '../lib/api-types';
import { buildEventCard } from '../lib/event-card';
import { ThemeService } from '../theme/theme.service';

@Component({
  selector: 'app-event-card',
  standalone: true,
  templateUrl: './event-card.component.html',
  styleUrl: './event-card.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EventCardComponent {
  readonly event = input<MapEvent | null>(null);
  readonly mode = input<Mode>('live');
  readonly closed = output<void>();

  protected readonly reducedMotion = inject(ThemeService).reducedMotion;
  protected readonly card = computed(() => {
    const event = this.event();
    return event ? buildEventCard(event, this.mode()) : null;
  });

  private readonly closeButton = viewChild<ElementRef<HTMLButtonElement>>('closeButton');
  private previousFocus: HTMLElement | null = null;

  constructor() {
    effect((onCleanup) => {
      const button = this.closeButton();
      if (!button) return;
      const active = document.activeElement;
      this.previousFocus = active instanceof HTMLElement ? active : null;
      button.nativeElement.focus();
      onCleanup(() => {
        const target = this.previousFocus;
        this.previousFocus = null;
        if (target && target.isConnected) target.focus();
      });
    });
  }

  protected close(): void {
    this.closed.emit();
  }

  protected onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.stopPropagation();
      this.close();
    }
  }
}
