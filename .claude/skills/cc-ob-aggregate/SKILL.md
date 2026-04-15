---
name: cc-ob-aggregate
description: 聚合Obsidian daily notes生成周报和月度综合报告（问题驱动，非机械汇总）。不写入项目知识库基线、不记录单次会话。用于知识沉淀循环、定期回顾、趋势分析
allowed-tools: Read, Write, Edit, Grep, Glob, Bash
---

# 递进式知识聚合

## Gotchas

> 从设计、对抗验证和方法论调研（GTD/Progressive Summarization/COG）中积累的陷阱。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 机械汇总（罗列完成事项） | 报告无价值，用户不看 | **问题驱动聚合**——每个层级由特定问题触发思考（"这周反复出现了什么？"而非"做了 A/B/C"）|
| 2 | Daily notes 格式不一致 | 聚合失败或遗漏 | 依赖 cc-ob-session-log 的统一模板；遇到非标准笔记降级为文本提取模式 |
| 3 | 时间范围内 daily notes 太少 | 无法提取有意义模式 | 少于 3 天数据时提示"数据不足，建议积累后再聚合" |
| 4 | 月报重复周报内容 | 冗余 | 月报聚焦**跨周趋势**，不复述周内细节 |
| 5 | 与 kb-sync 混淆边界 | 误将报告写入项目基线文档 | aggregate 只写 `weekly-reviews/` 和 `monthly-reviews/`，不触碰 `{项目}/基线文档/` |
| 6 | 连续两期报告重复分析相同 daily notes | 冗余分析浪费 token | frontmatter 含 `covered_dates` 字段，新期跳过已覆盖日期 |
| 7 | 只分析 daily notes 而忽视 spark 发现 | 错过知识洞察层 | 可选内嵌 cc-ob-spark 调用，将主题发现纳入聚合 |
| 8 | 用相对时间（"这周"）写入 frontmatter | 日后无法检索 | 使用绝对日期：`week: 2026-W14`，`date_range: 2026-04-06 — 2026-04-12` |

---

## 概述

cc-ob-aggregate 将日粒度 daily notes 递进式精炼为周报/月报。它是**知识飞轮**的结构精炼层——把零散的每日记录聚合为有洞察力的周期性综合。

**核心原则**：**问题驱动而非清单驱动**。每个层级由特定问题触发思考：

| 层级 | 输入 | 核心问题 | 输出 |
|------|------|---------|------|
| 日 → 周 | 7 天 daily notes | "这周反复出现了什么？什么阻碍最频繁？" | 模式 + 洞察 + 下周焦点 |
| 周 → 月 | 4 周周报 | "这些模式说明了什么趋势？方向需要调整吗？" | 趋势 + 战略建议 + 调整行动 |
| 月 → 季（可选）| 3 月月报 | "季度目标进展如何？需要重新校准吗？" | 目标评估 + 方向调整 |

**五步流程**：LOAD（加载）→ CLASSIFY（分类）→ PATTERN（模式识别）→ INSIGHT（洞察提取）→ ACTION（行动建议）

---

## 协作关系

- **接收自**: user（`/weekly` / `/monthly` 手动触发）
- **委托给**: cc-ob-spark（可选，将主题发现纳入聚合维度）
- **消费**: cc-ob-session-log 产出的 `vault/daily-notes/*.md`
- **产出**: `vault/weekly-reviews/YYYY-WNN.md` / `vault/monthly-reviews/YYYY-MM.md`

### 与相关 Skill 的区别

| 维度 | cc-ob-aggregate | cc-ob-session-log | cc-ob-spark | cc-kb-sync |
|------|----------------|-------------------|-------------|-----------|
| **时间维度** | 跨天（周/月） | 单次会话 | 跨天（可配置） | 单次会话 |
| **数据来源** | daily notes | 会话元数据 | vault 任何笔记 | 会话上下文 |
| **输出类型** | 聚合报告（问题驱动） | 行为日志 | 发现报告 | 基线文档更新 |
| **核心价值** | 递进精炼模式 | 积累数据 | 发现隐藏关联 | 固化结论 |

---

## 适用场景

| 场景 | 示例 |
|------|------|
| 周回顾 | 周日/周一生成上周周报，提取模式和下周焦点 |
| 月度回顾 | 月末生成月报，分析跨周趋势和战略调整 |
| 项目节点复盘 | 项目里程碑时聚合相关时期的 daily notes |
| 年度准备 | 月报积累到 12 期后，作为年度总结的输入 |

## 不适用场景

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 记录单次会话 | cc-ob-session-log | aggregate 不做单次记录 |
| 发现笔记间隐藏关联 | cc-ob-spark | aggregate 是时间聚合，不是主题发现 |
| 固化结论到基线 | cc-kb-sync | aggregate 只写 reviews 目录 |
| 数据少于 3 天 | 不触发 | 数据不足无法提取模式 |
| 生成日报 | 不触发 | daily note 本身就是日报；aggregate 从周开始 |

