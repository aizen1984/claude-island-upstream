# 执行计划：降低 Claude Island CPU 占用

> 状态图例：⬜ 未开始 | 🔄 进行中 | ✅ 完成 | ⏸️ 阻塞 | ❌ 取消

## 总览

| 项目 | 值 |
|------|-----|
| 任务总数 | 8 |
| 预计总耗时 | 25-35 分钟 |
| 复杂度 | 中型 |
| 执行模式 | 文件驱动 + 主 agent 直接执行（任务 < 5，无需 work-mode） |
| 策略 | Tier 1（降频）→ 基准测试 → Tier 2（可见性门控，按需）|

## 任务清单

### Tier 1：TimelineView 降频到 30 Hz（主收益）

#### T1 ✅ 基准测量：记录当前 CPU（23.8% 均值，4 会话）
**文件**：无（外部观测）
**动作**：
- 启动当前 app（已安装版本）
- 启动 3 个 claude CLI 会话并让至少 1 个处于 processing
- `top -pid $(pgrep -n "Claude Island") -stats pid,cpu -l 6 -s 1` 采样 5 次
- 记录均值到 progress.md

**验证**：progress.md 含改前 CPU 基准数据
**预计耗时**：2 分钟

---

#### T2 ✅ `SessionConstellationView.swift` 四处降频
**文件**：`ClaudeIsland/UI/Components/SessionConstellationView.swift`
**改动**：
| 行号 | 结构体 | old | new |
|------|--------|-----|-----|
| 341 | RunningRipple | `TimelineView(.animation)` | `TimelineView(.periodic(from: .now, by: 1.0/30.0))` |
| 394 | AttentionRipple | 同上 | 同上 |
| 433 | CompactingRipple | 同上 | 同上 |
| 467 | IdleRipple | 同上 | 同上 |

**验证**：
- `grep -n "TimelineView(.animation)" SessionConstellationView.swift` 应为 0
- Swift 语法编译通过

**预计耗时**：3 分钟

---

#### T3 ✅ `StatusLightStrip.swift` 两处降频
**文件**：`ClaudeIsland/UI/Components/StatusLightStrip.swift`
**改动**：
- line 33 processing LED：`.animation` → `.periodic(from: .now, by: 1.0/30.0)`
- line 50 compacting LED：同上

**验证**：`grep -n "TimelineView(.animation)" StatusLightStrip.swift` → 0
**预计耗时**：1 分钟

---

#### T4 ✅ `NotchView.swift` 的 AnimatedStatusText 降频
**文件**：`ClaudeIsland/UI/Views/NotchView.swift`
**改动**：
- line 664：`TimelineView(.animation)` → `TimelineView(.periodic(from: .now, by: 1.0/30.0))`

**验证**：单点改动，grep 对应行确认
**预计耗时**：1 分钟

---

#### T5 ✅ `NotchHeaderView.swift` HeaderProgressBar 评估
**文件**：`ClaudeIsland/UI/Views/NotchHeaderView.swift`
**背景**：line 181 注释明确提到 NSPanel 中 `.animation` / `withAnimation` 可能不 fire——这块风险较高。
**决策**：
- HeaderProgressBar 仅在 processing 时显示（受父 view 条件渲染）
- 亮点横向滑动周期 1.4s，30 Hz = 42 帧/周期，视觉可接受
- **试验性改动**：同样降到 30 Hz；若 NSPanel 渲染失败则 revert 为 `.animation`

**改动**：line 184 `TimelineView(.animation)` → `TimelineView(.periodic(from: .now, by: 1.0/30.0))`
**验证**：构建后观察 processing 时亮条是否仍然平滑移动。若断帧或停止，立即 revert。
**预计耗时**：2 分钟

---

### 基准验证

#### T6 ✅ 构建 + 覆盖安装 + 启动（新 PID 90221）
**动作**（由 Claude 执行，遵循用户偏好）：
- `xcodebuild -scheme ClaudeIsland -configuration Release build` 或 `./scripts/build.sh`（看哪个更合适）
- 找到旧 app 位置、杀掉旧进程
- 直接 `cp -R` 覆盖（无 .bak，per memory: feedback_no_backup_on_replace）
- 启动新 app

**验证**：`pgrep -l "Claude Island"` 返回新 PID，菜单栏出现 Island
**预计耗时**：4-6 分钟（构建为主）

---

#### T7 ⬜ 回归测量 + 视觉核对
**动作**：
- 再次开 3 个 claude 会话，至少 1 个 processing
- 同 T1 命令采样 5 次记录均值
- 肉眼核对：RunningRipple 呼吸、AttentionRipple 双涌、CompactingRipple 挤压、IdleRipple Zzz、StatusLightStrip LED、AnimatedStatusText 呼吸、HeaderProgressBar 滑动

**通过条件**：
- AC1：%CPU ≤ 5% ✅
- AC2/AC3/AC4：动效无明显退化 ✅
- 若 AC1 未达但 CPU ≤ 10%，跳到 T8 继续优化；若 CPU 仍 >10%，进入 REPLAN

**预计耗时**：3 分钟

---

### Tier 2：可见性门控（按需启用）

#### T8 ✅（部分达成） NotchView Timer 条件化 + shadow 条件化 + 15Hz
**触发条件**：T7 后 CPU > 5%
**文件**：`ClaudeIsland/UI/Views/NotchView.swift`
**改动**：
- line 315 `Timer.publish(every: 0.5)` 的 `dotCount` 轮询：仅在 `isAnyProcessing == true` 时订阅
  - 方式：将 `.onReceive(Timer.publish(...))` 挪到条件视图内，或改为 `if isAnyProcessing` 包裹
