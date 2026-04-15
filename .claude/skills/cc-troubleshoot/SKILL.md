---
name: cc-troubleshoot
description: 编排SLS日志/数据库/配置/代码多源排查并生成结构化诊断报告。不修复问题、不改代码。用于生产排障、问题定位、根因分析
argument-hint: [问题描述，如"用户123退款失败" 或 "vipship 生产 ERROR"]
effort: high
allowed-tools: Read, Grep, Glob, Bash, Agent, WebSearch, WebFetch
report_generation: true
report_protocol: data-report-protocol
report_protocol_mode: full
---

> **Report Generation 声明**：本 skill 生成 SIGVR 诊断报告，遵守 `shared-rules/data-report-protocol.md`。**特殊约定**：cc-troubleshoot 已有成熟的 **evidence chain** 机制（SLS-N / SQL-N / CODE-N / CFG-N + file:line），这是 quote grounding 的等效索引形式。**合规规则**：R 阶段报告的关键证据除保留原 evidence ID 外，额外补充 `<quote file="..." line="..."/>` 标签，便于 Iter 23 `verify_report_runtime.py` 统一反向校验。

# 系统化排障

## Gotchas

> 从实际使用中积累的常见陷阱。每次发现新问题时追加。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 跳过 Vault 检索直接查日志 | 缺乏业务上下文，查错方向 | S 阶段强制先查 Vault 获取域知识 |
| 2 | SQL 查询不记录输入来源 | 证据链断裂，报告不可追溯 | 每条 SQL 的 WHERE 参数标注 `<- evidence ID` |
| 3 | 单源结论就下定论 | 误诊（日志可能不完整、数据可能延迟） | V 阶段强制交叉验证，单源标记 ? |
| 4 | 无限调查不收敛 | Token 耗尽、用户等太久 | I 阶段最多 10 轮查询，超过必须进入 G 阶段 |
| 5 | 报告缺少代码定位 | 开发无法根据报告直接修复 | 每个发现必须关联 `file:line` |
| 6 | SQL 大表不走索引 | 查询超时 | 先 `describe.py --indexes-only`，WHERE 条件对齐索引 |
| 7 | traceId 查询加了 context 限制 | 丢失跨应用链路 | traceId 追踪不加 context 过滤 |
| 8 | 排障过程中修改代码/数据 | 职责越界 | cc-troubleshoot 只诊断，不产出任何变更 |
| 9 | SQL 只查状态/ID字段，遗漏 info/detail/ext 等业务详情字段 | 丢失关键排障线索（如 JSON 扩展信息、错误详情） | 查表前先 `describe.py` 看全量字段，SELECT 必须包含 info/detail/remark/ext_info 等业务详情列 |
| 10 | 跳级推导（日志看到 status=3 直接说"失败"，不查代码确认枚举） | 误判（3 可能是"处理中"而非"失败"） | 每个中间值必须逐层查证：日志->数据库->代码确认->配置验证，不允许跳过任何一层 |
| 11 | 报告用反推顺序叙述（"发现失败->反查原因->再反查..."） | 读者无法理解完整业务链路，只看到散乱碎片 | 报告因果链必须**正向叙述**：按业务时间线从触发动作->系统处理->问题点->症状，即使排障是反推的 |
| 12 | 简单单点问题强制走完整 SIGVR 五阶段报告 | 形式大于内容，30 行能说完的事写 300 行 | 先按复杂度路由分级（L0/L1/L2），单点问题用 lite 模板直接三段式输出 |
| 13 | 过程日志（H1/H2/H3 假设/🔗 委托日志/失败重查）泄漏进 R 报告 | 报告变成"排障过程实况转播"，结论被噪音淹没 | 严格执行「报告 vs 过程边界」：S/I/G/V 的过程信息只出现在对话流，R 报告只保留最终证据和结论 |

---

## 复杂度路由（S 阶段决策，强制）

S 阶段必须显式判定复杂度级别，并据此决定后续流程和报告模板：

