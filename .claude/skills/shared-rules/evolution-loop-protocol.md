# 策略进化循环协议

> **加载时机**：code-writer 审查进入 evolution loop 时；eval skill Layer 3 auto-fix 时。
> **来源**：Anthropic [Harness Design](https://www.anthropic.com/engineering/harness-design-long-running-apps) GAN 式 Generator-Evaluator 模式。

---

## 一、核心概念：Fix Loop vs Strategy Evolution

| 维度 | Fix Loop（降级选项） | Strategy Evolution（默认） |
|------|---------------------|--------------------------|
| **改什么** | 修补当前产出 | 改进生成策略 |
| **Implementer 行为** | 收到 fix_suggestion → patch 代码 | 收到 strategy_amendments → 从头/大幅重写 |
| **Reviewer 输出** | issues（具体问题） | issues + insights（模式分析） |
| **进化方式** | 线性改善（消除扣分项） | 质变飞跃（策略层面突破） |
| **适用场景** | 简单 bug 修复、明确的局部问题 | 反复审查不通过、需要架构级改进 |

**选择规则**：
- **默认 Strategy Evolution**（审查不通过时直接进入进化循环）
- 以下情况降级为 Fix Loop：
  - 用户显式指定（prompt 含 `--fix-only` 或"直接修"/"快速修复"）
  - Reviewer 未输出任何 insight（无 pattern 可提炼时，无论 P0/P1 数量，均降级为 Fix Loop——无 insight 驱动的 evolution loop 是空转）

**首次审查特殊处理**：首次审查时 ROUND_CONTRACT 不存在，Reviewer 不会输出 insights。因此首次审查不通过时始终走 Fix Loop 作为快速尝试。Fix Loop 失败后（第 2 轮），Lead 注入 ROUND_CONTRACT 触发 Reviewer 输出 insights，从第 2 轮起进入 Strategy Evolution

---

## 二、三组件定义

### 组件 1：Insight Extractor（由 Lead 执行，不是独立 agent）

**职责**：从 Reviewer 输出中提炼 pattern，聚合到 insights_log。

**执行时机**：每次收到 Reviewer 结果后。

**逻辑**：
1. 解析 Reviewer 的 `insights[]` 输出
2. 与 `strategy_store.insights_log` 比对：
   - 新 insight → 加入 log，frequency = 1
   - 已有 insight（同 dimension + 相似 pattern）→ frequency += 1
   - 上轮存在本轮消失 → 标记 resolved_at_round
3. 输出：更新后的 insights_log

### 组件 2：Strategy Evolver（由 Lead 执行）

**职责**：从 insights_log 中 frequency ≥ 2 的 insight 生成 strategy amendment。

**执行时机**：Insight Extractor 之后，下一轮 Implementer 派发之前。

**逻辑**：
1. 筛选 insights_log 中 frequency ≥ 2 的 insight
2. 为每个 insight 生成 amendment：
   - rule：一句话可执行规则（如"所有外部 API 调用必须包裹 try-catch"）
   - confidence：frequency 2 = medium，≥ 3 = high
3. 已 resolved 的 insight 对应的 amendment → 标记 `validated: true`（证明有效，保留）
4. 输出：更新后的 amendments[]

### 组件 3：Strategy Store（session 文件持久化）

**文件位置**：`$STARK_SESSION_DIR/strategy.yaml`

**职责**：持久化策略状态，跨轮次传递。

---

## 三、数据模型

### Insight（评价提炼物）

```yaml
insight:
  id: string                    # "INS-{round}-{seq}"
  dimension: string             # 对应 reviewer 九维度之一
  pattern: string               # 反复出现的问题模式描述
  frequency: number             # 跨轮次出现次数
  severity: string              # P0-P5
  root_cause: string            # 指向策略缺失，非代码 bug
  first_seen_round: number
  resolved_at_round: number | null
```

### Strategy Amendment（策略修正）

```yaml
amendment:
  id: string                    # "AMD-{seq}"
  source_insights: string[]     # insight id 列表
  rule: string                  # 一句话可执行规则
  confidence: "high" | "medium" # frequency ≥ 3 = high，= 2 = medium
  round_added: number
  validated: boolean            # 对应 insight resolved 后标记为 true
```

### Round Contract（每轮目标协商）

```yaml
round_contract:
  round_number: number
  focus_dimension: string       # 本轮重点审查维度（九维度之一）
  focus_weight_key: string      # 映射到的四维度 key（见映射表）
  weight_overrides:             # 评分权重覆盖（默认全 1.0）
    functionality: number
    quality: number
    security: number
    testing: number
  strategy_amendments: string[] # 本轮注入的 amendment rule 列表
  rationale: string             # 为什么选这个 focus（给 Reviewer 看）
```

### 九维度→四维度映射表

Reviewer 的 insight dimension 使用九维度，weight_overrides 使用四维度。Lead 生成 Round Contract 时按此表映射：

| Reviewer 九维度 | 映射到 weight_overrides key | 说明 |
|----------------|---------------------------|------|
| 安全审查 | `security` | 直接对应 |
| 数据完整性 | `security` | 事务/锁/状态一致性属安全范畴 |
| 业务行为验证 | `functionality` | 直接对应 |
| 流程顺序验证 | `functionality` | 操作顺序属功能正确性 |
| 架构合规 | `quality` | 分层/依赖属代码质量 |
| 单元测试 | `testing` | 直接对应 |
| 性能优化 | `quality` | 性能属代码质量范畴 |
| 设计模式 | `quality` | 设计属代码质量范畴 |
| 代码简化 | `quality` | 可读性属代码质量范畴 |

### Strategy Store（session 文件）

```yaml
# $STARK_SESSION_DIR/strategy.yaml
domain: string                  # "coding" | "design" | "testing"
task_id: string                 # 关联的任务 ID
amendments: Amendment[]
insights_log: Insight[]
round_contracts: RoundContract[]  # 历史 contract 记录
convergence:
  current_round: number
  scores: number[]              # 每轮 weighted_total
  status: "evolving" | "converged" | "max_rounds" | "user_stop"
```

---

## 四、单轮执行流程

```
Round N:

1. Round Contract 生成
   - Lead 分析 insights_log，选择 frequency 最高且未 resolved 的 dimension 作为 focus
   - 生成 weight_overrides（focus 维度权重 × 1.5，其余不变）
   - 收集 amendments[] 中 validated=false 的 rule 作为 strategy_amendments

2. Implementer 派发
   - 注入 STRATEGY_AMENDMENTS 到 prompt（来自 round_contract.strategy_amendments）
   - 如果 round_number > 1 且上轮 score < 3.0：从头生成（不是 patch）
   - 如果 round_number > 1 且上轮 score >= 3.0：在上轮基础上改进

3. Reviewer 评审
   - 接收 round_contract（含 weight_overrides + focus_dimension）
   - 输出标准 issues + 新增 insights[]
   - 评分时按 weight_overrides 计算 weighted_total

4. Insight Extraction
   - Lead 解析 insights，更新 insights_log

5. Strategy Evolution
   - Lead 从 insights_log 生成/更新 amendments

6. Convergence Check
   - 见第五章收敛规则
```

---

## 五、收敛规则

**三个条件任一满足即停止进化循环**：

| 条件 | 阈值 | 计算方式 | 说明 |
|------|------|---------|------|
| `max_rounds` | 5 | — | 绝对上限，防止无限循环 |
| `score_plateau` | 连续 2 轮提升 < 0.25 分 | `abs(score_n - score_{n-1}) < 0.25`（满分 5.0，即 5% 绝对分值） | 策略已趋稳定 |
| `no_new_insights` | 连续 2 轮无新 insight | 本轮新增 insight 数 = 0（不含 frequency 增长）；从 Round 2 开始计数 | 已无新模式可提炼 |

**insight "消失"判定**：insight 须连续 2 轮不出现才标记 `resolved`（去抖动，避免 Reviewer 非确定性导致误标记）

**停止时输出**：
1. 当前最佳产出（score 最高的那轮）
2. 累积 strategy amendments（可考虑毕业为持久规则）
3. 未 resolved 的 insights（需人工决策）

---

## 六、跨阶段回流规则

> 当 Strategy Evolution 被用于多阶段 pipeline（设计→编码→测试→排障）时适用。

| insight 来源阶段 | 回流到策略 | 触发条件 |
|----------------|-----------|---------|
| 测试失败 | 编码策略 | 总是 |
| 测试失败 | 设计策略 | root_cause 涉及"接口设计"或"数据模型" |
| 排障结论 | 编码策略 | 总是 |
| 排障结论 | 测试策略 | pattern 含"测试未覆盖" |
| Code Review | 编码策略 | 总是 |
| Code Review | 设计策略 | dimension = "architecture" 或 "data_model" |
| **Sprint Contract TB 失败** | 编码策略 | 总是（TB FAIL 自动转为 insight） |
| **Sprint Contract TB 失败** | 设计策略 | TB 涉及接口契约或数据模型 |

**Sprint Contract TB → Insight 转化规则**：

```yaml
for each failed_tb in sprint_contract.testable_behaviors:
  if failed_tb.result == "FAIL":
    insight:
      id: "INS-TB-{tb_id}"
      dimension: 映射 TB 行为类型到九维度（功能性→业务行为验证，并发→数据完整性，性能→性能优化）
      pattern: "Sprint Contract TB-{tb_id} 未通过: {tb.behavior}"
      frequency: 1  # 首次出现；跨轮次累加
      severity: "P1"  # TB 是协商确认的硬阈值，FAIL = P1
      root_cause: "{tb.verification_method} 输出: {验证命令实际输出摘要}"
```

> 这使得 Evaluator 在协商阶段定义的 TB 直接驱动后续迭代方向——协商不只是执行前的"门控"，而是持续进化的"锚点"。

**回流方式**：将 insight 写入对应 domain 的 strategy.yaml，下次该阶段执行时自动注入。

---

## 七、策略毕业

被反复验证有效的 amendment 可升级为持久规则：

| 阶段 | 存储 | 生命周期 | 毕业条件 |
|------|------|---------|---------|
| 初始 | `strategy.yaml` | 单次 evolution loop | — |
| 验证 | `strategy.yaml` validated=true | 当次会话 | insight resolved |
| 毕业 | SKILL.md gotchas / shared-rules / 知识库 | 永久 | confidence=high + validated + 跨 3 次会话出现 |

**毕业操作**：Lead 在 evolution loop 结束时，检查是否有满足毕业条件的 amendment，提示用户确认是否写入持久位置。

---

## 八、Opt-in 机制

Skill 通过以下方式声明支持 evolution loop：

1. **SKILL.md 资源加载表**：增加 `审查进入 evolution loop 时 | shared-rules/evolution-loop-protocol.md` 行
2. **workflows 中引用**：审查失败处理章节包含"双模式"逻辑
3. **prompts 中支持**：Reviewer prompt 包含 insights 输出要求，Implementer prompt 包含 STRATEGY_AMENDMENTS 字段

当前支持 evolution loop 的 Skill：
- `cc-code-writer`（Phase 1 实施）
- `eval`（Phase 2 计划）
