"""Semantic timeline -> shot list.

Reads transcript/transcript.json and emits
  storyboard/shots.json       (render data used by scenes/engine.js)
  storyboard/production.json  (scene-by-scene production sheet)
  storyboard/semantic_timeline.json
Every shot's narration is taken from the word timestamps inside its interval,
so each spoken word belongs to exactly one shot.
"""
import json, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
T = json.load(open(f"{ROOT}/transcript/transcript.json"))
DUR = T["duration"]
WORDS = [w for s in T["sections"] for c in s["clauses"] for w in c["words"]]

def cam(p0, t0, mm0, p1=None, t1=None, mm1=None, ease="inOut", **kw):
    c = {"from": {"p": p0, "t": t0, "mm": mm0}, "to": {"p": p1 or p0, "t": t1 or t0, "mm": mm1 or mm0}, "ease": ease}
    c.update(kw); return c

def tw(a, b, at=(0, 1), ease="inOut"):
    return {"from": a, "to": b, "at": list(at), "ease": ease}

def L(text, at3=None, sub=None, at=(0.1, 0.95), **kw):
    d = {"text": text, "at": list(at)}
    if at3: d["at3"] = at3
    if sub: d["sub"] = sub
    d.update(kw); return d

# world descriptions used by the production sheet
WORLD_INFO = {
 "body": dict(subject="Anonymous athletic human figure (SDF anatomy) with x-ray musculature",
   anatomy="Pectoralis major, deltoid, biceps/triceps brachii, rectus abdominis, latissimus, trapezius; featureless head for anonymity",
   environment="Dark studio void with contact floor and drifting dust", lighting="Warm high key spot, warm + cyan rim spots, volumetric key shaft",
   materials="Skin: SSS-approximated dielectric with pore-scale bump; muscle: fibrous tissue shader; x-ray fresnel shell + wireframe topology"),
 "fibers": dict(subject="Skeletal muscle bundle: epimysium, fascicles, sectioned fibres",
   anatomy="Epimysium > perimysium-wrapped fascicles > muscle fibres (Voronoi section) with myofibril network and mitochondria",
   environment="Deep charcoal microscopic space with bokeh particulate", lighting="Warm key spot with shadows, cyan rim, warm bounce from sectioned faces",
   materials="Fibre-striated tissue (clearcoat moisture, SSS rim), emissive cut-face shader, translucent sheath"),
 "sarcomere": dict(subject="Myofibril sarcomeres: actin, myosin cross-bridges, Z-discs, titin",
   anatomy="Hexagonal thick-filament lattice, trigonal thin filaments, bare zone, Z-disc lattice, titin springs",
   environment="Inside the muscle fibre, neighbouring myofibrils in fog", lighting="Warm key, cyan rim, myosin-head glow under load",
   materials="Clearcoated protein surfaces; emissive heads when force is produced"),
 "blood": dict(subject="Bloodstream fly-through with erythrocytes and glucose", anatomy="Biconcave erythrocytes (Evans-Fung profile), endothelium-lined vessel",
   environment="Vessel lumen with depth-dependent red scattering", lighting="Camera headlamp, warm key, faint cyan rim",
   materials="Translucent RBC tissue with SSS rim, wet endothelium, glass-like glucose glyphs"),
 "molecules": dict(subject="Carbohydrate structures", anatomy="beta-D-glucopyranose (CPK), highly branched cyclic dextrin (simplified), glycogen granule with glycogenin core",
   environment="Dark lab-space with soft halo", lighting="Key spot, cyan and warm rims", materials="Clearcoat CPK atoms; emissive glucose units"),
 "cell": dict(subject="Muscle-cell membrane cutaway: insulin receptor, GLUT4 translocation", anatomy="Lipid bilayer, insulin receptor dimer, kinase domains, GLUT4 storage vesicles",
   environment="Extracellular space above, sarcoplasm below", lighting="Warm key, cyan rim, warm under-glow", materials="Granular protein clusters, lipid head groups, emissive signal relay"),
 "powder": dict(subject="Carbohydrate powders in macro product photography", anatomy="n/a",
   environment="Dark slate studio surface", lighting="Soft key with shadows, cyan back rim, warm side kicker", materials="Instanced powder grains (crystalline / fine), varied-roughness slate"),
 "synthesis": dict(subject="Protein synthesis and mitochondrial energy production (conceptual)", anatomy="Ribosome subunits, mRNA, nascent polypeptide, amino acids, mitochondrion with cristae",
   environment="Sarcoplasm interior", lighting="Key spot, cyan rim, warm fill", materials="Protein clusters, translucent outer membrane, emissive cristae and ATP"),
 "timeline": dict(subject="12-week periodisation tiles", anatomy="n/a", environment="Reflective dark floor, volumetric backdrop",
   lighting="Phase-coloured practical lights inside glass tiles", materials="Dark glass with clearcoat, emissive labels"),
}

S = []   # shots
def shot(start, end, world, c, params=None, **kw):
    d = {"start": round(start, 3), "end": round(end, 3), "world": world, "cam": c, "params": params or {}}
    d.update(kw); S.append(d); return d

# ===================== 1. INTRO (0 - 17) =====================
shot(0.0, 1.7, "body", cam([1.0, 0.25, 2.3], [0, 0.4, 0], 70, [0.55, 0.38, 1.45], [-0.05, 0.42, 0], 70, ease="out", breathe=0.002),
     {"emerge": tw(0, 1, (0, 0.8)), "xray": 0, "curl": 0.25, "dumbbell": 1}, focus={"ap": 0.5},
     desc="Hook: a muscular anonymous torso emerges from darkness under a rising warm key and rim light.",
     sound=["sub-bass swell", "low impact at 0.15s"], post={"bloom": 0.25})
