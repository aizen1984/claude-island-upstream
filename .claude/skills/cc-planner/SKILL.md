---
name: cc-planner
description: 按RIPER五阶段拆解任务并生成可执行计划，支持设计评审门控、三层分解和迭代循环模式（Evaluator-Optimizer Loop）。不直接写代码。用于复杂任务拆解、多步骤开发规划、持续迭代优化
argument-hint: [任务描述或 PRD/设计文档路径]
effort: high
allowed-tools: Read, Grep, Glob, Write, Edit, Agent, WebSearch, WebFetch
---

## Gotchas

> 从实际使用中积累的常见陷阱。每次发现新问题时追加。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | plan.md 与 Task 状态不同步 | 执行偏离计划 | 以 plan.md 为唯一真实来源，Task 仅用于并行 agent 派发 |
| 2 | RIPER 阶段并行执行 | 跳过必要的分析/评审步骤 | 严格按 RESEARCH → PLAN → EXECUTE → REVIEW 顺序（INQUIRE 已融入 RESEARCH 作为可选微询问） |
| 3 | 未经用户确认就进入 EXECUTE | 执行错误的计划浪费大量 token | PLAN 完成后必须等用户确认才能进入 EXECUTE |
| 4 | 忘记 resolve workspace 直接读项目根 plan.md | 覆盖其他会话文件 | 操作五文件前先 echo $STARK_SESSION_DIR 确认路径 |
| 5 | ralph 完成后直接退出未进入 REVIEW | 代码质量审查缺失，AC 未验收 | EXECUTE 使用策略 4（设置 LIFECYCLE_MODE=planner-execute），通过 handoff 信号自动触发 REVIEW |
| 6 | 设计文档驱动 RESEARCH 完成后未更新 session.yaml | PLAN 无法识别已走过设计文档驱动路径，误触发 DESIGN 子阶段（重复设计） | Step 4 写入 vault 后立即更新 session.yaml：`research_path: design-doc-driven` + `design_review_status: skipped` |
| 7 | compact 后五文件路径丢失 | 执行偏离计划，读写错误文件 | 依赖 post-compact-inject.js 自动恢复；手动时先 `echo $STARK_SESSION_DIR` 确认路径 |
| 8 | 长任务 R+I+P 上下文影响 EXECUTE 质量 | 仅策略 1（主 agent 直接执行）受影响，策略 2-4 的 subagent 天然隔离 | 策略 2-4 无需干预（subagent = fresh context）；策略 1 仅用于小任务，上下文有限；auto-compaction + post-compact-inject 自动处理主 agent 上下文 |
| 9 | 迭代模式 EVALUATE 偏差检测（L1）误以为每轮都触发 | 不必要的审计 subagent 成本 | L1 仅在 L0 规则告警时触发（预计 <20% 轮次）；R2 有 2 轮冷却期；goal.md 可配置阈值和关闭 |

# 数禾工作计划工作流

## Overview

cc-planner 是一个专注于**任务规划和执行**的工作流 Skill。采用 RIPER 五阶段隔离模式（研究→询问→规划→执行→审查），中型/大型任务在 PLAN→EXECUTE 之间自动插入 DESIGN + DESIGN-REVIEW 可选子阶段，结合五文件持久化和文件驱动执行，确保复杂任务的可控执行。

**核心价值**：阶段隔离 | 2-5 分钟任务粒度 | 跨会话持久化 | 证据驱动 | 并行分析（最多 10 并发）

---

## 阶段门控检查（最高优先级）

> **5 个核心门控点，每个必须通过才能继续。** 精简自原 8 个，聚焦关键决策。

| # | 门控点 | 检查项 | 验证方式 | 未通过后果 |
|---|--------|--------|---------|-----------|
| G1 | RESEARCH 完成 | findings.md 已写入且质量达标 | **标准路径**: 文件存在 + ≥3 发现 + ≥1 代码路径引用 / **设计文档驱动**: findings.md 存在 + 含对抗验证综合结果 + 改动设计文档已写入 vault | 返回 RESEARCH |
| G2 | PLAN 完成 | plan.md 已写入（含任务表 + 依赖图） | 文件存在 + 任务数 ≥ 1 | 返回 PLAN |
| G3 | 用户确认 | 用户明确确认计划 + 复杂度评估 | 用户回复含确认意图 | 等待用户 |
| G4 | DESIGN 完成（仅中/大型） | 设计文档已生成 | `doc/cc-design/` 非空 | 返回 DESIGN |
| G5 | 评审通过（仅中/大型） | 对抗验证已完成 + 用户评审通过 | 用户回复 ✅ | 返回修改 |

> **小型任务**（≤3 任务/≤50 LOC）：仅需 G1→G2→G3→直接 EXECUTE，跳过 G4/G5。
> **EXECUTE → REVIEW**：progress.md 已更新即可进入，不设独立门控（属于流程常识）。

