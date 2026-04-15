---
name: cc-work-mode
description: 编排最多10个并发subagent执行批量开发任务（四阶段工作流：ANALYZE / PLAN / EXECUTE / SUMMARIZE）。不做单任务开发、不做需求分析。用于已明确的批量并行任务执行、任务数 ≥5 的批量场景
argument-hint: [plan.md 路径或任务描述]
effort: high
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, Agent
report_generation: true
report_protocol: data-report-protocol
report_protocol_mode: grounding-only
---

> **Report Generation**（data-report-protocol `grounding-only`）：quote grounding 由委托方负责——独立调用时由 `cc-code-reviewer`（**Skill**）负责，内联派发时由 `cc-executor`（**内部 subagent_type**，见下方"内部 Agent 角色"段）负责。SUMMARIZE 传递审查报告时必须完整保留 `<quote>` 标签和 `scan_complete` 字段。

## Gotchas

> 从实际使用中积累的常见陷阱。每次发现新问题时追加。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | Task + run_in_background 与 TeamCreate 混用 | `[Request interrupted by user]` 报错 | 二选一：纯 Team（TeamCreate + Task(team_name)）或纯 Task（不带 team_name，可 run_in_background） |
| 2 | worktree 隔离在 sandbox 环境下不可用 | .git 权限拒绝导致 agent 创建失败 | sandbox 环境下不使用 worktree 隔离 |
| 3 | 并发 batch 未做冲突检测 | 多 agent 修改同一文件导致覆盖 | 派发前检查文件归属，有冲突的任务不进入同一 batch（算法见 workflows.md EXECUTE 章节冲突检测） |
| 4 | subagent 未获得 workspace 路径 | 读写项目根 plan.md 覆盖其他会话 | executor prompt 必须注入 📂 Workspace: {path} |
| 5 | executor 超时 15min 后任务状态丢失 | 无法判断任务进度，可能重复执行 | 超时任务标记失败不自动重试，手动检查 progress.md |
| 6 | planner 传入任务粒度过粗 | executor 无法在 15min 内完成，频繁超时 | 前置条件检查包含粒度验证，不达标返回 planner 继续拆解 |

# 数禾干活模式（cc-work-mode）

## Overview

cc-work-mode 是数禾的**批量任务高效执行引擎**。通过四阶段工作流（分析->计划->并行执行->汇总）和最多 10 个并发 subagent 执行批量开发任务。

**核心特点**：
- **四阶段工作流**：ANALYZE -> PLAN -> EXECUTE -> SUMMARIZE
- **10 并发执行**：最多同时派发 10 个 subagent
- **Ralph 持久模式**：不完成不停止
- **外置计划**：计划持久化到文件，信息不丢失
- **智能审查**：SUMMARIZE 后根据变更规模决定审查深度：
  - \> 300 LOC 或涉及事务/并发：强制深度审查（完整九维度）
  - 100-300 LOC：标准审查
  - < 100 LOC：快速审查（仅 P0-P1）
  - 仅文档/配置变更：跳过代码审查

---

## When to Use

**适用场景**：任务数 >= 5 且任务明确、用户明确说"干活"/"ralph"、批量文件修改

## When Not to Use

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 任务数 < 5 | cc-code-writer | 并发优势不明显，code-writer 更轻量 |
| 任务不明确需要分析 | cc-planner | 本 Skill 执行已明确任务，不做需求分析和任务拆解 |
| 设计文档/PRD | cc-design | 本 Skill 不产出设计文档 |

---

## 协作关系

- **接收自**: user（干活指令）、cc-planner（任务清单）
- **委托给**: cc-code-reviewer（智能审查，深度按变更规模自适应）
- **联动**: cc-tdd（executor 执行含 test_first 标记的任务时，引用 cc-tdd 的 RED-GREEN-REFACTOR 规则和 test_first 决策表。TDD session 由 executor 创建/销毁，tdd-guard.js Hook 负责阻断）
- **禁止**: executor 不能递归调用 work-mode（嵌套并发导致资源竞争，由 planner 统一调度）
- **隐式依赖**: cc-java-backend（executor 必须预加载）

### ⛔ 强制委托日志（跨 Skill 调用时必须输出）

| 时机 | 必须输出 |
|------|---------|
| SUMMARIZE 阶段委托 cc-code-reviewer 做智能审查 | `🔗 cc-work-mode.SUMMARIZE → cc-code-reviewer \| 原因: [深度审查/标准审查/快速审查] (变更 N LOC)` |
| 接收自 cc-planner（如果是被动接收）| 由 cc-planner 侧输出 `🔗 cc-planner.EXECUTE → cc-work-mode`，本侧不重复输出 |

> 详细协作矩阵见 `shared-rules/skill-orchestration.md` 第二章，数据契约见 `shared-rules/data-contracts.md`，日志格式见 `shared-rules/observability-logs.md` §2 运行时日志格式

---

## 资源加载指导