| 级别 | 判断依据 | 流程 | 报告模板 |
|------|---------|------|---------|
| **L0 轻量** | 单点问题，初步假设指向同一组件；预计 ≤3 条查询可定位；用户描述明确 | S → I → R（**跳过 G/V**，证据闭环后直接出报告） | `references/report-template-lite.md` |
| **L1 标准** | 多源涉及需交叉验证；4-8 条查询；日志/DB/代码/配置至少 3 个维度 | 完整 SIGVR | `references/report-template.md` |
| **L2 复杂** | 跨服务/性能抖动/偶发 NPE；>8 条查询或需要 ARMS；根因可能多个 | 完整 SIGVR + 扩展章节 | `references/report-template.md` |

**判定时机**：S 阶段形成初始假设后，明确声明 `复杂度判定: L{0/1/2}，理由: {一句话}`。

**动态升降级**：

| 触发 | 从 | 到 | 动作 |
|------|-----|-----|------|
| I 阶段前 3 条证据已形成闭环（互相印证，无需再查） | L1 | L0 | 跳过 G/V，直接 R + lite 模板 |
| L0 调查中发现证据不闭环 / 单源结论无法交叉验证 | L0 | L1 | 补跑 G/V 阶段，改用完整模板 |
| L1 发现跨多服务/性能问题需扩展 | L1 | L2 | 继续 SIGVR，报告加扩展章节 |

---

## 报告 vs 过程边界（强制）

| 内容 | 出现位置 | 不出现位置 |
|------|---------|-----------|
| H1/H2/H3 初始假设 | 对话流 S 阶段 | R 报告 |
| 🔗 委托日志（`🔗 cc-troubleshoot.INVESTIGATE → cc-sql ...`） | 对话流 I 阶段 | R 报告 |
| 失败的 SQL、重查过程（如先查 order_id 未命中，再改用 uid） | 对话流 I 阶段 | R 报告（可折叠为"经 N 次重查后确认"一句） |
| 中间废弃的假设 | 对话流 | R 报告 |
| ★ Insight 教学块 | 仅当用户明确要求讲解时出现 | 默认 R 报告不含 |
| 工具调用日志 / describe.py 全量字段输出 | 对话流 I 阶段 | R 报告 |

**一句话规则**：R 阶段开始前在对话流中画一条分隔符（`---`），之上是过程，之下是报告。读者即使只读分隔符之下也能完整理解问题。

---

## Overview

cc-troubleshoot 是一个**诊断工作流 Skill**，通过 SIGVR 五阶段流程系统化排查生产问题。编排 SLS 日志查询、数据库查询、配置查询和源码分析，输出带完整证据链的结构化诊断报告。

**核心特点**：
- **多源编排**：SLS + SQL + CFG + 源码 + Vault 知识库
- **证据链追踪**：每条查询的输入参数可追溯来源
- **交叉验证**：每条结论至少 2 个独立证据源
- **纯诊断**：只读操作，不修改代码/数据/配置

## When to Use

**适用场景**：生产问题排查、根因分析、跨服务问题定位、数据状态排查

**不适用场景**：

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 单纯查日志 | cc-sls-query | 无需完整 SIGVR 五阶段诊断流程 |
| 单纯查数据 | sql | 无需多源交叉验证 |
| 写代码/修 bug | cc-planner / cc-code-writer | 本 Skill 只诊断不产出变更 |
| 性能火焰图分析 | ARMS MCP 工具 | 本 Skill 不做性能 profiling |

---

## 协作关系

- **接收自**: 用户直接触发（命令 `/cc-troubleshoot` 或关键词）
- **委托给**: cc-sls-query（MCP tools）、sql（scripts）、cfg（scripts）
- **内联引用**: cc-think-first（预思考）
- **读取**: Vault 知识库、项目源码
- **无 Skill 调用 cc-troubleshoot**

### ⛔ 强制委托日志（每次使用底层 Skill 工具前必须输出）

