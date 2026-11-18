// Decides whether a failed statistics read still allows keeping valid events (010, R7).
import type { ApiFailure } from './api-types';

export function statsFailureKeepsEvents(failure: ApiFailure): boolean {
  return failure.kind === 'invalid_parameters' || failure.kind === 'invalid_response';
}
