// Exercise real Three geometry and PLY round trips without a GPU or browser install.
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
registerHooks({resolve(specifier,context,nextResolve) {
  if(specifier==='three')return {url:new URL('../vendor/three.module.js',import.meta.url).href,shortCircuit:true};
  return nextResolve(specifier,context);
}});
const THREE=await import('../vendor/three.module.js');
const {SpaceViewer}=await import('../viewer.js');
function makeViewer() {
  const viewer=Object.create(SpaceViewer.prototype);
  viewer.scene=new THREE.Scene();viewer.material=new THREE.PointsMaterial();
  viewer.material.uniforms={maxY:{value:0}};viewer.threshold=.1;
  viewer.fit=()=>{};viewer.onCount=count=>viewer.count=count;
  return viewer;
}
const viewer=makeViewer();
const positions=[], colors=[], confidence=[];
for(let i=0;i<900;i++) {
  const x=(i%30)/29*4-2,z=Math.floor(i/30)/29*4-2,r=Math.PI/6;
  // OpenCV down/forward: the floor has a 30-degree roll.
  positions.push(Math.cos(r)*x,-Math.sin(r)*x,-z);colors.push(.2,.5,.8);confidence.push(i===0?.05:.9);
}
const source=new Float32Array(positions), immutable=source.slice();
viewer.setData({positions:source,colors:new Float32Array(colors),confidence:new Float32Array(confidence)},{flip:true});
assert.equal(viewer.alignment.found,true);
assert.deepEqual(source,immutable,'setData never mutates caller coordinates');
assert.ok(viewer.cloud.geometry.boundingBox.max.y<.001,'rendered floor is level');
assert.equal(viewer.count,899,'confidence filtering remains intact');
const saved=await viewer.exportPLY().arrayBuffer();
const prefix=new TextDecoder().decode(saved.slice(0,300));
assert.ok(prefix.includes('comment SPACE coordinate_system Y_UP'),'export records corrected coordinate system');
const restored=makeViewer();
restored.parsePLY(saved);
assert.equal(restored.orientation.automatic,false,'saved alignment is not automatically applied twice');
assert.equal(restored.data.confidence.length,899);
for(let i=0;i<restored.data.positions.length;i++)assert.ok(Math.abs(restored.data.positions[i]-viewer.data.positions[i+3])<1e-6,'export and import preserve corrected coordinates');
viewer.setOrientation({automatic:false,roll:90,pitch:15});
const adjusted=viewer.data.positions.slice();
viewer.setOrientation({roll:-45});viewer.setOrientation({roll:90});
assert.deepEqual(viewer.data.positions,adjusted,'repeated adjustments have no accumulated drift');
const adjustedSaved=await viewer.exportPLY().arrayBuffer();
restored.parsePLY(adjustedSaved);
for(let i=0;i<restored.data.positions.length;i++)assert.ok(Math.abs(restored.data.positions[i]-adjusted[i+3])<1e-6,'manual orientation is saved to PLY too');
viewer.setOrientation({automatic:false,roll:0,pitch:0});
for(let i=0;i<source.length;i+=3) {
  assert.equal(viewer.data.positions[i],source[i]);
  assert.equal(viewer.data.positions[i+1],-source[i+1]);
  assert.equal(viewer.data.positions[i+2],-source[i+2]);
}
console.log('PASS viewer orientation: real geometry, unchanged source, filtered export, Y_UP round trip, manual export, drift-free reset');
