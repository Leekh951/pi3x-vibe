import { jobProgress, watchGPUJob, runGPUJob, isQueueFull, waitingRoomProgress } from '../gpu-job.mjs';
const assert = (value, description) => { if (!value) throw Error(description); };
const queued = jobProgress({ stage: 'pending', position: 0 });
assert(queued.phase === 'queued' && queued.detail.startsWith('바로 다음 차례'), 'Position 0 means next in line');
assert(jobProgress({ stage: 'pending', position: 3, eta: 7.2 }).detail === '앞에 3명이 기다리고 있어요. · 예상 약 8초', 'Show people ahead and the estimate');
assert(!jobProgress({ stage: 'pending', position: 2, eta: null }).detail.includes('예상'), 'No estimate before the server has timing history');
const started = jobProgress({ stage: 'pending', position: 0, original_msg: 'process_starts' }, queued);
assert(started.phase === 'preparing' && !started.label.includes('순서'), 'Gradio pending process_starts is GPU preparation, not first place in queue');
const active = jobProgress({ stage: 'pending', progress_data: [{ desc: 'Pi3X 추론 중' }] }, started);
assert(active.phase === 'processing' && active.detail === 'Pi3X 추론 중', 'Forward real model progress');
assert(jobProgress({ stage: 'pending', position: 0 }, active).phase === 'processing', 'Late estimation must not return to queue label');

async function* successful() { yield { type: 'status' }; yield { type: 'data', data: ['result.ply'] }; }
const messages = [];
for await (const message of watchGPUJob(successful(), { timeout: 100 })) messages.push(message);
assert(messages.length === 2 && messages[1].data[0] === 'result.ply', 'Receive complete result');

let terminalIndex = 0;
const terminal = { next: async () => {
  if (terminalIndex++ === 0) return { done: false, value: { type: 'data', data: ['cloud.ply'] } };
  if (terminalIndex === 2) return { done: false, value: { type: 'status', stage: 'complete' } };
  return new Promise(() => {});
} };
const terminalMessages = [];
for await (const message of watchGPUJob(terminal, { timeout: 100 })) terminalMessages.push(message);
assert(terminalMessages.length === 2 && terminalIndex === 2, 'Stop on successful final status even if SDK never resolves next() again');

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

// Waiting room: a full queue is retried with the same upload, not shown as a failure.
assert(isQueueFull('This application is currently busy. Please try again. ') && !isQueueFull('Invalid file type'), 'Recognize Gradio queue-full rejection');
const busyThenOk = () => { let calls = 0; const submit = () => { calls++;
  const value = calls < 3 ? { type: 'status', stage: 'error', message: 'This application is currently busy. Please try again. ' } : { type: 'data', data: ['room.ply'] };
  let sent = false; return { next: async () => sent ? { done: true } : (sent = true, { done: false, value }), cancel() {}, return: async () => ({ done: true }) }; };
  return { submit, calls: () => calls }; };
const flaky = busyThenOk(), rooms = [];
const result = await runGPUJob(flaky.submit, { retryDelay: 1, retries: 5, onWaitingRoom: (attempt, total) => rooms.push(waitingRoomProgress(attempt, total).detail) });
assert(result[0] === 'room.ply' && flaky.calls() === 3 && rooms.length === 2 && rooms[1].includes('2/5'), 'Rejoin after queue-full and report attempts');
const exhausted = busyThenOk(); let gaveUp = false;
try { await runGPUJob(exhausted.submit, { retryDelay: 1, retries: 1 }); }
catch (error) { gaveUp = isQueueFull(error.message); }
assert(gaveUp && exhausted.calls() === 2, 'Give up after the retry budget with the queue-full reason');
const stopWaiting = new AbortController(), busyAlways = { next: async () => ({ done: false, value: { type: 'status', stage: 'error', message: 'This application is currently busy.' } }), cancel() {}, return: async () => ({ done: true }) };
const waiting = runGPUJob(() => ({ ...busyAlways }), { signal: stopWaiting.signal, retryDelay: 10000 });
setTimeout(() => stopWaiting.abort(), 20);
try { await waiting; throw Error('should abort'); } catch (error) { assert(error.name === 'AbortError', 'Cancel stops the waiting room immediately'); }
const invalid = runGPUJob(() => ({ next: async () => ({ done: false, value: { type: 'status', stage: 'error', message: 'Invalid file type' } }), cancel() {}, return: async () => ({ done: true }) }), { retryDelay: 1 });
try { await invalid; throw Error('should fail'); } catch (error) { assert(error.message === 'Invalid file type', 'Other server errors are not retried'); }
console.log('PASS queue position, estimate, waiting room retry, cancel and non-retryable errors');
