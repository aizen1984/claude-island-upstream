---
name: cc-ob-spark
description: 扫描近期Obsidian笔记发现正在形成的知识簇和跨域隐藏关联。不写新笔记、不修改已有内容。用于知识发现、主题聚合、连接建议、灵感激发
allowed-tools: Read, Grep, Glob, Write, Bash
---

# 知识簇发现（Spark）

## Gotchas

> 从设计、对抗验证和社区调研（Cornelius/Andy Matuschak）中积累的陷阱。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | LLM 幻觉关联（编造笔记间不存在的联系） | 用户被误导建立无意义链接 | 每个关联必须引用具体笔记内容作为证据（文件路径+1 行摘录） |
| 2 | 扫描范围过大（全量 vault） | Token 爆炸 + 噪声淹没信号 | 默认 14 天，最大 90 天，500+ 笔记时分项目/领域扫描 |
| 3 | 把已有显式链接当作"发现" | 报告缺乏增量价值 | 区分「已链接簇」和「未连接簇」，优先展示后者 |
| 4 | 纯随机推送（Matuschak 教训） | 用户疲劳，推送被忽略 | 必须语义相关性过滤，不随机推荐 |
| 5 | LLM 聚类结果不稳定 | 同输入多次运行结果不同 | 要求输出引用具体笔记标题作为锚点，锚点稳定即可 |
| 6 | 只找高相似度的显而易见匹配 | 错过真正有价值的隐藏桥梁 | Cornelius 策略：**优先发现低相似度（语义 0.50-0.70）但高概念强度的跨域连接** |
| 7 | 把"噪声模式"当作发现 | 报告充斥偶然共现 | 至少 3 条笔记才构成一个簇，单条笔记不报告 |
| 8 | 写新笔记或修改已有笔记 | 越界操作 | cc-ob-spark 只读分析，只输出报告到 `spark-reports/` |

---

## 概述

cc-ob-spark 扫描 vault 中近期笔记，用 LLM 语义分析发现正在形成但用户尚未显式关联的知识簇。它是**知识飞轮**的洞察发现层——在会话日志积累到一定量后，从中发现隐藏的主题关联。

**核心价值**：vault 中的笔记 → 发现潜在知识簇 → 建议连接和 MOC 创建

