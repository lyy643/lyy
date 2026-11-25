# 03. Unity Humanoid 绑骨、表情形态键与 FBX 导出指南

本阶段目标是在 Blender 中完成**零 MMD 依赖**的 Unity Humanoid 骨架绑定、权重动态验收、VRChat 标准 BlendShapes（口型/眨眼/表情），并导出可直接进 Unity 的规范 FBX。

---

## 1. Unity Humanoid 骨架规范

### 1.1 必需核心骨骼层级
所有骨骼使用标准英文命名（清晰对称，`.L` / `.R` 后缀），严格匹配 Unity Humanoid Avatar 映射：

```text
Armature
└── Hips
    ├── Spine
    │   └── Chest
    │       └── UpperChest (推荐)
    │           ├── Neck
    │           │   └── Head
    │           │       ├── LeftEye   (眼追必需)
    │           │       ├── RightEye  (眼追必需)
    │           │       └── Hair_* / Ear_* (物理子骨，挂在 Head 下)
    │           ├── Shoulder.L -> UpperArm.L -> LowerArm.L -> Hand.L -> [Thumb/Index/Middle/Ring/Little 1-3.L]
    │           └── Shoulder.R -> UpperArm.R -> LowerArm.R -> Hand.R -> [Thumb/Index/Middle/Ring/Little 1-3.R]
    ├── UpperLeg.L -> LowerLeg.L -> Foot.L -> Toes.L
    ├── UpperLeg.R -> LowerLeg.R -> Foot.R -> Toes.R
    ├── Skirt_*_* (裙摆物理链，挂在 Hips 下)
    └── Tail_01 -> Tail_02 -> ... (尾巴物理链，挂在 Hips 下)
```

### 1.2 VRC 绑骨避坑红线
- **姿态**：Rest Pose 严格保持 **T-Pose**（手臂水平沿 X 轴展开，手指自然伸直略微张开，双腿微开直立）。
- **单根骨骼与尺寸**：角色整体身高通常在 `1.3m ~ 1.8m`（Q 版可酌情缩小），脚底紧贴 `Z = 0` 平面。
- **胸/腹/胯层级**：严禁出现 `Hips -> Head` 跳过 Spine/Chest 的残缺骨架，否则 VR 全身追踪（FBT）与动画重定向会直接扭曲。
- **眼骨位置**：`LeftEye` / `RightEye` 骨骼根部必须精确位于左右眼球球心，且轴向水平朝前，保证 Unity `Eye Look` 旋转时不脱眶穿模。
- **物理骨链提前预留**：头发、呆毛、裙摆、飘带、兽耳、尾巴在 Blender 中直接建好骨骼链并刷好渐变权重（末端权重平滑过渡），供 Unity 中直接挂 **VRCPhysBone**。

---

## 2. 权重校验（先脚本查空点，再摆姿验变形）

1. **结构化检查**：运行 `scripts/blender_vrc_audit.py`，确保：
   - `unweighted_vertices == 0`（任何未分配权重的顶点都会在 Unity 动画里拉丝飞到原点）；
   - 每个顶点受影响骨骼数建议规范到 `<= 4`（Unity 蒙皮默认 4 Bone 权重，超过会被截断导致穿模；可用 Blender `Limit Total (4)` + `Normalize All` 自动处理）。
2. **极端摆姿压力测试**（通过 Blender MCP 临时旋转 Pose Bone 验证，测完恢复 Rest Pose）：
   - 双臂高举 150°（查腋下/肩膀塌陷与衣袖穿模）；
   - 双臂抱胸（查胸口与大臂穿插）；
   - 大幅度下蹲 / 抬腿 90°（查胯部、大腿根部与裙摆穿模）；
   - 抬头/低头/转头 60°（查颈部拉扯与头发穿肩）；
   - 握拳与五指弯曲（查手指关节折断）。
3. 必要时输出 **门禁 V3** 关键摆姿拼图供视觉确认，修复后再恢复归零姿态。

---

## 3. VRChat 标准 BlendShapes（Shape Keys）

> **注意**：VRChat 的口型（LipSync）和眨眼默认从 **同一个主面部 Mesh（通常是 `Body`）** 读取 Shape Keys！请勿把眼睛眨眼和嘴部口型拆散在两个不同的 Mesh 上，除非明确使用自定义 FX 动画分别驱动。

