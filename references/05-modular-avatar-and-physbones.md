# 05. Modular Avatar (MA) 优先装配与 VRCPhysBone 实时物理指南

本阶段贯彻两大原则：
1. **Unity 中凡是能用 Modular Avatar (MA) 实现的功能，一律优先用 MA**（非破坏性、模块化、可热插拔、彻底避免破坏原 Avatar 的 FX Controller 与 Menu）。
2. **用 VRChat 实时物理（VRCPhysBone）完全替代离线布料解算**，兼顾自然飘动与高稳定性。

---

## 1. Modular Avatar (MA) 优先决策表

在 Unity 中通过 **Unity MCP** 挂载对应 MA 组件（不要手改底层根控制器，除非 MA 确实无法覆盖）：

| 需求场景 | 首选 Modular Avatar 组件 | 优势与用法要点 |
| --- | --- | --- |
| **给角色穿新衣服/换装（带独立骨架）** | `MA Setup Outfit`（一键生成 `MA Merge Armature` + `MA Mesh Settings`） | 自动把服装骨架合并到角色主骨架，保持原 Prefab 干净，删掉服装节点即卸载 |
| **把简单饰品/道具挂到指定骨头上** | `MA Bone Proxy` | 例如挂耳环/发卡到 `Head`、挂手持物到 `Hand.R`，不修改原始骨架层级 |
| **制作简单的显示/隐藏开关（Toggle）** | `MA Menu Item`（Type = Toggle）+ `MA Object Toggle` | **零手写 Animation Clip、零手写 Animator 状态机！** 直接在 MA Object Toggle 里勾选显示/隐藏哪些物体 |
| **把自定义菜单挂载到主圆盘菜单** | `MA Menu Installer` + `MA Menu Group` | 自动将子功能打包成整齐的子菜单（如“换装”、“表情”、“饰品”），不会覆盖别人已有的主菜单 |
| **合并自定义表情/动作状态机（FX/Action）** | `MA Merge Animator` | 将手势表情控制器、眼面捕控制器作为独立模块合并进 `FX` 层，务必注意 **Write Defaults (WD)** 模式与主模型一致（推荐统一 `Match Avatar Write Defaults`） |
| **声明与同步参数（Saved / Synced）** | `MA Parameters` | 自动合并参数进 `VRCExpressionParameters`，避免手动维护参数表或超 Bit 限额 |
| **统一全身光照采样点与防消失包围盒** | `MA Mesh Settings` | 挂在 Avatar 根节点，一键接管全身 `Probe Anchor` 和 `Root Bone / Bounds` |
| **隐藏服装底下的素体防穿模** | `MA Shape Changer`（改 Shrink 形态键）或透明遮罩 | 配合 `MA Object Toggle`：穿上外套时自动把素体对应收缩 BlendShape 拉到 `100` |

### MA 避坑铁律
- **Write Defaults (WD) 一致性**：VRChat 最常见表情卡死 Bug 来源就是 FX 层里一半状态 `WD On`、一半 `WD Off`。使用 `MA Merge Animator` 时勾选 **Match Avatar Write Defaults**，并在独立表情动画中遵守统一规范。
- **手势表情防冲突（关键！）**：
  - 手势触发表情（如眯眼大笑 `Expr_Joy`）时，如果自动眨眼（`Eye Look` Blink）仍在运行，会叠加导致眼皮穿模扭曲！
  - 解决办法：在闭眼/眯眼类表情的 Animator State 上添加 **`VRC Animator Tracking Control`**，将 `Eyes & Eyelids` 设为 `Animation`；回到默认（Idle/Neutral）状态时再设回 `Tracking`！
- **测试 MA 构建结果**：通过 **Gesture Manager**（Play Mode）直接测试 MA 虚拟合并后的圆盘菜单、开关与手势，**完全无需频繁上传 VRChat**。

---

## 2. 什么时候回退到原生 FX Animator + Expressions Menu？

