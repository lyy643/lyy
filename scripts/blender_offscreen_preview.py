"""
Blender Non-Intrusive Offscreen 4-View Preview Renderer (vrc-character-forge)
-----------------------------------------------------------------------------
Renders a clean 2x2 contact sheet PNG (Front / Side / Back / Face Close-up)
purely offscreen inside Blender:
  - ZERO foreground window switching, ZERO mouse/keyboard interference
  - Works even when Blender is occluded, minimized, or running `--background`
  - Auto-frames any avatar height using world-space mesh bounds (+ Head bone if rigged)
  - Supports 'clay' (Workbench fast silhouette/topology check) and 'textured' (EEVEE)
  - 100% non-destructive: restores all scene render/camera/lighting settings & removes
    all temporary objects/datablocks in `finally`.

Usage (Blender MCP / Python Console):
    import sys, json
    sys.path.append("/path/to/vrc-character-forge/scripts")
    import blender_offscreen_preview
    res = blender_offscreen_preview.render_offscreen_preview(
        "D:/vrc/previews/v02_preview.png",
        mode="textured",
        tile_size=512,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))

Usage (Headless CLI):
    blender --background avatar.blend --python scripts/blender_offscreen_preview.py -- --out preview.png --mode clay --tile-size 512
"""

from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import bpy
    from mathutils import Vector
except ImportError as exc:
    raise SystemExit(
        "This script must be executed inside Blender (Blender MCP or `blender --background --python`)."
    ) from exc


def _resolve_eevee_engine() -> str:
    """Return the available EEVEE engine identifier across Blender 3.6 / 4.x / 5.x."""
    prop = bpy.types.RenderSettings.bl_rna.properties["engine"]
    available = {item.identifier for item in prop.enum_items}
    if "BLENDER_EEVEE_NEXT" in available:
        return "BLENDER_EEVEE_NEXT"
    if "BLENDER_EEVEE" in available:
        return "BLENDER_EEVEE"
    return "BLENDER_WORKBENCH"


def _compute_scene_mesh_bounds() -> Optional[Tuple[Vector, Vector]]:
    mesh_objs = [
        o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_viewport and o.visible_get()
    ]
    if not mesh_objs:
        return None

    min_v = Vector((float("inf"), float("inf"), float("inf")))
    max_v = Vector((float("-inf"), float("-inf"), float("-inf")))
    for obj in mesh_objs:
        for corner in obj.bound_box:
            wc = obj.matrix_world @ Vector(corner)
            min_v.x = min(min_v.x, wc.x)
            min_v.y = min(min_v.y, wc.y)
            min_v.z = min(min_v.z, wc.z)
            max_v.x = max(max_v.x, wc.x)
            max_v.y = max(max_v.y, wc.y)
            max_v.z = max(max_v.z, wc.z)
    return min_v, max_v


def _find_head_world_pos(min_v: Vector, max_v: Vector) -> Vector:
    """Locate Head bone world position if an Armature exists; fallback to top 86% of bounds."""
    center_x = (min_v.x + max_v.x) * 0.5
    center_y = (min_v.y + max_v.y) * 0.5
    height = max(0.01, max_v.z - min_v.z)

    for obj in bpy.context.scene.objects:
        if obj.type != "ARMATURE" or obj.hide_viewport or not obj.visible_get():
            continue
        for bone in obj.pose.bones:
            low = bone.name.lower().replace(" ", "").replace("-", "_")
            if low == "head" or low.endswith("_head") or low.endswith(".head"):
                head_mid = (bone.head + bone.tail) * 0.5
                return obj.matrix_world @ head_mid

    return Vector((center_x, center_y, min_v.z + height * 0.86))


def _aim_camera(cam_obj: bpy.types.Object, location: Vector, target: Vector) -> None:
    cam_obj.location = location
    direction = target - location
    rot_quat = direction.to_track_quat("-Z", "Y")
    cam_obj.rotation_euler = rot_quat.to_euler()


