export function jobProgress(message, previous = {}) {
  const description = message.progress_data?.find(item => item.desc)?.desc;
  const started = previous.started || message.original_msg === 'process_starts' || !!description ||
    ['generating', 'streaming', 'complete'].includes(message.stage);
  if (description) return { started, phase: 'processing', label: '공간을 이어주는 중', detail: description };
  if (started && previous.phase === 'processing') return previous;
  if (started) return { started, phase: 'preparing', label: 'GPU를 준비하는 중',
    detail: '차례가 됐어요. 사진을 GPU로 불러오고 있어요.' };
  // Gradio's position counts the people waiting ahead (0 = next); eta is its estimate in seconds.
  const eta = Number.isFinite(message.eta) && message.eta > 0 ? ` · 예상 약 ${Math.ceil(message.eta)}초` : '';
  const ahead = message.position == null ? 'GPU가 앞선 요청을 처리하는 동안 기다리고 있어요.'
    : message.position === 0 ? '바로 다음 차례예요.' : `앞에 ${message.position}명이 기다리고 있어요.`;
  return { started: false, phase: 'queued', label: '대기열에서 차례를 기다리는 중', detail: ahead + eta };
}

// Gradio rejects a join with this message when its queue is at max_size.
export const isQueueFull = message => /currently busy|queue is full/i.test(message || '');

export function waitingRoomProgress(attempt, total) {
  return { started: false, phase: 'waiting-room', label: '이용자가 많아 자리를 기다리는 중',
    detail: `대기열이 가득 찼어요. 자리가 나면 자동으로 들어가요 · ${attempt}/${total}번째 시도` };
}

const abortError = () => {
  const error = new Error('작업 대기를 취소했어요. 사진은 그대로 유지됩니다.');
  error.name = 'AbortError'; return error;
};
const pause = (ms, signal) => new Promise((resolve, reject) => {
  if (signal?.aborted) return reject(abortError());
  const timer = setTimeout(() => { signal?.removeEventListener('abort', stop); resolve(); }, ms);
  const stop = () => { clearTimeout(timer); reject(abortError()); };
  signal?.addEventListener('abort', stop, { once: true });
});

// Submit once, and while the server's queue is full keep the uploaded photos and
// rejoin every retryDelay ms (up to retries times) instead of failing the visitor.
export async function runGPUJob(submit, { signal, onStatus = () => {}, onWaitingRoom = () => {},
  retries = 24, retryDelay = 5000, timeout } = {}) {
  for (let attempt = 1; ; attempt++) {
    try {
      let output;
      for await (const message of watchGPUJob(submit(), { signal, timeout })) {
        if (message.type === 'data') output = message.data;
        if (message.type === 'status') {
          if (message.stage === 'error') throw Error(message.message || '공간을 만들지 못했어요. 다시 시도해주세요.');
          onStatus(message);
        }
      }
      return output;
    } catch (error) {
      if (error.name === 'AbortError' || !isQueueFull(error.message) || attempt > retries) throw error;
      onWaitingRoom(attempt, retries);
      await pause(retryDelay, signal);
    }
  }
}

// The SDK iterator can remain pending if a progress stream stops responding.
// Give the visitor a way to cancel and a bounded wait, keeping their photos.
export async function* watchGPUJob(job, { signal, timeout = 300000 } = {}) {
  let rejectStop, timer, completed = false;
  const stop = new Promise((_, reject) => { rejectStop = reject; });
  const abort = () => {
    const error = new Error('작업 대기를 취소했어요. 사진은 그대로 유지됩니다.');
    error.name = 'AbortError'; rejectStop(error);
  };
  timer = setTimeout(() => {
    const error = new Error('5분 안에 결과를 받지 못했어요. 잠시 후 다시 시도해주세요.');
    error.name = 'TimeoutError'; rejectStop(error);
  }, timeout);
  signal?.addEventListener('abort', abort, { once: true });
  if (signal?.aborted) abort();
  try {
    while (true) {
      const next = await Promise.race([job.next(), stop]);
      if (next.done) { completed = true; break; }
      // This SDK can send a final status and then leave next() pending. Finish
      // on its explicit terminal event so a valid PLY is displayed immediately.
      if (next.value?.type === 'status' && next.value.stage === 'complete') {
        completed = true; yield next.value; return;
      }
      yield next.value;
      if (next.value?.type === 'status' && next.value.stage === 'error') return;
    }
  } finally {
    clearTimeout(timer); signal?.removeEventListener('abort', abort);
    if (!completed) {
      try { Promise.resolve(job.cancel?.()).catch(() => {}); } catch {}
      try { Promise.resolve(job.return?.()).catch(() => {}); } catch {}
    }
  }
}
