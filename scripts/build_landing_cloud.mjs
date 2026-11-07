// Pack a real Pi3X PLY into the landing page's hero cloud (landing-cloud.bin).
// Usage: node scripts/build_landing_cloud.mjs <reconstruction.ply> [points=80000] [floor normal "x,y,z"]
// Pass the floor normal (Y-up viewer space) when automatic levelling picks a wall: Pi3X output
// frames need not keep camera Y up. The shipped hero used the RANSAC floor of photo 1's bottom rows.
// Uses the viewer's own orientation code so the hero is levelled like the studio.
import { readFileSync, writeFileSync } from 'node:fs';
import { estimateUp, composeOrientation, rotatePositions } from '../orientation.mjs';

const [source, limitArg, normalArg] = process.argv.slice(2);
const limit = Number(limitArg || 80000), MIN_CONFIDENCE = .3;
const raw = readFileSync(source), end = raw.indexOf('end_header\n') + 11;
const header = raw.subarray(0, end).toString();
if (!header.includes('property float confidence')) throw Error('Expected a Pi3X SPACE PLY');
const count = Number(/element vertex (\d+)/.exec(header)[1]), stride = 19;
const view = new DataView(raw.buffer, raw.byteOffset + end);
const positions = new Float32Array(count * 3), colors = new Uint8Array(count * 3), confidence = new Float32Array(count);
for (let i = 0; i < count; i++) {
  const o = i * stride;
  // OpenCV camera space -> Y up, as viewer.js does before estimating the floor.
  positions[i*3] = view.getFloat32(o, true); positions[i*3+1] = -view.getFloat32(o+4, true); positions[i*3+2] = -view.getFloat32(o+8, true);
  colors.set(raw.subarray(end + o + 12, end + o + 15), i * 3);
  confidence[i] = view.getFloat32(o + 15, true);
}
const normal = normalArg ? normalArg.split(',').map(Number) : estimateUp(positions, confidence).normal;
const levelled = rotatePositions(positions, composeOrientation(normal));

const kept = [];
for (let i = 0; i < count; i++) if (confidence[i] >= MIN_CONFIDENCE) kept.push(i);
let seed = 7; const random = () => (seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 2 ** 32;
for (let i = kept.length - 1; i > 0; i--) { const j = Math.floor(random() * (i + 1)); [kept[i], kept[j]] = [kept[j], kept[i]]; }
const chosen = kept.slice(0, Math.min(limit, kept.length));

// Centre on the median footprint, rest the 2nd-percentile floor at y=0, scale to unit radius.
const axis = a => chosen.map(i => levelled[i*3+a]).sort((x, y) => x - y);
const pick = (values, q) => values[Math.floor(values.length * q)];
const xs = axis(0), ys = axis(1), zs = axis(2);
const centre = [pick(xs, .5), pick(ys, .02), pick(zs, .5)];
const radius = Math.max(pick(xs, .98) - centre[0], centre[0] - pick(xs, .02), pick(ys, .98) - centre[1],
  pick(zs, .98) - centre[2], centre[2] - pick(zs, .02));

const out = Buffer.alloc(8 + chosen.length * 9); // 'P3C1', count, int16 xyz[], uint8 rgb[]
out.write('P3C1', 0); out.writeUInt32LE(chosen.length, 4);
chosen.forEach((index, n) => {
  for (let a = 0; a < 3; a++) {
    const v = Math.max(-1, Math.min(1, (levelled[index*3+a] - centre[a]) / radius));
    out.writeInt16LE(Math.round(v * 32767), 8 + n * 6 + a * 2);
  }
  out.set(colors.subarray(index * 3, index * 3 + 3), 8 + chosen.length * 6 + n * 3);
});
writeFileSync(new URL('../landing-cloud.bin', import.meta.url), out);
console.log(`landing-cloud.bin: ${chosen.length} of ${count} points (confidence >= ${MIN_CONFIDENCE}), ${out.length} bytes`);
