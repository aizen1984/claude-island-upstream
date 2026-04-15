---
name: cc-api-analyzer
description: 追踪Java Controller/Service接口调用链并生成ER图和接口文档。不画Mermaid通用图表。用于接口文档化、数据流追踪、表关系梳理
context: fork
agent: general-purpose
allowed-tools: Read, Grep, Glob, Write, Agent
paths: "**/*.java"
report_generation: true
report_protocol: data-report-protocol
report_protocol_mode: full
---

> **Report Generation 声明**：本 skill 是典型的 **Map-Reduce** 报告生成器（Phase 1 Scanner → Phase 2 N×Analyzer 并行 Map → Phase 3 Aggregator Reduce）。必须遵守 `shared-rules/data-report-protocol.md` 三防线：(1) 每个 Analyzer 在分析报告中引用 `<quote file line>` 锚定调用链每一跳；(2) 每个 Analyzer JSON 输出含 `scan_complete`；(3) Aggregator 优先用确定性汇总（Iter 22+ 可考虑改 Python 脚本路径），LLM 缝合是次选。

# API 接口分析器

## 概述

从 Controller/Service 方法切入，追踪调用链到 Repository 层，提取涉及的数据库表信息，最终生成 ER 图和 API 汇总文档。

**核心原则**：Parallel Analysis → File-Based Recording → Aggregation Last

---

## 协作关系

- **接收自**: user、cc-design（需要接口分析时）
- **ER 图生成**: aggregator 自行生成 Mermaid ER 图（遵循 `resources.md` 规范）
- **可选委托**: 表数量 > 5 或需要复杂排版时，可委托 cc-diagram 优化

### ⛔ 强制委托日志（跨 Skill 调用时必须输出）

| 时机 | 必须输出 |
|------|---------|
| Phase 3 Aggregation 表数量 > 5 委托 cc-diagram 优化 | `🔗 cc-api-analyzer.AGGREGATE → cc-diagram \| 原因: 表数量 N > 5 自动委托` |
| Phase 4 完成后用户主动要求生成额外图表 | `🔗 cc-api-analyzer.PRESENT → cc-diagram \| 原因: 用户请求 [图类型]` |

> 详细协作矩阵见 `shared-rules/skill-orchestration.md` 第二章，日志格式见 `shared-rules/observability-logs.md` §2 运行时日志格式

### 数据契约

**输入**：

| 字段 | 必须 | 说明 |
|------|------|------|
| 分析范围 | Y | Controller 类名或包路径（如 `OrderController` 或 `cn.caijiajia.xxx.controller`） |
| 分析模式 | 推荐 | standard（全量）/ quick（单方法） |
| 目标方法 | quick 模式必须 | 方法签名（如 `createOrder`） |

**输出**：

| 产出物 | 格式 | 说明 |
|--------|------|------|
| 接口分析报告 | Markdown（按 Controller 分章） | 含调用链、入参/出参、涉及表 |
| ER 图 | Mermaid erDiagram 代码块 | 表关系+字段+基数 |
| 汇总统计表 | Markdown 表格 | 接口数、表数、热度排名 |
| 传递给 cc-diagram | YAML（entities + relationships） | 表数量 > 5 时委托 |

> 完整字段定义见 `shared-rules/data-contracts.md`

---

## 适用场景

**适用**：分析项目 API 接口和调用链、生成数据库 ER 图、梳理业务逻辑和表关系、新人项目 onboarding

**不适用场景**：

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 单个方法的简单查看 | 直接 Read 工具 | 无需启动完整四阶段分析流程 |
| 纯前端项目 | - | 本 Skill 专注 Java Controller/Service 调用链 |
| 仅画 ER 图（无需接口分析） | cc-diagram | 本 Skill 核心是接口调用链追踪 |

## 模式选择

| 输入 | 模式 | 流程 |
|------|------|------|
| 目录 / 多个 Controller | **标准模式** | Phase 1→2→3→4 |
| 单个 Controller（多接口） | **标准模式** | Phase 1→2→3→4 |
| **单个方法** | **快速模式** | 直接分析，不保存文件 |

---

## 四阶段工作流（标准模式）

> **详细步骤见** `workflows.md`