def _compose_2x2_grid(tile_paths: List[Path], out_path: Path, tile_size: int) -> None:
    """Compose 4 square RGBA PNGs into a 2x2 contact sheet using Blender's built-in Image API (zero external deps)."""
    grid_w = tile_size * 2
    grid_h = tile_size * 2

    loaded_imgs = []
    grid_img = None
    try:
        # Blender image pixels are stored bottom-to-top (y=0 is bottom row)
        # Layout:
        #   Top-Left  (tile 0: Front)  | Top-Right    (tile 1: Side)
        #   Bot-Left  (tile 2: Back)   | Bot-Right    (tile 3: Face)
        grid_pixels = [0.12, 0.12, 0.14, 1.0] * (grid_w * grid_h)
        offsets = [
            (0, tile_size),          # tile 0 -> Top-Left
            (tile_size, tile_size),  # tile 1 -> Top-Right
            (0, 0),                  # tile 2 -> Bottom-Left
            (tile_size, 0),          # tile 3 -> Bottom-Right
        ]

        for idx, tpath in enumerate(tile_paths):
            img = bpy.data.images.load(str(tpath), check_existing=False)
            loaded_imgs.append(img)
            if img.size[0] != tile_size or img.size[1] != tile_size:
                img.scale(tile_size, tile_size)
            src = list(img.pixels[:])
            ox, oy = offsets[idx]
            row_floats = tile_size * 4
            grid_row_floats = grid_w * 4
            for y in range(tile_size):
                src_start = y * row_floats
                dst_start = (oy + y) * grid_row_floats + ox * 4
                grid_pixels[dst_start : dst_start + row_floats] = src[src_start : src_start + row_floats]

        grid_img = bpy.data.images.new(
            name="_vrc_preview_grid_tmp",
            width=grid_w,
            height=grid_h,
            alpha=True,
        )
        grid_img.pixels[:] = grid_pixels
        out_path.parent.mkdir(parents=True, exist_ok=True)
        grid_img.filepath_raw = str(out_path)
        grid_img.file_format = "PNG"
        grid_img.save()
    finally:
        for img in loaded_imgs:
            try:
                bpy.data.images.remove(img)
            except Exception:
                pass
        if grid_img is not None:
            try:
                bpy.data.images.remove(grid_img)
            except Exception:
                pass


