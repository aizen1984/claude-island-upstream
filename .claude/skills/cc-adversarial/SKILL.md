---
name: cc-adversarial
description: 对当前对话中的结论进行独立对抗验证，支持复杂度自适应（单challenger/三角辩论）。不修改代码、不产出设计。用于方案评审、分析结论验证、排障诊断复查
allowed-tools: Read, Grep, Glob, Agent
report_generation: true
report_protocol: data-report-protocol
report_protocol_mode: full
---

> **Report Generation**：`full` 模式 — 遵守 `data-report-protocol.md` §二 Quote Grounding + §三 Constrained Output + §四 Deterministic Reduce。

## Gotchas

> 从实际使用和学术研究中积累的核心陷阱。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 传递推理链给验证 agent | 验证方被"说服"，失去独立性（Anthropic Debate 实证：judge 不看推理链时准确率反而更高） | 只传结论清单 + 原始材料，不传推理过程 |
| 2 | L1 场景使用多 agent | 研究表明多 agent 辩论在标准任务上不优于单 agent 自一致性（"Can LLM Agents Really Debate?", arXiv 2511.07784），浪费 token | L1 只用单 challenger |
| 3 | L3 辩论超过 2 轮 | 4-5 轮引入噪声和误差积累，同模型辩论系统性过度自信（Free-MAD: R=1 64.43% vs R=2 baseline 62.50%） | 严格 2 轮（正反并行->裁判），**选择性触发比轮数更重要**（iMAD: 57-85% 辩论不必要，4-14% 有害） |
| 4 | 对话中无明确结论时硬提取 | 幻觉结论清单 | 识别失败时直接问用户"你想验证什么？" |
| 5 | 验证 agent 广泛探索代码库 | 上下文爆炸，验证质量下降 | 严格限定文件范围，只读指定范围 |
| 6 | 同构 agent 共识陷阱（confabulation consensus） | 正/反/裁判共享同一预训练偏见，在同一盲区集体失明 | L3 反方使用独立上下文（推理隔离）实现多视角；Judge 内置反从众规则 + FPD 分歧点定位 |
| 7 | 株连效应：一条结论错误导致 agent 对所有结论打低分 | 正确结论被连坐误判 | Challenger prompt 增加"逐条独立评估"校准规则 + 自检：全低分时强制重审 |
| 8 | 高共识当作"验证通过"：所有 agent 一致确认但集体盲区 | 移除动态检索后一致性上升但准确率下降7.5pp | 认知泡沫检测：>=80% 确认 + 0% 独立发现 -> 输出警告 |
| 9 | 反方角色扮演过度导致结构化否定偏差 | 所有 judge 过度产生 REFUTE | Devil's Advocate prompt 增加否定偏差校准：>70% 低分时强制重审 |

# 通用对抗验证

用户主动触发的独立对抗验证能力。与现有 `adversarial-verification.md` 被动协议互补——后者被 code-reviewer/cc-api-analyzer 内嵌调用，本 Skill 提供独立入口。

核心特点：
- **复杂度自适应**：自动判定 L1/L2/L3，避免简单结论走重流程
- **推理隔离**：验证 agent 只接收结论清单，不接收推理链
- **最大化模型能力**：prompt 只传上下文和约束，不指导分析方法

---

## When Not to Use

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 代码审查（reviewer 内置对抗） | cc-code-reviewer | 阶段11已内嵌对抗验证 |
| 无预设结论的开放探索 | Agent Teams 竞争假设 | 无预设结论时 Teams 双向通信更适合 |
| 修改代码/实现功能 | cc-code-writer | 本 Skill 只验证，不修改 |
| 方案选型对比 | cc-planner / cc-think-first | 本 Skill 验证已有结论，不做方案对比 |

---

## 协作关系

- **接收自**：user（直接 `/cc-adversarial`）、其他 Skill 工作流（内置对抗验证步骤）
- **委托给**：无（终端 Skill）
- **内联引用**：`adversarial-verification.md`（L1 场景的完整协议）
- **隐式依赖**：无

> 详细协作矩阵见 `shared-rules/skill-orchestration.md`

---

## 资源加载指导

