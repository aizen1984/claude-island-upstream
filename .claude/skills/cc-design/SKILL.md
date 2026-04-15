---
name: cc-design
description: 生成设计文档（PRD/技术方案/逆向文档），支持复杂度感知和分层设计。不写代码、不拆解任务。用于新功能设计、技术方案编写、已有代码文档化
argument-hint: [需求描述或现有功能模块名]
effort: high
allowed-tools: Read, Grep, Glob, Write, Agent, WebSearch, WebFetch
report_generation: true
report_protocol: data-report-protocol
report_protocol_mode: full
---

> **Report Generation 声明**（data-report-protocol Iter 22，仅逆向路径生效）：本 skill 的**逆向文档生成路径**（`workflows/workflows-reverse.md`）从现有代码生成 PRD/技术文档时，必须遵守 quote grounding。Gotcha #3 已要求"所有推断内容标记 `[推断]`"——本协议**升级**为：每条推断结论必须附 `<quote file="..." line="...">引用代码原文</quote>` + `[推断]` 标记，找不到原文支持的推断必须删除并在"待确认列表"留痕 `[REMOVED:no-quote]`。**正向设计路径不受约束**（设计文档基于需求而非现有代码，无 quote 来源）。

# 数禾设计文档工作流

## Overview

专注于**文档生成**：PRD 文档、技术设计文档、逆向文档。提供复杂度感知、分层设计、双向同步、逆向能力。

**核心产出**：设计文档（PRD、技术方案），而非可执行任务清单。

---

## When to Use

| 使用场景 | 示例 |
|---------|------|
| 新功能设计 | "帮我设计一个用户积分系统" |
| 技术方案编写 | "写一个技术方案文档" |
| 重构方案设计 | "设计订单系统的重构方案" |
| 逆向文档化 | "帮我整理 OrderService 的文档" |

## When Not to Use

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 任务拆解和执行规划 | cc-planner | 本 Skill 产出设计文档，不产出可执行任务清单 |
| 代码实现 | cc-code-writer | 本 Skill 不写代码，design 必须经 planner 拆解后才能进入实现 |
| 代码审查 | cc-code-reviewer | 本 Skill 做设计评审，不做代码级审查 |

---

## 协作关系

- **接收自**: user（直接请求）、cc-planner（PLAN完成后自动委托中型/大型任务）
- **委托给**: cc-planner（设计完成后拆解任务）、cc-diagram（架构图）、cc-api-analyzer（接口分析）
- **隐式依赖**: cc-java-backend（Java 相关设计自动加载规范）
- **禁止链路**: design -> code-writer（必须经 planner 拆解）

### ⛔ 强制委托日志（跨 Skill 调用时必须输出）

| 时机 | 必须输出 |
|------|---------|
| 设计完成后委托 cc-planner 拆解任务 | `🔗 cc-design.OUTPUT → cc-planner \| 原因: 设计文档已完成，需拆解为可执行任务` |
| 需要架构图时委托 cc-diagram | `🔗 cc-design.DIAGRAM → cc-diagram \| 原因: 生成 [架构图/时序图/类图]` |
| 需要接口分析时委托 cc-api-analyzer | `🔗 cc-design.RESEARCH → cc-api-analyzer \| 原因: 逆向分析现有接口` |
| 接收自 cc-planner（被动接收）| 由 cc-planner 侧输出 `🔗 cc-planner.PLAN → cc-design`，本侧不重复输出 |

> 详细协作矩阵见 `shared-rules/skill-orchestration.md` 第二章，数据契约见 `shared-rules/data-contracts.md`，日志格式见 `shared-rules/observability-logs.md` §2 运行时日志格式

### 输出数据契约

| 字段 | 说明 | 示例 |
|------|------|------|
| 设计文档路径 | vault 中的文档路径 | `vault/项目名/需求/xxx_技术设计.md` |
| 复杂度评估 | 大型/中型/小型 | `large` |
| 审查状态 | 设计审查是否通过 | `approved` / `pending` |
| 变更范围摘要 | 新增/修改文件数和模块列表 | `新增 3 文件，修改 5 文件，涉及 order/payment 模块` |

### 接收 planner 委托时的行为

1. 执行对应复杂度的 Phase 流程（详见 [references/complexity-rules.md](references/complexity-rules.md)）
2. 基于 planner 传递的任务清单和需求上下文生成总体技术设计文档
3. 完成后**返回 planner 控制流**，不展示 design 自身的"下一步建议"
4. 设计文档按全局 CLAUDE.md 的文档写入规则输出到 vault 对应目录

---

## 资源加载指导

