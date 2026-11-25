---
name: vrc-character-forge
description: End-to-end VRChat (VRC) 3D avatar production skill for AI agents. Covers quality-first model creation (Tripo/Meshy for complex avatars, Blender direct modeling for simple ones), Blender cleanup/texturing/Humanoid rigging/BlendShapes without MMD dependencies, and Unity (VCC/ALCOM) assembly with Modular Avatar (MA), lilToon/Poiyomi shaders, and VRCPhysBone. Enforces an MCP-first (Blender MCP / Unity MCP / Windows MCP), low-screenshot workflow supporting PC-first and optional PC+Quest dual builds.
---

# VRC Character Forge

一套面向任意 AI Agent（Claude Code、Codex、Antigravity、Cursor、Gemini CLI 等）的 **VRChat 3D 角色模型制作全流程 Skill**。

- **质量第一**：优先保证模型轮廓、贴图、五官神韵与动画变形质量，**PC 主线不设三角面数上限**（不做破坏外形的暴力减面）。
- **零 MMD / 零离线渲染**：完全不使用 `mmd_tools`、PMX/VMD、Houdini 离线布料或离线视频渲染管线；所有资产与物理均面向 Unity 实时渲染与 VRChat SDK3 Avatars。
- **MCP 优先、极少截图**：在 Blender、Unity、Windows 操作中优先使用 **Blender MCP / Unity MCP / Windows MCP** 进行结构化查询与脚本化修改；能用 JSON 体检数据验证的绝不靠截图猜测。
- **零干扰后台运行（不打断用户工作）**：借鉴 `ok-wuthering-waves` / `ok-script` 的后台捕获与后台消息理念，**严禁擅自切换前台窗口、抢占键盘焦点或劫持用户鼠标**；视觉验收优先用引擎离屏渲染直出 PNG，必要时仅按窗口句柄（`HWND`）后台抓取，绝不打扰用户当前正在进行的工作。
- **Modular Avatar (MA) 优先**：在 Unity 中凡是能通过 **Modular Avatar** 非破坏性装配实现的功能（换装、菜单、参数、Animator 合并、骨骼挂载、Bounds 统一），一律优先使用 MA。

---

## 0. 铁律与红线（任何阶段不得违反）

1. **原始资产只读**：Tripo/Meshy 导入的原文件、原始设定图、原始 `.blend` 永远只读；所有修改另存新版本（如 `v01_raw.blend` → `v02_clean.blend` → `v03_rig.blend`）。
2. **零干扰后台运行铁律（Non-Intrusive Background Operation）**（详见 `references/00-mcp-first-protocol.md` 第 6 节）：
   - **禁止抢焦点 / 抢鼠标 / 切前台截屏**：不得为了截屏或点按钮擅自把 Blender / Unity / VCC / ALCOM 窗口切到最前，也不得使用全局前台键鼠注入（如随意移动真实鼠标指针或 `SendInput`）打断用户当前工作。
   - **视觉取图严格分级**：① 首选 **Blender / Unity 引擎内离屏渲染直出 PNG**（直接调用 `scripts/blender_offscreen_preview.py` 或 `scripts/unity/VrcOffscreenPreviewEditor.cs`，完全无视窗口遮挡/最小化，1 张 2×2 四宫格顶 4 次截屏）；② 确需查看软件界面时，优先使用后台窗口句柄抓图（**WGC / `PrintWindow(PW_RENDERFULLCONTENT)` / `BitBlt`**，可用 `scripts/windows_bg_capture.py`），**禁止切到前台全屏截屏**。
   - **操作执行严格分级**：① 首选 **Blender MCP / Unity MCP / 命令行脚本**（纯进程内 API，零键鼠占用）；② 极少数无脚本 API 的 UI 控件，优先使用 Win32 **`PostMessage`** 向目标 `HWND` 投递后台消息；③ 若经验证必须回退到前台操作，**必须先停下来告知用户原因并征得同意**，绝不私自抢占桌面。
