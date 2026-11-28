// Shared building blocks: deterministic random, easing, GLSL noise,
// physically based tissue materials, depth-aware bokeh particles.
import * as THREE from 'three';

export function rng(seed = 1) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
export const ease = {
  linear: t => t,
  inOut: t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
  sine: t => -(Math.cos(Math.PI * t) - 1) / 2,
  out: t => 1 - Math.pow(1 - t, 3),
  in: t => t * t * t,
  expoOut: t => t === 1 ? 1 : 1 - Math.pow(2, -10 * t),
  quintInOut: t => t < .5 ? 16 * t ** 5 : 1 - Math.pow(-2 * t + 2, 5) / 2,
};

// ---------------------------------------------------------------- GLSL noise
export const NOISE_GLSL = /* glsl */`
vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}
vec4 mod289(vec4 x){return x-floor(x*(1.0/289.0))*289.0;}
vec4 permute(vec4 x){return mod289(((x*34.0)+10.0)*x);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
float snoise(vec3 v){
  const vec2 C=vec2(1.0/6.0,1.0/3.0); const vec4 D=vec4(0.0,0.5,1.0,2.0);
  vec3 i=floor(v+dot(v,C.yyy)); vec3 x0=v-i+dot(i,C.xxx);
  vec3 g=step(x0.yzx,x0.xyz); vec3 l=1.0-g; vec3 i1=min(g.xyz,l.zxy); vec3 i2=max(g.xyz,l.zxy);
  vec3 x1=x0-i1+C.xxx; vec3 x2=x0-i2+C.yyy; vec3 x3=x0-D.yyy;
  i=mod289(i);
  vec4 p=permute(permute(permute(i.z+vec4(0.0,i1.z,i2.z,1.0))+i.y+vec4(0.0,i1.y,i2.y,1.0))+i.x+vec4(0.0,i1.x,i2.x,1.0));
  float n_=0.142857142857; vec3 ns=n_*D.wyz-D.xzx;
  vec4 j=p-49.0*floor(p*ns.z*ns.z); vec4 x_=floor(j*ns.z); vec4 y_=floor(j-7.0*x_);
  vec4 x=x_*ns.x+ns.yyyy; vec4 y=y_*ns.x+ns.yyyy; vec4 h=1.0-abs(x)-abs(y);
  vec4 b0=vec4(x.xy,y.xy); vec4 b1=vec4(x.zw,y.zw);
  vec4 s0=floor(b0)*2.0+1.0; vec4 s1=floor(b1)*2.0+1.0; vec4 sh=-step(h,vec4(0.0));
  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy; vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
  vec3 p0=vec3(a0.xy,h.x); vec3 p1=vec3(a0.zw,h.y); vec3 p2=vec3(a1.xy,h.z); vec3 p3=vec3(a1.zw,h.w);
  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
  p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
  vec4 m=max(0.5-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.0); m=m*m;
  return 105.0*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}
float fbm2(vec3 p){return 0.6*snoise(p)+0.3*snoise(p*2.1);}
float fbm(vec3 p){float a=0.5,s=0.0;for(int i=0;i<4;i++){s+=a*snoise(p);p*=2.03;a*=0.5;}return s;}
`;

