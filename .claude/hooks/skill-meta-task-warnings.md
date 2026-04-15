⚠️ **Skills 元任务防线** — 编辑 my_claude 内 `.claude/skills/` / `shared-rules/` / `hooks/` 之前 3 秒自检：

1. **路径绝对**: 所有 Read/Edit/Write 用 `/Users/caochen/IdeaProjects/ai/my_claude/.claude/skills/...`
2. **Bash 先 cd**: `python .claude/skills/...` / `quick_validate.py` / `check_consistency.py` 之前必先 `cd /Users/caochen/IdeaProjects/ai/my_claude`（否则跑 vipship stale 副本 = **假阳性**）
3. **vipship 只读**: `vipship/.claude/skills/` 是 Iter 19 快照，禁止直接写

详细规则 + Iter 23/25 踩坑复盘: memory `feedback_my_claude_is_source_of_truth.md`
