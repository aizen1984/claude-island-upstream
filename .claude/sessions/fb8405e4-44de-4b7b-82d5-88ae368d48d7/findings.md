# RESEARCH 发现：Claude Island CPU 占用 15-19% 根因分析

## 1. 问题定义

**现象**：Claude Island.app 稳定占用 15-19% CPU（5 秒采样 18.5/15.6/15.8/17.3/15.3），内存仅 118MB。同机 WindowServer 同步飙到 57.8%。

**预期**：悬浮状态栏类 App 空闲时应 <1% CPU。

**问题类别**：渲染循环堆叠（非文件轮询、非 IPC 重连风暴）。

## 2. 根因

**SwiftUI `TimelineView(.animation)` 按 display-link（60/120 Hz）驱动 body 重新求值**。Notch 常驻层同时运行 **7+ 个**独立动画时钟，每个内部执行三角函数 + Canvas 重绘。会话数越多，时钟数越多（线性放大）。

WindowServer 高是合成副作用：合成半透明常动图层每帧都要重新混合。

## 3. 代码路径（证据）

### 3.1 常驻动画时钟清单

| 文件 | 行号 | 动画时钟数 | 触发条件 | 每帧代价 |
|------|------|-----------|---------|---------|
| `SessionConstellationView.swift` | 341 | 1 × RunningRipple | 每个 processing 会话 1 个 | Canvas + sin(elapsed) × 3 |
| `SessionConstellationView.swift` | 394 | 1 × AttentionRipple | 每个 attention 会话 1 个 | Canvas + sin × 3 + celebration particles |
| `SessionConstellationView.swift` | 433 | 1 × CompactingRipple | 每个 compacting 会话 1 个 | Canvas + sin/cos |
| `SessionConstellationView.swift` | 467 | 1 × IdleRipple | 每个 idle 会话 1 个 | Canvas + sin + Text drift |
| `StatusLightStrip.swift` | 33 | 1 × processing LED | 每个 processing 会话 1 个 | organicBreath sin |
| `StatusLightStrip.swift` | 50 | 1 × compacting LED | 每个 compacting 会话 1 个 | organicBreath sin |
| `NotchView.swift` | 664 | 1 × AnimatedStatusText | header 常驻 | sin + 2 × shadow + scaleEffect |
| `NotchHeaderView.swift` | 184 | 1 × HeaderProgressBar | 仅 processing 时出现 | Geometry + offset（相对便宜） |
| `NotchView.swift` | 315 | Timer 0.5s | 常驻 | `dotCount += 1` 触发 body 刷新 |

**常驻条件**：`showClosedActivity && viewModel.status != .opened`（NotchView.swift:450）
→ 只要有会话在，notch 没展开也在跑所有动画。

### 3.2 放大系数

当前用户：3 个 claude CLI 会话。实测分布：若全部 processing，则：
- 3 × RunningRipple（SessionConstellation）
- 3 × processing LED（StatusLightStrip）
- 1 × AnimatedStatusText
- 1 × HeaderProgressBar（processing 时）

= **8 个 TimelineView(.animation)** 同屏。ProMotion 120 Hz → **960 次/秒 body 求值 + Canvas 命令生成**。

### 3.3 本次改动的放大器

`git diff --stat` 显示 `SessionConstellationView.swift` 新增 **499 行**（从 ghost SF Symbol 重写成 Canvas Ripple 方案）。之前每会话 1 个静态 Image，本次改为每会话 1 个 Canvas + 独立 TimelineView。**这就是 CPU 突飞的拐点**。

## 4. 约束

- **视觉质感不能明显掉档**：涟漪/呼吸是产品核心观感，降帧不能造成跳跃
- **闭合 notch 也要显示状态**：`showClosedActivity` 是必须的，不能全关
- **用户记忆（全局偏好）**：
  - 覆盖安装不做 `.bak`
  - 构建+关旧 app+安装+启动 由 Claude 负责
  - 审批相关代码完全不碰
- **macOS 15.6+ API 可用**：`TimelineView(.periodic(from:by:))` 原生支持

## 5. 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| 30 Hz 降频后呼吸感觉"断" | 低 | 呼吸周期 2s，30 Hz = 60 帧/周期，肉眼无差 |
| 闭合 notch 暂停动画后恢复有跳帧 | 中 | 用 `elapsed` 基于 Date 计算，无状态累积，恢复即对齐 |
| `.periodic` API 在 NSPanel 中失效（参考 NotchHeaderView:181 注释） | 中 | 先单点验证 HeaderProgressBar 用 .periodic 是否照常渲染；失败则 fallback |
| Canvas → Shape+animatableData 重构破坏视觉 | 高 | 放 Tier 3，先不做，Tier 1/2 收益已足够 |

## 6. 优化方案（按收益/风险排序）

### Tier 1：降频（高收益，零风险）
所有 `TimelineView(.animation)` → `TimelineView(.periodic(from: .now, by: 1.0/30.0))`
- 影响：7 处
- 预期效果：CPU 从 15-19% 降到 **4-6%**（降频 75%）
- 视觉损失：几乎为零（呼吸 2s / 涟漪 3s / 双涌 0.9s，30 Hz 均远超视觉阈值）

### Tier 2：可见性门控（中等收益，低风险）
- `onReceive(Timer.publish(every: 0.5))` → 仅 processing 时订阅，或 notch 可见时订阅
- `showClosedActivity` 为 false 或 `viewModel.status == .opened` 时，不渲染 StatusLightStrip / SessionConstellation（已有，但确认 view 被从树中摘掉而非隐藏）
- 预期效果：再降 1-2%

### Tier 3：CA 原生动画（长期，暂不做）
- Canvas → Shape 带 `animatableData`
- `withAnimation(.linear.repeatForever)` 让 Core Animation 在 GPU 插值
- 预期效果：CPU <2%
- 风险：Ripple 当前用 sin 计算 opacity/scale，迁移到 animatableData 需重新设计数学模型

## 7. 验证方法

1. **活动监视器采样**：改前/改后各取 5 秒，%CPU 对比
2. **Instruments Time Profiler**：抓 10 秒样本，确认 `TimelineView` body 调用次数下降
3. **视觉回归**：录屏对比 Ripple / LED / AnimatedStatusText 动效
4. **构建产物**：Claude 构建 + 覆盖安装 + 启动 3 个 claude 会话观察 5 分钟稳态

## 8. 对抗验证（自检）

- **Q: 是不是 StatusLightStrip 只在有会话时出现，没会话就 0 CPU？**
  A: 是。但用户场景"3 个 claude 会话"正好触发。
- **Q: 能不能干脆全部换成 CSS-style `.animation` + `withAnimation`，让 Core Animation 处理？**
  A: NotchHeaderView.swift:181 有明确注释："secondary NSPanel 中 withAnimation / .animation() 可能不 fire"——已踩过坑。保守先降频。
- **Q: 降到 30 Hz 是不是太激进？**
  A: 不激进。系统的 scrolling/CA 大量使用 30-60 Hz；Ripple 的最快周期是 0.6s（AttentionRipple），30 Hz = 18 帧/周期，完全够。

## 9. 结论

根因明确、约束清晰、方案收敛。**先做 Tier 1 降频**，验证有效（预期 CPU 立降 ≥70%），再视情况追加 Tier 2。Tier 3 不纳入本次计划。
