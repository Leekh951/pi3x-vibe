import assert from 'node:assert/strict';
import { estimateUp, composeOrientation, rotatePositions } from '../orientation.mjs';

const radians = degrees => degrees * Math.PI / 180;
// Independent analytic fixture: a floor, a larger wall, clutter, and distant outliers.
function tiltPoint([x,y,z], roll, pitch) {
  const r=radians(roll), p=radians(pitch);
  const Y=Math.cos(p)*y-Math.sin(p)*z, Z=Math.sin(p)*y+Math.cos(p)*z;
  return [Math.cos(r)*x-Math.sin(r)*Y, Math.sin(r)*x+Math.cos(r)*Y, Z];
}
function room(roll, pitch) {
  const positions=[], confidence=[];
  for(let i=0; i<1600; i++) {
    const x=(i%40)/39*4-2, z=Math.floor(i/40)/39*4-2;
    positions.push(...tiltPoint([x, .001*Math.sin(i), z], roll, pitch));confidence.push(.9);
  }
  for(let i=0; i<2400; i++) {
    const y=(i%40)/39*3, z=Math.floor(i/40)/59*4-2;
    positions.push(...tiltPoint([2,y,z],roll,pitch));confidence.push(.9);
  }
  for(let i=0; i<200; i++) {
    positions.push(...tiltPoint([Math.sin(i)*1.7, .5+((i*17)%31)/31, Math.cos(i)*1.7],roll,pitch));confidence.push(.7);
  }
  for(let i=0; i<16; i++) { positions.push(i*500, i*200, -i*800);confidence.push(.05); }
  return { positions:new Float32Array(positions), confidence:new Float32Array(confidence) };
}
for(const [roll,pitch] of [[28,15],[-32,-18],[0,0],[8,-24]]) {
  const data=room(roll,pitch), original=data.positions.slice();
  const estimate=estimateUp(data.positions,data.confidence);
  assert.equal(estimate.found,true,`detect floor despite larger wall (${roll}, ${pitch})`);
  const normal=tiltPoint([0,1,0],roll,pitch);
  const cosine=normal.reduce((sum,v,i)=>sum+v*estimate.normal[i],0);
  assert.ok(cosine>Math.cos(radians(1)),`floor normal within 1 degree: ${JSON.stringify(estimate)}`);
  const upright=rotatePositions(data.positions,composeOrientation(estimate.normal));
  const floorY=Array.from({length:1600},(_,i)=>upright[i*3+1]);
  assert.ok(Math.max(...floorY)-Math.min(...floorY)<.02,'floor becomes horizontal');
  assert.deepEqual(data.positions,original,'source data is preserved');
  const distance=(points,a,b)=>Math.hypot(...[0,1,2].map(axis=>points[a*3+axis]-points[b*3+axis]));
  assert.ok(Math.abs(distance(upright,12,980)-distance(original,12,980))<1e-5,'physical scale and shape are preserved');
}
const sideways=new Float32Array([[1,0,0], [0,1,0], [0,0,1]].flatMap(p=>tiltPoint(p,90,0)));
const manual=rotatePositions(sideways,composeOrientation([0,1,0],{automatic:false,roll:-90}));
assert.deepEqual(Array.from(manual).map(v=>Math.round(v)||0),[1,0,0,0,1,0,0,0,1],'manual rotation can recover a sideways result');
const roomData=room(28,15);
const reset=rotatePositions(roomData.positions,composeOrientation([0,1,0],{automatic:false}));
assert.deepEqual(reset,roomData.positions,'original orientation can be restored exactly');
const wall=[];
for(let i=0;i<1600;i++)wall.push(0,(i%40)/39,Math.floor(i/40)/39);
assert.equal(estimateUp(new Float32Array(wall)).found,false,'vertical wall alone is not treated as floor');
assert.equal(estimateUp(roomData.positions,new Float32Array(roomData.confidence.length)).found,false,'uncertain points do not determine orientation');
assert.equal(estimateUp(new Float32Array(300)).found,false,'degenerate point cloud is left unchanged');
const sphere=[];
for(let i=0;i<2400;i++) {
  const y=1-2*(i+.5)/2400, r=Math.sqrt(1-y*y), angle=i*Math.PI*(3-Math.sqrt(5));
  sphere.push(r*Math.cos(angle),y,r*Math.sin(angle));
}
assert.equal(estimateUp(new Float32Array(sphere)).found,false,'nonplanar data is left for manual adjustment');
console.log('PASS upright orientation: tilted floors, dominant walls, outliers, manual rotation, scale, reset, ambiguous geometry');
