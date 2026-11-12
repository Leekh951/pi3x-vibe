// Run a job on the first GPU server that works: the free Hugging Face ZeroGPU Space first,
// then the operator's own GPU. A visitor whose ZeroGPU quota ran out skips the Space until midnight.
export const isQuotaError = message => /quota|daily.*GPU|GPU.*budget/i.test(message || '');

const QUOTA_KEY = 'pi3x-zerogpu-quota-until';
const storage = () => { try { return globalThis.localStorage ?? null; } catch { return null; } };

export function quotaExhausted(store = storage(), now = Date.now()) {
  try { return Number(store?.getItem(QUOTA_KEY)) > now; } catch { return false; }
}

export function rememberQuotaExhausted(store = storage(), now = new Date()) {
  const midnight = new Date(now); midnight.setHours(24, 0, 0, 0);
  try { store?.setItem(QUOTA_KEY, String(midnight.getTime())); } catch {}
}

const withinTime = (promise, ms) => !ms ? promise : new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(Object.assign(Error('서버가 제때 준비되지 않았어요.'), { name: 'ConnectTimeout' })), ms);
  promise.then(value => { clearTimeout(timer); resolve(value); }, error => { clearTimeout(timer); reject(error); });
});

// targets: [{ name, connect(): Promise<connection>, connectTimeout?, skip?(): boolean }]
// run(connection, target) does one full attempt (upload, inference, download).
// A cancelled job never moves on; any other failure tries the next server, and the
// last server's error is the one reported.
export async function runWithFailover(targets, run, { onSwitch = () => {}, onFailure = () => {} } = {}) {
  const usable = targets.filter(target => !target.skip?.());
  let lastError = null;
  for (const [index, target] of usable.entries()) {
    const next = usable[index + 1];
    let connection;
    try { connection = await withinTime(target.connect(), next ? target.connectTimeout : 0); }
    catch (error) {
      lastError = error; onFailure(target, error, 'connect');
      if (next) { onSwitch(target, next, error); continue; }
      throw error;
    }
    try { return { result: await run(connection, target), target }; }
    catch (error) {
      if (error?.name === 'AbortError') throw error;
      lastError = error; onFailure(target, error, 'run');
      if (next) { onSwitch(target, next, error); continue; }
      throw error;
    }
  }
  throw lastError ?? Error('사용할 수 있는 GPU 서버가 없어요.');
}