shot(1.7, 2.95, "body", cam([0.05, 0.5, 0.95], [-0.24, 0.38, 0.05], 85, [-0.18, 0.4, 0.42], [-0.24, 0.37, 0.05], 100, ease="in"),
     {"xray": tw(0, 1, (0.0, 0.7)), "curl": 0.55, "dumbbell": 1, "wire": 0.22, "glowArm": tw(0, 0.6)}, focus={"ap": 0.7},
     trans={"type": "cut", "dur": 0}, desc="Rapid dolly toward the biceps while skin dissolves into an x-ray view of the muscle.", sound=["whoosh rising"])
shot(2.95, 4.15, "fibers", cam([5.5, 0.9, 2.6], [0.6, 0, 0], 100, [2.6, 0.45, 1.25], [0.6, 0, 0], 100, ease="out"),
     {"glow": tw(0.4, 1.0), "sheath": 1}, focus={"ap": 0.9}, trans={"type": "push", "dur": 0.5},
     desc="Macro-to-micro push into a sectioned muscle bundle; fibres glow as the camera settles.", sound=["push whoosh", "micro texture"])
shot(4.15, 5.55, "sarcomere", cam([3.4, 1.1, 2.6], [0, 0, 0], 100, [1.8, 0.5, 1.7], [-0.3, 0, 0], 100, ease="out"),
     {"len": tw(1.0, 0.86), "active": 1, "load": tw(0.2, 0.9)}, focus={"ap": 0.8}, trans={"type": "push", "dur": 0.45},
     labels=[L("Actin", "actin", at=(0.2, 0.95)), L("Myosin", "myosin", at=(0.3, 0.95), warm=True)],
     desc="Molecular mechanism reveal: myosin heads cycle on actin as the sarcomere shortens under load.", sound=["pulse impact", "mechanical ticks"])
shot(5.55, 9.45, "body", cam([-0.75, 0.55, 1.6], [-0.1, 0.32, 0], 50, [-0.95, 0.5, 1.15], [-0.15, 0.32, 0], 55, orbit=[0, -6]),
     {"xray": 1, "curl": [[0, 0.1], [0.25, 0.95], [0.5, 0.1], [0.75, 0.95], [1, 0.3]], "dumbbell": 1, "wire": 0.18, "glowArm": [[0, 0.2], [0.25, 0.9], [0.5, 0.25], [0.75, 0.9], [1, 0.3]]},
     focus={"ap": 0.45}, trans={"type": "dissolve", "dur": 0.5},
     labels=[L("Biceps brachii", "biceps", sub="contracting against resistance", at=(0.15, 0.95))],
     desc="X-ray athlete performs curls; the working biceps glows with each contraction.", sound=["soft cloth/metal movement", "low pulse per rep"])
shot(9.45, 10.62, "blood", cam([0.4, 0.3, 8.0], [0, 0, -4], 35, [0.2, 0.1, 5.5], [0, 0, -6], 35, ease="linear"),
     {"flow": 1.0, "glucose": 1.0, "gglow": 0.8}, focus={"ap": 0.5}, trans={"type": "cut", "dur": 0},
     labels=[L("Nutrition", None, sub="nutrients carried in the blood", screen=[0.5, 0.17], at=(0.05, 0.98), side=1, len=0)],
     desc="Cut into the bloodstream: red cells and glucose flow past.", sound=["fluid whoosh"])
shot(10.62, 11.8, "synthesis", cam([-1.0, 1.4, 5.2], [-1.6, 1.2, 0], 85, [-1.3, 1.5, 4.6], [-1.6, 1.3, 0], 85),
     {"chain": tw(0.35, 0.6), "aa": 1, "fuel": 0}, focus={"ap": 0.7}, trans={"type": "cut", "dur": 0},
     labels=[L("Recovery", None, sub="repair and protein synthesis", screen=[0.5, 0.17], at=(0.05, 0.98), side=1, len=0)],
     desc="Recovery: a ribosome extends a new protein chain.", sound=["soft chime", "organic bubbles"])
shot(11.8, 14.35, "cell", cam([2.4, 0.7, 10.0], [0, -0.1, 0], 35, [1.4, 0.5, 8.6], [0, -0.2, 0], 35),
     {"dock": 1, "signal": tw(0, 1, (0, 0.5)), "glut": tw(0, 0.4, (0.3, 1)), "glucose": 1},
     focus={"ap": 0.5}, trans={"type": "dissolve", "dur": 0.4},
     labels=[L("Cell signalling", "kinase", sub="conceptual signal relay", at=(0.2, 0.95))],
     desc="Signals that drive adaptation: an activated receptor relays signals into the muscle cell.", sound=["signal pulses"])
shot(14.35, 17.0, "fibers", cam([6.5, 2.0, 5.0], [-0.5, 0, 0], 35, [5.2, 1.4, 4.0], [-0.5, 0, 0], 35),
     {"grow": tw(0, 0.6), "glow": 1}, focus={"ap": 0.4}, trans={"type": "dissolve", "dur": 0.6},
     title={"text": "The Science of Muscle Growth", "kicker": "A scientific documentary", "at": [0.2, 2.5], "vlines": ["The Science of", "Muscle Growth"]},
     desc="Title card over a muscle bundle that gradually thickens (hypertrophy).", sound=["title hit", "music swell"], post={"bloom": 0.36})

