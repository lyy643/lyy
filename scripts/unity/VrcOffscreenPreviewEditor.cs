// Place this script under Assets/Editor/VrcOffscreenPreviewEditor.cs in your Unity project.
// Renders a clean 2x2 offscreen PNG preview of a VRChat Avatar using a temporary hidden Camera
// and RenderTexture — ZERO window focus stealing, ZERO mouse/keyboard interference.
//
// Layout (2x2 contact sheet):
//   Top-Left:     Front Full Body (Normal Lighting)
//   Top-Right:    Back Full Body  (Normal Lighting)
//   Bottom-Left:  Face Close-Up   (Normal Lighting)
//   Bottom-Right: Dark-World Anti-Blackout Check (or Side View if includeDarkCheck = false)
//
// Usage via Unity MCP:
//   VrcOffscreenPreviewEditor.CapturePreviewToJson(avatarGameObject, null, 512, true);
// Usage via Unity Menu:
//   Tools -> VRC Character Forge -> Offscreen Preview (Normal + Dark Check)

using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace VrcCharacterForge.Editor
{
    public static class VrcOffscreenPreviewEditor
    {
        [MenuItem("Tools/VRC Character Forge/Offscreen Preview (Normal + Dark Check)")]
        public static void MenuCaptureSelectedWithDarkCheck()
        {
            RunMenuCapture(includeDarkCheck: true);
        }

        [MenuItem("Tools/VRC Character Forge/Offscreen Preview (4-Angle Normal)")]
        public static void MenuCaptureSelected4Angle()
        {
            RunMenuCapture(includeDarkCheck: false);
        }

        private static void RunMenuCapture(bool includeDarkCheck)
        {
            GameObject selected = Selection.activeGameObject;
            if (selected == null)
            {
                Debug.LogError("[VRC Character Forge] Please select an Avatar root GameObject first.");
                return;
            }
            string json = CapturePreviewToJson(selected, null, 512, includeDarkCheck);
            Debug.Log($"[VRC Character Forge] Offscreen Preview Result:\n{json}");
        }

        /// <summary>
        /// Entry point designed for Unity MCP. Captures a 2x2 offscreen PNG without stealing focus.
        /// </summary>
        public static string CapturePreviewToJson(
            GameObject avatarRoot,
            string outputPngPath = null,
            int tileSize = 512,
            bool includeDarkCheck = true)
        {
            if (avatarRoot == null)
            {
                return "{\"ok\":false,\"error\":\"avatarRoot is null\"}";
            }

            tileSize = Mathf.Clamp(tileSize, 128, 2048);

            if (string.IsNullOrEmpty(outputPngPath))
            {
                string outDir = Path.Combine(Application.dataPath, "..", "Temp", "VrcCharacterForge");
                Directory.CreateDirectory(outDir);
                string suffix = includeDarkCheck ? "preview_darkcheck.png" : "preview_4view.png";
                outputPngPath = Path.GetFullPath(Path.Combine(outDir, $"{avatarRoot.name}_{suffix}"));
            }
            else
            {
                outputPngPath = Path.GetFullPath(outputPngPath);
                string parent = Path.GetDirectoryName(outputPngPath);
                if (!string.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);
            }

            if (!TryComputeAvatarBounds(avatarRoot, out Bounds bounds))
            {
                return "{\"ok\":false,\"error\":\"No MeshRenderer or SkinnedMeshRenderer found on avatarRoot.\"}";
            }

            Vector3 center = bounds.center;
            float height = Mathf.Max(0.1f, bounds.size.y);
            float maxSpan = Mathf.Max(height, bounds.size.x, bounds.size.z);
            Vector3 headPos = FindHeadWorldPosition(avatarRoot, bounds);

            // Use avatar local forward/right so rotated avatars in Scene still frame accurately
            Vector3 fwd = avatarRoot.transform.forward;
            if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.forward;
            fwd.Normalize();
            Vector3 right = Vector3.Cross(Vector3.up, fwd).normalized;
            if (right.sqrMagnitude < 1e-4f) right = Vector3.right;

            // Create hidden temporary Camera (never saved to Scene, never dirties Prefab)
            GameObject camGo = new GameObject("_VRC_OffscreenPreviewCam")
            {
                hideFlags = HideFlags.HideAndDontSave
            };
            Camera cam = camGo.AddComponent<Camera>();
            cam.enabled = false;
            cam.fieldOfView = 35f;
            cam.nearClipPlane = 0.02f;
            cam.farClipPlane = 200f;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.16f, 0.17f, 0.20f, 1f);

            float halfFovRad = cam.fieldOfView * 0.5f * Mathf.Deg2Rad;
            float fullDist = (maxSpan * 0.62f) / Mathf.Tan(halfFovRad);
            float faceDist = (height * 0.16f) / Mathf.Tan(halfFovRad);

            RenderTexture rt = new RenderTexture(tileSize, tileSize, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            rt.antiAliasing = 4;
            rt.Create();

            Texture2D tileFront = null;
            Texture2D tileBack = null;
            Texture2D tileFace = null;
            Texture2D tileFourth = null;
            Texture2D gridTex = null;

            // Backup scene lights & ambient for optional dark-world blackout test
            var lightBackup = new List<(Light light, float intensity, bool enabled)>();
            float origAmbientIntensity = RenderSettings.ambientIntensity;
            Color origAmbientLight = RenderSettings.ambientLight;
            Color origAmbientSky = RenderSettings.ambientSkyColor;
            Color origAmbientEquator = RenderSettings.ambientEquatorColor;
            Color origAmbientGround = RenderSettings.ambientGroundColor;

            try
            {
                cam.targetTexture = rt;

                // 1. Front Full Body (Normal)
                tileFront = RenderTile(cam, rt, center + fwd * fullDist, center, tileSize);

                // 2. Back Full Body (Normal)
                tileBack = RenderTile(cam, rt, center - fwd * fullDist, center, tileSize);

                // 3. Face Close-Up (Normal)
                tileFace = RenderTile(cam, rt, headPos + fwd * faceDist, headPos, tileSize);

                // 4. Dark-World Check OR Side Full Body
                if (includeDarkCheck)
                {
                    Light[] allLights = UnityEngine.Object.FindObjectsOfType<Light>();
                    foreach (Light l in allLights)
                    {
                        lightBackup.Add((l, l.intensity, l.enabled));
                        l.intensity = l.intensity * 0.05f;
                    }
                    RenderSettings.ambientIntensity = 0.05f;
                    RenderSettings.ambientLight = new Color(0.03f, 0.03f, 0.04f, 1f);
                    RenderSettings.ambientSkyColor = new Color(0.03f, 0.03f, 0.04f, 1f);
                    RenderSettings.ambientEquatorColor = new Color(0.02f, 0.02f, 0.03f, 1f);
                    RenderSettings.ambientGroundColor = new Color(0.01f, 0.01f, 0.02f, 1f);
                    cam.backgroundColor = new Color(0.04f, 0.04f, 0.05f, 1f);

                    tileFourth = RenderTile(cam, rt, center + fwd * fullDist, center, tileSize);
                }
                else
                {
                    tileFourth = RenderTile(cam, rt, center + right * fullDist, center, tileSize);
                }

                // Compose 2x2 grid (Unity Texture2D y=0 is bottom row)
                gridTex = new Texture2D(tileSize * 2, tileSize * 2, TextureFormat.RGB24, false);
                gridTex.SetPixels(0, tileSize, tileSize, tileSize, tileFront.GetPixels());          // Top-Left
                gridTex.SetPixels(tileSize, tileSize, tileSize, tileSize, tileBack.GetPixels());    // Top-Right
                gridTex.SetPixels(0, 0, tileSize, tileSize, tileFace.GetPixels());                  // Bottom-Left
                gridTex.SetPixels(tileSize, 0, tileSize, tileSize, tileFourth.GetPixels());         // Bottom-Right
                gridTex.Apply();

                byte[] pngBytes = gridTex.EncodeToPNG();
                File.WriteAllBytes(outputPngPath, pngBytes);

                string fourthLabel = includeDarkCheck ? "bottom_right:front_dark_check" : "bottom_right:side";
                string escapedPath = outputPngPath.Replace("\\", "\\\\").Replace("\"", "\\\"");
                return "{"
                    + "\"ok\":true,"
                    + "\"focus_changed\":false,"
                    + $"\"avatar_name\":\"{avatarRoot.name.Replace("\"", "\\\"")}\","
                    + $"\"output_path\":\"{escapedPath}\","
                    + $"\"grid_resolution\":[{tileSize * 2},{tileSize * 2}],"
                    + $"\"include_dark_check\":{(includeDarkCheck ? "true" : "false")},"
                    + $"\"layout\":[\"top_left:front\",\"top_right:back\",\"bottom_left:face\",\"{fourthLabel}\"]"
                    + "}";
            }
            finally
            {
                // Always restore scene lights & ambient settings
                foreach (var entry in lightBackup)
                {
                    if (entry.light != null)
                    {
                        entry.light.intensity = entry.intensity;
                        entry.light.enabled = entry.enabled;
                    }
                }
                RenderSettings.ambientIntensity = origAmbientIntensity;
                RenderSettings.ambientLight = origAmbientLight;
                RenderSettings.ambientSkyColor = origAmbientSky;
                RenderSettings.ambientEquatorColor = origAmbientEquator;
                RenderSettings.ambientGroundColor = origAmbientGround;

                cam.targetTexture = null;
                RenderTexture.active = null;
                rt.Release();
                UnityEngine.Object.DestroyImmediate(rt);
                UnityEngine.Object.DestroyImmediate(camGo);
                if (tileFront != null) UnityEngine.Object.DestroyImmediate(tileFront);
                if (tileBack != null) UnityEngine.Object.DestroyImmediate(tileBack);
                if (tileFace != null) UnityEngine.Object.DestroyImmediate(tileFace);
                if (tileFourth != null) UnityEngine.Object.DestroyImmediate(tileFourth);
                if (gridTex != null) UnityEngine.Object.DestroyImmediate(gridTex);
            }
        }

        private static Texture2D RenderTile(Camera cam, RenderTexture rt, Vector3 camPos, Vector3 lookTarget, int size)
        {
            cam.transform.position = camPos;
            cam.transform.LookAt(lookTarget, Vector3.up);
            cam.Render();

            RenderTexture prev = RenderTexture.active;
            RenderTexture.active = rt;
            Texture2D tex = new Texture2D(size, size, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, size, size), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            return tex;
        }

        private static bool TryComputeAvatarBounds(GameObject root, out Bounds combined)
        {
            Renderer[] renderers = root.GetComponentsInChildren<Renderer>(false);
            combined = new Bounds();
            bool hasAny = false;
            foreach (Renderer r in renderers)
            {
                if (!(r is SkinnedMeshRenderer) && !(r is MeshRenderer)) continue;
                if (!hasAny)
                {
                    combined = r.bounds;
                    hasAny = true;
                }
                else
                {
                    combined.Encapsulate(r.bounds);
                }
            }
            return hasAny;
        }

        private static Vector3 FindHeadWorldPosition(GameObject root, Bounds bounds)
        {
            Animator anim = root.GetComponent<Animator>();
            if (anim != null && anim.avatar != null && anim.avatar.isHuman)
            {
                Transform lEye = anim.GetBoneTransform(HumanBodyBones.LeftEye);
                Transform rEye = anim.GetBoneTransform(HumanBodyBones.RightEye);
                if (lEye != null && rEye != null)
                {
                    return (lEye.position + rEye.position) * 0.5f;
                }
                Transform head = anim.GetBoneTransform(HumanBodyBones.Head);
                if (head != null)
                {
                    return head.position + Vector3.up * (bounds.size.y * 0.04f);
                }
            }
            return new Vector3(bounds.center.x, bounds.min.y + bounds.size.y * 0.86f, bounds.center.z);
        }
    }
}
