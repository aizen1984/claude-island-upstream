# CC Ralph - 持久执行模式统一入口

Ralph 循环的启动/查看/取消一体化命令。进入"不完成不停止"模式。

## 参数解析

参数: $ARGUMENTS

支持以下格式：
- `/cc-ralph` — 启动 Ralph Loop（默认）
- `/cc-ralph --status` — 查看当前项目所有 Ralph 会话状态
- `/cc-ralph -s` — 同上（短参数）
- `/cc-ralph --cancel` — 取消当前会话的 Ralph
- `/cc-ralph -c` — 同上（短参数）

根据参数路由到下方三个子流程之一。**无参数默认执行"启动"流程**。

---

## 子流程 1：启动 Ralph Loop（默认 / 无参数）

### 前置条件

- 需要有 plan.md 文件（含 Spec 摘要 + 任务列表），通常由 cc-planner 生成
- 如果没有 plan.md，先提示用户创建
- 需要 `CLAUDE_SESSION_ID` 环境变量（由 SessionStart hook 自动导出）

### 启动流程

执行以下 bash 命令，检测当前会话状态：

```bash
PROJECT_HASH=$(echo -n "$PWD" | md5sum 2>/dev/null | cut -c1-8 || md5 -q -s "$PWD" | cut -c1-8)
SESSION_ID="${CLAUDE_SESSION_ID:?需要 CLAUDE_SESSION_ID 环境变量（由 SessionStart hook 自动导出）}"
ANCHOR="/tmp/stark-ralph-${PROJECT_HASH}-${SESSION_ID}-current"
SESSIONS_DIR="${CLAUDE_PROJECT_DIR:-.}/.claude/sessions"

setopt NULL_GLOB 2>/dev/null || true  # zsh: glob 无匹配时返回空而非报错

# ===== 1. 清理旧版本残留（PPID 格式：纯数字后缀）=====
for old_file in /tmp/stark-ralph-${PROJECT_HASH}-[0-9]*-active; do
  [ -f "$old_file" ] || continue
  old_prefix="${old_file%-active}"
  rm -f ${old_prefix}-* 2>/dev/null
  echo "🧹 清理了旧版本（PPID 格式）残留"
done

# ===== 2. 清理旧版 per-project 锚文件（迁移期）=====
OLD_ANCHOR="/tmp/stark-ralph-${PROJECT_HASH}-current"
if [ -f "$OLD_ANCHOR" ]; then
  old_uuid=$(cat "$OLD_ANCHOR" 2>/dev/null || echo "")
  if [ -n "$old_uuid" ]; then
    rm -f /tmp/stark-ralph-${PROJECT_HASH}-${old_uuid}-* 2>/dev/null
  fi
  rm -f "$OLD_ANCHOR"
  echo "🧹 清理了旧版 per-project 锚文件"
fi

# ===== 3. 检查当前会话是否已有活跃 Ralph =====
if [ -f "$ANCHOR" ]; then
  EXISTING_UUID=$(cat "$ANCHOR" 2>/dev/null || echo "")
  if [ -n "$EXISTING_UUID" ] && [ -f "/tmp/stark-ralph-${PROJECT_HASH}-${EXISTING_UUID}-active" ]; then
    echo "⚠️ 当前会话已有活跃 Ralph（UUID: ${EXISTING_UUID}）"
    echo "请先 /cc-ralph --cancel 取消或等待完成"
    echo "RALPH_MODE=already_active"
    exit 0
  fi
  # 非活跃（已完成/无效），清理后继续
  [ -n "$EXISTING_UUID" ] && rm -f /tmp/stark-ralph-${PROJECT_HASH}-${EXISTING_UUID}-* 2>/dev/null
  rm -f "$ANCHOR"
  echo "🧹 清理了当前会话的已完成/无效 Ralph 状态"
fi

echo "RALPH_MODE=fresh"
```

### 全新启动（RALPH_MODE=fresh）