# ===================== 2. GLUCOSE-BASED POWDERS (17 - 34) =====================
CH2 = {"n": 2, "text": "Glucose-based carbohydrate powders"}
shot(17.0, 21.6, "powder", cam([-5.5, 1.5, 4.5], [-1.0, 0.5, 0], 50, [-2.6, 1.3, 4.6], [-0.6, 0.5, 0], 50),
     {"pour": 1}, focus={"ap": 0.7}, trans={"type": "dissolve", "dur": 0.7}, chapter=CH2, conceptual=False,
     labels=[L("Dextrose", "h0", sub="glucose (D-glucose)", at=(0.72, 0.98))],
     desc="Macro dolly across three heaps of carbohydrate powder; a stream of dextrose pours onto the first heap.", sound=["powder pour texture", "low drone"])
shot(21.6, 23.85, "molecules", cam([0, 5.5, 12.5], [0, 0, 0], 50, [0, 4.0, 10.0], [0, 0, 0], 50),
     {"show": "dextrin", "spin": 0.4, "glow": 0.6}, focus={"ap": 0.5}, trans={"type": "push", "dur": 0.5},
     labels=[L("Highly branched cyclic dextrin", "backbone", sub="cyclic glucose polymer (simplified)", at=(0.1, 0.98))],
     desc="Molecular view of a highly branched cyclic dextrin: a cyclic backbone of glucose units with branched clusters.", sound=["crystalline shimmer"])
shot(23.85, 25.45, "powder", cam([7.2, 1.9, 5.4], [2.4, 0.55, 0.3], 70, [6.6, 1.7, 4.9], [2.4, 0.5, 0.3], 70),
     {}, focus={"ap": 0.9}, trans={"type": "cut", "dur": 0}, conceptual=False,
     labels=[L("Karbolyn", "h2", sub="branded carbohydrate powder", at=(0.08, 0.98))],
     desc="Macro close-up of the third heap, identified as a branded product (no composition claims).", sound=["soft granular rustle"])
shot(25.45, 29.2, "powder", cam([0, 1.4, 7.5], [0, 0.9, 0], 35, [0, 2.2, 6.2], [0, 1.8, 0], 35),
     {"lift": tw(0, 1, (0.05, 0.9)), "liftHeap": 9, "glyphs": tw(0, 1, (0.12, 0.6))}, focus={"ap": 0.5}, trans={"type": "cut", "dur": 0},
     labels=[L("Carbohydrate", "glyph", sub="digested to glucose", at=(0.55, 0.98))],
     desc="Grains lift from all heaps and resolve into glucose molecules: the products supply carbohydrate.", sound=["rising granular swirl", "airy shimmer"])
shot(29.2, 34.0, "body", cam([0.9, 0.7, 1.9], [0, 0.35, 0], 50, [0.6, 0.55, 1.5], [-0.1, 0.35, 0], 50, orbit=[0, 10]),
     {"xray": 1, "curl": [[0, 0.1], [0.3, 0.95], [0.6, 0.1], [0.9, 0.95], [1, 0.8]], "curlL": [[0, 0.95], [0.3, 0.1], [0.6, 0.95], [0.9, 0.1], [1, 0.2]], "dumbbell": 1, "wire": 0.16, "glowArm": 1.0},
     focus={"ap": 0.4}, trans={"type": "dissolve", "dur": 0.6},
     labels=[L("Energy availability", "biceps", sub="around demanding sessions", at=(0.12, 0.95), warm=True)],
     note={"text": "Carbohydrate powders are a convenient carbohydrate source. They are not uniquely anabolic; any benefit depends on training demands and total daily intake.", "at": [0.12, 0.97]},
     desc="X-ray athlete trains alternating curls; working muscles glow to show energy demand.", sound=["rep pulses", "breathing ambience"])

# ===================== 3. GLUCOSE & METABOLISM (34 - 51) =====================
CH3 = {"n": 3, "text": "Glucose and muscle metabolism"}
shot(34.0, 37.95, "molecules", cam([0, 1.4, 11.5], [0, 0, 0], 50, [0, 0.8, 9.6], [0, 0, 0], 50),
     {"show": "glucose", "spin": 0.35}, focus={"ap": 0.5}, trans={"type": "dissolve", "dur": 0.7}, chapter=CH3,
     labels=[L("Glucose", "ring", sub="C6H12O6 · beta-D-glucopyranose", at=(0.2, 0.97))],
     desc="Ball-and-stick glucose molecule rotating in a dark lab space (CPK colours).", sound=["glassy tone"])
shot(37.95, 39.55, "synthesis", cam([9.5, 1.8, 6.0], [3.4, -0.5, -0.7], 50, [8.6, 1.2, 5.2], [3.4, -0.6, -0.8], 50),
     {"chain": 0.4, "aa": 0.3, "fuel": 1, "atp": 1}, focus={"ap": 0.6}, trans={"type": "push", "dur": 0.4},
     labels=[L("Mitochondrion", "mito", sub="glucose-derived fuel -> ATP", at=(0.1, 0.97), warm=True)],
     desc="Glucose streams into a mitochondrion that releases ATP sparks: energy supply.", sound=["energy crackle"])
