# CC Observatory - Skill 使用效果分析

分析 `.claude/observatory/` 中积累的 skill 使用数据，生成结构化报告。

## 参数解析

参数: $ARGUMENTS

支持以下格式：
- `/cc-observatory` — 分析最近 14 天，含洞察建议
- `/cc-observatory 7` — 分析最近 N 天，含洞察建议
- `/cc-observatory --json` — 仅输出原始 JSON（供程序消费，不做洞察）

## 流程

### Step 1: 运行分析脚本

```bash
node $CLAUDE_PROJECT_DIR/.claude/scripts/skill-observatory-report.js --days {N}
```

参数映射：
- 无参数 → `--days 14`
- 数字参数 → `--days {数字}`
- `--json` → 追加 `--json` flag，跳过 Step 3

### Step 2: 展示报告

将脚本输出直接展示给用户。

如果输出为"No observatory data found"，提示：
> Observatory 数据需要 hook 采集积累。正常使用 Claude Code 工作后数据会自动产生。
> 检查 `.claude/observatory/` 目录是否存在数据文件。

### Step 3: 洞察分析（默认执行，`--json` 时跳过）

在报告数据基础上，分析并输出：

1. **Skill 健康度判断**：
   - 高频 + 低纠正 = 健康
   - 高频 + 高纠正 = 需要改进（标注具体摩擦点）
   - 低频 + 高 IO = 可能过度加载（建议瘦身）
   - 从未激活 = 考虑是否需要保留或调整触发词

2. **触发词质量**：
   - 仅靠 pattern 匹配激活的 skill → 触发词可能不够精确
   - 高跳过/否决率的 skill → 触发词可能误匹配

3. **协作模式洞察**：
   - 高共现组合 → 是否需要合并为流水线？
   - 从未共现但逻辑相关的 skill → 是否缺少协作路径？

4. **可操作建议**（top 3，按影响排序）：
   - 每条建议包含：skill 名 + 问题 + 具体改进方向

## 前置条件

- `.claude/hooks/skill-activation-prompt.sh` 已包含 Observatory 落盘逻辑
- `.claude/hooks/skill-io-tracker.js` 已配置写入 `.claude/observatory/sessions/`
- `.claude/hooks/skill-correction-detector.js` 已注册到 settings.json
- `.claude/scripts/skill-observatory-report.js` 存在

缺少任一组件时，提示用户从 my_claude 仓库拷贝对应文件。
