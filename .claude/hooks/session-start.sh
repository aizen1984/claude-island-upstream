#!/bin/bash
# SessionStart Hook - 导出 CLAUDE_SESSION_ID 环境变量
# 将 stdin JSON 中的 session_id 写入 CLAUDE_ENV_FILE，使后续所有 bash 命令可用
#
# stdin: {"session_id": str, ...}
# 通过 CLAUDE_ENV_FILE 持久化环境变量

input=$(cat)
read -r sid source_type <<< $(echo "$input" | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('session_id',''), d.get('source',''))" 2>/dev/null || echo "")

if [[ -n "$sid" && -n "$CLAUDE_ENV_FILE" ]]; then
  echo "export CLAUDE_SESSION_ID=\"$sid\"" >> "$CLAUDE_ENV_FILE"

  # --- 会话 Workspace 隔离 ---
  # 参考: shared-rules/session-workspace.md

  # 确定项目根目录
  PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

  # 创建 session workspace 目录
  WORKSPACE="${PROJECT_DIR}/.claude/sessions/${sid}"
  mkdir -p "$WORKSPACE"

  # 导出 STARK_SESSION_DIR 环境变量
  echo "export STARK_SESSION_DIR=\"${WORKSPACE}\"" >> "$CLAUDE_ENV_FILE"

  # 写指针文件（备用通道，当环境变量不可用时）
  PROJECT_HASH=$(echo -n "$PROJECT_DIR" | md5sum 2>/dev/null | cut -c1-8 || md5 -q -s "$PROJECT_DIR" | cut -c1-8)
  echo "$WORKSPACE" > "/tmp/stark-workspace-${PROJECT_HASH}-${sid}"

  # --- Handoff 检测：仅在新会话/显式 clear 时触发（告示板模式，非自动认领）---
  # source 白名单：startup（全新 CLI）/ clear（/clear 后）才扫描 handoff
  # 跳过 resume（继续旧会话）/ compact（自动压缩后重载）——这两种是"同一会话延续"，
  # 读取跨任务 handoff 会污染上下文（2026-04-09 修复）
  if [[ "$source_type" == "startup" || "$source_type" == "clear" ]]; then
    HANDOFF_DIR="${PROJECT_DIR}/.claude/handoffs"
    if [[ -d "$HANDOFF_DIR" ]]; then
      # 单次 python3 调用完成：扫描目录 + 解析 frontmatter + 过滤 consumed_by
      # 输出纯文本提示（告示板），不再自动写 STARK_SESSION_DIR 或强制 Read
      # 归属绑定协议见 shared-rules/session-workspace.md + cc-handoff.md
      HANDOFF_NOTICE=$(HANDOFF_DIR="$HANDOFF_DIR" python3 <<'PYEOF'
import os, re, time, sys

handoff_dir = os.environ['HANDOFF_DIR']
if not os.path.isdir(handoff_dir):
    sys.exit(0)

now = time.time()
active = []   # 新格式，consumed_by 为空
legacy = []   # 无 frontmatter 老格式

try:
    entries = sorted(os.listdir(handoff_dir))
except OSError:
    sys.exit(0)

for name in entries:
    if not name.endswith('.md'):
        continue
    path = os.path.join(handoff_dir, name)
    if not os.path.isfile(path):
        continue
    # 跳过 >24h 文件
    try:
        if now - os.path.getmtime(path) > 86400:
            continue
    except OSError:
        continue
    # 读前 4KB 找 frontmatter
    try:
        with open(path, 'r', encoding='utf-8') as f:
            head = f.read(4096)
    except Exception:
        continue
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', head, re.DOTALL)
    if not m:
        legacy.append(path)
        continue
    fm = {}
    for line in m.group(1).splitlines():
        if ':' in line:
            k, _, v = line.partition(':')
            fm[k.strip()] = v.strip().strip('"').strip("'")
    if fm.get('consumed_by', '').strip():
        # 已被其他 session 认领，静默跳过
        continue
    active.append({
        'path': path,
        'task_tag': fm.get('task_tag', '(未标注)') or '(未标注)',
        'session_id': fm.get('session_id', '(未标注)') or '(未标注)',
        'created_at': fm.get('created_at', '(未标注)') or '(未标注)',
    })

lines = []
if len(active) == 1:
    a = active[0]
    lines.append("⚡ 发现 1 个未认领 handoff（告示板，不自动加载）：")
    lines.append(f"  path:       {a['path']}")
    lines.append(f"  task_tag:   {a['task_tag']}")
    lines.append(f"  session_id: {a['session_id']}")
    lines.append(f"  created_at: {a['created_at']}")
    lines.append("")
    lines.append("  → 如与本会话任务相关: 执行 /cc-handoff restore 命令认领并加载上下文")
    lines.append("  → 如与本会话任务无关: 直接忽略即可，hook 不会自动读取文件内容")
elif len(active) > 1:
    lines.append(f"⚡ 发现 {len(active)} 个未认领 handoff（告示板，不自动加载）：")
    for a in active:
        lines.append(f"  - {a['path']}")
        lines.append(f"      tag={a['task_tag']}, created={a['created_at']}")
    lines.append("")
    lines.append("  → 如需恢复: 执行 /cc-handoff restore 并指定具体文件路径")
    lines.append("  → 如均无关: 直接忽略即可")

if legacy:
    if lines:
        lines.append("")
    lines.append(f"⚠️ 另发现 {len(legacy)} 个老格式 handoff（无 frontmatter，hook 不处理）：")
    for p in legacy:
        lines.append(f"  - {p}")
    lines.append("  → 如需使用: 手动判断任务归属；如已过期: 移到 .claude/handoffs/consumed/ 归档")

if lines:
    print('\n'.join(lines))
PYEOF
)
      if [[ -n "$HANDOFF_NOTICE" ]]; then
        echo "$HANDOFF_NOTICE"
      fi
    fi
  fi

  # --- /clear 联动：清理当前 session 的五文件 ---
  if [[ "$source_type" == "clear" ]]; then
    cleaned=""
    for f in plan.md spec.md progress.md findings.md session.yaml; do
      if [[ -f "${WORKSPACE}/${f}" ]]; then
        rm -f "${WORKSPACE}/${f}"
        cleaned="${cleaned} ${f}"
      fi
    done
    if [[ -n "$cleaned" ]]; then
      echo "🗑️ /clear 联动清理:${cleaned}"
    fi
  fi

  # --- 兜底清理：残留的 tdd-session-active 标记文件 ---
  # tdd-session-active 由 code-writer/work-mode 创建，正常由它们自行清除。
  # 若 subagent 异常退出导致残留，会持续阻断所有源码修改（tdd-guard deny）。
  # 新会话启动时检测并清理超过 2 小时的残留文件。
  TDD_MARKER="${PROJECT_DIR}/.claude/tdd-session-active"
  if [[ -f "$TDD_MARKER" ]]; then
    MARKER_AGE=$(( $(date +%s) - $(stat -f %m "$TDD_MARKER" 2>/dev/null || stat -c %Y "$TDD_MARKER" 2>/dev/null || echo 0) ))
    if [[ $MARKER_AGE -gt 7200 ]]; then
      rm -f "$TDD_MARKER"
      echo "[session-start] ⚠️ 清理残留 tdd-session-active（已存在 ${MARKER_AGE}s）" >&2
    fi
  fi

  # 清理 7 天以上旧 session 目录
  SESSIONS_BASE="${PROJECT_DIR}/.claude/sessions"
  if [[ -d "$SESSIONS_BASE" ]]; then
    find "$SESSIONS_BASE" -mindepth 1 -maxdepth 1 -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true
  fi

  # --- cc-ob-session-log: 智能提醒注入（仅当用户已 opt-in 且今日 daily note 不存在时） ---
  # opt-in 方式：设置环境变量 OB_VAULT_ROOT 指向 Obsidian vault 根目录
  # 示例: export OB_VAULT_ROOT="/Users/caochen/tools/shuhe-kb/数禾项目"
  if [[ -n "$OB_VAULT_ROOT" && -d "$OB_VAULT_ROOT/daily-notes" ]]; then
    TODAY=$(date +%Y-%m-%d)
    TODAY_NOTE="$OB_VAULT_ROOT/daily-notes/${TODAY}.md"
    # 仅当今日 daily note 不存在且无 handoff 告示（避免与其他提醒冲突）时提示
    if [[ ! -f "$TODAY_NOTE" && -z "$HANDOFF_NOTICE" ]]; then
      echo "💡 cc-ob-session-log: 今日尚无 daily note。若本次会话有实质性工作（开发/排障/设计/调研），结束前执行 /session-log 记录"
    fi
  fi

  # --- skill 元任务警告注入（防 Iter 23+25 踩坑 2 重演）---
  # 触发条件: source_type=startup|clear + PROJECT_DIR 属于 my_claude 或 vipship
  # 原理: 参与 skill 元任务（修 cc-* / shared-rules / hooks）的会话才需要看到这个警告
  # 详见: /Users/caochen/tools/shuhe-kb/数禾项目/my_claude/审计报告/Skills全量评审-2026-04-07/fixes-log.md Iter 26
  if [[ "$source_type" == "startup" || "$source_type" == "clear" ]]; then
    if [[ "$PROJECT_DIR" == *"my_claude"* || "$PROJECT_DIR" == *"vipship"* ]]; then
      META_WARNINGS_FILE="/Users/caochen/IdeaProjects/ai/my_claude/.claude/hooks/skill-meta-task-warnings.md"
      if [[ -f "$META_WARNINGS_FILE" ]]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        cat "$META_WARNINGS_FILE"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
      fi
    fi
  fi
fi

exit 0
