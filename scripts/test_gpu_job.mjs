import { jobProgress, watchGPUJob } from '../gpu-job.mjs';
const assert = (value, description) => { if (!value) throw Error(description); };
const queued = jobProgress({ stage: 'pending', position: 0 });
assert(queued.phase === 'queued' && queued.detail.includes('1번째'), 'Show server queue before handler starts');
const started = jobProgress({ stage: 'pending', position: 0, original_msg: 'process_starts' }, queued);
assert(started.phase === 'preparing' && !started.label.includes('순서'), 'Gradio pending process_starts is GPU preparation, not first place in queue');
const active = jobProgress({ stage: 'pending', progress_data: [{ desc: 'Pi3X 추론 중' }] }, started);
assert(active.phase === 'processing' && active.detail === 'Pi3X 추론 중', 'Forward real model progress');
assert(jobProgress({ stage: 'pending', position: 0 }, active).phase === 'processing', 'Late estimation must not return to queue label');

async function* successful() { yield { type: 'status' }; yield { type: 'data', data: ['result.ply'] }; }
const messages = [];
for await (const message of watchGPUJob(successful(), { timeout: 100 })) messages.push(message);
assert(messages.length === 2 && messages[1].data[0] === 'result.ply', 'Receive complete result');

function stalled() {
  return { canceled: 0, returned: 0, next: () => new Promise(() => {}),
    cancel() { this.canceled++; }, return() { this.returned++; return Promise.resolve({ done: true }); } };
}
const hanging = stalled();
try {
  for await (const message of watchGPUJob(hanging, { timeout: 10 })) throw Error('Unexpected message');
  throw Error('Stalled iterator should time out');
} catch (error) { assert(error.name === 'TimeoutError', 'Report bounded wait'); }
assert(hanging.canceled === 1 && hanging.returned === 1, 'Cancel and release stalled SDK iterator');

const canceled = stalled(), controller = new AbortController();
const iterator = watchGPUJob(canceled, { signal: controller.signal, timeout: 1000 });
const pending = iterator.next(); controller.abort();
try { await pending; throw Error('Cancellation should stop waiting'); }
catch (error) { assert(error.name === 'AbortError', 'Visitor cancellation stops a pending next()'); }
assert(canceled.canceled === 1 && canceled.returned === 1, 'Canceled request is released');

// The SDK's return() can itself remain pending after an error status. Forward
// the server error without awaiting that broken cleanup iterator indefinitely.
const failed = { next: async () => ({ done: false, value: { type: 'status', stage: 'error', message: 'Invalid file type' } }),
  cancel() {}, return: () => new Promise(() => {}) };
let errorTimer;
try {
  const observed = (async () => {
    for await (const message of watchGPUJob(failed)) {
      if (message.stage === 'error') throw Error(message.message);
    }
  })();
  await Promise.race([observed, new Promise((_, reject) => { errorTimer = setTimeout(() => reject(Error('Error cleanup hung')), 100); })]);
  throw Error('Expected the server error');
} catch (error) { assert(error.message === 'Invalid file type', 'Server error is shown even when SDK return() hangs'); }
finally { clearTimeout(errorTimer); }
console.log('GPU start/progress labels, result delivery, stalled stream timeout and visitor cancellation passed.');
