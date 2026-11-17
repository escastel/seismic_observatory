import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Logotipo de seismicobservatory: una «S» cruzada por una línea de sismograma. */
@Component({
  selector: 'app-logo',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      width="32"
      height="32"
      fill="none"
      [attr.aria-hidden]="decorative() ? 'true' : null"
      [attr.role]="decorative() ? null : 'img'"
      [attr.aria-label]="decorative() ? null : 'Logotipo de seismicobservatory'"
    >
      <path
        d="M43 19.5C43 14.5 37.5 12 32 12C25.5 12 21 15.2 21 20.4C21 25.6 25.6 27.6 32 29.8C38.6 32.1 43 34.4 43 40C43 45.6 38.2 52 31.5 52C25.4 52 21 49.2 21 44"
        stroke="var(--accent, currentColor)"
        stroke-width="5.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <path
        d="M5 32H17L21 25L26 40L31 22L36 42L40 29L44 32H59"
        stroke="currentColor"
        stroke-width="2.6"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
  `,
  styles: [':host { display: inline-flex; line-height: 0; } svg { display: block; }'],
})
export class LogoComponent {
  /** Si es true, el logotipo es decorativo y se oculta a los lectores de pantalla. */
  readonly decorative = input(true);
}
