# Materials
All materials are procedural and defined in code (no texture files):
- `scenes/lib.js` → `tissueMaterial` (MeshPhysical + fibre striation, derivative bump, fresnel SSS), `fresnelMaterial` (x-ray shell), `bokehParticles` (CoC-scaled points).
- Per-world materials (membrane bilayer, Voronoi fibre caps, RBC, ribosome, mitochondrion, glass week tiles) live in `scenes/worlds/*.js`.
