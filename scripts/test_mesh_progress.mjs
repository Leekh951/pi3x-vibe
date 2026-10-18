import assert from 'node:assert/strict';
import { meshJobProgress,elapsedLabel,waitForMesh,meshResultURL } from '../mesh-progress.mjs';

const queued=meshJobProgress({stage:'pending',position:2});
assert.match(queued.detail,/3번째/);
const started=meshJobProgress({stage:'pending',original_msg:'process_starts'},queued);
assert.equal(started.started,true);
assert.doesNotMatch(started.label,/GPU/,'CPU mesh work must not be labeled as GPU preparation');
const active=meshJobProgress({progress_data:[{desc:'메시 생성',progress:.5},{desc:'UV 생성',progress:.6}]},started);
assert.equal(active.label,'UV 생성','Show the most recent nested progress description');
assert.equal(active.percent,60);
assert.deepEqual(meshJobProgress({stage:'pending',position:0},active),active,'Late queue estimates must not hide active processing');
assert.equal(meshJobProgress({progress_data:[{desc:'포즈 복원'}]}).percent,null,'Unknown work must remain indeterminate');
assert.equal(meshJobProgress({progress_data:[{desc:'UV',progress:12}]}).percent,null,'Do not turn invalid fractions into a fake percentage');
assert.equal(elapsedLabel(125900),'2분 5초');

const never=()=>new Promise(()=>{});
await assert.rejects(waitForMesh(never,{timeout:10,message:'연결 시간 초과'}),{name:'TimeoutError',message:'연결 시간 초과'});
const controller=new AbortController();
const canceled=waitForMesh(never,{signal:controller.signal,timeout:100});controller.abort();
await assert.rejects(canceled,{name:'AbortError'});
let called=false;
await assert.rejects(waitForMesh(()=>{called=true;},{signal:controller.signal}),{name:'AbortError'});
assert.equal(called,false,'An already canceled action must not start an upload or prediction');
let resolve,closed=false;
await assert.rejects(waitForMesh(()=>new Promise(done=>{resolve=done;}),{timeout:10,onLateValue:client=>client.close()}),{name:'TimeoutError'});
resolve({close(){closed=true;}});await Promise.resolve();await Promise.resolve();
assert.equal(closed,true,'A late connection is closed after its wait has ended');

const endpoint='https://leekh951-pi3x-mesh.hf.space';
assert.equal(meshResultURL({path:'/tmp/posed-images.zip'},endpoint),endpoint+'/gradio_api/file=%2Ftmp%2Fposed-images.zip');
assert.equal(new URL(meshResultURL({url:'https://other.example/private',path:'/tmp/result.glb'},endpoint)).origin,endpoint);
assert.throws(()=>meshResultURL({url:'https://other.example/private'},endpoint));
console.log('Mesh progress, indefinite waits, cancellation, late connections and result download links passed.');
