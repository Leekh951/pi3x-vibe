// Deterministic synthetic point cloud for exploring the viewer before GPU connection.
// This scene is deliberately labelled as a demo; it is not a Pi3X reconstruction.
export function makeDemo() {
  const points = [], colors = [], confidence = [];
  let seed = 734;
  const random = () => { seed = (1664525 * seed + 1013904223) >>> 0; return seed / 4294967296; };
  function point(x, y, z, c) {
    const noise = .76 + random() * .23;
    points.push(x + (random() - .5) * .008, y + (random() - .5) * .008, z + (random() - .5) * .008);
    colors.push(...c.map(v => v / 255 * noise)); confidence.push(.35 + random() * .65);
  }
  function plane(origin, u, v, nu, nv, color, variation) {
    for (let i = 0; i <= nu; i++) for (let j = 0; j <= nv; j++) {
      const a = i / nu, b = j / nv;
      point(...origin.map((p, k) => p + u[k] * a + v[k] * b), variation ? variation(a, b) : color);
    }
  }
  function box(x, y, z, w, h, d, c, step = .038) {
    const nx = Math.ceil(w / step), ny = Math.ceil(h / step), nz = Math.ceil(d / step);
    plane([x, y, z], [w, 0, 0], [0, h, 0], nx, ny, c);
    plane([x, y, z + d], [w, 0, 0], [0, h, 0], nx, ny, c);
    plane([x, y + h, z], [w, 0, 0], [0, 0, d], nx, nz, c);
    plane([x, y, z], [0, h, 0], [0, 0, d], ny, nz, c);
    plane([x + w, y, z], [0, h, 0], [0, 0, d], ny, nz, c);
  }
  function cylinder(x, z, y, r, h, c, taper = 1) {
    for (let t = 0; t < h; t += .025) for (let a = 0; a < Math.PI * 2; a += .055) {
      const radius = r * (1 - t / h * (1 - taper));
      point(x + Math.cos(a) * radius, y + t, z + Math.sin(a) * radius, c);
    }
    for (let rr = 0; rr < r * taper; rr += .026) for (let a = 0; a < Math.PI * 2; a += .08) point(x + Math.cos(a) * rr, y + h, z + Math.sin(a) * rr, c);
  }
  // Cutaway room: parquet, rug, two walls, window and framed artwork.
  plane([-2.6, 0, -2.2], [5.2, 0, 0], [0, 0, 4.4], 190, 160, [129, 145, 128], (a, b) => {
    const plank = Math.floor(b * 22), seam = (a * 14 + (plank % 2) * .5) % 1;
    return seam < .02 || (b * 22) % 1 < .025 ? [75, 94, 84] : [143 + (plank % 3) * 7, 151 + (plank % 3) * 4, 125];
  });
  plane([-2.6, .02, -2.2], [5.2, 0, 0], [0, 2.7, 0], 180, 93, [167, 182, 169], (a, b) => (a > .57 && a < .87 && b > .4 && b < .91) ? [49, 89, 97] : [173, 187, 172]);
  plane([-2.6, .02, -2.2], [0, 0, 4.4], [0, 2.7, 0], 155, 93, [123, 148, 137]);
  box(-2.6, .03, -2.19, 5.2, .08, .06, [206, 209, 180]);
  box(-2.58, .03, -2.2, .055, .08, 4.4, [177, 193, 168]);
  // Window frame and panes.
  box(.36, 1.09, -2.14, .04, 1.4, .05, [214, 223, 200]);
  box(1.91, 1.09, -2.14, .04, 1.4, .05, [214, 223, 200]);
  box(.36, 1.09, -2.14, 1.59, .04, .05, [214, 223, 200]);
  box(.36, 2.45, -2.14, 1.59, .04, .05, [214, 223, 200]);
  box(1.12, 1.09, -2.14, .035, 1.4, .05, [176, 199, 175]);
  box(.36, 1.7, -2.14, 1.59, .035, .05, [176, 199, 175]);
  box(-1.95, 1.45, -2.13, .82, .95, .06, [59, 83, 77]);
  plane([-1.89, 1.52, -2.056], [.7, 0, 0], [0, .81, 0], 26, 30, [182, 187, 148], (a,b)=> ((a-.5)**2+(b-.55)**2<.09) ? [204,154,106] : [174,186,157]);
  // Rug, modular sofa, cushions.
  plane([-1.65, .015, -.85], [3.35, 0, 0], [0, 0, 2.5], 128, 90, [185, 183, 151], (a,b)=> a<.02||a>.98||b<.02||b>.98 ? [92,116,98] : [187,187,156]);
  box(-2.02, .18, -1.77, 2.14, .46, .87, [104, 135, 112]);
  box(-2.04, .63, -1.88, 2.19, .51, .25, [123, 149, 121]);
  box(-2.11, .55, -1.81, .22, .38, 1.01, [130, 154, 124]);
  box(-.01, .55, -1.81, .22, .38, 1.01, [130, 154, 124]);
  box(-1.82, .64, -1.55, .8, .13, .64, [155, 173, 135]);
  box(-.96, .64, -1.55, .8, .13, .64, [157, 173, 136]);
  box(-1.76, .8, -1.68, .46, .35, .16, [206, 192, 145]);
  box(-.77, .79, -1.69, .48, .33, .17, [90, 123, 113]);
  for(const x of [-1.88,-.03]) for(const z of [-1.59,-1.02]) box(x,.02,z,.09,.18,.09,[56,79,71]);
  // Round coffee table, books and mug.
  cylinder(-.23, .38, .52, .62, .08, [183, 154, 110]);
  for(const [x,z] of [[-.64,.13],[.15,.12],[-.2,.77]]) cylinder(x,z,.02,.045,.5,[87,105,85]);
  box(-.46,.603,.2,.3,.05,.22,[205,201,165],.015);
  box(-.43,.66,.22,.25,.027,.2,[76,112,105],.014);
  cylinder(.02,.56,.605,.075,.13,[220,222,189]);
  // Cabinet and standing lamp.
  box(1.73,.12,-1.66,.64,.75,1.3,[119,135,106]);
  box(1.71,.87,-1.68,.68,.06,1.34,[188,170,123]);
  for(const z of [-1.2,-.58]) box(1.71,.44,z,.025,.04,.2,[202,200,150],.02);
  cylinder(-2.02,.61,.02,.22,.04,[85,106,90]);
  cylinder(-2.02,.61,.06,.025,1.82,[206,202,159]);
  cylinder(-2.02,.61,1.69,.38,.46,[197,200,157],.62);
  // Plants with measured leaves in 3D, part of the synthetic point-cloud data.
  function plant(x,z,y,r,height) {
    cylinder(x,z,y,r,height*.33,[160,140,105],1.15);
    for(let leaf=0;leaf<17;leaf++) {
      const a=random()*Math.PI*2, root=y+height*.31, reach=height*(.33+random()*.35), elev=.28+random()*.75;
      for(let i=0;i<30;i++) for(let j=0;j<7;j++) {
        const t=i/29, width=Math.sin(t*Math.PI)*height*.10, side=(j/6-.5)*width;
        point(x+Math.cos(a)*reach*t+Math.sin(a)*side,root+Math.sin(t*elev)*height*.85,z+Math.sin(a)*reach*t-Math.cos(a)*side,[93+leaf%3*9,145+leaf%4*8,94]);
      }
    }
  }
  plant(1.6,1.25,.02,.22,1.28); plant(2.06,-1.24,.94,.12,.61);
  return { positions: new Float32Array(points), colors: new Float32Array(colors), confidence: new Float32Array(confidence) };
}
