// Landing overlay: a real Pi3X reconstruction assembles in the hero, "들어가기" reveals the studio.
// The studio stays mounted underneath, so its viewer sizes and server warm-up are unaffected.
import * as THREE from 'three';

const landing = document.getElementById('landing');
const root = document.documentElement;
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const directVisit = () => location.hash === '#studio' || root.classList.contains('studio-direct');
let hero = null;

function setBackgroundInert(value) {
  for (const element of document.body.children) {
    if (element !== landing && element.tagName !== 'SCRIPT') element.inert = value;
  }
}

function showLanding() {
  landing.hidden = false; landing.classList.remove('is-leaving');
  document.body.classList.add('landing-open'); setBackgroundInert(true);
  hero ??= startHero(); hero?.resume();
}

function enterStudio({ push = true } = {}) {
  if (push && location.hash !== '#studio') history.pushState({ studio: true }, '', '#studio');
  hero?.pause(); setBackgroundInert(false); document.body.classList.remove('landing-open');
  const done = () => { landing.hidden = true; landing.classList.remove('is-leaving'); };
  if (reduceMotion || landing.hidden) done();
  else { landing.classList.add('is-leaving'); setTimeout(done, 460); }
  const heading = document.querySelector('.sidebar-heading h1');
  if (heading) { heading.tabIndex = -1; heading.focus({ preventScroll: true }); }
  window.scrollTo(0, 0);
}

for (const button of landing.querySelectorAll('[data-enter]')) button.addEventListener('click', () => enterStudio());
addEventListener('popstate', () => {
  if (location.hash === '#studio') enterStudio({ push: false });
  else if (!new URLSearchParams(location.search).has('colab')) { root.classList.remove('studio-direct'); showLanding(); landing.scrollTo(0, 0); }
});
addEventListener('keydown', event => {
  if (event.key === 'Enter' && !landing.hidden && event.target === document.body) enterStudio();
});

if (directVisit()) { landing.hidden = true; } else showLanding();

// Fade sections in as they scroll into view.
const revealer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
  for (const entry of entries) if (entry.isIntersecting) { entry.target.classList.add('is-visible'); revealer.unobserve(entry.target); }
}, { root: landing, threshold: .15 }) : null;
for (const element of landing.querySelectorAll('.lp-reveal')) revealer ? revealer.observe(element) : element.classList.add('is-visible');