shot(39.55, 41.75, "molecules", cam([0, 2.0, 11.0], [0, 0, 0], 50, [0, 1.4, 9.0], [0, 0, 0], 50),
     {"show": "glycogen", "build": tw(0.25, 1.0), "glow": 0.8, "spin": 0.3}, focus={"ap": 0.5}, trans={"type": "cut", "dur": 0},
     labels=[L("Glycogen", "tiers", sub="stored glucose, replenished", at=(0.15, 0.97))],
     desc="A glycogen granule rebuilds tier by tier around its glycogenin core (replenishment).", sound=["building chimes"])
shot(41.75, 46.25, "blood", cam([0.6, 0.4, 6.0], [0, 0, -6], 50, [0.0, 0.1, 2.0], [0, 0, -9], 50, ease="linear"),
     {"flow": 0.8, "glucose": 0.8, "insulin": 1, "gglow": 0.6}, focus={"ap": 0.6}, trans={"type": "cut", "dur": 0},
     labels=[L("Insulin", None, sub="hormone released in response to glucose", screen=[0.62, 0.36], at=(0.25, 0.97), side=1, len=0)],
     desc="Bloodstream with circulating insulin and glucose: the hormonal environment around exercise.", sound=["fluid flow", "soft heartbeat"])
shot(46.25, 51.0, "fibers", cam([7.0, 2.6, 6.0], [-1.0, 0, 0], 35, [6.0, 2.0, 5.2], [-1.0, 0, 0], 35, orbit=[0, 8]),
     {"glow": 0.8, "grow": 0.1}, focus={"ap": 0.35}, trans={"type": "dissolve", "dur": 0.6},
     labels=[L("Training", "cap", at=(0.08, 0.95), sub="the growth stimulus"), L("Nutrition", "sheath", at=(0.22, 0.95), sub="protein + total energy", warm=True),
             L("Recovery", "bundle", at=(0.36, 0.95), sub="sleep and rest")],
     desc="The wider context: the muscle bundle surrounded by the factors that determine the outcome.", sound=["calm pad"])

# ===================== 4. ANABOLIC & ANTI-CATABOLIC (51 - 68) =====================
CH4 = {"n": 4, "text": "Anabolic and anti-catabolic"}
shot(51.0, 55.1, "cell", cam([-4.5, 1.3, 11.5], [-0.5, 0.4, 0], 35, [-2.6, 0.9, 9.8], [-0.4, 0.3, 0], 35),
     {"dock": tw(0, 0.55), "signal": 0, "glut": 0, "glucose": 1}, focus={"ap": 0.45}, trans={"type": "dissolve", "dur": 0.7}, chapter=CH4,
     labels=[L("Insulin", "insulin", at=(0.25, 0.97), warm=True), L("Insulin receptor", "receptor", sub="muscle cell membrane", at=(0.45, 0.97))],
     desc="Establishing shot of the muscle-cell membrane; insulin approaches its receptor.", sound=["deep ambience", "drift"])
shot(55.1, 58.85, "cell", cam([1.2, 0.4, 9.0], [0.4, -0.6, 0], 35, [2.8, 0.1, 9.4], [0.8, -0.9, 0], 35),
     {"dock": 1, "signal": tw(0.2, 1, (0, 0.35)), "glut": tw(0, 1, (0.2, 0.9)), "uptake": tw(0, 1, (0.55, 1)), "glucose": 1},
     focus={"ap": 0.45}, trans={"type": "cut", "dur": 0},
     labels=[L("Insulin signalling", "kinase", at=(0.05, 0.6), warm=True), L("GLUT4", "glut", sub="moves to the membrane, glucose enters", at=(0.45, 0.98))],
     desc="Insulin binding activates the receptor; signal relay moves GLUT4 vesicles to the membrane and glucose enters.", sound=["activation chime", "pulse train"])
shot(58.85, 63.45, "synthesis", cam([0.5, 1.6, 10.5], [0.4, 0.6, 0], 35, [0.3, 1.3, 9.0], [0.4, 0.6, 0], 35),
     {"chain": tw(0.3, 0.9), "aa": 1, "fuel": 1, "atp": 1}, focus={"ap": 0.4}, trans={"type": "dissolve", "dur": 0.6},
     labels=[L("Amino acids", "aa", sub="spared for protein building", at=(0.1, 0.97)), L("Glucose -> energy", "mito", at=(0.25, 0.97), warm=True)],
     note={"text": "Protein-sparing: adequate carbohydrate reduces the use of amino acids as fuel. Its contribution to muscle growth is modest compared with training and protein intake.", "at": [0.15, 0.97]},
     desc="Glucose fuels the mitochondrion while amino acids are routed to the ribosome for synthesis.", sound=["soft energy hum"])
shot(63.45, 68.0, "fibers", cam([4.2, 0.6, 2.6], [0.5, 0, 0], 85, [5.0, 1.0, 3.4], [0.4, 0, 0], 85),
     {"grow": 0, "glow": tw(1.0, 0.55), "mito": 0.6}, focus={"ap": 0.7}, trans={"type": "dissolve", "dur": 0.6},
     note={"label": "Key point", "text": "Muscle growth needs a training stimulus, sufficient protein and energy, and recovery. Carbohydrate alone does not drive hypertrophy.", "at": [0.12, 0.97]},
     desc="The fibre cross-section dims without growing: carbohydrates alone do not guarantee growth.", sound=["music dips", "low tone"])

