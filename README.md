# VRC Character Forge

一套面向任意 AI Agent 的 **VRChat (VRC) 3D 角色模型制作 Skill**，参考 `cxp-character-forge` 的分阶段工程验收理念重构，彻底移除 MMD 与 Houdini 离线渲染管线，全面转向 **Unity (VCC / ALCOM) + VRCSDK3 + Modular Avatar (MA) + 实时着色器 + MCP 优先自动化工作流**。

## 核心特性

- **跨 Agent 通用**：遵循标准 `SKILL.md` + `references/` + `scripts/` 规范，可直接用于 Claude Code、Codex、Antigravity、Cursor、Gemini CLI 等任意支持 Skills 的 Agent。
- **质量最优先**：PC 主线不设三角面数上限，不做破坏造型的暴力减面；需要双端兼容时单独构建 Quest 轻量化变体。
- **双生模策略**：复杂角色走 Tripo / Meshy（网页或本地手动导入 GLB/FBX，整体一次生成），简单模型/硬表面配件直接用 Blender MCP 建模。
- **零 MMD 依赖**：不依赖 `mmd_tools`、PMX、VMD，原生对接 Blender（CATS / Mesh 工具）与 Unity Humanoid。
- **MCP 优先 & 低截图**：优先用 **Blender MCP**、**Unity MCP**、**Windows MCP** 与 JSON 体检脚本获取精确状态，大幅减少无效截屏与 token 消耗。
- **零干扰后台运行**：借鉴 `ok-wuthering-waves` / `ok-script` 的后台捕获与后台输入理念——严禁切窗抢焦点、严禁劫持鼠标键盘；视觉验收优先走引擎离屏渲染，必要时按窗口句柄（`HWND`）后台抓取，绝不打断用户当前工作。
- **Modular Avatar (MA) 优先**：Unity 装配、换装、菜单、参数、Animator 合并与 Bounds 统一全部优先使用 MA 非破坏性工作流。

---

## 目录结构

```text
vrc-character-forge/
├── SKILL.md                                  # Agent 入口：核心铁律、阶段路由表与门禁规则
├── README.md                                 # 安装与使用说明
├── references/
│   ├── 00-mcp-first-protocol.md              # Blender / Unity / Windows MCP 协同与低截图规范
│   ├── 01-concept-and-generation.md          # 复杂模型(Tripo/Meshy) vs 简单模型(Blender直建)路由
│   ├── 02-blender-cleanup-and-texturing.md   # 质量优先拆件修模、分组件重贴图、眼部精修、CATS/Mesh 工具
│   ├── 03-humanoid-rigging-and-blendshapes.md# Humanoid 骨骼、权重动态校验、15 Visemes、表情与 FBX 导出
│   ├── 04-unity-vcc-alcom-and-shaders.md     # VCC/ALCOM 项目配置、FBX 导入、lilToon/Poiyomi、Bounds/Anchor
│   ├── 05-modular-avatar-and-physbones.md    # Modular Avatar 非破坏性装配 + VRCPhysBone 实时物理
│   └── 06-pc-quest-qa-and-delivery.md        # PC 主线验收 + Quest 双端适配分支 + 上传交付清单
├── scripts/
│   ├── blender_vrc_audit.py                  # Blender 结构化 JSON 体检脚本（可由 MCP 或 CLI 调用）
│   ├── blender_offscreen_preview.py          # Blender 零干扰离屏 4 视图(正/侧/背/脸)四宫格渲染脚本
│   ├── blender_export_vrc_fbx.py             # Blender 标准化 VRC FBX 导出脚本
│   ├── windows_bg_capture.py                 # Windows 零干扰后台句柄抓图工具（PrintWindow，不切窗不抢焦点）
│   └── unity/
│       ├── VrcAvatarAuditEditor.cs           # Unity Editor 结构化 JSON 体检工具（放入 Assets/Editor/）
│       └── VrcOffscreenPreviewEditor.cs      # Unity 零干扰离屏 2×2 预览 + 暗光防死黑检测工具（放入 Assets/Editor/）
└── templates/
    └── avatar-checklist.json                 # 角色制作阶段追踪与资产版本清单模板
```

---

## 在不同 Agent 中安装使用

只需将整个 `vrc-character-forge/` 文件夹放到对应 Agent 的 skills 目录即可：

| Agent 平台 | 推荐放置路径 |
| --- | --- |
| **Antigravity** | `~/.gemini/config/skills/vrc-character-forge/`（或 `<工作区>/.agents/skills/vrc-character-forge/`） |
| **dsh (DeepSeek Harness)** | `~/.dsh/skills/vrc-character-forge/`（或 `~/.agents/skills/vrc-character-forge/`） |
| **Codex** | `~/.codex/skills/vrc-character-forge/` |
| **Claude Code** | `~/.claude/skills/vrc-character-forge/` 或 `<项目>/.claude/skills/vrc-character-forge/` |
| **Cursor** | `<项目>/.cursor/skills/vrc-character-forge/`（或将 `SKILL.md` 作为规则引用） |
| **Gemini CLI** | `~/.gemini/skills/vrc-character-forge/` |

### 快速开始示例提示词

- 复杂角色：`使用 vrc-character-forge，帮我把我刚从 Tripo 导出的角色 GLB（路径：D:/vrc/raw/catgirl.glb）处理成 PC+Quest 双端可用的 VRChat 模型，用 lilToon 和 Modular Avatar。`
- 简单模型：`使用 vrc-character-forge，直接在 Blender 里通过 Blender MCP 帮我建一个 Q 版浮空机器人挂件，并做成带 MA 开关的 VRC 资产。`
- 已有项目体检：`使用 vrc-character-forge，优先用 Blender MCP / Unity MCP 对我当前打开的模型跑一遍结构化体检，不要乱截图，只输出问题清单和修复方案。`

---

## 推荐搭配环境

- **建模端**：Blender 3.6 LTS / 4.x（建议配 CATS Blender Plugin 社区维护版 + 常规 Mesh/UV 工具；无需 `mmd_tools`）
- **引擎端**：Unity 2022.3.22f1（VRChat 当前官方支持版本，通过 **VCC** 或 **ALCOM** 管理）
- **Unity 必备包**（通过 VCC / ALCOM 安装）：
  - VRChat SDK - Avatars (3.x)
  - Modular Avatar (nadena.dev)
  - lilToon 或 Poiyomi Toon
  - Gesture Manager（强烈推荐，用于 Unity 内无上传测试菜单与表情）
- **推荐 MCP 服务**（有则自动优先使用，缺省自动回退 CLI / 脚本）：
  - Blender MCP
  - Unity MCP
  - Windows MCP
