<!-- ⛔ 修改前必须先补 golden-set 测试用例（P3 #4 / 审计报告 2026-04-06）
     原因: 迭代模式是 planner 最复杂的代码路径但零测试覆盖。
     最少 3 个用例: 单轮达标 / 多轮收敛 / 停滞终止。
     位置: eval/golden-sets/cc-planner.yaml -->

## evaluate

# Phase 5: 评估工作流（Evaluate）— 迭代循环模式专用

> **仅在 `iteration_mode: evaluator-optimizer` 时执行**。`single-pass` 模式或 `iteration_mode` 字段缺失时跳过本阶段。

## 迭代循环模式概述

> 在现有 RIPER 单向流水线外层包裹 Evaluator-Optimizer 循环，支持"测试→规划→执行→验证→不满意则继续迭代"的无限循环模式。
> 设计文档：vault/my_claude/需求/Planner无限迭代循环模式/技术设计文档.md

### 激活条件

用户在 prompt 中表达"持续改进直到..."、"迭代测试直到..."、"循环优化..."，或 RESEARCH 阶段判断任务适合迭代。

### 新增文件

- `goal.md`（workspace 内，迭代专用附加文件，不改变五文件体系）：定义最终目标、评估标准、终止条件、risk_profile

### 阶段流转

```
单次模式（默认）: RESEARCH → PLAN → EXECUTE → REVIEW → 完成
迭代模式:
  首轮: RESEARCH → PLAN → EXECUTE → REVIEW → EVALUATE
  后续: [PLAN/RESEARCH] → ... → REVIEW → EVALUATE
  回退: EVALUATE FAIL → PLAN（默认）或 RESEARCH（深回退）
  终止: EVALUATE PASS / max_iterations / 停滞 / 趋势预测 / 用户中断
```

### 门控扩展

| # | 门控点 | 说明 |
|---|--------|------|
| G6 | EVALUATE 完成 | goal.md 评估记录已写入（仅迭代模式） |

### 关键设计决策

- **两级回退**：PLAN（默认）/ RESEARCH（深），无 EXECUTE 级浅回退
- **动态策略决策**：`strategy_mode: auto` 根据分数趋势判断 refine（深化）vs pivot（转向），替代静态开关
- **risk_profile**：`exploratory`（pivot 自动执行，默认 10 轮）/ `production`（pivot 等确认，默认 5 轮）
- **评估器隔离**：独立 subagent，不传思考过程，rules-based 权重 >= 50%，**必须工具调用验证禁止纯推理**
- **方向性反馈**：EVALUATE 产出结构化 Insights（维度+模式+方向性建议），写入 findings.md 供下一轮 PLAN 参考
- **归档策略**：每轮结束时 plan.md/spec.md 压缩归档到 progress.md 后覆盖

---
> **目标**：独立评估是否达成最终目标，判断 PASS/FAIL 和回退深度 | **权限**：只读 + 运行验证命令

| 操作 | 允许 |
|------|------|
| 读取代码/文档、运行验证命令/脚本、读写 workspace 五文件 + goal.md | Y |
| 修改源代码 | N |

---

## 与 REVIEW 的区别

| 维度 | REVIEW（现有） | EVALUATE（本阶段） |
|------|---------------|-------------------|
| **位置** | RIPER 第四阶段 | 迭代循环的外层判断点，在 REVIEW 之后 |
| **评估对象** | 本轮执行的代码质量和计划符合性 | 是否达成最终目标（goal.md） |
| **评估标准** | spec.md 的 AC + 测试通过 + 代码质量 | goal.md 的评估标准 |
| **产出** | 审查报告（通过/不通过） | PASS/FAIL + 反馈 + 回退深度 |
| **失败处理** | 返回 EXECUTE 修复 | 根据回退深度返回 RESEARCH 或 PLAN |

---

## 前置条件

1. REVIEW 阶段已完成
2. `{workspace}/session.yaml` 中 `iteration_mode == "evaluator-optimizer"`
3. `{workspace}/goal.md` 存在且含评估标准