# ===================== 5. ECCENTRIC OVERLOAD (68 - 85) =====================
CH5 = {"n": 5, "text": "Eccentric overload"}
shot(68.0, 72.8, "body", cam([1.4, 0.45, 1.6], [0, 0.3, 0], 50, [1.1, 0.4, 1.25], [-0.05, 0.3, 0], 50, orbit=[0, -8]),
     {"xray": 1, "curl": tw(1.0, 0.1, (0.15, 0.95), "sine"), "dumbbell": 1, "wire": 0.18, "glowArm": 0.9},
     focus={"ap": 0.4}, trans={"type": "dissolve", "dur": 0.7}, chapter=CH5,
     title={"text": "Eccentric Overload", "kicker": "Training concept", "at": [0.6, 4.2], "y": 0.5},
     desc="Title over the x-ray athlete slowly lowering a dumbbell.", sound=["title hit", "tension drone"])
shot(72.8, 75.95, "body", cam([-1.6, 0.4, 0.55], [-0.2, 0.28, 0.05], 50, [-1.45, 0.42, 0.75], [-0.2, 0.26, 0.05], 50),
     {"xray": 1, "curl": tw(1.0, 0.05, (0.05, 0.95), "sine"), "dumbbell": 1, "wire": 0.2, "glowArm": 1.0},
     focus={"ap": 0.6}, trans={"type": "cut", "dur": 0},
     labels=[L("Eccentric phase", "forearm", sub="the lowering phase", at=(0.15, 0.97), warm=True)],
     desc="Side profile of the lowering phase: the elbow extends under control.", sound=["slow creak", "breath"])
shot(75.95, 78.65, "sarcomere", cam([2.6, 1.2, 3.4], [0, 0, 0], 50, [1.8, 0.8, 2.8], [0, 0, 0], 50),
     {"len": tw(0.92, 1.18), "active": 0.8, "load": 1.0, "zglow": 0.5}, focus={"ap": 0.6}, trans={"type": "push", "dur": 0.45},
     labels=[L("Lengthening under load", "titin", sub="myosin heads still generate force", at=(0.12, 0.97), warm=True)],
     desc="Sarcomeres lengthen while myosin heads stay engaged and glowing: force while lengthening.", sound=["stretch tension", "heads clicking"])
shot(78.65, 85.0, "fibers", cam([3.2, 1.8, 4.6], [0.2, 0, 0], 50, [2.4, 0.6, 3.0], [0.4, 0, 0], 85, orbit=[0, -10]),
     {"pulse": 1, "glow": tw(0.8, 1.3), "grow": tw(0, 0.25, (0.4, 1))}, focus={"ap": 0.6}, trans={"type": "dissolve", "dur": 0.6},
     labels=[L("Training stimulus", "cap", sub="mechanical tension", at=(0.2, 0.95), warm=True)],
     desc="Fibres pulse with tension then begin to adapt: a powerful training stimulus.", sound=["rhythmic pulses", "swell"], post={"bloom": 0.38})

# ===================== 6. FOUR WEEKS ON / EIGHT OFF (85 - 102) =====================
CH6 = {"n": 6, "text": "Four weeks on, eight weeks off"}
shot(85.0, 90.2, "timeline", cam([0, 1.8, 15.5], [0, 0.3, 0], 28, [0, 1.3, 13.5], [0, 0.3, 0], 28),
     {"mode": "onoff", "reveal": tw(0, 1, (0.05, 0.7))}, focus={"ap": 0.35}, trans={"type": "dissolve", "dur": 0.7}, chapter=CH6, conceptual=False,
     labels=[L("4 weeks on", "on", sub="eccentric overload block", at=(0.55, 0.98), warm=True), L("8 weeks off", "off", sub="away from that method", at=(0.75, 0.98))],
     desc="Twelve glass week-tiles light up: four lit in crimson, eight dimmed.", sound=["tile clicks", "pulse"])
shot(90.2, 97.0, "timeline", cam([-9.5, 0.5, 6.8], [-4.5, 0.2, 0], 50, [3.5, 0.7, 7.0], [6.5, 0.2, 0], 50, ease="sine"),
     {"mode": "onoff", "reveal": 1}, focus={"ap": 0.6}, trans={"type": "cut", "dur": 0}, conceptual=False,
     labels=[L("Demanding block", "w2", at=(0.05, 0.4), warm=True), L("Extended period away", "w9", at=(0.5, 0.97))],
     desc="Low tracking dolly along the tiles from the demanding block into the long recovery period.", sound=["dolly whoosh"])
shot(97.0, 102.0, "timeline", cam([2.0, 4.5, 14.0], [0, 0.2, 0], 35, [1.0, 3.5, 13.0], [0, 0.2, 0], 35),
     {"mode": tw(0, 0, ), "reveal": 1}, focus={"ap": 0.4}, trans={"type": "dissolve", "dur": 0.5}, conceptual=False,
     note={"label": "Scientific context", "text": "This is one specific protocol. Periodisation schemes vary widely, and a 4-on / 8-off eccentric cycle is not an established requirement.", "at": [0.05, 0.97]},
     desc="High angle; tiles return to neutral while a context note clarifies the protocol's status.", sound=["neutral pad"])
S[-1]["params"]["mode"] = "neutral"