3. **MCP-First & 低截图纪律**（详见 `references/00-mcp-first-protocol.md`）：
   - 查询层级、面数、材质槽、骨骼、BlendShape、组件属性、报错日志时，**必须优先调用 Blender MCP / Unity MCP / Windows MCP 或运行 `scripts/` 里的结构化体检脚本**。
   - **禁止**在未做结构化体检前频繁截屏排查；仅在阶段视觉验收门禁（灰模轮廓、贴图观感、表情神态、Unity 最终实机光照）输出少量拼图/关键视角图。
4. **双生模路由纪律**：
   - **复杂模型**（写实/精致二次元人物、复杂服饰与饰品）：通过 **Tripo（网页/本地手动导入 GLB/FBX）或 Meshy** 生成，**头与身体必须整体一次生成**，禁止头身分离生成再拼接；单次任务验证合格后再迭代，禁止盲目抽卡。
   - **简单模型**（Q 版简模、硬表面道具、几何饰品、基础服装件）：**直接通过 Blender MCP 在 Blender 内建模**，不要浪费时间去外部 AI 生模再修烂拓扑。
5. **阶段门禁（Gate）**：上一阶段的结构化体检（JSON Audit）与关键视觉确认未通过前，不得进入下一阶段（尤其禁止带着坏拓扑/未拆件模型直接绑骨或导入 Unity）。
6. **MA 优先**：Unity 侧新增换装、表情开关、参数、Animator 层、网格设置统一优先走 **Modular Avatar (MA)** 组件，避免直接手动魔改基础 FX Controller 导致维护地狱。

---

## 1. 阶段路由表（按当前进度按需读取文档）

收到用户任务后，先确定处于哪个阶段，再读取对应的 `references/` 文档，**不要一次全读浪费上下文**。

| 阶段 | 核心任务 | 必读文档 / 工具 | 门禁产出 |
| --- | --- | --- | --- |
| **通用协议** | 探测可用 MCP（Blender / Unity / Windows），确立低截图工作流与文件版本管理 | `references/00-mcp-first-protocol.md`<br>`templates/avatar-checklist.json` | 确认 MCP 通道与工作目录结构 |
| **阶段 1：设定与生模** | 判定复杂/简单路线；复杂走正背对齐 T-Pose 设定图 → Tripo/Meshy 导入；简单走 Blender MCP 直建 | `references/01-concept-and-generation.md` | 原始比例/手指/轮廓合格的基础网格（`v01_raw.blend`） |
| **阶段 2：拆件与贴图** | 质量优先修模（去非流形/修法线，**不强行减面**）、拆件、分组件重贴图、眼部精修、CATS/Mesh 工具整理 | `references/02-blender-cleanup-and-texturing.md`<br>`scripts/blender_vrc_audit.py` | 拆件干净、UV/贴图高精、体检通过（`v02_tex.blend`） |
| **阶段 3：绑骨与表情** | Unity Humanoid 骨架绑定、权重动态摆姿校验、15 Visemes 口型、眨眼/眼追、手势表情（可选 ARKit 52）、标准化 FBX 导出 | `references/03-humanoid-rigging-and-blendshapes.md`<br>`scripts/blender_vrc_audit.py`<br>`scripts/blender_export_vrc_fbx.py` | 零穿模权重 + 完整 BlendShapes + 规范 `.fbx` |
| **阶段 4：Unity 与着色器** | VCC/ALCOM 项目校验、FBX 导入配置、Avatar Descriptor、lilToon / Poiyomi Toon 材质调校、防死黑与 Bounds 统一 | `references/04-unity-vcc-alcom-and-shaders.md`<br>`scripts/unity/VrcAvatarAuditEditor.cs` | 材质光照正确、Humanoid 映射全绿的 Prefab |
| **阶段 5：MA 与实时物理** | 用 Modular Avatar 完成服装/表情/开关/参数装配，配置 VRCPhysBone 与碰撞体（头发/裙摆/尾巴/饰品） | `references/05-modular-avatar-and-physbones.md` | 无冲突 MA 装配 + 稳定不穿模的 PhysBone |
| **阶段 6：双端验收与交付** | PC 主线质量终审；如需 Quest 兼容则创建独立 Android 变体（合规 Shader/减面合图），清理临时文件并交付 | `references/06-pc-quest-qa-and-delivery.md`<br>`scripts/unity/VrcAvatarAuditEditor.cs` | 零阻断报错的可上传 Avatar 与完整验收报告 |