> **守卫条件**：`iteration_mode` 字段缺失或值为 `"single-pass"` → 跳过 EVALUATE，REVIEW 完成即结束。

---

## 工作流程

### Step 1: 读取目标与历史

```yaml
读取:
  - "{workspace}/goal.md" 评估标准表
  - "{workspace}/session.yaml" iteration.history（了解历史评估分数和趋势）
  - "{workspace}/progress.md" 最近一段（了解本轮执行了什么）
```

### Step 2: 执行评估（独立 subagent）

派发独立 `general-purpose` subagent 执行评估。**评估器隔离规则**：

1. subagent 只接收 `goal.md` + 当前产出物（代码/文档/测试结果），**不接收 plan.md 和思考过程**
2. subagent prompt 中包含"你是独立评估者，不是执行者的队友"的角色设定
3. `rules-based` 标准：subagent **必须**实际运行验证命令（工具调用），以命令输出为准。**禁止用推理替代执行**
4. `llm-as-judge` 标准：subagent **必须**先用 Read 工具读取实际产出物，再评分。prompt 采用 **Phase A/B 两阶段分离**（发现与判定分离，详见 prompt 模板）
5. `manual` 标准：subagent 标记为"待用户确认"，由主 agent 询问用户。**评分规则**：用户确认前该标准不计入加权总分（权重按比例分配到其他标准），不阻塞 PASS 判断；用户确认后补入分数并重新计算
6. subagent **额外输出结构化 Insights**（从评估结果中提炼跨轮次模式）：
   ```yaml
   insights:
     - dimension: "[评估维度]"
       pattern: "[反复出现的问题模式]"
       frequency: N  # 跨轮次出现次数
       suggestion: "[方向性建议——不只说'哪里不够好'，还说'往哪个方向走']"
   ```

> **强制约束**：goal.md 中 `rules-based` 类型权重合计 >= 50%。不满足时在 Step 1 输出警告并要求用户调整。

### Step 3: 计算评分

```yaml
每条标准:
  score: 0-5（subagent 评分或命令输出映射）
  status: ✅ 通过 / ❌ 未通过

加权总分: Σ(标准分数 × 权重)
```

### Step 3.5: Meta-Evaluation 偏差检测（P4）

> 三层递进检测：零成本规则触发 → 按需反面验证 → 仅异常时仲裁。
> 设计文档：vault/my_claude/需求/Planner无限迭代循环模式/P4-评估器偏差检测-设计文档.md
> 方法论参考：通用/方法论/Agent上下文工程方法论-2026.md §方法论七

**前置条件**：`meta_eval_enabled == true`（goal.md 配置，默认 true）。为 false 时跳过整个 Step 3.5。

#### Layer 0: 规则触发器（每轮自动，零成本）

Step 3 计算完评分后，执行以下三个检查（仅计算，不派发 subagent）：

```yaml
meta_evaluation_triggers:
  R1_score_gap:
    description: "rules-based 与 llm-as-judge 加权均分差异过大"
    前置条件: llm-as-judge 标准数量 >= 1 且 rules-based 标准数量 >= 1（否则跳过）
    计算方法:
      - 排除 manual 标准（使用各类型的原始权重，不受 manual 待确认时的权重重分配影响）
      - rules_avg = Σ(rules-based 标准分数 × 原始权重) / Σ(rules-based 原始权重)
      - llm_avg = Σ(llm-as-judge 标准分数 × 原始权重) / Σ(llm-as-judge 原始权重)
      - gap = llm_avg - rules_avg
    触发条件: gap > r1_gap_threshold（默认 1.5；单个 llm-as-judge 标准时放宽至 2.0，标注"低置信度"）

  R2_consecutive_high:
    description: "连续 2 轮 llm-as-judge 均分接近满分"
    前置条件: iteration.current >= 2（首轮不触发）
    计算方法: 从 session.yaml iteration.history 取最近 2 轮的 llm-as-judge 均分
    触发条件: 最近 2 轮 llm_avg 均 >= r2_high_threshold（默认 4.8）
    冷却机制: R2 触发且 L1 验证通过后，设 r2_cooldown_until = current_iteration + 2，冷却期内不再触发

  R3_score_jump:
    description: "单轮 llm-as-judge 均分异常跳变"
    前置条件: iteration.current >= 3（需足够历史数据）
    计算方法:
      - 取所有历史轮次的 llm_avg，计算 mean 和 std
      - jump = |当前轮 llm_avg - mean|
    触发条件: jump > r3_sigma_multiplier × std（默认 2σ）且 std > 0
```