# ===================== 7. THE EIGHT-SECOND NEGATIVE (102 - 119) =====================
CH7 = {"n": 7, "text": "The eight-second negative"}
shot(102.0, 110.85, "body", cam([1.6, 0.62, 2.0], [-0.12, 0.3, 0], 70, [1.3, 0.48, 1.55], [-0.2, 0.3, 0.02], 70, orbit=[0, -18], ease="sine"),
     {"xray": tw(0.3, 1, (0, 0.2)), "curl": tw(1.0, 0.04, (0.11, 0.98), "linear"), "dumbbell": 1, "wire": 0.18, "glowArm": tw(0.5, 1.2)},
     focus={"ap": 0.5}, trans={"type": "dissolve", "dur": 0.7}, chapter=CH7,
     timer={"show": [102.4, 110.85], "start": 102.95, "end": 110.75, "count": 8, "label": "Final repetition · lowering"},
     desc="Final repetition: the dumbbell is lowered over about eight seconds, timed by a minimal counter.", sound=["clock ticks each second", "tension drone"])
shot(110.85, 114.1, "sarcomere", cam([0.5, 2.6, 4.2], [0, 0, 0], 50, [-0.6, 1.8, 3.6], [0, 0, 0], 50),
     {"len": tw(0.95, 1.15, ease="linear"), "active": 0.5, "load": 0.8}, focus={"ap": 0.6}, trans={"type": "push", "dur": 0.45},
     labels=[L("Controlled lengthening", "titin", at=(0.12, 0.97), warm=True)],
     desc="Inside the fibre the sarcomeres lengthen slowly and evenly under load.", sound=["slow stretch"])
shot(114.1, 119.0, "body", cam([0.0, 0.55, 2.1], [0, 0.3, 0], 50, [0.25, 0.5, 1.8], [0, 0.3, 0], 50),
     {"xray": 1, "curl": [[0, 1], [0.6, 0.05], [1, 0.05]], "curlL": [[0, 0.9], [0.1, 0.1], [0.2, 0.9], [0.3, 0.1], [0.4, 0.9], [0.5, 0.1], [0.6, 0.9], [0.7, 0.1], [0.8, 0.9], [0.9, 0.1], [1, 0.5]],
      "dumbbell": 1, "wire": 0.16, "glowArm": 0.8}, focus={"ap": 0.35}, trans={"type": "cut", "dur": 0},
     labels=[L("Controlled", "biceps", sub="slow, deliberate lowering", at=(0.1, 0.97), warm=True, side=-1, len=260), L("Fast", "bicepsL", sub="as quickly as possible", at=(0.25, 0.97), side=1, len=260)],
     desc="Side-by-side comparison: one arm lowers slowly under control, the other moves quickly.", sound=["contrasting fast whips vs slow drone"])

# ===================== 8. MA30 PROTOCOL (119 - 136) =====================
CH8 = {"n": 8, "text": "MA30 Aggression Intelligence Protocol"}
shot(119.0, 125.1, "fibers", cam([9.0, 3.0, 7.0], [-1.5, 0, 0], 35, [7.5, 1.2, 6.0], [-1.0, 0, 0], 35, orbit=[0, 12]),
     {"glow": 0.75, "grow": 0.2, "explode": tw(0, 0.4)}, focus={"ap": 0.3}, trans={"type": "dissolve", "dur": 0.7}, chapter=CH8,
     title={"text": "MA30 Aggression Intelligence Protocol", "kicker": "Presented in the source", "at": [0.6, 5.2], "size": 52, "vlines": ["MA30 Aggression", "Intelligence Protocol"]},
     note={"label": "Scientific context", "text": "A named protocol presented in the source material, not a recognised scientific standard.", "at": [0.55, 0.98]},
     desc="Title card over a slowly separating muscle bundle.", sound=["title hit", "pulse"])
shot(125.1, 128.0, "timeline", cam([0, 2.6, 15.5], [0, 0.2, 0], 28, [0, 1.6, 13.5], [0, 0.3, 0], 28),
     {"mode": "phases", "reveal": tw(0, 1, (0, 0.8))}, focus={"ap": 0.35}, trans={"type": "dissolve", "dur": 0.5}, conceptual=False,
     desc="Week tiles light up in four phase colours.", sound=["tile cascade"])
shot(128.0, 129.75, "body", cam([0.9, 0.5, 1.8], [-0.15, 0.3, 0], 70, [0.75, 0.48, 1.6], [-0.15, 0.3, 0], 70),
     {"xray": 1, "curl": [[0, 0.1], [0.45, 1.0], [1, 0.2]], "dumbbell": 1, "glowArm": 1.2, "wire": 0.2}, focus={"ap": 0.5}, trans={"type": "cut", "dur": 0},
     labels=[L("Strength work", None, screen=[0.5, 0.17], at=(0.05, 0.98), side=1, len=0)],
     desc="A heavy, powerful curl.", sound=["impact"])
shot(129.75, 131.45, "fibers", cam([3.0, 0.5, 2.2], [0.5, 0, 0], 85, [2.7, 0.4, 2.0], [0.5, 0, 0], 85),
     {"grow": tw(0.1, 0.7), "glow": 1.1}, focus={"ap": 0.8}, trans={"type": "cut", "dur": 0},
     labels=[L("Hypertrophy training", None, screen=[0.5, 0.17], at=(0.05, 0.98), side=1, len=0)],
     desc="Fascicles thicken: hypertrophy.", sound=["swell"])
shot(131.45, 132.95, "sarcomere", cam([2.0, 0.6, 2.6], [0, 0, 0], 85, [1.6, 0.6, 2.4], [0, 0, 0], 85),
     {"len": tw(0.95, 1.15, ease="linear"), "active": 0.5, "load": 0.9}, focus={"ap": 0.7}, trans={"type": "cut", "dur": 0},
     labels=[L("Slow negatives", None, screen=[0.5, 0.17], at=(0.05, 0.98), side=1, len=0)],
     desc="Sarcomeres lengthening slowly.", sound=["stretch"])