仅在以下少数场景使用原生手写 Animator（并依然用 `MA Merge Animator` 挂载，保持模块化）：
- 复杂的连续 Radial Puppet 混合树（如无级调节裙长、无级色相/发光亮度滑动条）；
- 多条件组合状态机（如“左手剪刀手 + 右手握拳 = 特殊连招表情”）；
- 复杂的材质属性动画（驱动 lilToon/Poiyomi Shader 参数的逐帧曲线动画）。

---

## 3. VRCPhysBone 实时物理配置规范

用 **VRCPhysBone** 驱动头发、呆毛、裙摆、飘带、兽耳、尾巴、胸部的实时弹性物理。

### 3.1 推荐挂载位置与分组策略
- **不要直接把 `VRCPhysBone` 挂在 `Head` 或 `Hips` 根节点上然后靠 Ignore 排除全身！**
- 推荐做法：在 Avatar 下新建一个空物体组 `PhysBones`（方便集中管理），按部位建子物体（如 `PB_Hair_Front`、`PB_Hair_Back`、`PB_Skirt`、`PB_Tail`、`PB_Ears`），在组件里指定 `Root Transform`（或直接挂在对应链的父骨骼上，开启 `Multi-Child Type = Ignore` 或 `Average`）。

### 3.2 常用部位初始手感参考参数（可在 Play Mode 用 Gesture Manager 拖拽测试）

| 部位 | Pull（回弹力） | Spring（弹性惯性） | Immobile（抗位移僵硬） | Gravity（重力） | Limit（角度限制） |
| --- | --- | --- | --- | --- | --- |
| **前刘海 / 鬓角** | `0.25 ~ 0.4` | `0.2 ~ 0.35` | `0.3 ~ 0.5` | `0.05` | Hinge 或 Angle `20°~35°`（防穿进脸里） |
| **长发 / 马尾** | `0.15 ~ 0.25` | `0.3 ~ 0.5` | `0.15 ~ 0.3` | `0.1 ~ 0.2` | Angle `45°~70°` + 胸/背/肩碰撞体 |
| **兽耳 / 呆毛** | `0.3 ~ 0.5` | `0.5 ~ 0.7` | `0.1 ~ 0.2` | `0` | Angle `30°~45°`（Q 弹有活力） |
| **裙摆** | `0.25 ~ 0.4` | `0.15 ~ 0.3` | `0.2 ~ 0.4` | `0.1 ~ 0.25` | 配合大腿 `Inside/Outside` 胶囊碰撞体防坐姿穿模 |
| **尾巴** | `0.15 ~ 0.3` | `0.35 ~ 0.55` | `0.1 ~ 0.25` | `0.05 ~ 0.15` | Angle `50°~80°` |

### 3.3 碰撞体（VRCPhysBoneCollider）极简原则
- 优先挂在 `Head`、`Chest`、`UpperLeg.L / R`、`Hand.L / R` 上（手部碰撞体可实现自己和别人摸头/拨头发互动）。
- 碰撞体尽量使用 **Capsule（胶囊体）**，准确包住头、躯干与大腿，并在各部位 PhysBone 的 `Colliders` 列表中**只关联真正会接触的碰撞体**（例如前刘海只需要头碰撞体和手碰撞体，不需要大腿碰撞体，减少无效计算与鬼畜抖动）。
- 如需防止角色在原地微小抽搐，开启合理的 `Radius` 与 `Limit`，并在 Blender 绑骨阶段确保裙摆/头发末端骨有平滑权重。

---

## 4. 阶段 5 验收门禁（Gate 5）

- [ ] 通过 Unity MCP 运行 `VrcAvatarAuditEditor.cs`，确认：
  - 所有 MA 组件无 Missing Reference / 空目标；
  - 所有 `VRCPhysBone` 均正确指定有效根骨，无空 Collider 引用，无把整条 Humanoid 躯干骨误纳入物理链的严重错误。
- [ ] 在 Unity Play Mode（Gesture Manager）中验证：
  - 所有 MA 菜单层级清晰、开关生效且无残留穿模；
  - 触发手势表情时眨眼不会打架穿模；
  - 拖拽角色或摆动时，头发/裙摆物理自然回弹、无剧烈爆炸抖动。
