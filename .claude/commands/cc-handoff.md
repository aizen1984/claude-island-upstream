# CC Handoff — 结构化上下文重置

在阶段边界（如 PLAN → EXECUTE 切换）执行结构化交接后重启，以干净上下文开始新阶段。适用于中大型任务的阶段切换，不基于工具调用计数。

> **2026-04-09 架构变更（档位 C）**：handoff 从 push 模型（hook 自动认领+读取）改为 pull 模型（hook 只告示，`/cc-handoff restore` 显式认领）。解决跨任务污染问题：同项目多任务并行时，不相关的 handoff 不再被 compact/resume 事件自动加载。

---

## 子命令路由

| 命令 | 作用 | 使用场景 |
|------|------|---------|
| `/cc-handoff` | 生成交接文件（默认动作） | 当前会话想交接给下一会话时 |
| `/cc-handoff restore <path>` | 认领并加载已有 handoff | 新会话启动时看到告示板有未认领文件 |

---

## 一、生成交接文件（默认动作）

### 1. 状态快照

读取当前五文件状态：

```bash
echo $STARK_SESSION_DIR
echo $CLAUDE_SESSION_ID
```

- Read `{workspace}/spec.md` 目标
- Read `{workspace}/plan.md` 完成/未完成统计
- Read `{workspace}/progress.md` 最近 3 条日志

### 2. 派生元数据

```bash
# 文件名：YYYY-MM-DDTHHmm-{任务摘要前20字}.md
FILENAME="$(date +%Y-%m-%dT%H%M)-{任务摘要}.md"

# 创建时间：ISO 8601 带时区
CREATED_AT="$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)"

# task_tag：从 spec.md 一级标题派生的 kebab-case 标识，如 claude-island-fork / s-grade-sprint
#   作用：hook 告示板上显示，帮用户判断该 handoff 是否属于当前会话任务
TASK_TAG="{从 spec.md 派生，或用户显式指定}"
```

### 3. 写入交接文件

写入 `{project}/.claude/handoffs/{FILENAME}`（隔离目录，支持多任务并发）：

```markdown
---
session_id: "{$CLAUDE_SESSION_ID 生成时值}"
task_tag: "{派生的 kebab-case 标识}"
created_at: "{ISO 8601 时间戳}"
consumed_by: ""
consumed_at: ""
---

# 会话交接摘要

## 生成时间
{timestamp 可读格式}

## 工作目录
{STARK_SESSION_DIR 绝对路径}

## 任务目标
{从 spec.md 提取}

## 进度
- 总任务：{total}
- 已完成：{done}（{percentage}%）
- 当前进行中：{current_task}
- 下一个待办：{next_task}

## 最近完成
{从 progress.md 提取最近 3 条}

## 关键发现/决策
{从 findings.md 提取核心决策}

## 执行上下文
- Git 分支：{当前分支名}
- 未提交变更：{有/无，简要描述}
- 执行策略：{策略编号和名称}
- 环境变量：{LIFECYCLE_MODE, TDD 标记等关键变量，若无则填"无"}

## 恢复指令
请继续执行 `{workspace}/plan.md` 中的下一个 ⬜ 任务。
```

> **⛔ frontmatter 必填**：缺失 `---` YAML block 的文件会被 session-start hook 归入"老格式"分类，不会被自动告示。生成时若不确定 `task_tag`，填写 `"(未标注)"` 而非留空。

### 4. 提示用户

```
交接文件已写入 {project}/.claude/handoffs/{filename}
  task_tag: {tag}
  session_id: {sid}

下一步：
  - 执行 /clear 清空上下文，新会话启动时会在告示板看到此 handoff
  - 在新会话中执行 /cc-handoff restore {filename} 完成认领并加载上下文
```

---

## 二、认领并恢复（`/cc-handoff restore <path>`）

当 session-start hook 在告示板列出 handoff 后，执行此子命令完成认领 + 加载。

### 1. 验证文件可认领

```bash
HANDOFF_FILE="{用户传入的路径}"
```

- Read `$HANDOFF_FILE` 前 15 行，提取 frontmatter
- 检查 `consumed_by` 字段：
  - 为空 → 可以认领，继续
  - 非空 → 报错 "已被 session {consumed_by} 于 {consumed_at} 认领，如需强制恢复请先清空 frontmatter"
- 检查 `task_tag` 与当前会话意图是否匹配：
  - 不确定时，向用户确认："当前 handoff 的 task_tag 是 `{tag}`，是否与本会话任务相关？"

### 2. 写入 `consumed_by` / `consumed_at`

