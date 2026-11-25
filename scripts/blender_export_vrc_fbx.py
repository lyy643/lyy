"""
Blender Standardized VRChat FBX Exporter (vrc-character-forge)
--------------------------------------------------------------
Exports visible ARMATURE and MESH objects with Unity/VRChat-safe settings:
- Scale normalized (FBX_SCALE_ALL)
- Forward -Z, Up Y
- Leaf bones disabled (prevents phantom _end bones)
- Apply Modifiers disabled (preserves Shape Keys / Visemes)
- Excludes cameras, lights, empties

Usage (Blender MCP / Python Console):
    import sys, json
    sys.path.append("/path/to/vrc-character-forge/scripts")
    import blender_export_vrc_fbx
    res = blender_export_vrc_fbx.export_vrc_fbx("D:/vrc/export/avatar.fbx")
    print(json.dumps(res, ensure_ascii=False, indent=2))

Usage (Headless CLI):
    blender --background avatar.blend --python scripts/blender_export_vrc_fbx.py -- --out D:/vrc/export/avatar.fbx
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import bpy
except ImportError as exc:
    raise SystemExit(
        "This script must be executed inside Blender (Blender MCP or `blender --background --python`)."
    ) from exc


def export_vrc_fbx(
    output_path: str,
    embed_textures: bool = False,
    bake_anim: bool = False,
    strict_shape_key_guard: bool = True,
) -> Dict[str, Any]:
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    # Ensure OBJECT mode safely
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    export_targets = [
        o
        for o in bpy.context.scene.objects
        if o.type in {"ARMATURE", "MESH"} and not o.hide_viewport and o.visible_get()
    ]

    if not export_targets:
        return {
            "ok": False,
            "error": "No visible ARMATURE or MESH objects available to export.",
            "output_path": str(out),
        }

    # Guard against unapplied non-Armature modifiers on meshes with Shape Keys
    blocked_meshes: List[Dict[str, Any]] = []
    for obj in export_targets:
        if obj.type != "MESH":
            continue
        has_sk = bool(obj.data.shape_keys and len(obj.data.shape_keys.key_blocks) > 1)
        other_mods = [m.name for m in obj.modifiers if m.type != "ARMATURE"]
        if has_sk and other_mods:
            blocked_meshes.append({"mesh": obj.name, "modifiers": other_mods})

    if strict_shape_key_guard and blocked_meshes:
        return {
            "ok": False,
            "error": (
                "Export aborted: one or more meshes have Shape Keys alongside unapplied non-Armature modifiers. "
                "Apply or remove those modifiers cleanly before exporting so Shape Keys remain intact."
            ),
            "blocked_meshes": blocked_meshes,
            "output_path": str(out),
        }

    # Save and replace selection cleanly
    prev_selected = list(bpy.context.selected_objects)
    prev_active = bpy.context.view_layer.objects.active

    try:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in export_targets:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = export_targets[0]

        bpy.ops.export_scene.fbx(
            filepath=str(out),
            use_selection=True,
            object_types={"ARMATURE", "MESH"},
            use_mesh_modifiers=False,
            mesh_smooth_type="FACE",
            use_tspace=True,
            apply_scale_options="FBX_SCALE_ALL",
            axis_forward="-Z",
            axis_up="Y",
            add_leaf_bones=False,
            primary_bone_axis="Y",
            secondary_bone_axis="X",
            armature_nodetype="NULL",
            bake_anim=bake_anim,
            path_mode="COPY" if embed_textures else "AUTO",
            embed_textures=embed_textures,
        )
    finally:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in prev_selected:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        if prev_active and prev_active.name in bpy.data.objects:
            bpy.context.view_layer.objects.active = prev_active

    return {
        "ok": out.exists(),
        "output_path": str(out),
        "file_size_bytes": out.stat().st_size if out.exists() else 0,
        "exported_objects": [o.name for o in export_targets],
        "embed_textures": embed_textures,
        "bake_anim": bake_anim,
    }


def _parse_cli_args() -> Dict[str, Any]:
    out_path: Optional[str] = None
    embed = False
    bake_anim = False
    if "--" in sys.argv:
        extra = sys.argv[sys.argv.index("--") + 1 :]
        i = 0
        while i < len(extra):
            if extra[i] == "--out" and i + 1 < len(extra):
                out_path = extra[i + 1]
                i += 2
            elif extra[i] == "--embed-textures":
                embed = True
                i += 1
            elif extra[i] == "--bake-anim":
                bake_anim = True
                i += 1
            else:
                i += 1
    return {"out": out_path, "embed": embed, "bake_anim": bake_anim}


if __name__ == "__main__":
    args = _parse_cli_args()
    if not args["out"]:
        raise SystemExit("Usage: blender --background file.blend --python blender_export_vrc_fbx.py -- --out path.fbx")
    report = export_vrc_fbx(args["out"], embed_textures=args["embed"], bake_anim=args["bake_anim"])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report.get("ok"):
        raise SystemExit(1)
