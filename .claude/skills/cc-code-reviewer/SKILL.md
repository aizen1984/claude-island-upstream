---
name: cc-code-reviewer
description: 执行九维度代码审查（安全/架构/事务/并发/数据完整性），支持advisory/unified/blocking三种模式。不修改代码、不实现功能。用于PR审查、代码质量检查
allowed-tools: Read, Grep, Glob
paths: "**/*.java, **/*.js, **/*.ts, **/*.py"
report_generation: true
report_protocol: data-report-protocol
report_protocol_mode: full
---

> **Report Generation 声明**：本 skill 生成九维度审查报告（P0-P5 findings + 统计概览 + 对抗验证结论），必须遵守 `shared-rules/data-report-protocol.md` 的 §二 Quote Grounding + §三 Constrained Output Contract。每条 finding 的"位置"字段已含 file:line，**新增要求"原文"字段必须以 `<quote file line>` 包裹原文字符**——防止"位置对但解读错"的伪造。

## Gotchas

> 从实际使用中积累的常见陷阱。每次发现新问题时追加。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 低置信度的问题也报告 | 低质量问题稀释审查报告价值 | 低置信度（无法指向具体代码行或无法排除合理解释）的问题不输出，仅内部记录。标准见 rules.md 置信度评估 |
| 2 | code-reviewer 直接修改代码 | 违反只读审查原则，破坏职责边界 | reviewer 只输出问题列表，由调用方（code-writer/用户）修复 |
| 3 | 内置审查 vs 独立审查场景混淆 | 用错审查深度（九维度 vs 基础质量） | code-writer 完成后 → 内置审查；用户主动请求 → 独立九维度审查 |
| 4 | 对未改动的旧代码报 P3-P5 问题 | 噪音过多，用户只关心自己改的代码 | 增量优先：只审 diff，旧代码仅在被改动触发 Bug 或 P0 安全时才报告 |
| 5 | P2-P5 建议未经代码验证就输出 | 建议听起来合理但实际不可行（如"提取重复"但代码有细微差异） | 每条 P2-P5 建议必须通过可行性自检：有代码锚点、确认可行性、收益真实。不满足则降级为"仅供参考"或丢弃。详见 prompts.md 阶段 10 |
| 6 | 审查范围过大（>500 行 diff）导致超时或遗漏 | 上下文耗尽，后半段审查质量断崖式下降 | diff > 500 行时分批审查：按模块/文件拆分，每批 ≤300 行，分批输出后合并报告 |
| 7 | 审查零问题时无正面输出 | 用户收到空报告，以为审查未执行 | 零问题时显式输出「审查通过」结论 + 至少 3 项良好实践 |
| 8 | 对非 Java 代码套用 Java 专项规则 | 产生大量不适用的建议或误报 | 检测目标语言，非 Java 时声明降级为通用审查 |

# 数禾 Code Reviewer

> 基于实际项目代码抽象的综合代码审查规范，整合安全、数据完整性、业务行为、流程顺序、架构、单元测试、性能、设计模式、代码简化九大维度

---

## Overview

**cc-code-reviewer** 是九维度代码审查 Skill，支持建议式（advisory）、统一审查门控（unified）和阻断式（blocking）三种模式，输出带置信度的问题列表。

---

## When to Use

**适用场景**：代码实现后审查 | PR/MR 提交前检查 | 重构前评估 | work-mode 完成后强制审查

## When Not to Use

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 设计阶段的架构评审 | cc-design | 本 Skill 审查代码实现，不审查设计方案 |
| 直接修复代码问题 | cc-code-writer | 本 Skill 只输出审查报告，不修改代码 |
| 批量并行代码修改 | cc-work-mode | 本 Skill 是终端审查，不编排任务 |

### 语言适用性

本 Skill 针对 Java（Spring Boot + MyBatis）技术栈深度优化。审查非 Java 代码时：

| 维度 | Java 专项（不适用非 Java） | 通用（适用所有语言） |
|------|--------------------------|--------------------| 
| 安全审查 | #{}/PreparedStatement → 对应语言参数化方案 | 注入防护、敏感数据、加密 |
| 数据完整性 | @Transactional/AopContext → 对应语言事务机制 | 事务边界、竞态条件、状态机 |
| 架构合规 | Controller→Service→Repository 分层 | 分层依赖、SRP/OCP/DIP |
| 性能优化 | PageHelper/MyBatis 批量 | N+1、分页、缓存 |

**非 Java 审查**：检测语言 → 声明降级 → 仅通用维度。详见 `references/language-support.md`

---

## 协作关系

- **接收自**: user（直接审查请求）、cc-work-mode（SUMMARIZE 阶段 subagent 派发）
- **规则被引用（非 Skill 激活）**: cc-code-writer 的"内置审查" subagent 遵循本 Skill 的 P0-P5 规则，但不走 Skill 激活路径（即不作为独立 Skill 被调用）——这与 cc-code-writer/SKILL.md L47 的"不是调用 code-reviewer Skill"声明对齐
- **委托给**: 无（终端 Skill）
- **禁止**: 审查结果应返回原调用方（cc-work-mode 或 user）处理，reviewer 不直接调用 code-writer 修复代码
- **隐式依赖**: cc-java-backend（审查时参考规范）

> 详细协作矩阵见 `shared-rules/skill-orchestration.md` 第二章

---

