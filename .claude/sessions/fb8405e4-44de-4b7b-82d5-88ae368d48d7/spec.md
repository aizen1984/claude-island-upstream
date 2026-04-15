# 需求：降低 Claude Island 常驻 CPU 占用

## What
优化 Claude Island 菜单栏 App 的空闲/运行态 CPU 占用，从当前 **15-19%** 降到 **<5%**（悬浮状态栏 App 的合理区间）。

## Why
- 本次 `SessionConstellationView` 重写（499 行新增 Canvas + TimelineView 方案）使 CPU 从可忽略水平跃升到 15-19%
- WindowServer 被动飙到 57.8%，拖慢整机（用户同时在用 IDEA + 3 个 claude CLI）
- App 本身仅 118MB 内存，说明问题是持续计算/重绘，非数据处理

## 验收标准（AC）

| # | 验收项 | 验证方式 |
|---|--------|---------|
| AC1 | 3 个 claude 会话全 processing 状态下，Claude Island %CPU ≤ 5%（5 秒稳态采样均值） | `top -stats pid,command,cpu -l 6 -s 1 | grep "Claude Island"` |
| AC2 | 所有 Ripple/LED/header 动效肉眼无明显差异（无卡顿、无跳跃） | 录屏对比改前 vs 改后 |
| AC3 | 状态切换（processing → waitingForInput → idle）触发庆祝动画仍然正常 | 手动触发 claude 完成任务观察 |
| AC4 | Notch 展开/收起、hover 响应延迟 ≤ 当前水平 | 人工操作感知 |
| AC5 | 构建后的 app 覆盖安装，3 个会话并发工作 5 分钟不出现 CPU 尖峰 | 手动 5 分钟监测 |

## Out of Scope（本次不做）
- Canvas → Shape + animatableData 的 Core Animation 迁移（Tier 3，留待后续）
- NotchPanel 的合成策略优化（涉及 NSPanel 窗口层级，风险大）
- 审批流程任何改动（用户明确禁止）

## 复杂度评估
- **中型任务**：4 文件修改、约 10-15 处点修改、涉及动画语义验证
- **风险等级**：低（改动都是 `.animation` → `.periodic`，可逆）
- **建议流程**：RIPER 标准流程，跳过 DESIGN（改动机械、无架构决策）
