---
name: cc-eval
description: 执行Skill自动化评估（三层检查+LLM评分+自动修复闭环）。不修改评分标准和测试用例。用于Skill质量验证、回归测试、自动迭代优化
disable-model-invocation: true
argument-hint: [skill 名称或 'all']
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Agent
  - Grep
  - Glob
report_generation: true
report_protocol: data-report-protocol
report_protocol_mode: full
---

> **Report Generation 声明**（data-report-protocol Iter 22）：本 skill Layer 2 的 Grader Agent 生成评分报告 + 改进建议，每条改进建议必须以 `<quote file="..." line="...">原文</quote>` 引用被评估 skill 的具体原文（避免"建议优化但找不到位置"的空洞建议）。Grader 评分本身（数字）不需要 quote，但**附带的改进建议**必须 quote 锚定。fixer 阶段读取建议时也校验 quote 存在。

# Skill 自动化评估器

## Overview

三层递进式评估：Layer 1 确定性脚本检查（0 token）→ Layer 2 LLM-as-Judge 自动评分 → Layer 3 自动修复闭环。支持 CLI 和 Skill 双入口，共享 `eval/` 数据层。

基于 Anthropic [Harness design for long-running apps](https://www.anthropic.com/engineering/harness-design-long-running-apps) 的 Generator-Evaluator 模式。

---

## When to Use

| 使用场景 | 示例 |
|---------|------|
| Skill 变更后质量验证 | "检查一下 reviewer 的 skill 质量" |
| 批量回归测试 | "跑一下全部 skill 的评估" |
| 自动迭代优化 | "帮我自动优化 reviewer 的 SKILL.md" |

**不适用场景**：

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 创建新 Skill | cc-skill-creator | 本 Skill 评估已有 Skill，不创建新的 |
| 代码审查 | cc-code-reviewer | 本 Skill 评估 Skill 定义质量，不审查业务代码 |
| 修改评分标准 | 手动编辑 eval/rubrics/ | 评分标准不可由评估器自身修改 |

---

## 三层架构

> **Step 级执行流程详见 [workflows.md](workflows.md)**（Step 0 初始化 → Step 1 Layer 1 → Step 2 Executor+Grader → Step 3 Fixer 闭环 → 报告生成 + 快捷模式）。本段只给入口概述。

### Layer 1: 确定性检查（bash 脚本，0 token）

```bash
bash eval/run.sh <skill-name>           # 只跑 Layer 1
bash eval/run.sh --all                  # 全部 Skill Layer 1
```

串行执行 `eval/scripts/layer1-all.sh`，包含 9 个通用检查 + 8 个 Hook 行为测试。输出 JSON 报告。**Layer 1 全部 PASS 才进入 Layer 2。**

### Layer 2: LLM-as-Judge（Claude 评分）

```bash
bash eval/run.sh <skill-name> --evaluate   # Layer 1 + 2
/cc-eval <skill-name>                         # Skill 入口默认 L1+L2
```

三角色分离：
- **Executor Agent**: 用 golden-set prompt 触发 Skill，收集输出
- **Grader Agent（独立上下文）**: 用领域化 rubric 评分，生成改进建议
- **Reporter**: 聚合分数，生成 JSON + MD 报告

### Layer 3: 自动修复闭环

```bash
bash eval/run.sh <skill-name> --auto-fix   # 深度闭环
/cc-eval <skill-name> --auto-fix
```

循环逻辑：评估 → 取 P0/P1 建议 → Fixer Agent 修改 → 重跑 L1（安全检查） → 重跑 L2（评分） → 收敛/退出。

**退出条件**（任一即退出）：
1. 分数 ≥ 阈值（默认 0.90）
2. 达到 max_rounds（默认 5）
3. 连续 2 轮分数提升 < 2%
4. L1 失败（结构被改坏，自动回滚）
5. 无可操作的改进建议

---

## Fixer 安全约束

| 约束 | 值 |
|------|---|
| 可修改文件 | `.claude/skills/*/SKILL.md`, `*/workflows/*.md`, `*/prompts*.md`, `*/checklists*.md`, `*/references/*.md`, `shared-rules/*.md` |
| 禁止修改 | `.claude/settings.json`, `skill-rules.json`, `eval/golden-sets/*`, `eval/rubrics/*` |
| 单轮修改上限 | ≤ 3 个文件 |
| L1 回滚 | 修改后 L1 失败自动 git checkout |

---

## 领域化 Rubric

| Skill 类型 | Rubric 文件 | 核心维度 |
|-----------|------------|---------|
| 工具类（sql/cc-cfg/cc-diagram/cc-skill-creator） | `eval/rubrics/domain/tool-skills.yaml` | correctness(0.5) + format(0.3) + efficiency(0.2) |
| 内容生成类（reviewer/cc-code-writer/cc-design/cc-tdd/java-backend） | `eval/rubrics/domain/content-skills.yaml` | 按 Skill 细化（如 reviewer: 检出率+误报率+可操作性+优先级） |
| 流程编排类（planner/cc-work-mode） | `eval/rubrics/domain/workflow-skills.yaml` | phase_completeness + task_granularity + contract_compliance + file_hygiene |

---

## 配置

全局配置见 `eval/config.yaml`。核心参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| layer1.fail_fast | true | L1 失败不进 L2 |
| layer2.pass_threshold | 0.90 | 通过分数线 |
| layer3.max_rounds | 5 | 最大闭环轮次 |
| layer3.convergence_threshold | 0.02 | 收敛判断（提升<2%） |
| layer3.no_improvement_exit | 2 | 连续无改善退出轮次 |

---

## 报告输出

| 格式 | 路径 | 用途 |
|------|------|------|
| JSON | `eval/reports/{date}-{skill}-eval.json` | 机读、前端预留 |
| Markdown | `eval/reports/{date}-{skill}-eval.md` | 人读 |

报告 schema 详见 `eval/templates/skill-audit-report.md.tpl` 模板，以及实际产出 `eval/reports/{date}-{skill}-eval.md`。

---

## Agent 派发配置（强制）

| Agent | model | 独立上下文 | 说明 |
|-------|-------|:---------:|------|
| Executor | sonnet | 是 | 执行 golden-set，收集输出 |
| Grader | opus | **是（强制）** | 独立评分，不看执行过程 |
| Fixer | opus | 是 | 应用修复建议 |

---

## Gotchas

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | Fixer 修改了 golden-set 或 rubric | 被测对象篡改评分标准，评估失效 | golden-set 和 rubric 为只读，deny_modify_patterns 保护 |
| 2 | Grader 与 Executor 共享上下文 | 评分过于乐观（文章核心教训） | Grader 必须用独立 Agent（不共享执行过程） |
| 3 | auto-fix 死循环消耗大量 token | 无限制修复-重评 | max_rounds=5 + 收敛检测 + no_improvement 退出 |
| 4 | Layer 1 失败后继续 Layer 2 | 结构性问题上跑 LLM 评估浪费 token | Layer 1 全部 PASS 才进入 Layer 2 |
