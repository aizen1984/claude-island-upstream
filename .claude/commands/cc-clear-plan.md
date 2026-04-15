# CC Clear Plan - 清理当前会话的五文件

清理当前 session workspace 中的 planner 五文件（plan.md/spec.md/progress.md/findings.md/session.yaml）。

## 执行流程

```bash
WORKSPACE="${STARK_SESSION_DIR:-}"

if [ -z "$WORKSPACE" ]; then
  echo "❌ STARK_SESSION_DIR 未设置，无文件可清理"
  exit 0
fi

if [ ! -d "$WORKSPACE" ]; then
  echo "❌ Workspace 目录不存在: $WORKSPACE"
  exit 0
fi

# 检查是否有文件
found=0
for f in plan.md spec.md progress.md findings.md session.yaml; do
  [ -f "${WORKSPACE}/${f}" ] && found=1 && break
done

if [ "$found" -eq 0 ]; then
  echo "ℹ️ 当前 session 无任务文件，无需清理"
  exit 0
fi

# 显示即将清理的内容
echo "📂 Workspace: $WORKSPACE"
echo ""
for f in plan.md spec.md progress.md findings.md session.yaml; do
  if [ -f "${WORKSPACE}/${f}" ]; then
    size=$(wc -c < "${WORKSPACE}/${f}" 2>/dev/null | tr -d ' ')
    echo "  🗑️ ${f} (${size} bytes)"
  fi
done
echo ""

# 执行清理
rm -f "${WORKSPACE}/plan.md" "${WORKSPACE}/spec.md" "${WORKSPACE}/progress.md" "${WORKSPACE}/findings.md" "${WORKSPACE}/session.yaml"
echo "✅ 五文件已清理，当前 session 可开始新任务"
```

## 说明

- 仅清理当前 session 的五文件，不影响其他 session
- `/clear` 命令会自动触发同样的清理（通过 session-start.sh 联动）
- 清理后可直接开始新的 planner 任务
