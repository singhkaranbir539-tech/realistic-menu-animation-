"""Generate anatomical meshes for the documentary.

Sources (all openly licensed, see production_notes.txt):
  * TotalSegmentator v2.0.1 subject s1380 (CC BY 4.0) via the pyvista data repo:
    whole-body CT + per-structure segmentation masks -> marching-cubes meshes.
  * FreeSurfer fsaverage5 pial surfaces (bundled with nilearn) -> folded cortex.

Outputs binary PLY meshes (metres, Blender Z-up: X=patient left->right, Y=posterior, Z=superior)
into assets/human_anatomy and assets/brain.
"""
import gzip, os, sys, numpy as np, nibabel as nib
from scipy import ndimage as ndi
from skimage import measure

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "assets/human_anatomy/raw/s1380")
OUT = os.path.join(ROOT, "assets/human_anatomy")
BRAIN_OUT = os.path.join(ROOT, "assets/brain")
VOX = 1.5  # mm


def write_ply(path, verts, faces):
    verts = np.asarray(verts, np.float32); faces = np.asarray(faces, np.int32)
    with open(path, "wb") as f:
        f.write((f"ply\nformat binary_little_endian 1.0\nelement vertex {len(verts)}\n"
                 "property float x\nproperty float y\nproperty float z\n"
                 f"element face {len(faces)}\nproperty list uchar int vertex_indices\nend_header\n").encode())
        f.write(verts.tobytes())
        rec = np.empty(len(faces), dtype=[("n", "u1"), ("i", "<i4", (3,))])
        rec["n"] = 3; rec["i"] = faces
        f.write(rec.tobytes())
    print(f"  wrote {os.path.relpath(path, ROOT)}  v={len(verts)} f={len(faces)}")


def seg(name):
    return np.asarray(nib.load(f"{RAW}/segmentations/{name}.nii.gz").dataobj) > 0


def mesh_from_mask(mask, sigma=1.0, level=0.5, step=1):
    m = ndi.gaussian_filter(mask.astype(np.float32), sigma)
    m = np.pad(m, 2)
    v, f, _, _ = measure.marching_cubes(m, level, step_size=step, spacing=(VOX, VOX, VOX))
    v -= 2 * VOX
    return v, f


def to_world(v):
    # voxel RAS mm -> metres; centre on the body origin computed below
    return (v - ORIGIN) / 1000.0 * np.array([1, -1, 1])  # flip A->posterior so +Y is posterior


ct = np.asarray(nib.load(f"{RAW}/ct.nii.gz").dataobj).astype(np.float32)
print("CT", ct.shape)

# ---------------------------------------------------------------- body / skin shell
body = ct > -400
body = ndi.binary_opening(body, iterations=2)
lab, n = ndi.label(body)
sizes = ndi.sum(body, lab, range(1, n + 1))
body = lab == (1 + int(np.argmax(sizes)))          # drop CT table / blankets
body = ndi.binary_fill_holes(body)

# remove raised arms: anything within ~45 mm of humerus / radius-ulna region, and above the
# shoulders keep only the 2D component that contains the skull/spine centre line.
arm_bones = np.zeros_like(body)
for nme in ["humerus_left", "humerus_right"]:
    arm_bones |= seg(nme)
skull = seg("skull"); brain_m = seg("brain"); cord = seg("spinal_cord")
zs_sk = np.where(skull.any((0, 1)))[0]
clav = seg("clavicula_left") | seg("clavicula_right") | seg("scapula_left") | seg("scapula_right")
z_shoulder = int(np.where(clav.any((0, 1)))[0].max())
print("shoulder z", z_shoulder, "skull z", zs_sk.min(), zs_sk.max())
cx_line = {}
for z in range(body.shape[2]):
    ref = skull[:, :, z] | cord[:, :, z] | brain_m[:, :, z]
    if ref.any():
        cx_line[z] = np.array(ndi.center_of_mass(ref))
