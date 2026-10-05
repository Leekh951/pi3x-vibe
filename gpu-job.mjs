export function jobProgress(message, previous = {}) {
  const description = message.progress_data?.find(item => item.desc)?.desc;
  const started = previous.started || message.original_msg === 'process_starts' || !!description ||
    ['generating', 'streaming', 'complete'].includes(message.stage);
  if (description) return { started, phase: 'processing', label: '공간을 이어주는 중', detail: description };
  if (started && previous.phase === 'processing') return previous;
  if (started) return { started, phase: 'preparing', label: 'GPU를 준비하는 중',
    detail: '처리 요청이 시작됐어요. GPU 배정과 사진 준비를 기다리고 있어요.' };
  return { started: false, phase: 'queued', label: '처리 순서를 기다리는 중',
    detail: message.position != null ? `서버 대기 순서 ${message.position + 1}번째 · GPU 배정 시간은 별도예요.` : '무료 공용 GPU는 혼잡하면 배정에 시간이 걸릴 수 있어요.' };
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
      yield next.value;
    }
  } finally {
    clearTimeout(timer); signal?.removeEventListener('abort', abort);
    if (!completed) {
      try { Promise.resolve(job.cancel?.()).catch(() => {}); } catch {}
      try { Promise.resolve(job.return?.()).catch(() => {}); } catch {}
    }
  }
}