| 条件 | 加载文件 | 不加载 |
|------|---------|--------|
| L1 轻量验证 | `shared-rules/adversarial-verification.md` §三-§六 | prompts.md |
| L1 归桶归档 | `shared-rules/adversarial-verification.md` §四（含 FLCA 评分输出） | — |
| L2 标准验证 | `prompts.md`（Challenger prompt + §五 L2 策略） | adversarial-verification.md |
| L3 深度辩论 | `prompts.md`（三角色 prompt + S6 L3 策略） | adversarial-verification.md |
| 输出报告 | `templates/report-format.md` | — |
| 规则阈值校准/回归测试 | `evals/calibration-baseline.md`（10 个 FLCA 典型样例 + 旧/新规则翻转对照） | — |

---

## 复杂度自适应

自动判定验证级别，用户可通过参数覆盖。

### 判定规则

| 级别 | 判定条件 | 验证策略 | Agent 数 | max_turns |
|------|---------|---------|---------|-----------|
| **L1 轻量** | 结论 <=3 条 AND 非 P0 关键词 AND 非代码场景（纯业务流程/产品方案/运营策略；引用类名/方法名/SQL/注解的讨论算代码场景） | 单 challenger | 1 | 6 |
| **L2 标准** | 结论 4-10 条 OR 涉及代码变更 OR 中等复杂度 | Challenger + Verification-First | 1-2 | 8 |
| **L3 深度** | P0 关键词 OR 结论 >10 条 OR 用户指定 `--deep` | 三角辩论（正/反/裁判），**反方使用独立上下文实现推理隔离** | 3 | 10 |

### 辩论必要性前置评估（来源: iMAD AAAI 2026）

> 57-85% 的辩论不必要，4-14% 有害。派发 agent 前，Lead 快速评估三信号（任一命中 -> 判定"辩论必要"，否则降级一档：L3→L2 / L2→L1，**不再继续降级**）：

1. **不确定性信号**：结论中含对冲用语（"应该"、"大概率"、"一般来说"、"理论上"）。排除："应"用作规范性建议（"接口应返回 200"）不算对冲
2. **争议性信号**：结论涉及设计取舍（trade-off）、多方案选择、或已知有争议的技术点
3. **复杂度信号**：结论涉及跨模块交互、状态机流转、或并发/事务场景

**⛔ 降级例外（强约束）**：

- **P0 关键词硬触发的 L3 不被前置评估降级**（即使三信号全未命中，P0 路径仍走完整 L3 三角辩论）
- **用户显式 `--deep` 参数不被降级**（用户意图优先）
- **降级只影响"候选级别"**：如 L2 被降级到 L1；L3 被降级到 L2（而非直接到 L1）

### P0 关键词（触发 L3 升级）

**双条件触发**：关键词命中 **AND** 涉及核心改动 / 不可逆操作 / 新增竞态风险 —— 仅提及但未实际修改相关代码时，不升级到 L3（避免"看到 @Transactional 就触发辩论"的过严问题）。

**关键词清单**：`@Transactional` / `synchronized` / `FOR UPDATE` / `DistributedLock` / `DELETE` / `DROP` / `TRUNCATE` / 支付 / 退款 / 消费 / 计费 / 账单 / 金额 / 余额 / 安全漏洞 / 数据迁移 / 不可逆操作

**核心改动判定**：
- ✅ 升级 L3：新增/修改 `@Transactional` 方法、修改分布式锁边界、新 DELETE/DROP SQL、金额计算/幂等改动
- ❌ 不升级：方案中仅"提到"要加事务但未实际修改、仅查询 SELECT 不涉及写入、纯文档变更

### 用户覆盖

- `/cc-adversarial` — 自动判定
- `/cc-adversarial --l1` — 强制轻量
- `/cc-adversarial --deep` — 强制深度辩论
- `/cc-adversarial "要验证的结论"` — 跳过自动提取，直接使用指定结论

---

## 核心流程

结论提取 → 复杂度判定(L1/L2/L3) → iMAD 前置评估 → 推理隔离 → Agent 派发 → 综合对比 → 输出报告

---

## L1 轻量验证

