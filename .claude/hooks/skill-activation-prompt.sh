#!/bin/bash
# UserPromptSubmit Hook - Skill 自动激活（精简版）
# 核心：关键词/意图匹配 → 优先级排序 → 强制激活指令
#
# stdout → Claude 可见 | stderr → 用户日志

# ========== Ralph 孤儿检测函数（per-session 锚文件）==========
_ralph_orphan_check() {
  local _rph _rcurses _ranc _anc_sid _ruuid _rowner _rplan _rtodo _rdone
  _rph=$(echo -n "$PWD" | md5sum 2>/dev/null | cut -c1-8 || md5 -q -s "$PWD" | cut -c1-8)
  _rcurses=$(jq -r '.session_id // ""' <<< "$input" 2>/dev/null || echo "")

  setopt NULL_GLOB 2>/dev/null || true
  for _ranc in /tmp/stark-ralph-${_rph}-*-current; do
    [[ -f "$_ranc" ]] || continue
    # 从文件名提取 session_id
    _anc_sid=$(basename "$_ranc" | sed "s/stark-ralph-${_rph}-//;s/-current//")
    # 跳过当前会话自己的 ralph
    [[ "$_anc_sid" == "$_rcurses" ]] && continue
    _ruuid=$(cat "$_ranc" 2>/dev/null || echo "")
    [[ -z "$_ruuid" ]] && continue
    _rowner=$(cat "/tmp/stark-ralph-${_rph}-${_ruuid}-owner" 2>/dev/null || echo "")
    if [[ -z "$_rowner" ]]; then
      # owner 为空 = 真正的孤儿 Ralph（会话断开后遗留）
      _rplan=$(cat "/tmp/stark-ralph-${_rph}-${_ruuid}-plan" 2>/dev/null || echo "")
      if [[ -n "$_rplan" && -f "$_rplan" ]]; then
        _rtodo=$(grep -c '⬜' "$_rplan" 2>/dev/null || echo "0")
        _rdone=$(grep -c '✅' "$_rplan" 2>/dev/null || echo "0")
        if [[ "$_rtodo" -gt 0 ]]; then
          echo "⚠️ 发现未完成的孤儿 Ralph 任务（无 owner，${_rdone} 已完成 / ${_rtodo} 待完成）。输入 /cc-ralph --status 查看详情，或 /cc-ralph --cancel 放弃。"
          break
        fi
      fi
    fi
    # 有 owner = 别人在跑，静默跳过
  done

  # 兼容旧版 per-project 锚文件
  _ranc="/tmp/stark-ralph-${_rph}-current"
  if [[ -f "$_ranc" ]]; then
    _ruuid=$(cat "$_ranc" 2>/dev/null || echo "")
    if [[ -n "$_ruuid" ]]; then
      _rowner=$(cat "/tmp/stark-ralph-${_rph}-${_ruuid}-owner" 2>/dev/null || echo "")
      if [[ -z "$_rowner" ]]; then
        _rplan=$(cat "/tmp/stark-ralph-${_rph}-${_ruuid}-plan" 2>/dev/null || echo "")
        if [[ -n "$_rplan" && -f "$_rplan" ]]; then
          _rtodo=$(grep -c '⬜' "$_rplan" 2>/dev/null || echo "0")
          if [[ "$_rtodo" -gt 0 ]]; then
            echo "⚠️ 发现旧版孤儿 Ralph（建议 /cc-ralph --status 查看或 /cc-ralph --cancel 清理）"
          fi
        fi
      fi
    fi
  fi
}

# ========== 健康检查 + 读取输入 ==========
if ! command -v jq &> /dev/null; then
  echo "[skill-activation] WARNING: jq not found, skill activation disabled" >&2
  exit 0
fi

input=$(cat)
prompt=$(jq -r '.prompt // ""' <<< "$input" 2>/dev/null || echo "")
_session_id=$(jq -r '.session_id // ""' <<< "$input" 2>/dev/null || echo "")
_project_hash=$(echo -n "$PWD" | md5sum 2>/dev/null | cut -c1-8 || md5 -q -s "$PWD" | cut -c1-8)

if [[ -z "$prompt" ]]; then
  exit 0
fi

# 跳过 task-notification（Agent 返回结果注入的系统消息，非用户真实意图）
if echo "$prompt" | grep -q '<task-notification>' 2>/dev/null; then
  exit 0