---

## 五步流程

### Step 1: LOAD — 数据加载

**确定范围**：
- `/weekly` → 默认本周一至周日（或上周，若本周刚开始；ISO 8601 周一起始）
- `/monthly` → 默认本月或上月
- 自定义：`/weekly 2026-W14` / `/monthly 2026-04`

**加载策略**（CLI 首选 + Glob 退化双轨，对齐全局 CLAUDE.md 检索协议）：

**主路径 — Obsidian CLI**（首选，用全文索引 + tag 语义）：

```bash
# 周报：用 tag + 创建日期范围精准检索
obsidian search "query=tag:#daily-note created:>={START} created:<={END}" \
  "format=json" --vault "数禾项目"
# 返回命中文件的 JSON 路径列表 → 解析后 Read
```

**退化路径 — Glob + Read**（CLI 不可用或无命中时）：

```
Glob pattern="daily-notes/{YYYY-MM-DD}.md" path="$OB_VAULT_ROOT"
# 对每个命中日期逐个 Read（禁止用 bash 循环 + date -d，macOS 的 date 不支持 GNU 语法）
```

> ⛔ **禁止使用** `for date in $(seq...)` + `date -d` 这类 GNU 专有 shell 循环——macOS 默认 date 不兼容。必须用 CLI 或 Glob。

**可观测性日志**（强制）：

```
📖 Vault [数禾项目] ✓ 命中 CLI | query: tag:#daily-note created:>=... | 命中: N 篇
📖 Vault [数禾项目] ⚠️ CLI 不可用 → 退化 Glob | pattern: daily-notes/YYYY-MM-DD.md | 命中: N 篇
```

**去重检查**（用 `obsidian property:read` 高效读 frontmatter）：

```bash
# 扫描已有同周/月报告，收集所有已覆盖日期
obsidian search "query=tag:#weekly-review" "format=json" --vault "数禾项目" | \
  xargs -I{} obsidian property:read covered_dates file="{}"
```

- 用命中集合 vs 本期目标日期范围取**差集**
- 差集为空：报错"本周已聚合，无新增 daily notes"
- 差集 ≥ 3 天：正常聚合
- 差集 1-2 天：提示用户"仅 N 天新增不足以提取模式，建议跳过本周"

**退化**（CLI property:read 不可用时）：`Read` 已有周报前 25 行，手动 parse `covered_dates:` YAML 字段。

### Step 2: CLASSIFY — 分类统计

**数据抽取策略**（CLI 首选）：

```bash
# 对 Step 1 加载的每篇 daily note，用 property:read 批量读 frontmatter
# 比 Read 前 20 行手动 parse frontmatter 高效一个数量级
for file in {step1 命中的 daily notes}; do
  obsidian property:read type,sessions,project,status file="$file"
done
```

**退化**（CLI property:read 不可用）：对每篇 daily note `Read` 前 25 行，手动 parse YAML frontmatter 的 type/sessions/project/status 字段。

**聚合为结构化字段**：

```yaml
classification:
  work_type_distribution:
    dev: {count, percentage}
    debug: {count, percentage}
    design: {count, percentage}
    research: {count, percentage}
    meeting: {count, percentage}
    learning: {count, percentage}

  project_distribution:
    {project_name}: {count, percentage}

  status_distribution:
    completed: {count}
    in_progress: {count}
    blocked: {count}

  time_metrics:
    total_sessions: {N}
    avg_sessions_per_day: {N}
    total_tool_calls: {N}
```

**可观测性日志**：

```
📊 CLASSIFY: 工作类型 dev:{%} debug:{%} design:{%} | 项目分布 {top3} | 会话总数 {N}
```

### Step 3: PATTERN — 模式识别（五维分析，来自 COG 社区洞察）

对加载的 daily notes 做**五维模式识别**：

1. **频率分析**: 主题/关键词出现次数
2. **时间聚类**: 哪些主题在同期集中出现
3. **域间相关**: 跨项目/跨领域的共同模式
4. **矛盾分析**: 决策冲突、方向反复
5. **元模式**: 决策方式、问题解决策略、学习模式

**工具调用**：

```
提示 LLM：
"分析以下 daily notes，从五个维度识别模式：
1. 频率: 哪些主题出现 3+ 次？
2. 时间聚类: 哪些主题在同一天/连续几天集中出现？
3. 域间: 跨项目共同的关键词是什么？
4. 矛盾: 是否有决策反复或方向调整？
5. 元模式: 我倾向于如何做决策/解决问题？

输出要求：
- 每个维度 3-5 条发现，按重要性排序
- 每条发现必须引用具体 daily note 作为证据
- 不要编造不存在的模式"
```

