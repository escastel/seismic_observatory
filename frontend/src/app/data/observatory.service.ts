import { Injectable, OnDestroy, computed, signal } from '@angular/core';
import type { AdaptResult } from '../lib/adapt';
import { adaptEvents, adaptHealth, adaptStatistics, parseFailure } from '../lib/adapt';
import type { ApiFailure, Health, Mode, PanelConfig, QueryFilters, Reading, Statistics } from '../lib/api-types';
import { parseConfig } from '../lib/config';
import { eventParams, statsParams } from '../lib/filters';
import { statsFailureKeepsEvents } from '../lib/stats-tolerance';
import { derivePanelStatus } from '../lib/status';

export const PAGE_SIZE = 1000;

type Fetched = { ok: true; body: unknown } | { ok: false; failure: ApiFailure };

/**
 * Spec 010 (justified change): a statistics failure that is only a bad answer (422 or an invalid
 * response) no longer discards the whole refresh; the valid events of the new filter are shown with
 * `statistics = null` and `statsFailure`, instead of keeping another filter's reading.
 *
 * Reads the 006 API. One refresh cycle at a time (the timer is re-armed when a cycle ends),
 * a sequence number discards late responses, and the last correct reading is kept on failure.
 */
@Injectable({ providedIn: 'root' })
export class ObservatoryService implements OnDestroy {
  readonly config = signal<PanelConfig | null>(null);
  readonly configError = signal<string | null>(null);
  readonly filters = signal<QueryFilters>({ mode: 'live', start: null, end: null, minMag: null, countryId: null, excludeSynthetic: false });
  readonly reading = signal<Reading | null>(null);
  readonly failure = signal<ApiFailure | null>(null);
  /** A failure of /api/estadisticas only (events were read correctly), e.g. a 422 for a too long period. */
  readonly statsFailure = signal<ApiFailure | null>(null);
  readonly health = signal<Health | null>(null);
  readonly loading = signal(false);
  readonly loadingMore = signal(false);
  readonly now = signal(Date.now());

  readonly status = computed(() => {
    const config = this.config();
    return derivePanelStatus(this.reading(), this.failure(), this.health(), this.now(), config?.staleAfterMs ?? 900000);
  });
  /** Label emitted by the API for the displayed reading (e.g. REPRODUCCIÓN); null in live mode. */
  readonly label = computed(() => this.reading()?.metadata.label ?? null);
  readonly canLoadMore = computed(() => this.reading()?.metadata.nextOffset != null);

  private seq = 0;
  private controller = new AbortController();
  private timer?: ReturnType<typeof setTimeout>;
  private clock?: ReturnType<typeof setInterval>;
  private destroyed = false;