> **⚠️ 重要语义说明（必读）**：本 Skill 的 🔗 是**特例语义** —— cc-troubleshoot **不真正嵌套** Skill 流程（详见下方「与底层 Skill 的调用约定」章节），🔗 仅标注「**数据来源 Skill**」而非真正的 Skill 委托。

**Skill 名 → 实际调用对象映射表**（必须知道你在调什么）：

| 🔗 写法 | 实际调用对象 | 调用方式 |
|---------|-------------|---------|
| `→ cc-sls-query` | SLS MCP 工具集 | MCP tool 直接调用 |
| `→ cc-sql` | `python3 .claude/skills/cc-sql/*.py` | python 脚本（非 Skill 流程） |
| `→ cc-cfg` | `python3 .claude/skills/cc-cfg/query.py` | python 脚本（非 Skill 流程） |
| `→ cc-think-first` | 真正的 Skill 内联引用 | 唯一真实的 Skill 委托 |

**为什么仍要输出 🔗**：cc-troubleshoot 是排障编排，会**多次跨源查询**，没有 🔗 日志的话用户看到的是一堆松散的工具调用，无法理解"为什么这一刻去查这个"。🔗 把"动机 + 数据来源 + 证据 ID"绑在一起，让证据链可读。

**输出模板**：

| 时机 | 必须输出 |
|------|---------|
| I 阶段调用 SLS MCP 工具查日志 | `🔗 cc-troubleshoot.INVESTIGATE → cc-sls-query \| 原因: 查询 [应用/k8s] 日志 (evidence SLS-N)` |
| I 阶段调用 sql 脚本查数据库 | `🔗 cc-troubleshoot.INVESTIGATE → cc-sql \| 原因: 验证 [表名] 状态 (evidence SQL-N)` |
| I 阶段调用 cfg 脚本查配置 | `🔗 cc-troubleshoot.INVESTIGATE → cc-cfg \| 原因: 确认 [配置项] 值 (evidence CFG-N)` |
| 调用 cc-think-first 预思考 | `🔗 cc-troubleshoot.SYMPTOM → cc-think-first \| 原因: L[1/2] 假设生成` |

> 详细协作矩阵见 `shared-rules/skill-orchestration.md`，日志格式见 `shared-rules/observability-logs.md` §2 运行时日志格式，本 Skill 的"不嵌套"设计详见下方 §与底层 Skill 的调用约定

---

## 资源加载指导

| 条件 | 加载文件 | 读取范围 | 不加载 |
|------|---------|---------|--------|
| S 阶段（症状确认 + 复杂度判定） | SKILL.md | 全量 | workflows/, references/ |
| I 阶段（信息收集） | [workflows/sigvr-workflow.md](workflows/sigvr-workflow.md), [references/evidence-chain-format.md](references/evidence-chain-format.md) | 全量 | references/report-template*.md |
| G 阶段（L1/L2 才执行） | [workflows/sigvr-workflow.md](workflows/sigvr-workflow.md)（已加载则复用）, [references/evidence-chain-format.md](references/evidence-chain-format.md)（已加载则复用） | 复用 | references/report-template*.md |
| V 阶段（L1/L2 才执行） | [workflows/sigvr-workflow.md](workflows/sigvr-workflow.md)（已加载则复用） | 复用 | references/ |
| **R 阶段（L0 轻量）** | [workflows/sigvr-workflow.md](workflows/sigvr-workflow.md)（已加载则复用）, **[references/report-template-lite.md](references/report-template-lite.md)** | 全量 | references/report-template.md, references/evidence-chain-format.md |
| **R 阶段（L1/L2 标准）** | [workflows/sigvr-workflow.md](workflows/sigvr-workflow.md)（已加载则复用）, [references/report-template.md](references/report-template.md) | 全量 | references/report-template-lite.md, references/evidence-chain-format.md |
| 问题描述模糊时 | `shared-rules/inquiry-protocol.md` | 全量 | workflows/, references/ |

---

## 安全规则