**禁止行为**：
- plan.md 未写完或未经用户确认就进入 EXECUTE
- RESEARCH 不产出 findings.md 就跳到 PLAN
- 中型/大型任务跳过 DESIGN 直接 EXECUTE（**设计文档驱动路径除外**——该路径在 RESEARCH 阶段已完成设计验证和对抗确认）

---

## When to Use

**适用场景**：复杂任务拆解 | 多步骤开发规划 | 跨会话持久化 | 复杂依赖梳理

## When Not to Use

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 设计文档（PRD、技术方案） | cc-design | 本 Skill 产出任务清单，不产出设计文档 |
| 单文件简单修改 | cc-code-writer | 无需完整 RIPER 五阶段规划 |
| 批量并行执行已规划任务 | cc-work-mode | 任务已明确时直接用 work-mode 执行 |

**INQUIRE 跳过标准**：INQUIRE 跳过判断遵循 `shared-rules/inquiry-protocol.md` 的三步决策（快速通道→红线→置信度），不再使用独立条件

> **INQUIRE 轻量化**：INQUIRE 不再作为独立阶段硬卡点。改为 RESEARCH 阶段内的可选微询问——仅在 inquiry-protocol.md 红线命中时才中断流程等待用户确认。其他情况下 RESEARCH → PLAN 直通。

---

## RIPER 触发标准 & 轻量快速通道

> 详见 [workflows/workflows-lightweight-fasttrack.md](workflows/workflows-lightweight-fasttrack.md)（含 2 步快判流程图 + Bug Fix 快速通道 + 小型任务轻量流程）

---

## 预思考（强制，RESEARCH 阶段第一步）

进入 RESEARCH 阶段时，**必须**先执行 cc-think-first 预思考协议（`shared-rules/skill-orchestration.md` §七 预思考协议）。

**planner 专用规则**：
- **⛔ 意图确认（L1/L2 首问，在五问之前）**：用一句话复述"用户想要什么结果"。如果复述后发现有歧义（如"测试"可以指运行测试脚本、也可以指用真实场景验证），**必须在 RESEARCH 开始前向用户确认**，不要假设最容易执行的含义。
- **L0 跳过**：仅 Bug Fix 快速通道（有明确报错+复现步骤+修复范围可预判）
- **级别由 cc-think-first 自动判定**：planner 场景通常 L1（中等）或 L2（3+ 文件/架构决策）。L0 仅 Bug Fix 快速通道
- **L2 复用**：五步分析输出直接作为 findings.md 初始内容（Step 1→问题定义，Step 2→约束，Step 4→风险），RESEARCH 在此基础上补充代码路径等细节，**不重复分析**
- **L1 复用**：四问输出作为 findings.md 的"快速预判"章节，RESEARCH 从此出发展开

输出 `🧠 Think-First L{0|1|2} {级别名}` 到控制台。

---

## 协作关系

- **接收自**: user（直接请求规划）、cc-design（设计完成后拆解任务）
- **委托给**: cc-design（中型/大型）、cc-work-mode（任务>=5）、cc-code-writer（任务<5）、自身（分析型>=2，10并发）
- **隐式依赖**: cc-java-backend（Java 相关任务自动加载规范）

> 详细协作矩阵见 `shared-rules/skill-orchestration.md` 第二章，数据契约见 `shared-rules/data-contracts.md`

---

## 资源加载指导

### 阶段资源（按当前阶段加载对应行）

| 阶段 | 加载文件 | 读取范围 | 不加载 |
|------|---------|---------|--------|
| RESEARCH | SKILL.md + [workflows/workflows-research-inquire.md](workflows/workflows-research-inquire.md) | 全量 | workflows-plan.md, workflows-execute-review.md, workflows-lightweight-fasttrack.md, prompts.md, templates/ |
| RESEARCH（设计文档驱动） | [workflows/workflows-research-inquire.md](workflows/workflows-research-inquire.md) + [templates/templates-change-design.md](templates/templates-change-design.md) | 全量 | workflows-plan.md, workflows-execute-review.md, prompts.md |
| INQUIRE | SKILL.md + `shared-rules/inquiry-protocol.md` | 全量 | workflows/, prompts.md, templates/ |
| PLAN | [workflows/workflows-plan.md](workflows/workflows-plan.md) + `templates.md` | 全量 | workflows-research-inquire.md, workflows-execute-review.md, prompts.md |
| EXECUTE | [workflows/workflows-execute-review.md](workflows/workflows-execute-review.md) + [prompts.md](prompts.md) | 全量 | workflows-research-inquire.md, workflows-plan.md, templates/ |
| REVIEW | [workflows/workflows-execute-review.md](workflows/workflows-execute-review.md)（review 章节） | 按标题定位 | workflows-research-inquire.md, workflows-plan.md, prompts.md |
| EVALUATE | [workflows/workflows-evaluate.md](workflows/workflows-evaluate.md) | 全量 | workflows-research-inquire.md, workflows-plan.md, prompts.md |
| 触发标准判断 | [workflows/workflows-lightweight-fasttrack.md](workflows/workflows-lightweight-fasttrack.md) | 全量 | 其他 workflows, templates/ |