---

## 2. 标准执行工作流（Agent 决策模板）

### 步骤 A：启动探测（先查环境，不盲干）
1. 通过可用工具探测当前会话中是否存在 **Blender MCP**、**Unity MCP**、**Windows MCP**。
2. 若缺少某个 MCP，**明确降级方案**：
   - 无 Blender MCP → 用命令行 `blender --background <file.blend> --python <script.py>` 执行无头检查与导出。
   - 无 Unity MCP → 生成/更新 Unity Editor C# 脚本（放进 `Assets/Editor/`），让用户在菜单一键执行并输出 JSON 报告。
   - 无 Windows MCP → 使用标准 shell/文件工具操作项目文件与 VCC/ALCOM 目录。
3. 复制 `templates/avatar-checklist.json` 到项目目录，记录当前角色名、平台模式（`pc_only` 或 `pc_and_quest`）、生模路线（`tripo_meshy` 或 `blender_direct`）以及版本号。

### 步骤 B：Blender 阶段闭环（先数据，后视觉）
1. 导入或新建模型后，先运行 `scripts/blender_vrc_audit.py` 输出 JSON 报告：核查尺寸身高（建议 `1.4m ~ 1.8m`）、朝向（面向 `-Y`，顶部 `+Z`）、非流形/翻转法线、材质槽、UV 通道、骨骼命名、未分配权重顶点、15 Visemes 是否齐全。
2. 修复完 JSON 报告中的阻断项（`errors`）后，再在必要节点导出少量正/侧/背拼图做视觉确认。
3. 使用 `scripts/blender_export_vrc_fbx.py` 导出符合 Unity Humanoid 与 BlendShape 规范的 FBX。

### 步骤 C：Unity 阶段闭环（MA 优先 + 脚本审计）
1. 优先用 Unity MCP 配置 FBX Importer（`Humanoid`、`Legacy Blend Shape Normals`、`Read/Write` 按需开启）、生成 Prefab、挂载 `VRC Avatar Descriptor`。
2. 材质优先使用用户项目内已安装的 **lilToon** 或 **Poiyomi Toon**；统一设置 `Anchor Override` 与合理的 `Bounds`（可通过 MA Mesh Settings 统一管理，避免镜头转角模型突然消失或光照闪烁）。
3. 换装、表情菜单、开关、Animator 合并、骨骼代理全部优先挂载 **Modular Avatar** 组件，不破坏原始 Prefab。
4. 运行 `VrcAvatarAuditEditor.cs` 生成 JSON 体检报告，逐项消除 `errors`，最后仅在 VRChat Gesture Manager / 实机预览时按需看 1~2 张关键视图确认最终观感。

---

## 3. 交付物规范

交付给用户时，始终给出结构化摘要（而非冗长过程日志）：
- **已完成阶段 & 当前版本文件路径**（`.blend`、`.fbx`、Unity Prefab 路径）。
- **结构化体检摘要**（面数、材质数、SkinnedMeshRenderer 数、PhysBone 统计、Visemes/表情完整度、是否有剩余警告）。
- **平台状态**：明确标明当前交付为 `PC Quality-First` 版本，若同时做了 `Quest` 变体则单列 Quest 指标与降级差异。
- **待人工确认项**：仅列出 AI 无法主观裁决的审美微调项（如眼位微调、物理软硬手感、表情夸张度）。