### 3.1 15 个标准 Visemes 口型（语音对口型必需）
全部放在主面部 Mesh 上，推荐标准命名：
- `vrc.v_sil`（静音闭口，可为极微弱基准态）
- `vrc.v_pp`（双唇闭紧：p/b/m）
- `vrc.v_ff`（上齿咬下唇：f/v）
- `vrc.v_th`（舌尖微露：th）
- `vrc.v_dd`（舌抵上腭：d/t）
- `vrc.v_kk`（后颚微张：k/g）
- `vrc.v_ch`（齿合微咧：ch/j/sh）
- `vrc.v_ss`（齿合微笑：s/z）
- `vrc.v_nn`（鼻音微张：n/l）
- `vrc.v_rr`（卷舌微圆：r）
- `vrc.v_aa`（大张口：a）
- `vrc.v_e`（横向张口：e）
- `vrc.v_ih`（微扁张口：i）
- `vrc.v_oh`（圆形张口：o）
- `vrc.v_ou`（小圆嘟嘴：u）

**质量红线**：测试任意口型拉到 `1.0` 时，嘴唇边缘不能撕裂、不能露出外部背景穿洞、口腔/牙齿/舌头位置自然。

### 3.2 眨眼与基础表情（手势驱动用）
- **眨眼**：`Blink`（双眼闭合，用于 VRChat 自动眨眼），可选 `Blink_L` / `Blink_R`（Wink）。
- **常用 7 套基础表情**（可组合或独立制作，供 Unity 手势触发）：
  - `Expr_Smile`（微笑/开心）
  - `Expr_Joy`（眯眼大笑）
  - `Expr_Angry`（生气皱眉）
  - `Expr_Sad`（委屈/难过）
  - `Expr_Surprise`（惊讶）
  - `Expr_Blush`（害羞/脸红，可配合材质或脸红贴片）
  - `Expr_Smug` / `Expr_Wink`（得意/眨眼）
- **进阶可选（面捕玩家）**：若用户需要眼面捕，按 **ARKit 52** 标准名称（`eyeBlinkLeft`, `jawOpen`, `cheekPuff` 等）制作完整形态键，或使用 VRCFaceTracking 标准映射。

---

## 4. 标准化 FBX 导出规范

始终优先使用 `scripts/blender_export_vrc_fbx.py` 导出（或在 Blender MCP 中按以下参数执行 `bpy.ops.export_scene.fbx`）：

- **只导出可见的 `ARMATURE` 和 `MESH`**（剔除 `CAMERA`、`LIGHT`、`EMPTY` 杂物）。
- **Apply Scalings**：`FBX_SCALE_ALL`（确保进 Unity 后 Scale 为干净的 `(1, 1, 1)`，避免 `100` 倍缩放坑）。
- **Forward / Up**：`-Z Forward`、`Y Up`（Blender 导出器自动把面向 `-Y`、顶部 `+Z` 的模型转为 Unity 标准坐标）。
- **Apply Modifiers**：**关闭**（`use_mesh_modifiers=False`）！如果开着 Apply Modifiers 导出带 Shape Keys 的 Mesh，Blender 会直接把所有 Shape Keys 全部抹掉！必须提前把除 `Armature` 之外的修改器手动合并好。
- **Add Leaf Bones**：**关闭**（`add_leaf_bones=False`），避免生成一堆无用的 `_end` 末端骨污染 PhysBone 和骨骼计数。
- **Geometry Smoothing**：`FACE` 或 `EDGE`，确保法线平滑不产生奇怪硬边。

---

## 5. 阶段 3 验收门禁（Gate 3）

- [ ] `scripts/blender_vrc_audit.py` 返回 `errors: []`（无空权重顶点、无超 4 骨权重警告、Humanoid 核心骨全齐、15 Visemes 与 `Blink` 命名检查通过）。
- [ ] 导出 FBX 后，可重新导入空白 Blender 场景或直接进 Unity MCP 验证：**Shape Keys 完整未丢失、骨骼无多余 Leaf Bones、模型站立朝前且身高正常**。
- [ ] 另存为 `04_rigged_blendshapes.blend`。
