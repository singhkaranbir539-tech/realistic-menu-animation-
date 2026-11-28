// Capillary/arteriole interior fly-through. Biconcave erythrocytes (Evans-Fung
// profile), glucose molecules, optional insulin (protein clusters), endothelial wall.
// Vessel axis runs along -z; camera moves along z. Params: flow, glucose, insulin, toWall
import { tissueMaterial, bokehParticles, rng, glucoseGlyphGeometry, proteinBlob, lerp } from '../lib.js';

export async function build({ THREE, env }) {
  const scene = new THREE.Scene();
  scene.environment = env; scene.environmentIntensity = 0.3;
  scene.fog = new THREE.FogExp2(0x1a0306, 0.06);
  const r = rng(21);
  const RAD = 3.2, LEN = 90;
  // vessel wall: displaced tube, viewed from inside
  const wallGeo = new THREE.CylinderGeometry(RAD, RAD, LEN, 160, 260, true);
  const pa = wallGeo.attributes.position;
  for (let i = 0; i < pa.count; i++) {
    const x = pa.getX(i), y = pa.getY(i), z = pa.getZ(i);
    const a = Math.atan2(z, x);
    const d = 1 + 0.06 * Math.sin(a * 5 + y * 0.35) + 0.04 * Math.sin(a * 11 - y * 0.8) + 0.12 * Math.sin(y * 0.11);
    pa.setXYZ(i, x * d, y, z * d);
  }
  wallGeo.computeVertexNormals(); wallGeo.rotateX(Math.PI / 2);
  const wallMat = tissueMaterial({ color: 0x9a3a34, varColor: 0x5a1418, axis: [0, 0, 1], fibreFreq: 2.2, fibre: 0.5, bump: 1.2, bumpScale: 2.5,
    sss: 0xff5a48, sssAmt: 0.55, clearcoat: 0.9, clearcoatRoughness: 0.2, side: THREE.BackSide, roughness: 0.38 });
  const wall = new THREE.Mesh(wallGeo, wallMat); wall.position.z = -LEN / 2 + 10; scene.add(wall);

  // erythrocyte: Evans-Fung biconcave profile, lathe
  const prof = [];
  for (let i = 0; i <= 28; i++) {
    const x = i / 28; const R0 = 0.42;
    const hz = R0 * 0.5 * Math.sqrt(Math.max(0, 1 - x * x)) * (0.207 + 2.003 * x * x - 1.123 * x ** 4);
    prof.push(new THREE.Vector2(Math.max(0.001, x * R0), hz));
  }
  for (let i = 27; i >= 0; i--) { const p = prof[i]; prof.push(new THREE.Vector2(p.x, -p.y)); }
  const rbcGeo = new THREE.LatheGeometry(prof, 48); rbcGeo.computeVertexNormals();
  const rbcMat = tissueMaterial({ color: 0xa81812, varColor: 0x6a0808, fibre: 0.0, bump: 0.25, bumpScale: 22, sss: 0xff2a10, sssAmt: 0.9,
    clearcoat: 0.6, clearcoatRoughness: 0.35, roughness: 0.45, axis: [0, 1, 0] });
  const NR = 420;
  const rbc = new THREE.InstancedMesh(rbcGeo, rbcMat, NR);
  const rbcs = [];
  for (let i = 0; i < NR; i++) { const a = r() * 6.28, d = Math.sqrt(r()) * (RAD - 0.6);
    rbcs.push({ x: Math.cos(a) * d, y: Math.sin(a) * d, z: 12 - r() * 70, sp: 0.8 + r() * 0.5, rx: r() * 6, ry: r() * 6, wr: (r() - .5) * 1.2, s: 0.9 + r() * 0.2 }); }
  scene.add(rbc);
  // glucose glyphs
  const gGeo = glucoseGlyphGeometry();
  const gMat = new THREE.MeshPhysicalMaterial({ color: 0xe8f4f8, roughness: 0.15, clearcoat: 1, emissive: 0x2a7a8a, emissiveIntensity: 0.7, transparent: true });
  const NG = 360; const glu = new THREE.InstancedMesh(gGeo, gMat, NG); const glus = [];
  for (let i = 0; i < NG; i++) { const a = r() * 6.28, d = Math.sqrt(r()) * (RAD - 0.4);
    glus.push({ x: Math.cos(a) * d, y: Math.sin(a) * d, z: 12 - r() * 70, sp: 1 + r() * 0.6, rx: r() * 6, ry: r() * 6, s: 0.13 + r() * 0.05 }); }
  scene.add(glu);
  // insulin / plasma proteins (clustered blobs, cool blue like the reference look)
  const insulin = new THREE.Group(); const ins = [];
  for (let i = 0; i < 14; i++) {
    const b = proteinBlob((x, y, z) => Math.hypot(x * 1.2, y, z * 0.9) - 0.32 - 0.08 * Math.sin(x * 9) * Math.cos(z * 7), { count: 260, bounds: [[-.5, -.5, -.5], [.5, .5, .5]], r0: 0.025, r1: 0.045,
      colors: [0x2a70d0, 0x30c0c8], seed: 40 + i, shell: 0.08 });
    const a = r() * 6.28, d = Math.sqrt(r()) * (RAD - 0.8);
    b.position.set(Math.cos(a) * d, Math.sin(a) * d, 10 - r() * 60); insulin.add(b); ins.push({ b, z: b.position.z, sp: 0.9 + r() * 0.3, rx: r() * 6 });
  }
  scene.add(insulin);

  const headlamp = new THREE.PointLight(0xffd8c8, 9, 18, 1.6);
  const key = new THREE.DirectionalLight(0xffc0a0, 0.9); key.position.set(2, 4, 3);
  const rim = new THREE.DirectionalLight(0x6ac8e8, 0.35); rim.position.set(-3, -2, -6);
  const amb = new THREE.HemisphereLight(0x6a2a2a, 0x200406, 0.9);
  scene.add(headlamp, key, rim, amb);
  scene.add(bokehParticles({ count: 900, box: [6, 6, 70], center: [0, 0, -20], colors: [0xffb0a0, 0xffffff, 0x80d0e0], size: 0.008, intensity: 0.6 }));

  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), sv = new THREE.Vector3(), pv = new THREE.Vector3();
  const keepOut = (pv, cam, need0) => { const dz = cam.position.z - pv.z; if (dz > -0.5 && dz < 3.5) { const dx = pv.x - cam.position.x, dy = pv.y - cam.position.y, rr = Math.hypot(dx, dy) || 1e-3;
    const need = need0 * (1 - Math.max(0, dz - 1.5) / 2); if (rr < need) { pv.x = cam.position.x + dx / rr * need; pv.y = cam.position.y + dy / rr * need; } } };
  const wrapZ = (z, cz) => { const span = 70; let d = z - (cz - span + 12); d = ((d % span) + span) % span; return cz - span + 12 + d; };
  return {
    scene, clear: 0x120406,
    update({ t, P, cam }) {
      const flow = P('flow', 1), gl = P('glucose', 1), insA = P('insulin', 0);
      const cz = cam.position.z;
      headlamp.position.copy(cam.position);
      rbcs.forEach((c, i) => {
        const z = wrapZ(c.z + t * flow * 2.2 * c.sp, cz);
        pv.set(c.x + Math.sin(t * 0.4 + i) * 0.1, c.y + Math.cos(t * 0.33 + i) * 0.1, z);
        { const dz = cam.position.z - z; if (dz > -0.5 && dz < 3.5) { const dx = pv.x - cam.position.x, dy = pv.y - cam.position.y, rr = Math.hypot(dx, dy) || 1e-3;
          const need = 1.3 * (1 - Math.max(0, dz - 1.5) / 2); if (rr < need) { pv.x = cam.position.x + dx / rr * need; pv.y = cam.position.y + dy / rr * need; } } }
        e.set(c.rx + t * c.wr * 0.4, c.ry + t * 0.15, 0); q.setFromEuler(e); sv.setScalar(c.s);
        m.compose(pv, q, sv); rbc.setMatrixAt(i, m);
      });
      rbc.instanceMatrix.needsUpdate = true;
      glu.count = Math.round(NG * gl);
      glus.forEach((g, i) => {
        if (i >= glu.count) return;
        const z = wrapZ(g.z + t * flow * 2.6 * g.sp, cz);
        pv.set(g.x + Math.sin(t + i) * 0.15, g.y + Math.cos(t * 0.8 + i) * 0.15, z); keepOut(pv, cam, 0.9);
        e.set(g.rx + t * 0.9, g.ry + t * 0.7, 0); q.setFromEuler(e); sv.setScalar(g.s * (0.6 + 0.4 * gl));
        m.compose(pv, q, sv); glu.setMatrixAt(i, m);
      });
      glu.instanceMatrix.needsUpdate = true;
      gMat.emissiveIntensity = 0.5 + P('gglow', 0.4);
      insulin.visible = insA > 0.01;
      ins.forEach((o, i) => { o.b.position.z = wrapZ(o.z + t * flow * 2.0 * o.sp, cz); keepOut(o.b.position, cam, 1.4); o.b.rotation.set(o.rx + t * 0.3, t * 0.2, 0); o.b.scale.setScalar(insA); });
      wallMat.userData.u.uTime.value = t;
    },
  };
}