**L0 输出**（追加到评估报告，无论是否触发）：

```markdown
## Meta-Evaluation 检查

| 触发器 | 状态 | 值 | 阈值 | 备注 |
|--------|------|-----|------|------|
| R1 分差检测 | ⚠️/✅/⏭️ | gap=X.X | >1.5 | ⏭️=跳过（前置条件不满足） |
| R2 连续满分 | ⚠️/✅/⏭️ | [X.X, X.X] | >=4.8 | |
| R3 分数跳变 | ⚠️/✅/⏭️ | jump=X.X, 2σ=X.X | >2σ | |
```

**触发任一** → 进入 Layer 1。**全部通过/跳过** → 直接进入 Step 4。

#### Layer 1: 反面验证重评（L0 触发时，0.3x-0.7x 额外成本）

派发第二个独立 `general-purpose` subagent（不共享 Step 2 subagent 的上下文）。**仅重评 llm-as-judge 标准**（rules-based 分数作为客观锚点保持不变）。

```markdown
# Layer 1 审计 subagent prompt

你是一个严格的质量审计员。你的任务是找出产出物中的问题，而非证明它有多好。

## 审计目标
{goal_description}

## 审计标准（仅重评以下 llm-as-judge 标准）
{triggered_llm_criteria_only}

> rules-based 标准的分数作为客观锚点保持不变，不在审计范围内。

## 当前产出物
{current_deliverables}

## 约束
- 你是独立审计员，不是执行者的队友，也不是之前评估者的队友
- **⛔ 发现与判定分离**：与主评估者相同，必须先输出 Phase A（纯证据），再输出 Phase B（评分）
- 必须用 Read 工具读取实际产出物，再评分
- 如果证据不足以给出明确评分，返回 "Unknown"（不强制打分）
- 输出不超过 100 行

## 输出格式

### Phase A: 审计发现

| # | 标准 | 不符合证据 | 符合证据 |
|---|------|-----------|---------|

### Phase B: 审计评分（基于 Phase A）

| # | 标准 | 分数 | 判定依据 |
|---|------|------|---------|
```

**结果对比**（逐标准）：

```yaml
for each llm_criterion:
  delta = |original_score - audit_score|
  if delta <= 1.0:
    verdict: "L1 验证通过"
    action: 采信原评分
  else:
    verdict: "L1 验证失败——评分显著分歧"
    action: 该标准进入 Layer 2 仲裁
```

L1 输出：`🔍 Meta-Eval L1: {N} 个标准重评，通过 {P}，分歧 {F}`

#### Layer 2: 分数仲裁（L1 升级时）

**仲裁粒度：按标准级别**。仅处理 L1 验证失败的 llm-as-judge 标准。

```yaml
仲裁逻辑:
  for each failed_criterion:
    arbitration_strategy（来自 goal.md 配置，默认 "min"）:
      - "min": arbitrated_score = min(original_score, audit_score)
        # 两个 LLM 的宽容偏差方向一致，取较低分更安全
      - "mean": arbitrated_score = (original_score + audit_score) / 2
      - "weighted": arbitrated_score = original_score × 0.4 + audit_score × 0.6

  # 用仲裁后的标准分数重算加权总分
  new_weighted_total = Σ(各标准最终分数 × 权重)
  # 未被仲裁的标准保持原分数

  # 记录偏差事件
  session.yaml → iteration.bias_events 追加:
    - iteration: N
      trigger: "R1/R2/R3"
      criteria_arbitrated:
        - criterion: "标准名"
          original_score: X.X
          audit_score: X.X
          arbitrated_score: X.X
      original_weighted_total: X.X
      arbitrated_weighted_total: X.X

  # 处理
  risk_profile == "production":
    - 输出偏差报告（逐标准两次评分对比 + 证据摘要）
    - 暂停等用户确认：A=原评分 / B=仲裁分数 / C=审计分数
  risk_profile == "exploratory":
    - 自动采用仲裁分数（arbitrated_weighted_total）
    - 输出："⚠️ Meta-Eval L2: 原总分 X.X → 仲裁后 X.X（策略: min）"
    - 用仲裁后的加权总分替代原总分，继续 Step 4
```