直接引用 `adversarial-verification.md` 协议，派发单个 challenger agent。

1. 按协议 §四 准备验证 agent 输入（结论清单 + 原始材料 + 文件范围）
2. 派发 1 个 `general-purpose` agent，按协议 §四 通用约束执行
3. 按协议 §五 综合对比算法处理结果
4. 按 `templates/report-format.md` 输出格式生成报告

> L2/L3 详细策略见 `prompts.md` 第五、六章。

---

## 综合对比

> 完整 FLCA 算法（四维评分 + 三桶映射 + 认知泡沫检测）见 `prompts.md` §共享约束 — 综合判定规则。
> 分歧裁决防偏规则见 `adversarial-verification.md` §五。
>
> **快速参考**：任一 ≤3 → ❌ | 均 ≥6 且无 ≤4 → ✅ | 其余 → ⚠️ | P0 分歧 → ❌ 强制升级用户

---

## 报告生成（Lead 必做 — 最终交付物）

> ⛔ **Agent 返回结果 ≠ 流程结束**。Lead 必须将 Agent 原始输出转换为面向用户的三桶行动报告。报告是用户看到的唯一交付物——缺少报告 = 验证未完成。

**Lead 在 Agent 返回后执行以下步骤**：

1. **汇总评分**：从 Agent 输出中提取每条结论的 FLCA 四维评分
2. **归桶**：按综合判定规则（任一 ≤3 → ❌ | 均 ≥6 且无 ≤4 → ✅ | 其余 → ⚠️）将每条结论归入三桶
3. **加载模板**：`📂 templates/report-format.md ← 报告生成`
4. **生成报告**：按 `templates/report-format.md` 模板输出完整报告，包含：
   - 一句话总结（"N 条中 X 条有误、Y 条需补充、Z 条确认"）
   - ❌ 有误：每条列出 错在哪 + 为什么 + 怎么改
   - ⚠️ 不完整：每条列出 缺什么 + 不补的影响 + 怎么补
   - ✅ 已确认：每条列出验证方式
   - 💡 盲区发现（如有）
   - `<details>` 折叠的评分明细和验证过程
5. **认知泡沫检测**：>=80% 确认 + 独立发现率=0% → 输出 WARNING

> **空桶处理**：❌/⚠️/💡 节如果无内容则整节删除，不输出空表格。

---

## 可观测性日志

验证启动：
```
SEARCH 对抗验证 L{N} | 结论: {M}条 | 场景: {type} | Agent: {数量}
```

验证完成：
```
SEARCH 验证完成: 确认 {N} | 反驳 {N} | 盲区 {N} | 未覆盖 {N} | 独立发现率: {X}% | 质量: [充分/不充分]
```

---

## 数据契约

### 输入

| 字段 | 必须 | 说明 |
|------|------|------|
| 对话中的结论 | Y | 自动提取或用户指定 |
| 原始材料位置 | Y | 代码路径/需求文档/分析范围 |
| 级别覆盖 | N | `--l1` / `--deep` |

### 输出

| 字段 | 必须 | 说明 |
|------|------|------|
| verification_level | Y | L1 / L2 / L3 |
| status | Y | CONSENSUS / DIVERGENCE / SUPPLEMENT |
| consensus_items | Y | 共识结论列表（high 置信度），**每条必须含 `<quote file line>` 支持** |
| divergence_items | Y | 分歧列表（含双方观点 + 严重度 + 裁决），**每条必须含双方 quote** |
| supplement_items | Y | 盲区发现列表，**每条必须含 `<quote>` 指向盲区原文** |
| coverage | Y | 已验证/总数 百分比 |
| scan_complete | Y | `true / false`（data-report-protocol §三） |
| unscanned_reason | N | scan_complete=false 时必填，说明未完成原因 |
| removed_no_quote | N | 自审删除的无 quote 支持的原始结论列表（data-report-protocol §二 [REMOVED:no-quote]） |

> **Quote Grounding 强制规则**: consensus/divergence/supplement 三类结论的每一条都必须含 `<quote file="..." line="..."/>` 支持。由 `verify_report_runtime.py` 运行时拦截 + `check_consistency.py` 静态检查。