function startHero() {
  const canvas = document.getElementById('lp-canvas');
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: true, powerPreference: 'high-performance' }); }
  catch { canvas.hidden = true; return null; }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, .01, 50);
  const group = new THREE.Group(); scene.add(group);
  const target = new THREE.Vector3(0, .1, 0);

  const grid = new THREE.GridHelper(3.2, 32, 0xbaff6c, 0xbaff6c);
  grid.material.transparent = true; grid.material.opacity = .07; grid.position.y = -.005; group.add(grid);

  const uniforms = { uProgress: { value: reduceMotion ? 1 : 0 }, uSize: { value: 2.1 * renderer.getPixelRatio() }, uScale: { value: 1 } };
  const material = new THREE.ShaderMaterial({
    uniforms, transparent: true, depthWrite: false,
    vertexShader: `
      attribute vec3 color; attribute vec3 scatter; attribute float delay;
      uniform float uProgress, uSize, uScale; varying vec3 vColor; varying float vFade;
      void main() {
        float t = clamp((uProgress - delay * .55) / .45, 0., 1.);
        t = 1. - pow(1. - t, 3.);
        vec3 p = mix(scatter, position, t);
        vec4 mv = modelViewMatrix * vec4(p, 1.);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = uSize * uScale / -mv.z;
        vColor = mix(vec3(.73, 1., .42), color, smoothstep(.55, 1., t));
        vFade = .35 + .65 * t;
      }`,
    fragmentShader: `
      varying vec3 vColor; varying float vFade;
      void main() {
        vec2 c = gl_PointCoord - .5; float d = dot(c, c);
        if (d > .25) discard;
        gl_FragColor = vec4(vColor, vFade * smoothstep(.25, .12, d));
      }`,
  });

  fetch(new URL('./landing-cloud.bin', import.meta.url)).then(r => { if (!r.ok) throw Error(r.status); return r.arrayBuffer(); }).then(buffer => {
    const view = new DataView(buffer);
    if (new TextDecoder().decode(buffer.slice(0, 4)) !== 'P3C1') throw Error('Unknown hero cloud');
    const count = view.getUint32(4, true);
    const quantized = new Int16Array(buffer, 8, count * 3), positions = new Float32Array(count * 3);
    for (let i = 0; i < positions.length; i++) positions[i] = quantized[i] / 32767;
    const colors = new Uint8Array(buffer, 8 + count * 6, count * 3);
    const scatter = new Float32Array(count * 3), delay = new Float32Array(count);
    let seed = 1;
    const random = () => (seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296;
    for (let i = 0; i < count; i++) {
      const theta = random() * Math.PI * 2, phi = Math.acos(2 * random() - 1), radius = 1.6 + random() * 1.4;
      scatter[i*3] = radius * Math.sin(phi) * Math.cos(theta);
      scatter[i*3+1] = .3 + radius * Math.cos(phi) * .6;
      scatter[i*3+2] = radius * Math.sin(phi) * Math.sin(theta);
      delay[i] = Math.min(1, Math.max(0, positions[i*3+1] / .6 * .6 + random() * .4)); // floor first, then walls
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.Uint8BufferAttribute(colors, 3, true));
    geometry.setAttribute('scatter', new THREE.BufferAttribute(scatter, 3));
    geometry.setAttribute('delay', new THREE.BufferAttribute(delay, 1));
    group.add(new THREE.Points(geometry, material));
    landing.querySelector('.lp-live')?.removeAttribute('hidden');
  }).catch(() => { /* Hero stays a gradient; the page remains usable. */ });

  let width = 0, height = 0, wide = true;
  const resize = () => {
    width = canvas.clientWidth; height = canvas.clientHeight; if (!width || !height) return;
    wide = width > 760;
    renderer.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix();
    uniforms.uScale.value = height / 330; // ~2.5 CSS px per point at the orbit distance on a 900px-tall hero
    // Shift the projection, not the room: wide screens put it right of the headline, narrow ones above it.
    camera.setViewOffset(width, height, wide ? -width * .24 : 0, wide ? 0 : height * .2, width, height);
  };
  new ResizeObserver(resize).observe(canvas); resize();

  const pointer = { x: 0, y: 0, tx: 0, ty: 0 };
  landing.addEventListener('pointermove', event => {
    pointer.tx = (event.clientX / innerWidth - .5) * 2; pointer.ty = (event.clientY / innerHeight - .5) * 2;
  }, { passive: true });

  let running = false, visible = true, frame = 0, last = performance.now(), angle = .9, startedAt = null;
  const loop = now => {
    frame = 0; if (!running) return;
    const dt = Math.min(.05, (now - last) / 1000); last = now;
    if (group.children.length > 1) {
      startedAt ??= now;
      if (!reduceMotion) { uniforms.uProgress.value = Math.min(1, (now - startedAt) / 2600); angle += dt * .12; }
    }
    pointer.x += (pointer.tx - pointer.x) * .04; pointer.y += (pointer.ty - pointer.y) * .04;
    const distance = wide ? 3.3 : 3.9, a = angle + pointer.x * .25;
    camera.position.set(Math.sin(a) * distance, 1.6 + pointer.y * -.18, Math.cos(a) * distance);
    camera.lookAt(target);
    renderer.render(scene, camera);
    schedule();
  };
  const schedule = () => { if (running && visible && !document.hidden && !frame) frame = requestAnimationFrame(loop); };
  new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; last = performance.now(); schedule(); }, { root: landing }).observe(canvas);
  document.addEventListener('visibilitychange', () => { last = performance.now(); schedule(); });
  return {
    resume() { running = true; last = performance.now(); schedule(); },
    pause() { running = false; if (frame) cancelAnimationFrame(frame); frame = 0; },
  };
}
