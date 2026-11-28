// Macro product-style studio: three heaps of carbohydrate powder on dark slate,
// a pouring stream, and a dissolve where grains lift and resolve into glucose glyphs.
// Params: pour (0..1), lift (0..1, heap index `liftHeap`), glyphs (0..1)
import { bokehParticles, rng, glucoseGlyphGeometry, clamp, lerp, ease, NOISE_GLSL } from '../lib.js';

export async function build({ THREE, env }) {
  const scene = new THREE.Scene();
  scene.environment = env; scene.environmentIntensity = 0.25;
  scene.fog = new THREE.FogExp2(0x060608, 0.05);
  const r = rng(51);
  // slate surface with fine noise roughness
  const slateMat = new THREE.MeshPhysicalMaterial({ color: 0x0e0e10, roughness: 0.5, clearcoat: 0.5, clearcoatRoughness: 0.35 });
  slateMat.onBeforeCompile = sh => {
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vW;').replace('#include <begin_vertex>', '#include <begin_vertex>\nvW=position;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vW;\n' + NOISE_GLSL)
      .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\nroughnessFactor=clamp(roughnessFactor+snoise(vW*4.0)*0.18+snoise(vW*40.0)*0.08,0.15,1.0);')
      .replace('#include <color_fragment>', '#include <color_fragment>\ndiffuseColor.rgb*=0.8+0.4*(0.5+0.5*snoise(vW*1.5));');
  };
  const slate = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), slateMat); slate.rotation.x = -Math.PI / 2; slate.receiveShadow = true; scene.add(slate);
  const heapsDef = [{ x: -2.3, z: 0.2, h: 1.05, rad: 1.25, col: 0xf4f2ee, size: 0.016, sparkle: 1.0 },  // dextrose (crystalline)
    { x: 0.2, z: -0.9, h: 0.9, rad: 1.35, col: 0xf6f3ea, size: 0.012, sparkle: 0.3 },                   // cyclic dextrin (fine)
    { x: 2.5, z: 0.4, h: 0.95, rad: 1.2, col: 0xeeebe4, size: 0.013, sparkle: 0.5 }];                 // branded product
  const grainGeo = new THREE.IcosahedronGeometry(1, 0);
  const heaps = heapsDef.map((H, hi) => {
    const N = 26000;
    const mat = new THREE.MeshPhysicalMaterial({ color: H.col, roughness: 0.55 - H.sparkle * 0.35, clearcoat: H.sparkle, clearcoatRoughness: 0.1, emissive: 0x000000 });
    const im = new THREE.InstancedMesh(grainGeo, mat, N); im.castShadow = true; im.receiveShadow = true;
    const base = [];
    for (let i = 0; i < N; i++) {
      const a = r() * 6.28, d = Math.pow(r(), 0.62) * H.rad;
      const prof = H.h * Math.pow(Math.max(0, 1 - d / H.rad), 1.35) * (1 + 0.08 * Math.sin(a * 5 + hi));
      const y = prof * (0.8 + r() * 0.2);
      base.push({ p: new THREE.Vector3(H.x + Math.cos(a) * d, y, H.z + Math.sin(a) * d), rot: [r() * 6, r() * 6, r() * 6], s: H.size * (0.5 + r()), ph: r() });
    }
    scene.add(im);
    return { im, base, H };
  });
  // pouring stream from above heap 0
  const NS = 2500; const stream = new THREE.InstancedMesh(grainGeo, new THREE.MeshPhysicalMaterial({ color: 0xf6f4f0, roughness: 0.3, clearcoat: 1 }), NS);
  const sb = []; for (let i = 0; i < NS; i++) sb.push({ ph: r(), a: r() * 6.28, d: r() * 0.06, s: 0.006 + r() * 0.01 });
  scene.add(stream);
  // glucose glyphs that the lifted grains resolve into
  const gGeo = glucoseGlyphGeometry();
  const gMat = new THREE.MeshPhysicalMaterial({ color: 0xf0f6f8, roughness: 0.2, clearcoat: 1, emissive: 0x2a8090, emissiveIntensity: 2.0, transparent: true, opacity: 1 });
  const NGl = 90; const glyphs = new THREE.InstancedMesh(gGeo, gMat, NGl); const gb = [];
  for (let i = 0; i < NGl; i++) gb.push({ p: new THREE.Vector3((r() - .5) * 7, 1.4 + r() * 2.6, (r() - .5) * 3 - 0.5), rot: [r() * 6, r() * 6, r() * 6], s: 0.16 + r() * 0.08 });
  scene.add(glyphs);

  const key = new THREE.SpotLight(0xffe6d0, 38, 30, 0.55, 0.85, 1.5); key.position.set(-3, 7, 5); key.target.position.set(0, 0.4, 0);
  key.castShadow = true; key.shadow.mapSize.set(1024, 1024); key.shadow.bias = -0.0004;
  const rim = new THREE.SpotLight(0x70c8ff, 34, 30, 0.6, 0.7, 1.5); rim.position.set(4, 3, -6); rim.target.position.set(0, 0.5, 0);
  const warm = new THREE.SpotLight(0xff8a50, 20, 25, 0.6, 0.8, 1.5); warm.position.set(6, 2, 3); warm.target.position.set(0, 0.5, 0);
  scene.add(key, key.target, rim, rim.target, warm, warm.target, new THREE.HemisphereLight(0x202428, 0x050505, 0.4));
  scene.add(bokehParticles({ count: 700, box: [20, 8, 16], center: [0, 3, -2], colors: [0xffffff, 0xffd0a0, 0x80d0e0], size: 0.01, intensity: 0.6, drift: 0.08 }));

  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), sv = new THREE.Vector3(), pv = new THREE.Vector3();
  return {
    anchors: { h0: () => [heapsDef[0].x, heapsDef[0].h + 0.05, heapsDef[0].z], h1: () => [heapsDef[1].x, heapsDef[1].h + 0.05, heapsDef[1].z], h2: () => [heapsDef[2].x, heapsDef[2].h + 0.05, heapsDef[2].z], glyph: () => [1.5, 3.0, -0.5] },
    scene, clear: 0x050506,
    update({ t, P }) {
      const lift = P('lift', 0), pour = P('pour', 0), glyph = P('glyphs', 0);
      heaps.forEach((h, hi) => {
        const lk = hi === P('liftHeap', -1) || P('liftHeap', -1) === 9 ? lift : 0;
        h.base.forEach((g, i) => {
          let p = g.p;
          const lifts = g.ph < 0.12;
          if (lk > 0 && lifts) { const k = clamp(lk * 1.8 - g.ph * 0.8 - (1 - g.p.y) * 0.2); const kk = ease.inOut(k);
            pv.set(p.x + Math.sin(g.ph * 30 + t) * kk * 0.8, p.y + kk * (1.5 + g.ph * 2.5), p.z + Math.cos(g.ph * 20 + t) * kk * 0.8); p = pv; }
          e.set(g.rot[0] + lk * t, g.rot[1], g.rot[2]); q.setFromEuler(e); sv.setScalar(g.s * (lk > 0 && lifts ? 1 - clamp(lk * 1.8 - g.ph * 0.8 - 0.3) : 1));
          m.compose(p, q, sv); h.im.setMatrixAt(i, m);
        });
        h.im.instanceMatrix.needsUpdate = true;
      });
      sb.forEach((s, i) => { const u = (s.ph + t * 0.9) % 1; const y = lerp(4.5, heapsDef[0].h * 0.9, u * u);
        pv.set(heapsDef[0].x + Math.cos(s.a) * s.d * (1 + u * 2), y, heapsDef[0].z + Math.sin(s.a) * s.d * (1 + u * 2));
        m.compose(pv, q.identity(), sv.setScalar(pour > 0.01 ? s.s : 0)); stream.setMatrixAt(i, m); });
      stream.instanceMatrix.needsUpdate = true;
      gb.forEach((g, i) => { const k = clamp(glyph * 1.5 - i / NGl * 0.5);
        pv.set(g.p.x + Math.sin(t * 0.4 + i) * 0.2, g.p.y + Math.sin(t * 0.6 + i * 2) * 0.15, g.p.z);
        e.set(g.rot[0] + t * 0.5, g.rot[1] + t * 0.4, 0); q.setFromEuler(e); m.compose(pv, q, sv.setScalar(g.s * ease.out(k))); glyphs.setMatrixAt(i, m); });
      glyphs.instanceMatrix.needsUpdate = true;
    },
  };
}
