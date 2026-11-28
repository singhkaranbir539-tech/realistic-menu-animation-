// Intracellular metabolism (conceptual): ribosome translating mRNA into a growing
// polypeptide from free amino acids; mitochondrion receiving glucose-derived fuel.
// Params: chain (0..1 growth), aa (amino-acid flow), fuel (glucose->mitochondrion), atp, breakdown (0..1)
import { proteinBlob, glucoseGlyphGeometry, bokehParticles, rng, ellipsoid, smin, clamp, lerp, NOISE_GLSL } from '../lib.js';

export async function build({ THREE, env }) {
  const scene = new THREE.Scene();
  scene.environment = env; scene.environmentIntensity = 0.3;
  scene.fog = new THREE.FogExp2(0x0a0406, 0.05);
  const r = rng(61);
  // ---- ribosome (large + small subunit)
  const ribo = new THREE.Group(); ribo.position.set(-2.4, 0, 0); scene.add(ribo);
  const large = proteinBlob((x, y, z) => smin(ellipsoid(x, y, z, [0, 0.35, 0], [1.0, 0.7, 0.85]), ellipsoid(x, y, z, [0.5, 0.75, 0.2], [0.45, 0.4, 0.4]), 0.3),
    { count: 3800, bounds: [[-1.2, -0.5, -1], [1.2, 1.4, 1]], r0: 0.05, r1: 0.085, colors: [0x4a3a78, 0x6a5890], seed: 1, shell: 0.14 });
  const small = proteinBlob((x, y, z) => ellipsoid(x, y, z, [0, -0.55, 0], [0.9, 0.38, 0.7]),
    { count: 1800, bounds: [[-1.1, -1.0, -0.8], [1.1, -0.1, 0.8]], r0: 0.05, r1: 0.08, colors: [0x2a5a7a, 0x3a7a90], seed: 2, shell: 0.14 });
  ribo.add(large, small);
  // mRNA strand
  const mrnaPts = []; for (let i = 0; i <= 20; i++) { const x = -6 + i * 0.3; mrnaPts.push(new THREE.Vector3(x, -0.15 + Math.sin(i * 0.6) * 0.06, Math.cos(i * 0.4) * 0.08)); }
  const mrna = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(mrnaPts), 200, 0.045, 8), new THREE.MeshPhysicalMaterial({ color: 0xe0c060, roughness: 0.3, clearcoat: 0.8, emissive: 0x3a2a08 }));
  mrna.position.x = -2.4 + 3; scene.add(mrna);
  // growing polypeptide chain (beads along a meandering path from exit tunnel)
  const chainCurve = new THREE.CatmullRomCurve3([[0, 1.2, 0], [0.4, 2.0, 0.3], [1.2, 2.4, -0.2], [1.8, 2.0, 0.6], [2.4, 2.6, 0.9], [3.0, 3.2, 0.2], [3.6, 2.8, -0.6], [4.2, 3.4, -0.2]].map(p => new THREE.Vector3(p[0] - 2.4, p[1], p[2])));
  const NC = 64;
  const aaCols = [0xb8583a, 0xc89058, 0x4a8a98, 0xa84a4a, 0x8a9a62, 0x7a6aa0].map(c => new THREE.Color(c));
  const beadMat = new THREE.MeshPhysicalMaterial({ roughness: 0.3, clearcoat: 0.9 });
  const chain = new THREE.InstancedMesh(new THREE.SphereGeometry(0.13, 20, 14), beadMat, NC);
  for (let i = 0; i < NC; i++) chain.setColorAt(i, aaCols[Math.floor(r() * aaCols.length)]);
  scene.add(chain);
  // free amino acids drifting toward the ribosome
  const NA = 120; const aas = new THREE.InstancedMesh(new THREE.SphereGeometry(0.1, 14, 10), beadMat, NA); const aab = [];
  for (let i = 0; i < NA; i++) { aab.push({ p: new THREE.Vector3(-7 + r() * 8, -3 + r() * 6, -3 + r() * 5), ph: r() }); aas.setColorAt(i, aaCols[i % aaCols.length]); }
  scene.add(aas);
  // ---- mitochondrion: translucent outer membrane + folded cristae
  const mito = new THREE.Group(); mito.position.set(3.6, -0.6, -0.8); mito.rotation.set(0.2, -0.5, 0.25); scene.add(mito);
  const outerGeo = new THREE.CapsuleGeometry(0.95, 2.6, 24, 48); outerGeo.rotateZ(Math.PI / 2);
  const outer = new THREE.Mesh(outerGeo, new THREE.MeshPhysicalMaterial({ color: 0xd86a3a, roughness: 0.35, clearcoat: 1, transparent: true, opacity: 0.38, depthWrite: false, emissive: 0x2a0a04 }));
  mito.add(outer);
  const cristaeMat = new THREE.MeshPhysicalMaterial({ color: 0xe88a4a, roughness: 0.4, clearcoat: 0.6, emissive: 0x000000, side: THREE.DoubleSide });
  for (let i = 0; i < 7; i++) {
    const g = new THREE.PlaneGeometry(1.25, 1.2, 24, 24); const pa = g.attributes.position;
    for (let k = 0; k < pa.count; k++) { const x = pa.getX(k), y = pa.getY(k); pa.setZ(k, Math.sin(y * 6 + i) * 0.12 + Math.sin(x * 4) * 0.06); }
    g.computeVertexNormals();
    const c = new THREE.Mesh(g, cristaeMat); c.rotation.y = Math.PI / 2; c.position.x = -1.2 + i * 0.4; c.scale.set(1, 0.9 + 0.1 * Math.sin(i), 1); mito.add(c);
  }
  const mGlow = new THREE.PointLight(0xffa050, 0, 6, 2); mito.add(mGlow);
  // glucose fuel stream + ATP sparks
  const gGeo = glucoseGlyphGeometry();
  const gMat = new THREE.MeshPhysicalMaterial({ color: 0xf0f6f8, roughness: 0.2, clearcoat: 1, emissive: 0x2a7a8a, emissiveIntensity: 1 });
  const NG = 40; const glu = new THREE.InstancedMesh(gGeo, gMat, NG); scene.add(glu);
  const NAt = 60; const atp = new THREE.InstancedMesh(new THREE.OctahedronGeometry(0.06, 0), new THREE.MeshBasicMaterial({ color: 0x9ff4ff }), NAt); scene.add(atp);
  const gPath = new THREE.CatmullRomCurve3([new THREE.Vector3(8, 3, 2), new THREE.Vector3(6, 1.5, 1), new THREE.Vector3(4.6, 0, 0.2), new THREE.Vector3(3.6, -0.6, -0.8)]);

  const key = new THREE.SpotLight(0xffe2cc, 110, 30, 0.75, 0.8, 1.5); key.position.set(-2, 7, 7);
  const rim = new THREE.DirectionalLight(0x60c8f0, 1.4); rim.position.set(-5, 2, -7);
  const warm = new THREE.PointLight(0xff6a3a, 6, 12, 1.6); warm.position.set(5, -3, 3);
  scene.add(key, rim, warm, new THREE.HemisphereLight(0x302838, 0x100406, 0.6));
  scene.add(bokehParticles({ count: 900, box: [26, 14, 18], center: [0, 0, -3], colors: [0xff8050, 0x60c8e0, 0xc080ff], size: 0.02, intensity: 0.8 }));

  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), sv = new THREE.Vector3(), pv = new THREE.Vector3(), e = new THREE.Euler();
  return {
    anchors: { ribosome: () => [-2.4, 1.05, 0.6], chain: () => chainCurve.getPoint(0.55).toArray(), mito: () => [3.6, -0.2, -0.2], aa: () => [-5, -1.2, 0.5], mrna: () => [-5.5, -0.15, 0] },
    scene, clear: 0x070305,
    update({ t, P }) {
      const ch = P('chain', 0.5), aa = P('aa', 0.6), fuel = P('fuel', 0), brk = P('breakdown', 0);
      const nVis = Math.floor(NC * ch);
      for (let i = 0; i < NC; i++) { const u = i / NC; const p = chainCurve.getPoint(clamp((nVis - i) / NC));
        let s = i < nVis ? 1 : 0;
        if (brk > 0 && i > nVis * (1 - brk)) { s *= 0; }
        pv.copy(p); pv.y += Math.sin(t * 1.5 + i * 0.5) * 0.03; m.compose(pv, q.identity(), sv.setScalar(s)); chain.setMatrixAt(i, m); }
      chain.instanceMatrix.needsUpdate = true;
      aab.forEach((a, i) => { const u = (a.ph + t * 0.12 * aa) % 1;
        const target = new THREE.Vector3(-2.4, 0.2, 0.3);
        pv.lerpVectors(a.p, target, u * u * aa); pv.y += Math.sin(t + i) * 0.1;
        const s = aa > 0.02 ? (1 - Math.max(0, u - 0.85) / 0.15) : 0.6;
        m.compose(pv, q.identity(), sv.setScalar(s)); aas.setMatrixAt(i, m); });
      aas.instanceMatrix.needsUpdate = true;
      for (let i = 0; i < NG; i++) { const u = ((i / NG) + t * 0.15) % 1; const p = gPath.getPoint(u);
        e.set(t + i, t * 0.7, 0); q.setFromEuler(e); m.compose(p, q, sv.setScalar(fuel > 0.01 ? 0.16 * (1 - Math.max(0, u - 0.85) / 0.15) : 0)); glu.setMatrixAt(i, m); }
      glu.instanceMatrix.needsUpdate = true;
      const at = P('atp', fuel);
      for (let i = 0; i < NAt; i++) { const u = ((i * 0.6180339) % 1 + t * 0.25) % 1; const a = i * 2.4;
        pv.set(3.6 + Math.cos(a) * (0.8 + u * 3), -0.6 + Math.sin(a) * (0.6 + u * 2.2), -0.8 + Math.sin(a * 1.7) * u * 2);
        e.set(t * 3 + i, t * 2, 0); q.setFromEuler(e); m.compose(pv, q, sv.setScalar(at * (1 - u))); atp.setMatrixAt(i, m); }
      atp.instanceMatrix.needsUpdate = true;
      cristaeMat.emissive.setRGB(0.9, 0.35, 0.08).multiplyScalar(0.15 + at * 0.6 * (0.8 + 0.2 * Math.sin(t * 4)));
      mGlow.intensity = at * 4;
      ribo.rotation.y = Math.sin(t * 0.2) * 0.08;
    },
  };
}
