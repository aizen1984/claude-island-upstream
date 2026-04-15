# 迭代目标模板

> 仅在迭代循环模式（`iteration_mode: evaluator-optimizer`）下使用。
> goal.md 是迭代专用附加文件，不改变五文件体系。

---

## goal-template

```markdown
# [功能名称] 迭代目标

> 迭代模式：evaluator-optimizer
> 创建时间：YYYY-MM-DD HH:mm

---

## 目标描述

[一段话描述最终想要达到的效果]

## 评估标准

| # | 标准 | 类型 | 验证方法 | 权重 | 当前状态 |
|---|------|------|---------|------|---------|
| 1 | [标准描述] | rules-based | [运行命令/脚本] | 40% | ⬜ |
| 2 | [标准描述] | llm-as-judge | [评估 prompt 摘要] | 30% | ⬜ |
| 3 | [标准描述] | rules-based | [运行命令/脚本] | 30% | ⬜ |

> **强制约束**：`rules-based` 类型权重合计 >= 50%，防止 llm-as-judge 占比过高导致系统性偏乐观。

## 终止条件

| 条件 | 值 | 说明 |
|------|-----|------|
| max_iterations | 10 | 最大迭代轮次（production 场景建议 5） |
| min_score | 4.0 | 加权总分达标线（0-5） |
| stagnation_rounds | 2 | 连续 N 轮评分无改善（δ < 0.1）则停止 |
| max_time_minutes | 120 | 最大总耗时 |

## 迭代策略

| 配置 | 值 | 说明 |
|------|-----|------|
| strategy_mode | auto | `auto`=根据分数趋势动态判断 refine/pivot / `refine-only`=只深化不转向 / `allow-pivot`=允许转向 |
| risk_profile | exploratory | `exploratory`=放手试（pivot 自动执行）/ `production`=慎重（pivot 等用户确认） |
| ralph_per_iteration | false | 每轮 EXECUTE 是否使用 Ralph 持久模式 |

> **risk_profile 默认值推断规则**（用户不显式设时自动判断）：
> - EXECUTE 产出为文档/知识库/Skill 配置文件 → 默认 `exploratory`（max_iterations 默认 10）
> - EXECUTE 产出为项目源代码（src/、pom.xml 等） → 默认 `production`（max_iterations 默认 5）
>
> **strategy_mode: auto 决策逻辑**（EVALUATE 阶段 Step 6 执行）：
> - 分数趋势上升（本轮 > 上轮）→ **refine**（深化当前方向）
> - 分数停滞（|本轮 - 上轮| < 0.1）→ **建议 pivot**（建议换方向）
> - 分数下降（本轮 < 上轮 - 0.3）→ **强制 pivot**（必须换方向）

## 偏差检测配置（可选，有合理默认值）

| 配置 | 默认值 | 说明 |
|------|--------|------|
| meta_eval_enabled | true | 是否启用偏差检测（迭代模式下默认开启） |
| r1_gap_threshold | 1.5 | R1 分差阈值（单个 llm 标准时自动放宽至 2.0） |
| r2_high_threshold | 4.8 | R2 满分嫌疑阈值 |
| r3_sigma_multiplier | 2 | R3 跳变倍数 |
| arbitration_strategy | min | L2 仲裁策略：`min`=取较低分（默认，保守）/ `mean`=均值 / `weighted`=审计权重 0.6 |

> **何时调整**：如果偏差检测频繁误报（L0 触发但 L1 验证通过），可提高阈值；如果评估器持续虚高，可降低阈值或切换仲裁策略。

## 迭代记录

### Iteration 1

| 标准 | 分数 | 状态 | 反馈 |
|------|------|------|------|
| 标准 1 | -/5 | ⬜ | - |
| 标准 2 | -/5 | ⬜ | - |
| 标准 3 | -/5 | ⬜ | - |
| **加权总分** | **-/5** | - | - |

**评估结论**：[PASS/FAIL]
**回退深度**：[RESEARCH/PLAN/N/A]
**反馈摘要**：[评估者的关键反馈]
```

---

## iteration-archive-template

> 每轮迭代结束（EVALUATE FAIL → 进入下一轮前），从 plan.md/spec.md 提取关键信息归档到 progress.md。

```markdown
### Iteration N 归档 (YYYY-MM-DD HH:mm)

**方案**: [方案选择及原因]
**评估分数**: X.X/5 → FAIL
**回退深度**: [RESEARCH/PLAN]

**任务完成情况**:

| 任务 | 状态 | 备注 |
|------|------|------|
| [任务描述] | ✅/❌ | [备注] |

**AC 达成情况**:

| AC | 状态 |
|----|------|
| [AC 描述] | ✅/❌ 实际值 |

**关键决策**: [从 spec.md 决策记录提取]
**评估反馈**: [从 goal.md 迭代记录提取]
```