| 条件 | 加载文件 | 读取范围 | 不加载 |
|------|---------|---------|--------|
| 首次激活 | SKILL.md | 全量 | workflows.md, prompts.md, resources.md |
| ANALYZE 阶段 | `workflows.md`（ANALYZE 章节） | 按标题定位章节 | prompts.md, resources.md |
| PLAN 阶段 | `workflows.md`（PLAN 章节）+ `resources.md`（工作计划模板） | 按标题定位章节 | prompts.md |
| EXECUTE 阶段 | `workflows.md`（EXECUTE 章节：「核心算法：Ultrapilot 并行执行」→「并行派发方法」→「Ralph 持久模式」→「状态流转」） + `prompts.md`（executor prompt） | 按子章节标题分段读取 | resources.md |
| SUMMARIZE 阶段 | `workflows.md`（SUMMARIZE 章节）+ `prompts.md`（reviewer prompt） | 按标题定位章节 | resources.md |
| 派发 subagent | `resources.md`（Agent 调用示例 + 并行派发示例） | 按标题定位章节 | — |
| executor 执行 test_first 任务 | `cc-tdd/SKILL.md` | 全量 | prompts.md, resources.md |
| Subagent 预算约束 | `shared-rules/subagent-budget.md` | 全量 | — |
| 遇到需求模糊时 | `shared-rules/inquiry-protocol.md` | 全量 | workflows.md, prompts.md, resources.md |
| ANALYZE 前预思考 | `shared-rules/skill-orchestration.md` §七 预思考协议 | 全量 | workflows.md, prompts.md, resources.md |
| 会话文件操作前 | `shared-rules/session-workspace.md` | 全量 | — |
| 日志输出规范 | `shared-rules/observability-logs.md` | 全量 | — |
| Agent Teams 派发规则 | `agent-teams-rules.md`（本 Skill 目录） | 全量 | — |

---

## 前置条件检查（强制）

激活前必须检查：

| 条件 | 不满足时处理 |
|------|-------------|
| 有任务清单 | 建议先运行 cc-planner |
| 任务数 >= 5 | 建议使用 cc-code-writer |
| 任务已原子化（2-5 分钟粒度） | 返回 planner 继续拆解 |
| 依赖关系清晰 | 返回 planner 理清依赖 |

**例外**：用户明确说"干活"/"ralph"时，从 ANALYZE 阶段开始自行拆解。但若同时指向已有 plan.md（如"按 plan.md 执行"/"按计划执行"），则跳过 ANALYZE/PLAN，验证 plan 完整性后直接 EXECUTE。

---

## 预思考（强制，ANALYZE 阶段第一步）

进入 ANALYZE 阶段时，**必须**先执行 cc-think-first 预思考协议（`shared-rules/skill-orchestration.md` §七 预思考协议）。

**work-mode 专用 L0 条件**（在 protocol 通用 L0 基础上收紧）：
- **L0 跳过**：来自 planner 的完整任务清单（已原子化 + 依赖清晰） **或** 用户明确说"直接做"
- **至少 L1**：用户直接说"干活"但未提供完整任务清单，即使任务看似明确

输出 `🧠 Think-First L{0|1|2} {级别名}` 到控制台，L1/L2 完成后才可进入任务拆解。

**L1 结论复用**：L1 五问结论直接作为 ANALYZE 阶段"需求理解"和"约束识别"的初始输入，ANALYZE 仅补充 L1 未覆盖的内容（如现有代码分析），不重复已回答的问题。用户指令缺少关键信息时，L1 第 0 问即触发 inquiry-protocol 询问，补齐后再进入 ANALYZE。

---

## 四阶段工作流概览

> 各阶段详细流程见 `workflows.md`

```
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌───────────┐
│ ANALYZE │ → │  PLAN   │ → │ EXECUTE │ → │ SUMMARIZE │
│ 需求理解 │   │ 外置计划 │   │ 10并发   │   │ 执行报告   │
│ 只读    │   │ TaskCreate│   │ subagent │   │ 智能审查   │
└─────────┘   └─────────┘   └─────────┘   └───────────┘
```

| 阶段 | 目标 | 权限 | 产出 |
|------|------|------|------|
| ANALYZE | 深度理解需求，识别约束 | 只读 | 需求理解报告 |
| PLAN | 拆分原子任务，持久化计划 | 只读代码+写计划 | 外置计划文件 + TaskCreate |
| EXECUTE | 并行执行（最多10并发） | 全权限 | 可工作的代码 |
| SUMMARIZE | 生成报告 + **智能**审查（按变更规模选深度） | 只读代码+写报告 | 执行报告 + 审查报告 |

### 执行超时标准

| 维度 | 超时值 | 超时处理 |
|------|--------|---------|
| 单个 executor 任务 | 15 min | 标记失败，跳过，记录到 progress |
| 单个批次（10 并发） | 20 min | 等待所有 executor 完成或超时 |
| ANALYZE 阶段 | 10 min | 强制进入 PLAN |
| PLAN 阶段 | 5 min | 直接使用已有拆解 |
| 整体 work-mode 流程 | 60 min（非 Ralph）/ 180 min（Ralph Loop） | 保存检查点，建议分会话继续 |

---

## 数据契约（planner -> work-mode）

> 字段定义见 `shared-rules/data-contracts.md`

**接收后**：验证必填字段 -> 跳过 ANALYZE/PLAN -> 导入任务 -> 直接 EXECUTE

---

## 内部 Agent 角色

> 内部角色，不是独立 Skill，只能在 work-mode 内通过 Task 工具 `subagent_type` 调用。
> 调用代码示例见 `resources.md` 第二节。

| Agent | 预加载 Skills | 用途 |
|-------|--------------|------|
| cc-executor | cc-java-backend + cc-python + cc-frontend | 代码执行（EXECUTE 阶段主力，含测试编写） |
| cc-researcher | - | 快速代码研究（ANALYZE 阶段） |
| cc-reviewer | cc-code-reviewer + cc-java-backend + cc-python + cc-frontend | 深度审查（SUMMARIZE 阶段） |

---

## 外置文件位置

| 文件类型 | 位置 | 说明 |
|----------|------|------|
| 计划文件 | `.claude/work-plans/{timestamp}-{name}.md` | 项目 .claude/ 下（非 workspace 隔离） |
| 执行报告 | `.claude/work-reports/{timestamp}-{name}.md` | 项目 .claude/ 下（非 workspace 隔离） |
| plan.md | `{workspace}/plan.md` | Ralph 模式使用，workspace 由 session-workspace.md 规则决定 |

---



