---
name: cc-skill-creator
description: 创建或更新Skill的元工具，提供设计原则、目录模板、一致性校验脚本。不执行其他Skill、不做业务开发。用于新建Skill、Skill结构重构、frontmatter规范检查
disable-model-invocation: true
argument-hint: [新 skill 名称或 --validate <skill>]
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
paths: "**/.claude/skills/**"
---

# Skill Creator

创建和更新 Skill 的元工具。

## 设计原则速览

- **简洁至上**：Claude 已经很聪明，只提供它不知道的信息
- **渐进式披露**：L0 metadata -> L1 SKILL.md body(<=500行) -> L2 bundled resources
- **自由度匹配**：脆弱操作用脚本（低自由度），启发式任务用文本指令（高自由度）

> 完整设计原则、Skill 结构、Progressive Disclosure 模式见 [references/skill-design-guide.md](references/skill-design-guide.md)

## 资源加载指导

| 场景 | 加载文件 | 读取范围 | 不加载 |
|------|---------|---------|--------|
| 创建新 Skill 时 | [references/templates.md](references/templates.md) | 全量（模板+目录结构+质量清单） | skill-design-guide.md, check_consistency.py |
| 需要设计原则参考时 | [references/skill-design-guide.md](references/skill-design-guide.md) | 全量（渐进式披露+自由度匹配） | templates.md, check_consistency.py |
| 执行完整创建流程时 | [workflows/create-workflow.md](workflows/create-workflow.md) | 全量（6 步流程+命名+CSO 规则） | check_consistency.py |
| 注册/校验阶段 | [references/registration-checklist.md](references/registration-checklist.md) | 全量（字段规范+协作矩阵更新） | templates.md, skill-design-guide.md |
| 检查跨文件一致性时 | [scripts/check_consistency.py](scripts/check_consistency.py) | 全量 | templates.md, skill-design-guide.md |
| **报告运行时校验**（quote grounding + under-report） | [scripts/verify_report_runtime.py](scripts/verify_report_runtime.py) | 按需 (Iter 23 新增) | templates.md, skill-design-guide.md |
| Skill 治理（Subagent 预算/对抗验证）时 | `shared-rules/subagent-budget.md` + `shared-rules/adversarial-verification.md` | 全量 | references/, scripts/, workflows/ |
| 遇到需求模糊时 | `shared-rules/inquiry-protocol.md` | 全量 | references/, scripts/, workflows/ |

> **元工具防线总览**：
> - L1 静态: `quick_validate.py`（单 skill frontmatter + CSO + naming）
> - L2 静态: `check_consistency.py`（跨 skill 10 规则）
> - L3 运行时: `verify_report_runtime.py`（agent 报告 quote grounding + under-report 检测）
>
> 三层互补：L1/L2 拦截"修复成果 regression"，L3 拦截"新报告 AP3/AP4 失真"。详见 `shared-rules/data-report-protocol.md`。

## 不适用场景

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 写业务代码/实现功能 | cc-code-writer | 本 Skill 只创建/管理 Skill 结构 |
| 执行已有 Skill | 对应 Skill | 本 Skill 是元工具，不执行其他 Skill |
| 代码审查 | cc-code-reviewer | 本 Skill 不做代码级审查 |

---

## 协作关系

- **接收自**: user（直接请求创建/更新 Skill）
- **内联引用**: cc-think-first（创建/重构前预思考，L1-L2）
- **注册更新**: skill-rules.json（激活规则）、skill-orchestration.md（协作矩阵）
- **无委托给**: 本 Skill 是终端元工具，不委托其他 Skill

> 详细协作矩阵见 `shared-rules/skill-orchestration.md` 第二章

---

## 数据契约

### 输入（最低要求）

| 字段 | 必须 | 说明 |
|------|------|------|
| Skill 名称/意图 | Y | 用户描述的 Skill 用途或名称 |
| 使用示例 | 推荐 | 至少 1 个触发场景示例 |
| MCP/外部依赖 | 可选 | 是否需要外部工具（影响 allowed-tools） |

