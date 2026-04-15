#!/usr/bin/env bash
# Stop Hook - Ralph 循环守护（精简版）
# 核心三件：迭代计数 + 超时检测 + 进度检测
#
# stdin: {"session_id": str, "stop_hook_active": bool, ...}
# exit 0 = 放行停止, exit 2 = 阻止停止（继续工作）

set -euo pipefail

# ========== 配置 ==========
STARK_RALPH_MAX_ITERATIONS="${STARK_RALPH_MAX_ITERATIONS:-20}"
STARK_RALPH_TIMEOUT_MINUTES="${STARK_RALPH_TIMEOUT_MINUTES:-180}"
NO_PROGRESS_LIMIT=2  # 连续无进度次数上限

# ========== 读取 stdin ==========
input=$(cat)

# ========== 解析 JSON 字段（纯 bash + python3 最小化） ==========
parse_json_field() {
  local field="$1"
  echo "$input" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    v = d.get('$field', '')
    print(str(v).lower() if isinstance(v, bool) else str(v))
except: print('')
" 2>/dev/null || echo ""
}

SESSION_ID=$(parse_json_field "session_id")
STOP_HOOK_ACTIVE=$(parse_json_field "stop_hook_active")

# 无 session_id → 跳过
[[ -z "$SESSION_ID" ]] && exit 0

# stop_hook_active=true → 防无限循环，直接放行
[[ "$STOP_HOOK_ACTIVE" == "true" ]] && exit 0

# ========== 会话隔离：查找 Ralph 锚文件 ==========
if command -v md5sum &>/dev/null; then
  PROJECT_HASH=$(echo -n "$PWD" | md5sum | cut -c1-8)
else
  PROJECT_HASH=$(echo -n "$PWD" | md5 -q | cut -c1-8)
fi

ANCHOR="/tmp/stark-ralph-${PROJECT_HASH}-${SESSION_ID}-current"

# 无锚文件 → 不在 Ralph 模式，放行
if [[ ! -f "$ANCHOR" ]]; then
  # 兼容旧版 per-project 锚文件
  OLD_ANCHOR="/tmp/stark-ralph-${PROJECT_HASH}-current"
  if [[ -f "$OLD_ANCHOR" ]]; then
    ANCHOR="$OLD_ANCHOR"
  else
    exit 0
  fi
fi

UUID=$(cat "$ANCHOR" 2>/dev/null || echo "")
[[ -z "$UUID" ]] && exit 0

RALPH_PREFIX="/tmp/stark-ralph-${PROJECT_HASH}-${UUID}"

# 无 active 标记 → 放行
[[ ! -f "${RALPH_PREFIX}-active" ]] && exit 0

# ========== cleanup 函数 ==========
cleanup() {
  local reason="${1:-unknown}"
  # Lifecycle handoff
  local lifecycle_file="${RALPH_PREFIX}-lifecycle"
  if [[ -f "$lifecycle_file" ]]; then
    local lifecycle_mode
    lifecycle_mode=$(cat "$lifecycle_file" 2>/dev/null || echo "")
    if [[ "$lifecycle_mode" == "planner-execute" ]]; then
      local workspace_dir
      workspace_dir=$(cat "${RALPH_PREFIX}-plan" 2>/dev/null | xargs dirname 2>/dev/null || echo "")
      if [[ -n "$workspace_dir" && -d "$workspace_dir" ]]; then
        echo "$reason" > "${workspace_dir}/.ralph-handoff"
      fi
    fi
  fi
  rm -f "${RALPH_PREFIX}"-*
  rm -f "$ANCHOR"
  echo "[ralph-stop] cleanup: $reason" >&2
}

# ========== 检查 1: 超时 ==========
starttime_file="${RALPH_PREFIX}-starttime"
if [[ -f "$starttime_file" ]]; then
  start_ts=$(cat "$starttime_file" 2>/dev/null || echo "0")
  now_ts=$(date +%s)
  elapsed_min=$(( (now_ts - start_ts) / 60 ))
  if [[ "$elapsed_min" -ge "$STARK_RALPH_TIMEOUT_MINUTES" ]]; then
    echo "[ralph-stop] 超时: ${elapsed_min}min >= ${STARK_RALPH_TIMEOUT_MINUTES}min" >&2
    cleanup "ralph-failed:timeout:${elapsed_min}min"
    exit 0  # 放行停止
  fi
else
  elapsed_min=0
fi

# ========== 检查 2: 迭代计数 ==========
iterations_file="${RALPH_PREFIX}-iterations"
current_iter=0
[[ -f "$iterations_file" ]] && current_iter=$(cat "$iterations_file" 2>/dev/null || echo "0")

if [[ "$current_iter" -ge "$STARK_RALPH_MAX_ITERATIONS" ]]; then
  echo "[ralph-stop] 迭代上限: ${current_iter} >= ${STARK_RALPH_MAX_ITERATIONS}" >&2
  cleanup "ralph-failed:iterations:${current_iter}"
  exit 0  # 放行停止
fi

# ========== 检查 3: 进度检测 ==========
no_progress_file="${RALPH_PREFIX}-noprogress"
no_progress_count=0
[[ -f "$no_progress_file" ]] && no_progress_count=$(cat "$no_progress_file" 2>/dev/null || echo "0")

# 用 git diff 检测是否有文件变更
has_progress=false
if git diff --stat HEAD 2>/dev/null | grep -q '.'; then
  has_progress=true
fi

# 检查 plan.md 是否有任务状态变更
plan_file=""
[[ -f "${RALPH_PREFIX}-plan" ]] && plan_file=$(cat "${RALPH_PREFIX}-plan" 2>/dev/null || echo "")
if [[ -n "$plan_file" && -f "$plan_file" ]]; then
  completed=$(grep -c '✅' "$plan_file" 2>/dev/null || echo "0")
  last_completed_file="${RALPH_PREFIX}-lastcompleted"
  last_completed=0
  [[ -f "$last_completed_file" ]] && last_completed=$(cat "$last_completed_file" 2>/dev/null || echo "0")
  if [[ "$completed" -gt "$last_completed" ]]; then
    has_progress=true
    echo "$completed" > "$last_completed_file"
  fi
fi

if [[ "$has_progress" == "false" ]]; then
  no_progress_count=$((no_progress_count + 1))
  echo "$no_progress_count" > "$no_progress_file"
  if [[ "$no_progress_count" -ge "$NO_PROGRESS_LIMIT" ]]; then
    echo "[ralph-stop] 连续 ${no_progress_count} 次无进度，终止" >&2
    cleanup "ralph-failed:no-progress:${no_progress_count}"
    exit 0  # 放行停止
  fi
else
  echo "0" > "$no_progress_file"
fi

# ========== 继续工作：递增迭代计数，阻止停止 ==========
echo $((current_iter + 1)) > "$iterations_file"

# 输出决策（Claude 可见）
cat << EOF
继续执行 Ralph 循环。
- 迭代: $((current_iter + 1))/${STARK_RALPH_MAX_ITERATIONS}
- 运行时间: ${elapsed_min}min/${STARK_RALPH_TIMEOUT_MINUTES}min
- 进度: $(if [[ "$has_progress" == "true" ]]; then echo "有新进度"; else echo "无新进度 (${no_progress_count}/${NO_PROGRESS_LIMIT})"; fi)

请继续执行 plan.md 中的下一个待办任务。
EOF

exit 2  # 阻止停止
