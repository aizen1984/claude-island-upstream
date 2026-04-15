# 会话 Workspace 隔离协议

> **加载时机**：五文件操作前（planner/cc-work-mode 等使用会话文件时）。定义会话级文件隔离机制，确保多会话并发时五文件互不干扰。

---

## 一、Workspace 概念

**Workspace** = 当前会话的五文件存放目录。所有 Skill 对五文件的读写操作必须指向 workspace，而非项目根目录。

### 目录结构

| 场景 | Workspace 路径 | 设置方 |
|------|---------------|--------|
| 普通会话 | `.claude/sessions/{SESSION_ID}/` | session-start.sh（SessionStart hook） |
| Ralph 会话 | `.claude/sessions/{UUID}/` | ralph-loop 命令 |

> **⛔ 无 Fallback**：`STARK_SESSION_DIR` 未设置时，禁止在项目根目录创建五文件。必须先确认 session 目录存在。

### 文件布局

```
{workspace}/
├── plan.md          # 任务计划 + 执行状态
├── spec.md          # 需求/验收标准
├── progress.md      # 执行日志
├── findings.md      # 研究发现
└── session.yaml     # 会话元数据
```

---

## 二、解析协议

### Skill 指令中使用（必须在操作五文件前执行一次）

```bash
# 获取 session 路径（环境变量由 session-start.sh 或 ralph-loop 设置）
WORKSPACE="${STARK_SESSION_DIR}"
if [ -z "$WORKSPACE" ]; then
  echo "❌ STARK_SESSION_DIR 未设置，无法操作五文件"
  exit 1  # 或对 Claude 指令：停止执行并报错
fi
# 后续使用:
# Read  ${WORKSPACE}/plan.md
# Edit  ${WORKSPACE}/plan.md
# Write ${WORKSPACE}/spec.md
```

### Hook/脚本中使用

```javascript
// Node.js（Hook 用）
const workspace = process.env.STARK_SESSION_DIR;
if (!workspace) { console.error('STARK_SESSION_DIR 未设置'); process.exit(0); }
const planPath = path.join(workspace, 'plan.md');
```

```bash
# Bash（脚本用）
WORKSPACE="${STARK_SESSION_DIR:?STARK_SESSION_DIR 未设置}"
```

---

## 三、环境变量

| 变量 | 设置方 | 值 |
|------|--------|-----|
| `STARK_SESSION_DIR` | session-start.sh | `.claude/sessions/{SESSION_ID}/` 绝对路径 |
| `STARK_SESSION_DIR`（覆盖） | ralph-loop | `.claude/sessions/{UUID}/` 绝对路径 |

通过 `CLAUDE_ENV_FILE` 持久化，后写覆盖前写（bash source 语义）。

### 指针文件（备用通道）

路径: `/tmp/stark-workspace-{PROJECT_HASH}-{SESSION_ID}`
内容: workspace 绝对路径
用途: 当环境变量不可用时（如 Read 工具无法访问 env），可读取此文件

---

## 四、Subagent 传递规则

Subagent（executor/researcher/cc-code-reviewer）不保证继承 `STARK_SESSION_DIR` 环境变量。因此：

**强制**: 派发 subagent 时，prompt 中必须包含 workspace 路径：

```
📂 Workspace: {workspace 绝对路径}
所有五文件（plan.md/spec.md/progress.md/findings.md/session.yaml）读写限定在此目录。
```

这是**双通道保障**：环境变量 + prompt 显式注入。

---

## 五、快照同步（可选）

五文件始终保留在 session 目录内，**不同步回项目根目录**。查看方式：

```bash
cat "${STARK_SESSION_DIR}/plan.md"
# 或
ls .claude/sessions/  # 找到对应 session 目录
```

---

## 六、引用此协议的 Skill

| Skill | 引用位置 |
|-------|---------|
| cc-planner | SKILL.md 资源加载表 + 五文件持久化章节 |
| cc-work-mode | SKILL.md 资源加载表 |
| cc-code-writer | prompts.md（spec.md 引用） |
| cc-tdd | workflows.md（plan.md 引用） |
| shared-rules/task-tracking-rules.md | 模式 B 文件驱动 |
