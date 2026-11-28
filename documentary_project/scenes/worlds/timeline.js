// 12-week periodisation visual: dark glass week tiles floating over a reflective
// floor, lit by phase. Params: mode 'onoff' | 'phases' | 'neutral', reveal (0..1),
// focusPhase (-1 none, 0..3), raise12 (0..1)
import { bokehParticles, rng, clamp, ease, smooth } from '../lib.js';

const PHASES = [ { w: [1, 4], col: 0xff4a36, name: 'STRENGTH + HYPERTROPHY' }, { w: [5, 8], col: 0xffa040, name: 'SLOW NEGATIVES' },
  { w: [9, 11], col: 0x4fd0e0, name: 'REST-PAUSE · CLUSTER' }, { w: [12, 12], col: 0xb0c4ff, name: 'DELOAD' } ];
export const TILE_X = (i) => (i - 6.5) * 1.32;

export async function build({ THREE, env }) {
  const scene = new THREE.Scene();
  scene.environment = env; scene.environmentIntensity = 0.35;
  scene.fog = new THREE.FogExp2(0x060609, 0.05);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.MeshPhysicalMaterial({ color: 0x08080a, roughness: 0.22, metalness: 0.2, clearcoat: 1, clearcoatRoughness: 0.08 }));
  floor.rotation.x = -Math.PI / 2; floor.position.y = -1.2; scene.add(floor);
  const tiles = [];
  const mkLabel = (txt) => { const c = document.createElement('canvas'); c.width = 256; c.height = 256; const x = c.getContext('2d');
    x.fillStyle = '#000'; x.fillRect(0, 0, 256, 256); x.fillStyle = '#fff'; x.textAlign = 'center';
    x.font = '600 34px Inter'; x.fillText('WEEK', 128, 92); x.font = '300 104px Inter'; x.fillText(txt, 128, 196);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t; };
  for (let i = 1; i <= 12; i++) {
    const g = new THREE.Group(); g.position.set(TILE_X(i), 0.2, 0);
    const glass = new THREE.Mesh(new THREE.BoxGeometry(1.08, 1.5, 0.12), new THREE.MeshPhysicalMaterial({ color: 0x101216, roughness: 0.12, metalness: 0.1, clearcoat: 1, clearcoatRoughness: 0.05, emissive: 0x000000 }));
    const face = new THREE.Mesh(new THREE.PlaneGeometry(0.8, 0.8), new THREE.MeshBasicMaterial({ map: mkLabel(String(i)), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, color: 0x555555 }));
    face.position.set(0, 0.1, 0.065);
    const bar = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.035, 0.02), new THREE.MeshBasicMaterial({ color: 0x222222 }));
    bar.position.set(0, -0.62, 0.07);
    const edge = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1.08, 1.5, 0.12)), new THREE.LineBasicMaterial({ color: 0x444a50, transparent: true, opacity: 0.6 }));
    const light = new THREE.PointLight(0xffffff, 0, 3.5, 2); light.position.set(0, -0.2, 0.6);
    g.add(glass, face, bar, edge, light); scene.add(g);
    tiles.push({ g, glass, face, bar, edge, light, phase: PHASES.findIndex(p => i >= p.w[0] && i <= p.w[1]) });
  }
  // backdrop: soft volumetric gradient wall
  const wall = new THREE.Mesh(new THREE.PlaneGeometry(60, 20), new THREE.ShaderMaterial({ depthWrite: false,
    vertexShader: 'varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: 'varying vec2 vUv; void main(){ float d=length((vUv-vec2(0.5,0.42))*vec2(1.0,2.2)); vec3 c=mix(vec3(0.07,0.02,0.025),vec3(0.012,0.012,0.016),smoothstep(0.0,0.5,d)); gl_FragColor=vec4(c,1.0);} ' }));
  wall.position.set(0, 3, -10); scene.add(wall);
  const key = new THREE.SpotLight(0xffe0d0, 60, 40, 0.8, 0.9, 1.5); key.position.set(0, 8, 6);
  scene.add(key, new THREE.HemisphereLight(0x20242c, 0x050505, 0.5));
  scene.add(bokehParticles({ count: 700, box: [30, 10, 16], center: [0, 1.5, -2], colors: [0xff6a50, 0x60c8e0, 0xffc080], size: 0.02, intensity: 0.7 }));
  const col = new THREE.Color(), dim = new THREE.Color(0x30343a);
  const anchors = {};
  for (let i = 1; i <= 12; i++) anchors['w' + i] = () => [TILE_X(i), tiles[i - 1].g.position.y + 0.8, 0];
  PHASES.forEach((p, k) => anchors['p' + k] = () => [(TILE_X(p.w[0]) + TILE_X(p.w[1])) / 2, 1.15, 0]);
  anchors.on = () => [(TILE_X(1) + TILE_X(4)) / 2, 1.15, 0]; anchors.off = () => [(TILE_X(5) + TILE_X(12)) / 2, 1.15, 0];
  return {
    anchors,
    scene, clear: 0x060608,
    update({ t, P }) {
      const mode = P('mode', 'phases'), reveal = P('reveal', 1), fp = P('focusPhase', -1), raise12 = P('raise12', 0);
      tiles.forEach((T, idx) => {
        const i = idx + 1; const k = ease.out(clamp(reveal * 13 - idx));
        let c = dim, on = 0.15;
        if (mode === 'onoff') { if (i <= 4) { c = col.set(0xff4a36); on = 1; } else { c = col.set(0x8090a0); on = 0.22; } }
        else if (mode === 'phases') { c = col.set(PHASES[T.phase].col); on = fp < 0 ? 0.85 : (T.phase === fp ? 1.1 : 0.12); }
        on *= k;
        T.bar.material.color.copy(c).multiplyScalar(0.25 + on * 2.2);
        T.face.material.color.setScalar(0.25 + on * 0.75);
        T.edge.material.color.copy(c).multiplyScalar(0.3 + on * 0.9);
        T.glass.material.emissive.copy(c).multiplyScalar(on * 0.09);
        T.light.color.copy(c); T.light.intensity = on * 1.6;
        const lift = (mode === 'phases' && T.phase === fp ? 0.18 : 0) + (i === 12 ? raise12 * 0.5 : 0);
        T.g.position.y = 0.2 + lift + Math.sin(t * 0.8 + idx * 0.5) * 0.025 + (1 - k) * -0.4;
        T.g.rotation.y = Math.sin(t * 0.3 + idx) * 0.03;
        T.g.visible = k > 0.001;
      });
    },
  };
}