def render_offscreen_preview(
    output_path: str,
    mode: str = "textured",
    tile_size: int = 512,
    save_individual: bool = False,
) -> Dict[str, Any]:
    """
    Render a 2x2 offscreen preview PNG without touching UI focus or mouse input.
    mode: 'clay' (Workbench gray matcap/studio) or 'textured' (EEVEE with neutral studio fill).
    """
    bounds = _compute_scene_mesh_bounds()
    if bounds is None:
        return {"ok": False, "error": "No visible MESH objects found to render."}

    min_v, max_v = bounds
    center = (min_v + max_v) * 0.5
    size = max_v - min_v
    height = max(0.05, size.z)
    max_span = max(height, size.x, size.y)
    head_pos = _find_head_world_pos(min_v, max_v)

    scene = bpy.context.scene
    render = scene.render

    # Backup original scene render settings
    backup = {
        "camera": scene.camera,
        "engine": render.engine,
        "res_x": render.resolution_x,
        "res_y": render.resolution_y,
        "res_pct": render.resolution_percentage,
        "filepath": render.filepath,
        "file_format": render.image_settings.file_format,
        "color_mode": render.image_settings.color_mode,
        "film_transparent": render.film_transparent,
        "wb_light": getattr(scene.display.shading, "light", None),
        "wb_color_type": getattr(scene.display.shading, "color_type", None),
    }

    temp_objects: List[bpy.types.Object] = []
    temp_datablocks: List[Any] = []
    out_file = Path(output_path).resolve()

    try:
        # Configure fast offscreen engine
        if mode == "clay":
            render.engine = "BLENDER_WORKBENCH"
            if hasattr(scene.display.shading, "light"):
                scene.display.shading.light = "STUDIO"
            if hasattr(scene.display.shading, "color_type"):
                scene.display.shading.color_type = "SINGLE"
        else:
            render.engine = _resolve_eevee_engine()

        render.resolution_x = tile_size
        render.resolution_y = tile_size
        render.resolution_percentage = 100
        render.image_settings.file_format = "PNG"
        render.image_settings.color_mode = "RGBA"
        render.film_transparent = False

        # Create temporary camera (50mm lens for natural character proportions)
        cam_data = bpy.data.cameras.new("_vrc_offscreen_cam_data")
        cam_data.lens = 50.0
        cam_data.clip_start = 0.01
        cam_data.clip_end = 1000.0
        cam_obj = bpy.data.objects.new("_vrc_offscreen_cam", cam_data)
        scene.collection.objects.link(cam_obj)
        scene.camera = cam_obj
        temp_objects.append(cam_obj)
        temp_datablocks.append(cam_data)

        # Add gentle neutral studio fill lights only if scene has no visible lights
        existing_lights = [
            o for o in scene.objects if o.type == "LIGHT" and not o.hide_render and not o.hide_viewport
        ]
        if mode != "clay" and not existing_lights:
            light_specs = [
                ("key", Vector((max_span * 1.2, -max_span * 1.8, center.z + height * 0.6)), 3.0),
                ("fill", Vector((-max_span * 1.4, -max_span * 1.2, center.z + height * 0.2)), 1.5),
                ("rim", Vector((0.0, max_span * 1.8, center.z + height * 0.7)), 2.2),
            ]
            for name, loc, energy in light_specs:
                ldata = bpy.data.lights.new(f"_vrc_tmp_light_{name}", type="SUN")
                ldata.energy = energy
                lobj = bpy.data.objects.new(f"_vrc_tmp_light_{name}", ldata)
                scene.collection.objects.link(lobj)
                _aim_camera(lobj, loc, center)
                temp_objects.append(lobj)
                temp_datablocks.append(ldata)

        # Compute framing distances (50mm lens, 36mm sensor -> half FOV ~ 19.8 deg)
        fov_rad = 2.0 * math.atan(cam_data.sensor_width / (2.0 * cam_data.lens))
        full_dist = (max_span * 0.62) / math.tan(fov_rad * 0.5)
        face_dist = (height * 0.17) / math.tan(fov_rad * 0.5)

        # Blender VRC convention: character faces -Y, up +Z
        views = [
            ("front", Vector((center.x, center.y - full_dist, center.z)), center),
            ("side", Vector((center.x + full_dist, center.y, center.z)), center),
            ("back", Vector((center.x, center.y + full_dist, center.z)), center),
            ("face", Vector((head_pos.x, head_pos.y - face_dist, head_pos.z)), head_pos),
        ]

        with tempfile.TemporaryDirectory(prefix="vrc_offscreen_") as tmpdir:
            tile_paths: List[Path] = []
            saved_individuals: List[str] = []

            for label, loc, tgt in views:
                _aim_camera(cam_obj, loc, tgt)
                if save_individual:
                    tpath = out_file.parent / f"{out_file.stem}_{label}.png"
                    saved_individuals.append(str(tpath))
                else:
                    tpath = Path(tmpdir) / f"{label}.png"
                tpath.parent.mkdir(parents=True, exist_ok=True)
                render.filepath = str(tpath)
                bpy.ops.render.render(write_still=True)
                tile_paths.append(tpath)

            _compose_2x2_grid(tile_paths, out_file, tile_size)

        return {
            "ok": out_file.exists(),
            "mode": mode,
            "engine_used": render.engine,
            "focus_changed": False,
            "output_path": str(out_file),
            "grid_resolution": [tile_size * 2, tile_size * 2],
            "layout": ["top_left:front", "top_right:side", "bottom_left:back", "bottom_right:face"],
            "individual_files": saved_individuals,
        }
    finally:
        # Clean up all temporary objects and datablocks
        for obj in temp_objects:
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
            except Exception:
                pass
        for db in temp_datablocks:
            try:
                if isinstance(db, bpy.types.Camera):
                    bpy.data.cameras.remove(db)
                elif isinstance(db, bpy.types.Light):
                    bpy.data.lights.remove(db)
            except Exception:
                pass

        # Restore original scene settings
        scene.camera = backup["camera"]
        render.engine = backup["engine"]
        render.resolution_x = backup["res_x"]
        render.resolution_y = backup["res_y"]
        render.resolution_percentage = backup["res_pct"]
        render.filepath = backup["filepath"]
        render.image_settings.file_format = backup["file_format"]
        render.image_settings.color_mode = backup["color_mode"]
        render.film_transparent = backup["film_transparent"]
        if backup["wb_light"] is not None and hasattr(scene.display.shading, "light"):
            scene.display.shading.light = backup["wb_light"]
        if backup["wb_color_type"] is not None and hasattr(scene.display.shading, "color_type"):
            scene.display.shading.color_type = backup["wb_color_type"]


def _parse_cli_args() -> Dict[str, Any]:
    out_path: Optional[str] = None
    mode = "textured"
    tile_size = 512
    save_individual = False
    if "--" in sys.argv:
        extra = sys.argv[sys.argv.index("--") + 1 :]
        i = 0
        while i < len(extra):
            if extra[i] == "--out" and i + 1 < len(extra):
                out_path = extra[i + 1]
                i += 2
            elif extra[i] == "--mode" and i + 1 < len(extra):
                mode = extra[i + 1]
                i += 2
            elif extra[i] == "--tile-size" and i + 1 < len(extra):
                tile_size = int(extra[i + 1])
                i += 2
            elif extra[i] == "--save-individual":
                save_individual = True
                i += 1
            else:
                i += 1
    return {
        "out": out_path,
        "mode": mode,
        "tile_size": tile_size,
        "save_individual": save_individual,
    }


if __name__ == "__main__":
    args = _parse_cli_args()
    if not args["out"]:
        raise SystemExit(
            "Usage: blender --background file.blend --python blender_offscreen_preview.py -- --out preview.png [--mode clay|textured] [--tile-size 512]"
        )
    res = render_offscreen_preview(
        args["out"],
        mode=args["mode"],
        tile_size=args["tile_size"],
        save_individual=args["save_individual"],
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if not res.get("ok"):
        raise SystemExit(1)
