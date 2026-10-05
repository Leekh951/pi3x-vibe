// Exercise the shipped SDK against a public API whose preflight omits ACAC.
import { Client } from '../vendor/gradio-client.js';
import { Blob } from 'node:buffer';

const originalFetch = globalThis.fetch, originalWindow = globalThis.window;
const requests = [];
const endpoint = 'https://transport-test.hf.space';
const config = { version: '5.49.1', api_prefix: '/gradio_api', components: [],
  dependencies: [{ id: 0, api_name: 'reconstruct', inputs: [], outputs: [] }] };
const info = { named_endpoints: { '/reconstruct': { parameters: [], returns: [] } }, unnamed_endpoints: {} };
let client;
try {
  // Select the browser transport without installing Node WebSocket packages.
  globalThis.window = { WebSocket: class {}, location: { href: endpoint } };
  globalThis.fetch = async (url, options = {}) => {
    const address = url.url || String(url), credentials = options.credentials ?? url.credentials;
    requests.push({ url: address, options: { ...options, credentials } });
    if (credentials === 'include') throw Error('Credentialed CORS preflight rejected');
    const path = new URL(address).pathname;
    if (path === '/config') return Response.json(config);
    if (path === '/gradio_api/info') return Response.json(info);
    if (path === '/gradio_api/upload') {
      if (!(options.body instanceof FormData) || options.body.getAll('files').length !== 1) throw Error('Missing photo upload');
      return Response.json(['/tmp/upload.png']);
    }
    if (path === '/gradio_api/queue/join') return Response.json({ event_id: 'test-event' });
    if (path === '/gradio_api/queue/data') return new Response('data: {"msg":"heartbeat"}\n\n', { headers: { 'Content-Type': 'text/event-stream' } });
    throw Error('Unexpected request: ' + url);
  };
  client = await Client.connect(endpoint);
  const uploaded = await client.upload_files(endpoint, [new Blob(['photo'], { type: 'image/png' })]);
  if (uploaded.files?.[0] !== '/tmp/upload.png') throw Error('Upload did not complete');
  const [queued, status] = await client.post_data(endpoint + '/gradio_api/queue/join', { data: [], session_hash: 'test' });
  if (status !== 200 || queued.event_id !== 'test-event') throw Error('Queue request did not complete');
  const stream = client.stream(new URL(endpoint + '/gradio_api/queue/data?session_hash=test'));
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(Error('Progress stream did not respond')), 1000);
    stream.onmessage = event => {
      clearTimeout(timer);
      if (JSON.parse(event.data).msg === 'heartbeat') resolve(); else reject(Error('Invalid progress stream'));
    };
    stream.onerror = error => { clearTimeout(timer); reject(error); };
  });
  for (const path of ['/config', '/gradio_api/info', '/gradio_api/upload', '/gradio_api/queue/join', '/gradio_api/queue/data']) {
    if (!requests.some(item => new URL(item.url).pathname === path)) throw Error('Missing transport check: ' + path);
  }
  console.log('Public Gradio connection, upload, queue and progress transport passed (simulated CORS API).');
} finally {
  client?.close();
  globalThis.fetch = originalFetch;
  if (originalWindow === undefined) delete globalThis.window; else globalThis.window = originalWindow;
}
