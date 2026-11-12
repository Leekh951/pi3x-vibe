import { runWithFailover, isQuotaError, quotaExhausted, rememberQuotaExhausted } from '../gpu-failover.mjs';

let checks = 0;
const check = (condition, message) => { if (!condition) throw Error(message); checks++; };
const target = (name, connect, extra = {}) => ({ name, connect, ...extra });
const ok = name => async () => ({ name });
const fail = message => async () => { throw Error(message); };

// Space works: home is never touched.
let homeConnects = 0;
let outcome = await runWithFailover([target('space', ok('space')), target('home', async () => { homeConnects++; return {}; })],
  async connection => `done on ${connection.name}`);
check(outcome.result === 'done on space' && outcome.target.name === 'space' && homeConnects === 0, 'Space first');

// ZeroGPU quota error during the job: the same job runs on home, and the switch is reported.
const switches = [], failures = [];
outcome = await runWithFailover([target('space', ok('space')), target('home', ok('home'))], async connection => {
  if (connection.name === 'space') throw Error('You have exceeded your GPU quota (40s requested vs. 12s left).');
  return 'home result';
}, { onSwitch: (from, to, error) => switches.push([from.name, to.name, isQuotaError(error.message)]),
     onFailure: (server, error, stage) => failures.push([server.name, stage]) });
check(outcome.result === 'home result' && outcome.target.name === 'home', 'Quota falls back to home');
check(JSON.stringify(switches) === '[["space","home",true]]' && JSON.stringify(failures) === '[["space","run"]]', 'Switch reported once');

// Sleeping Space that does not connect in time: home takes over after connectTimeout.
const started = Date.now();
outcome = await runWithFailover([target('space', () => new Promise(() => {}), { connectTimeout: 30 }), target('home', ok('home'))],
  async connection => connection.name);
check(outcome.result === 'home' && Date.now() - started < 1000, 'Slow Space times out to home');

// Skipped Space (quota remembered): straight to home.
let spaceConnects = 0;
outcome = await runWithFailover([target('space', async () => { spaceConnects++; return {}; }, { skip: () => true }), target('home', ok('home'))],
  async connection => connection.name);
check(outcome.result === 'home' && spaceConnects === 0, 'Remembered quota skips Space');

// Home down: the Space alone still serves the job.
outcome = await runWithFailover([target('space', ok('space')), target('home', fail('home offline'))], async connection => connection.name);
check(outcome.result === 'space', 'Space serves when home is off');

// Cancelled by the visitor: never moves to another server.
let homeRuns = 0;
try {
  await runWithFailover([target('space', ok('space')), target('home', ok('home'))], async connection => {
    if (connection.name === 'home') homeRuns++;
    throw Object.assign(Error('cancelled'), { name: 'AbortError' });
  });
  check(false, 'Abort must throw');
} catch (error) { check(error.name === 'AbortError' && homeRuns === 0, 'Abort does not fail over'); }

// Both down: the last server's error is reported.
try { await runWithFailover([target('space', fail('quota exceeded')), target('home', fail('home offline'))], async () => 'x'); check(false, 'Must throw'); }
catch (error) { check(error.message === 'home offline', 'Last error reported'); }

// The last server waits as long as it needs (no connectTimeout cut-off).
outcome = await runWithFailover([target('home', () => new Promise(r => setTimeout(() => r({ name: 'home' }), 60)), { connectTimeout: 10 })],
  async connection => connection.name);
check(outcome.result === 'home', 'Last server not cut off');

check(isQuotaError('You have exceeded your GPU quota') && isQuotaError('ZeroGPU daily GPU limit') && !isQuotaError('GPU 메모리가 부족합니다.'), 'Quota detection');

// Quota memory lasts until local midnight and tolerates missing storage.
const store = new Map(); const storage = { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) };
const noon = new Date(2026, 10, 12, 12, 0, 0);
check(!quotaExhausted(storage, noon.getTime()), 'No quota memory initially');
rememberQuotaExhausted(storage, noon);
check(quotaExhausted(storage, new Date(2026, 10, 12, 23, 59).getTime()), 'Remembered for the rest of the day');
check(!quotaExhausted(storage, new Date(2026, 10, 13, 0, 1).getTime()), 'Cleared after midnight');
const broken = { getItem() { throw Error('blocked'); }, setItem() { throw Error('blocked'); } };
rememberQuotaExhausted(broken); check(!quotaExhausted(broken) && !quotaExhausted(null), 'Blocked storage is harmless');

console.log(`failover: ${checks} checks passed`);