fi

skill_rules="$CLAUDE_PROJECT_DIR/.claude/skills/skill-rules.json"

if [[ ! -f "$skill_rules" ]]; then
  echo "[skill-activation] WARNING: skill-rules.json not found" >&2
  exit 0
fi

# ========== 单次 jq 读取所有数据（skill + priority + limit）==========
# \x1c (File Separator) 分隔三段：skill_data \x1c priority_order \x1c max_skills
all_data=$(jq -r '
  [
    ([.skills | to_entries[] |
      [
        .key,
        ([.value.promptTriggers.keywords[]?] | join("\u001f")),
        ([.value.promptTriggers.intentPatterns[]?] | join("\u001f")),
        ([.value.skipConditions.keywords[]?] | join("\u001f"))
      ] | join("\u001e")
    ] | join("\n")),
    ([.priorityOrder[]?] | join("\n")),
    (.globalSettings.maxSkillsPerPrompt // 3 | tostring)
  ] | join("\u001c")
' "$skill_rules" 2>/dev/null)

# 拆分三段数据（-d '' 避免 read 在 skill_data 内部换行处截断）
IFS=$'\x1c' read -d '' -r skill_data priority_order max_skills <<< "$all_data"
max_skills="${max_skills%%$'\n'}"

# ========== 关键词/意图匹配 + skipConditions 过滤 ==========
matched=()
match_reasons=()    # 记录匹配原因
skip_log=()         # 记录被跳过的 skill

while IFS=$'\x1e' read -r name keywords_str patterns_str skip_str; do
  found=""
  match_reason=""

  # 关键词匹配
  if [[ -n "$keywords_str" ]]; then
    IFS=$'\x1f' read -ra keywords <<< "$keywords_str"
    for keyword in "${keywords[@]}"; do
      [[ -z "$keyword" ]] && continue
      # 纯英文关键词使用词边界匹配，避免子串误匹配（如 "PR" 匹配 "PRD"）
      if [[ "$keyword" =~ ^[a-zA-Z][a-zA-Z\ ]*$ ]]; then
        if printf '%s\n' "$prompt" | grep -qwF -- "$keyword" 2>/dev/null; then
          found="true"
          match_reason="keyword:$keyword(word)"
          break
        fi
        # 回退：处理中英文混排场景（如"生成PRD"、"Controller怎么实现"）
        # 如果子串存在，检查前后邻接字符不是英文字母即视为有效边界
        if [[ -z "$found" && "$prompt" == *"$keyword"* ]]; then
          local_before="${prompt%%"$keyword"*}"
          local_after="${prompt#*"$keyword"}"
          local_bc="${local_before: -1}"
          local_ac="${local_after:0:1}"
          if { [[ -z "$local_bc" ]] || ! [[ "$local_bc" =~ [a-zA-Z] ]]; } && \
             { [[ -z "$local_ac" ]] || ! [[ "$local_ac" =~ [a-zA-Z] ]]; }; then
            found="true"
            match_reason="keyword:$keyword(cjk-boundary)"
            break
          fi
        fi
      else
        if [[ "$prompt" == *"$keyword"* ]]; then
          found="true"
          match_reason="keyword:$keyword"
          break
        fi
      fi
    done
  fi

  # 意图模式匹配（合并为单次 grep）
  if [[ -z "$found" && -n "$patterns_str" ]]; then
    IFS=$'\x1f' read -ra patterns <<< "$patterns_str"
    combined=""
    for pattern in "${patterns[@]}"; do
      if [[ -n "$pattern" ]]; then
        combined="${combined:+$combined|}$pattern"
      fi
    done
    if [[ -n "$combined" ]] && printf '%s\n' "$prompt" | grep -qE "$combined" 2>/dev/null; then
      found="true"
      match_reason="pattern"
    fi
  fi

  # skipConditions 过滤
  if [[ -n "$found" && -n "$skip_str" ]]; then
    IFS=$'\x1f' read -ra skip_keywords <<< "$skip_str"
    for skip_kw in "${skip_keywords[@]}"; do
      if [[ -n "$skip_kw" && "$prompt" == *"$skip_kw"* ]]; then
        skip_log+=("$name(排斥词:$skip_kw)")
        found=""
        match_reason=""
        break
      fi
    done
  fi

  # 否定前缀检测（覆盖 keyword + intentPattern）
  # 扫描 prompt 中所有 skill 关键词，检查前方是否有否定词
  # 对 intentPattern 匹配：prompt 以否定词开头时取消匹配
  if [[ -n "$found" ]]; then
    _neg_cancelled=""
    # 策略1：扫描 keywords 列表中出现在 prompt 中的词
    if [[ -n "$keywords_str" ]]; then
      IFS=$'\x1f' read -ra _neg_keywords <<< "$keywords_str"
      for _neg_kw in "${_neg_keywords[@]}"; do
        [[ -z "$_neg_kw" ]] && continue
        if [[ "$prompt" == *"$_neg_kw"* ]]; then
          _neg_before="${prompt%%"$_neg_kw"*}"
          if [[ "$_neg_before" == *"没必要" || "$_neg_before" == *"不需要" || \
                "$_neg_before" == *"不想" || "$_neg_before" == *"不要" || \
                "$_neg_before" == *"不用" || "$_neg_before" == *"无需" || \
                "$_neg_before" == *"别" ]]; then
            skip_log+=("$name(否定前缀:$_neg_kw)")
            _neg_cancelled="true"
            break
          fi
        fi
      done
    fi
    # 策略2：prompt 以否定词开头时，对 pattern 匹配也取消（覆盖 intentPattern 场景）
    if [[ -z "$_neg_cancelled" && "$match_reason" == "pattern" ]]; then
      if [[ "$prompt" == "不想"* || "$prompt" == "不要"* || "$prompt" == "不用"* || \
            "$prompt" == "无需"* || "$prompt" == "没必要"* || "$prompt" == "不需要"* || \
            "$prompt" == "别"* ]]; then
        skip_log+=("$name(否定前缀:prompt开头)")
        _neg_cancelled="true"
      fi
    fi
    if [[ -n "$_neg_cancelled" ]]; then
      found=""
      match_reason=""
    fi
  fi

  if [[ -n "$found" ]]; then
    matched+=("$name")
    match_reasons+=("$match_reason")
  fi
done <<< "$skill_data"

# 无匹配时：仅做孤儿检测后退出
if [[ ${#matched[@]} -eq 0 ]]; then
  # Ralph 孤儿检测（无 Skill 匹配时也要检测）
  _ralph_orphan_check
  exit 0
fi

# ========== 按 priorityOrder 排序 ==========
sorted=()
for ordered_name in $priority_order; do
  for m in "${matched[@]}"; do
    if [[ "$ordered_name" == "$m" ]]; then
      sorted+=("$m")
    fi
  done
done
# 兜底：追加不在 priorityOrder 中的
for m in "${matched[@]}"; do
  local_found=""
  for s in "${sorted[@]}"; do
    if [[ "$s" == "$m" ]]; then local_found="true"; break; fi
  done
  if [[ -z "$local_found" ]]; then
    sorted+=("$m")
  fi
done

# ========== maxSkillsPerPrompt 简单截断 ==========
if [[ ${#sorted[@]} -gt $max_skills ]]; then
  sorted=("${sorted[@]:0:$max_skills}")
fi

result="${sorted[*]}"

# ========== 结论类 Skill 对抗验证标记 ==========
_conclusion_whitelist="cc-planner cc-design cc-code-reviewer cc-troubleshoot cc-api-analyzer"
if [[ -n "$_session_id" ]]; then
  _verify_marker="/tmp/stark-verify-required-${_project_hash}-${_session_id}"
  _matched_conclusion=""
  for _cs in $_conclusion_whitelist; do
    for _s in "${sorted[@]}"; do
      [[ "$_cs" == "$_s" ]] && _matched_conclusion="${_matched_conclusion:+$_matched_conclusion,}$_s"
    done
  done
  if [[ -n "$_matched_conclusion" ]]; then
    echo "$_matched_conclusion" > "$_verify_marker"
    echo "[skill-hook] 🔒 对抗验证标记: $_matched_conclusion" >&2
  fi
fi

# ========== Observatory 落盘 ==========
_obs_dir="${CLAUDE_PROJECT_DIR:-.}/.claude/observatory/activations"
mkdir -p "$_obs_dir" 2>/dev/null
_obs_date=$(date +%Y-%m-%d 2>/dev/null || echo "unknown")
_obs_ts=$(date +%H:%M:%S 2>/dev/null || echo "00:00:00")
_obs_prompt_preview=$(printf '%s' "$prompt" | head -c 30 | tr '\n' ' ')

# 构建 JSON 数组（-c 紧凑输出确保单行 JSONL）
_obs_matched_json=$(printf '%s\n' "${sorted[@]}" | jq -Rc . | jq -sc . 2>/dev/null || echo "[]")
_obs_reasons_json="[]"
if [[ ${#match_reasons[@]} -gt 0 ]]; then
  _obs_reasons_json=$(printf '%s\n' "${match_reasons[@]}" | jq -Rc . | jq -sc . 2>/dev/null || echo "[]")
fi
_obs_skipped_json="[]"
if [[ ${#skip_log[@]} -gt 0 ]]; then
  _obs_skipped_json=$(printf '%s\n' "${skip_log[@]}" | jq -Rc . | jq -sc . 2>/dev/null || echo "[]")
fi

printf '{"ts":"%s","session_id":"%s","matched":%s,"match_reasons":%s,"skipped":%s,"final":"%s","prompt_preview":"%s"}\n' \
  "$_obs_ts" "$_session_id" "$_obs_matched_json" "$_obs_reasons_json" "$_obs_skipped_json" "$result" "$_obs_prompt_preview" \
  >> "$_obs_dir/${_obs_date}.jsonl" 2>/dev/null

# ========== 输出 ==========

# stderr: 结构化匹配详情（用户可见）
echo "[skill-hook] ━━━ Skill 匹配详情 ━━━" >&2

# 输出匹配成功的 skill 及原因
for i in "${!sorted[@]}"; do
  # 查找该 skill 在 matched 数组中的原始索引以获取 reason
  reason=""
  for j in "${!matched[@]}"; do
    if [[ "${matched[$j]}" == "${sorted[$i]}" ]]; then
      reason="${match_reasons[$j]}"
      break
    fi
  done
  echo "[skill-hook] ✅ ${sorted[$i]} ← ${reason:-unknown}" >&2
done

# 输出被跳过的 skill
for entry in "${skip_log[@]}"; do
  echo "[skill-hook] ⛔ $entry" >&2
done

# 仅截断时输出截断信息
if [[ ${#matched[@]} -gt $max_skills ]]; then
  echo "[skill-hook] ✂️ 截断: ${#sorted[@]}/${#matched[@]} (max: $max_skills)" >&2
fi

echo "[skill-hook] ━━━ 最终激活: [$result] ━━━" >&2

# ========== 禁止组合检测 ==========
forbidden_warnings=""
_has_skill() { [[ " ${sorted[*]} " == *" $1 "* ]]; }

# design → code-writer（跳过 planner）
if _has_skill "cc-design" && _has_skill "cc-code-writer" && ! _has_skill "cc-planner"; then
  forbidden_warnings+="
⛔ 禁止组合检测：cc-design + cc-code-writer 不可直接组合！必须经过 cc-planner 进行任务拆解。正确链路：design → planner → code-writer。"
  echo "[skill-hook] 🚫 禁止组合: design+writer(无planner)" >&2
fi

# work-mode + work-mode（嵌套）— 不适用于激活层，跳过
# code-reviewer → code-writer（reviewer 不直接修改）
if _has_skill "cc-code-reviewer" && _has_skill "cc-code-writer"; then
  forbidden_warnings+="
⚠️ 冲突组合检测：cc-code-reviewer + cc-code-writer 同时激活。请向用户确认意图：是审查代码还是编写代码？reviewer 不应直接触发 writer 修改代码。"
  echo "[skill-hook] ⚠️ 冲突组合: reviewer+writer" >&2
fi

# stdout: 激活提示 + 可观测性指令（注入给 Claude）
echo "检测到关键词匹配，请在回复前调用 Skill 工具。匹配的 Skills（按优先级排序）: [$result]。
📋 可观测性要求：
  • 加载资源文件 → '📂 [skill/文件] ← [原因]'
  • 派发 agent → '🤖 [agent类型] ← [来源].[阶段] | 任务: [subject]'
  • 委托其他 skill 或启动 slash command → '🔗 [源skill].[阶段] → [目标skill或/command] | 原因: [触发条件]'
  格式详见 shared-rules/observability-logs.md。${forbidden_warnings}"

# ========== Ralph 孤儿检测（追加输出）==========
_ralph_orphan_check
