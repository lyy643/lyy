# 06. PC 质量优先终审、Quest 双端适配与交付清单

本阶段处理两个核心问题：
1. **PC 主线终审**：贯彻“**质量最优先、三角面不限**”，只拦截真正影响体验与上传的阻断性错误（不为了凑 Good 评级毁坏模型质量）。
2. **PC + Quest 双端兼容分支（按需开启）**：当用户需要 Quest/Android 独立端玩家也能看到角色时，如何在**不破坏 PC 高质量版本**的前提下构建合规的 Quest 变体。

---

## 1. PC 主线（Quality-First）终审清单

通过 Unity MCP 运行 `scripts/unity/VrcAvatarAuditEditor.cs`（Mode = `PC`），逐项确认：

### 阻断项（Errors —— 必须 100% 清零）
- [ ] `VRCAvatarDescriptor` 存在且无空引用。
- [ ] Animator 绑定的 Avatar 为有效 `Humanoid`，无骨骼缺失报错，且 `Jaw` 未误绑头发/饰品骨。
- [ ] 无 `Missing Script`（任意子节点存在丢失脚本都会导致 VRCSDK 拒绝上传或运行异常）。
- [ ] 无 `Hidden/InternalErrorShader` 或粉色丢失材质。
- [ ] 未超出 VRCSDK 硬性上传限制（例如 Expression Parameters 同步总 Bit 数 `<= 256 bits`）。
- [ ] 所有 MA 组件在虚拟构建（NDMF / Modular Avatar Build）时零报错。

### 质量项（强烈建议满足，不以牺牲画质为代价）
- [ ] **三角面数**：PC 主线**不设硬性上限**（哪怕 100k+ 甚至 200k+，只要外观精致、无废面即可保留）；但仍应通过审计记录精确面数，方便用户知情。
- [ ] **材质与贴图**：贴图清晰无模糊、无未压缩导致的巨型包体异常（单张贴图在 Unity Import Settings 建议开启合适压缩如 `BC7` / `DXT5` + `Mip Maps` + `Crunch` 谨慎使用以免毁画质）。
- [ ] **光照与防隐身**：全身 `Anchor Override` 与 `Bounds` 已通过 `MA Mesh Settings` 统一。
- [ ] **物理稳定性**：PhysBone 无鬼畜抖动、碰撞体精准、支持手部交互。
- [ ] **蓝图 ID 管理**：确认 `Pipeline Manager` 状态（新建上传留空自动生成，更新旧模型则保留对应 `Blueprint ID`）。

---

## 2. PC + Quest 双端兼容分支（仅在需要双端时执行）

VRChat 的 **Quest (Android)** 平台有极其严格的引擎硬性限制（不合规的 Shader 或组件会被强制屏蔽或拒绝上传）。

**核心原则：永远不要直接在 PC Prefab 上降级！** 必须复制出独立的 **`<AvatarName>_Quest.prefab`**（或使用专门的 Quest 转换分支），共享同一个 `Blueprint ID` 分别在 PC 与 Android 平台上传。

### Quest 端硬性兼容红线（必须全部满足才能上传）
1. **Shader 必须替换为 VRChat Mobile 官方内置着色器**：
   - Quest **不支持** `lilToon`、`Poiyomi Toon` 或任何自定义 Shader（上传时 VRCSDK 会直接报错拦截！）。
   - 必须全部切换为 **`VRChat/Mobile/Toon Lit`**（最适合二次元）、`VRChat/Mobile/MatCap Lit`（金属/眼睛反光）或 `VRChat/Mobile/Standard Lite`。
   - **注意透明限制**：`VRChat/Mobile/*` 不支持半透明（Transparent）与常规 Cutout 镂空！头发边缘/蕾丝若依赖透明贴图，在 Quest 版上需要改为实心几何或重新整理边缘。
2. **面数与组件轻量化（仅针对 Quest 变体）**：
   - 建议将 Quest 变体三角面控制在合理范围（理想 `< 20,000` Tris，硬性需注意移动 GPU 承受力与 VRChat 兜底回退阈值），可通过独立导出的减面 FBX 或非破坏性减面工具生成，**绝不影响 PC 原版**。
   - **合并网格与图集（Atlas）**：Quest 端强烈建议将材质槽压到 `1 ~ 4` 个、SkinnedMeshRenderer 压到 `1 ~ 2` 个。
   - **精简 PhysBone**：Quest 上 PhysBone 限制极严（Good/Medium 要求极少组件与骨骼数，且 **最多 8 个 PhysBone 组件 / 64 个 Affected Transforms** 否则直接 Very Poor 甚至被安全设置屏蔽），Quest 变体通常仅保留头发核心主链与尾巴/耳朵，或直接移除次要碎发与多层裙物理。
   - **包体上限**：Quest 端压缩后包体限制极严（务必保持贴图最大尺寸 `512px ~ 1024px` + `ASTC` 压缩，避免超过 VRChat Android 包体硬上限）。
3. **跨平台参数同步一致性**：
   - PC 版与 Quest 版的 `VRCExpressionParameters` 参数名称与类型必须一致（尤其换装开关和表情参数），否则 PC 玩家切了换装，Quest 玩家看到的同步状态会错乱。

---

## 3. 最终上传与交付清单

在宣布任务完成前，按以下格式向用户输出简洁明了的交付摘要：

1. **资产索引**：
   - 原始只读文件位置
   - Blender 最终定稿 `.blend` 与导出 `.fbx` 路径
   - Unity PC Prefab 路径（以及 Quest Prefab 路径，如有）
2. **结构化体检报告摘要**（直接摘自 `VrcAvatarAuditEditor.cs` 输出 JSON）：
   - 总三角面数 / SkinnedMeshRenderer 数 / 材质槽数
   - Humanoid 映射状态 + 15 Visemes & Eye Look 状态
   - MA 组件清单 + 同步参数占用 Bit 数（`XX / 256 bits`）
   - VRCPhysBone 组件数 / 影响骨骼数 / 碰撞体数
   - VRCSDK 阻断项数量（必须为 `0`）
3. **最终视觉确认**：仅在必要时附上最终 Unity 实机图（门禁 V4），确认光照、表情、穿戴效果无误。
4. **上传操作指引**：告知用户可在 VRChat SDK Control Panel 点击 `Build & Publish`（以及若为双端，如何先传 PC 再切 Android 平台传同一 Blueprint ID 的 Quest 版）。
