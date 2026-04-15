---
name: cc-ob-session-log
description: 将当前会话的工作摘要写入Obsidian daily note，记录行为而非提炼知识。不提取结论性知识、不修改基线文档。用于会话记录、工作模式分析、知识飞轮数据采集
allowed-tools: Read, Write, Edit, Grep, Glob, Bash
---

# 会话日志记录

## Gotchas

> 从设计和对抗验证中积累的陷阱。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 闲聊/简单问答也记录 | daily note 被噪声淹没 | 工具调用 < 5 次 或 仅单次问答时跳过，不写入 |
| 2 | 记录过于详细（贴代码/完整对话） | token 浪费 + daily note 臃肿 | 摘要级别，工作摘要 3-5 条 bullet，每条 < 20 字 |
| 3 | 敏感信息写入 daily note | 凭据/密码/token 泄露 | 写入前脱敏检测：API Key / Bearer / password / secret 等关键词匹配 |
| 4 | 与 cc-kb-sync 混淆 | 两个 Skill 做同一件事 | session-log 记"做了什么"（行为），kb-sync 提"发现了什么"（知识）。session-log 的"发现"字段只写索引级标题（1 行），不写展开论证 |
| 5 | 覆盖已有 daily note 用户内容 | 手动日记被破坏 | 检测已有文件格式：非标准模板时只在末尾追加"## Claude Code 会话记录"分区，不改已有内容 |
| 6 | 时间戳用相对时间（"刚才"） | 日后无法定位 | 使用绝对时间：YYYY-MM-DD HH:mm |
| 7 | 多次会话同一天重复写 frontmatter | YAML 解析失败 | 检查 daily note 是否已存在，存在则只追加会话条目，不重写 frontmatter |
| 8 | "下次上下文"字段写成任务清单而非上下文 | 下次会话无法快速续接 | 明确区分：下次上下文 = 需要知道什么背景/状态；待办事项 = 用 `- [ ]` 单独列出 |

---

## 概述

cc-ob-session-log 将当前会话的**工作元数据**（做了什么、用了什么工具、遇到什么决策）摘要后写入 Obsidian vault 的 daily note。它是**知识飞轮**的数据采集层——为后续 cc-ob-aggregate（周/月报）和 cc-ob-spark（主题发现）提供原始素材。

**核心价值**：会话元数据 → 持久化日志 → 工作模式分析基础

**四步流程**：ANALYZE（分析）→ SUMMARIZE（摘要）→ FORMAT_CHECK（格式检测）→ WRITE（写入）（详见下方"四步流程"章节）

---

## 协作关系

- **接收自**: user（直接触发 `/session-log`）、SessionStart hook 提醒后用户主动触发
- **委托给**: 无
- **消费者**: cc-ob-aggregate（读取 daily notes 生成周/月报）、cc-ob-spark（可选，扫描 daily notes 发现模式）
- **与 cc-kb-sync 的边界**: 见下方"与 cc-kb-sync 的区别"

### 知识循环链定位

```
cc-ob-session-log  ← 数据采集层（本 Skill）
      ↓ 积累 daily notes
cc-ob-aggregate    ← 结构精炼层
      ↓ 递进精炼
cc-ob-spark        ← 洞察发现层
      ↓ 发现聚类
cc-kb-sync         ← 知识固化层
```

### 与 cc-kb-sync 的区别

| 维度 | cc-ob-session-log | cc-kb-sync |
|------|-------------------|-----------|
| **输入源** | 会话元数据（工具调用/文件操作/对话摘要） | 会话中的结论性内容（架构洞察/排障根因/方案决策） |
| **输出目标** | `vault/daily-notes/YYYY-MM-DD.md` | `vault/{项目名}/基线文档/*.md` |
| **粒度** | 会话级摘要（标题+1 行） | 知识点级（章节/段落完整论证） |
| **触发频率** | 每次有实质性工作的会话 | 仅当产生高价值可沉淀知识时 |
| **价值** | 积累工作模式数据，供后续分析 | 固化高价值结论到项目知识库 |

