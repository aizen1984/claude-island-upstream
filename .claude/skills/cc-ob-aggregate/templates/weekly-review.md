---
date_range: {{YYYY-MM-DD}} — {{YYYY-MM-DD}}
week: {{YYYY-WNN}}
type: weekly_review
tags:
  - weekly-review
covered_dates:
  - {{date_1}}
  - {{date_2}}
  - {{date_3}}
  - {{date_4}}
  - {{date_5}}
sessions_analyzed: {{N}}
---

# 周报 — {{YYYY 年第 NN 周}}（{{YYYY-MM-DD}} — {{YYYY-MM-DD}}）

> 数据来源：{{N}} 天 daily notes | 会话数：{{count}} | 工具调用：{{tool_calls}}
> 核心原则：问题驱动，非机械汇总

---

## 📊 本周统计

### 工作类型分布

| 类型 | 会话数 | 占比 | 趋势（vs 上周） |
|------|-------|------|----------------|
| 开发 | {{N}} | {{%}} | {{↑↓→}} |
| 排障 | {{N}} | {{%}} | {{↑↓→}} |
| 设计 | {{N}} | {{%}} | {{↑↓→}} |
| 调研 | {{N}} | {{%}} | {{↑↓→}} |
| 会议 | {{N}} | {{%}} | {{↑↓→}} |
| 学习 | {{N}} | {{%}} | {{↑↓→}} |

### 项目分布

| 项目 | 会话数 | 占比 | 主要工作 |
|------|-------|------|---------|
| {{project_1}} | {{N}} | {{%}} | {{summary}} |
| {{project_2}} | {{N}} | {{%}} | {{summary}} |

---

## 🔍 本周模式

> 问题 1: "这周反复出现了什么？"

### 反复出现的主题

1. **{{pattern_1}}**: 出现 {{N}} 次
   - **证据**: [[{{daily_note_1}}]], [[{{daily_note_2}}]], [[{{daily_note_3}}]]
   - **含义**: {{interpretation}}
   - **类型**: {{开发聚焦 | 技术难点 | 反复排障 | 持续探索}}

2. **{{pattern_2}}**: 出现 {{N}} 次
   ...

> 问题 2: "什么阻碍最频繁？根因假设是什么？"

### 最频繁的阻碍

| # | 阻碍 | 频率 | 涉及 daily notes | 根因假设 | 建议行动 |
|---|------|------|-----------------|---------|---------|
| 1 | {{blocker_1}} | {{N}} 次 | [[...]] | {{hypothesis}} | {{action}} |
| 2 | {{blocker_2}} | {{N}} 次 | [[...]] | {{hypothesis}} | {{action}} |

> 问题 3: "哪些决策的结果值得反思？"

### 决策回顾

| 决策 | 时间 | 结果 | 反思 | 是否需要调整 |
|------|------|------|------|-------------|
| {{decision_1}} | {{date}} | {{outcome}} | {{reflection}} | {{yes/no}} |

---

## 💡 本周洞察

> 不是"做了什么"，而是"学到了什么"。每条洞察必须引用具体 daily note 证据。

### 洞察 1: {{insight_title}}

**观察**: {{what you noticed}}

**证据**:
- [[{{daily_note}}]] — {{evidence_quote}}
- [[{{daily_note}}]] — {{evidence_quote}}

**含义**: {{interpretation}}

**可行动**: {{yes/no}}，如何行动？{{action}}

---

### 洞察 2: {{insight_title}}
（同上）

---

## 🎯 下周焦点

### 必须完成（基于本周阻塞项）

1. **{{must_do_1}}**
   - 为什么：{{reason}}
   - 成功标准：{{criteria}}

2. **{{must_do_2}}**

### 应该关注（基于本周模式）

1. **{{should_focus_1}}** — 基于 "{{pattern}}" 模式
2. **{{should_focus_2}}**

### 可以探索（基于 spark 发现，可选）

> 如本周执行了 `/weekly --with-spark`，此处展示发现的知识簇

1. **{{could_explore_1}}** — 发现的新兴主题：{{theme}}

### 预防性行动（基于本周阻碍模式）

1. **{{preventive_1}}** — 防止 "{{blocker}}" 再次出现

---

## 📚 本周沉淀到知识库

> 如果本周有需要固化的高价值洞察，列在此处并执行 cc-kb-sync

- [ ] **{{insight_to_sync_1}}** → 建议沉淀到 `vault/{{project}}/基线文档/{{topic}}.md`
- [ ] **{{insight_to_sync_2}}** → 建议沉淀到 `vault/通用/方法论/{{topic}}.md`

---

## 📎 引用的 daily notes

- [[daily-notes/{{date_1}}]]
- [[daily-notes/{{date_2}}]]
- [[daily-notes/{{date_3}}]]
- [[daily-notes/{{date_4}}]]
- [[daily-notes/{{date_5}}]]

---

## 📝 下周周报时间

下次聚合: {{next_weekly_date}}