```bash
UUID=$(python3 -c "import uuid; print(str(uuid.uuid4()).replace('-','')[:16])")
RALPH_PREFIX="/tmp/stark-ralph-${PROJECT_HASH}-${UUID}"
SESSION_DIR="${SESSIONS_DIR}/${UUID}"
LOCK_DIR="/tmp/stark-ralph-${PROJECT_HASH}-lock"

# 原子抢占：mkdir 是原子操作，失败说明有另一个会话正在启动
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "⛔ 另一个 Ralph 正在启动（lock 存在），请稍后重试"
  exit 1
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null' EXIT

# 创建会话目录
mkdir -p "$SESSION_DIR"

# 复制五文件到会话目录（从当前 STARK_SESSION_DIR 复制，禁止 fallback 到根目录）
if [ -z "$STARK_SESSION_DIR" ]; then
  echo "❌ STARK_SESSION_DIR 未设置，无法启动 Ralph"
  exit 1
fi
for f in plan.md spec.md progress.md findings.md session.yaml; do
  [ -f "${STARK_SESSION_DIR}/${f}" ] && cp "${STARK_SESSION_DIR}/${f}" "${SESSION_DIR}/${f}"
done
PLAN_PATH="${SESSION_DIR}/plan.md"

# 创建状态文件（锚文件为 per-session）
echo "$UUID" > "$ANCHOR"
echo "active" > "${RALPH_PREFIX}-active"
echo "0" > "${RALPH_PREFIX}-iterations"
echo "$(date +%s)" > "${RALPH_PREFIX}-starttime"
echo "$PLAN_PATH" > "${RALPH_PREFIX}-plan"

# 写入 owner（SESSION_ID:TIMESTAMP 格式，供 --status 展示）
echo "${SESSION_ID}:$(date +%s)" > "${RALPH_PREFIX}-owner"

# Progress 追踪文件初始化（Re-Act 增强）
touch "${RALPH_PREFIX}-progress"
echo "0" > "${RALPH_PREFIX}-stall-count"

# Lifecycle 模式（由 cc-planner EXECUTE 自动设置，用户直接 /cc-ralph 时不设置）
LIFECYCLE_MODE="${LIFECYCLE_MODE:-}"
if [ -n "$LIFECYCLE_MODE" ]; then
  echo "$LIFECYCLE_MODE" > "${RALPH_PREFIX}-lifecycle"
fi

# 覆盖 workspace 指向 ralph session 目录
echo "export STARK_SESSION_DIR=\"${SESSION_DIR}\"" >> "$CLAUDE_ENV_FILE"
# 更新指针文件
echo "${SESSION_DIR}" > "/tmp/stark-workspace-${PROJECT_HASH}-${SESSION_ID}"

echo "✅ Ralph 已启动（UUID: ${UUID}）"
echo "   Plan: ${PLAN_PATH}"
echo "   Session: ${SESSION_ID:0:12}..."
[ -n "$LIFECYCLE_MODE" ] && echo "   Lifecycle: ${LIFECYCLE_MODE}"
```

Ralph 启动时会从当前 `$STARK_SESSION_DIR` 复制五文件到新的 session 目录。如果当前 workspace 没有 plan.md，先帮用户创建。

### 启动后行为

1. 确认标志文件创建成功
2. 读取 plan.md 的 Spec 摘要章节
3. 找到第一个 ⬜ 任务开始执行
4. Stop Hook 会阻止过早退出，直到所有任务完成

### 重要规则

- **⛔ 禁止向 plan.md 追加新任务或新 Phase**。只执行已有的 ⬜ 任务
- 全部完成后输出 STARK_COMPLETE

### 恢复历史会话

不再自动恢复。如需恢复历史会话：
1. 执行 `/cc-ralph --status` 查看所有历史会话
2. 将目标会话的 plan.md 复制到当前 session：`cp .claude/sessions/{UUID}/plan.md ${STARK_SESSION_DIR}/plan.md`
3. 执行 `/cc-ralph` 启动新的 Ralph

### 环境变量（可选）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| STARK_RALPH_MAX_ITERATIONS | 20 | 最大迭代轮数 |
| STARK_RALPH_TIMEOUT_MINUTES | 180 | 超时分钟数 |
| STARK_RALPH_COMPACT_INTERVAL | 5 | compact 提示间隔轮数 |
| STARK_RALPH_MAX_STALL | 3 | Circuit Breaker: 连续停滞轮数上限 |
| STARK_RALPH_MAX_SAME_ERROR | 3 | Circuit Breaker: 同一错误重复次数上限 |
| STARK_RALPH_VERIFY_TIMEOUT | 120 | final_verify 命令超时秒数 |
| LIFECYCLE_MODE | (空) | 生命周期模式（planner-execute 时由 planner 自动设置） |

---

## 子流程 2：查看状态（`--status` / `-s`）

查看当前项目所有 Ralph 会话的运行状态。

