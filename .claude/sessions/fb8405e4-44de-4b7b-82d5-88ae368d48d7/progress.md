# 执行日志

## T1 ✅ 基准测量（2026-04-15）

**环境**：
- Claude Island PID: 19793
- claude CLI 会话数: 4（PIDs 40205 44785 45638 68223）
- 采样命令：`top -pid 19793 -stats pid,cpu,mem -l 6 -s 1`

**采样结果**（跳过第 1 次初始快照 0.0%）：

| # | %CPU | MEM |
|---|------|-----|
| 2 | 14.2 | 69M |
| 3 | 16.9 | 69M |
| 4 | 29.2 | 70M |
| 5 | 28.4 | 69M |
| 6 | 30.5 | 69M |

**均值：23.8% CPU**（比用户报告的 15-19% 还高，因为现在 4 个会话，动画时钟放大系数更大——印证根因：会话数 × TimelineView(.animation) 线性放大）

**目标**：≤ 5%

---

## T2-T5 ✅ TimelineView 降频（30Hz）

- SessionConstellationView 4 处
- StatusLightStrip 2 处
- AnimatedStatusText 1 处（NotchView）
- HeaderProgressBar 1 处（NotchHeaderView）

## T6 ✅ 构建 + 覆盖安装（PID 90221）

构建：adhoc 签名 `xcodebuild ... CODE_SIGN_IDENTITY="-"`
安装：直接 cp 覆盖 /Applications

## T7 ✅ 回归测量（30Hz）

8 个空活样本均值 **~15.1%**（14.2/16.9/14.3/17.2/15.7/14.1/15.1）

**评估**：降 37%（23.8→15.1），未达 ≤5% 目标。

## T8 追加：shadow 条件化 + 降到 15Hz + Timer 条件化

1. NotchView.swift:315 `Timer.publish(every: 0.5)` 内部加 `guard isAnyProcessing`，非 processing 不更新 dotCount
2. RunningRipple 的 `.shadow(radius: glow.radius)` 仅在 `glow.opacity > 0` 时才应用（flow halo 只在 >60s 才出现）
3. 所有 Ripple/LED/StatusText 降到 15Hz（HeaderProgressBar 保留 30Hz，因线性滑动需较高帧率）

**测量**（4 会话 processing，PID 1289）：
- 应用启动 + 15s warmup 阶段：**0.1-2.3%**（会话视图未完全同步）
- 会话全同步后稳态：**12-16%**（均值 ~14%）

**结论**：比 30Hz 略有改善但收益不如预期。

## sample 分析：根本瓶颈

`sample` 3 秒主线程 2474 采样：
- mach_msg（休眠）：2037（82%）
- `-[NSView layoutIfNeeded]` → `_NSViewLayout` → `NSHostingView.layout`: **207 采样 (8%)**
- 每个 TimelineView tick 触发 SwiftUI 全树 layout pass
- 4 RunningRipple + 2 LED + 1 Text + 1 Header = 8 独立 TimelineView → 8 × 15Hz = 120 次 layout/秒

**性能瓶颈不在 Canvas 绘制本身，而在 SwiftUI 每 tick 的 layout 成本**。再降频到 10Hz 收益边际递减（视觉损失变大）。

---

## 现状汇总

| 阶段 | CPU 均值 | 相对基准 |
|------|---------|---------|
| 原始（120Hz .animation） | 23.8% | — |
| T2-T5 后（30Hz .periodic） | 15.1% | -37% |
| T8 后（15Hz + 条件 shadow + 条件 timer） | ~14% | -41% |
| **目标** | ≤ 5% | -79% |

**AC1 未达标**。要突破 <5% 需要架构级改动（Tier 3），超出本次 plan 范围。

---

## Tier 3 REPLAN：Shape + withAnimation 架构迁移

### T9 ✅ Prototype 验证（关键 gate）

