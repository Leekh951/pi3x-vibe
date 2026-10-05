// Manual verification using the same shipped client and submit API as the page.
import { File, Blob } from 'node:buffer';
import { writeFile } from 'node:fs/promises';
import { uploadImages } from '../gpu-upload.mjs';
import { watchGPUJob } from '../gpu-job.mjs';
globalThis.File = File; globalThis.Blob = Blob;
globalThis.window = { WebSocket: class {}, location: { search: '', hostname: 'leekh951.github.io' } };
globalThis.window.parent = globalThis.window;
globalThis.document = {};
const { Client } = await import('../vendor/gradio-client.js');
const endpoint = 'https://leekh951-pi3x-vibe.hf.space';
const revision = '9fa3ddb3f8d53041f8b2738df404f62223bbaa7b';
let client, job, completed = false, timer;
const started = Date.now();
try {
  client = await Client.connect(endpoint, { events: ['data', 'status'], headers: { Origin: 'https://leekh951.github.io' } });
  const images = [];
  for (let index = 0; index < 3; index++) {
    const response = await fetch(`https://raw.githubusercontent.com/yyfz/Pi3/${revision}/examples/room/rgb/${index}.png`);
    if (!response.ok) throw Error('Sample download failed');
    images.push(new File([await response.arrayBuffer()], `${index}.png`, { type: 'image/png' }));
  }
  const uploaded = await uploadImages(client, endpoint, images);
  job = client.submit('/reconstruct', { images: uploaded, quality: 'fast' });
  const result = (async () => {
    let output;
    for await (const message of watchGPUJob(job)) {
      console.log(Math.round((Date.now() - started) / 1000) + 's', JSON.stringify(message));
      if (message.type === 'status' && message.stage === 'error') throw Error(message.message || 'GPU request failed');
      if (message.type === 'data') output = message.data;
    }
    if (!output?.[0]?.path || output[1]?.engine !== 'Pi3X') throw Error('Missing Pi3X result');
    const file = await fetch(endpoint + '/gradio_api/file=' + encodeURIComponent(output[0].path));
    if (!file.ok) throw Error('Result download failed');
    const bytes = Buffer.from(await file.arrayBuffer());
    const headerEnd = bytes.indexOf('end_header\n') + 'end_header\n'.length;
    const count = Number(bytes.subarray(0, headerEnd).toString().match(/element vertex (\d+)/)?.[1]);
    if (!(count > 0) || bytes.length - headerEnd !== count * 19 || output[1].point_count !== count) throw Error('Invalid PLY result');
    await writeFile('/tmp/pi3x-js-result.ply', bytes);
    completed = true;
    console.log('PASS actual shipped JS submit → GPU → PLY:', JSON.stringify(output[1]));
  })();
  await Promise.race([result, new Promise((_, reject) => { timer = setTimeout(() => reject(Error('JS GPU request stalled for 5 minutes')), 300000); })]);
} finally {
  clearTimeout(timer);
  if (!completed) await job?.cancel().catch(() => {});
  client?.close();
}
