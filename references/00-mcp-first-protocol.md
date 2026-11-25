# 00. MCP 优先与低截图协同规范

本规范旨在最大化利用 **Blender MCP**、**Unity MCP**、**Windows MCP** 的结构化读写与代码执行能力，将高 token 消耗、低精度的盲目截屏降到最低。

---

## 1. 工具优先级矩阵

执行任何操作前，按以下优先级选择通道：

| 操作领域 | 第一优先（MCP） | 第二优先（命令行/脚本） | 最后兜底（人工/截图） |
| --- | --- | --- | --- |
| **Blender 场景查询与建模** | **Blender MCP**（读取场景树、执行 Python、修改对象/材质/骨骼/形态键） | `blender --background <file> --python <script>` | 仅在视觉审美确认时输出拼图 |
| **Unity 资产/组件/Inspector** | **Unity MCP**（读 Hierarchy、改 Prefab、挂 MA/PhysBone、执行菜单/脚本、查 Console） | 生成 `Assets/Editor/*.cs` 脚本让用户一键触发 | 仅在着色器实机光照验收时查看 |
| **系统文件/应用调度/窗口** | **Windows MCP**（窗口聚焦、非破坏性系统查询、启动 VCC/ALCOM/Blender/Unity） | PowerShell / Python 标准库操作文件 | 用户手动点选（如网页登录下载） |

> **跨 Agent 兼容提示**：不同 MCP 服务实现的方法名可能略有差异（例如 `execute_blender_code` vs `run_python`，`unity_get_hierarchy` vs `manage_gameobject`）。Agent 启动时应先**检查自己当前挂载的工具列表**，动态映射到对应工具，不要硬编码某一版 MCP 的函数名。

---

## 2. 最小化截图铁律（Low-Screenshot Discipline）

### 绝对禁止截图的场景（必须用 MCP / JSON 数据代替）
1. **查物体/骨骼/组件是否存在**：用 MCP 查 Scene Tree / Hierarchy / Component 列表。
2. **查面数、材质槽、UV、非流形、法线朝向、未绑定权重、BlendShape 名称**：运行 `scripts/blender_vrc_audit.py` 或通过 Blender MCP 执行诊断代码，直接看 JSON。
3. **查 Unity 报错、Missing Script、Missing Shader、Humanoid 骨骼映射、PhysBone 统计**：用 Unity MCP 读 Console 日志 + 运行 `scripts/unity/VrcAvatarAuditEditor.cs` 输出 JSON。
4. **验证脚本是否执行成功**：在脚本末尾打印明确的结构化 JSON 状态（`{"ok": true, ...}`），禁止靠截屏看弹窗。

### 允许且推荐截图的 4 个视觉门禁（Visual Gates）
只有涉及**人类审美与三维直观观感**、纯 JSON 无法判断时，才生成图像：
1. **门禁 V1（生模后灰模验收）**：1 张正/侧/背 3 视图拼图，确认比例、手指、轮廓无畸形。
2. **门禁 V2（贴图与眼部验收）**：1 张全身 + 1 张面部特写，确认贴图无接缝污染、眼睛有神。
3. **门禁 V3（权重/表情极端测试）**：1 张摆姿拼图（举手/下蹲/眨眼/张嘴），确认无明显穿模与面部崩坏。
4. **门禁 V4（Unity 着色器终审）**：1~2 张 Unity Game/Scene 实机光照图（含暗光环境防死黑检查）。

> **原则**：如果能在 Blender 里用 Python 一次性渲染 4 视角并拼成 1 张图，绝不连续截 4 次全屏窗口！

---

## 3. Blender MCP 实操要点

- **批量操作原子化**：将多步建模/改名/清理逻辑合并在**一次 Python 执行调用**里完成，并在末尾 `bpy.ops.wm.save_as_mainfile()` 另存新版本，避免反复来回调用 MCP。
- **永远先保护上下文模式**：执行任何修改前先确认 `bpy.context.mode == 'OBJECT'`，并在 `try ... finally` 中恢复视图状态。
- **不要直接覆写原始文件**：每次重大阶段变更前递增版本号：
  - `01_raw_import.blend`（原始导入，只读备份）
  - `02_cleaned_parts.blend`（拆件与拓扑修补）
  - `03_textured.blend`（重贴图与眼部精修）
  - `04_rigged_blendshapes.blend`（Humanoid 绑骨 + 表情形态键）

---

## 4. Unity MCP 实操要点

- **先查包环境再动手**：通过读取 `<UnityProject>/Packages/manifest.json` 和 `Packages/vpm-manifest.json` 确认已安装的具体版本：
  - `com.vrchat.avatars`（VRCSDK3）
  - `nadena.dev.modular-avatar`（Modular Avatar）
  - `jp.lilxyzw.liltoon` 或 `com.poiyomi.toon`（实时着色器）
  - `black.startcreator.gesturemanager`（Gesture Manager，可选但强烈推荐）
- **AssetDatabase 刷新纪律**：通过脚本/Windows 修改 `.fbx` 或贴图文件后，必须通过 Unity MCP 触发 `AssetDatabase.Refresh()` 再读取 Importer 属性。
- **非破坏性修改**：在 Scene 里测试或装配 Avatar 时，**优先基于 FBX 创建 Prefab Variant**，一切 MA 组件和 PhysBone 挂在 Prefab/Variant 上，不要直接修改源 FBX 的内部结构。

---

## 5. Windows MCP 实操要点