**灰色地带澄清**：daily note 模板中的"决策记录"和"发现与洞察"字段是**索引级**（仅标题+1 行摘要）。详细的知识提炼（决策理由展开、洞察的完整论证）由 kb-sync 负责。session-log 的发现字段相当于"书签"，kb-sync 才是"正文"。

---

## 适用场景

| 场景 | 示例 |
|------|------|
| 开发会话收尾 | 完成功能开发后记录改了哪些文件、做了什么决策 |
| 排障会话收尾 | cc-troubleshoot 排完障，记录排查路径（但根因详情由 kb-sync 沉淀） |
| 设计会话收尾 | cc-design 产出设计文档后记录设计决策的概要 |
| 调研会话收尾 | 技术调研完成后记录调研结论的标题（详细分析由 kb-sync 沉淀） |
| 定期复盘前 | 周末/月末执行前先 session-log，确保最新会话已记录 |

## 不适用场景

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 提炼会话中的架构洞察 | cc-kb-sync | session-log 只记索引，不展开论证 |
| 从 vault 已有笔记发现主题 | cc-ob-spark | session-log 只写入，不读取分析 |
| 生成周报/月报 | cc-ob-aggregate | session-log 是数据采集，不做聚合 |
| 记录闲聊/简单问答 | 不触发 | 工具调用 < 5 次的会话无记录价值 |
| 代码实现 | cc-code-writer | session-log 只做记录 |

---

## 四步流程

### Step 1: ANALYZE — 分析当前会话

**Bash 命令清单**（Low autonomy，逐条执行）：

```bash
# 日期与时间（无 Bash 则 Claude 无法获得准确 HH:mm）
date +%Y-%m-%d                               # date 字段
date +%H:%M                                  # time_range 结束时间（开始时间由会话启动时记录或 Claude 估算）

# 项目与分支
basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || basename "$(pwd)"
git branch --show-current 2>/dev/null || echo "(not-a-git-repo)"
```

**提取会话元数据**（字段名对齐 `templates/daily-note.md` frontmatter）：

```yaml
session_metadata:
  date: YYYY-MM-DD                      # 来自 date +%Y-%m-%d
  time_range: HH:mm - HH:mm             # 来自 date +%H:%M
  project: {git 仓库名或 basename}
  branch: {git 分支名或 "(not-a-git-repo)"}
  tool_call_summary: {Read/Write/Edit/Bash/Agent 等调用次数}   # 对齐模板字段名
  files_touched: {读写过的文件列表}
  activated_skills: {激活过的 Skill 列表}                       # 对齐模板字段名
  dispatched_agents: {派发的 subagent 列表}                     # 对齐模板字段名
```

> **字段名统一**：`tool_call_summary` / `activated_skills` / `dispatched_agents` 三个字段名必须与 `templates/daily-note.md` frontmatter 保持一致。不要使用 `tool_calls`/`skills_activated`/`agents_dispatched` 等变体。

**触发门控**（任一满足才记录）：
- 工具调用 >= 5 次
- 或修改了文件（Write/Edit 次数 >= 1）
- 或派发了 subagent
- 或用户显式触发 `/session-log`

不满足 → 提示"本次会话无实质性工作，跳过记录"并退出。

**Observatory 数据采集**（可选，目录存在时执行）：

```bash
# 读取当日 skill 激活数据（填充模板"Skill 效果观察"表）
observatory_dir="$CLAUDE_PROJECT_DIR/.claude/observatory"
if [[ -d "$observatory_dir" ]]; then
  date_today=$(date +%Y-%m-%d)
  cat "$observatory_dir/activations/${date_today}.jsonl" 2>/dev/null  # 激活记录
  cat "$observatory_dir/corrections/${date_today}.jsonl" 2>/dev/null  # 纠正记录
fi
```

如有数据，在 SUMMARIZE 阶段自动填充"Skill 效果观察"表：
- `有用?` = `yes`（默认）/ `partial`（有纠正记录关联）/ `no`（用户明确否定）
- `摩擦点` = 纠正记录中的 `correction_keyword` + `prompt_preview`

无 observatory 目录或无当日数据时，该表标注"无观测数据"。

### Step 2: SUMMARIZE — 生成结构化摘要