---

### Step 4: 判断 PASS/FAIL

```yaml
PASS 条件（全部满足）:
  - 加权总分 >= goal.md 的 min_score
  - 无 0 分项
  - Sprint Contract TB 全部通过（如存在 spec.md 冲刺合同）

Sprint Contract 检查（spec.md 含 "## 冲刺合同" 时执行）:
  读取 spec.md 冲刺合同的 Testable Behaviors 表
  for each TB where 状态 == "🟢 agreed":
    if TB.类型 == "rules-based":
      → 必须执行验证命令（工具调用），以实际输出判定 PASS/FAIL
    if TB.类型 == "llm-as-judge":
      → 读取产出物后评估，按 TB.阈值 判定
    if 任一 TB FAIL:
      → 整个 sprint FAIL（per-criterion 硬阈值，不依赖加权总分）
      → 反馈中标注具体 TB 编号 + 失败原因 + 验证命令输出

  TB 结果写入 goal.md 迭代记录（补充在标准评分表之后）:
    | TB# | 行为 | 结果 | 验证输出摘要 |
    |-----|------|------|-------------|

FAIL:
  - 生成反馈（每条未通过标准的具体原因 + 未通过 TB 的具体原因）
  - 判断回退深度（见下方）
```

### Step 5: 终止条件检查（FAIL 时执行）

在判断回退深度之前，先检查是否应该终止循环：

```yaml
终止条件检查（按优先级）:
  1. 达到 max_iterations → 终止，输出当前状态 + 未达标项
  2. 停滞检测 → 连续 stagnation_rounds 轮评分变化 < 0.1：
     - strategy_mode == "auto" 且**首次停滞** → 不终止，交给 Step 6 处理（SUGGEST_PIVOT）
     - strategy_mode == "auto" 且**pivot 后仍停滞**（第二轮连续 δ<0.1） → 终止
     - strategy_mode != "auto" → 终止，建议调整目标
  3. Pivot 有效性检查（P2） → 上轮 strategy_applied == "pivot" 且本轮分数未改善 → 输出"pivot 无效"警告，建议终止或回退 RESEARCH
  4. 趋势预测 → 首尾斜率估算预测剩余轮次无法达标 → 告警（非强制停止，输出预测供用户决策）
  5. 超时 → 总耗时 >= max_time_minutes → 终止（强制停止）
  6. 以上均未触发 → 继续迭代
```

**停滞检测算法**：

```python
def is_stagnated(history, stagnation_rounds):
    if len(history) < stagnation_rounds + 1:
        return False
    recent = history[-stagnation_rounds:]
    baseline = history[-(stagnation_rounds + 1)].weighted_score
    return all(abs(h.weighted_score - baseline) < 0.1 for h in recent)
```

**趋势预测**（启发式，>= 3 轮数据时启用，仅供参考不强制终止）：

```python
def predict_can_reach_goal(history, max_iterations, min_score):
    if len(history) < 3:
        return True  # 数据不足，不预测
    scores = [h.weighted_score for h in history]
    # 首尾斜率估算（非严格线性回归，数据点少时足够）
    slope = (scores[-1] - scores[0]) / (len(scores) - 1)
    remaining = max_iterations - len(history)
    predicted_final = scores[-1] + slope * remaining
    return predicted_final >= min_score
```

### Step 6: 动态策略决策（refine vs pivot）

> 核心洞察（来源 Anthropic GAN Harness）："generator 根据分数趋势决定是深化当前方向还是完全换一个方向"

