# CC Commit - 智能提交代码（可选推送）

分析当前变更，生成提交信息并提交，可选推送到远程。

## 参数解析

参数: $ARGUMENTS

支持以下格式：
- `/cc-commit` — 仅提交，不推送
- `/cc-commit --push` — 提交并推送到远程
- `/cc-commit -p` — 同上（短参数）

## 流程

### 1. 收集信息（并行执行）

同时运行以下 3 个命令：

```bash
git status
```

```bash
git diff --staged && git diff
```

```bash
git log --oneline -10
```

### 2. 分析变更

基于上述信息：

1. **识别变更类型**：feat / fix / refactor / docs / test / chore
2. **概括变更目的**：聚焦 "why" 而非 "what"
3. **检查敏感文件**：如有 .env、credentials、密钥文件，**警告用户并排除**
4. **遵循仓库风格**：参考最近 10 条 commit message 的格式

### 3. 暂存文件

- 优先 `git add` 具体文件名，**不用 `git add -A` 或 `git add .`**
- 排除 .env、credentials.json 等敏感文件
- 如有未跟踪文件需要提交，明确列出让用户确认

### 4. 提交

使用 HEREDOC 格式提交：

```bash
git commit -m "$(cat <<'EOF'
{type}({scope}): {简洁描述}

{详细说明（如需要）}

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

**提交信息规范**：
- 第一行：`{type}({scope}): {描述}`，≤70 字符
- 空行后可选详细说明
- 末尾固定 Co-Authored-By

### 5. 验证提交

```bash
git status
```

确认提交成功，向用户报告提交的 hash 和变更摘要。

---

> **以下步骤仅在 `--push` / `-p` 时执行**

### 6. 推送前检查

```bash
git remote -v
git branch -vv
```

确认：
- 当前分支有对应的远程跟踪分支
- 如果没有，使用 `git push -u origin {当前分支名}`
- **绝不推送到 main/master**，如果当前在 main/master 分支上，**警告用户并停止**

### 7. 推送

```bash
git push
```

如果需要设置上游：

```bash
git push -u origin $(git branch --show-current)
```

### 8. 验证推送

```bash
git log --oneline -1
git branch -vv
```

向用户报告推送结果。

## 约束

- **绝不**使用 `--amend`（除非用户明确要求）
- **绝不**使用 `--no-verify` 跳过 hooks
- **绝不** `git push --force` 或 `git push -f`
- **绝不**推送到 main/master（检测到时警告并停止）
- 无变更时不创建空提交，直接告知用户
- 如果 pre-commit hook 失败，**修复问题后创建新提交**，不 amend
- 推送失败时诊断原因（远程有新提交？权限？），不盲目重试

ARGUMENTS: $ARGUMENTS
