// Myofibril / sarcomere close-up. Thick (myosin) filaments with helical heads,
// thin (actin) double-bead helices anchored on Z-discs, titin springs.
// Params: len (sarcomere length scale: 0.85 contracted .. 1.2 lengthened),
//         active (cross-bridge cycling 0..1), load (head glow), zglow
import { bokehParticles, rng, lerp } from '../lib.js';

export async function build({ THREE, env }) {
  const scene = new THREE.Scene();
  scene.environment = env; scene.environmentIntensity = 0.25;
  scene.fog = new THREE.FogExp2(0x0a0306, 0.075);
  const r = rng(11);
  const NS = 4, L0 = 2.4;                       // sarcomeres, rest length
  const hex = [];                                // thick filament lattice (y,z)
  for (let q = -2; q <= 2; q++) for (let s = -2; s <= 2; s++) { const y = (q + s * 0.5) * 0.42, z = s * 0.364; if (Math.hypot(y, z) < 0.95) hex.push([y, z]); }
  const thin = [];                               // thin filaments at trigonal positions
  for (const [y, z] of hex) for (const a of [0, 2.094]) { const ty = y + Math.cos(a + 0.52) * 0.242, tz = z + Math.sin(a + 0.52) * 0.242; if (Math.hypot(ty, tz) < 1.05 && !thin.some(t => Math.hypot(t[0] - ty, t[1] - tz) < 0.05)) thin.push([ty, tz]); }

  const thickMat = new THREE.MeshPhysicalMaterial({ color: 0x8a2a1c, roughness: 0.35, clearcoat: 0.6, emissive: 0x200402 });
  const headMat = new THREE.MeshPhysicalMaterial({ color: 0xc8602a, roughness: 0.3, clearcoat: 0.7, emissive: 0x000000 });
  const actinMat = new THREE.MeshPhysicalMaterial({ color: 0x6aa8b8, roughness: 0.3, clearcoat: 0.8, emissive: 0x041418 });
  const zMat = new THREE.MeshPhysicalMaterial({ color: 0xc8d8e0, roughness: 0.25, emissive: 0x1a4a58, transparent: true, opacity: 0.85 });

  const thickLen = 1.55, headsPer = 36;
  const thickGeo = new THREE.CylinderGeometry(0.045, 0.045, thickLen, 12); thickGeo.rotateZ(Math.PI / 2);
  const thickIM = new THREE.InstancedMesh(thickGeo, thickMat, NS * hex.length);
  const headGeo = new THREE.SphereGeometry(1, 10, 8); headGeo.scale(0.032, 0.015, 0.017);
  const nHeads = NS * hex.length * headsPer;
  const headIM = new THREE.InstancedMesh(headGeo, headMat, nHeads);
  const headInfo = [];
  for (let s = 0; s < NS; s++) hex.forEach(([y, z], fi) => { for (let h = 0; h < headsPer; h++) {
    const along = (h / (headsPer - 1) - 0.5) * (thickLen - 0.25); if (Math.abs(along) < 0.09) continue; // bare zone
    headInfo.push({ s, y, z, along, ang: h * 2.094 + fi, ph: r() * 6.28 }); } });
  headIM.count = headInfo.length;
  const beadsPer = 34, actinLen = 1.05;
  const beadGeo = new THREE.IcosahedronGeometry(0.026, 1);
  const nBeads = NS * 2 * thin.length * beadsPer * 2;
  const actinIM = new THREE.InstancedMesh(beadGeo, actinMat, nBeads);
  const zGroup = new THREE.Group();
  const zDiscs = [];
  for (let s = 0; s <= NS; s++) {
    const d = new THREE.Group();
    const ring = new THREE.Mesh(new THREE.TorusGeometry(1.08, 0.025, 8, 64), zMat); ring.rotation.y = Math.PI / 2; d.add(ring);
    const plate = new THREE.Mesh(new THREE.CircleGeometry(1.06, 64), new THREE.MeshBasicMaterial({ color: 0x3a8090, transparent: true, opacity: 0.05, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending }));
    plate.rotation.y = Math.PI / 2; d.add(plate);
    zGroup.add(d); zDiscs.push(d);
  }
  // titin: thin coiled springs from Z to M
  const titinMat = new THREE.LineBasicMaterial({ color: 0xffd0a0, transparent: true, opacity: 0.35 });
  const titins = [];
  for (let s = 0; s < NS; s++) for (const side of [-1, 1]) for (let k = 0; k < 6; k++) {
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(60 * 3), 3));
    const l = new THREE.Line(g, titinMat); titins.push({ l, s, side, a: k / 6 * 6.28 }); scene.add(l);
  }
  // surrounding sarcoplasmic reticulum sleeve (translucent)
  const sleeve = new THREE.Mesh(new THREE.CylinderGeometry(1.35, 1.35, 14, 64, 1, true), new THREE.MeshPhysicalMaterial({ color: 0x5a1a20, roughness: 0.4, transparent: true, opacity: 0.18, side: THREE.BackSide, depthWrite: false }));
  sleeve.rotation.z = Math.PI / 2;
  scene.add(thickIM, headIM, actinIM, zGroup, sleeve);
  // neighbouring myofibrils in background for depth
  const bgMat = new THREE.MeshStandardMaterial({ color: 0x4a1410, roughness: 0.6, emissive: 0x0a0202 });
  for (let i = 0; i < 6; i++) { const c = new THREE.Mesh(new THREE.CylinderGeometry(1.1, 1.1, 22, 32, 1, true), bgMat); c.rotation.z = Math.PI / 2; const a = i / 6 * 6.28 + 0.3; c.position.set(0, Math.cos(a) * 3.0, Math.sin(a) * 1.4 - 3.4); scene.add(c); }

  const key = new THREE.DirectionalLight(0xffd8c0, 1.6); key.position.set(3, 5, 4);
  const rim = new THREE.DirectionalLight(0x60c8e8, 1.4); rim.position.set(-4, -1, -5);
  const fill = new THREE.HemisphereLight(0x402028, 0x080204, 0.8);
  const glowL = new THREE.PointLight(0xff8040, 0, 5, 2);
  scene.add(key, rim, fill, glowL);
  scene.add(bokehParticles({ count: 700, box: [20, 10, 12], center: [0, 0, 0], colors: [0xff7040, 0x70d0e0, 0xffc080], size: 0.012, intensity: 0.8 }));

  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), sv = new THREE.Vector3(), pv = new THREE.Vector3();
  let LsNow = L0;
  return {
    anchors: { z: () => [-NS * LsNow / 2 + LsNow, 1.08, 0], myosin: () => [-NS * LsNow / 2 + LsNow * 1.5 + 0.45, 0.42, 0.18], actin: () => [-NS * LsNow / 2 + LsNow * 2 + 0.35, -0.5, 0.36],
      m: () => [-NS * LsNow / 2 + LsNow * 2.5, -0.9, 0.2], titin: () => [-NS * LsNow / 2 + LsNow * 2.25, 0.75, 0] },
    scene, clear: 0x080205,
    update({ t, P }) {
      const len = P('len', 1), active = P('active', 0.6), load = P('load', 0);
      const Ls = L0 * len, x0 = -NS * Ls / 2; LsNow = Ls;
      // Z discs
      zDiscs.forEach((d, i) => { d.position.x = x0 + i * Ls; });
      zMat.emissive.setRGB(0.1, 0.29, 0.35).multiplyScalar(0.6 + P('zglow', 0) * 2);
      // thick filaments centred in each sarcomere (M-line)
      let k = 0;
      for (let s = 0; s < NS; s++) { const cx = x0 + (s + 0.5) * Ls; for (const [y, z] of hex) { m.makeTranslation(cx, y, z); thickIM.setMatrixAt(k++, m); } }
      thickIM.instanceMatrix.needsUpdate = true;
      // myosin heads: power-stroke rotation cycling
      headInfo.forEach((h, i) => {
        const cx = x0 + (h.s + 0.5) * Ls + h.along;
        const cyc = (Math.sin(t * 7 * active + h.ph) * 0.5 + 0.5);
        const dir = Math.sign(h.along) || 1;
        const tilt = (0.9 - 0.7 * cyc * active) * -dir;
        pv.set(cx, h.y + Math.cos(h.ang) * 0.065, h.z + Math.sin(h.ang) * 0.065);
        e.set(h.ang, 0, tilt); q.setFromEuler(e); sv.set(1, 1, 1);
        m.compose(pv, q, sv); headIM.setMatrixAt(i, m);
      });
      headIM.instanceMatrix.needsUpdate = true;
      headMat.emissive.setRGB(0.9, 0.3, 0.06).multiplyScalar(load * 0.9 * (0.75 + 0.25 * Math.sin(t * 9)));
      glowL.intensity = load * 6; glowL.position.set(0, 0, 1.5);
      // thin filaments: double helix beads from each Z disc inward
      k = 0;
      for (let s = 0; s < NS; s++) for (const side of [0, 1]) {
        const zx = x0 + (s + side) * Ls, dir = side ? -1 : 1;
        for (const [y, z] of thin) for (let b = 0; b < beadsPer; b++) for (const st of [0, 1]) {
          const a = b * 0.48 + st * Math.PI + y * 3;
          pv.set(zx + dir * (b + st * 0.5) * actinLen / beadsPer, y + Math.cos(a) * 0.022, z + Math.sin(a) * 0.022);
          m.makeTranslation(pv.x, pv.y, pv.z); actinIM.setMatrixAt(k++, m);
        }
      }
      actinIM.count = k; actinIM.instanceMatrix.needsUpdate = true;
      // titin springs (coil compresses/extends with length)
      titins.forEach(T => {
        const zx = x0 + (T.s + (T.side > 0 ? 0 : 1)) * Ls, mx = x0 + (T.s + 0.5) * Ls;
        const arr = T.l.geometry.attributes.position.array;
        for (let i = 0; i < 60; i++) { const u = i / 59; const x = lerp(zx, mx, u); const a = T.a + u * 30;
          arr[i * 3] = x; arr[i * 3 + 1] = Math.cos(T.a) * 0.75 + Math.cos(a) * 0.03; arr[i * 3 + 2] = Math.sin(T.a) * 0.75 + Math.sin(a) * 0.03; }
        T.l.geometry.attributes.position.needsUpdate = true;
      });
    },
  };
}
