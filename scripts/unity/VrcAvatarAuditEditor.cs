// Place this script under Assets/Editor/VrcAvatarAuditEditor.cs in your Unity project.
// Works cleanly with or without Modular Avatar / VRCSDK3 compile defines (uses reflection for safe cross-project compatibility).
// Can be invoked via Unity MCP (calling VrcAvatarAuditEditor.AuditAvatarToJson) or via Unity top menu:
//   Tools -> VRC Character Forge -> Audit Selected Avatar (PC Quality-First)
//   Tools -> VRC Character Forge -> Audit Selected Avatar (Quest Compatibility)

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace VrcCharacterForge.Editor
{
    public static class VrcAvatarAuditEditor
    {
        private static readonly string[] QuestAllowedShaderPrefixes =
        {
            "VRChat/Mobile/",
            "Mobile/"
        };

        [MenuItem("Tools/VRC Character Forge/Audit Selected Avatar (PC Quality-First)")]
        public static void MenuAuditSelectedPC()
        {
            RunMenuAudit(questMode: false);
        }

        [MenuItem("Tools/VRC Character Forge/Audit Selected Avatar (Quest Compatibility)")]
        public static void MenuAuditSelectedQuest()
        {
            RunMenuAudit(questMode: true);
        }

        private static void RunMenuAudit(bool questMode)
        {
            GameObject selected = Selection.activeGameObject;
            if (selected == null)
            {
                Debug.LogError("[VRC Character Forge] Please select an Avatar root GameObject in the Hierarchy first.");
                return;
            }

            string json = AuditAvatarToJson(selected, questMode);
            string outDir = Path.Combine(Application.dataPath, "..", "Temp", "VrcCharacterForge");
            Directory.CreateDirectory(outDir);
            string fileName = $"{selected.name}_{(questMode ? "quest" : "pc")}_audit.json";
            string fullPath = Path.GetFullPath(Path.Combine(outDir, fileName));
            File.WriteAllText(fullPath, json, Encoding.UTF8);

            Debug.Log($"[VRC Character Forge] Audit complete -> {fullPath}\n{json}");
        }

        /// <summary>
        /// Entry point designed for Unity MCP or automated Editor tests.
        /// Returns a structured JSON audit string without requiring screenshots.
        /// </summary>
        public static string AuditAvatarToJson(GameObject avatarRoot, bool questMode = false)
        {
            var errors = new List<string>();
            var warnings = new List<string>();
            var info = new List<string>();

            if (avatarRoot == null)
            {
                return "{\"ok\":false,\"errors\":[\"avatarRoot is null\"]}";
            }

            // 1. Missing Scripts check
            int missingScripts = 0;
            foreach (Transform t in avatarRoot.GetComponentsInChildren<Transform>(true))
            {
                Component[] comps = t.gameObject.GetComponents<Component>();
                foreach (Component c in comps)
                {
                    if (c == null) missingScripts++;
                }
            }
            if (missingScripts > 0)
            {
                errors.Add($"Found {missingScripts} Missing Script component(s) in hierarchy. VRCSDK will block or fail upload.");
            }

            // 2. Animator & Humanoid check
            var animator = avatarRoot.GetComponent<Animator>();
            bool isHumanoid = false;
            bool jawMapped = false;
            if (animator == null)
            {
                errors.Add("Missing Animator component on avatar root.");
            }
            else if (animator.avatar == null)
            {
                errors.Add("Animator has no Avatar asset assigned.");
            }
            else
            {
                isHumanoid = animator.avatar.isHuman && animator.avatar.isValid;
                if (!isHumanoid)
                {
                    errors.Add($"Animator Avatar '{animator.avatar.name}' is not a valid Humanoid Avatar.");
                }
                else
                {
                    Transform jawBone = animator.GetBoneTransform(HumanBodyBones.Jaw);
                    if (jawBone != null)
                    {
                        jawMapped = true;
                        warnings.Add(
                            $"Humanoid Jaw bone is mapped to '{jawBone.name}'. If using Viseme BlendShapes, " +
                            "unmap Jaw in FBX Rig -> Configure to prevent hair/accessories moving during speech."
                        );
                    }
                    if (animator.GetBoneTransform(HumanBodyBones.LeftEye) == null ||
                        animator.GetBoneTransform(HumanBodyBones.RightEye) == null)
                    {
                        warnings.Add("LeftEye or RightEye Humanoid bone is unmapped (needed for bone-based Eye Look).");
                    }
                }
            }

            // 3. Renderers, Triangles, Materials, Shaders, Anchor Override
            var smrs = avatarRoot.GetComponentsInChildren<SkinnedMeshRenderer>(true);
            var mrs = avatarRoot.GetComponentsInChildren<MeshRenderer>(true);
            int totalTriangles = 0;
            var uniqueMaterials = new HashSet<Material>();
            var shaderNames = new HashSet<string>();
            int missingProbeAnchorCount = 0;
            int questDisallowedShaders = 0;

            void InspectMaterials(Renderer r, Material[] mats)
            {
                if (r.probeAnchor == null) missingProbeAnchorCount++;
                foreach (Material m in mats)
                {
                    if (m == null)
                    {
                        errors.Add($"Renderer '{r.name}' has a null (missing) material slot.");
                        continue;
                    }
                    uniqueMaterials.Add(m);
                    string sName = m.shader != null ? m.shader.name : "<null>";
                    shaderNames.Add(sName);

                    if (sName == "<null>" || sName.Contains("InternalErrorShader"))
                    {
                        errors.Add($"Material '{m.name}' on '{r.name}' uses broken/missing shader '{sName}'.");
                    }
                    else if (questMode)
                    {
                        bool allowed = false;
                        foreach (string prefix in QuestAllowedShaderPrefixes)
                        {
                            if (sName.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                            {
                                allowed = true;
                                break;
                            }
                        }
                        if (!allowed)
                        {
                            questDisallowedShaders++;
                            errors.Add($"[Quest] Material '{m.name}' uses non-Quest shader '{sName}'. Replace with VRChat/Mobile/Toon Lit or Standard Lite.");
                        }
                    }
                    else if (sName == "Standard")
                    {
                        warnings.Add($"Material '{m.name}' uses Unity Standard shader; consider lilToon or Poiyomi Toon for consistent VRC lighting.");
                    }
                }
            }

            foreach (var smr in smrs)
            {
                if (smr.sharedMesh != null)
                {
                    totalTriangles += smr.sharedMesh.triangles.Length / 3;
                }
                else
                {
                    errors.Add($"SkinnedMeshRenderer '{smr.name}' has a null mesh.");
                }
                InspectMaterials(smr, smr.sharedMaterials);
            }

            foreach (var mr in mrs)
            {
                var mf = mr.GetComponent<MeshFilter>();
                if (mf != null && mf.sharedMesh != null)
                {
                    totalTriangles += mf.sharedMesh.triangles.Length / 3;
                }
                InspectMaterials(mr, mr.sharedMaterials);
            }

            if (questMode && totalTriangles > 20000)
            {
                warnings.Add($"[Quest] Total triangles = {totalTriangles} (>20,000 recommended Quest budget; consider creating a dedicated decimated Quest variant).");
            }
            else if (!questMode)
            {
                info.Add($"[PC Quality-First] Total triangles = {totalTriangles} (unlimited policy active).");
            }

            // 4. Modular Avatar & VRCSDK Reflection Inspection
            var allComponents = avatarRoot.GetComponentsInChildren<Component>(true);
            int maComponentCount = 0;
            bool hasMaMeshSettings = false;
            var maTypesFound = new HashSet<string>();

            Component vrcDescriptor = null;
            int physBoneCount = 0;
            int physBoneColliderCount = 0;

            foreach (Component c in allComponents)
            {
                if (c == null) continue;
                Type t = c.GetType();
                string fullName = t.FullName ?? t.Name;

                if (fullName.Contains("ModularAvatar") || fullName.StartsWith("nadena.dev.modular_avatar"))
                {
                    maComponentCount++;
                    maTypesFound.Add(t.Name);
                    if (t.Name.Contains("MeshSettings")) hasMaMeshSettings = true;
                }
                else if (t.Name == "VRCAvatarDescriptor")
                {
                    vrcDescriptor = c;
                }
                else if (t.Name == "VRCPhysBone")
                {
                    physBoneCount++;
                }
                else if (t.Name == "VRCPhysBoneCollider")
                {
                    physBoneColliderCount++;
                }
            }

            if (missingProbeAnchorCount > 0 && !hasMaMeshSettings)
            {
                warnings.Add(
                    $"{missingProbeAnchorCount} Renderer(s) have no Anchor Override AND no MA Mesh Settings component was found. " +
                    "Add 'MA Mesh Settings' on the avatar root to unify Probe Anchor & Bounds."
                );
            }

            if (maComponentCount == 0)
            {
                info.Add("No Modular Avatar components detected yet. Prefer MA components for outfits, toggles, menus, and FX merging.");
            }

            if (questMode && physBoneCount > 8)
            {
                warnings.Add($"[Quest] Found {physBoneCount} VRCPhysBone components (>8 may drop to Very Poor or get disabled on Quest).");
            }

            // 5. VRCAvatarDescriptor detail checks via Reflection
            bool hasDescriptor = vrcDescriptor != null;
            string lipSyncMode = "Unknown";
            bool eyeLookEnabled = false;
            int syncedParamBitsEstimate = -1;

            if (!hasDescriptor)
            {
                errors.Add("Missing VRCAvatarDescriptor on avatar root.");
            }
            else
            {
                Type dt = vrcDescriptor.GetType();
                FieldInfo lipSyncField = dt.GetField("lipSync");
                if (lipSyncField != null)
                {
                    object val = lipSyncField.GetValue(vrcDescriptor);
                    lipSyncMode = val != null ? val.ToString() : "None";
                    if (lipSyncMode != "VisemeBlendShape")
                    {
                        warnings.Add($"Avatar Descriptor LipSync mode is '{lipSyncMode}' (expected 'VisemeBlendShape' for 15-viseme avatars).");
                    }
                }

                FieldInfo visemeMeshField = dt.GetField("VisemeSkinnedMesh");
                if (visemeMeshField != null && visemeMeshField.GetValue(vrcDescriptor) == null)
                {
                    warnings.Add("Avatar Descriptor VisemeSkinnedMesh is not assigned.");
                }

                FieldInfo enableEyeLookField = dt.GetField("enableEyeLook");
                if (enableEyeLookField != null)
                {
                    eyeLookEnabled = Convert.ToBoolean(enableEyeLookField.GetValue(vrcDescriptor));
                    if (!eyeLookEnabled)
                    {
                        warnings.Add("Avatar Descriptor Eye Look is disabled.");
                    }
                }

                // Estimate synced parameter cost if expressionParameters is set
                FieldInfo expParamsField = dt.GetField("expressionParameters");
                if (expParamsField != null)
                {
                    object expParams = expParamsField.GetValue(vrcDescriptor);
                    if (expParams != null)
                    {
                        MethodInfo calcCost = expParams.GetType().GetMethod("CalcTotalCost");
                        if (calcCost != null)
                        {
                            syncedParamBitsEstimate = Convert.ToInt32(calcCost.Invoke(expParams, null));
                            if (syncedParamBitsEstimate > 256)
                            {
                                errors.Add($"VRCExpressionParameters total cost is {syncedParamBitsEstimate}/256 bits (exceeds hard limit).");
                            }
                        }
                    }
                }
            }

            // Build clean JSON output without requiring external JSON packages
            var sb = new StringBuilder();
            sb.Append("{\n");
            sb.AppendFormat("  \"ok\": {0},\n", errors.Count == 0 ? "true" : "false");
            sb.AppendFormat("  \"mode\": \"{0}\",\n", questMode ? "quest" : "pc_quality_first");
            sb.AppendFormat("  \"avatar_name\": \"{0}\",\n", EscapeJson(avatarRoot.name));
            sb.Append("  \"summary\": {\n");
            sb.AppendFormat("    \"total_triangles\": {0},\n", totalTriangles);
            sb.AppendFormat("    \"skinned_mesh_renderers\": {0},\n", smrs.Length);
            sb.AppendFormat("    \"mesh_renderers\": {0},\n", mrs.Length);
            sb.AppendFormat("    \"unique_materials\": {0},\n", uniqueMaterials.Count);
            sb.AppendFormat("    \"missing_scripts\": {0},\n", missingScripts);
            sb.AppendFormat("    \"humanoid_valid\": {0},\n", isHumanoid ? "true" : "false");
            sb.AppendFormat("    \"jaw_mapped\": {0},\n", jawMapped ? "true" : "false");
            sb.AppendFormat("    \"has_vrc_descriptor\": {0},\n", hasDescriptor ? "true" : "false");
            sb.AppendFormat("    \"lip_sync_mode\": \"{0}\",\n", EscapeJson(lipSyncMode));
            sb.AppendFormat("    \"eye_look_enabled\": {0},\n", eyeLookEnabled ? "true" : "false");
            sb.AppendFormat("    \"synced_param_bits_base\": {0},\n", syncedParamBitsEstimate);
            sb.AppendFormat("    \"modular_avatar_component_count\": {0},\n", maComponentCount);
            sb.AppendFormat("    \"has_ma_mesh_settings\": {0},\n", hasMaMeshSettings ? "true" : "false");
            sb.AppendFormat("    \"physbone_count\": {0},\n", physBoneCount);
            sb.AppendFormat("    \"physbone_collider_count\": {0},\n", physBoneColliderCount);
            sb.AppendFormat("    \"quest_disallowed_shaders\": {0},\n", questDisallowedShaders);
            sb.AppendFormat("    \"error_count\": {0},\n", errors.Count);
            sb.AppendFormat("    \"warning_count\": {0}\n", warnings.Count);
            sb.Append("  },\n");
            sb.AppendFormat("  \"shaders_used\": {0},\n", ToJsonArray(shaderNames));
            sb.AppendFormat("  \"modular_avatar_types\": {0},\n", ToJsonArray(maTypesFound));
            sb.AppendFormat("  \"errors\": {0},\n", ToJsonArray(errors));
            sb.AppendFormat("  \"warnings\": {0},\n", ToJsonArray(warnings));
            sb.AppendFormat("  \"info\": {0}\n", ToJsonArray(info));
            sb.Append("}");
            return sb.ToString();
        }

        private static string EscapeJson(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "");
        }

        private static string ToJsonArray(IEnumerable<string> items)
        {
            var list = new List<string>();
            foreach (string item in items)
            {
                list.Add("\"" + EscapeJson(item) + "\"");
            }
            return "[" + string.Join(", ", list) + "]";
        }
    }
}
