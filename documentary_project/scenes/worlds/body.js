// Anonymous athletic human figure built from a signed-distance anatomy model.
// Skin layer (subsurface-approximated) can dissolve into an x-ray shell that
// reveals the musculature underneath (fibrous tissue + wireframe topology).
// The right arm is a separate rig (shoulder/elbow) for biceps-curl animation.
// Params: xray (0 skin..1 x-ray), curl (0 extended..1 flexed), dumbbell, glowArm, hyper, emerge
import { tissueMaterial, fresnelMaterial, bokehParticles, sdfMesh, smin, capsule, ellipsoid, rng, clamp } from '../lib.js';

function torsoSDF(x, y, z, o = 0) {
  const X = Math.abs(x);
  let d = ellipsoid(X, y, z, [0, 0.38, 0], [0.18, 0.2, 0.112]);                            // rib cage (V-taper)
  d = smin(d, ellipsoid(X, y, z, [0, 0.14, 0.005], [0.122, 0.19, 0.09]), 0.07);            // narrow waist
  d = smin(d, ellipsoid(X, y, z, [0, -0.08, 0], [0.142, 0.12, 0.098]), 0.07);
  d = smin(d, ellipsoid(X, y, z, [0.088, 0.425, 0.072], [0.098, 0.068, 0.05]), 0.025);    // pectorals (defined lower border)
  d = smin(d, ellipsoid(X, y, z, [0.14, 0.31, -0.02], [0.08, 0.16, 0.085]), 0.05);         // lats
  for (let i = 0; i < 3; i++) d = smin(d, ellipsoid(X, y, z, [0.135, 0.34 - i * 0.04, 0.06], [0.03, 0.016, 0.03]), 0.02); // serratus
  d = smin(d, capsule(X, y, z, [0.03, 0.6, -0.03], [0.17, 0.545, -0.02], 0.05), 0.06);      // trapezius
  d = smin(d, capsule(X, y, z, [0, 0.55, 0], [0, 0.71, 0.012], 0.056), 0.05);               // neck
  d = smin(d, ellipsoid(X, y, z, [0.055, 0.64, 0.02], [0.02, 0.08, 0.02]), 0.03);           // sternocleidomastoid
  d = smin(d, ellipsoid(X, y, z, [0, 0.83, 0.02], [0.083, 0.108, 0.098]), 0.05);            // head (featureless)
  d = smin(d, ellipsoid(X, y, z, [0.215, 0.525, 0], [0.078, 0.078, 0.075]), 0.035);          // deltoid
  for (let i = 0; i < 3; i++) d = smin(d, ellipsoid(X, y, z, [0.038, 0.24 - i * 0.07, 0.078], [0.033, 0.03, 0.022]), 0.012); // rectus abdominis
  if (y > 0.02 && y < 0.31) d = Math.max(d, -(Math.hypot(x, (z - 0.1) * 0.6) - 0.005));                          // linea alba groove
  d = smin(d, ellipsoid(X, y, z, [0.11, 0.18, 0.04], [0.045, 0.12, 0.06]), 0.05);           // obliques
  d = smin(d, capsule(X, y, z, [0.085, -0.12, 0.0], [0.1, -0.7, 0.02], [0.095, 0.06]), 0.05); // thighs
  return d - o;
}
export function upperArmSDF(x, y, z, o = 0) { // shoulder at origin, elbow at (0,-0.28,0)
  let d = capsule(x, y, z, [0, 0, 0], [0, -0.28, 0], [0.052, 0.04]);
  d = smin(d, ellipsoid(x, y, z, [0, -0.15, 0.03], [0.042, 0.09, 0.045]), 0.03);           // biceps
  d = smin(d, ellipsoid(x, y, z, [0, -0.12, -0.03], [0.045, 0.1, 0.042]), 0.03);           // triceps
  d = smin(d, ellipsoid(x, y, z, [0, -0.01, 0], [0.07, 0.07, 0.068]), 0.04);               // deltoid cap
  return d - o;
}
export function forearmSDF(x, y, z, o = 0) { // elbow at origin, wrist at (0,-0.25,0)
  let d = capsule(x, y, z, [0, 0, 0], [0, -0.25, 0.005], [0.043, 0.027]);
  d = smin(d, ellipsoid(x, y, z, [0.012, -0.06, 0.01], [0.04, 0.075, 0.038]), 0.03);       // brachioradialis / flexors
  d = smin(d, ellipsoid(x, y, z, [0, -0.3, 0.01], [0.032, 0.045, 0.045]), 0.03);           // closed fist
  return d - o;
}

