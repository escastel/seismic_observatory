import { describe, expect, it } from 'vitest';
import type { ApiFailure, FailureKind } from './api-types';
import { statsFailureKeepsEvents } from './stats-tolerance';

const f = (kind: FailureKind): ApiFailure => ({ kind, message: 'x' });

describe('statsFailureKeepsEvents', () => {
  it('keeps events for invalid parameters and invalid response', () => {
    expect(statsFailureKeepsEvents(f('invalid_parameters'))).toBe(true);
    expect(statsFailureKeepsEvents(f('invalid_response'))).toBe(true);
  });

  it('discards the refresh for unreachable and server-side failures', () => {
    expect(statsFailureKeepsEvents(f('unreachable'))).toBe(false);
    expect(statsFailureKeepsEvents(f('database_unavailable'))).toBe(false);
    expect(statsFailureKeepsEvents(f('server_error'))).toBe(false);
  });
});
