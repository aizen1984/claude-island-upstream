---
name: cc-code-writer
description: 派发subagent编写代码并执行统一审查（P0-P1阻断+P2+建议）。不做任务规划、不做批量并行。用于功能开发、Bug修复、重构
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, Agent
paths: "**/*.java, **/*.js, **/*.ts, **/*.py"
---

## Gotchas

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | subagent 不继承对话历史 | 缺失上下文导致生成无关代码 | prompt 中传递完整需求描述、文件路径、相关代码片段 |
| 2 | 多 subagent 并发写同一文件 | 后写覆盖先写，丢失变更 | 文件冲突检测：同一文件不得分配给多个并发 subagent |
| 3 | 审查重试超 3 次仍失败 | 陷入无限修复循环 | 重试上限 3 次，超过后停止并报告用户 |
| 4 | 照着已有接口直接 implements 抄管道 | 80% 相同管道被完整复制 | 共性 > 50% 必须先提取基类/共享管道 |
| 5 | TDD 联动时会话文件未清理 | `.claude/tdd-session-active` 残留 | TDD 完成后删除，work-mode SUMMARIZE 兜底 |
| 6 | subagent 代码风格与项目不一致 | 命名/结构差异明显 | Implementer prompt 必须嵌入 CONVENTIONS 字段 |
| 7 | 审查不通过时降级为 Fix Loop | 应走 Strategy Evolution 积累改进 | 默认 Strategy Evolution；仅纯局部 bug 或 `--fix-only` 时降级 |

# 数禾代码编写 Agent

> 基于 subagent-driven-development 模式的符合数禾规范的代码编写工作流

## Overview

采用 subagent-driven-development 模式的代码实现引擎：多子 agent 并发执行独立任务，内置统一审查（P0-P1 阻断 + P2+ 建议）。

---

## When to Use

**适用场景**：新功能开发、Bug 修复、重构、TDD（任务数 < 5 的编码任务）

## When Not to Use

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 任务数 >= 5 且已明确 | cc-work-mode | work-mode 支持 10 并发，批量执行效率更高 |
| 需要先规划再实现 | cc-planner | 本 Skill 直接编码，不做完整任务拆解 |
| 仅做代码审查 | cc-code-reviewer | 本 Skill 写代码，审查应由 reviewer 负责 |

---

## 协作关系

- **接收自**: user、cc-planner
- **内置审查**: 统一审查（Unified Reviewer，P0-P5 全维度）通过 subagent 执行，遵循 `cc-code-reviewer` Skill 的**规则**但**不走其 Skill 激活路径**（即本 Skill 不会作为调用方触发 code-reviewer Skill 激活）。独立调用 cc-code-reviewer Skill 的场景：用户主动请求独立审查、cc-work-mode SUMMARIZE 阶段——详见 `cc-code-reviewer/SKILL.md` "接收自/规则被引用" 段
- **联动**: cc-tdd（TDD 模式时引用其规则和 test_first 决策表）
- **隐式依赖**: cc-java-backend（必须预加载）
- **禁止嵌套**: code-writer 的 subagent 不可再调用 code-writer，subagent 直接编写代码

> 详细协作矩阵见 `shared-rules/skill-orchestration.md` 第二章，数据契约见 `shared-rules/data-contracts.md`

---

## 资源加载指导

| 条件 | 加载文件 | 读取范围 | 不加载 |
|------|---------|---------|--------|
| 首次激活（模式判断） | [resources.md](resources.md) 第一~三章 | 全量 | workflows.md, prompts.md |
| Bug Fix 场景 | [workflows.md](workflows.md) 第 1-B 章（Bug Fix 通道） | 按子章节定位 | resources.md 第二~三章, prompts.md |
| 需求分析 / 任务执行 / 并发执行 | [workflows.md](workflows.md) 第一~三章 | 按章节定位 | prompts.md |
| 审查失败 / TDD 流程 | [workflows.md](workflows.md) 第四~五章 | 按章节定位 | resources.md, prompts.md |
| 派发 Implementer subagent | [prompts.md](prompts.md) 第一章 | 按章节定位 | resources.md, workflows.md |
| 派发 Unified Reviewer | [prompts.md](prompts.md) 第二章 | 按章节定位 | resources.md, workflows.md |
| 审查进入 evolution loop | `shared-rules/evolution-loop-protocol.md` | 全量 | resources.md |
| Subagent 预算约束 | `shared-rules/subagent-budget.md` | 全量 | - |
| 遇到需求模糊时 | `shared-rules/inquiry-protocol.md` | 全量 | workflows.md, prompts.md, resources.md |
| 任务开始前预思考 | `shared-rules/skill-orchestration.md` 第七章 预思考协议 | 全量 | workflows.md, prompts.md, resources.md |

