import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';

import { ThemeService } from '../theme/theme.service';

@Component({
  selector: 'app-theme-toggle',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './theme-toggle.component.html',
  styleUrl: './theme-toggle.component.css'
})
export class ThemeToggleComponent {
  private readonly themeService = inject(ThemeService);

  readonly isDark = computed(() => this.themeService.theme() === 'dark');
  readonly animated = computed(() => !this.themeService.reducedMotion());
  readonly label = computed(() => (this.isDark() ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'));

  toggle(): void {
    this.themeService.toggle();
  }
}
