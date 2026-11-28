// Carbohydrate structures. show: 'glucose' | 'dextrin' | 'glycogen'
// glucose  : beta-D-glucopyranose ball-and-stick (CPK colours)
// dextrin  : highly branched cyclic dextrin - cyclic alpha-1,4 backbone with alpha-1,6 branched clusters (simplified)
// glycogen : glycogenin core with tiered alpha-1,6 branching; `build` reveals tiers (replenishment)
import { ballStick, glucoseAtoms, glucoseGlyphGeometry, proteinBlob, bokehParticles, rng, clamp } from '../lib.js';

export async function build({ THREE, env }) {
  const scene = new THREE.Scene();
  scene.environment = env; scene.environmentIntensity = 0.55;
  scene.fog = new THREE.FogExp2(0x05070a, 0.03);
  const r = rng(31);
  // ---- glucose hero
  const { atoms, bonds } = glucoseAtoms();
  const glucose = ballStick(atoms, bonds); glucose.scale.setScalar(0.9); scene.add(glucose);
  // ---- glyph instancing helper
  const gGeo = glucoseGlyphGeometry();
  const unitMat = new THREE.MeshPhysicalMaterial({ color: 0xf0f4f6, roughness: 0.2, clearcoat: 1, emissive: 0x16404a, emissiveIntensity: 1 });
  function chainTree(units, start, dir, n, tier, maxTier, step) {
    let p = start.clone(), d = dir.clone();
    for (let i = 0; i < n; i++) {
      d.add(new THREE.Vector3(r() - .5, r() - .5, r() - .5).multiplyScalar(0.35)).normalize();
      p = p.clone().add(d.clone().multiplyScalar(step));
      units.push({ p, tier: tier + i / n, rot: [r() * 6, r() * 6, r() * 6] });
      if (tier < maxTier && (i === 2 || i === 6)) {
        const nd = d.clone().add(new THREE.Vector3(r() - .5, r() - .5, r() - .5).multiplyScalar(1.6)).normalize();
        chainTree(units, p, nd, 8 + Math.floor(r() * 4), tier + 1, maxTier, step);
      }
    }
  }
  function unitsMesh(units, scale) {
    const im = new THREE.InstancedMesh(gGeo, unitMat, units.length);
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    units.forEach((u, i) => { e.set(...u.rot); q.setFromEuler(e); m.compose(u.p, q, new THREE.Vector3(scale, scale, scale)); im.setMatrixAt(i, m); });
    im.userData.units = units; im.userData.scale = scale; return im;
  }
  // ---- glycogen
  const glyU = [];
  for (let k = 0; k < 2; k++) chainTree(glyU, new THREE.Vector3(), new THREE.Vector3(k ? 1 : -1, r() - .5, r() - .5).normalize(), 10, 0, 5, 0.42);
  for (let k = 0; k < 4; k++) chainTree(glyU, new THREE.Vector3(), new THREE.Vector3(r() - .5, r() - .5, r() - .5).normalize(), 9, 1, 5, 0.42);
  glyU.sort((a, b) => a.tier - b.tier);
  const glycogen = new THREE.Group();
  const glyIM = unitsMesh(glyU, 0.3); glycogen.add(glyIM);
  const core = proteinBlob((x, y, z) => Math.hypot(x, y * 1.2, z) - 0.42, { count: 600, bounds: [[-.6, -.6, -.6], [.6, .6, .6]], r0: 0.03, r1: 0.06, colors: [0xd8602a, 0xffa050], seed: 3, shell: 0.12 });
  glycogen.add(core); scene.add(glycogen);
  // ---- highly branched cyclic dextrin
  const dexU = []; const NB = 34, RR = 2.4;
  for (let i = 0; i < NB; i++) { const a = i / NB * Math.PI * 2; const p = new THREE.Vector3(Math.cos(a) * RR, Math.sin(a * 3) * 0.25, Math.sin(a) * RR);
    dexU.push({ p, tier: 0, rot: [r() * 6, r() * 6, r() * 6] });
    if (i % 3 === 0) chainTree(dexU, p, new THREE.Vector3(Math.cos(a), (r() - .5) * 1.2, Math.sin(a)).normalize(), 6 + Math.floor(r() * 4), 1, 3, 0.4); }
  const dextrin = new THREE.Group(); const dexIM = unitsMesh(dexU, 0.27); dextrin.add(dexIM); scene.add(dextrin);
  // glow backdrop plane (soft volumetric falloff)
  const halo = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uC: { value: new THREE.Color(0x3a0a10) } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: 'uniform vec3 uC; varying vec2 vUv; void main(){ float d=length(vUv-0.5); gl_FragColor=vec4(uC*exp(-d*d*14.0),1.0); }' }));
  halo.position.z = -8; scene.add(halo);

  const key = new THREE.SpotLight(0xffe0cc, 90, 30, 0.7, 0.8, 1.6); key.position.set(4, 6, 7);
  const rim = new THREE.DirectionalLight(0x6ad0ee, 1.6); rim.position.set(-5, 2, -6);
  const rim2 = new THREE.DirectionalLight(0xff7a50, 0.8); rim2.position.set(5, -2, -4);
  scene.add(key, rim, rim2, new THREE.HemisphereLight(0x283040, 0x060404, 0.4));
  scene.add(bokehParticles({ count: 600, box: [24, 14, 20], center: [0, 0, -2], colors: [0x70d0e8, 0xff9060, 0xffffff], size: 0.02, intensity: 0.7 }));

  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), sv = new THREE.Vector3();
  const wp = (o, v) => () => o.localToWorld(new THREE.Vector3(...v)).toArray();
  return {
    anchors: { ring: wp(glucose, [1.45, -0.25, 0]), oxygen: wp(glucose, [-0.72, 0.25, -1.25]), backbone: wp(dextrin, [2.4, 0, 0]), branch: wp(dextrin, [-2.9, 0.4, 1.2]),
      core: () => [0, 0, 0], tiers: wp(glycogen, [2.2, 1.0, 0.5]) },
    scene, clear: 0x040507,
    update({ t, P }) {
      const show = P('show', 'glucose');
      glucose.visible = show === 'glucose'; glycogen.visible = show === 'glycogen'; dextrin.visible = show === 'dextrin';
      const spin = P('spin', 0.15);
      glucose.rotation.set(0.35 + Math.sin(t * 0.3) * 0.1, t * spin, 0.15);
      dextrin.rotation.set(0.5, t * spin * 0.6, 0.12);
      glycogen.rotation.set(0.2, t * spin * 0.5, 0);
      unitMat.emissiveIntensity = 0.6 + P('glow', 0.5);
      if (show === 'glycogen') { // reveal tiers progressively, new units pop in with a bright flash
        const b = P('build', 1); const maxT = 6 * b;
        const units = glyIM.userData.units, s0 = glyIM.userData.scale;
        units.forEach((u, i) => { const k = clamp((maxT - u.tier) * 2); e.set(...u.rot); q.setFromEuler(e); sv.setScalar(s0 * k); m.compose(u.p, q, sv); glyIM.setMatrixAt(i, m); });
        glyIM.instanceMatrix.needsUpdate = true;
      }
    },
  };
}