识别会话主要类型：**开发 / 排障 / 设计 / 调研 / 会议 / 学习**。

按模板填充字段：

```yaml
session_entry:
  goal: {本次会话目标，1 句话}
  type: {上述类型之一}
  status: {completed | in_progress | blocked}
  work_summary:      # 3-5 条 bullet，每条 < 20 字
    - {核心操作 1}
    - {核心操作 2}
  decisions:         # 仅有决策时填
    - title: {决策标题}
      choice: {选择}
      rationale: {1 行理由}
  discoveries:       # 仅有发现时填（索引级）
    - title: {发现标题}
      brief: {1 行摘要}
  errors_fixed:      # 仅有错误修复时填
    - error: {错误}
      fix: {修复方式}
  next_context: {下次会话需要知道的背景/状态}
  next_todos:        # 可选，待办事项
    - {待办项 1}
```

**脱敏检测**：在写入前扫描敏感关键词（`password` / `secret` / `api_key` / `token` / `Bearer` / `credential`），命中则替换为 `[REDACTED]`。

### Step 3: FORMAT_CHECK — 检测已有 daily note 格式（CLI 首选）

**主路径 — obsidian CLI**：

```bash
# 用 daily:path 解析今日 daily note 的标准路径（无需手动拼接 vault 根）
obsidian daily:path date="$(date +%Y-%m-%d)" --vault "数禾项目"

# 如果文件存在，用 property:read 精确读 type 字段（比 Read 前 20 行快一个数量级）
obsidian property:read type file="{daily_note_path}" --vault "数禾项目"
```

判定：
- `type == daily_note` → **标准模板**，走 Step 4 的 `obsidian daily:append` 原子追加
- `type` 不存在或值不同 → **用户手动日记**，仅追加 `## Claude Code 会话记录` 分区
- 文件不存在 → **新建** flow（Step 4 的 `Write` 路径）

**退化路径 — Read + 手动 parse**（CLI 不可用时）：

1. 检查 `vault/daily-notes/YYYY-MM-DD.md` 是否存在（Glob）
2. 存在 → Read 前 25 行 parse YAML frontmatter 判断 type
3. 不存在 → 新建 flow

**可观测性日志**（强制）：

```
📖 Vault [数禾项目] ✓ 命中 CLI | daily:path + property:read | type: daily_note
# 或退化: 📖 Vault [数禾项目] ⚠️ CLI 不可用 → 退化 Read 前 25 行 parse frontmatter
```

### Step 4: WRITE — 写入 daily note（CLI 首选）

⛔ **写前备份铁律**（与 cc-kb-sync 规范一致）：对已存在的 daily note 执行 `daily:append` / Edit 前，**必须先 `cp` 备份**：

```bash
cp "{daily_note_path}" "{daily_note_path}.bak.$(date +%Y%m%dT%H%M)"
# 失败立即停止，不执行后续写入
```

> 注：daily:append 本身是原子追加（不是 replace），但 vault 无 git，一旦脚本 bug 写错位置就无法回滚。备份是最后防线。
> new_file 豁免（文件原本不存在，失败时 rm 即可）。

**主路径 — obsidian CLI**：

按 Step 3 判定分三类：

**类型 A: 新建（文件不存在）**：

```bash
# Write 工具写完整模板（CLI 无 daily:create 对等命令）
Write path="{daily_note_path}" content="{模板渲染结果}"

# 新建后用 property:set 初始化 sessions 计数
obsidian property:set name="sessions" value="1" file="{daily_note_path}"
```

**类型 B: 追加标准模板（daily_note 类型）**：

```bash
# 原子追加会话条目到 ## 会话记录 章节末尾
obsidian daily:append content="{会话条目 markdown}" date="$(date +%Y-%m-%d)"

# 更新 sessions 计数（读当前值 + 1 + 写回）
current=$(obsidian property:read sessions file="{daily_note_path}")
obsidian property:set name="sessions" value="$((current + 1))" file="{daily_note_path}"
```

**类型 C: 追加用户日记（非 daily_note 类型，保留用户内容）**：

