// Estimate a ground-like plane from a bounded sample. Camera Y is only a prior:
// geometry alone cannot tell gravity from a wall, so manual adjustment stays available.
const IDENTITY = [0, 0, 0, 1];
const unit = v => { const length = Math.hypot(...v); return length > 1e-12 ? v.map(x => x / length) : null; };

export function estimateUp(positions, confidence) {
  const count = positions.length / 3, sample = [];
  const limit = Math.min(count, 4096);
  for (let i = 0; i < limit; i++) {
    const index = Math.floor(i * count / limit), offset = index * 3;
    const point = [positions[offset], positions[offset + 1], positions[offset + 2]];
    if (point.every(Number.isFinite) && (!confidence || confidence[index] >= .15)) sample.push(point);
  }
  if (sample.length < 80) return { normal: [0, 1, 0], found: false };
  // Percentile bounds keep isolated faraway points from inflating the plane tolerance.
  let diagonalSquared = 0;
  for (let axis = 0; axis < 3; axis++) {
    const values = sample.map(p => p[axis]).sort((a, b) => a - b);
    const span = values[Math.floor(values.length * .98)] - values[Math.floor(values.length * .02)];
    diagonalSquared += span * span;
  }
  const tolerance = Math.sqrt(diagonalSquared) * .0075;
  if (tolerance < 1e-10) return { normal: [0, 1, 0], found: false };
  let seed = 951, best = null;
  const randomIndex = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed % sample.length; };
  for (let trial = 0; trial < 768; trial++) {
    const a = sample[randomIndex()];
    let b, c;
    if (trial % 2) { b = sample[randomIndex()]; c = sample[randomIndex()]; }
    else {
      // Local triangles find smaller floor patches even when walls dominate the scene.
      let first = Infinity, second = Infinity;
      for (let j = 0; j < 32; j++) {
        const p = sample[randomIndex()];
        const distance = (p[0]-a[0])**2 + (p[1]-a[1])**2 + (p[2]-a[2])**2;
        if (distance < tolerance * tolerance) continue;
        if (distance < first) { second = first; c = b; first = distance; b = p; }
        else if (distance < second) { second = distance; c = p; }
      }
    }
    if (!b || !c) continue;
    const ab = b.map((v, i) => v-a[i]), ac = c.map((v, i) => v-a[i]);
    let normal = unit([ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0]]);
    if (!normal) continue;
    if (normal[1] < 0) normal = normal.map(v => -v);
    if (normal[1] < .57) continue; // Avoid turning a clearly vertical wall into the floor.
    const offset = normal.reduce((sum, v, i) => sum + v*a[i], 0);
    let support = 0;
    for (const p of sample) if (Math.abs(normal[0]*p[0]+normal[1]*p[1]+normal[2]*p[2]-offset) < tolerance) support++;
    if (support < Math.max(64, sample.length * .08)) continue;
    const score = support * normal[1]**3;
    if (!best || score > best.score) best = { normal, offset, support, score };
  }
  if (!best) return { normal: [0, 1, 0], found: false };
  const inliers = sample.filter(p => Math.abs(best.normal[0]*p[0]+best.normal[1]*p[1]+best.normal[2]*p[2]-best.offset) < tolerance);
  const mean = [0, 0, 0];
  for (const p of inliers) for (let axis = 0; axis < 3; axis++) mean[axis] += p[axis] / inliers.length;
  let xx=0, zz=0, xz=0, xy=0, zy=0;
  for (const p of inliers) {
    const x=p[0]-mean[0], y=p[1]-mean[1], z=p[2]-mean[2];
    xx+=x*x; zz+=z*z; xz+=x*z; xy+=x*y; zy+=z*y;
  }
  const determinant = xx*zz-xz*xz;
  if (determinant > (xx+zz)**2 * 1e-8) {
    const refined = unit([-(xy*zz-zy*xz)/determinant, 1, -(zy*xx-xy*xz)/determinant]);
    if (refined && refined[1] >= .57) best.normal = refined;
  }
  return { normal: best.normal, found: true, support: best.support / sample.length };
}

export function rotationForUp(normal) {
  // Quaternion rotating the plane's upward normal to world +Y.
  const q = unit([-normal[2], 0, normal[0], 1+normal[1]]);
  return q || [...IDENTITY];
}

function multiply(a, b) {
  const [x,y,z,w] = a, [X,Y,Z,W] = b;
  return [w*X+x*W+y*Z-z*Y, w*Y-x*Z+y*W+z*X, w*Z+x*Y-y*X+z*W, w*W-x*X-y*Y-z*Z];
}

export function composeOrientation(normal, { automatic = true, roll = 0, pitch = 0 } = {}) {
  const r=roll*Math.PI/360, p=pitch*Math.PI/360;
  return multiply([0, 0, Math.sin(r), Math.cos(r)], multiply([Math.sin(p), 0, 0, Math.cos(p)], automatic ? rotationForUp(normal) : IDENTITY));
}

export function rotatePositions(positions, quaternion) {
  const [x,y,z,w] = quaternion;
  if(x===0 && y===0 && z===0 && Math.abs(w)===1)return positions.slice();
  const matrix = [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w),
    2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w),
    2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)];
  const rotated = new Float32Array(positions.length);
  for (let i=0; i<positions.length; i+=3) {
    const X=positions[i], Y=positions[i+1], Z=positions[i+2];
    rotated[i]=matrix[0]*X+matrix[1]*Y+matrix[2]*Z;
    rotated[i+1]=matrix[3]*X+matrix[4]*Y+matrix[5]*Z;
    rotated[i+2]=matrix[6]*X+matrix[7]*Y+matrix[8]*Z;
  }
  return rotated;
}