```yaml
strategy_decision（strategy_mode: auto 时执行）:
  
  # 读取分数趋势
  prev_score: session.yaml → iteration.history[-1].weighted_score（上轮）
  curr_score: 本轮加权总分
  delta: curr_score - prev_score
  
  # 趋势判断（按优先级，从严到宽）
  - delta < -0.3 → FORCE_PIVOT（大幅下降，强制换方向）
    action:
      - risk_profile == "exploratory" → 自动 pivot
      - risk_profile == "production" → 输出强制 pivot 建议，等用户确认

  - |delta| < 0.1 → SUGGEST_PIVOT（停滞，建议换方向）
    action: 
      - risk_profile == "exploratory" → 自动 pivot，PLAN 收到 insights + "尝试全新方向"
      - risk_profile == "production" → 输出 pivot 建议，等用户确认

  - delta > 0 → REFINE（趋势上升，深化当前方向）
    action: 回退到 PLAN，PLAN 阶段收到指令"在当前方向上深化"

  - 兜底（delta 在 [-0.3, -0.1) 区间，即小幅下降） → REFINE + 警告
    action: 回退到 PLAN 深化当前方向，但输出警告"分数小幅下降，如连续 2 轮下降将触发 FORCE_PIVOT"

  # strategy_mode 非 auto 时的行为
  - refine-only → 始终 REFINE（无论分数趋势）
  - allow-pivot → 按 auto 逻辑但跳过用户确认（即使 production）
```

### Step 7: 回退深度判断（两级）

```yaml
regression_depth_decision:
  # 优先检查深度条件
  - condition: "评估反馈/insights 中出现：假设不成立 / 理解偏差 / 需要重新研究 / 目标需调整"
    depth: RESEARCH
    confirmation: 始终等用户确认（不受 risk_profile 影响）

  # 默认中度（最浅回退）
  - condition: "其他所有情况"
    depth: PLAN
    confirmation: 由 Step 6 的策略决策结果决定（refine 自动 / pivot 按 risk_profile）
```

### Step 7.5: Insights 写入 findings.md

```yaml
# 7.5a: EVALUATE subagent insights（原有）
将 EVALUATE subagent 输出的 insights 追加到 findings.md 的"策略进化"章节:
  - 新增 insights 追加到末尾
  - 已有 insights 更新 frequency（跨轮次出现次数 +1）
  - insights 供下一轮 PLAN 阶段参考（PLAN 读 findings.md 时自动获取方向性建议）

# 7.5b: Sprint Contract TB 失败 → insight 转化（spec.md 含冲刺合同时执行）
# 转化规则详见 shared-rules/evolution-loop-protocol.md §六
将 Step 4 中失败的 TB 转化为 insights 并追加:
  for each failed_tb:
    - 检查 findings.md 是否已有 "INS-TB-{tb_id}" → 有则 frequency += 1
    - 无则新增 insight（dimension 按 TB 行为类型映射九维度，severity = P1）
    - insight.root_cause 填入验证命令的实际输出摘要（非推理）
  TB insights 与 EVALUATE subagent insights 合并后统一写入 findings.md
```

### Step 8: 更新迭代状态 + 归档

```yaml
更新 goal.md:
  - 追加本轮 Iteration 记录（分数 + 反馈 + 回退深度）

更新 session.yaml:
  - iteration.current += 1
  - iteration.history 追加本轮记录

归档流程（仅 FAIL 时执行）:
  1. 从 plan.md 提取：方案选择 + 任务完成状态表 + 关键偏差
  2. 从 spec.md 提取：AC 达成状态 + 决策记录
  3. progress.md 增长控制（P3）:
     - 如果 iteration.current > 3，将 progress.md 中第 1 ~ (current-3) 轮的完整归档压缩为摘要行：
       `### Iteration N 摘要 | 分数: X.X/5 | 方案: [一句话]`
     - 保留最近 3 轮完整归档
  4. 合并写入 progress.md（追加模式，使用 iteration-archive-template）
  5. 覆盖 plan.md / spec.md 为空（等待下一轮 PLAN 填充）

PASS 时:
  - 输出最终报告（总轮次 + 分数变化趋势 + 关键改进点）
  - 更新 session.yaml status 为 "completed"
