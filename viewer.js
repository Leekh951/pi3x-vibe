import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { PLYLoader } from './vendor/PLYLoader.js';

export class SpaceViewer {
  constructor(mount, onCount) {
    this.mount = mount; this.onCount = onCount; this.threshold = .1;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x101a23); mount.append(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(43, 1, .01, 2000);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true; this.controls.dampingFactor = .075;
    this.controls.autoRotateSpeed = .65; this.controls.maxPolarAngle = Math.PI * .96;
    this.controls.addEventListener('start', () => this.controls.autoRotate = false);
    this.grid = new THREE.GridHelper(20, 40, 0x30404a, 0x1d2b35);
    this.grid.position.y = -.04; this.scene.add(this.grid);
    this.material = new THREE.ShaderMaterial({
      transparent: true, depthWrite: true,
      uniforms: { pointSize: { value: 2 * this.renderer.getPixelRatio() }, threshold: { value: .1 }, colorMode: { value: 0 }, minY: { value: 0 }, maxY: { value: 3 } },
      vertexShader: `attribute vec3 color; attribute float confidence;
        varying vec3 vColor; varying float vConfidence; varying float vHeight;
        uniform float pointSize; uniform float minY; uniform float maxY;
        void main() { vColor=color; vConfidence=confidence;
          vHeight=clamp((position.y-minY)/max(maxY-minY,0.001),0.0,1.0);
          gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); gl_PointSize=pointSize; }`,
      fragmentShader: `uniform float threshold; uniform int colorMode;
        varying vec3 vColor; varying float vConfidence; varying float vHeight;
        void main() { if(vConfidence<threshold) discard;
          float r=length(gl_PointCoord-vec2(0.5)); if(r>0.5) discard;
          vec3 c=vColor; if(colorMode==1) c=mix(vec3(.09,.27,.43),vec3(.49,.94,.24),vHeight);
          gl_FragColor=vec4(c,1.0-smoothstep(.34,.5,r));
          #include <tonemapping_fragment>
          #include <colorspace_fragment>
        }`
    });
    this.observer = new ResizeObserver(() => this.resize()); this.observer.observe(mount);
    this.renderer.setAnimationLoop(() => { this.controls.update(); this.renderer.render(this.scene, this.camera); });
    this.resize();
  }
  resize() {
    const { width, height } = this.mount.getBoundingClientRect();
    if (!width || !height) return;
    this.renderer.setSize(width, height); this.camera.aspect = width / height; this.camera.updateProjectionMatrix();
  }
  setData(data, { flip = false } = {}) {
    if (!data.positions.length || data.positions.length % 3) throw Error('표시할 3D 점이 없는 파일입니다.');
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(data.positions, 3));
    // WebGL uses linear colour internally. Demo and PLY colours arrive as sRGB.
    const linear = new Float32Array(data.colors.length), c = new THREE.Color();
    for (let i = 0; i < linear.length; i += 3) { c.setRGB(data.colors[i], data.colors[i+1], data.colors[i+2], THREE.SRGBColorSpace); c.toArray(linear, i); }
    geometry.setAttribute('color', new THREE.BufferAttribute(linear, 3));
    geometry.setAttribute('confidence', new THREE.BufferAttribute(data.confidence, 1));
    if (flip) geometry.rotateX(Math.PI); // OpenCV right/down/forward -> Three right/up/back.
    geometry.computeBoundingBox();
    const bounds = geometry.boundingBox, size = bounds.getSize(new THREE.Vector3());
    const center = bounds.getCenter(new THREE.Vector3());
    const scale = 5.2 / Math.max(size.x, size.y, size.z, .0001);
    geometry.translate(-center.x, -bounds.min.y, -center.z); geometry.scale(scale, scale, scale);
    geometry.computeBoundingBox(); geometry.computeBoundingSphere();
    const oldGeometry = this.cloud?.geometry;
    if (this.cloud) this.scene.remove(this.cloud);
    oldGeometry?.dispose();
    this.cloud = new THREE.Points(geometry, this.material); this.scene.add(this.cloud);
    this.material.uniforms.maxY.value = geometry.boundingBox.max.y;
    this.data = data; this.coordinateSystem=flip?'OPENCV':'Y_UP'; this.fit(); this.updateCount();
  }
  parsePLY(buffer, flip = true) {
    if (buffer.byteLength > 100 * 1024 * 1024) throw Error('100 MB 이하의 PLY 파일을 선택해주세요.');
    const prefix = new TextDecoder().decode(buffer.slice(0, 128 * 1024));
    const end = prefix.indexOf('end_header');
    if (!prefix.startsWith('ply') || end < 0) throw Error('올바른 PLY 파일이 아닙니다.');
    const header = prefix.slice(0,end);
    if (/comment SPACE coordinate_system Y_UP/.test(header)) flip=false;
    const declared = Number(header.match(/element vertex\s+(\d+)/)?.[1] || 0);
    if (!declared || declared > 2000000) throw Error('점이 1–2,000,000개인 PLY 파일을 선택해주세요.');
    const loader = new PLYLoader();
    const hasConfidence = /property\s+\w+\s+confidence/.test(header);
    if (hasConfidence) loader.setCustomPropertyNameMapping({ confidence: ['confidence'] });
    const parsed = loader.parse(buffer), position = parsed.getAttribute('position'), color = parsed.getAttribute('color');
    if (!position || position.count !== declared) { parsed.dispose(); throw Error('PLY 점 데이터가 손상되었거나 지원하지 않는 구조입니다.'); }
    const rawPositions = position.array, rawColors = color?.array;
    const conf = parsed.getAttribute('confidence')?.array;
    // PLYLoader already converts sRGB colours to linear; convert back for setData.
    const positions = [], colors = [], confidence = [], c = new THREE.Color();
    for (let i = 0; i < position.count; i++) {
      const xyz = [rawPositions[i*3],rawPositions[i*3+1],rawPositions[i*3+2]];
      if (!xyz.every(Number.isFinite)) continue;
      positions.push(...xyz);
      if(rawColors) { c.setRGB(rawColors[i*3],rawColors[i*3+1],rawColors[i*3+2]); c.convertLinearToSRGB(); colors.push(c.r,c.g,c.b); }
      else colors.push(.70,.87,.54);
      confidence.push(conf && Number.isFinite(conf[i]) ? Math.min(1,Math.max(0,conf[i])) : 1);
    }
    parsed.dispose();
    this.setData({ positions: new Float32Array(positions), colors: new Float32Array(colors), confidence: new Float32Array(confidence) }, { flip });
    return { count: positions.length / 3, hasConfidence };
  }
  fit(top = false) {
    if (!this.cloud) return;
    const target = this.cloud.geometry.boundingSphere.center;
    this.controls.target.copy(target); this.controls.autoRotate = false;
    // Account for portrait viewports when fitting the bounding sphere.
    const halfFov = Math.min(THREE.MathUtils.degToRad(this.camera.fov/2), Math.atan(Math.tan(THREE.MathUtils.degToRad(this.camera.fov/2))*this.camera.aspect));
    const distance = this.cloud.geometry.boundingSphere.radius / Math.sin(halfFov) * 1.08;
    const direction = top ? new THREE.Vector3(0,1,.0001) : new THREE.Vector3(1.12,.84,1.35).normalize();
    this.camera.position.copy(target).addScaledVector(direction,distance);
    this.camera.near = Math.max(distance/1000,.001); this.camera.far=distance*100;
    this.camera.updateProjectionMatrix(); this.controls.minDistance=distance*.07; this.controls.maxDistance=distance*7;
    this.controls.update();
  }
  setThreshold(value) { this.threshold=value; this.material.uniforms.threshold.value=value; this.updateCount(); }
  updateCount() { if(this.data) { let n=0; for(const c of this.data.confidence) if(c>=this.threshold)n++; this.onCount(n); } }
  setSize(size) { this.material.uniforms.pointSize.value = size * this.renderer.getPixelRatio(); }
  setColor(mode) { this.material.uniforms.colorMode.value = mode==='height' ? 1 : 0; }
  exportPLY() {
    if (!this.data) throw Error('저장할 공간이 없습니다.');
    const { positions, colors, confidence } = this.data;
    let count=0; for (const c of confidence) if(c>=this.threshold)count++;
    if(!count)throw Error('표시할 점이 없어요. 노이즈 정리 기준을 낮춰주세요.');
    const header = new TextEncoder().encode(`ply\nformat binary_little_endian 1.0\ncomment SPACE coordinate_system ${this.coordinateSystem}\nelement vertex ${count}\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nproperty float confidence\nend_header\n`);
    const body = new ArrayBuffer(count*19), view = new DataView(body); let offset=0;
    for(let i=0;i<confidence.length;i++) {
      if(confidence[i]<this.threshold)continue;
      for(let j=0;j<3;j++)view.setFloat32(offset+j*4,positions[i*3+j],true);
      for(let j=0;j<3;j++)view.setUint8(offset+12+j,Math.round(Math.min(1,Math.max(0,colors[i*3+j]))*255));
      view.setFloat32(offset+15,confidence[i],true); offset+=19;
    }
    return new Blob([header,body],{type:'application/octet-stream'});
  }
}