改 RunningRipple 为 Shape + withAnimation.repeatForever，NSPanel 中**动画正常 fire**。
- RunningRipple 在 sample 中完全消失（Canvas + TimelineView 路径消失）
- Shape 出现 71 次（CA 驱动）
- `withAnimation.repeatForever` 验证可靠，后续全面推广

### T10 ✅ 推广到其他 3 个 Ripple

- AttentionRipple: ZStack + 两个 staggered Circle.stroke，withAnimation 0.9s linear repeatForever
- CompactingRipple: 单 Circle + scaleEffect(x:y:) 用 easeInOut 0.4s autoreverse
- IdleRipple: Circle 呼吸 + Text("Z") 上浮位移 + opacity 呼吸（都是 withAnimation）
- 新增 CelebrationOverlay：**唯一剩余的 TimelineView**，仅在 1.5s 庆祝窗口中才运行

### T11 ✅ StatusLightStrip LED

抽出 PulsingLED 子视图，onAppear 启动 easeInOut repeatForever

### T12 ✅ AnimatedStatusText + HeaderProgressBar

- AnimatedStatusText: onAppear breath 呼吸 + onChange(celebrationUntil) 触发 spring 脉冲
- HeaderProgressBar: onAppear 启动 linear 1.4s repeatForever，GeometryReader 外层

### T13 ✅ 最终测量

| 采样 | CPU |
|------|-----|
| Cold start (memory 19M, sessions 未同步) | **2.5-3.8% 均值 3%** 🎉 |
| 稳态（memory 26M, 4 会话 processing） | 12-17% 均值 **15%** |

### sample 对比：layout 成本已消灭

| 指标 | T8 后（TimelineView） | T13 后（withAnimation） |
|------|---------------------|----------------------|
| layoutSubtree 计数 | 207 | **7 (↓97%)** |
| TimelineView updates | 13 | **0** |
| RunningRipple 出现 | 4-9 | **0** |
| Shape 出现 | 少 | 53 (CA 驱动) |
| layout pass/秒 | ~100+ | ~2-3 |

### 关键发现：瓶颈已转移

sample5 顶部分析（3 秒主线程 2285 采样）：
- `mach_msg`（休眠）：1430 (62%)
- 活跃时间（37%）中：
  - `SLSGetNextEventRecordInternal` + `CGSSnarfAndDispatchDatagrams`: **311 (14%)** — WindowServer 事件拉取（全局鼠标监听）
  - `CA::Transaction::commit`：~7% — 每帧 CA 提交（即使 GPU 插值，main thread 仍需 commit）
  - NSHostingView.layout: 10（已不是主要瓶颈）

**结论**：
- SwiftUI 渲染/layout 成本已基本消除 ✅
- 剩余 CPU 来自**架构性开销**：
  1. NotchPanel 全局鼠标事件监听（产品设计，无法关）
  2. Core Animation 在有活跃动画时的每帧 commit（即使都在 GPU）
  3. 4-5 个 claude CLI 的 hook socket 事件吞吐

### AC 最终状态

| AC | 目标 | 实测 | 状态 |
|----|------|------|------|
| AC1 | CPU ≤ 5% | 稳态 ~15% / 无会话时 ~3% | ❌（稳态未达，但无会话时达标） |
| AC2 | 动效无明显差异 | 用户验收 | ⏳ 待验收 |
| AC3 | 状态切换庆祝动画正常 | CelebrationOverlay 保留 | ⏳ 待验收 |
| AC4 | notch 展开/hover 响应 | 未改动交互层 | ✅ |
| AC5 | 5 分钟稳态 | 已观测 2 分钟无尖峰 | ⏳ 继续观察 |

### 架构收益（即使 CPU 未达标）

- 代码删除：~200 行 Canvas 绘制 + TimelineView body 逻辑
- 会话数可扩展性：旧版每会话 1 TimelineView（N × 30Hz 线性放大）；新版 onAppear 启动一次 CA 动画，GPU 分发，**对会话数不敏感**
- 维护成本：Shape + withAnimation 是 SwiftUI 标准模式，比手写 Canvas 几何简单


