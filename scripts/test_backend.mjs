import { GPUBackend, BackendUnavailable, normalizeEndpoint } from '../gpu-backend.mjs';

const assert = (condition, message) => { if (!condition) throw Error(message); };
const mustFail = async operation => {
  try { await operation(); } catch (error) { assert(error instanceof BackendUnavailable, 'Public connection error'); return; }
  throw Error('Operation should fail');
};
const endpoint = 'https://space-test.gradio.live';
let checks = 0;
function check(condition, message) { assert(condition, message); checks++; }

check(normalizeEndpoint(endpoint + '/') === endpoint, 'Normalize HTTPS endpoint');
for (const value of ['javascript:alert(1)', 'http://space-test.gradio.live', 'https://evil.example',
  'https://space-test.gradio.live.evil.example', 'https://user:password@space-test.gradio.live', 'https://space-test.gradio.live:8080']) {
  let rejected = false;
  try { normalizeEndpoint(value); } catch { rejected = true; }
  check(rejected, `Reject invalid endpoint: ${value}`);
}

let loads = 0;
const status = [];
const offline = new GPUBackend({ fetchConfig: async () => ({ colabEndpoint: '' }),
  loadClient: async () => { loads++; }, onStatus: phase => status.push(phase) });
await mustFail(() => offline.ensureReady());
check(loads === 0 && status.at(-1) === 'offline' && !offline.client, 'No fake result or client without server');

let configured = endpoint, connections = 0, configReads = 0;
const clients = [];
const sdk = { Client: { connect: async address => {
  connections++;
  const client = { address, closed: false, close() { this.closed = true; },
    view_api: async () => ({ named_endpoints: { '/reconstruct': {} } }) };
  clients.push(client); return client;
} }, handle_file: file => file };
const backend = new GPUBackend({ fetchConfig: async () => { configReads++; return { colabEndpoint: configured }; }, loadClient: async () => sdk });
const first = backend.ensureReady(), same = backend.ensureReady();
check(first === same, 'Page startup and photo upload share one connection');
await first;
check(backend.client === clients[0] && backend.endpoint === endpoint && connections === 1, 'Automatic configured connection');
await backend.ensureReady();
check(connections === 1 && configReads === 2, 'Reuse client while checking fresh published configuration');
configured = 'https://replacement.gradio.live';
await backend.ensureReady();
check(connections === 2 && clients[0].closed && backend.endpoint === configured, 'Replace expired runtime address without visitor setup');
backend.invalidate();
check(!backend.client && clients[1].closed, 'Release stale connection');

let wrongClosed = false;
const wrong = new GPUBackend({ fetchConfig: async () => ({ colabEndpoint: endpoint }),
  loadClient: async () => ({ Client: { connect: async () => ({ close: () => { wrongClosed = true; },
    view_api: async () => ({ named_endpoints: { '/wrong': {} } }) }) } }) });
await mustFail(() => wrong.ensureReady());
check(wrongClosed && !wrong.client, 'Require actual reconstruct API');

let attempts = 0;
const retry = new GPUBackend({ fetchConfig: async () => {
  if (++attempts === 1) throw Error('Temporary network failure');
  return { colabEndpoint: endpoint };
}, loadClient: async () => sdk });
await mustFail(() => retry.ensureReady());
await retry.ensureReady();
check(attempts === 2 && retry.client, 'Retry after temporary connection failure');
retry.invalidate();

let finishOpening, lateClosed = false;
const timed = new GPUBackend({ timeout: 10, fetchConfig: async () => ({ colabEndpoint: endpoint }),
  loadClient: async () => ({ Client: { connect: () => new Promise(resolve => { finishOpening = resolve; }) } }) });
await mustFail(() => timed.ensureReady());
finishOpening({ close: () => { lateClosed = true; }, view_api: async () => ({ named_endpoints: { '/reconstruct': {} } }) });
await new Promise(resolve => setTimeout(resolve, 0));
check(lateClosed && !timed.client && !timed.pending, 'Close late connection after timeout; no stalled spinner');

const session = new GPUBackend({ fetchConfig: async () => { throw Error('Session should not read config'); }, loadClient: async () => sdk });
session.useSessionEndpoint(endpoint);
await session.ensureReady();
check(session.endpoint === endpoint, 'Owner return link tests a session without exposing setup to visitors');
session.invalidate();
console.log(`${checks} automatic GPU connection checks passed (simulated API, no actual inference).`);