## 资源加载指导

| 条件 | 加载文件 | 读取范围 | 不加载 |
|------|---------|---------|--------|
| 快速审查/小改动 | `checklists.md` 快速检查清单 | 按标题定位 | rules.md |
| 全面审查 | `checklists.md` 完整审查清单 | 全量 | — |
| 架构/分层/SOLID | `rules.md` 架构合规章节 | 按标题定位 | checklists.md |
| 事务/并发/锁 | `rules.md` 数据完整性章节 | 按标题定位 | checklists.md |
| 性能、N+1、批量 | `rules.md` 性能优化章节 | 按标题定位 | checklists.md |
| 设计模式、枚举 | `rules.md` 设计模式章节 | 按标题定位 | checklists.md |
| 安全、注入 | `rules.md` 安全审查章节 | 按标题定位 | checklists.md |
| 阻断式审查、门控 | `rules.md` 门控流程章节 | 按标题定位 | checklists.md |
| 误报处理 | `rules.md` 误报处理章节 | 按标题定位 | checklists.md |
| 审查报告/零问题处理 | `prompts.md` | 全量 | rules.md, checklists.md |
| 非 Java 语言审查 | `references/language-support.md` | 全量 | rules.md |
| 需要评分校准 | `calibration-examples.md` | 全量 | rules.md |

---

## 预思考（仅独立审查时强制）

用户直接请求审查时，**必须**执行 cc-think-first 预思考协议（`shared-rules/skill-orchestration.md` §七 预思考协议）。code-writer/cc-work-mode 内置审查时**不执行**（调用方已完成预思考）。

**reviewer 专用 L0 条件**（在 protocol 通用 L0 基础上收紧）：
- **L0 跳过**：来自 code-writer/cc-work-mode 的内置审查 **或** 用户说"快速看一下"/"直接审"
- **至少 L1**：用户直接请求独立审查（需判断审查重点和范围）

输出 `🧠 Think-First L{0|1|2} {级别名}` 到控制台。

---

## 核心能力概述

### 智能维度选择（默认模式）

根据变更类型自动选择相关维度，而非强制九项全检：

| 变更类型 | 必查维度 | 可选维度 |
|---------|---------|---------|
| 涉及数据写入 | 安全、数据完整性、业务行为 | 架构、性能 |
| 纯读取/查询 | 安全、性能 | 架构 |
| DTO/枚举/配置 | 架构 | 代码简化 |
| 测试代码 | 单元测试 | - |
| 跨模块/跨服务 | 架构、流程顺序 | 性能、设计模式 |

**强制完整审查**：涉及事务、并发、安全、支付金融、公共工具类时，执行全部九维度。

### 九维度审查（参考清单）

| 维度 | 关注点 | 优先级 | 详细规则 |
|------|--------|--------|----------|
| **安全审查** | 注入防护、敏感数据、加密 | P0 | `rules.md` 安全审查 |
| **数据完整性** | 事务、锁、状态机、一致性 | P0 | `rules.md` 数据完整性 |
| **业务行为** | 验收标准、边界条件、异常处理 | P0 | `checklists.md` 业务行为验证 |
| **流程顺序** | 操作顺序、幂等性、补偿机制 | P0 | `checklists.md` 流程顺序验证 |
| **架构合规** | 分层、依赖注入、职责边界、**方法注释** | P1 | `rules.md` 架构合规 |
| **单元测试** | 断言质量、覆盖率 | P2 | `checklists.md` 单元测试 |
| **性能优化** | 批量处理、N+1、分页、并发 | P3 | `rules.md` 性能优化 |
| **设计模式** | 策略、工厂、枚举、上下文 | P4 | `rules.md` 设计模式 |
| **代码简化** | 方法长度、嵌套、Java 8+ | P5 | `rules.md` 代码简化 |

### 三种模式支持

> 审查模式（建议式/统一审查门控/阻断式强制）及审查深度选择详见 `shared-rules/skill-quality.md`

---

## 审查范围原则（增量优先）

**核心规则：只审查 diff，旧代码不主动找问题。**

| 范围 | 审查强度 | 说明 |
|------|---------|------|
| **新增/修改的代码行**（diff 绿色） | 全量九维度 | 主审目标 |
| **被改动直接影响的旧代码**（调用方、被调用方） | 仅检查是否因改动引入 Bug | 如：改了方法签名，调用方是否适配 |
| **未被改动触及的旧代码** | **不审查** | 即使有问题也不报告（除非用户明确要求全量审查） |

**例外**：旧代码中的安全漏洞（P0 安全）如果被改动代码路径经过，仍需报告。

---

## 审查工作流程

> 获取 diff → 识别变更类型 → 扩大上下文 → 执行检查清单(P0→P5) → 自我审视 → 对抗验证 → 综合输出 → 询问确认
>
> 完整流程（阶段 1-11 展开 + 维度→门控映射 + 对抗验证策略 + 询问确认条件表）见 `prompts.md`。
> 检查清单见 `checklists.md`，问题严重度定义（P0-P5）见 `rules.md`。

---

## 审查结果数据契约

> 完整数据契约见 `shared-rules/data-contracts.md`，审查流程见 `shared-rules/skill-quality.md`

---

## 严谨审查原则

疑似问题先扩大上下文再定性；P0/P1 必须反向验证；不确定标记"待确认"。详见 `rules.md`。