**核心策略**（Cornelius auto-discovery 三原则：低表面相似+高概念强度、跨域连接、生产性张力）—— 详见 [Step 3: LLM_CLUSTER](#step-3-llm_cluster--llm-聚类分析) 的"核心策略"段（**唯一真源**，避免与 LLM Prompt 双源漂移）。

**四步流程**：COLLECT（收集）→ PREPROCESS（预处理）→ LLM_CLUSTER（LLM 聚类）→ REPORT（报告）

---

## 协作关系

- **接收自**: user（`/spark` 触发）、cc-ob-aggregate（周报流程中可选调用）
- **委托给**: cc-diagram（可选，生成知识网络可视化）
- **消费**: vault 中任何 Markdown 笔记（不限于 daily notes）
- **产出**: `vault/spark-reports/YYYY-MM-DD-{topic}.md`

### 与相关 Skill 的区别

| 维度 | cc-ob-spark | cc-kb-sync | cc-ob-session-log | cc-ob-aggregate |
|------|------------|-----------|-------------------|-----------------|
| **方向** | 只读 vault，分析已有笔记 | 写入 vault，固化会话结论 | 写入 vault，记录会话行为 | 写入 vault，聚合 daily notes |
| **范围** | 跨笔记、跨领域 | 单次会话的结论 | 单次会话的元数据 | 时间范围内的 daily notes |
| **输出** | 发现报告（索引级） | 基线文档更新 | daily note 追加 | 周报/月报 |
| **触发** | 用户手动 / aggregate 内嵌 | 用户手动 | 用户手动 / SessionStart 提醒 | 用户手动 / 定时 |

---

## 适用场景

| 场景 | 示例 |
|------|------|
| 周/月回顾时探索 | "这个月都研究了什么？有什么隐藏关联？" |
| 写作前灵感激发 | 写新文章前用 `/spark` 发现可以串联的已有笔记 |
| 建立 MOC 前的探索 | 创建 Map of Content 前用 spark 找到该主题下的所有相关笔记 |
| 知识图谱体检 | 发现被遗忘的笔记、孤立主题、潜在聚类 |
| 跨项目发现 | 发现多个项目笔记共享的底层模式 |

## 不适用场景

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 记录当前会话 | cc-ob-session-log | spark 只读分析，不写入 |
| 固化会话结论到基线 | cc-kb-sync | spark 只输出报告，不修改基线 |
| 生成周报/月报 | cc-ob-aggregate | spark 是发现器，不做时间聚合 |
| 代码分析 | cc-code-reviewer | spark 分析知识笔记，不分析代码 |
| 精确检索单个笔记 | Obsidian CLI search | spark 是发现聚类，不是搜索 |

---

## 四步流程

### Step 1: COLLECT — 数据收集

**范围界定**：
- 默认扫描 `$OB_VAULT_ROOT` 下近 14 天修改的笔记
- 排除 `归档/` 目录、`.obsidian/` 目录、`*/辅助资料/_raw/` 目录（raw 层是未编译外部源，不参与 wiki 连接分析）
- 支持参数覆盖：`/spark 30天` / `/spark 项目=vipship` / `/spark 领域=订单`

**收集策略**（CLI 首选 + Glob 退化双轨，与 cc-kb-sync / cc-ob-aggregate / cc-ob-session-log 一致）：

**主路径 — Obsidian CLI**（权重排序 + 修改时间范围精确）：

```bash
# 按时间范围精准检索近 N 天修改的笔记
obsidian search "query=modified:>14d" "format=json" --vault "数禾项目"

# 或按项目/领域精准定位
obsidian search "query=path:vipship/ modified:>14d" "format=json" --vault "数禾项目"
obsidian search "query=tag:#订单域 modified:>30d" "format=json" --vault "数禾项目"
```

**退化路径 — Glob + Read**（CLI 不可用时）：

```
Glob pattern="**/*.md" path="$OB_VAULT_ROOT"
# 对每个结果用 Read 获取 mtime 信息（Glob 按 mtime 排序），筛选近 14 天
# 或 Bash: find "$OB_VAULT_ROOT" -name "*.md" -mtime -14 -not -path "*/归档/*" -not -path "*/.obsidian/*"
```

> ⛔ **禁止跳过 CLI 主路径直接 Grep**。Grep 无 mtime 感知，无法精确筛选"近 N 天修改"。

**可观测性日志**（强制）：

```
📖 Vault [数禾项目] ✓ 命中 CLI | query: modified:>14d | 命中: N 篇
# 或退化: 📖 Vault [数禾项目] ⚠️ CLI 不可用 → 退化 Glob+mtime | 命中: N 篇
```

**对每条笔记提取**（用 `obsidian property:read` 批量读 frontmatter）：

```bash
# 批量读 frontmatter 字段，比 Read 前 25 行手动 parse 高效
for file in {命中文件}; do
  obsidian property:read tags,aliases,type,created,modified file="$file"
done
```

退化：Read 前 25 行手动 parse YAML frontmatter。

- 标题（文件名，来自 search 返回的 path）
- frontmatter：tags / aliases / type / created / modified（由 property:read 提取）
- 前 10 行正文（摘要信号）—— 需 Read（CLI 无对等命令）
- 所在目录（领域归属信号，来自 path）

**并收集 vault 元信息**（CLI 一次调用搞定）：

```bash
# 高频标签统计（按出现次数排序）
obsidian tags sort=count counts --vault "数禾项目"

# 笔记间链接网络（对每个候选笔记获取反向链接）
obsidian backlinks file="{file}" --vault "数禾项目"
```

退化：Grep `#\w+` 全量扫描 → 手动统计频率（慢且易漏）；backlinks 无等价退化（Grep 全 vault 找 `[[{title}]]` 性能差）。

### Step 2: PREPROCESS — 预处理

构建结构化输入（纯文本格式，喂给 LLM）：

```markdown
## 待分析笔记清单 (N=142)

### 领域: my_claude (42 篇)
- 基线文档/Ralph_Wiggum循环功能指南.md [tags: #skill #hook] (摘要: ...)
- 需求/Planner无限迭代循环模式/技术设计文档.md [tags: #planner #riper] (摘要: ...)
...

### 领域: vipship (35 篇)
- 基线文档/退款域基线.md [tags: #退款域 #订单] (摘要: ...)
...

### 跨项目高频标签
- #事务 (出现在 8 篇笔记)
- #幂等 (出现在 6 篇笔记)
- #对抗验证 (出现在 5 篇笔记)

### 现有 MOC 和领域索引
- my_claude/首页.md (search_index 含 42 个关键词)
- vipship/首页.md (search_index 含 28 个关键词)
```

**Token 预估**：N 篇 × 150 token ≈ 总消耗。100 篇 ≈ 15k，500 篇 ≈ 75k，1000 篇 ≈ 150k。500+ 时建议分项目扫描。

### Step 3: LLM_CLUSTER — LLM 聚类分析

**核心 Prompt**（强调 Cornelius 策略）：

```
你是知识图谱分析专家。以下是用户 vault 中近 {N} 天的笔记。

## 任务
识别 3-7 个正在形成的知识簇。一个簇 = 多条笔记在语义上自然聚集但尚未显式关联。

## 核心策略（重要）
- **优先发现低表面相似度但高概念强度的跨域连接**：看似不相关的笔记间共享的深层结构模式比显而易见的同主题聚类更有"Aha!"价值
- **区分已链接簇和未连接簇**：未连接簇（潜在桥梁）价值更高
- **生产性张力标记**：如发现结论对立但语义相似的笔记对，单独标记为"张力点"

## 输出要求
对每个簇：
1. 主题名称（2-5 字，中文）
2. 包含的笔记（引用具体文件路径）
3. 区分性关键词（是什么让这个簇不同于其他簇？）
4. 聚合趋势（近期新增频率：稳定/增长中/爆发）
5. 潜在洞察（这些笔记放在一起能产生什么新认知？1-2 句话）
6. 建议行动（创建 MOC？合并笔记？建立链接？）
7. 是否已有显式链接（yes/partial/no）

## 约束
- 不要创造笔记中不存在的关联（禁止幻觉）
- 只输出有证据支撑的簇（至少 3 条笔记）
- 每个关联必须引用具体笔记内容作为证据
- 输出不超过 7 个簇
- 标记孤立笔记（无明显归属但可能有价值的单条）

## 输入数据
{preprocessed_data}
```

### Step 4: REPORT — 报告生成

写入 `$OB_VAULT_ROOT/spark-reports/YYYY-MM-DD-{topic}.md`：

> 报告模板详见 [templates/spark-report.md](templates/spark-report.md)（含完整 frontmatter、簇结构、张力点、孤立笔记、行动清单和局限说明）。

---

## 触发方式

| 命令 | 场景 |
|------|------|
| `/spark` | 默认扫描 14 天 |
| `/spark 30天` | 自定义时间范围 |
| `/spark 项目=vipship` | 聚焦特定项目 |
| `/spark 领域=订单` | 聚焦特定领域（按标签或目录） |
| `/spark --tensions-only` | 只检测生产性张力，不做聚类 |

---

## 可观测性日志

```
🔥 cc-ob-spark 启动 | 扫描: {N} 天 | 范围: {项目/领域/全部}
📖 Vault [数禾项目] ✓ 命中 CLI | query: modified:>{N}d | 命中: {count} 篇
# 或退化: 📖 Vault [数禾项目] ⚠️ CLI 不可用 → 退化 Glob+mtime
🔥 COLLECT: 笔记 {count} | 标签 {tag_count} | backlinks {link_count} | Token 预估: {k}k
🔥 PREPROCESS: 领域 {domain_count} | 跨域标签 {cross_tag_count}
🔥 CLUSTER: 潜在簇 {N} | 已连接簇 {N} | 生产性张力 {N} | 孤立 {N}
🔥 REPORT: {vault_path}
```

> 日志格式见 `shared-rules/observability-logs.md` §3 Vault 检索日志。
> 所有 📖 Vault 检索日志必须在 CLI 命令执行前后立即输出（命中/退化/失败三态）。

---

## Token 消耗估算

| 笔记规模 | 预估 Token | 是否可承受 |
|---------|-----------|-----------|
| ≤ 100 篇 | ~15k | ✅ 轻松 |
| 100-500 篇 | 15-75k | ✅ 可承受 |
| 500-1000 篇 | 75-150k | ⚠️ 建议分领域 |
| > 1000 篇 | >150k | ❌ 必须分项目/领域 |

Claude Opus 4.6 1M context 下均可运行，但信噪比在 500+ 篇时下降。

---

## 相关 Skill

- **cc-ob-aggregate**: 周报/月报流程可内嵌 spark 调用
- **cc-diagram**: 可视化知识网络（可选）
- **cc-kb-sync**: 用户接受 spark 的行动建议后，用 kb-sync 创建 MOC 或写入新关联
