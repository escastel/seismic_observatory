import { ChangeDetectionStrategy, Component, DestroyRef, computed, effect, inject, input, signal } from '@angular/core';

import type { Alert, AlertKind } from '../lib/alerts';

const KIND_LABEL: Record<AlertKind, string> = {
  error: 'Error',
  warning: 'Aviso',
  info: 'Información',
  success: 'Correcto'
};

@Component({
  selector: 'app-alerts',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './alerts.component.html',
  styleUrl: './alerts.component.css'
})
export class AlertsComponent {
  readonly alerts = input<Alert[]>([]);

  private readonly dismissed = signal<ReadonlySet<string>>(new Set());
  private readonly timers = new Map<string, ReturnType<typeof setTimeout>>();

  protected readonly visible = computed(() => this.alerts().filter((a) => !this.dismissed().has(a.id)));

  constructor() {
    const destroyRef = inject(DestroyRef);
    destroyRef.onDestroy(() => {
      this.timers.forEach((timer) => clearTimeout(timer));
      this.timers.clear();
    });

    effect(() => {
      const current = this.alerts();
      const ids = new Set(current.map((a) => a.id));

      // An alert that disappeared may show again later: forget its dismissal and timer.
      for (const [id, timer] of this.timers) {
        if (!ids.has(id)) {
          clearTimeout(timer);
          this.timers.delete(id);
        }
      }
      const dismissed = this.dismissed();
      if ([...dismissed].some((id) => !ids.has(id))) {
        this.dismissed.set(new Set([...dismissed].filter((id) => ids.has(id))));
      }

      for (const alert of current) {
        if (alert.autoDismissMs !== null && !this.timers.has(alert.id) && !dismissed.has(alert.id)) {
          this.timers.set(
            alert.id,
            setTimeout(() => this.dismiss(alert.id), alert.autoDismissMs)
          );
        }
      }
    });
  }

  protected label(kind: AlertKind): string {
    return KIND_LABEL[kind];
  }

  protected dismiss(id: string): void {
    const timer = this.timers.get(id);
    if (timer !== undefined) clearTimeout(timer);
    this.timers.delete(id);
    this.dismissed.update((set) => new Set(set).add(id));
  }
}