keys = sorted(cx_line)
for z in range(z_shoulder - 25, body.shape[2]):
    sl = body[:, :, z]
    if not sl.any():
        continue
    c = cx_line[min(keys, key=lambda k: abs(k - z))]
    l2, n2 = ndi.label(sl)
    if n2 == 0:
        continue
    ii0, jj0 = np.mgrid[:sl.shape[0], :sl.shape[1]]
    cyl = ((ii0 - c[0]) / 50.0) ** 2 + ((jj0 - c[1]) / 70.0) ** 2 < 1.0
    ov = ndi.sum(cyl, l2, range(1, n2 + 1))
    lbl = 1 + int(np.argmax(ov))
    keep = l2 == lbl
    # when the arm touches the head, additionally clip laterally to a head-width ellipse
    if z > z_shoulder + 8:
        ii, jj = np.mgrid[:sl.shape[0], :sl.shape[1]]
        keep &= ((ii - c[0]) / 62.0) ** 2 + ((jj - c[1]) / 80.0) ** 2 < 1.0
    body[:, :, z] = keep
# lateral cut of the shoulders/arms below the head, protecting a head+neck cylinder
heart_m = seg("heart")
ii, jj = np.mgrid[:body.shape[0], :body.shape[1]]
cz = sorted(cx_line)
for z in range(z_shoulder - 70, body.shape[2]):
    c = cx_line[min(cz, key=lambda k: abs(k - z))]
    t = np.clip((z - (z_shoulder - 70)) / 60.0, 0, 1)
    half_w = 125 * (1 - t) + 70 * t           # voxels: taper shoulders toward the neck
    lateral = np.abs(ii - c[0]) > half_w
    arm_near = ndi.binary_dilation(arm_bones[:, :, z], iterations=22) if arm_bones[:, :, z].any() else np.zeros_like(lateral)
    head_cyl = ((ii - c[0]) / 58.0) ** 2 + ((jj - c[1]) / 78.0) ** 2 < 1.0
    body[:, :, z] &= ~((lateral | arm_near) & ~head_cyl)
lab, n = ndi.label(body)
keep_ids = set(np.unique(lab[skull])) | set(np.unique(lab[heart_m]))
keep_ids.discard(0)
body = np.isin(lab, list(keep_ids))
body = ndi.binary_opening(body, iterations=1)
# soften the cut shoulders (outside the head/neck) so the shell reads like a sculpted anatomical bust
soft = ndi.gaussian_filter(body.astype(np.float32), 4.0) > 0.5
zone = np.zeros_like(body)
for z in range(max(0, z_shoulder - 90), body.shape[2]):
    c = cx_line[min(cz, key=lambda k: abs(k - z))]
    zone[:, :, z] = np.abs(ii - c[0]) > 45
body = np.where(zone, soft, body)
lab, n = ndi.label(body)
keep_ids = set(np.unique(lab[skull])) | set(np.unique(lab[heart_m])); keep_ids.discard(0)
body = np.isin(lab, list(keep_ids))
from PIL import Image
Image.fromarray((np.rot90(body.mean(1)) * 255).astype(np.uint8)).save(os.path.join(OUT, "debug_body_coronal.png"))
Image.fromarray((np.rot90(body.mean(0)) * 255).astype(np.uint8)).save(os.path.join(OUT, "debug_body_sagittal.png"))
zb = np.where(body.any((0, 1)))[0]
ib = np.where(body.any((1, 2)))[0]; jb = np.where(body.any((0, 2)))[0]
ORIGIN = np.array([(ib.min() + ib.max()) / 2 * VOX, (jb.min() + jb.max()) / 2 * VOX, zb.min() * VOX])
np.save(os.path.join(OUT, "origin_mm.npy"), ORIGIN)
print("origin", ORIGIN)

os.makedirs(OUT, exist_ok=True); os.makedirs(BRAIN_OUT, exist_ok=True)
print("skin")
v, f = mesh_from_mask(body, sigma=1.6)
write_ply(f"{OUT}/skin.ply", to_world(v), f)

if "--skin-only" in sys.argv:
    sys.exit(0)
