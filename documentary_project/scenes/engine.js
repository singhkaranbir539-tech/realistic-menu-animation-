// Offline cinematic frame engine.
// window.setup({w,h,vertical}) builds everything; window.renderFrame(t) draws frame at time t.
import * as THREE from 'three';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ease, clamp, lerp, smooth, updateBokeh, NOISE_GLSL } from './lib.js';
import { drawOverlay } from './overlay.js';

const WORLD_MODULES = ['body', 'fibers', 'sarcomere', 'blood', 'molecules', 'cell', 'powder', 'synthesis', 'timeline'];

let R, W, H, VERT, shots, worlds = {}, post, overlayCtx, camA, camB;

// ------------------------------------------------------------------ post FX
const FS_VERT = `varying vec2 vUv; void main(){ vUv=uv; gl_Position=vec4(position.xy,0.0,1.0); }`;
function fsQuad(mat) { const m = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat); const s = new THREE.Scene(); s.add(m); return s; }
const orthoCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

function makeRT(w, h, depth = false) {
  const rt = new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, samples: depth ? window.CFG.samples : 0 });
  if (depth) { rt.depthTexture = new THREE.DepthTexture(w, h); rt.depthTexture.type = THREE.FloatType; }
  return rt;
}

function buildPost() {
  const p = {};
  p.sceneRT = [makeRT(W, H, true), makeRT(W, H, true)];
  p.dofRT = [makeRT(W, H), makeRT(W, H)];
  p.mixRT = makeRT(W, H);
  // Depth of field: golden-angle gather, CoC from thin-lens model
  p.dofMat = new THREE.ShaderMaterial({ defines: { DOF_TAPS: window.CFG.dofTaps },
    uniforms: { tColor: { value: null }, tDepth: { value: null }, uNear: { value: .1 }, uFar: { value: 100 },
      uFocus: { value: 5 }, uAperture: { value: 1 }, uRes: { value: new THREE.Vector2(W, H) }, uMaxR: { value: H * 0.018 } },
    vertexShader: FS_VERT,
    fragmentShader: `uniform sampler2D tColor,tDepth; uniform float uNear,uFar,uFocus,uAperture,uMaxR; uniform vec2 uRes; varying vec2 vUv;
      float lin(float z){ return uNear*uFar/(uFar-z*(uFar-uNear)); }
      float coc(float d){ return clamp(abs(1.0/d-1.0/uFocus)*uFocus*uAperture*uRes.y*0.012,0.0,uMaxR); }
      void main(){
        float d0=lin(texture2D(tDepth,vUv).x); float c0=coc(d0);
        vec3 acc=texture2D(tColor,vUv).rgb; float wsum=1.0;
        if(c0>0.6){
          const int N=DOF_TAPS; float ga=2.39996;
          for(int i=1;i<N;i++){
            float r=sqrt(float(i)/float(N))*c0; float a=float(i)*ga;
            vec2 o=vec2(cos(a),sin(a))*r/uRes; vec2 uv=vUv+o;
            float ds=lin(texture2D(tDepth,uv).x); float cs=coc(ds);
            float w=(ds<d0)? smoothstep(r-1.0,r+1.0,cs) : 1.0;  // foreground bleeds only by its own CoC
            vec3 c=texture2D(tColor,uv).rgb; w*=1.0+dot(c,vec3(0.3))*0.4;           // bright bokeh
            acc+=c*w; wsum+=w;
          }
        }
        gl_FragColor=vec4(acc/wsum,1.0); }`,
  });
  p.dofScene = fsQuad(p.dofMat);
  // Transition mixer
  p.mixMat = new THREE.ShaderMaterial({
    uniforms: { tA: { value: null }, tB: { value: null }, uMix: { value: 0 }, uMode: { value: 0 }, uTime: { value: 0 } },
    vertexShader: FS_VERT,
    fragmentShader: `uniform sampler2D tA,tB; uniform float uMix,uMode,uTime; varying vec2 vUv; ${NOISE_GLSL}
      vec3 zoomBlur(sampler2D t, vec2 uv, float amt, float scale){
        vec2 c=vec2(0.5); vec3 s=vec3(0.0); for(int i=0;i<12;i++){ float k=1.0-amt*float(i)/12.0; s+=texture2D(t,c+(uv-c)*k/scale).rgb; } return s/12.0; }
      void main(){
        float m=uMix;
        if(uMode<0.5){ // organic dissolve driven by noise + luminance
          vec3 a=texture2D(tA,vUv).rgb, b=texture2D(tB,vUv).rgb;
          float n=0.5+0.5*snoise(vec3(vUv*vec2(3.0,1.8),uTime*0.2)); float l=dot(b,vec3(0.33));
          float th=clamp(m*1.6-0.3,0.0,1.0); float k=smoothstep(th-0.25,th+0.25,mix(n,1.0-l,0.35));
          gl_FragColor=vec4(mix(b,a,k),1.0);
        } else { // macro->micro push: outgoing zooms in & blurs, incoming settles from slight zoom
          float e=m*m*(3.0-2.0*m);
          vec3 a=zoomBlur(tA,vUv,e*0.35,1.0+e*0.8);
          vec3 b=zoomBlur(tB,vUv,(1.0-e)*0.3,1.0-(1.0-e)*0.25);
          vec3 c=mix(a,b,smoothstep(0.35,0.75,m)); c+=vec3(1.0,0.85,0.75)*exp(-pow((m-0.55)*7.0,2.0))*0.25;
          gl_FragColor=vec4(c,1.0);
        } }`,
  });
  p.mixScene = fsQuad(p.mixMat);
  p.bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 0.32, 0.55, 0.82);
  // Final grade: exposure, AgX, filmic grade, vignette, CA, grain
  p.gradeMat = new THREE.ShaderMaterial({
    uniforms: { tIn: { value: null }, uExposure: { value: 1 }, uTime: { value: 0 }, uRes: { value: new THREE.Vector2(W, H) },
      uFade: { value: 1 }, uVig: { value: 0.32 } },
    vertexShader: FS_VERT,
    fragmentShader: `uniform sampler2D tIn; uniform float uExposure,uTime,uFade,uVig; uniform vec2 uRes; varying vec2 vUv;
      vec3 agxCurve(vec3 x){ vec3 x2=x*x; vec3 x4=x2*x2; return 15.5*x4*x2-40.14*x4*x+31.96*x4-6.868*x2*x+0.4298*x2+0.1191*x-0.00232; }
      vec3 agx(vec3 c){
        const mat3 inM=mat3(0.856627153315983,0.137318972929847,0.11189821299995,0.0951212405381588,0.761241990602591,0.0767994186031903,0.0482516061458583,0.101439036467562,0.811302368396859);
        const mat3 outM=mat3(1.1271005818144368,-0.1413297634984383,-0.14132976349843826,-0.11060664309660323,1.157823702216272,-0.11060664309660294,-0.016493938717834573,-0.016493938717834257,1.2519364065950405);
        c=inM*c; c=max(c,1e-10); c=log2(c); c=(c+12.47393)/(4.026069+12.47393); c=clamp(c,0.0,1.0);
        c=agxCurve(c); c=outM*c; return pow(max(c,0.0),vec3(2.2)); }
      float h(vec2 p){ return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453); }
      void main(){
        vec2 d=(vUv-0.5); float r2=dot(d,d);
        vec3 c; c.r=texture2D(tIn,vUv-d*0.0025).r; c.g=texture2D(tIn,vUv).g; c.b=texture2D(tIn,vUv+d*0.0025).b;
        c*=uExposure; c=agx(c);
        // grade: cool charcoal shadows, warm highlights, gentle contrast
        float l=dot(c,vec3(0.2126,0.7152,0.0722));
        c=mix(c, c*vec3(0.92,1.0,1.06), (1.0-smoothstep(0.0,0.35,l))*0.6);
        c=mix(c, c*vec3(1.05,1.0,0.95), smoothstep(0.4,1.0,l)*0.5);
        c=mix(vec3(l),c,1.22);
        c*=1.0-uVig*smoothstep(0.08,0.55,r2*1.6);
        c=pow(clamp(c,0.0,1.0),vec3(1.0/2.2));
        c+=(h(vUv*uRes+fract(uTime*7.13)*100.0)-0.5)*0.022;
        gl_FragColor=vec4(c*uFade,1.0); }`,
  });
  p.gradeScene = fsQuad(p.gradeMat);
  return p;
}

