"""
Blender VRC Structured JSON Audit Script (vrc-character-forge)
--------------------------------------------------------------
Designed for MCP-first, low-screenshot inspection of VRChat avatars in Blender.
Quality-first policy: triangle count is reported for visibility but NOT capped for PC.

Usage (Blender MCP / Python Console):
    import sys, json
    sys.path.append("/path/to/vrc-character-forge/scripts")
    import blender_vrc_audit
    report = blender_vrc_audit.run_vrc_audit()
    print(json.dumps(report, ensure_ascii=False, indent=2))

Usage (Headless CLI):
    blender --background avatar.blend --python scripts/blender_vrc_audit.py -- --out audit.json
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import bpy
    import bmesh
    from mathutils import Vector
except ImportError as exc:
    raise SystemExit(
        "This script must be executed inside Blender (Blender MCP or `blender --background --python`)."
    ) from exc


STANDARD_VRC_VISEMES = [
    "vrc.v_sil",
    "vrc.v_pp",
    "vrc.v_ff",
    "vrc.v_th",
    "vrc.v_dd",
    "vrc.v_kk",
    "vrc.v_ch",
    "vrc.v_ss",
    "vrc.v_nn",
    "vrc.v_rr",
    "vrc.v_aa",
    "vrc.v_e",
    "vrc.v_ih",
    "vrc.v_oh",
    "vrc.v_ou",
]

ARKIT_SAMPLE_KEYS = [
    "eyeBlinkLeft",
    "eyeBlinkRight",
    "jawOpen",
    "mouthSmileLeft",
    "mouthSmileRight",
    "browInnerUp",
    "cheekPuff",
]

HUMANOID_CORE_KEYWORDS = {
    "hips": ["hips", "pelvis", "root"],
    "spine": ["spine"],
    "chest": ["chest", "spine1", "spine2"],
    "neck": ["neck"],
    "head": ["head"],
    "left_upper_arm": ["upperarm.l", "upper_arm.l", "leftupperarm", "leftarm", "arm.l"],
    "right_upper_arm": ["upperarm.r", "upper_arm.r", "rightupperarm", "rightarm", "arm.r"],
    "left_lower_arm": ["lowerarm.l", "lower_arm.l", "leftlowerarm", "leftforearm", "forearm.l"],
    "right_lower_arm": ["lowerarm.r", "lower_arm.r", "rightlowerarm", "rightforearm", "forearm.r"],
    "left_hand": ["hand.l", "lefthand", "wrist.l"],
    "right_hand": ["hand.r", "righthand", "wrist.r"],
    "left_upper_leg": ["upperleg.l", "upper_leg.l", "leftupperleg", "thigh.l", "leftupleg"],
    "right_upper_leg": ["upperleg.r", "upper_leg.r", "rightupperleg", "thigh.r", "rightupleg"],
    "left_lower_leg": ["lowerleg.l", "lower_leg.l", "leftlowerleg", "shin.l", "calf.l", "leftleg"],
    "right_lower_leg": ["lowerleg.r", "lower_leg.r", "rightlowerleg", "shin.r", "calf.r", "rightleg"],
    "left_foot": ["foot.l", "leftfoot"],
    "right_foot": ["foot.r", "rightfoot"],
    "left_eye": ["lefteye", "eye.l", "eye_l"],
    "right_eye": ["righteye", "eye.r", "eye_r"],
}


def _vec_close(values: Tuple[float, float, float], target: float, tol: float = 1e-3) -> bool:
    return all(abs(v - target) <= tol for v in values)


def _match_humanoid_bones(bone_names: List[str]) -> Dict[str, Optional[str]]:
    lower_map = [(b, b.lower().replace(" ", "").replace("-", "_")) for b in bone_names]
    matched: Dict[str, Optional[str]] = {}
    for slot, keywords in HUMANOID_CORE_KEYWORDS.items():
        found = None
        for orig, low in lower_map:
            if any(k == low or k in low for k in keywords):
                found = orig
                break
        matched[slot] = found
    return matched


def _inspect_mesh(obj: bpy.types.Object) -> Dict[str, Any]:
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    tri_count = sum(max(0, len(f.verts) - 2) for f in bm.faces)
    non_manifold_edges = sum(1 for e in bm.edges if not e.is_manifold)
    loose_verts = sum(1 for v in bm.verts if len(v.link_edges) == 0)
    zero_area_faces = sum(1 for f in bm.faces if f.calc_area() < 1e-8)
    bm.free()

    mat_slots = [slot.material.name if slot.material else None for slot in obj.material_slots]
    empty_mat_slots = sum(1 for m in mat_slots if m is None)

    has_armature_mod = any(m.type == "ARMATURE" for m in obj.modifiers)
    non_armature_mods = [m.name for m in obj.modifiers if m.type != "ARMATURE"]

    shape_keys: List[str] = []
    if mesh.shape_keys and mesh.shape_keys.key_blocks:
        shape_keys = [kb.name for kb in mesh.shape_keys.key_blocks if kb.name != "Basis"]

    unweighted_verts = 0
    over_4_weight_verts = 0
    if has_armature_mod and len(obj.vertex_groups) > 0:
        for v in mesh.vertices:
            nonzero_groups = [g for g in v.groups if g.weight > 1e-4]
            if len(nonzero_groups) == 0:
                unweighted_verts += 1
            elif len(nonzero_groups) > 4:
                over_4_weight_verts += 1

    world_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_z = min(c.z for c in world_corners) if world_corners else 0.0
    max_z = max(c.z for c in world_corners) if world_corners else 0.0

    return {
        "name": obj.name,
        "vertices": len(mesh.vertices),
        "polygons": len(mesh.polygons),
        "triangles": tri_count,
        "uv_layers": [uv.name for uv in mesh.uv_layers],
        "material_slots": mat_slots,
        "empty_material_slots": empty_mat_slots,
        "non_manifold_edges": non_manifold_edges,
        "loose_vertices": loose_verts,
        "zero_area_faces": zero_area_faces,
        "scale": [round(s, 4) for s in obj.scale],
        "rotation_euler_deg": [round(math.degrees(r), 2) for r in obj.rotation_euler],
        "scale_applied": _vec_close(tuple(obj.scale), 1.0),
        "rotation_applied": _vec_close(tuple(obj.rotation_euler), 0.0),
        "has_armature_modifier": has_armature_mod,
        "non_armature_modifiers": non_armature_mods,
        "shape_key_count": len(shape_keys),
        "shape_keys": shape_keys,
        "unweighted_vertices": unweighted_verts,
        "over_4_weight_vertices": over_4_weight_verts,
        "world_z_range": [round(min_z, 4), round(max_z, 4)],
    }


def run_vrc_audit(include_hidden: bool = False) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    objs = [
        o
        for o in bpy.context.scene.objects
        if include_hidden or (not o.hide_viewport and o.visible_get())
    ]

    mesh_objs = [o for o in objs if o.type == "MESH"]
    armature_objs = [o for o in objs if o.type == "ARMATURE"]

    mesh_reports = [_inspect_mesh(m) for m in mesh_objs]
    total_tris = sum(m["triangles"] for m in mesh_reports)
    unique_materials = sorted(
        {mat for m in mesh_reports for mat in m["material_slots"] if mat is not None}
    )

    if not mesh_objs:
        errors.append("No visible MESH objects found in the current Blender scene.")

    # Compute overall character height and ground offset
    all_min_z = min((m["world_z_range"][0] for m in mesh_reports), default=0.0)
    all_max_z = max((m["world_z_range"][1] for m in mesh_reports), default=0.0)
    total_height = round(all_max_z - all_min_z, 4)

    if mesh_reports and (total_height < 0.3 or total_height > 3.0):
        warnings.append(
            f"Overall model height is {total_height}m (typical VRC avatar is 1.2m-1.8m; check unit scaling)."
        )
    if mesh_reports and abs(all_min_z) > 0.05:
        warnings.append(
            f"Lowest mesh vertex Z is {round(all_min_z, 4)}m (expected near 0.0m ground plane)."
        )

    all_shape_keys = set()
    for m in mesh_reports:
        all_shape_keys.update(m["shape_keys"])

        if not m["uv_layers"]:
            errors.append(f"Mesh '{m['name']}' has no UV layer.")
        if m["empty_material_slots"] > 0:
            errors.append(f"Mesh '{m['name']}' has {m['empty_material_slots']} empty material slot(s).")
        if not m["scale_applied"]:
            warnings.append(f"Mesh '{m['name']}' has unapplied scale {m['scale']}; apply transforms before export.")
        if m["shape_key_count"] > 0 and m["non_armature_modifiers"]:
            errors.append(
                f"Mesh '{m['name']}' has Shape Keys AND unapplied non-Armature modifiers "
                f"{m['non_armature_modifiers']}; Apply Modifiers on export would destroy Shape Keys."
            )
        if m["unweighted_vertices"] > 0:
            errors.append(
                f"Mesh '{m['name']}' has {m['unweighted_vertices']} unweighted vertex/vertices (will spike in Unity)."
            )
        if m["over_4_weight_vertices"] > 0:
            warnings.append(
                f"Mesh '{m['name']}' has {m['over_4_weight_vertices']} vertices influenced by >4 bones "
                "(run Weight Paint -> Limit Total 4 + Normalize All)."
            )
        if m["non_manifold_edges"] > 0:
            warnings.append(
                f"Mesh '{m['name']}' has {m['non_manifold_edges']} non-manifold edges "
                "(verify whether intentional open rims like skirt/sleeves or mesh holes)."
            )
        if m["zero_area_faces"] > 0:
            warnings.append(f"Mesh '{m['name']}' has {m['zero_area_faces']} zero-area degenerate faces.")

    # Armature inspection
    armature_reports: List[Dict[str, Any]] = []
    for arm in armature_objs:
        bone_names = [b.name for b in arm.data.bones]
        humanoid_match = _match_humanoid_bones(bone_names)
        missing_core = [k for k, v in humanoid_match.items() if v is None and not k.endswith("_eye")]
        missing_eyes = [k for k, v in humanoid_match.items() if v is None and k.endswith("_eye")]
        scale_ok = _vec_close(tuple(arm.scale), 1.0)

        if not scale_ok:
            warnings.append(f"Armature '{arm.name}' has unapplied scale {[round(s, 4) for s in arm.scale]}.")
        if missing_core:
            warnings.append(
                f"Armature '{arm.name}' could not auto-match core Humanoid bones by name: {missing_core}. "
                "Verify Unity Humanoid mapping."
            )
        if missing_eyes:
            warnings.append(
                f"Armature '{arm.name}' missing eye bones {missing_eyes} (required for VRChat Eye Look bone tracking)."
            )

        armature_reports.append(
            {
                "name": arm.name,
                "bone_count": len(bone_names),
                "scale": [round(s, 4) for s in arm.scale],
                "scale_applied": scale_ok,
                "humanoid_bone_match": humanoid_match,
                "missing_core_slots": missing_core,
                "missing_eye_slots": missing_eyes,
            }
        )

    if len(armature_objs) == 0:
        warnings.append("No Armature found (acceptable during Stage 1-2; required for Stage 3+).")
    elif len(armature_objs) > 1:
        warnings.append(
            f"Found {len(armature_objs)} Armatures; typically an avatar export should have 1 unified Armature "
            "(unless exporting a standalone Modular Avatar outfit)."
        )

    # BlendShape / Viseme checks
    lower_keys = {k.lower(): k for k in all_shape_keys}
    present_visemes = [v for v in STANDARD_VRC_VISEMES if v in lower_keys]
    missing_visemes = [v for v in STANDARD_VRC_VISEMES if v not in lower_keys]
    has_blink = any("blink" in k for k in lower_keys)
    arkit_hits = [k for k in ARKIT_SAMPLE_KEYS if k.lower() in lower_keys]

    if armature_objs and missing_visemes:
        warnings.append(
            f"Missing {len(missing_visemes)}/15 standard VRC Viseme Shape Keys: {missing_visemes}."
        )
    if armature_objs and not has_blink:
        warnings.append("No Blink Shape Key detected (recommended for VRChat Eye Look auto-blink).")

    return {
        "ok": len(errors) == 0,
        "quality_policy": "quality_first_unlimited_tris",
        "blend_file": bpy.data.filepath or "<unsaved>",
        "summary": {
            "mesh_count": len(mesh_reports),
            "armature_count": len(armature_reports),
            "total_triangles": total_tris,
            "unique_material_count": len(unique_materials),
            "unique_materials": unique_materials,
            "total_height_m": total_height,
            "ground_min_z_m": round(all_min_z, 4),
            "visemes_present": f"{len(present_visemes)}/15",
            "has_blink": has_blink,
            "has_arkit_hints": len(arkit_hits) >= 4,
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
        "errors": errors,
        "warnings": warnings,
        "meshes": mesh_reports,
        "armatures": armature_reports,
        "blendshapes": {
            "present_visemes": present_visemes,
            "missing_visemes": missing_visemes,
            "arkit_sample_hits": arkit_hits,
        },
    }


def _parse_cli_out_path() -> Optional[str]:
    if "--" not in sys.argv:
        return None
    extra = sys.argv[sys.argv.index("--") + 1 :]
    for idx, arg in enumerate(extra):
        if arg == "--out" and idx + 1 < len(extra):
            return extra[idx + 1]
    return None


if __name__ == "__main__":
    result = run_vrc_audit()
    out_path = _parse_cli_out_path()
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(payload, encoding="utf-8")
        print(f"[vrc-character-forge] Audit written to: {out_path}")
    print(payload)
