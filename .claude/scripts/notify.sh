#!/usr/bin/env bash
# 统一通知入口
# 用法: notify.sh "标题" "内容"
# 扩展: 设置环境变量即可启用远程渠道，无需改代码

TITLE="${1:-Claude Code}"
BODY="${2:-任务完成}"

# --- Layer 1: 本地通知（始终启用） ---

# macOS 桌面通知（自带声音）
osascript -e "display notification \"${BODY}\" with title \"${TITLE}\"" 2>/dev/null

# --- Layer 2: 远程推送（通过环境变量按需启用） ---

# Bark (iOS): 设置 NOTIFY_BARK_KEY 启用
if [[ -n "${NOTIFY_BARK_KEY}" ]]; then
  curl -sf -m 5 "https://api.day.app/${NOTIFY_BARK_KEY}/$(python3 -c "import urllib.parse; print(urllib.parse.quote('${TITLE}'))")/$(python3 -c "import urllib.parse; print(urllib.parse.quote('${BODY}'))")" >/dev/null 2>&1 &
fi

# ntfy.sh: 设置 NOTIFY_NTFY_TOPIC 启用
if [[ -n "${NOTIFY_NTFY_TOPIC}" ]]; then
  curl -sf -m 5 -H "Title: ${TITLE}" -d "${BODY}" "ntfy.sh/${NOTIFY_NTFY_TOPIC}" >/dev/null 2>&1 &
fi

# 飞书 Webhook: 设置 NOTIFY_FEISHU_KEY 启用
if [[ -n "${NOTIFY_FEISHU_KEY}" ]]; then
  curl -sf -m 5 -X POST "https://open.feishu.cn/open-apis/bot/v2/hook/${NOTIFY_FEISHU_KEY}" \
    -H 'Content-Type: application/json' \
    -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"${TITLE}: ${BODY}\"}}" >/dev/null 2>&1 &
fi

# 自定义命令: 设置 NOTIFY_CUSTOM_CMD 启用（万能逃生口）
if [[ -n "${NOTIFY_CUSTOM_CMD}" ]]; then
  eval "${NOTIFY_CUSTOM_CMD}" "${TITLE}" "${BODY}" >/dev/null 2>&1 &
fi

exit 0