```

---

## EVALUATE subagent prompt 模板

```markdown
你是一个独立评估者。你的任务是评估当前产出物是否达成目标，不是帮助执行者辩护。

## 评估目标
{goal_description}

## 评估标准
{evaluation_criteria_table}

## 当前产出物
{current_deliverables}

## 约束
- 你是独立评估者，不是执行者的队友
- rules-based 标准：**必须**运行指定命令/脚本（工具调用），以实际输出为准。**禁止用推理替代执行**
- llm-as-judge 标准：**必须**先用 Read 工具读取实际产出物，再评分
- manual 标准：标记为"待用户确认"，不自行判断
- 幻觉防护：引用的文件路径、函数名必须来自 Read 工具确认
- 输出不超过 200 行
- **⛔ 发现与判定分离（反自我合理化）**：必须严格按 Phase A → Phase B 顺序输出。Phase A 完成前禁止出现任何分数。Phase B 中不得推翻、淡化或重新解释 Phase A 已记录的问题

## 输出格式

### Phase A: 发现报告（纯证据，无评分）

逐条标准收集证据，每条列出：

| # | 标准 | 不符合证据 | 符合证据 |
|---|------|-----------|---------|
| 1 | [标准描述] | [具体的不符合事实] | [具体的符合事实] |

> Phase A 规则：
> - 只记录观察到的事实和证据，不做"是否严重""是否可接受"的判断
> - 发现了问题就写，不要自我说服"这不算大问题"
> - 不符合证据和符合证据**必须分列**，禁止在同一单元格内用转折连接词（但是/不过/虽然）混合正反面

### Phase B: 评分判定（基于 Phase A 证据）

基于上方发现报告逐条评分：

| # | 标准 | 分数 | 状态 | 判定依据 |
|---|------|------|------|---------|
| 1 | [标准描述] | X/5 | ✅/❌ | [引用 Phase A 第 N 条证据 → 评分理由] |

> Phase B 规则：
> - 每条评分必须显式引用 Phase A 的证据编号
> - Phase A 中每条**不符合证据**必须在 Phase B 被显式回应（要么扣分，要么给出不扣分的充分理由）。遗漏的 Phase A 发现视为审查缺陷
> - 如果 Phase A 记录了问题但 Phase B 给了高分，必须给出充分理由（不能忽略）

**加权总分**: X.X/5
**建议回退深度**: [RESEARCH/PLAN]
**回退理由**: [一句话]

## 语义漂移检测（P1 — 防止多轮迭代后方案偏离原始目标）
当前方案与 goal.md 原始目标描述的语义一致性: X/5
（5=完全服务于目标 / 3=部分偏离 / 1=严重偏离。< 3 时建议回退 RESEARCH）

## 抽样深度验证（P5 — 防止 Reward Hacking）
随机选择一个 llm-as-judge 标准，深入验证其实际质量:
- 抽中标准: [标准名]
- 深入验证结果: [读代码/文档后的具体证据]
- 是否与评分一致: [是/否，如不一致说明原因]

## Insights（方向性反馈——不只说"哪里不好"，还说"往哪走"）

| # | 维度 | 模式 | 出现次数 | 方向性建议 |
|---|------|------|---------|----------|
| 1 | [维度] | [反复出现的问题模式] | N | [建议往哪个方向探索] |
```

---

## 超时保护

```yaml
计时基准: session.yaml → iteration.history[0].started_at（首轮开始时间）
计算方式: 当前时间 - 首轮开始时间 = 已用时间

超时检查（每轮 EVALUATE Step 5 执行）:
  - 已用时间 >= max_time_minutes × 80% → 输出警告
  - 已用时间 >= max_time_minutes → 完成当前任务后强制停止（不中断正在执行的操作）

注意: compact 不影响计时（时间戳在 session.yaml 文件中，不在对话上下文中）
```

---

## 阶段完成标准

- [ ] goal.md 迭代记录已写入
- [ ] session.yaml iteration.history 已更新
- [ ] PASS: 最终报告已输出 / FAIL: 归档已完成 + 回退深度已判断
- [ ] 终止条件已检查（未触发才继续迭代）