shot(132.95, 136.0, "synthesis", cam([-1.0, 1.8, 7.5], [-1.4, 1.2, 0], 50, [-0.6, 1.5, 6.5], [-1.2, 1.2, 0], 50),
     {"chain": tw(0.5, 0.95), "aa": 0.9, "fuel": 0.4, "atp": 0.4}, focus={"ap": 0.5}, trans={"type": "cut", "dur": 0},
     labels=[L("Recovery-focused methods", None, screen=[0.5, 0.17], at=(0.05, 0.98), side=1, len=0)],
     desc="Repair: protein synthesis continues calmly.", sound=["calm chime"])

# ===================== 9. THE TRAINING PHASES (136 - 155) =====================
CH9 = {"n": 9, "text": "The training phases"}
shot(136.0, 142.0, "timeline", cam([-8.0, 1.2, 6.5], [-4.6, 0.3, 0], 50, [-6.0, 1.0, 5.2], [-4.6, 0.4, 0], 50),
     {"mode": "phases", "reveal": 1, "focusPhase": 0}, focus={"ap": 0.6}, trans={"type": "dissolve", "dur": 0.6}, chapter=CH9, conceptual=False,
     labels=[L("Weeks 1-4", "p0", sub="strength + hypertrophy", at=(0.25, 0.97), warm=True)],
     desc="Weeks 1-4 rise and glow crimson.", sound=["tile rise"])
shot(142.0, 144.75, "timeline", cam([-1.0, 1.0, 6.0], [-0.6, 0.3, 0], 50, [0.2, 1.1, 5.6], [-0.6, 0.3, 0], 50),
     {"mode": "phases", "reveal": 1, "focusPhase": 1}, focus={"ap": 0.6}, trans={"type": "cut", "dur": 0}, conceptual=False,
     labels=[L("Weeks 5-8", "p1", sub="slow negatives", at=(0.1, 0.97), warm=True)],
     desc="Weeks 5-8 glow amber.", sound=["tile rise"])
shot(144.75, 147.55, "timeline", cam([6.5, 0.8, 6.0], [4.0, 0.3, 0], 50, [5.6, 1.0, 5.4], [4.0, 0.3, 0], 50),
     {"mode": "phases", "reveal": 1, "focusPhase": 2}, focus={"ap": 0.6}, trans={"type": "cut", "dur": 0}, conceptual=False,
     labels=[L("Weeks 9-11", "p2", sub="rest-pause · cluster sets", at=(0.1, 0.97))],
     note={"label": "Definition", "text": "Rest-pause and cluster sets insert short rests within a set so more repetitions can be performed with a given load.", "at": [0.12, 0.98]},
     desc="Weeks 9-11 glow cyan.", sound=["tile rise"])
shot(147.55, 150.0, "timeline", cam([10.6, 1.4, 5.2], [7.0, 0.4, 0], 50, [10.0, 1.2, 4.7], [7.0, 0.5, 0], 50),
     {"mode": "phases", "reveal": 1, "focusPhase": 3}, focus={"ap": 0.7}, trans={"type": "cut", "dur": 0}, conceptual=False,
     labels=[L("Week 12", "w12", sub="scheduled deload", at=(0.1, 0.97))],
     desc="Week 12 glows pale blue: the deload.", sound=["soft tone"])
shot(150.0, 155.0, "timeline", cam([0, 3.2, 13.0], [0, 0.3, 0], 28, [0, 2.0, 16.5], [0, 0.4, 0], 28, ease="sine"),
     {"mode": "phases", "reveal": 1, "focusPhase": -1}, focus={"ap": 0.35}, trans={"type": "cut", "dur": 0}, conceptual=False,
     labels=[L("Strength + hypertrophy", "p0", at=(0.2, 0.97), warm=True, rise=-60, len=90), L("Slow negatives", "p1", at=(0.28, 0.97), warm=True, rise=-150, len=90), L("Rest-pause · cluster", "p2", at=(0.36, 0.97), rise=-60, len=90, side=1), L("Deload", "p3", at=(0.44, 0.97), rise=-150, len=90, side=-1)],
     desc="Pull back to show all four phases, each with a different emphasis.", sound=["resolve chord"])

# ===================== 10. THE FINAL DELOAD (155 - 172.37) =====================
CH10 = {"n": 10, "text": "The final deload"}
shot(155.0, 158.55, "timeline", cam([10.0, 2.0, 6.0], [7.0, 0.6, 0], 50, [9.4, 1.5, 4.6], [7.1, 0.7, 0], 50),
     {"mode": "phases", "reveal": 1, "focusPhase": 3, "raise12": tw(0, 1)}, focus={"ap": 0.6}, trans={"type": "dissolve", "dur": 0.6}, chapter=CH10, conceptual=False,
     labels=[L("Week 12", "w12", sub="deload week", at=(0.2, 0.97))],
     desc="Week 12 rises from the row.", sound=["rise tone"])
shot(158.55, 160.95, "body", cam([0.8, 0.6, 1.7], [-0.1, 0.32, 0], 50, [0.7, 0.55, 1.5], [-0.1, 0.32, 0], 50),
     {"xray": 1, "curl": [[0, 0.1], [0.45, 0.8], [1, 0.1]], "dumbbell": 1, "glowArm": 0.3, "wire": 0.14}, focus={"ap": 0.4}, trans={"type": "dissolve", "dur": 0.5},
     labels=[L("Lower load · slower tempo", "biceps", at=(0.1, 0.97))],
     desc="A light, slow curl with a calmer glow.", sound=["calm drone"], post={"exposure": 0.95})