### 输出（产出物清单）

创建/更新 Skill 后，以下文件必须被变更：

| 文件 | 操作 | 说明 |
|------|------|------|
| `{skill-name}/SKILL.md` | 创建/更新 | Skill 主文件（frontmatter + body） |
| `skill-rules.json` | 更新 | 添加/修改激活规则条目 |
| `shared-rules/skill-orchestration.md` | 更新 | 协作矩阵添加新 Skill 行（如有协作） |
| `{skill-name}/` 子文件 | 按需 | workflows/ / references/ / scripts/ |

> 完整字段定义见 `shared-rules/data-contracts.md`

---

## 预思考（强制，创建/重构前执行）

创建新 Skill 或重构现有 Skill 前，**必须**执行 cc-think-first 预思考协议（`shared-rules/skill-orchestration.md` 第七章 预思考协议）。

**cc-skill-creator 专用 L0 条件**（在 protocol 通用 L0 基础上收紧）：
- **L0 跳过**：小幅更新（改描述文本、修 typo、调整资源表）**或**用户说"直接改"
- **至少 L1**：新建 Skill（需确认边界和协作关系）
- **至少 L2**：涉及协作矩阵变更、shared-rules 修改、Skill 合并/拆分

---

## Skill 创建流程（摘要）

> 完整流程详见 [workflows/create-workflow.md](workflows/create-workflow.md)

| 步骤 | 目标 |
|------|------|
| 1. 理解 | 收集具体使用场景和触发示例 |
| 2. 规划 | 识别可复用资源（脚本、引用、资产），判断是否需领域知识注入 |
| 3. 初始化 | 运行 `init_skill.py` 创建目录和模板 |
| 4. 编辑 | 实现资源文件，编写 SKILL.md（frontmatter 遵守 CSO 规则） |
| 5. 验证注册 | 运行 `quick_validate.py`，注册到 [skill-rules.json + 协作矩阵](references/registration-checklist.md) |
| 6. 迭代 | 真实使用后持续改进 |

按顺序执行，仅在有明确理由时跳过。

---

## Gotchas

> 从实际使用中积累的常见陷阱。每次发现新问题时追加。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 新建 Skill 未同步更新 skill-rules.json | Skill 无法被 Hook 自动激活 | 创建 Skill 后必须在 skill-rules.json 中注册 |
| 2 | templates.md 模板变更后未验证新建流程 | 模板错误在下次新建 Skill 时才暴露 | 模板变更后用 dry-run 验证一次完整新建流程 |
| 3 | frontmatter 使用 version/type/priority 字段 | 非标准字段被 Claude Code 运行时忽略 | frontmatter 只使用 description 等标准字段，版本通过 git 管理 |
| 4 | 更新 Skill 后未同步 skill-orchestration.md 协作矩阵 | 新/改 Skill 的协作关系未被其他 Skill 识别 | 注册检查清单中必须包含协作矩阵更新步骤 |
| 5 | description 摘要了工作流（违反 CSO 规则） | Claude 用 description 替代阅读完整 SKILL.md，流程被简化执行 | description 只写触发条件+负空间，不描述流程步骤 |
| 6 | 新 Skill keywords 与已有 Skill 重叠 | 多个 Skill 被同时触发，超出 maxSkillsPerPrompt | 注册前 grep 已有 keywords，确保无冲突 |
| 7 | implicitDependencies 字段遗漏 | Java 相关 Skill 未自动加载 java-backend 规范 | 涉及 Java 操作时必须声明 `["cc-java-backend"]` |

### Skill 增删/重构后必检清单

每次 Skill 增删或重构后，检查以下文件一致性：
- `skill-rules.json`: description 文本、keywords/intentPatterns
- `shared-rules/skill-orchestration.md`: 边界决策表和禁止协作表是否需更新
- 各 `SKILL.md` frontmatter: description 是否与 skill-rules.json 一致
- 如有隐式依赖变更: 检查 implicitDependencies 字段