| 条件 | 加载文件 | 读取范围 | 不加载 |
|------|---------|---------|--------|
| 设计文档生成流程 | [workflows/workflows-forward.md](workflows/workflows-forward.md) | 全量 | workflows-reverse.md, prompts-reverse.md, templates-prd.md（逆向用） |
| 逆向文档生成流程 | [workflows/workflows-reverse.md](workflows/workflows-reverse.md) | 全量 | workflows-forward.md, prompts-forward.md |
| PRD 模板填充 | `templates.md`（templates-prd.md） | 全量 | workflows/, prompts/ |
| 技术设计模板填充 | `templates.md`（templates-tech-design-part1/2.md） | 全量 | workflows/, prompts/ |
| Agent 提示词 / 质量门禁 | `prompts.md`（对应 forward/reverse） | 按场景定位 | workflows/, templates/ |
| Phase 拆分 / Agent 角色 / 输出规范 | [references/complexity-rules.md](references/complexity-rules.md) | 按需定位 | workflows/, templates/, prompts/ |
| 遇到需求模糊时 | `shared-rules/inquiry-protocol.md` | 全量 | workflows/, templates/, prompts/ |

---

## 预思考（强制，设计启动前执行）

开始设计前，**必须**执行 cc-think-first 预思考协议（`shared-rules/skill-orchestration.md` 第七章 预思考协议）。

**design 专用 L0 条件**（在 protocol 通用 L0 基础上收紧）：
- **L0 跳过**：来自 planner 的委托且需求上下文已充分 **或** 逆向文档生成（输入是现有代码，无决策空间）
- **至少 L1**：用户直接请求设计文档（需确认需求边界和约束）
- **至少 L2**：涉及架构决策、多方案权衡、跨模块设计

输出 `Think-First L{0|1|2} {级别名}` 到控制台，L1/L2 完成后才可进入设计流程。

---

## 核心能力

| 能力 | 输入 | 输出 | 场景 |
|------|------|------|------|
| 设计文档生成 | 需求描述 | 技术设计文档 | 新功能开发、架构设计 |
| 重构方案设计 | 现有代码 + 重构目标 | 重构技术方案 | 系统重构、架构升级 |
| 逆向文档生成 | 现有代码 | PRD + 技术文档 | 遗留系统文档化 |

### 复杂度分级摘要

> 详细 Phase 拆分、Agent 角色、输出规范见 [references/complexity-rules.md](references/complexity-rules.md)

| 级别 | Phase 数 | 说明 |
|------|---------|------|
| 大型 | 6 | 完整流程：复杂度分析 -> PRD -> 技术设计 -> 图表 -> 审查 -> 输出验证 |
| 中型 | 4 | 跳过 PRD 和独立审查，审查合并到技术设计阶段 |
| 小型 | - | Phase 1 判断后退出，建议用 planner 或 code-writer |

> 复杂度分级标准及 Skill 推荐见 `shared-rules/skill-quality.md`
> 详细工作流文件见上方"资源加载指导"表（workflows/workflows-forward.md 正向、workflows/workflows-reverse.md 逆向）

---

## 强制任务跟踪

- 设计开始前必须 `TaskCreate` 创建所有 Phase 任务（Phase 拆分表见 [references/complexity-rules.md](references/complexity-rules.md)）
- 每个 Phase 开始/完成时必须 `TaskUpdate`
- 所有 Phase 完成后输出汇总报告
- 所有文档必须包含「快速熟悉」章节，遵循 [templates.md](templates.md) 文档表达原则
- Agent 派发强制配置：`model: opus` + `effort: max`

---

## 设计 vs 规划 决策树

> 易混淆场景速查及边界定义见 `shared-rules/skill-orchestration.md` 第一章

---

## 最佳实践

**设计文档**：先确定复杂度避免过度设计；大型任务必须先写 PRD；覆盖异常场景；预留扩展点。

**逆向文档**：从入口点开始分析（Controller）；标记所有推断内容；生成待确认列表；与业务方确认后定稿。

---

## Gotchas

> 从实际使用中积累的常见陷阱。每次发现新问题时追加。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 跳过 planner 直接到 code-writer | 设计文档未经任务拆解直接实现，遗漏**异常分支/幂等性/回滚路径**等 planner DESIGN-REVIEW 门控关注项 | design -> planner -> code-writer，禁止跳过 planner |
| 2 | 小型任务仍走完整 6 Phase | 过度设计消耗大量 token | Phase 1 判断为小型后退出，建议用 planner 或 code-writer |
| 3 | 逆向文档中推断内容未标记 + 无 quote grounding | 用户无法区分确认事实和推断假设；frontmatter 声明 `report_protocol_mode: full` 但实际无 `<quote>` 引用 = 运行时漂移 | 所有推断内容附 `[推断] + <quote file="..." line="...">原文</quote>`；无 quote 支持的改 `[REMOVED:no-quote]` 并移入待确认清单（详见 workflows-reverse.md 顶部"Quote Grounding 三件套"） |
| 4 | 设计文档未写入 vault 正确目录 | 文档散落在项目中，无法被 vault 检索协议发现 | 按全局 CLAUDE.md 的文档写入规则输出到 vault 对应目录 |
| 5 | 设计文档缺少「快速熟悉」章节 | 新人无法快速理解模块，vault L1 检索无法命中 | 所有文档必须包含「快速熟悉」章节（见 templates.md） |
| 6 | 设计文档与实际代码长期不同步 | 文档变成误导性信息，比没有文档更有害 | 设计文档标注版本和适用范围，重大代码变更时提醒更新文档 |