### 按需资源（触发条件满足时加载）

| 触发条件 | 加载文件 |
|---------|---------|
| 会话恢复（检测到已有五文件） | `prompts.md` session-recovery 章节 |
| Spec/BugFix-Spec 编写 | `templates.md` → `templates/templates-spec.md` |
| 并行分析（≥2 独立分析任务） | `prompts.md` Anti-Pattern 章节 |
| 需求模糊 | `shared-rules/inquiry-protocol.md` |
| RESEARCH 前预思考 | `shared-rules/skill-orchestration.md` §七 预思考协议 |
| 对抗验证 | `shared-rules/adversarial-verification.md` |
| Sprint Contract 协商（PLAN Step 5，任务数 > 8） | `prompts.md` contract-negotiation-reviewer 章节 |
| 迭代循环模式激活 | `workflows/workflows-evaluate.md` + `templates/templates-goal.md` |

---

## 核心理念

1. **阶段隔离**：每个阶段有明确的权限边界
2. **理解优先**：先理解代码，再编写代码
3. **计划粒度**：任务拆分到 2-5 分钟可完成的单元
4. **五文件持久化**：spec.md / plan.md / progress.md / findings.md / session.yaml
5. **证据驱动验证**：不接受"应该修复了"，必须看到测试输出
6. **文件驱动执行**：plan.md 为唯一执行状态源，Agent 工具仅用于并行 agent 派发
7. **假设可退出**：每个 harness 机制编码一个模型能力假设，详见 [harness-assumptions.md](harness-assumptions.md)

| 文件数 | 任务拆分详细程度 |
|--------|---------|
| 1-2 | 简单描述 |
| 3-5 | +文件路径 +代码骨架 |
| 5+ | +三层分解 +依赖图 |

---

## 文件驱动执行

> 详细规则见 `shared-rules/task-tracking-rules.md`（模式 B：文件驱动）

执行循环（plan.md 为唯一状态源）：

1. **⛔ 首步强制**：`echo $STARK_SESSION_DIR` 确认路径（为空则报错停止）。Read spec.md 目标 + plan.md 首个 ⬜ 任务
2. 执行任务（⬜ → 🔄），验证通过后更新（🔄 → ✅）
3. 每完成 3 个任务追加 progress.md
4. 循环直到所有任务 ✅

**Agent 工具使用**（仅限并行）：分析型 ≥2 独立任务 → Agent 派发 | 对抗验证 → Agent 派发 | 其他一律不用

---

## 五文件持久化

| 文件 | 职责 | 写入时机 |
|------|------|---------|
| `spec.md` | 需求/验收标准（What/Why） | PLAN 写入，REVIEW 勾选 AC |
| `plan.md` | 任务计划 + 执行状态（唯一状态源） | PLAN 写入，EXECUTE 实时更新 |
| `progress.md` | 执行日志、会话断点 | 每完成 3 个任务追加 |
| `findings.md` | 研究发现、决策记录 | RESEARCH 阶段 |
| `session.yaml` | 会话元数据 | 阶段切换时 |

**文件位置**: `$STARK_SESSION_DIR`（详见 `shared-rules/session-workspace.md`）。**⛔ 未设置时报错停止，禁止 fallback 到项目根**。

**更新策略**: plan.md 每任务实时更新 | progress.md 每 3 任务批量追加 | session.yaml 阶段切换/会话结束/REPLAN 时 | **强制完整同步**: 阶段切换、任务阻塞、会话即将结束

> 模板详见 `templates.md`

---

## 会话自动检测

> 详见 `prompts.md`（session-recovery 章节）

---

## 输出数据契约

> 数据契约的唯一定义见 `shared-rules/data-contracts.md`。本 Skill 不重复定义字段，仅说明使用方式。

### 传递行为

| 目标 Skill | 触发条件 | 跳过阶段 | 附加参数 |
|-----------|---------|---------|---------|
| cc-code-writer | 任务数 < 5 | skip_analysis: true | - |
| cc-work-mode | 任务数 >= 5 | skip_phases: ["ANALYZE", "PLAN"] | parallel_limit: 10 |

---

## 迭代循环模式（Evaluator-Optimizer Loop）

> 在单向 RIPER 外层包裹迭代循环。激活条件：用户表达"持续改进直到..."或 RESEARCH 判断适合迭代。
> 完整概述（激活条件、阶段流转、门控 G6、设计决策）见 [workflows/workflows-evaluate.md](workflows/workflows-evaluate.md)。

---

## 与其他 Skill 协作

> 详见 `shared-rules/skill-orchestration.md` 第一章（激活优先级与冲突解决）和第二章（边界决策表）
