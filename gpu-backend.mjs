export function normalizeEndpoint(value) {
  let url;
  try { url = new URL(value.trim()); } catch { throw Error('GPU 서버 주소를 확인해주세요.'); }
  if (url.protocol !== 'https:' || !/^[a-z0-9-]+\.(?:gradio\.live|hf\.space)$/i.test(url.hostname) ||
      url.username || url.password || url.port) throw Error('GPU 서버 주소를 확인해주세요.');
  return url.origin;
}

export class BackendUnavailable extends Error {
  constructor(message = '서버를 준비하고 있어요. 잠시 후 다시 시도해주세요.') {
    super(message); this.name = 'BackendUnavailable';
  }
}

// Visitors use the operator's running GPU server; no notebook or setup UI is needed.
export class GPUBackend {
  constructor({ fetchConfig = async () => {
    const response = await fetch(new URL('./space.config.json', import.meta.url), { cache: 'no-store' });
    if (!response.ok) throw new BackendUnavailable();
    return response.json();
  }, loadClient = () => import('./vendor/gradio-client.js'), onStatus = () => {}, timeout = 25000,
    spaceTimeout = 180000, retryDelay = 3000 } = {}) {
    this.fetchConfig = fetchConfig; this.loadClient = loadClient; this.onStatus = onStatus;
    this.timeout = timeout; this.client = null; this.api = null; this.endpoint = ''; this.pending = null;
    this.sessionEndpoint = '';
    this.spaceTimeout = spaceTimeout; this.retryDelay = retryDelay;
  }

  useSessionEndpoint(value) { this.sessionEndpoint = normalizeEndpoint(value); }

  ensureReady() {
    if (this.pending) return this.pending;
    this.pending = this.connect().finally(() => { this.pending = null; });
    return this.pending;
  }

  async connect() {
    this.onStatus('connecting');
    let candidate = null, expired = false, timer;
    let rejectDeadline;
    const deadline = new Promise((_, reject) => { rejectDeadline = reject; });
    const armDeadline = duration => {
      clearTimeout(timer);
      timer = setTimeout(() => { expired = true; candidate?.close?.(); rejectDeadline(new BackendUnavailable('서버 연결이 지연되고 있어요. 잠시 후 다시 시도해주세요.')); }, duration);
    };
    armDeadline(this.timeout);
    const opening = (async () => {
      const config = this.sessionEndpoint ? {} : await this.fetchConfig();
      const address = this.sessionEndpoint || config.colabEndpoint;
      if (!address) throw new BackendUnavailable();
      const endpoint = normalizeEndpoint(address);
      if (expired) throw new BackendUnavailable();
      if (this.client && this.endpoint === endpoint) return this;
      const isSpace = new URL(endpoint).hostname.endsWith('.hf.space');
      if (isSpace) armDeadline(this.spaceTimeout);
      this.api ??= await this.loadClient();
      if (expired) throw new BackendUnavailable();
      // A visit to a sleeping Space starts it again. Retry connection while the
      // app loads its model, keeping one bounded request shared by all callers.
      while (!expired) {
        try {
          candidate = await this.api.Client.connect(endpoint, { events: ['data', 'status'] });
          break;
        } catch (error) {
          if (!isSpace || expired) throw error;
          await new Promise(resolve => setTimeout(resolve, this.retryDelay));
        }
      }
      if (!candidate) throw new BackendUnavailable();
      if (expired) { candidate.close?.(); throw new BackendUnavailable(); }
      const info = await candidate.view_api();
      if (!info.named_endpoints?.['/reconstruct']) throw new BackendUnavailable();
      if (expired) { candidate.close?.(); throw new BackendUnavailable(); }
      this.client?.close?.(); this.client = candidate; candidate = null; this.endpoint = endpoint;
      return this;
    })();
    try {
      const connection = await Promise.race([opening, deadline]);
      this.onStatus('ready'); return connection;
    } catch (error) {
      expired = true; candidate?.close?.(); this.invalidate();
      if (error instanceof BackendUnavailable) throw error;
      throw new BackendUnavailable('서버에 연결하지 못했어요. 잠시 후 다시 시도해주세요.');
    } finally { clearTimeout(timer); }
  }

  invalidate() { this.client?.close?.(); this.client = null; this.endpoint = ''; this.onStatus('offline'); }
}