```bash
PROJECT_HASH=$(echo -n "$PWD" | md5sum 2>/dev/null | cut -c1-8 || md5 -q -s "$PWD" | cut -c1-8)
CURRENT_SID="${CLAUDE_SESSION_ID:-}"
SESSIONS_DIR="${CLAUDE_PROJECT_DIR:-.}/.claude/sessions"

echo "═══════════════════════════════════════"
echo "  🔄 Ralph Loop Status"
echo "═══════════════════════════════════════"

setopt NULL_GLOB 2>/dev/null || true

# ───────── 活跃会话（per-session 锚文件）─────────
echo ""
echo "───────── 活跃会话 ─────────"
idx=0
for anchor in /tmp/stark-ralph-${PROJECT_HASH}-*-current; do
  [ -f "$anchor" ] || continue
  fname=$(basename "$anchor")
  sid=$(echo "$fname" | sed "s/stark-ralph-${PROJECT_HASH}-//;s/-current//")
  UUID=$(cat "$anchor" 2>/dev/null || echo "")
  [ -z "$UUID" ] && continue
  RALPH_PREFIX="/tmp/stark-ralph-${PROJECT_HASH}-${UUID}"
  [ -f "${RALPH_PREFIX}-active" ] || continue

  idx=$((idx + 1))
  marker=""
  [ "$sid" = "$CURRENT_SID" ] && marker=" ← 当前会话"

  echo ""
  echo "[${idx}] Session: ${sid:0:16}...${marker}"
  echo "    UUID: ${UUID}"

  if [ -f "${RALPH_PREFIX}-owner" ]; then
    owner=$(cat "${RALPH_PREFIX}-owner" 2>/dev/null || echo "N/A")
    echo "    Owner: ${owner:0:20}..."
  fi

  if [ -f "${RALPH_PREFIX}-iterations" ]; then
    iters=$(cat "${RALPH_PREFIX}-iterations" 2>/dev/null || echo "0")
    max_iters="${STARK_RALPH_MAX_ITERATIONS:-20}"
    echo "    迭代: ${iters}/${max_iters}"
  fi

  if [ -f "${RALPH_PREFIX}-starttime" ]; then
    start_ts=$(cat "${RALPH_PREFIX}-starttime" 2>/dev/null || echo "0")
    now_ts=$(date +%s)
    elapsed=$(( (now_ts - start_ts) / 60 ))
    timeout="${STARK_RALPH_TIMEOUT_MINUTES:-60}"
    echo "    已运行: ${elapsed}min / ${timeout}min"
  fi

  if [ -f "${RALPH_PREFIX}-plan" ]; then
    plan=$(cat "${RALPH_PREFIX}-plan" 2>/dev/null || echo "N/A")
    echo "    Plan: ${plan}"
    if [ -f "$plan" ]; then
      todo=$(grep -c '⬜' "$plan" 2>/dev/null || echo "0")
      wip=$(grep -c '🔄' "$plan" 2>/dev/null || echo "0")
      done_c=$(grep -c '✅' "$plan" 2>/dev/null || echo "0")
      echo "    任务: ✅${done_c} 🔄${wip} ⬜${todo}"
    fi
  fi

  # Re-Act 增强信息
  if [ -f "${RALPH_PREFIX}-stall-count" ]; then
    stall=$(cat "${RALPH_PREFIX}-stall-count" 2>/dev/null || echo "0")
    [ "$stall" -gt 0 ] && echo "    ⚠️ 停滞: 连续 ${stall} 轮无进展"
  fi
  if [ -f "${RALPH_PREFIX}-circuit-break-reason" ]; then
    cb_reason=$(cat "${RALPH_PREFIX}-circuit-break-reason" 2>/dev/null || echo "")
    [ -n "$cb_reason" ] && echo "    🛑 Circuit Break: ${cb_reason}"
  fi
  if [ -f "${RALPH_PREFIX}-progress" ]; then
    last_snap=$(tail -1 "${RALPH_PREFIX}-progress" 2>/dev/null || echo "")
    [ -n "$last_snap" ] && echo "    📊 最近快照: ${last_snap}"
  fi
done

# 兼容旧版 per-project 锚文件
OLD_ANCHOR="/tmp/stark-ralph-${PROJECT_HASH}-current"
if [ -f "$OLD_ANCHOR" ]; then
  OLD_UUID=$(cat "$OLD_ANCHOR" 2>/dev/null || echo "")
  if [ -n "$OLD_UUID" ] && [ -f "/tmp/stark-ralph-${PROJECT_HASH}-${OLD_UUID}-active" ]; then
    idx=$((idx + 1))
    echo ""
    echo "[${idx}] ⚠️ 旧版 Ralph（建议清理）"
    echo "    UUID: ${OLD_UUID}"
    old_owner=$(cat "/tmp/stark-ralph-${PROJECT_HASH}-${OLD_UUID}-owner" 2>/dev/null || echo "N/A")
    echo "    Owner: ${old_owner:0:20}..."
    if [ -f "/tmp/stark-ralph-${PROJECT_HASH}-${OLD_UUID}-plan" ]; then
      old_plan=$(cat "/tmp/stark-ralph-${PROJECT_HASH}-${OLD_UUID}-plan" 2>/dev/null || echo "N/A")
      echo "    Plan: ${old_plan}"
    fi
  fi
fi

[ "$idx" -eq 0 ] && echo "无活跃会话"

# ───────── 历史会话 ─────────
echo ""
echo "───────── 历史会话 ─────────"
if [ -d "$SESSIONS_DIR" ]; then
  found=0
  for session_dir in $(ls -d ${SESSIONS_DIR}/*/ 2>/dev/null); do
    session_uuid=$(basename "$session_dir")
    session_plan="${session_dir}plan.md"
    if [ -f "$session_plan" ]; then
      todo=$(grep -c '⬜' "$session_plan" 2>/dev/null || echo "0")
      done_c=$(grep -c '✅' "$session_plan" 2>/dev/null || echo "0")
      title=$(head -1 "$session_plan" 2>/dev/null | sed 's/^# //')
      status_icon="✅"
      [ "$todo" -gt 0 ] && status_icon="⬜"
      echo "${status_icon} ${session_uuid} | ${title} | ✅${done_c} ⬜${todo}"
      found=1
    fi
  done
  [ "$found" -eq 0 ] && echo "无历史会话"
else
  echo "无历史会话"
fi

echo ""
echo "═══════════════════════════════════════"
```

