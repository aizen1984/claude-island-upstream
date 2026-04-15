# spec-template

# [功能名称] Spec

**创建时间**: {{timestamp}}
**类型**: feature | bugfix
**状态**: 草稿 | 已确认 | 已完成

## 目标
{{一句话目标，不带"和"——范围测试：能用一句话不带"和"描述则粒度合适}}

## 需求
- REQ-1: {{需求描述}}
- REQ-2: ...

## 约束
- CON-1: {{技术约束}}
- CON-2: {{业务约束}}

## 验收标准
- [ ] AC-1: Given {{前置条件}} When {{操作}} Then {{期望结果}} | 验证: {{具体命令/SQL/断言}}
- [ ] AC-2: Given ... When ... Then ... | 验证: ...

## 变更范围
- 新增/修改: {{文件列表}}
- 不应触及: {{不应变更的文件/模块}}

## 非目标
- {{明确排除的范围}}

## 决策记录
| # | 决策 | 选择 | 原因 | 被否决方案 |
|---|------|------|------|-----------|

## 冲刺合同（Sprint Contract）

> **触发条件**：任务数 > 8 时必须；≤ 8 时可选（用户或 Planner 主动触发）。
> **协商方**：Generator（Planner）提出 → Evaluator subagent 审查 → 用户最终确认。
> **设计来源**：Anthropic Harness Design — "the generator proposed what it would build and how success would be verified, and the evaluator reviewed that proposal"

### 实现范围（Generator 填写）
| # | 做什么 | 涉及文件 | 预估 LOC |
|---|--------|---------|---------|
| 1 | {实现项描述} | {file1, file2} | {N} |

### Testable Behaviors（双方协商）

> 每行是一个**独立可验证的行为**。Evaluator 审查四维度：可测性、完整性、防作弊、阈值合理性。
> 状态流转：🔴 proposed → 🟡 challenged → 🟢 agreed

| # | 行为描述 | 验证方法 | 类型 | 阈值 | 提出方 | 状态 |
|---|---------|---------|------|------|--------|------|
| TB-1 | {具体行为，如"POST /api/x 返回 200 且 body.id > 0"} | {命令/脚本/断言} | rules-based | PASS/FAIL | Generator | 🟢 |
| TB-2 | {边界场景，如"并发 10 请求幂等，仅产生 1 条记录"} | {验证方法} | rules-based | PASS/FAIL | Evaluator | 🟢 |

> **强制约束**：rules-based 类型占比 >= 50%（与 goal.md 评估标准一致）。
> **Per-criterion 阈值**：EXECUTE 完成后，任一 TB 低于阈值即 sprint FAIL，不依赖加权总分。

### 评分目标（加权总分，补充 per-criterion 阈值）
- 功能正确性 >= {X}
- 代码质量 >= {X}
- 安全与数据完整性 >= {X}

### 明确排除项
- {不包含在本次冲刺的内容}

### 变更条款
- 超出范围的需求 → 创建新 Issue/任务，不在本冲刺实现
- 技术障碍无法预见 → 触发 REPLAN，重新协商合同
- TB 执行中发现不可行 → 标记 ⚠️ 并在 Negotiation Log 追加原因

### Negotiation Log
- R{N}: {谁} 挑战/补充了什么 → {结果}
- **Status: 🔴 PROPOSED / 🟡 IN NEGOTIATION / 🟢 AGREED (R{N})**

### 确认
- [ ] Evaluator 审查通过（四维度：可测性/完整性/防作弊/阈值合理性）
- [ ] 用户同意实现范围
- [ ] 用户同意 Testable Behaviors

---

# bugfix-spec-template

# [Bug 简述] Bug Fix Spec

**创建时间**: {{timestamp}}
**类型**: bugfix
**严重度**: P0-Critical | P1-High | P2-Medium | P3-Low

## Bug 描述
- **现象**: {{用户可见的错误描述}}
- **复现步骤**: 1. ... 2. ... 3. ...
- **影响范围**: {{用户数/功能/数据}}

## 根因分析
- **根因**: {{一句话根因}}
- **证据**: {{日志/代码路径/SQL 结果}}
- **调用链**: `ServiceA.method → ServiceB.method → DAO.update`

## 修复方案
- FIX-1: {{修复动作}} | 文件: {{file:line}}
- FIX-2: ...

## 验收标准
- [ ] AC-1: Given {{Bug 复现条件}} When {{执行操作}} Then {{Bug 不再出现}} | 验证: {{命令}}
- [ ] AC-2: Given {{正常流程}} When {{执行操作}} Then {{功能正常（回归）}} | 验证: {{命令}}

## 变更范围
- 修改: {{文件列表}}
- 不应触及: {{不应变更的文件/模块}}
