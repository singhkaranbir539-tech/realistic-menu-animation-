// Skeletal muscle macro-anatomy: epimysium-wrapped bundle of fascicles with
// sectioned ends showing individual fibres (Voronoi), myofibril networks and
// mitochondria. Params: grow (hypertrophy), glow, explode, pulse, sheath
import { tissueMaterial, fresnelMaterial, bokehParticles, rng, NOISE_GLSL, lerp } from '../lib.js';

export async function build({ THREE, env }) {
  const scene = new THREE.Scene();
  scene.environment = env; scene.environmentIntensity = 0.1;
  scene.fog = new THREE.FogExp2(0x07060a, 0.045);
  const r = rng(7);
  const root = new THREE.Group(); scene.add(root);
  root.rotation.y = -0.35;

  // circle packing of fascicles inside a bundle (radius ~1.25)
  const fas = [];
  const tryPlace = (rad) => { for (let k = 0; k < 500; k++) { const a = r() * Math.PI * 2, d = Math.sqrt(r()) * (1.22 - rad);
      const y = Math.sin(a) * d, z = Math.cos(a) * d; if (fas.every(f => Math.hypot(f.y - y, f.z - z) > f.r + rad + 0.035)) { fas.push({ y, z, r: rad }); return; } } };
  tryPlace(0.34); for (let i = 0; i < 6; i++) tryPlace(0.3 - r() * 0.06); for (let i = 0; i < 30; i++) tryPlace(0.22 - r() * 0.08);

  const capMat = (seed) => new THREE.ShaderMaterial({
    uniforms: { uSeed: { value: seed }, uGlow: { value: 1 }, uTime: { value: 0 }, uMito: { value: 1 } },
    vertexShader: `varying vec2 vUv; varying vec3 vN; varying vec3 vV; void main(){ vUv=uv; vec4 mv=modelViewMatrix*vec4(position,1.0); vN=normalMatrix*normal; vV=-mv.xyz; gl_Position=projectionMatrix*mv; }`,
    fragmentShader: `uniform float uSeed,uGlow,uTime,uMito; varying vec2 vUv; varying vec3 vN; varying vec3 vV; ${NOISE_GLSL}
      vec2 h2(vec2 p){ p=vec2(dot(p,vec2(127.1,311.7)),dot(p,vec2(269.5,183.3))); return fract(sin(p+uSeed)*43758.5453); }
      vec3 voro(vec2 x){ vec2 n=floor(x), f=fract(x); float md=8.0, md2=8.0; vec2 mr, id;
        for(int j=-1;j<=1;j++)for(int i=-1;i<=1;i++){ vec2 g=vec2(i,j); vec2 o=0.5+0.38*sin(6.2831*h2(n+g)); vec2 rr=g+o-f; float d=dot(rr,rr);
          if(d<md){md2=md; md=d; mr=rr; id=n+g;} else if(d<md2) md2=d; }
        return vec3(sqrt(md2)-sqrt(md), h2(id).x, sqrt(md)); }
      void main(){
        vec2 p=(vUv-0.5)*2.0; float rad=length(p);
        if(rad>1.0) discard;
        vec3 v=voro(p*2.6+uSeed);                    // individual muscle fibres
        float edge=smoothstep(0.02,0.11,v.x);        // endomysium boundary
        float centre=1.0-smoothstep(0.0,0.75,v.z);
        // myofibril / sarcoplasmic-reticulum network inside each fibre
        float net=1.0-abs(snoise(vec3(p*14.0,uSeed))); net=pow(net,7.0);
        vec3 deep=vec3(0.16,0.015,0.01), warm=vec3(0.62,0.16,0.04), hot=vec3(0.95,0.55,0.2);
        vec3 c=mix(deep,warm,0.35+0.65*centre)*(0.75+0.5*v.y);
        c+=hot*net*0.9*(0.35+centre);
        c*=edge; c+=vec3(0.55,0.16,0.08)*(1.0-edge)*0.35;
        // mitochondria: small cyan bodies near fibre periphery
        vec3 m=voro(p*15.0+uSeed*3.1); float mito=(1.0-smoothstep(0.06,0.11,m.z))*step(0.55,m.y)*smoothstep(0.03,0.15,v.x)*(1.0-centre*0.6);
        c=mix(c,vec3(0.2,0.8,0.75)*0.9,mito*uMito);
        float rim=smoothstep(0.86,1.0,rad); c=mix(c,vec3(0.55,0.2,0.15)*0.6,rim);
        gl_FragColor=vec4(c*uGlow*(1.0+0.06*sin(uTime*1.3+uSeed)),1.0); }`,
  });

  const fasMat = tissueMaterial({ color: 0x7a1c14, varColor: 0x2a0606, axis: [1, 0, 0], fibreFreq: 22, fibre: 0.55, striFreq: 120, stri: 0.12,
    bump: 0.5, bumpScale: 9, sss: 0xff5a28, sssAmt: 0.75, clearcoat: 0.7, sheenColor: 0xffa070 });
  const fasGroup = new THREE.Group(); root.add(fasGroup);
  const L = 7;
  const fasObjs = fas.map((f, i) => {
    const g = new THREE.Group();
    const len = L - (i === 0 ? -0.9 : r() * 0.5);
    const cyl = new THREE.Mesh(new THREE.CylinderGeometry(f.r, f.r * 1.02, len, 72, 48, true), fasMat);
    cyl.rotation.z = Math.PI / 2; cyl.position.x = -len / 2; cyl.castShadow = cyl.receiveShadow = true;
    const cap = new THREE.Mesh(new THREE.CircleGeometry(f.r * 0.985, 72), capMat(i * 1.37 + 0.3));
    cap.rotation.y = Math.PI / 2; cap.position.x = 0.001;
    const ring = new THREE.Mesh(new THREE.TorusGeometry(f.r, f.r * 0.035, 10, 72), tissueMaterial({ color: 0x7a3a2a, axis: [0, 0, 1], sssAmt: 0.5 }));
    ring.rotation.y = Math.PI / 2;
    g.add(cyl, cap, ring);
    g.position.set(i === 0 ? 0.9 : r() * 0.35, f.y, f.z);
    g.userData = { base: g.position.clone(), f, cap };
    fasGroup.add(g); return g;
  });
  // epimysium sheath: translucent outer wrap, open at the sectioned end
  const sheathMat = tissueMaterial({ color: 0x3a1210, varColor: 0x120404, axis: [1, 0, 0], fibreFreq: 9, fibre: 0.8, sssAmt: 0.5,
    transparent: true, opacity: 0.4, side: THREE.DoubleSide, depthWrite: false, clearcoat: 1, roughness: 0.3 });
  const sheath = new THREE.Mesh(new THREE.CylinderGeometry(1.32, 1.36, L + 1, 96, 32, true), sheathMat);
  sheath.rotation.z = Math.PI / 2; sheath.position.x = -(L + 1) / 2 - 0.35; root.add(sheath);
  const sheathGlow = new THREE.Mesh(sheath.geometry, fresnelMaterial({ color: 0xff6a40, power: 3, amount: 0.25 }));
  sheathGlow.rotation.copy(sheath.rotation); sheathGlow.position.copy(sheath.position); sheathGlow.scale.setScalar(1.002); root.add(sheathGlow);
  // trailing connective-tissue strands
  const strands = new THREE.Group(); root.add(strands);
  const strandMat = tissueMaterial({ color: 0x5a4040, axis: [1, 0, 0], fibreFreq: 30, sssAmt: 0.4, transparent: true, opacity: 0.7 });
  for (let i = 0; i < 14; i++) {
    const pts = []; const a = r() * 6.28, d = 1.1 + r() * 0.3;
    for (let k = 0; k < 6; k++) pts.push(new THREE.Vector3(-L - 0.5 - k * 0.6, Math.sin(a) * d + (r() - .5) * 0.4 * k * 0.4, Math.cos(a) * d + (r() - .5) * 0.4 * k * 0.4));
    strands.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 40, 0.02 + r() * 0.03, 8), strandMat));
  }

  // lighting: warm key, cyan rim, soft fill
  const key = new THREE.SpotLight(0xffc49a, 60, 30, 0.6, 0.7, 1.6); key.position.set(4, 6, 6); key.target.position.set(0, 0, 0);
  key.castShadow = true; key.shadow.mapSize.set(1024, 1024); key.shadow.bias = -0.0005;
  const rim = new THREE.DirectionalLight(0x6fd0ff, 0.9); rim.position.set(-6, 3, -5);
  const fill = new THREE.HemisphereLight(0x302830, 0x080404, 0.6);
  const capLight = new THREE.PointLight(0xff7a3a, 8, 6, 2); capLight.position.set(1.8, 0, 0.5);
  scene.add(key, key.target, rim, fill, capLight);
  scene.add(bokehParticles({ count: 900, box: [26, 14, 22], center: [-3, 0, 0], colors: [0xff7040, 0xffa060, 0x60d0e0], size: 0.018, intensity: 0.9 }));

  const wp = (o, x = 0, y = 0, z = 0) => () => o.localToWorld(new THREE.Vector3(x, y, z)).toArray();
  const hero = fasObjs[0], side = fasObjs[3];
  return {
    anchors: { cap: wp(hero, 0.02, 0, 0), fibre: wp(hero, 0.02, fas[0].r * 0.45, fas[0].r * 0.3), mito: wp(hero, 0.02, -fas[0].r * 0.5, -fas[0].r * 0.2),
      fascicle: wp(side, -2.2, side.userData.f.r, 0), sheath: wp(root, -4.5, 1.33, 0.3), bundle: wp(root, -1.5, 0, 0) },
    scene, clear: 0x060508,
    update({ t, P }) {
      const grow = P('grow', 0), glow = P('glow', 1), explode = P('explode', 0), pulse = P('pulse', 0);
      root.rotation.y = P('rotY', -0.35); root.rotation.x = P('rotX', 0);
      fasObjs.forEach((g, i) => {
        const b = g.userData.base; const dir = new THREE.Vector2(b.y, b.z); const l = dir.length() || 1;
        const s = 1 + grow * (0.16 + 0.08 * Math.sin(i * 3.1)) + pulse * 0.03 * Math.sin(t * 6 - i);
        g.scale.set(1, s, s);
        g.position.set(b.x + explode * (i % 3) * 0.35, b.y * (1 + grow * 0.14) + explode * b.y / l * 0.5, b.z * (1 + grow * 0.14) + explode * b.z / l * 0.5);
        const u = g.userData.cap.material.uniforms; u.uGlow.value = glow * (1 + grow * 0.35); u.uTime.value = t; u.uMito.value = P('mito', 1);
      });
      sheath.scale.set(1, 1 + grow * 0.15, 1 + grow * 0.15); sheathGlow.scale.copy(sheath.scale);
      sheath.visible = sheathGlow.visible = P('sheath', 1) > 0.01;
      sheathMat.opacity = 0.4 * P('sheath', 1);
      fasMat.userData.u.uTime.value = t;
      capLight.intensity = 2.5 * glow;
    },
  };
}
