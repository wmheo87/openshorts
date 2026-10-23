import { apiFetch } from '../../lib/api';
import { errorMessage } from './strings';

export class DiscoveryError extends Error {
  constructor(code, status = 0) {
    super(errorMessage(code, status));
    this.code = code;
    this.status = status;
  }
}

// A single attempt only. Aborting the browser does not cancel the server's search.
async function request(path, options = {}, timeoutMs = 75000) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  options.signal?.addEventListener('abort', abort, { once: true });
  if (options.signal?.aborted) controller.abort();
  let timedOut = false;
  const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  try {
    const response = await apiFetch(path, { ...options, signal: controller.signal });
    let body;
    try { body = await response.json(); }
    catch {
      if (controller.signal.aborted) throw new DiscoveryError(timedOut ? 'client_timeout' : 'cancelled');
      throw new DiscoveryError(response.ok ? 'invalid_response' : null, response.status);
    }
    if (!response.ok) throw new DiscoveryError(body?.detail?.code, response.status);
    if (!body || !Array.isArray(body.items)) throw new DiscoveryError('invalid_response');
    return body;
  } catch (error) {
    if (error instanceof DiscoveryError) throw error;
    if (controller.signal.aborted) throw new DiscoveryError(timedOut ? 'client_timeout' : 'cancelled');
    throw new DiscoveryError('network_error');
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener('abort', abort);
  }
}

export const searchVideos = (payload, signal) => request('/api/discovery/search', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal,
});
export function getSearchHistory(beforeId, signal) {
  const query = new URLSearchParams({ limit: '10' });
  if (beforeId != null) query.set('before_id', String(beforeId));
  return request(`/api/discovery/history?${query}`, { signal });
}
