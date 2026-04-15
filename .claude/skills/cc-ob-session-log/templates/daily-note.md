---
date: {{YYYY-MM-DD}}
type: daily_note
tags:
  - daily-note
sessions: {{session_count}}
---

# {{YYYY-MM-DD}} 工作日志

> 由 cc-ob-session-log 自动记录。每次会话追加新条目到"会话记录"章节。

## 今日上下文

> 可选：从最近的 weekly/monthly review 自动拉取（级联上下文注入，来自 obsidian-claude-pkm 社区洞察）

- **本周 ONE Big Thing**: {{从 vault/weekly-reviews/ 最新一期提取，无则留空}}
- **本月焦点**: {{从 vault/monthly-reviews/ 最新一期提取，无则留空}}

---

## 会话记录

### 会话 1 — {{HH:mm}} | {{project}} | {{branch}}

**目标**: {{session_goal}}
**类型**: {{dev|debug|design|research|meeting|learning}}
**状态**: {{completed|in_progress|blocked}}

#### 工作摘要
- {{bullet 1}}
- {{bullet 2}}
- {{bullet 3}}

#### 决策记录
<!-- 仅有决策时填。决策理由展开由 cc-kb-sync 负责沉淀到基线文档。 -->

| 决策 | 选择 | 被否决方案 | 1 行理由 |
|------|------|-----------|---------|
| {{decision}} | {{choice}} | {{rejected}} | {{rationale}} |

#### 发现与洞察
<!-- 索引级（1 行摘要）。详细论证由 cc-kb-sync 沉淀到基线。 -->

- **{{discovery_title}}**: {{brief_1_line}}

#### 错误与修复
<!-- 仅有错误修复时填。 -->

| 错误 | 根因 | 修复方式 |
|------|------|---------|
| {{error}} | {{root_cause}} | {{fix}} |

#### 工具使用
<!-- 可选。仅当工具使用模式值得关注时记录。 -->

- 激活 Skill: {{activated_skills}}
- 派发 Agent: {{dispatched_agents}}
- 主要工具调用: {{tool_call_summary}}

#### Skill 效果观察
<!-- 从 .claude/observatory/ 数据自动填充。无数据时留空或标注"无观测数据"。 -->

| Skill | 有用? | 摩擦点 |
|-------|-------|--------|
| {{skill_name}} | {{yes/no/partial}} | {{friction_note or 无}} |

#### 下次上下文
> {{next_session_context}}

#### 待办
- [ ] {{todo_1}}
- [ ] {{todo_2}}

---

<!--
新会话追加格式：

### 会话 2 — {{HH:mm}} | ...

（同上结构，在上面一条的下方追加）
-->

## 今日统计

<!-- 可选：由 cc-ob-aggregate 周报流程或用户手动统计时填充 -->

- 会话数: {{session_count}}
- 总工具调用: {{total_tool_calls}}
- 涉及项目: {{projects_list}}
- 主要类型分布: {{type_distribution}}
