// Skeletal-muscle cell membrane cutaway (conceptual): insulin receptor dimer,
// insulin docking, intracellular signal relay, GLUT4 vesicle translocation and
// glucose entry through GLUT4 transporters.
// Params: dock (0..1), signal (0..1), glut (0..1), uptake (0..1), glucose
import { proteinBlob, glucoseGlyphGeometry, bokehParticles, rng, ellipsoid, capsule, smin, clamp, lerp, ease } from '../lib.js';

export async function build({ THREE, env }) {
  const scene = new THREE.Scene();
  scene.environment = env; scene.environmentIntensity = 0.3;
  scene.fog = new THREE.FogExp2(0x0a0508, 0.045);
  const r = rng(41);
  const X = 11, Z = 6.5, SP = 0.19;
  // ---- lipid bilayer: two leaflets of instanced head groups
  const headGeo = new THREE.IcosahedronGeometry(0.1, 1);
  const lipidMat = new THREE.MeshPhysicalMaterial({ color: 0xb08470, roughness: 0.6, clearcoat: 0.15, clearcoatRoughness: 0.5, emissive: 0x140604 });
  const heads = [];
  for (let iz = 0; iz * SP * 0.866 < 2 * Z; iz++) for (let ix = 0; ix * SP < 2 * X; ix++) {
    const x = -X + ix * SP + (iz % 2) * SP / 2, z = -Z + iz * SP * 0.866;
    if (Math.hypot(x, z) < 0.55) continue;
    heads.push([x, z, r()]);
  }
  const lip = new THREE.InstancedMesh(headGeo, lipidMat, heads.length * 2);
  const lipC = new THREE.Color();
  heads.forEach((h, i) => { for (const L of [0, 1]) { lipC.setHSL(0.03 + h[2] * 0.04, 0.35, 0.5 + h[2] * 0.12); lip.setColorAt(i * 2 + L, lipC); } });
  scene.add(lip);
  // cut face showing hydrophobic tails
  const cut = new THREE.Mesh(new THREE.PlaneGeometry(2 * X, 0.62, 1, 1), new THREE.ShaderMaterial({
    uniforms: { uT: { value: 0 } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: `varying vec2 vUv; uniform float uT; void main(){ float x=vUv.x*115.0; float y=vUv.y;
      float tails=smoothstep(0.35,0.0,abs(fract(x)-0.5))*(1.0-smoothstep(0.38,0.5,abs(y-0.5)))*step(0.12,abs(y-0.5)+0.12);
      float wav=sin(y*40.0+x*0.7)*0.15; vec3 c=mix(vec3(0.18,0.08,0.05),vec3(0.75,0.55,0.35),tails*(0.6+wav));
      gl_FragColor=vec4(c*0.55,1.0); }` }));
  cut.position.set(0, 0, Z); scene.add(cut);

  // ---- insulin receptor (conceptual dimer: extracellular arms, TM helices, kinase domains)
  const recSDF = (x, y, z) => {
    let d = ellipsoid(x, y, z, [-0.45, 1.15, 0], [0.32, 0.55, 0.38]);
    d = smin(d, ellipsoid(x, y, z, [0.45, 1.15, 0], [0.32, 0.55, 0.38]), 0.15);
    d = smin(d, ellipsoid(x, y, z, [0, 1.75, 0], [0.62, 0.25, 0.42]), 0.2);
    d = smin(d, capsule(x, y, z, [-0.18, 0.6, 0], [-0.18, -0.55, 0], 0.09), 0.08);
    d = smin(d, capsule(x, y, z, [0.18, 0.6, 0], [0.18, -0.55, 0], 0.09), 0.08);
    return d;
  };
  const receptor = proteinBlob(recSDF, { count: 4200, bounds: [[-1, -0.7, -0.6], [1, 2.1, 0.6]], r0: 0.035, r1: 0.06, colors: [0x1a6ab0, 0x38b8d0], seed: 7, shell: 0.1 });
  scene.add(receptor);
  const kinSDF = (x, y, z) => smin(ellipsoid(x, y, z, [-0.42, -0.95, 0.05], [0.34, 0.3, 0.32]), ellipsoid(x, y, z, [0.42, -0.95, -0.05], [0.34, 0.3, 0.32]), 0.1);
  const kinMat = new THREE.MeshStandardMaterial({ roughness: 0.38, emissive: 0x000000 });
  const kinase = proteinBlob(kinSDF, { count: 1500, bounds: [[-0.9, -1.35, -0.45], [0.9, -0.55, 0.45]], r0: 0.035, r1: 0.06, colors: [0x2060a8, 0x3090c8], seed: 8, shell: 0.12, material: kinMat });
  scene.add(kinase);
  // ---- insulin
  const insulin = proteinBlob((x, y, z) => Math.hypot(x, y * 1.15, z) - 0.28 - 0.05 * Math.sin(x * 10 + z * 6), { count: 420, bounds: [[-.4, -.4, -.4], [.4, .4, .4]], r0: 0.028, r1: 0.045,
    colors: [0xe8602a, 0xffa040], seed: 9, shell: 0.1 });
  scene.add(insulin);
  // ---- signal relay pulses
  const vesPos = [[-3.2, -2.6, 1.2], [2.8, -2.8, 0.4], [-1.2, -3.1, -1.5], [4.6, -2.4, 2.2]];
  const curves = vesPos.map(v => new THREE.CatmullRomCurve3([new THREE.Vector3(0, -1.1, 0), new THREE.Vector3(v[0] * 0.3, -1.9, v[2] * 0.4 + 0.5), new THREE.Vector3(v[0] * 0.7, v[1] + 0.2, v[2] * 0.8), new THREE.Vector3(...v)]));
  const pulseMat = new THREE.MeshBasicMaterial({ color: 0x9ff0ff });
  const NP = 48; const pulses = new THREE.InstancedMesh(new THREE.SphereGeometry(0.06, 12, 8), pulseMat, NP); scene.add(pulses);
  const trailMat = new THREE.MeshBasicMaterial({ color: 0x2a8090, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
  curves.forEach(c => scene.add(new THREE.Mesh(new THREE.TubeGeometry(c, 80, 0.012, 6), trailMat)));
  // ---- GLUT4 storage vesicles -> membrane
  const vesicles = vesPos.map((p, i) => {
    const g = new THREE.Group();
    const shell = proteinBlob((x, y, z) => Math.hypot(x, y, z) - 0.5, { count: 700, bounds: [[-.6, -.6, -.6], [.6, .6, .6]], r0: 0.035, r1: 0.05, colors: [0xb88a78, 0xd8aa90], seed: 60 + i, shell: 0.06 });
    const glut = proteinBlob((x, y, z) => Math.hypot(x, y * 0.7, z) - 0.16, { count: 160, bounds: [[-.25, -.3, -.25], [.25, .3, .25]], r0: 0.02, r1: 0.035, colors: [0x8a5ad0, 0xb080f0], seed: 70 + i, shell: 0.08 });
    glut.position.set(0, 0.5, 0); g.add(shell, glut); g.position.set(...p); scene.add(g);
    return { g, shell, glut, p };
  });
  // ---- glucose
  const gGeo = glucoseGlyphGeometry();
  const gMat = new THREE.MeshPhysicalMaterial({ color: 0xf0f6f8, roughness: 0.2, clearcoat: 1, emissive: 0x2a7080, emissiveIntensity: 0.9 });
  const NG = 70; const glu = new THREE.InstancedMesh(gGeo, gMat, NG); const gl = [];
  for (let i = 0; i < NG; i++) gl.push({ x: -X + r() * 2 * X, y: 0.8 + r() * 4, z: -Z + r() * 2 * Z * 0.9, ph: r() * 6.28, tgt: i % vesPos.length, d: r() });
  scene.add(glu);
  // ---- light
  const key = new THREE.SpotLight(0xffe0c8, 120, 40, 0.75, 0.8, 1.5); key.position.set(4, 9, 8);
  const rim = new THREE.DirectionalLight(0x60c8f0, 1.4); rim.position.set(-6, 3, -8);
  const under = new THREE.PointLight(0xff5a3a, 10, 14, 1.6); under.position.set(0, -4, 3);
  scene.add(key, rim, under, new THREE.HemisphereLight(0x2a2030, 0x200608, 0.6));
  scene.add(bokehParticles({ count: 800, box: [26, 14, 18], center: [0, 0, -2], colors: [0x60c8e0, 0xff7050, 0xffd0b0], size: 0.02, intensity: 0.8 }));

  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), sv = new THREE.Vector3(), pv = new THREE.Vector3();
  return {
    anchors: { receptor: () => [0.5, 1.6, 0.3], insulin: () => insulin.position.toArray(), kinase: () => [0.5, -1.0, 0.3], glut: () => vesicles[1].g.position.toArray(),
      membrane: () => [-5, 0.3, 3], interior: () => [-6, -2.5, 2], outside: () => [-6, 3.2, 1] },
    scene, clear: 0x070406,
    update({ t, P }) {
      const dock = P('dock', 0), sig = P('signal', 0), glut = P('glut', 0), up = P('uptake', 0);
      // membrane undulation
      heads.forEach((h, i) => { const w = Math.sin(h[0] * 0.6 + t * 0.6) * 0.05 + Math.sin(h[1] * 0.8 - t * 0.4) * 0.04;
        for (const L of [0, 1]) { pv.set(h[0], (L ? -0.26 : 0.26) + w, h[1]); m.makeTranslation(pv.x, pv.y, pv.z); lip.setMatrixAt(i * 2 + L, m); } });
      lip.instanceMatrix.needsUpdate = true;
      // insulin path to binding site
      const k = ease.inOut(dock);
      insulin.position.set(lerp(-3.5, 0, k), lerp(4.2, 2.18, k) + Math.sin(t * 1.3) * 0.05 * (1 - k), lerp(1.5, 0.15, k));
      insulin.rotation.set(t * 0.4 * (1 - k), t * 0.3 * (1 - k), 0);
      insulin.visible = P('insulin', 1) > 0.5;
      receptor.rotation.y = Math.sin(t * 0.2) * 0.05;
      kinMat.emissive.setRGB(1.0, 0.45, 0.1).multiplyScalar(sig * (0.5 + 0.2 * Math.sin(t * 6)));
      // pulses
      for (let i = 0; i < NP; i++) { const c = curves[i % curves.length]; const u = ((t * 0.45 + i / NP * 3) % 1);
        const p = c.getPoint(u); const s = sig > 0.02 ? 1 : 0; m.compose(p, q.identity(), sv.setScalar(s * (0.6 + 0.6 * Math.sin(u * Math.PI)))); pulses.setMatrixAt(i, m); }
      pulses.instanceMatrix.needsUpdate = true; trailMat.opacity = sig * 0.6; pulseMat.color.setRGB(0.6 + sig, 0.94, 1);
      // vesicles rise and fuse; GLUT4 left in membrane
      vesicles.forEach((v, i) => { const kk = ease.inOut(clamp(glut * 1.2 - i * 0.07));
        v.g.position.set(v.p[0], lerp(v.p[1], -0.15, kk), v.p[2]);
        v.shell.scale.set(1 + kk * 0.6, 1 - kk * 0.85, 1 + kk * 0.6); v.glut.position.y = lerp(0.5, 0.15, kk); });
      // glucose drifting; with uptake, molecules funnel through the transporters
      gl.forEach((g, i) => {
        const v = vesicles[g.tgt]; const tx = v.p[0], tz = v.p[2];
        const ph = ((t * 0.18 + g.d) % 1);
        let x = g.x + Math.sin(t * 0.3 + g.ph) * 0.4, y = g.y + Math.sin(t * 0.5 + g.ph) * 0.2, z = g.z;
        if (up > 0 && i % 2 === 0) { const u = ph; x = lerp(x, tx, Math.min(1, u * 1.6) * up); z = lerp(z, tz, Math.min(1, u * 1.6) * up); y = lerp(y, lerp(1.2, -3.5, clamp((u - 0.55) * 2.2)), up * Math.min(1, u * 1.3)); }
        e.set(t * 0.8 + g.ph, t * 0.6, 0); q.setFromEuler(e); m.compose(pv.set(x, y, z), q, sv.setScalar(0.17 * P('glucose', 1))); glu.setMatrixAt(i, m);
      });
      glu.instanceMatrix.needsUpdate = true;
    },
  };
}
