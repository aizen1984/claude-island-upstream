# Eval Skill 工作流

## 入口分发

```
/cc-eval <skill> [--auto-fix]
  │
  ├─ Step 0: 验证 skill 存在 + 读取 config.yaml
  ├─ Step 1: Layer 1（bash eval/scripts/layer1-all.sh）
  │   └─ 失败 → 输出报告，停止
  ├─ Step 2: Layer 2（LLM-as-Judge）
  │   ├─ 读取 golden-set + rubric
  │   ├─ 对每个 case: Executor → Grader（独立 agent）
  │   └─ 聚合评分 + 输出报告
  ├─ [--auto-fix] Step 3: Layer 3（闭环）
  │   ├─ 检查达标 → 完成
  │   ├─ 收集建议 → Fixer Agent → 重跑 L1+L2
  │   └─ 循环直到退出条件
  └─ 输出最终报告
```

---

## Step 0: 初始化

```yaml
行为:
  - 读取 eval/config.yaml
  - 验证目标 skill 在 skill-rules.json 中存在
  - 确定 skill_type（从 config.layer2.skill_type_map 查）
  - 读取对应 rubric 文件（eval/rubrics/domain/{type}-skills.yaml）
  - 读取 golden-set（eval/golden-sets/{skill}.yaml）
  - 如果 golden-set 不存在，输出警告并只跑 Layer 1
```

---

## Step 1: Layer 1 执行

```yaml
行为:
  - 运行: Bash("bash eval/scripts/layer1-all.sh --skill {skill}")
  - 解析 JSON 输出
  - 如果 status=fail 且 config.layer1.fail_fast=true:
      输出失败详情，停止
  - 如果 status=pass:
      继续 Step 2
```

---

## Step 2: Layer 2 — LLM-as-Judge

对 golden-set 中的每个 case 执行：

### 2.1 Executor Agent 派发

```yaml
agent_config:
  subagent_type: general-purpose
  model: sonnet                    # 用 sonnet 执行（成本低）
  isolation: worktree              # 隔离执行环境

prompt: |
  {executor_prompt_template}
  # 从 prompts.md "Executor Agent Prompt" 填充变量
```

**对 eval/java-test 靶标的 case**：Executor 在 worktree 中读取 `eval/java-test/` 下的 Java 文件，模拟用户发送审查请求。

**对无靶标的 case**（如 planner 的规划测试）：Executor 描述场景，收集 Skill 的规划输出。

### 2.2 Grader Agent 派发

```yaml
agent_config:
  subagent_type: general-purpose
  model: opus                      # 用 opus 评分（需要判断力）
  # 不设 isolation — Grader 只读数据不改文件

prompt: |
  {grader_prompt_template}
  # 从 prompts.md "Grader Agent Prompt" 填充变量
  # actual_output = Executor 的输出
  # domain_rubric = 对应 Skill 的 rubric
```

**关键：Grader 不能看到 Executor 的执行过程，只看最终 actual_output。**

### 2.3 结果聚合

```yaml
行为:
  - 收集所有 case 的 Grader 评分
  - 计算加权平均分
  - 汇总 must_include/must_not_include 检查结果
  - 合并所有 suggestions（去重）
  - 生成 Layer 2 报告段
```

---

## Step 3: Layer 3 — 自动修复闭环

仅在 `--auto-fix` 模式触发。

### 3.1 达标检查

```yaml
条件:
  avg_score >= config.layer2.pass_threshold (0.90):
    → 输出 "✅ 达标"，跳到报告生成
  otherwise:
    → 继续修复流程
```

### 3.2 收敛检测

```yaml
条件:
  round > 1 且 (score - prev_score) < config.layer3.convergence_threshold:
    no_improve_count += 1
    if no_improve_count >= config.layer3.no_improvement_exit:
      → 输出 "⚠️ 收敛，停止"
  round > config.layer3.max_rounds:
    → 输出 "⚠️ 达到最大轮次"
```

### 3.3 Fixer Agent 派发

```yaml
agent_config:
  subagent_type: general-purpose
  model: opus                      # 修改需要判断力
  mode: acceptEdits                # 允许编辑文件

prompt: |
  {fixer_prompt_template}
  # 从 prompts.md "Fixer Agent Prompt" 填充变量
  # suggestions = 所有 P0+P1 建议
```

### 3.4 修复后验证

```yaml
行为:
  - 重跑 Layer 1: Bash("bash eval/scripts/layer1-all.sh --skill {skill}")
  - 如果 Layer 1 失败:
      - git checkout 回滚 Fixer 修改的文件
      - 输出 "❌ 修复破坏结构，已回滚"
      - 停止闭环
  - 如果 Layer 1 通过:
      - 继续下一轮（回到 Step 2）
```

---

## 报告生成

每轮评估结束后生成两个文件：

### JSON 报告

```yaml
路径: eval/reports/{date}-{skill}-eval.json
内容: 设计文档 §1.2 定义的 schema
```

### Markdown 报告

```yaml
路径: eval/reports/{date}-{skill}-eval.md
结构:
  - 元信息（skill/日期/模式/轮次）
  - Layer 1 结果表
  - Layer 2 评分矩阵（每 case × 每维度）
  - Layer 3 修复轨迹（如有）
  - 汇总分数和趋势
  - 改进建议（未执行的 P2）
```

---

## 快捷模式

| 命令 | 执行内容 |
|------|---------|
| `/cc-eval <skill>` | Layer 1 + Layer 2，输出报告 |
| `/cc-eval <skill> --auto-fix` | Layer 1 + 2 + 3，自动闭环 |
| `/cc-eval --all` | 全部 Skill Layer 1（CLI 委托） |
| `/cc-eval --smoke` | 每个 Skill 的第一个 normal case，快速冒烟 |