- **只读**：SLS 查询、SQL SELECT/SHOW/DESCRIBE、CFG 查询均为只读
- **不修改**：不修改代码、不修改数据库、不修改配置
- **不执行**：不运行测试、不部署、不重启服务
- SQL 遵循 sql skill 的安全规则（索引预检、LIMIT 限制、禁止 SELECT *）

---

## SIGVR 五阶段流程摘要

> 详细流程见 [workflows/sigvr-workflow.md](workflows/sigvr-workflow.md)

| 阶段 | 目标 | 门控/收敛 |
|------|------|----------|
| **S** 症状确认 | 明确问题、影响范围、时间；Vault 检索域知识；形成 H1-H3 假设 | 至少有问题描述 + 时间范围 |
| **I** 信息收集 | SLS/SQL/CFG/源码多源取证，逐层推导 | 最多 10 轮查询，每 3-5 条评估收敛 |
| **G** 整理分析 | 构建证据依赖链，逐层完整性检查，确定根因链 | 证据链无断裂（否则回退 I） |
| **V** 验证确认 | 交叉验证：双源验证、反证检查、全覆盖测试 | 每条关键结论至少 2 个独立证据源 |
| **R** 报告输出 | 按 report-template.md 生成结构化诊断报告 | 质量检查清单通过 |

---

## 证据链核心规则摘要

以下规则在 I/G 阶段强制执行（详细说明及示例见 workflows/sigvr-workflow.md）：

1. **逐层推导，禁止跳级**：每一层输出是下一层输入，SLS->SQL->CODE->CFG 每次跨源必须写明"用了什么值（来自哪条 evidence）去查了什么"
2. **中间值必须查证**：日志里的 status/code 等值，必须通过 CODE-N 确认枚举含义，不可直接臆断
3. **数据流向显式化**：禁止"根据分析"等模糊表述，必须标注具体 evidence ID 和字段
4. **证据编号体系**：SLS-N / SQL-N / CODE-N / CFG-N，每条标注输入来源和结论
5. **SQL WHERE 参数标注来源**：`WHERE uid = 123 <- SLS-1`
6. **SELECT 必须包含业务详情列**：info/detail/remark/ext_info/reason 等，先 describe.py 查全量字段
7. **完整性逐跳检查**：G 阶段从首条证据到结论逐跳验证，有断裂则回退 I 阶段补查
8. **Quote 标签补充（data-report-protocol §二）**：R 阶段报告的根因结论 + 关键 CODE-N 证据除保留 evidence ID 外，必须额外附 `<quote file="..." line="...">代码原文</quote>` 标签。SLS/SQL/CFG 类证据保留原 evidence ID 即可（无对应文件）。**这条规则只在 R 阶段执行，I/G/V 阶段对话流不要求**——保持调查阶段的紧凑。

---

## 正向叙述原则

排障过程可能是反推的（从错误反查原因），但**报告必须正向讲述**——按业务时间线正序：

1. **触发动作**（用户做了什么 / 定时任务触发了什么）
2. **系统处理步骤**（按代码执行顺序）
3. **问题发生点**（代码定位 file:line）
4. **传导到症状**（用户看到了什么）

---

## 与底层 Skill 的调用约定

cc-troubleshoot **不触发** cc-sls-query/cc-sql/cc-cfg 的完整 Skill 流程（那样会导致 Skill 嵌套），而是**直接使用它们的底层工具**：

| 需求 | 调用方式 | 说明 |
|------|---------|------|
| SLS 日志查询 | MCP 工具直接调用 | 参数映射参考 cc-sls-query workflows.md |
| 数据库查询 | `python3 .claude/skills/cc-sql/*.py` | 遵循 sql skill 安全规则 |
| 配置查询 | `python3 .claude/skills/cc-cfg/query.py` | 遵循 cfg skill 使用方式 |
| 源码分析 | Read/Grep/Glob | 标准工具 |
| Vault 检索 | Read + L0->L1->L2 协议 | 遵循全局 CLAUDE.md |