```bash
# 用户日记不更新 sessions（避免污染用户 frontmatter），仅在文件末尾追加分区
obsidian daily:append content="\n## Claude Code 会话记录\n\n{会话条目}" date="$(date +%Y-%m-%d)"
```

**退化路径 — Read + Edit + Write**（CLI 不可用时）：

- 类型 A：Write 完整模板（不变）
- 类型 B：Read 完整文件 → Edit 在 `## 会话记录` 末尾插入 → Edit frontmatter sessions +1（需两次 Edit，不如 CLI 原子）
- 类型 C：Read 完整文件 → Edit 在文件末尾追加分区（不动 frontmatter）

**验证（所有路径）**：

```bash
# 读回验证 frontmatter type / sessions 字段正确
obsidian property:read type,sessions,date file="{daily_note_path}"
# 或退化：Read 前 25 行
```

**可观测性日志**：

```
📊 WRITE: {daily_note_path} | 类型: A新建/B追加/C用户日记 | sessions: {new_count}
📖 Vault [数禾项目] ✓ 备份 → {daily_note_path}.bak.20260409T0012
```

---

## 触发机制

### 手动触发（主要路径）

```
用户输入 /session-log 或 "记录会话日志"
  → 激活 cc-ob-session-log
  → 执行四步流程
```

### SessionStart 注入提醒（辅助路径）

每次会话启动时，session-start.sh 在 additionalContext 中注入提醒：

```
💡 如果本次会话有实质性工作（开发/排障/设计/调研），
   结束前可执行 /session-log 记录到 daily note
```

这是**建议性提醒**而非自动写入——Claude 在判断会话有实质性工作时主动提示用户。

---

## Daily Note 模板

完整模板见 [templates/daily-note.md](templates/daily-note.md)。

**frontmatter 关键字段**：

```yaml
---
date: YYYY-MM-DD
type: daily_note
tags:
  - daily-note
sessions: N  # 当日会话数，每次追加 +1
---
```

**会话条目格式**：

```markdown
### 会话 {N} — {time} | {project} | {branch}

**目标**: {goal}
**类型**: {type}
**状态**: {status}

#### 工作摘要
- {bullet 1}
- {bullet 2}

#### 决策记录（可选）
| 决策 | 选择 | 理由 |
|------|------|------|
| ... | ... | ... |

#### 发现与洞察（可选，索引级）
- **{发现标题}**: {1 行摘要}

#### 下次上下文
> {next_context}

#### 待办
- [ ] {todo 1}
```

---

## 输出数据契约

| 字段 | 必须 | 说明 |
|------|------|------|
| date | Y | 当日日期 YYYY-MM-DD |
| session_goal | Y | 会话目标（1 句话） |
| status | Y | completed / in_progress / blocked |
| work_summary | Y | 3-5 条 bullet |
| next_context | Y | 下次会话续接要点 |
| decisions | N | 决策列表（有则记） |
| discoveries | N | 索引级发现（有则记） |
| errors_fixed | N | 错误修复记录（有则记） |
| tool_usage | N | 工具调用统计（可选） |

---

## 可观测性日志

```
📝 cc-ob-session-log 启动 | project: {name} | branch: {branch}
📝 ANALYZE: 会话类型 {dev/debug/design/research} | tool_call_summary: {N}
📖 Vault [数禾项目] ✓ 命中 CLI | daily:path + property:read | type: {daily_note|user_diary|new}
📊 WRITE: {vault_path} | 类型: A新建/B追加/C用户日记 | sessions: {new_count}
📖 Vault [数禾项目] ✓ 备份 → {vault_path}.bak.{timestamp}  # 仅 B/C 类型
```

> CLI 不可用时对应的退化日志：`📖 Vault [数禾项目] ⚠️ CLI 不可用 → 退化 Read 前 25 行 parse frontmatter`
> 日志格式见 `shared-rules/observability-logs.md` §3 Vault 检索日志。

---

## 相关 Skill

- **cc-ob-aggregate**: 消费本 Skill 产出的 daily notes 生成周/月报
- **cc-ob-spark**: 可扫描 daily notes 发现工作模式
- **cc-kb-sync**: 处理"发现"字段中需要展开的知识（互补不重叠）