# ---------------------------------------------------------------- skeleton & organs
groups = {
    "skeleton": ["skull", "sacrum", "sternum", "costal_cartilages", "clavicula_left", "clavicula_right",
                 "scapula_left", "scapula_right", "hip_left", "hip_right", "femur_left", "femur_right"]
                + [f"rib_{s}_{i}" for s in ("left", "right") for i in range(1, 13)]
                + [f"vertebrae_{v}" for v in ["C1", "C2", "C3", "C4", "C5", "C6", "C7"] +
                   [f"T{i}" for i in range(1, 13)] + [f"L{i}" for i in range(1, 6)] + ["S1"]],
    "heart": ["heart", "atrial_appendage_left"],
    "lungs": ["lung_upper_lobe_left", "lung_lower_lobe_left", "lung_upper_lobe_right",
              "lung_middle_lobe_right", "lung_lower_lobe_right"],
    "airway": ["trachea"],
    "liver": ["liver", "gallbladder"],
    "kidneys": ["kidney_left", "kidney_right", "adrenal_gland_left", "adrenal_gland_right"],
    "gut": ["stomach", "small_bowel", "colon", "duodenum", "esophagus", "pancreas", "spleen"],
    "arteries": ["aorta", "brachiocephalic_trunk", "common_carotid_artery_left", "common_carotid_artery_right",
                 "subclavian_artery_left", "subclavian_artery_right", "iliac_artery_left", "iliac_artery_right",
                 "pulmonary_vein"],
    "veins": ["inferior_vena_cava", "superior_vena_cava", "brachiocephalic_vein_left", "brachiocephalic_vein_right",
              "iliac_vena_left", "iliac_vena_right", "portal_vein_and_splenic_vein"],
    "spinal_cord": ["spinal_cord"],
    "muscles": ["gluteus_maximus_left", "gluteus_maximus_right", "iliopsoas_left", "iliopsoas_right",
                "autochthon_left", "autochthon_right"],
    "brain_ct": ["brain"],
}
for g, names in groups.items():
    m = np.zeros(ct.shape, bool)
    for nme in names:
        p = f"{RAW}/segmentations/{nme}.nii.gz"
        if os.path.exists(p):
            m |= seg(nme)
    if not m.any():
        print("skip", g); continue
    print(g)
    v, f = mesh_from_mask(m, sigma=0.9 if g in ("skeleton", "arteries", "veins", "spinal_cord", "airway") else 1.2)
    write_ply(f"{OUT}/{g}.ply", to_world(v), f)

# ---------------------------------------------------------------- folded cortex (fsaverage5)
import nilearn
ndir = os.path.join(os.path.dirname(nilearn.__file__), "datasets/data/fsaverage5")
bm = brain_m
bi = np.where(bm.any((1, 2)))[0]; bj = np.where(bm.any((0, 2)))[0]; bk = np.where(bm.any((0, 1)))[0]
ct_min = np.array([bi.min(), bj.min(), bk.min()]) * VOX; ct_max = np.array([bi.max(), bj.max(), bk.max()]) * VOX
hemis = {}
for h in ("left", "right"):
    g = nib.load(os.path.join(ndir, f"pial_{h}.gii.gz"))
    hemis[h] = (g.darrays[0].data.astype(np.float64), g.darrays[1].data.astype(np.int32))
    sulc = nib.load(os.path.join(ndir, f"sulc_{h}.gii.gz")).darrays[0].data
    np.save(os.path.join(BRAIN_OUT, f"sulc_{h}.npy"), sulc.astype(np.float32))
allv = np.concatenate([hemis["left"][0], hemis["right"][0]])
fs_min, fs_max = allv.min(0), allv.max(0)
# fsaverage coords are RAS mm; fit the cortex into the subject's segmented brain bounding box (cerebrum)
scale = (ct_max - ct_min) / (fs_max - fs_min)
scale[2] = scale[0] * 0.98  # keep plausible aspect; cerebellum not in pial surface
for h, (v, f) in hemis.items():
    vv = (v - fs_min) * scale + ct_min
    vv[:, 2] += (ct_max[2] - (fs_max[2] - fs_min[2]) * scale[2] - ct_min[2])  # align tops
    write_ply(f"{BRAIN_OUT}/cortex_{h}_inbody.ply", to_world(vv), f)
    # standalone hero brain (centred, metres, scaled to real size ~ 0.17 m long)
    c = (allv.min(0) + allv.max(0)) / 2
    hv = (v - c) / 1000.0 * np.array([1, -1, 1])
    write_ply(f"{BRAIN_OUT}/cortex_{h}_hero.ply", hv, f)
print("done")