// ------------------------------------------------------------- camera rig
function camFromShot(cam, shot, u, t) {
  const c = shot.cam, e = ease[c.ease || 'inOut'](u);
  const A = c.from, B = c.to || c.from;
  const p = A.p.map((v, i) => lerp(v, B.p[i], e)), tg = A.t.map((v, i) => lerp(v, B.t[i], e));
  if (c.orbit) { // orbit around target, degrees over shot
    const ang = THREE.MathUtils.degToRad(lerp(c.orbit[0], c.orbit[1], e));
    const dx = p[0] - tg[0], dz = p[2] - tg[2];
    p[0] = tg[0] + dx * Math.cos(ang) - dz * Math.sin(ang); p[2] = tg[2] + dx * Math.sin(ang) + dz * Math.cos(ang);
  }
  // subtle hand-held breathing (very low amplitude, slow) -- not shake
  const br = c.breathe ?? 0.004;
  p[0] += Math.sin(t * 0.7) * br; p[1] += Math.sin(t * 0.53 + 1) * br * 0.7;
  let mm = lerp(A.mm ?? 50, B.mm ?? A.mm ?? 50, e);
  cam.position.set(...p); cam.up.set(0, 1, 0);
  if (c.roll) cam.up.set(Math.sin(lerp(c.roll[0], c.roll[1], e)), Math.cos(lerp(c.roll[0], c.roll[1], e)), 0);
  cam.lookAt(...tg);
  cam.aspect = W / H;
  if (VERT) { // recompose for 9:16: keep the landscape horizontal field-of-view, slightly tighter
    const hfov = 2 * Math.atan(36 / 2 / mm);
    const k = shot.vert?.fit ?? 0.82;
    cam.fov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(hfov / 2) * k / cam.aspect));
    if (shot.vert?.dolly) { const dir = new THREE.Vector3(...p).sub(new THREE.Vector3(...tg)); cam.position.copy(new THREE.Vector3(...tg).add(dir.multiplyScalar(shot.vert.dolly))); cam.lookAt(...tg); }
  } else {
    cam.filmGauge = 36; cam.setFocalLength(mm);
  }
  cam.updateProjectionMatrix();
  const f = shot.focus || {};
  const tgV = new THREE.Vector3(...tg);
  const fd0 = f.from ?? cam.position.distanceTo(tgV), fd1 = f.to ?? fd0;
  const fu = f.rack ? smooth(f.rack[0], f.rack[1], u) : e;
  return { focus: lerp(fd0, fd1, fu), aperture: f.ap ?? 0.6, target: tgV };
}

