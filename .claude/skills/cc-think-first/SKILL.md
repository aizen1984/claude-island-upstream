---
name: cc-think-first
description: 在行动前执行三级预思考（L0跳过/L1快扫/L2深度分析），输出结构化思考结果。不执行任务本身。用于复杂决策、架构评估、模糊需求澄清
allowed-tools: Read, Grep, Glob
---

## Gotchas

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 简单任务使用 L2 深度分析 | 过度分析浪费上下文和时间 | 严格遵循三级判断：L0 条件命中直接跳过 |
| 2 | L1 五问中信息不足仍强行回答 | 结论基于猜测而非事实 | 第 0 问是门控：信息不足先补充信息再回答 |
| 3 | L2 分析后未执行 Step 5 自检反思 | 方案可能违反约束或超出边界 | L2 必须完整 5 步，Step 5 回扫 Step 1/2/4 |
| 4 | 多 Skill 串联时重复执行 cc-think-first | 上下文浪费 | 上游已执行并传递结论时，下游走 L0 跳过 |

# Think First

## Overview

- **双形态**：独立调用（`/cc-think-first`）+ 协议引用（`shared-rules/skill-orchestration.md` §七 预思考协议）

## 控制台输出（强制）

每次触发必须打印到控制台：

```
🧠 Think-First L{0|1|2} {级别名}
  {L0: 无后续 | L1: 五问单行摘要 | L2: S1-S5 标题列表}
```

**示例**：

L1：
```
🧠 Think-First L1 Quick
  信息: tdd-guard.js 已读 | 根因: Hook 超时频繁触发 | 约束: onError=deny 会阻断编辑 | 风险: 10s 过长影响体验 | 最简: 改 tdd-guard.js 1 处
```

## 三级自适应

| 级别 | 触发条件 | 输出 | 输出约束 |
|------|---------|------|---------|
| **L0 Skip** | 纯信息查询（不改代码）/已有 plan 执行子任务/用户说"直接改" | 输出 `🧠 L0 Skip`，直接执行 | 1 行 |
| **L1 Quick** | 变更涉及业务规则或跨模块约束/需确认影响面/中等任务 | 标题 + 五问摘要 | 2-5 行 |
| **L2 Deep** | 3+文件/模糊需求/架构决策/不可逆操作/用户主动要求 | 完整 5 步分析 | 不超过 1 屏（~40 行） |

**判断优先级**：L0 条件命中 → 跳过；L2 条件命中 → 深度；其余 → L1。

## L1 快速扫描（5 问）

```
0. 信息？ → 我是否已掌握足够上下文？还需要先读哪些文件/查什么日志/搜什么知识库/查什么最佳实践？（按研究阶梯 S1 代码→S2 知识库→S3 网络，见 inquiry-protocol.md §2）
1. 根因？ → 为什么要做这个改动？触发条件是什么？
2. 约束？ → 有哪些硬约束不能违反？
3. 风险？ → 最可能的失败方式？
4. 最简？ → 有没有改 1 个文件的方案？
```

**第 0 问是门控**：如果信息不足，先补充信息再回答后续四问。回答完即可行动，不展开分析。输出控制在 2-5 行。

**L1→L2 自动升级**：五问中 ≥3 个无法从现有上下文回答时，自动升级到 L2。控制台输出：`🧠 Think-First L1→L2 升级 | 原因: {N}/5 问题缺乏信息`

## L2 深度分析（5 步）

> 完整 L2 五步框架见 [analysis-l2.md](analysis-l2.md)（Step 1 精准定义 → Step 2 约束扫描 → Step 3 域判断 → Step 4 反转检查 → Step 5 方案与验证）。仅在三级自适应判定为 L2 时加载。

## 协作关系

> 被 6+ 个 Skill 内联引用（planner/cc-work-mode/code-writer/cc-design/cc-code-reviewer/cc-skill-creator）。详见 `shared-rules/skill-orchestration.md` §七。

---

## When Not to Use

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 完整任务拆解和多步骤规划 | cc-planner | 只做预思考，不产出可执行计划 |
| 直接写代码实现功能 | cc-code-writer | 只输出思考结论，不执行任务本身 |
| 需要对抗验证已有结论 | cc-adversarial | 正向分析，不是挑战结论 |

---

## 资源加载指导

| 时机 | 资源 | 说明 | 不加载 |
|------|------|------|--------|
| 独立调用（L0/L1） | SKILL.md（本文件） | 三级判断 + L1 五问 | analysis-l2.md, skill-orchestration.md §七 |
| 独立调用（L2） | SKILL.md + [analysis-l2.md](analysis-l2.md) | 完整五步框架 | skill-orchestration.md §七 |
| 被引用时 | shared-rules/skill-orchestration.md §七 预思考协议 | 精简版协议（仅 L0/L1/L2 判断规则 + L1 五问） | SKILL.md, analysis-l2.md（避免重复加载） |


