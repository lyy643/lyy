# 04. Unity (VCC / ALCOM) 配置、FBX 导入与实时着色器指南

本阶段全部优先通过 **Unity MCP** 执行（查询包清单、修改 ModelImporter、创建 Prefab Variant、配置材质参数、触发 `VrcAvatarAuditEditor` 体检），尽量不截屏。

---

## 1. VCC / ALCOM 项目环境校验

开始操作前，先直接读取项目根目录下的 `Packages/vpm-manifest.json` 与 `Packages/manifest.json`：

- **Unity 版本**：确认匹配当前 VRChat 官方支持版本（如 `Unity 2022.3.22f1`），由 **VCC (VRChat Creator Companion)** 或 **ALCOM** 统一管理，禁止手动拖入旧版 `.unitypackage` 形式的 VRCSDK。
- **必备 VPM 包核验**：
  1. `com.vrchat.avatars`（VRCSDK3 Avatars）
  2. `nadena.dev.modular-avatar`（Modular Avatar，简称 MA）
  3. 实时着色器（至少其一）：`jp.lilxyzw.liltoon`（lilToon）或 `com.poiyomi.toon`（Poiyomi Toon）
  4. 强烈推荐：`black.startcreator.gesturemanager`（Unity 内零上传测试菜单、开关、表情与物理）
- 若缺包，提醒用户通过 **VCC / ALCOM** 添加对应 VPM 仓库并安装（不要尝试手工下载散装脚本拼凑）。

---

## 2. FBX ModelImporter 铁律（通过 Unity MCP / 脚本设置）

FBX 放入 `Assets/Avatars/<AvatarName>/Model/` 后，必须核对以下导入设置：

### Model 页签
- **Scale Factor**：`1`（若 Blender 按规范导出，模型高度应为正常米制）。
- **Import BlendShapes**：勾选 `true`。
- **Blend Shape Normals**：**必须设为 `Calculate` 或按需选 `Legacy Blend Shape Normals`（导入后无面部黑斑/硬折痕为准）**；在 Unity 2022 中，AI 生成或手修的二次元面部开启 `Legacy Blend Shape Normals`（通过勾选 ModelImporter 的 `keepQuads`/法线模式或将 Blend Shape Normals 设为 `None` / `Import`）能显著避免张嘴/眨眼时脸颊出现诡异阴影折线。
- **Read/Write Enabled**：若后续用到部分运行时 Mesh 工具或特定插件则开启；纯渲染可保持默认，但如遇到 MA Mesh 处理或某些烘培需求再按需开启。
- **Import Cameras / Import Lights**：全部关闭 `false`。

### Rig 页签
- **Animation Type**：`Humanoid`。
- **Avatar Definition**：`Create From This Model`。
- 点击/通过脚本检查 **Configure Avatar 骨骼映射**：
  - 确认所有必需骨骼绿色映射正确；
  - 重点排查 **`Chest` / `UpperChest`** 是否漏映、**`Jaw`（下巴骨）是否误映射了头发/颈部饰品骨**（非常经典的 VRC 坑：Unity 常把 `Jaw` 错绑到前刘海或领带骨，导致一说话头发乱飞——**如果角色口型靠 BlendShapes 驱动，务必将 Humanoid 的 `Jaw` 映射清空为 `None`**！）；
  - 确认 **`LeftEye` / `RightEye`** 正确映射，且 **Toe / 5 指骨骼** 无错位。

### Materials 页签
- 提取材质与贴图到独立子目录（`Materials/`、`Textures/`），保持原始 FBX 干净可读。

---

## 3. VRC Avatar Descriptor 核心配置

基于 FBX 创建 **Prefab Variant**（如 `<AvatarName>_PC.prefab`），在根节点挂载 `VRCAvatarDescriptor`：

1. **View Position（眼位标定）**：
   - 将视角小白球精确放在**双眼眉心正前方贴近鼻梁处**（通过脚本读取 `LeftEye` 与 `RightEye` 中点，Z 轴向前微偏 `0.03m ~ 0.05m`）。
   - 错误的 View Position 会导致 VR 中进游戏看到自己头骨内部或视角歪斜。
2. **LipSync（口型同步）**：
   - Mode 设为 `Viseme Blend Shape`。
   - Face Mesh 指定为主面部 `SkinnedMeshRenderer`（如 `Body`）。
   - 绑定 15 个 `vrc.v_*` BlendShape（若命名标准，VRCSDK 自动填充）。