### Step 4: INSIGHT — 问题驱动的洞察提取

**周级问题**（3 个核心问题）：

1. **"这周反复出现了什么？"**
   → 识别重复主题、频繁阻碍、反复决策
2. **"什么阻碍最频繁？根因假设是什么？"**
   → 从错误修复记录中提取阻碍模式
3. **"哪些决策的结果值得反思？"**
   → 回顾决策 → 结果的映射

**月级问题**（4 个核心问题）：

1. **"这些模式说明了什么趋势？"**
   → 跨周对比，识别方向性变化
2. **"哪些模式持续？哪些新增？哪些消失？"**
   → 持续/新增/消失三类
3. **"工作分布变化意味着什么？"**
   → dev/debug/design 占比变化的含义
4. **"方向是否需要调整？"**
   → 战略级反思

**输出格式**（洞察级别而非汇总级别）：

```
❌ 错误示范（汇总）:
"本周完成了用户模块开发、订单 bug 修复、Redis 缓存优化..."

✅ 正确示范（洞察）:
"本周模式：排障占比 40%（3 次 Redis 相关），暗示缓存架构需要系统性
审视而非逐个修复。开发任务集中在用户模块，但需求评审反馈显示接口
设计有 2 处与下游不兼容——说明设计阶段需要加入下游联调验证步骤。"
```

### Step 5: ACTION — 行动建议

**周报行动建议类型**：
- **下周必须完成**: 基于本周阻塞项
- **下周应该关注**: 基于本周模式
- **下周可以探索**: 基于 spark 发现（可选内嵌 cc-ob-spark 调用）
- **预防性行动**: 基于本周阻碍模式

**月报行动建议类型**：
- **战略调整**: 基于跨周趋势
- **习惯养成**: 基于元模式发现
- **知识固化**: 值得沉淀到基线的结论（推荐用 cc-kb-sync 执行）
- **预防性行动**: 基于月级阻碍模式

---

## 触发方式

| 命令 | 场景 |
|------|------|
| `/weekly` | 生成上周周报（默认） |
| `/weekly 2026-W14` | 指定周 |
| `/monthly` | 生成上月月报（默认） |
| `/monthly 2026-04` | 指定月 |
| `/weekly --with-spark` | 内嵌 spark 发现 |

---

## 智能路由（可选扩展）

参考 obsidian-claude-pkm 的 `/review` 智能路由：

```
用户执行 /review 时：
  月底前 3 天 或 月初第 1 天 → /monthly（最高优先级）
  周日 或 周一 → /weekly（次优先级）
  其他 → 提示"本周已生成周报，无需聚合"或"距离月报还有 X 天"
  
过期检测：
  上次周报 > 7 天 → 强制建议 /weekly
  上次月报 > 35 天 → 强制建议 /monthly
```

此路由作为 Phase 5 迭代目标，当前 Phase 3 仅实现 `/weekly` 和 `/monthly`。

---

## 输出模板

完整模板见：
- 周报: [templates/weekly-review.md](templates/weekly-review.md)
- 月报: [templates/monthly-review.md](templates/monthly-review.md)

---

## 可观测性日志

**启动 + 分阶段进度**（强制输出，不得省略）：

```
📊 cc-ob-aggregate 启动 | 类型: [weekly|monthly] | 范围: {date_range}
📖 Vault [数禾项目] ✓ 命中 CLI | query: tag:#daily-note created:>=... | 命中: N 篇
# 或退化：📖 Vault [数禾项目] ⚠️ CLI 不可用 → 退化 Glob | 命中: N 篇
📊 LOAD: 加载 {N} 篇 daily notes | 已覆盖跳过 {M} 天 | 差集 {diff} 天
📊 CLASSIFY: 工作类型 dev:{%} debug:{%} design:{%} | 项目分布 {top3} | 会话总数 {N}
📊 PATTERN: 频率 {N} | 时间聚类 {N} | 域间 {N} | 矛盾 {N} | 元模式 {N}
📊 INSIGHT: 生成 {N} 条核心洞察 | 证据链接 {N} 条
📊 WRITE: {vault_path} | covered_dates: {N} 天
```

> 为何每阶段都要打日志：INSIGHT 阶段依赖 LLM 推理，卡住时用户需要知道到底是"LLM 慢"还是"某阶段失败"。
> 日志格式见 `shared-rules/observability-logs.md` §3 Vault 检索日志。

---

## 相关 Skill

- **cc-ob-session-log**: 上游数据源
- **cc-ob-spark**: 可选内嵌，发现主题聚类
- **cc-kb-sync**: 下游，月报中的高价值洞察可触发 kb-sync 固化到基线