shot(160.95, 167.3, "fibers", cam([7.5, 2.2, 6.0], [-1.0, 0, 0], 35, [6.2, 1.6, 4.8], [-0.8, 0, 0], 35, orbit=[0, -12]),
     {"glow": 0.9, "grow": tw(0.1, 0.35)}, focus={"ap": 0.35}, trans={"type": "dissolve", "dur": 0.6},
     labels=[L("Training stress", "cap", at=(0.05, 0.97), warm=True), L("Recovery", "bundle", at=(0.53, 0.97)), L("Nutrition", "sheath", at=(0.66, 0.97)), L("Consistency", "fascicle", at=(0.83, 0.97))],
     desc="Balance: the muscle bundle with training stress, recovery, nutrition and consistency appearing as spoken.", sound=["balanced pad"])
shot(167.3, 170.05, "body", cam([0.0, 0.45, 1.2], [0, 0.35, 0], 50, [0.0, 0.5, 2.4], [0, 0.32, 0], 35, ease="sine"),
     {"xray": 1, "curl": 0.15, "curlL": 0.15, "dumbbell": 0, "wire": 0.18, "glowArm": 0.5, "hyper": 0.5}, focus={"ap": 0.4}, trans={"type": "cut", "dur": 0},
     desc="Pull back from the chest to reveal the whole x-ray figure: train intelligently, recover properly.", sound=["swell"])
shot(170.05, DUR, "fibers", cam([4.0, 0.8, 2.8], [0.5, 0, 0], 50, [9.5, 3.0, 8.0], [-1.0, 0, 0], 35, ease="sine"),
     {"glow": 1.0, "grow": 0.35}, focus={"ap": 0.4}, trans={"type": "dissolve", "dur": 0.5},
     title={"text": "Understand the Process", "kicker": "The science of muscle growth", "at": [0.3, 2.3], "vlines": ["Understand", "the Process"]},
     desc="Final pull-back from the muscle bundle with the closing title, fading to black.", sound=["final hit", "music resolve"])

# ---------------- validation + export
for i, s in enumerate(S):
    s["id"] = f"S{i+1:02d}"
    if i: assert abs(S[i-1]["end"] - s["start"]) < 1e-6, (S[i-1]["id"], s["id"])
    s.setdefault("trans", {"type": "cut", "dur": 0})
assert S[0]["start"] == 0 and abs(S[-1]["end"] - DUR) < 1e-6
for s in S:
    s["narration"] = " ".join(w["word"] for w in WORDS if s["start"] <= (w["start"] + w["end"]) / 2 < s["end"])
covered = sum(len(s["narration"].split()) for s in S)
assert covered == len(WORDS), (covered, len(WORDS))
long = [s["id"] for s in S if s["end"] - s["start"] > 7.0]
json.dump({"duration": DUR, "fps": 30, "shots": S}, open(f"{ROOT}/storyboard/shots.json", "w"), indent=1)

FOCAL = lambda c: f"{c['from']['mm']}mm -> {c['to']['mm']}mm"
prod = []
for s in S:
    wi = WORLD_INFO[s["world"]]
    c = s["cam"]
    move = "orbit %s deg" % c["orbit"] if c.get("orbit") else ("dolly/track" if c["from"]["p"] != c["to"]["p"] else "locked-off")
    prod.append({
        "id": s["id"], "start": s["start"], "end": s["end"], "duration": round(s["end"] - s["start"], 3),
        "narration": s["narration"], "scene_description": s.get("desc", ""), "world": s["world"],
        "main_subject": wi["subject"], "anatomical_requirements": wi["anatomy"], "environment": wi["environment"],
        "lighting": wi["lighting"], "materials": wi["materials"],
        "camera_position": {"start": c["from"]["p"], "end": c["to"]["p"], "target_start": c["from"]["t"], "target_end": c["to"]["t"]},
        "camera_movement": f"{move}, {FOCAL(c)}, ease {c.get('ease','inOut')}, aperture {s.get('focus',{}).get('ap',0.6)}",
        "animation": {k: v for k, v in s["params"].items()},
        "motion_graphics": {"labels": [l["text"] for l in s.get("labels", [])], "title": s.get("title", {}).get("text"), "context_note": s.get("note", {}).get("text"),
                            "timer": bool(s.get("timer"))},
        "transition_in": s["trans"], "sound_design": s.get("sound", []),
        "conceptual_visualization": s.get("conceptual", True),
    })
json.dump({"title": "The Science of Muscle Growth", "duration": DUR, "fps": 30, "shot_count": len(S), "scenes": prod},
          open(f"{ROOT}/storyboard/production.json", "w"), indent=1)
sem = [{"section": sec["id"], "title": sec["title"], "start": sec["start"], "end": sec["end"],
        "clauses": [{"start": c["start"], "end": c["end"], "text": c["text"],
                     "topic": next((s["desc"] for s in S if s["start"] <= c["start"] < s["end"]), "")} for c in sec["clauses"]]} for sec in T["sections"]]
json.dump(sem, open(f"{ROOT}/storyboard/semantic_timeline.json", "w"), indent=1)
lens = [s["end"] - s["start"] for s in S]
print(f"{len(S)} shots, {covered} words covered, mean {sum(lens)/len(lens):.2f}s, max {max(lens):.2f}s, long>7s: {long}")