---

## 预思考（强制，任务开始前执行）

接到任务后、派发 subagent 前，**必须**执行 cc-think-first 预思考协议（`shared-rules/skill-orchestration.md` 第七章）。

**code-writer 专用 L0 条件**：
- **L0 跳过**：任务来自 planner/cc-work-mode 且已原子化，或用户明确说"直接改"/"直接做"
- **至少 L1**：用户直接下达的编码任务（即使是"单文件修改"），除非用户用了跳过词

输出 `Think-First L{0|1|2} {级别名}` 到控制台。

---

## 核心原则

| # | 原则 | 要点 | 详情 |
|---|------|------|------|
| 1 | Fresh Subagent Per Task | 每个任务使用全新子 agent，完成后销毁，避免上下文污染 | - |
| 2 | Unified Review | P0-P1 高置信度阻断必须修复；P2+ 建议记录不阻断 | `shared-rules/skill-quality.md` |
| 3 | SOLID 设计预检 | 新建类/接口时：职责单一？扩展需改代码？能 Mock 测试？ | - |
| 4 | TDD Discipline（默认开启） | 先写失败测试 -> 最小实现 -> 测试通过 -> 重构。仅用户显式跳过或纯数据类(DTO/Config/Entity)豁免 | `cc-tdd/SKILL.md` |
| 5 | Ask Before Guess | 遇到不明确需求先询问用户，不猜测 | `shared-rules/inquiry-protocol.md` |
| 6 | Parallel When Possible | 独立任务并发，有依赖任务顺序执行 | [workflows.md](workflows.md) 第三章 |
| 7 | Incremental Commit | 每组完成且审查通过后自动保存点提交 | [workflows.md](workflows.md) 第三章步骤 2.6 |
| 8 | Subagent Context Contract | 派发时必须填充上下文合约（working_directory/project_structure/existing_patterns/dependencies/conventions），禁止仅传任务描述 | [prompts.md](prompts.md) 第一章 |
| 9 | Failure Rollback | 编译失败修复当前任务；审查失败最多重试 3 次；超过后回退保存点+报告用户；P2+ 不重试 | [workflows.md](workflows.md) 第四章 |

**TDD 生命周期**：code-writer 负责创建和销毁 `.claude/tdd-session-active`；tdd-guard.js Hook 仅检查和提醒（additionalContext）。编排流程见 [workflows.md](workflows.md) **第二章** 步骤 1.5（RED，Lead 创建）→ 2.5（GREEN）→ 4.5（REFACTOR）。注意：第三章并发工作流中也有"步骤 1.5：文件冲突检测"——非 TDD 语义，勿混淆。

---

## 使用模式

| 模式 | 触发条件 | 执行流程 |
|------|---------|---------|
| **A: 独立使用** | 用户直接请求 | requirement-analysis -> task-execution |
| **B: Planner 调用** | 已拆解的任务清单 | 跳过分析 -> 直接执行 |

> 模式判断详情见 [resources.md](resources.md) 第一章

---

## 子 Agent 调度

| Subagent | 执行顺序 | 提示词 |
|----------|---------|--------|
| Implementer | 1.实现任务 | [prompts.md](prompts.md) 第一章 |
| Unified Reviewer | 2.实现后（P0-P5 全维度统一审查） | [prompts.md](prompts.md) 第二章 |

> 派发时必须填充上下文合约（原则 8），禁止仅传任务描述。