| 阶段 | 工作 | 子 Agent | 输出 |
|------|------|---------|------|
| Phase 1: Discovery | 批量扫描 Controller | Scanner | Controller + 接口清单 |
| Phase 2: Analysis | 并行分析每个接口（最大10并发） | Analyzer x N | 分析报告 |
| Phase 3: Aggregation | 汇总生成 ER 图 | Aggregator | ER 图 + 汇总 |
| Phase 4: Presentation | **直接展示给用户** | - | 汇总 + ER 图 + 热度 |

## 快速模式

```
用户输入: 分析 OrderController.createOrder 方法
  → 定位目标方法
  → 追踪调用链（Controller→Service→Repository）
  → 提取涉及的表
  → 直接返回分析结果（不保存文件、不调用 diagram）
```

**快速模式输出格式**：

```markdown
## 接口分析：OrderController.createOrder

### 调用链
OrderController.createOrder
  → OrderService.createOrder
    → OrderRepository.save
    → OrderItemRepository.batchInsert

### 涉及表
| 表名 | 操作 | 说明 |
|------|------|------|
| order | INSERT | 订单主表 |
| order_item | INSERT | 订单明细表 |

### 表关系（简化）
order 1--* order_item : order_id
```

---

## 资源加载指导

| 条件 | 加载文件 | 读取范围 | 不加载 |
|------|---------|---------|--------|
| 首次激活 | SKILL.md | 全量 | workflows.md, prompts.md, resources.md |
| Phase 1: Discovery | `workflows.md`（Phase 1 章节） | 按标题定位章节 | prompts.md（Analyzer/Aggregator 部分） |
| Phase 2: Analysis | `workflows.md`（Phase 2 章节）+ `prompts.md`（Analyzer prompt） | 按标题定位章节 | resources.md |
| Phase 3: Aggregation | `workflows.md`（Phase 3 章节）+ `prompts.md`（Aggregator prompt）+ `resources.md`（ER 图规范） | 按标题定位章节 | — |
| Phase 4: Presentation | `resources.md`（报告模板） | 按标题定位章节 | workflows.md, prompts.md |
| 委托 cc-diagram | `shared-rules/data-contracts.md` | 全量 | workflows.md, prompts.md |
| 遇到需求模糊时 | `shared-rules/inquiry-protocol.md` | 全量 | workflows.md, prompts.md, resources.md |

---

## 输出文件归档

```
.api-analysis/
├── reports/                           # 单接口分析报告
│   ├── {Controller}_{Method}.md
│   └── ...
├── er-diagram.md                      # ER 图
└── api-summary.md                     # 方法汇总
```

Phase 4 **必须**向用户直接展示：汇总统计表、完整 ER 图（Mermaid 代码块）、表热度排名、文件保存位置。

---

## 常见错误

| 错误 | 正确做法 |
|------|---------|
| 一次性分析所有接口 | 分批并行（最多10个） |
| 只看 Controller 层 | 追踪到 Repository 层 |
| 漏掉间接调用的表 | 递归追踪 Service 调用 |
| ER 图手动推断关系 | 从代码中 FK 字段推断 |
| **只保存文件不展示** | **必须向用户直接展示 ER 图和汇总** |

## ER 图核心要求

> 详细规范、模板和质量检查清单见 `references/er-guide.md`

---

## 与其他 Skill 协作

> 协作场景详见 `shared-rules/skill-orchestration.md` 第二章

---

## Gotchas

> 从实际使用中积累的常见陷阱。每次发现新问题时追加。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | fork 上下文隔离，不继承主对话 | subagent 缺失用户之前的讨论上下文 | 在 fork prompt 中显式传递分析范围和 Controller 列表 |
| 2 | 表数量 > 5 时自行生成 ER 图 | Mermaid 语法复杂度超限导致渲染失败 | 表数量 > 5 时委托 cc-diagram 生成 |
| 3 | MyBatis XML 中的动态 SQL 可能漏扫 | if/choose 标签内的表引用被遗漏 | 扫描时同时检查 XML mapper 文件的动态标签内容 |
| 4 | 对多接口 Controller 误用快速模式 | 只分析第一个方法，遗漏其他接口 | 快速模式仅用于单方法分析，多接口用标准模式 |
| 5 | Phase 4 只保存文件不向用户展示结果 | 用户无法直接看到 ER 图和汇总 | Phase 4 必须向用户直接展示汇总统计表+ER 图+文件位置 |
| 6 | Service 层循环调用导致追踪死循环 | Analyzer subagent 超时或无限递归 | 追踪时记录已访问方法集合，检测到循环立即中断并标记 |