3. **Eye Look（眼球追踪与自动眨眼）**：
   - 启用 `Eye Look`。
   - 绑定 `LeftEye`、`RightEye` 骨骼并设定安全旋转角度（例如 Looking Up `12°`、Down `15°`、Out `18°`、In `18°`，防止翻白眼或穿模）。
   - Eyelids Type 设为 `Blendshapes`，指定面部 Mesh 并绑定 `Blink`（以及可选 `Looking Up/Down` 眼皮微动）。
4. **Playable Layers**：
   - 保持基础结构整洁；**后续自定义手势表情、换装与开关统一交给 Modular Avatar 的 `MA Merge Animator` 合并**，不要把所有功能硬塞进一个难以维护的巨型手写 Controller。

---

## 4. 实时着色器配置规范（lilToon / Poiyomi Toon）

### 4.1 lilToon（二次元 VRC 首选推荐）
- **基础设置**：使用 `lilToon`（不透明部位）或 `lilToonCutout` / `lilToonTransparent`（镂空蕾丝/半透明纱裙，按需选 `Cutout` 避免半透明排序穿帮）。
- **防死黑保底（必设）**：
  - 将 **Lighting Settings → Light Min Limit（最低亮度下限）** 设为 `0.05 ~ 0.15`（防止进暗黑世界角色变成纯黑剪影）；
  - **Light Max Limit** 设为 `1.0 ~ 1.2`（防止进过曝世界角色变闪光弹）；
  - **Unlit Intensity / As Unlit** 适度微调（如 `0.05 ~ 0.15`）保证面部在复杂光线下依旧通透。
- **面部特殊处理**：
  - 面部阴影使用柔和平滑阴影（Shadow Border / Blur 调柔）或搭配面部阴影贴图（SDF / Shadow Mask），开启 **Backface Force Shadow = Off**；
  - 眼睛可叠加 **MatCap / 高光贴图** 与极轻微 **Emission**（让暗处眼睛仍有神采）。
- **描边（Outline）**：按画风按需开启 `lilToonOutline`，面部/鼻尖区域可用 Outline Width Mask 减细，避免近看像“脏胡子”。

### 4.2 Poiyomi Toon（美型/特效/发光材质极强）
- 选择 `Poiyomi Toon` 9.x+，同样配置 **Light Data → Min Brightness (`0.05 ~ 0.15`)** 与 **Max Brightness** 防死黑/防过曝。
- 利用 Poiyomi 的 **Shading (Flat / Realistic / Toon)**、**Rim Lighting**、**MatCap** 和 **AudioLink**（如需音乐律动特效）增强视觉表现。
- 完成后记得执行材质 **Lock（锁定优化）**（通常 VRCSDK / Poiyomi 会在上传时自动锁定，但调试期保持解锁）。

---

## 5. Bounds 与 Anchor Override（防隐身、防明暗割裂必做）

当角色由多个 `SkinnedMeshRenderer`（身体、头发、衣服、饰品）组成时，常见两大 Bug：
1. **转头或近距离时某件衣服/头发突然消失**（包围盒 Bounds 裁切问题）；
2. **身体和衣服在不同光源下明暗不一致、接缝处色差突变**（不同 Mesh 的光照探针采样点不同）。

**最佳解法（MA 优先）**：
- 直接在 Avatar 根节点挂载 **`MA Mesh Settings`** 组件（属于 Modular Avatar）：
  - **Inherit Probe Anchor** → 设为 `Set` 并指定 `Chest` 或 `Hips`（一键统一全部子网格的 `Anchor Override`，彻底消除全身明暗色差！）；
  - **Inherit Bounds** → 设为 `Set` 并指定统一的全局包围盒（例如基于根骨 `Center (0, 0.85, 0)`、`Extent (1.2, 1.2, 1.2)`，彻底杜绝穿模视角消失 Bug！）。

---

## 6. 阶段 4 验收门禁（Gate 4）

- [ ] 运行 `VrcAvatarAuditEditor.cs`，确认：`Humanoid` 映射有效、`Jaw` 未误绑头发、15 Visemes 与 Eye Look 绑定无缺失、无 `Hidden/InternalErrorShader` 或 Standard 漏配材质、所有 SkinnedMeshRenderer 已配置统一 `Anchor Override`（或已挂载 `MA Mesh Settings`）。
- [ ] 在 Unity Scene/Game 视图下（配合暗光 + 常规光测试）确认 **门禁 V4** 无死黑、无背面透明破洞、眼部自然。