### 操作说明

- 取消当前会话的 Ralph：`/cc-ralph --cancel`
- 恢复历史会话：将目标会话的 plan.md 复制到项目根目录，再 `/cc-ralph`
  ```
  cp .claude/sessions/{UUID}/plan.md ${STARK_SESSION_DIR}/plan.md
  ```
- 不修改任何状态，纯只读查看

---

## 子流程 3：取消当前 Ralph（`--cancel` / `-c`）

立即停止当前会话的 Ralph 循环，清理所有标志文件。

```bash
PROJECT_HASH=$(echo -n "$PWD" | md5sum 2>/dev/null | cut -c1-8 || md5 -q -s "$PWD" | cut -c1-8)
SESSION_ID="${CLAUDE_SESSION_ID:-}"
ANCHOR="/tmp/stark-ralph-${PROJECT_HASH}-${SESSION_ID}-current"

if [ -n "$SESSION_ID" ] && [ -f "$ANCHOR" ]; then
  UUID=$(cat "$ANCHOR" 2>/dev/null || echo "")
  if [ -n "$UUID" ]; then
    rm -f /tmp/stark-ralph-${PROJECT_HASH}-${UUID}-*
  fi
  rm -f "$ANCHOR"
  echo "🛑 当前会话 Ralph 已取消（UUID: ${UUID}，Session: ${SESSION_ID:0:12}...）"
else
  # fallback: 兼容旧版 per-project 锚文件
  OLD_ANCHOR="/tmp/stark-ralph-${PROJECT_HASH}-current"
  if [ -f "$OLD_ANCHOR" ]; then
    UUID=$(cat "$OLD_ANCHOR" 2>/dev/null || echo "")
    if [ -n "$UUID" ]; then
      rm -f /tmp/stark-ralph-${PROJECT_HASH}-${UUID}-*
    fi
    rm -f "$OLD_ANCHOR"
    echo "🛑 旧版 Ralph 已取消（UUID: ${UUID}）"
  else
    echo "ℹ️ 当前会话无活跃的 Ralph"
  fi
fi
```

### 说明

- 只取消当前会话的 Ralph，不影响其他会话
- 任务进度保留在 plan.md 中，不会丢失
- 下次可重新 `/cc-ralph` 从断点继续
- 已完成的任务（✅）不受影响

---

> **关于 `/tmp/stark-ralph-*` 前缀**：这些是运行时临时文件，与 Skill 命名系统解耦，不随 cc-* 重命名变更。用户不可见。