- 用于检查进程状态（Blender / Unity / VCC / ALCOM 是否已打开）、在用户授权下唤起软件（建议使用后台/不抢焦点启动方式）或定位本地导出文件夹。
- **禁止**用模拟鼠标盲点 Blender / Unity 复杂面板菜单来代替 Blender MCP / Unity MCP 的直接 API 调用（GUI 点击不仅脆弱且依赖截图，更会粗暴打断用户的正常工作）。
- 只有当某个插件功能**完全没有脚本 API**（例如极少数第三方插件的专属弹窗按钮）时，才考虑走下文的**后台无干扰通道**，绝不默认切到前台抢键鼠。

---

## 6. 零干扰后台运行规范（借鉴 `ok-wuthering-waves` / `ok-script`）

> 核心目标：**Agent 在后台干活，用户在前台照常办公/打游戏/看网页，互不干扰。**

### 6.1 绝对禁止的“扰民行为”
- ❌ 禁止为了截屏擅自调用 `SetForegroundWindow`、`Alt+Tab` 或激活目标窗口把用户的当前窗口顶掉。
- ❌ 禁止擅自移动用户的真实物理鼠标光标（如 `SetCursorPos`、`pyautogui`、`SendInput`）或抢占全局键盘焦点。
- ❌ 禁止在后台脚本运行期间弹出抢焦点的终端黑框或模态提示框。

### 6.2 无干扰视觉取图分级（从最优到兜底）
当到达必须做视觉验收的门禁（V1~V4）时，严格按以下顺序获取画面：

1. **Level 1 — 引擎内离屏渲染直出 PNG（最推荐，100% 零干扰）**
   - **Blender**：直接调用 `scripts/blender_offscreen_preview.py`（支持 `clay` 灰模与 `textured` EEVEE 模式，一键输出 `正/侧/背/面部特写` 2×2 四宫格 PNG，并在 `finally` 中自动清理全部临时相机与灯光），**窗口被完全遮挡甚至软件最小化都能稳定出图，且画质远高于截屏**。
   - **Unity**：直接调用 `scripts/unity/VrcOffscreenPreviewEditor.cs` 的 `CapturePreviewToJson(...)`（通过 `HideAndDontSave` 隐藏相机直出 GPU `RenderTexture` 2×2 四宫格 PNG，内置**暗光防死黑测试**并在 `finally` 中 100% 还原场景灯光），**完全不碰 Scene/Game 窗口焦点**。
2. **Level 2 — Windows 后台句柄抓图（借鉴 `ok-wuthering-waves`）**
   - 仅当确实需要查看某个无法离屏渲染的软件 UI（例如 VCC/ALCOM 弹窗、第三方插件面板、VRCSDK 面板）时使用。
   - 按目标窗口句柄（`HWND`）抓取后台窗口，**绝不切换前台窗口**：
     - 优先机制：**Windows Graphics Capture (WGC)** 或 Win32 **`PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)`** / **`BitBlt`**（对被其他窗口遮挡但未最小化的后台窗口可直接抓到清晰画面）。
     - 可直接调用本 Skill 自带的零依赖工具脚本 `scripts/windows_bg_capture.py`（从代码层面禁止 `SetForegroundWindow` 和鼠标操作，只读捕获指定 `HWND`）。
   - **Windows 最小化坑提示**（来自 `ok-script` 实战经验）：被**完全最小化（Iconic）**的窗口在 Windows DWM 下可能暂停帧重绘，导致 WGC/`PrintWindow` 抓出黑屏或旧帧；因此后台运行 Blender/Unity 时，应提醒用户将它们**留在桌面底层被遮挡即可，不要点最小化**。
3. **Level 3 — 前台截屏（严格禁用，除非用户明确许可）**
   - 仅在前两级均不可行时，**必须先暂停并询问用户**是否允许短暂切窗，严禁先斩后奏。

### 6.3 无干扰输入与操作分级（借鉴 `ok-script` 后台输入协议）
1. **Level 1 — 进程内 API / MCP（99% 场景的唯一正解）**
   - Blender MCP（`bpy`）、Unity MCP（Unity Editor API / `VrcAvatarAuditEditor`）、命令行脚本全部在目标进程内部执行，**天然零鼠标、零键盘、零焦点干扰**。
2. **Level 2 — 后台窗口消息投递（`PostMessage`）**
   - 仅针对极少数没有脚本 API 的 Win32 按钮/快捷键：直接向目标 `HWND` 投递 `WM_LBUTTONDOWN` / `WM_LBUTTONUP` / `WM_KEYDOWN` / `WM_KEYUP`（`PostMessage`），不移动用户物理鼠标，不激活前台窗口。
   - **验证与权限避坑（参考 `ok-script`）**：
     - `PostMessage` 返回成功**不代表目标窗口真的响应了动作**，必须结合后台抓图或 MCP 状态查询对比动作前后的真实变化（如面板状态/物体属性确实改变了），限制重试次数，避免无效死循环。
     - 若遇到 `Access Denied (Win32 Error 5)`，说明调用方进程权限低于目标进程（UIPI 限制）；**严禁绕过 UAC 或关闭安全机制**，应向用户如实报告权限差异并由用户决定如何处理。
     - 不要把“普通按钮支持后台 `PostMessage`”想当然推广到“拖拽/复杂视口操作也支持后台输入”；单一动作不支持后台输入时，只针对该动作做隔离处理，不要把全局模式切换成前台抢鼠标。
3. **Level 3 — 狭义前台回退（Narrow Foreground Fallback，最后底线）**
   - 如果某个必须执行的单步操作经确认既无 API 也无法通过后台消息触发：
     1. **必须先告知用户**该操作会短暂激活目标窗口并占用鼠标，等待用户确认空闲后再执行；
     2. 仅限该单一动作使用前台输入，结束后立即恢复按键释放状态并交还桌面控制权，绝不扩大范围。