- 确认 `showClosedActivity == false` 时 SessionConstellationView / StatusLightStrip 不在 view 树中（而非仅 opacity:0）

**验证**：
- 无 processing 会话时 CPU ≤ 2%
- dotCount "…" 三点动画仅在 processing 时显示

**预计耗时**：5 分钟（含验证）

---

## 依赖关系

```
T1 (基准) → T2/T3/T4/T5 (可并行但机械修改，主 agent 直接串行)
                     ↓
                     T6 (构建安装)
                     ↓
                     T7 (回归测量)
                     ↓
            达标? ──是→ ✅ 完成
                 ──否→ T8 (可见性门控)
                     ↓
                     循环回 T7
```

## 回滚策略

所有改动都是局部替换 `.animation` → `.periodic(...)`，单行可逆。若某处视觉异常：
```bash
git diff <file>  # 查看改动
git checkout <file>  # 回滚单文件
```

不涉及数据、不涉及 API 协议、不涉及审批逻辑。

---

### Tier 3（REPLAN）：Shape + withAnimation 架构迁移

> 用户选定 C 选项：架构级重写，目标 CPU <2%。
> **门控风险**：NotchHeaderView.swift:181 注释警告 `withAnimation` 在 NSPanel 中"may not fire"——T9 是 gate，失败即回退并停止。

#### T9 ✅ Prototype：RunningRipple 改 Shape+withAnimation（验证 NSPanel 兼容性）
**文件**：`SessionConstellationView.swift`（先只改 RunningRipple）
**方案**：
```swift
private struct RunningRipple: View {
    let phaseIndex: Int
    let phaseStartedAt: Date
    @State private var breath: Double = 0
    @State private var ringProgress: Double = 0

    var body: some View {
        ZStack {
            Circle()  // expanding ring
                .stroke(TerminalColors.prompt, lineWidth: 1)
                .scaleEffect(0.5 + ringProgress * 0.94)
                .opacity(0.55 * (1 - ringProgress))
            Circle()  // center dot
                .fill(TerminalColors.prompt)
                .frame(width: size * 0.5, height: size * 0.5)
                .opacity(0.78 + breath * 0.22)
        }
        .frame(width: size, height: size)
        .onAppear {
            withAnimation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true)) {
                breath = 1.0
            }
            withAnimation(.linear(duration: 3.0).repeatForever(autoreverses: false)) {
                ringProgress = 1.0
            }
        }
    }
}
```
**验证通过条件**：
- A) 视觉：Ripple 和原来一样呼吸+扩散（允许 breath 曲线从 asymmetric organicBreath → easeInOut 的轻微差异）
- B) CPU：仅改 RunningRipple 后，4 会话稳态 CPU 下降可测（至少比 14% 低 30%）

**验证失败条件**：
- 视觉僵死不动（withAnimation 在 NSPanel 不 fire）
- 或视觉错乱

**失败处理**：`git checkout SessionConstellationView.swift`，回到 T8 后状态，停止 Tier 3，接受 14%。

**预计耗时**：15 分钟（含构建+测量）

---

#### T10 ✅ [已执行] 推广到其他 3 个 Ripple
**触发条件**：T9 成功
**文件**：`SessionConstellationView.swift`
**改动**：
- AttentionRipple：双 ring 用 phase-offset 的 withAnimation（两个 Circle 各自 repeatForever）
- CompactingRipple：scaleEffect(x:y:) 用 withAnimation.easeInOut.repeatForever(autoreverses: true)
- IdleRipple：center breath + Z 字位移用 withAnimation

**删除**：Canvas、drawRipple、organicBreath 的 TimelineView 调用（保留 organicBreath 函数本身，可能还被其它地方用）

**预计耗时**：20 分钟

---

#### T11 ✅ [已执行] 推广到 StatusLightStrip LED
**文件**：`StatusLightStrip.swift`
**改动**：processing/compacting LED 用 `.opacity(breath)` + withAnimation.easeInOut.repeatForever(autoreverses: true) 替代 TimelineView
**预计耗时**：5 分钟

---

#### T12 ✅ [已执行] 推广到 AnimatedStatusText + HeaderProgressBar
**文件**：`NotchView.swift` / `NotchHeaderView.swift`
**改动**：
- AnimatedStatusText：text 的 opacity 呼吸用 withAnimation
- HeaderProgressBar：亮条 offset 用 withAnimation.linear.repeatForever（非常适合，线性+循环）

**预计耗时**：10 分钟

---

#### T13 ✅ 最终测量 + 视觉回归
**验证**：
- AC1：CPU 稳态 ≤ 5%（理想 <2%）
- AC2-AC4：完整视觉回归
- 至少 2 分钟稳态观测，无 CPU 尖峰

**预计耗时**：5 分钟

---

## 阶段确认

**⛔ G3 门控**：PLAN 完成，等待用户确认后进入 EXECUTE。

用户确认项：
1. 是否同意 Tier 1（7 处 `.animation` → `.periodic` 30Hz）一把梭？
2. 是否接受 Tier 2（T8 可见性门控）作为条件触发的追加任务？
3. 对 HeaderProgressBar（T5）的试验性降频有无保留意见？