使用 Edit 工具更新 handoff 文件的 frontmatter（替换 `consumed_by: ""` 为当前 `$CLAUDE_SESSION_ID`，同理 `consumed_at`）：

```yaml
consumed_by: "{当前 $CLAUDE_SESSION_ID}"
consumed_at: "{当前 ISO 8601 时间戳}"
```

### 3. 归档到 `consumed/` 子目录

```bash
mkdir -p "{project}/.claude/handoffs/consumed"
mv "$HANDOFF_FILE" "{project}/.claude/handoffs/consumed/$(basename "$HANDOFF_FILE")"
```

> 归档后的文件不再出现在 hook 告示板，但历史可审计。如需"撤销认领"：清空 frontmatter 两字段 + mv 回原目录即可。

### 4. 加载旧 workspace 五文件

从交接文件正文 `## 工作目录` 章节提取旧 workspace 路径：

- 若目录存在：
  - 更新 `STARK_SESSION_DIR`（通过 `CLAUDE_ENV_FILE` 写 export）指向旧 workspace
  - Read 旧 workspace 的五文件（仅存在的），汇总关键信息：
    - `plan.md`: 总任务数、已完成数、下一个待办
    - `spec.md`: AC 数量
    - `progress.md`: 最近日志条数
    - `findings.md`: 关键发现数
    - `session.yaml`: 当前 phase、执行策略
  - 如有 `session.yaml`，检查并更新 phase 状态
- 若目录已清理：
  - 提示 "旧 workspace 已不存在，仅恢复 handoff 文本上下文；若需重建五文件请重新执行 /cc-planner"

### 5. 打印恢复日志

```
● 已从 handoff 恢复上下文：

1. 认领了 handoff {path}（已写入 consumed_by={sid}，归档到 consumed/）
2. 读取了旧 workspace 五文件：plan.md ({N} 个任务)、spec.md ({N} 个 AC)、session.yaml
3. 更新了 STARK_SESSION_DIR = {old_workspace}
4. 更新了 session.yaml: phase: {old} → {new}, current_task: {task}
```

> 恢复日志必须打印到控制台，让用户确认恢复完整性。五文件中不存在的跳过，不报错。

---

## 三、Hook 自动告示机制

`session-start.sh` 在会话启动时扫描 `{project}/.claude/handoffs/`，仅在 `source ∈ {startup, clear}` 时触发（跳过 resume/compact 避免跨任务污染）：

| 情况 | 行为 |
|------|------|
| 目录为空/不存在 | 静默，不提示 |
| 全部 >24h | 静默，不提示 |
| 新格式 + `consumed_by` 已填 | 静默跳过（已认领） |
| 新格式 + `consumed_by` 空 | 告示板显示：path、task_tag、session_id、created_at + 提示 "如相关执行 /cc-handoff restore" |
| 无 frontmatter（老格式） | 告示板显示警告：列出路径 + 提示 "hook 不处理，请手动判断" |

### Hook 输出示例

**单个未认领 handoff**：
```
⚡ 发现 1 个未认领 handoff（告示板，不自动加载）：
  path:       /path/to/handoffs/2026-04-09T1436-xxx.md
  task_tag:   claude-island-fork
  session_id: 11a89939-ed13-4670-8de0-dcbcda26df54
  created_at: 2026-04-09T14:36:00+08:00

  → 如与本会话任务相关: 执行 /cc-handoff restore 命令认领并加载上下文
  → 如与本会话任务无关: 直接忽略即可，hook 不会自动读取文件内容
```

**重要行为变化**：
- hook 不再自动写 `STARK_SESSION_DIR` 指向旧 workspace
- hook 不再自动 Read handoff / 五文件
- hook 不再给 Claude 强制性"请执行恢复流程"指令
- 新会话 Claude **应该默认无视告示板**，除非用户明确说"恢复 handoff" 或告示的 task_tag 显然匹配当前会话目标

---

## 四、归档与清理

- `.claude/handoffs/` 根目录：当前未认领的 handoff
- `.claude/handoffs/consumed/` 子目录：已被认领的历史 handoff（不再出现在告示板）
- `>24h` 的文件：不会进告示板，但不自动删除（保留审计）
- 手动清理：直接删除 `.claude/handoffs/consumed/` 或 `>24h` 文件

---

## 五、老格式 handoff 兼容

2026-04-09 之前生成的 handoff 文件（无 YAML frontmatter）会被归入 "legacy" 分类：

- Hook 告示板单独列出，带 ⚠️ 警告
- 不做 `consumed_by` 检查（因为没有字段）
- 用户需手动判断：若确认老 handoff 已失效，移动到 `consumed/` 归档；若仍需认领，先手动补齐 frontmatter 再执行 restore