  async start(configUrl = 'config.json'): Promise<void> {
    try {
      const response = await fetch(configUrl, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const parsed = parseConfig(await response.json());
      if (!parsed.ok) {
        this.configError.set(parsed.error);
        return;
      }
      this.config.set(parsed.value);
      this.filters.update((f) => ({ ...f, mode: parsed.value.mode }));
    } catch {
      this.configError.set('No se pudo leer config.json');
      return;
    }
    this.clock = setInterval(() => this.now.set(Date.now()), 10000);
    await this.refresh();
  }

  /** Applies new filters. A change of mode clears everything from the previous mode first. */
  async applyFilters(next: QueryFilters): Promise<void> {
    const modeChanged = next.mode !== this.filters().mode;
    this.filters.set(next);
    if (modeChanged) this.clearAll();
    await this.refresh();
  }

  async setMode(mode: Mode): Promise<void> {
    if (mode === this.filters().mode) return;
    await this.applyFilters({ ...this.filters(), mode, excludeSynthetic: mode === 'replay' ? this.filters().excludeSynthetic : false });
  }

  private clearAll(): void {
    this.abortPending();
    this.reading.set(null);
    this.failure.set(null);
    this.statsFailure.set(null);
    this.health.set(null);
  }

  private abortPending(): void {
    this.seq++;
    this.controller.abort();
    this.controller = new AbortController();
    clearTimeout(this.timer);
    this.loading.set(false);
    this.loadingMore.set(false);
  }

  private async fetchJson(path: string, params: URLSearchParams | null): Promise<Fetched> {
    const config = this.config() as PanelConfig;
    const query = params && params.size > 0 ? `?${params}` : '';
    const headers: Record<string, string> = {};
    if (config.skipNgrokWarning) headers['ngrok-skip-browser-warning'] = '1';
    try {
      const response = await fetch(`${config.apiUrl}/api/${path}${query}`, {
        // No `cache` option: `no-store` makes browsers send Cache-Control/Pragma, which the API CORS
        // contract (Content-Type, ngrok-skip-browser-warning only) rejects in the preflight with 400.
        headers,
        signal: AbortSignal.any([this.controller.signal, AbortSignal.timeout(config.requestTimeoutMs)])
      });
      let body: unknown;
      try {
        body = await response.json();
      } catch {
        return { ok: false, failure: { kind: 'unreachable', message: 'La respuesta no es JSON (¿página intermedia del túnel?)' } };
      }
      if (!response.ok) return { ok: false, failure: parseFailure(response.status, body) };
      return { ok: true, body };
    } catch (error) {
      if (this.controller.signal.aborted) throw error;
      return { ok: false, failure: { kind: 'unreachable', message: 'No hay respuesta del backend (red, tiempo agotado o CORS)' } };
    }
  }

  /** One refresh cycle. Never overlaps: starting a new one aborts and invalidates the previous. */
  async refresh(): Promise<void> {
    if (!this.config() || this.destroyed) return;
    this.abortPending();
    const seq = this.seq;
    const filters = this.filters();
    this.loading.set(true);
    try {
      const [events, stats, health] = await Promise.all([
        this.fetchJson('eventos', eventParams(filters, PAGE_SIZE, 0)),
        this.fetchJson('estadisticas', statsParams(filters)),
        this.fetchJson('salud', null)
      ]);
      if (seq !== this.seq) return; // a newer query replaced this one: discard
      const adaptedHealth = health.ok ? adaptHealth(health.body) : null;
      this.health.set(adaptedHealth && adaptedHealth.ok ? adaptedHealth.value : null);

      const page = this.adapt(events, (b) => adaptEvents(b, filters.mode));
      if (!page.ok) return this.fail(page.failure);
      let statistics: Statistics | null = null;
      this.statsFailure.set(null);
      const adaptedStats = this.adapt(stats, (b) => adaptStatistics(b, filters.mode));
      if (adaptedStats.ok) {
        statistics = adaptedStats.value;
      } else if (statsFailureKeepsEvents(adaptedStats.failure)) {
        this.statsFailure.set(adaptedStats.failure);
      } else {
        return this.fail(adaptedStats.failure);
      }
      this.failure.set(null);
      this.reading.set({
        readAt: Date.now(),
        filters,
        events: page.value.events,
        metadata: page.value.metadata,
        statistics,
        health: this.health()
      });
      this.now.set(Date.now());
    } catch {
      // aborted by a newer query or by destroy: nothing to do
    } finally {
      if (seq === this.seq) {
        this.loading.set(false);
        this.schedule();
      }
    }
  }

  private adapt<T>(fetched: Fetched, fn: (body: unknown) => AdaptResult<T>): AdaptResult<T> {
    return fetched.ok ? fn(fetched.body) : { ok: false, failure: fetched.failure };
  }

  /** Keeps the previous reading; only the failure is recorded. */
  private fail(failure: ApiFailure): void {
    this.failure.set(failure);
    this.now.set(Date.now());
  }

  private schedule(): void {
    clearTimeout(this.timer);
    if (this.destroyed) return;
    this.timer = setTimeout(() => void this.refresh(), this.config()?.refreshMs ?? 60000);
  }

  /** Loads the next page of the table (same filters, same reading). */
  async loadMore(): Promise<void> {
    const current = this.reading();
    const offset = current?.metadata.nextOffset;
    if (!current || offset == null || this.loadingMore()) return;
    const seq = this.seq;
    this.loadingMore.set(true);
    try {
      const fetched = await this.fetchJson('eventos', eventParams(current.filters, PAGE_SIZE, offset));
      if (seq !== this.seq) return;
      const page = this.adapt(fetched, (b) => adaptEvents(b, current.filters.mode));
      if (!page.ok) return this.fail(page.failure);
      const latest = this.reading();
      if (!latest || latest !== current) return;
      this.reading.set({
        ...latest,
        events: [...latest.events, ...page.value.events],
        metadata: { ...latest.metadata, nextOffset: page.value.metadata.nextOffset }
      });
    } catch {
      // aborted
    } finally {
      if (seq === this.seq) this.loadingMore.set(false);
    }
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.abortPending();
    clearInterval(this.clock);
  }
}