// ------------------------------------------------------------ tissue material
// MeshPhysicalMaterial + injected: procedural micro-normal perturbation,
// fibre striation along an object-space axis, wrap/back-scatter term that
// approximates subsurface scattering, and colour variation.
export function tissueMaterial(o = {}) {
  const m = new THREE.MeshPhysicalMaterial({
    color: o.color ?? 0x8a1c1c, roughness: o.roughness ?? 0.42, metalness: 0,
    clearcoat: o.clearcoat ?? 0.55, clearcoatRoughness: o.clearcoatRoughness ?? 0.28,
    sheen: o.sheen ?? 0, sheenColor: new THREE.Color(o.sheenColor ?? 0xff6a50), sheenRoughness: 0.5,
    transparent: !!o.transparent, opacity: o.opacity ?? 1, side: o.side ?? THREE.FrontSide,
    depthWrite: o.depthWrite ?? true,
  });
  const u = {
    uFibreAxis: { value: new THREE.Vector3(...(o.axis ?? [0, 1, 0])) },
    uFibreFreq: { value: o.fibreFreq ?? 40 }, uFibreAmt: { value: o.fibre ?? 0.5 },
    uStriFreq: { value: o.striFreq ?? 0 }, uStriAmt: { value: o.stri ?? 0 },
    uBump: { value: o.bump ?? 0.35 }, uBumpScale: { value: o.bumpScale ?? 6 },
    uSSS: { value: new THREE.Color(o.sss ?? 0xff3a20) }, uSSSAmt: { value: o.sssAmt ?? 0.6 },
    uVar: { value: new THREE.Color(o.varColor ?? 0x3a0608) }, uVarAmt: { value: o.varAmt ?? 0.5 },
    uGlow: { value: new THREE.Color(o.glow ?? 0x000000) }, uTime: { value: 0 },
  };
  m.userData.u = u;
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, u);
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vObjPos;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvObjPos = position;');
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', `#include <common>
varying vec3 vObjPos; uniform vec3 uFibreAxis; uniform float uFibreFreq,uFibreAmt,uStriFreq,uStriAmt,uBump,uBumpScale,uSSSAmt,uVarAmt,uTime;
uniform vec3 uSSS,uVar,uGlow;
${NOISE_GLSL}
float fibrePattern(vec3 p){
  vec3 ax=normalize(uFibreAxis);
  vec3 q=p-ax*dot(p,ax);            // collapse along fibre axis -> long streaks
  float along=dot(p,ax);
  float f=snoise(q*uFibreFreq+vec3(along*0.6))*0.6+snoise(q*uFibreFreq*2.3+vec3(along*1.4))*0.4;
  float s=uStriFreq>0.0?0.5+0.5*sin(along*uStriFreq+snoise(q*8.0)*1.5):0.5;
  return f*uFibreAmt+(s-0.5)*uStriAmt;
}`)
      .replace('#include <color_fragment>', `#include <color_fragment>
  float fp=fibrePattern(vObjPos);
  float vn=snoise(vObjPos*uBumpScale*0.35);
  diffuseColor.rgb=mix(diffuseColor.rgb,uVar,clamp(uVarAmt*(0.5+0.5*vn)+fp*0.25,0.0,1.0));
  diffuseColor.rgb*=0.85+0.3*fp;`)
      .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
  { // screen-space derivative bump (cheap on CPU rasterisers)
    float hb=(fbm2(vObjPos*uBumpScale)+fp*2.0)*uBump*0.004;
    vec3 dpx=dFdx(-vViewPosition), dpy=dFdy(-vViewPosition);
    float dhx=dFdx(hb), dhy=dFdy(hb);
    vec3 r1=cross(dpy,normal), r2=cross(normal,dpx); float det=dot(dpx,r1);
    vec3 grad=sign(det)*(dhx*r1+dhy*r2);
    normal=normalize(abs(det)*normal-grad); }`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
  { vec3 V=normalize(vViewPosition); float fr=1.0-abs(dot(normal,-V));
    totalEmissiveRadiance+=uSSS*uSSSAmt*(pow(fr,2.5)*0.55+0.08)*(0.7+0.3*vn);
    totalEmissiveRadiance+=uGlow; }`);
  };
  return m;
}

// Simple fresnel shell (x-ray skin / translucent membranes)
export function fresnelMaterial(o = {}) {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, side: o.side ?? THREE.FrontSide,
    blending: o.additive === false ? THREE.NormalBlending : THREE.AdditiveBlending,
    uniforms: { uColor: { value: new THREE.Color(o.color ?? 0x9fb8c8) }, uPow: { value: o.power ?? 2.6 },
      uAmt: { value: o.amount ?? 1 }, uBase: { value: o.base ?? 0.02 }, uTime: { value: 0 },
      uNoise: { value: o.noise ?? 0.3 } },
    vertexShader: `varying vec3 vN; varying vec3 vV; varying vec3 vP;
      void main(){ vec4 mv=modelViewMatrix*vec4(position,1.0); vN=normalize(normalMatrix*normal); vV=-mv.xyz; vP=position;
      gl_Position=projectionMatrix*mv; }`,
    fragmentShader: `uniform vec3 uColor; uniform float uPow,uAmt,uBase,uNoise,uTime; varying vec3 vN; varying vec3 vV; varying vec3 vP;
      ${NOISE_GLSL}
      void main(){ float f=1.0-abs(dot(normalize(vN),normalize(vV)));
        float n=0.75+uNoise*snoise(vP*9.0+uTime*0.1);
        float a=(pow(f,uPow)+uBase)*uAmt*n; gl_FragColor=vec4(uColor*a,1.0); }`,
  });
}

// ------------------------------------------------------ bokeh dust particles
// Points whose sprite size grows with circle-of-confusion -> soft bokeh discs
export function bokehParticles({ count = 800, box = [20, 12, 30], center = [0, 0, 0], colors = [0xff6040, 0x60c8ff],
  size = 0.05, seed = 3, intensity = 1, drift = 0.15 } = {}) {
  const r = rng(seed), g = new THREE.BufferGeometry();
  const pos = new Float32Array(count * 3), col = new Float32Array(count * 3), rnd = new Float32Array(count);
  const cs = colors.map(c => new THREE.Color(c));
  for (let i = 0; i < count; i++) {
    pos[i * 3] = center[0] + (r() - .5) * box[0]; pos[i * 3 + 1] = center[1] + (r() - .5) * box[1]; pos[i * 3 + 2] = center[2] + (r() - .5) * box[2];
    const c = cs[Math.floor(r() * cs.length)]; const k = 0.4 + r() * 0.8;
    col[i * 3] = c.r * k; col[i * 3 + 1] = c.g * k; col[i * 3 + 2] = c.b * k; rnd[i] = r();
  }
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  g.setAttribute('rnd', new THREE.BufferAttribute(rnd, 1));
  const mat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, vertexColors: true,
    uniforms: { uFocus: { value: 10 }, uAperture: { value: 1 }, uSize: { value: size }, uTime: { value: 0 },
      uRes: { value: 1080 }, uInt: { value: intensity }, uDrift: { value: drift } },
    vertexShader: `attribute float rnd; uniform float uFocus,uAperture,uSize,uTime,uRes,uDrift; varying vec3 vC; varying float vA;
      void main(){ vec3 p=position+vec3(sin(uTime*0.3+rnd*40.0),cos(uTime*0.23+rnd*17.0),sin(uTime*0.17+rnd*9.0))*uDrift;
        vec4 mv=modelViewMatrix*vec4(p,1.0); float d=-mv.z;
        float coc=abs(1.0/max(d,0.01)-1.0/uFocus)*uAperture*uFocus*0.35;
        float s=uSize*(1.0+rnd)*uRes*projectionMatrix[1][1]/max(d,0.01);
        float px=s+coc*uRes*0.03; gl_PointSize=clamp(px,1.5,uRes*0.09);
        vA=clamp((s*s+4.0)/(px*px+4.0),0.04,1.0); vC=color; gl_Position=projectionMatrix*mv; }`,
    fragmentShader: `uniform float uInt; varying vec3 vC; varying float vA;
      void main(){ vec2 c=gl_PointCoord-0.5; float r=length(c)*2.0; if(r>1.0) discard;
        float edge=smoothstep(1.0,0.82,r); float ring=0.75+0.25*smoothstep(0.6,0.95,r);
        float a=edge*ring*vA; gl_FragColor=vec4(vC*a*uInt,1.0); }`,
  });
  const pts = new THREE.Points(g, mat);
  pts.frustumCulled = false;
  pts.userData.isBokeh = true;
  return pts;
}

// Called per frame by the engine on every bokeh system in a scene
export function updateBokeh(scene, cam, focus, aperture, t, res) {
  scene.traverse(o => {
    if (o.userData.isBokeh) {
      const u = o.material.uniforms; u.uFocus.value = focus; u.uAperture.value = aperture;
      u.uTime.value = t; u.uRes.value = res;
    }
  });
}

// SDF -> mesh using three's MarchingCubes as the polygoniser.
// bounds: {c:[x,y,z], h: half-extent of the cube}
import { MarchingCubes } from 'three/addons/objects/MarchingCubes.js';
export function sdfMesh(sdf, { res = 96, c = [0, 0, 0], h = 1, maxPoly = 400000 } = {}) {
  const mc = new MarchingCubes(res, new THREE.MeshBasicMaterial(), false, false, maxPoly);
  mc.isolation = 0;
  const half = res / 2;
  for (let z = 0; z < res; z++) for (let y = 0; y < res; y++) for (let x = 0; x < res; x++)
    mc.field[z * res * res + y * res + x] = -sdf(c[0] + (x - half) / half * h, c[1] + (y - half) / half * h, c[2] + (z - half) / half * h);
  mc.update();
  const n = mc.count;
  const P = mc.geometry.getAttribute('position').array.slice(0, n * 3);
  const N = mc.geometry.getAttribute('normal').array.slice(0, n * 3);
  for (let i = 0; i < n; i++) { P[i * 3] = c[0] + P[i * 3] * h; P[i * 3 + 1] = c[1] + P[i * 3 + 1] * h; P[i * 3 + 2] = c[2] + P[i * 3 + 2] * h; }
  for (let i = 0; i < n; i++) { const l = Math.hypot(N[i*3],N[i*3+1],N[i*3+2]) || 1; N[i*3]/=l; N[i*3+1]/=l; N[i*3+2]/=l; }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(P, 3));
  g.setAttribute('normal', new THREE.BufferAttribute(N, 3));
  mc.geometry.dispose();
  return g;
}

export const smin = (a, b, k) => { const h = Math.max(k - Math.abs(a - b), 0) / k; return Math.min(a, b) - h * h * k * 0.25; };
export function capsule(px, py, pz, a, b, r) {
  const bax = b[0] - a[0], bay = b[1] - a[1], baz = b[2] - a[2];
  const pax = px - a[0], pay = py - a[1], paz = pz - a[2];
  const h = clamp((pax * bax + pay * bay + paz * baz) / (bax * bax + bay * bay + baz * baz));
  const r0 = Array.isArray(r) ? lerp(r[0], r[1], h) : r;
  return Math.hypot(pax - bax * h, pay - bay * h, paz - baz * h) - r0;
}
export function ellipsoid(px, py, pz, c, r) {
  const x = (px - c[0]) / r[0], y = (py - c[1]) / r[1], z = (pz - c[2]) / r[2];
  const k0 = Math.hypot(x, y, z), k1 = Math.hypot(x / r[0], y / r[1], z / r[2]);
  return k0 * (k0 - 1) / Math.max(k1, 1e-6);
}

// ------------------------------------------------ molecular helpers
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

// Protein-like cluster: spheres scattered on/inside an SDF iso-surface (instanced)
export function proteinBlob(sdf, { count = 1500, bounds = [[-1, -1, -1], [1, 1, 1]], r0 = 0.05, r1 = 0.09, colors = [0x2a8ac0, 0x40b8d8], seed = 5,
  shell = 0.06, material } = {}) {
  const r = rng(seed); const pts = [];
  const [mn, mx] = bounds; let guard = 0;
  while (pts.length < count && guard++ < count * 400) {
    const x = lerp(mn[0], mx[0], r()), y = lerp(mn[1], mx[1], r()), z = lerp(mn[2], mx[2], r());
    const d = sdf(x, y, z); if (d < 0 && d > -shell) pts.push([x, y, z]);
  }
  const geo = new THREE.IcosahedronGeometry(1, 2);
  const mat = material ?? new THREE.MeshStandardMaterial({ roughness: 0.38, metalness: 0.0 });
  const im = new THREE.InstancedMesh(geo, mat, pts.length);
  const m = new THREE.Matrix4(), c = new THREE.Color(), cs = colors.map(x => new THREE.Color(x));
  pts.forEach((p, i) => {
    const s = lerp(r0, r1, r());
    m.makeScale(s, s, s).setPosition(...p); im.setMatrixAt(i, m);
    c.copy(cs[0]).lerp(cs[1 % cs.length], r()).multiplyScalar(0.75 + r() * 0.4); im.setColorAt(i, c);
  });
  im.userData.points = pts;
  return im;
}

// glucose ring glyph (6-membered ring with substituent stubs), unit ~1
export function glucoseGlyphGeometry() {
  const parts = [];
  for (let i = 0; i < 6; i++) {
    const a = i / 6 * Math.PI * 2, x = Math.cos(a) * 0.5, z = Math.sin(a) * 0.5, y = (i % 2 ? 0.08 : -0.08);
    const s = new THREE.SphereGeometry(i === 0 ? 0.17 : 0.14, 12, 8); s.translate(x, y, z); parts.push(s);
    const a2 = (i + 1) / 6 * Math.PI * 2, x2 = Math.cos(a2) * 0.5, z2 = Math.sin(a2) * 0.5, y2 = ((i + 1) % 2 ? 0.08 : -0.08);
    const b = new THREE.CylinderGeometry(0.045, 0.045, Math.hypot(x2 - x, y2 - y, z2 - z), 6);
    b.lookAt(new THREE.Vector3(x2 - x, y2 - y, z2 - z)); b.rotateX(0); // align
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(x2 - x, y2 - y, z2 - z).normalize());
    const bb = new THREE.CylinderGeometry(0.045, 0.045, Math.hypot(x2 - x, y2 - y, z2 - z), 6); bb.applyQuaternion(q); bb.translate((x + x2) / 2, (y + y2) / 2, (z + z2) / 2); parts.push(bb);
    if (i !== 0) { const st = new THREE.SphereGeometry(0.09, 8, 6); st.translate(Math.cos(a) * 0.85, y * 2.5, Math.sin(a) * 0.85); parts.push(st); }
  }
  return mergeGeometries(parts.map(g => { g.deleteAttribute('uv'); return g.toNonIndexed(); }));
}

// ball-and-stick molecule from atom list [{e:'C',p:[x,y,z]}] and bonds [[i,j]]
const CPK = { C: [0x3a3d42, 0.36], O: [0xd8342c, 0.34], H: [0xeef2f4, 0.22], N: [0x3a6ad8, 0.34] };
export function ballStick(atoms, bonds, { bondR = 0.09 } = {}) {
  const g = new THREE.Group();
  const mats = {};
  for (const e of Object.keys(CPK)) mats[e] = new THREE.MeshPhysicalMaterial({ color: CPK[e][0], roughness: 0.25, clearcoat: 0.8, clearcoatRoughness: 0.15 });
  const sg = new THREE.SphereGeometry(1, 40, 28);
  atoms.forEach(a => { const m = new THREE.Mesh(sg, mats[a.e]); m.scale.setScalar(CPK[a.e][1]); m.position.set(...a.p); g.add(m); });
  const bm = new THREE.MeshPhysicalMaterial({ color: 0xb8bec4, roughness: 0.3, metalness: 0.2, clearcoat: 0.5 });
  bonds.forEach(([i, j]) => {
    const a = new THREE.Vector3(...atoms[i].p), b = new THREE.Vector3(...atoms[j].p);
    const c = new THREE.Mesh(new THREE.CylinderGeometry(bondR, bondR, a.distanceTo(b), 16), bm);
    c.position.copy(a).add(b).multiplyScalar(0.5);
    c.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize()); g.add(c);
  });
  return g;
}

// beta-D-glucopyranose (approximate chair geometry, Angstrom-scaled)
export function glucoseAtoms() {
  const ring = []; // C1..C5, O5 in chair
  for (let i = 0; i < 6; i++) { const a = i / 6 * Math.PI * 2; ring.push([Math.cos(a) * 1.45, (i % 2 ? 0.25 : -0.25), Math.sin(a) * 1.45]); }
  const atoms = [], bonds = [];
  const names = ['C', 'C', 'C', 'C', 'C', 'O'];
  ring.forEach((p, i) => atoms.push({ e: names[i], p }));
  for (let i = 0; i < 6; i++) bonds.push([i, (i + 1) % 6]);
  const out = (i, k = 1) => { const p = ring[i]; const l = Math.hypot(p[0], p[2]); return [p[0] / l * k, p[2] / l * k]; };
  // equatorial OH on C1..C4, CH2OH on C5; axial H on C1..C5
  for (let i = 0; i < 5; i++) {
    const [ox, oz] = out(i, 1.4); const p = ring[i];
    const sgn = i % 2 ? 1 : -1;
    if (i < 4) {
      const O = atoms.push({ e: 'O', p: [p[0] + ox, p[1] - sgn * 0.35, p[2] + oz] }) - 1; bonds.push([i, O]);
      const H = atoms.push({ e: 'H', p: [p[0] + ox * 1.55, p[1] - sgn * 0.1, p[2] + oz * 1.55] }) - 1; bonds.push([O, H]);
    } else {
      const C6 = atoms.push({ e: 'C', p: [p[0] + ox, p[1] - sgn * 0.4, p[2] + oz] }) - 1; bonds.push([i, C6]);
      const O6 = atoms.push({ e: 'O', p: [p[0] + ox * 1.9, p[1] + 0.5, p[2] + oz * 1.9] }) - 1; bonds.push([C6, O6]);
      const H6 = atoms.push({ e: 'H', p: [p[0] + ox * 2.5, p[1] + 0.3, p[2] + oz * 2.5] }) - 1; bonds.push([O6, H6]);
      for (const s of [-1, 1]) { const h = atoms.push({ e: 'H', p: [p[0] + ox * 1.2 + s * oz * 0.6, p[1] - sgn * 1.2, p[2] + oz * 1.2 - s * ox * 0.6] }) - 1; bonds.push([C6, h]); }
    }
    const Hx = atoms.push({ e: 'H', p: [p[0] + ox * 0.15, p[1] + sgn * 1.05, p[2] + oz * 0.15] }) - 1; bonds.push([i, Hx]);
  }
  return { atoms, bonds };
}
