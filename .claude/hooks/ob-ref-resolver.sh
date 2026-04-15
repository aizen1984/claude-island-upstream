#!/bin/bash
# UserPromptSubmit Hook - Obsidian 文档引用解析
# 检测 prompt 中的 #xxx 模式，自动搜索 Obsidian vault 并注入文件路径
#
# 用法：在 prompt 中使用 #文件名 引用知识库文档
# 示例：#VipShip基线  #退款域  #首页
#
# stdout → Claude 可见 | stderr → 用户日志

input=$(cat)
prompt=$(jq -r '.prompt // ""' <<< "$input" 2>/dev/null || echo "")

[[ -z "$prompt" ]] && exit 0

# 跳过 markdown 标题行（行首 # 开头）和纯数字引用（如 #123）
# 只处理句中的 #文件名 模式

VAULT="/Users/caochen/tools/shuhe-kb/数禾项目"

# 提取 #xxx 模式（取 # 后到空格/逗号/句号等为止的内容）
# 排除：行首 markdown 标题、纯数字（issue编号）、单个字符
refs=()
while IFS= read -r ref; do
  [[ -z "$ref" ]] && continue
  # 跳过纯数字（如 #123 issue 编号）
  [[ "$ref" =~ ^[0-9]+$ ]] && continue
  # 跳过单个字符
  [[ ${#ref} -lt 2 ]] && continue
  refs+=("$ref")
done < <(echo "$prompt" | grep -oE '(^|[^#])#([^ #,，。？！、]+)' | grep -o '#[^ #,，。？！、]*' | sed 's/^#//' | sed 's/[,.:;!?，。？！、]*$//')

[[ ${#refs[@]} -eq 0 ]] && exit 0

echo "[ob-ref] ━━━ Obsidian 引用解析 ━━━" >&2

results=""
for ref in "${refs[@]}"; do
  echo "[ob-ref] 🔍 搜索: #${ref}" >&2

  # 搜索策略：精确文件名 > 模糊文件名 > 目录名
  found=""

  # 1. 精确匹配文件名（不含扩展名，忽略大小写）
  exact=$(find "$VAULT" -iname "${ref}.md" ! -path "*/归档/*" 2>/dev/null | head -3)
  if [[ -n "$exact" ]]; then
    found="$exact"
    echo "[ob-ref] ✅ #${ref} → 精确匹配" >&2
  fi

  # 2. 模糊匹配文件名（包含关键词，忽略大小写）
  if [[ -z "$found" ]]; then
    fuzzy=$(find "$VAULT" -iname "*${ref}*" -iname "*.md" ! -path "*/归档/*" 2>/dev/null | head -5)
    if [[ -n "$fuzzy" ]]; then
      found="$fuzzy"
      count=$(echo "$fuzzy" | wc -l | tr -d ' ')
      echo "[ob-ref] ✅ #${ref} → 模糊匹配 (${count} 个)" >&2
    fi
  fi

  # 3. 目录名匹配（找目录下的首页/基线，忽略大小写）
  if [[ -z "$found" ]]; then
    dir_match=$(find "$VAULT" -type d -iname "*${ref}*" ! -path "*/归档/*" 2>/dev/null | head -3)
    if [[ -n "$dir_match" ]]; then
      for dir in $dir_match; do
        for entry_name in "首页.md" "基线文档.md" "README.md"; do
          if [[ -f "$dir/$entry_name" ]]; then
            found="${found:+$found
}$dir/$entry_name"
            break
          fi
        done
        # 如果没有入口文件，找目录下第一个 .md
        if [[ -z "$found" ]]; then
          first_md=$(find "$dir" -maxdepth 1 -name "*.md" 2>/dev/null | head -1)
          [[ -n "$first_md" ]] && found="$first_md"
        fi
      done
      [[ -n "$found" ]] && echo "[ob-ref] ✅ #${ref} → 目录匹配" >&2
    fi
  fi

  if [[ -n "$found" ]]; then
    results+="
📎 #${ref} 匹配到以下文档：
$(echo "$found" | sed 's|^|  - |')
"
  else
    results+="
📎 #${ref} 在知识库中未找到匹配，请尝试手动搜索。
"
    echo "[ob-ref] ⚠️ #${ref} → 未找到" >&2
  fi
done

echo "[ob-ref] ━━━━━━━━━━━━━━━━━━━━━" >&2

# 输出给 Claude（additionalContext）
echo "${results}
请读取上述匹配到的文档作为上下文使用。如果有多个匹配，选择最相关的读取。"