export async function build({ THREE, env }) {
  const scene = new THREE.Scene();
  scene.environment = env; scene.environmentIntensity = 0.12;
  scene.fog = new THREE.FogExp2(0x050507, 0.08);
  const mk = (sdf, res, c, h, o) => sdfMesh((x, y, z) => sdf(x, y, z, o), { res, c, h });
  const torsoMus = mk(torsoSDF, 150, [0, 0.07, 0], 0.82, 0);
  const torsoSkin = mk(torsoSDF, 128, [0, 0.07, 0], 0.82, 0.008);
  const torsoWire = mk(torsoSDF, 56, [0, 0.07, 0], 0.82, 0.002);
  const uaM = mk(upperArmSDF, 80, [0, -0.14, 0], 0.2, 0), uaS = mk(upperArmSDF, 70, [0, -0.14, 0], 0.2, 0.008), uaW = mk(upperArmSDF, 34, [0, -0.14, 0], 0.2, 0.002);
  const faM = mk(forearmSDF, 80, [0, -0.16, 0], 0.21, 0), faS = mk(forearmSDF, 70, [0, -0.16, 0], 0.21, 0.008), faW = mk(forearmSDF, 34, [0, -0.16, 0], 0.21, 0.002);

  const mkMus = () => tissueMaterial({ color: 0x7a160e, varColor: 0x2a0404, axis: [0, 1, 0], fibreFreq: 90, fibre: 0.9, stri: 0.0, bump: 0.9, bumpScale: 40,
    sss: 0xff3a14, sssAmt: 0.45, clearcoat: 0.7, clearcoatRoughness: 0.25, roughness: 0.4 });
  const muscleMat = mkMus(), armRMat = mkMus(), armLMat = mkMus();
  const skinMat = tissueMaterial({ color: 0x8a5040, varColor: 0x5a2a1c, axis: [0, 1, 0], fibre: 0.02, fibreFreq: 200, bump: 0.06, bumpScale: 90,
    sss: 0xff6040, sssAmt: 0.35, clearcoat: 0.15, clearcoatRoughness: 0.5, roughness: 0.55, sheen: 0.3, sheenColor: 0xffc0a0, varAmt: 0.25,
    transparent: true, depthWrite: true });
  const xrayMat = fresnelMaterial({ color: 0xa8c8dc, power: 2.6, amount: 0, base: 0.004 });
  const wireMat = new THREE.MeshBasicMaterial({ color: 0xff7a3a, wireframe: true, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });

  const fig = new THREE.Group(); scene.add(fig);
  const layer = (geo, mm = muscleMat) => {
    const g = new THREE.Group();
    const m = new THREE.Mesh(geo.m, mm); m.castShadow = m.receiveShadow = true;
    const s = new THREE.Mesh(geo.s, skinMat); s.castShadow = true;
    const x = new THREE.Mesh(geo.s, xrayMat);
    const w = new THREE.Mesh(geo.w, wireMat);
    g.add(m, s, x, w); g.userData = { m, s, x, w }; return g;
  };
  fig.add(layer({ m: torsoMus, s: torsoSkin, w: torsoWire }));
  // arms: left arm static, right arm rigged
  const mkArm = (side, mm) => {
    const shoulder = new THREE.Group(); shoulder.position.set(0.215 * side, 0.52, 0);
    const ua = layer({ m: uaM, s: uaS, w: uaW }, mm); shoulder.add(ua);
    const elbow = new THREE.Group(); elbow.position.set(0, -0.28, 0); shoulder.add(elbow);
    const fa = layer({ m: faM, s: faS, w: faW }, mm); elbow.add(fa);
    fig.add(shoulder); return { shoulder, elbow, ua, fa };
  };
  const armR = mkArm(-1, armRMat), armL = mkArm(1, armLMat);
  // dumbbell (brushed steel + rubber plates)
  const steel = new THREE.MeshPhysicalMaterial({ color: 0x9aa0a6, metalness: 1, roughness: 0.32, clearcoat: 0.3 });
  const rubber = new THREE.MeshPhysicalMaterial({ color: 0x141416, roughness: 0.6, metalness: 0.1, sheen: 0.3 });
  const db = new THREE.Group();
  const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.27, 32), steel); bar.rotation.z = Math.PI / 2; db.add(bar);
  for (const s of [-1, 1]) { const p = new THREE.Mesh(new THREE.CylinderGeometry(0.052, 0.052, 0.045, 48), rubber); p.rotation.z = Math.PI / 2; p.position.x = s * 0.1; db.add(p);
    const c = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.05, 32), steel); c.rotation.z = Math.PI / 2; c.position.x = s * 0.1; db.add(c); }
  db.position.set(0, -0.3, 0.01); armR.elbow.add(db);
  const dbL = db.clone(); armL.elbow.add(dbL);

  // floor for contact shadows (dark studio)
  const floor = new THREE.Mesh(new THREE.CircleGeometry(6, 64), new THREE.MeshStandardMaterial({ color: 0x0a0a0c, roughness: 0.85 }));
  floor.rotation.x = -Math.PI / 2; floor.position.y = -0.72; floor.receiveShadow = true; scene.add(floor);

  // lighting: high warm key, two rims (warm + cyan), low fill
  const key = new THREE.SpotLight(0xffd2b0, 11, 12, 0.5, 0.8, 1.5); key.position.set(1.6, 2.6, 2.2); key.target.position.set(0, 0.3, 0);
  key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0004; key.shadow.normalBias = 0.01;
  const rimW = new THREE.SpotLight(0xff8a50, 22, 10, 0.6, 0.6, 1.5); rimW.position.set(-2.2, 1.6, -1.6); rimW.target.position.set(0, 0.3, 0);
  const rimC = new THREE.SpotLight(0x70c8ff, 14, 10, 0.6, 0.6, 1.5); rimC.position.set(2.4, 1.2, -1.8); rimC.target.position.set(0, 0.3, 0);
  const fill = new THREE.HemisphereLight(0x20242c, 0x060406, 0.35);
  // volumetric key shaft (additive cone)
  const shaftMat = new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    uniforms: { uA: { value: 0.05 } },
    vertexShader: `varying float vY; varying vec3 vN; varying vec3 vV; void main(){ vY=uv.y; vec4 mv=modelViewMatrix*vec4(position,1.0); vN=normalMatrix*normal; vV=-mv.xyz; gl_Position=projectionMatrix*mv; }`,
    fragmentShader: `uniform float uA; varying float vY; varying vec3 vN; varying vec3 vV; void main(){ float f=abs(dot(normalize(vN),normalize(vV))); gl_FragColor=vec4(vec3(1.0,0.85,0.7)*uA*f*f*vY,1.0); }` });
  const shaft = new THREE.Mesh(new THREE.ConeGeometry(1.1, 3.4, 48, 1, true), shaftMat); shaft.position.set(0.8, 1.2, 1.1); shaft.lookAt(1.6, 2.6, 2.2); shaft.rotateX(-Math.PI / 2);
  scene.add(key, key.target, rimW, rimW.target, rimC, rimC.target, fill, shaft);
  scene.add(bokehParticles({ count: 700, box: [6, 4, 6], center: [0, 0.4, 0], colors: [0xffb080, 0x80c8ff, 0xffffff], size: 0.004, intensity: 0.7, drift: 0.05 }));

  const layers = [fig.children[0], armR.ua, armR.fa, armL.ua, armL.fa];
  const wp = (o, x = 0, y = 0, z = 0) => () => { fig.updateMatrixWorld(true); return o.localToWorld(new THREE.Vector3(x, y, z)).toArray(); };
  return {
    scene, clear: 0x040405,
    anchors: { biceps: wp(armR.ua, 0, -0.15, 0.07), forearm: wp(armR.fa, 0, -0.1, 0.04), dumbbell: wp(db, 0.13, 0, 0), chest: wp(fig, -0.09, 0.43, 0.12),
      bicepsL: wp(armL.ua, 0, -0.15, 0.07), abs: wp(fig, 0, 0.15, 0.1), delt: wp(armR.ua, -0.05, -0.02, 0.03) },
    update({ t, P }) {
      const xr = P('xray', 0), curl = P('curl', 0), emerge = P('emerge', 1), hyper = P('hyper', 0);
      fig.rotation.y = P('rotY', 0);
      skinMat.opacity = 1 - xr; skinMat.visible = xr < 0.995; skinMat.depthWrite = xr < 0.5;
      xrayMat.uniforms.uAmt.value = xr * 1.1; xrayMat.uniforms.uTime.value = t;
      wireMat.opacity = xr * P('wire', 0.16) * 1.3;
      const gb = xr * 0.25;
      muscleMat.userData.u.uGlow.value.setRGB(0.1, 0.018, 0.008).multiplyScalar(gb);
      armRMat.userData.u.uGlow.value.setRGB(0.12, 0.025, 0.008).multiplyScalar(gb + P('glowArm', 0) * 3.5);
      armLMat.userData.u.uGlow.value.setRGB(0.12, 0.025, 0.008).multiplyScalar(gb + P('glowArmL', 0) * 3.5);
      layers.forEach(g => { g.userData.m.visible = xr > 0.01; g.scale.setScalar(1 + hyper * 0.035); });
      // right arm curl: upper arm slightly forward, elbow flexion 10..140 degrees
      const flex = THREE.MathUtils.degToRad(10 + curl * 125);
      armR.shoulder.rotation.set(-0.12 - curl * 0.1, 0, -0.12);
      armR.elbow.rotation.set(-flex, 0, 0);
      armR.ua.userData.m.scale.set(1 + curl * 0.07, 1, 1 + curl * 0.12);   // biceps shortening/bulge
      const curlL = P('curlL', 0);
      armL.shoulder.rotation.set(-0.12 - curlL * 0.1, 0, 0.12); armL.elbow.rotation.set(-THREE.MathUtils.degToRad(10 + curlL * 125), 0, 0);
      db.visible = dbL.visible = P('dumbbell', 0) > 0.5;
      key.intensity = 11 * emerge; rimW.intensity = 22 * Math.min(1, emerge * 1.6); rimC.intensity = 14 * emerge;
      shaftMat.uniforms.uA.value = 0.05 * emerge;
    },
  };
}
