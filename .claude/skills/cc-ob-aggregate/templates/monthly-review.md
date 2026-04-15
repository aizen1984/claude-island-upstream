---
date_range: {{YYYY-MM-DD}} — {{YYYY-MM-DD}}
month: {{YYYY-MM}}
type: monthly_review
tags:
  - monthly-review
covered_weeks:
  - {{YYYY-WNN}}
  - {{YYYY-WNN}}
  - {{YYYY-WNN}}
  - {{YYYY-WNN}}
weekly_reviews_input: {{N}}
---

# 月报 — {{YYYY 年 MM 月}}

> 数据来源：{{N}} 周周报 | 涉及 daily notes: {{daily_count}} | 总会话：{{session_count}}
> 核心原则：聚焦跨周趋势，不复述周内细节

---

## 📊 月度统计

### 工作类型变化

| 类型 | W1 | W2 | W3 | W4 | 月均 | vs 上月 |
|------|----|----|----|----|------|---------|
| 开发 | {{%}} | {{%}} | {{%}} | {{%}} | {{%}} | {{↑↓→ N%}} |
| 排障 | {{%}} | {{%}} | {{%}} | {{%}} | {{%}} | {{↑↓→ N%}} |
| 设计 | {{%}} | {{%}} | {{%}} | {{%}} | {{%}} | {{↑↓→ N%}} |
| 调研 | {{%}} | {{%}} | {{%}} | {{%}} | {{%}} | {{↑↓→ N%}} |

### 项目投入分布

| 项目 | 投入占比 | vs 上月 | 主要产出 |
|------|---------|---------|---------|
| {{project_1}} | {{%}} | {{↑↓→}} | {{summary}} |

---

## 🔄 跨周趋势分析

> 问题 1: "这些模式说明了什么趋势？"

### 持续模式（连续多周出现）

1. **{{persistent_pattern_1}}**: 连续 {{N}} 周出现
   - **周次轨迹**: W1 提及 2 次 → W2 提及 3 次 → W3 提及 5 次
   - **含义**: {{意味着什么}}
   - **建议**: {{是否需要系统性解决}}

2. **{{persistent_pattern_2}}**

### 新增模式（本月新出现）

1. **{{new_pattern_1}}**: 月中开始出现
   - **触发事件**: {{what triggered it}}
   - **是否会持续**: {{hypothesis}}

### 消失模式（上月有，本月没了）

1. **{{vanished_pattern_1}}**: 上月频繁，本月消失
   - **可能原因**: {{解决了 | 优先级下降 | 被遗忘}}
   - **是否需要关注**: {{yes/no}}

> 问题 2: "工作分布变化意味着什么？"

### 分布变化解读

- **{{change_1}}**: {{dev 占比从 50% 降到 30%}}
  - **原因假设**: {{项目阶段变化 | 新排障需求 | 学习投入增加}}
  - **是否符合预期**: {{yes/no}}

---

## 🧭 战略反思

> 问题 3: "方向是否需要调整？"

### 方向评估

- **当前方向**: {{direction_description}}
- **本月进展**:
  - 推进的: {{what moved forward}}
  - 停滞的: {{what got stuck}}
- **是否需要调整**: {{yes/no}}
- **理由**: {{reasoning}}

### 元模式发现（决策/问题解决/学习模式）

> 问题 4: "我倾向于如何做决策/解决问题？"

1. **决策模式**: {{how I tend to make decisions}}
   - **证据**: 本月 {{N}} 个决策中 {{M}} 个采用此模式
   - **是否有效**: {{evaluation}}

2. **问题解决模式**: {{how I tackle problems}}

3. **学习模式**: {{how I absorb new knowledge}}

---

## 📈 知识增长热区

> 基于 daily notes 的知识领域扩展，可选内嵌 spark 发现

- **{{domain_1}}**: {{growth_description}}
  - 新增笔记: {{N}} 篇
  - 新增 wikilink: {{N}} 个
  - 涉及项目: {{projects}}

- **{{domain_2}}**: {{growth_description}}

---

## 🎯 下月规划

### 主要目标（1-3 个）

1. **{{goal_1}}**
   - **为什么**: {{rationale}}
   - **成功标准**: {{criteria}}
   - **时间分配**: {{estimated weeks}}

### 三层优先级

**Must (必须)**:
- {{must_1}}

**Should (应该)**:
- {{should_1}}

**Nice-to-have (可选)**:
- {{nice_1}}

### 预防性行动（基于本月阻碍模式）

1. **{{preventive_1}}** — 防止本月 {{blocker}} 再次发生
2. **{{preventive_2}}**

### 战略调整（基于跨周趋势）

1. **{{adjustment_1}}**: {{from_state}} → {{to_state}}
   - **理由**: {{trend_rationale}}

---

## 📚 建议固化到知识库

> 本月产生的可沉淀洞察，建议执行 cc-kb-sync

| 洞察 | 目标位置 | 优先级 |
|------|---------|--------|
| {{insight_1}} | `vault/{{project}}/基线文档/{{topic}}.md` | P0 |
| {{insight_2}} | `vault/通用/方法论/{{topic}}.md` | P1 |

---

## 📎 引用的周报

- [[weekly-reviews/{{YYYY-W01}}]]
- [[weekly-reviews/{{YYYY-W02}}]]
- [[weekly-reviews/{{YYYY-W03}}]]
- [[weekly-reviews/{{YYYY-W04}}]]

---

## 📝 下月月报时间

下次聚合: {{next_monthly_date}}