// ------------------------------------------------------------- params
// param values may be numbers, or {from,to,at:[u0,u1],ease} tweens on shot-local u, or keyed arrays [[u,v],...]
export function P(shot, name, u, def = 0) {
  const v = shot.params?.[name];
  if (v === undefined) return def;
  if (typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean') return v;
  if (Array.isArray(v)) {
    if (u <= v[0][0]) return v[0][1];
    for (let i = 1; i < v.length; i++) if (u <= v[i][0]) { const k = (u - v[i - 1][0]) / (v[i][0] - v[i - 1][0]); return lerp(v[i - 1][1], v[i][1], ease.sine(k)); }
    return v[v.length - 1][1];
  }
  const at = v.at || [0, 1]; const k = clamp((u - at[0]) / (at[1] - at[0]));
  return lerp(v.from, v.to, ease[v.ease || 'inOut'](k));
}

function renderShot(shot, t, idx) {
  const world = worlds[shot.world];
  const dur = shot.end - shot.start;
  const u = clamp((t - shot.start) / dur);
  const cam = idx ? camB : camA;
  const lt = t - shot.start;
  const c = camFromShot(cam, shot, u, t);
  world.update({ t, lt, u, shot, P: (n, d) => P(shot, n, u, d), cam, vertical: VERT });
  updateBokeh(world.scene, cam, c.focus, c.aperture * 2.0, t, H);
  R.setRenderTarget(post.sceneRT[idx]);
  R.setClearColor(world.clear ?? 0x050608, 1);
  R.clear();
  R.render(world.scene, cam);
  const d = post.dofMat.uniforms;
  d.tColor.value = post.sceneRT[idx].texture; d.tDepth.value = post.sceneRT[idx].depthTexture;
  d.uNear.value = cam.near; d.uFar.value = cam.far; d.uFocus.value = c.focus; d.uAperture.value = c.aperture;
  R.setRenderTarget(post.dofRT[idx]); R.render(post.dofScene, orthoCam);
  return { cam, focus: c.focus, target: c.target, u };
}

window.setup = async ({ w, h, vertical, cfg }) => {
  window.CFG = Object.assign({ samples: 2, dofTaps: 28, bloom: true }, cfg || {});
  W = w; H = h; VERT = !!vertical;
  R = new THREE.WebGLRenderer({ canvas: document.getElementById('gl'), antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  R.setPixelRatio(1); R.setSize(W, H, false);
  R.outputColorSpace = THREE.LinearSRGBColorSpace; R.toneMapping = THREE.NoToneMapping;
  R.shadowMap.enabled = true; R.shadowMap.type = THREE.PCFSoftShadowMap;
  document.getElementById('gl').style.width = W + 'px'; document.getElementById('gl').style.height = H + 'px';
  const ov = document.getElementById('ov'); ov.width = W; ov.height = H; ov.style.width = W + 'px'; ov.style.height = H + 'px';
  overlayCtx = ov.getContext('2d');
  shots = await (await fetch('../storyboard/shots.json')).json();
  camA = new THREE.PerspectiveCamera(40, W / H, 0.05, 400); camB = camA.clone();
  post = buildPost();
  const pmrem = new THREE.PMREMGenerator(R);
  const { RoomEnvironment } = await import('three/addons/environments/RoomEnvironment.js');
  const env = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  const needed = [...new Set(shots.shots.map(s => s.world))];
  for (const name of needed) {
    const mod = await import(`./worlds/${name}.js`);
    worlds[name] = await mod.build({ THREE, env, R, W, H, vertical: VERT });
  }
  await document.fonts.ready;
  return { shots: shots.shots.length, duration: shots.duration };
};

window.renderFrame = (t) => {
  const S = shots.shots;
  let i = S.findIndex(s => t >= s.start && t < s.end); if (i < 0) i = S.length - 1;
  const cur = S[i];
  // transition: the incoming shot's `trans` defines {type,dur} centred on its start
  let A = cur, B = null, mix = 0, mode = 0;
  const next = S[i + 1];
  const tin = cur.trans && cur.trans.type !== 'cut' ? cur.trans.dur : 0;
  const tout = next && next.trans && next.trans.type !== 'cut' ? next.trans.dur : 0;
  if (tin && t < cur.start + tin / 2 && S[i - 1]) { A = S[i - 1]; B = cur; mix = (t - (cur.start - tin / 2)) / tin; mode = cur.trans.type === 'push' ? 1 : 0; }
  else if (tout && t >= next.start - tout / 2) { A = cur; B = next; mix = (t - (next.start - tout / 2)) / tout; mode = next.trans.type === 'push' ? 1 : 0; }
  const infoA = renderShot(A, t, 0);
  let final = post.dofRT[0], info = infoA, shownShot = A;
  if (B) {
    const infoB = renderShot(B, t, 1);
    const m = post.mixMat.uniforms; m.tA.value = post.dofRT[0].texture; m.tB.value = post.dofRT[1].texture;
    m.uMix.value = clamp(mix); m.uMode.value = mode; m.uTime.value = t;
    R.setRenderTarget(post.mixRT); R.render(post.mixScene, orthoCam); final = post.mixRT;
    if (mix > 0.5) { info = infoB; shownShot = B; }
  }
  const bloomStr = (B && mix > .5 ? B : A).post?.bloom ?? 0.32;
  post.bloom.strength = bloomStr;
  if (window.CFG.bloom) post.bloom.render(R, null, final, 0, false);
  const g = post.gradeMat.uniforms; g.tIn.value = final.texture; g.uTime.value = t;
  g.uExposure.value = (shownShot.post?.exposure ?? 1.0);
  // fade in from black at programme start, out at end
  g.uFade.value = smooth(0, 0.6, t) * (1 - smooth(shots.duration - 0.8, shots.duration, t));
  R.setRenderTarget(null); R.render(post.gradeScene, orthoCam);
  drawOverlay(overlayCtx, { W, H, VERT, t, shots: S, shot: shownShot, cam: info.cam, anchors: worlds[shownShot.world].anchors || {}, mix: B ? mix : null, globalFade: g.uFade.value, meta: shots });
  return true;
};
