# cc-work-mode 工作流

---

# 一、ANALYZE 阶段：深度分析

## 阶段目标

在动手之前，充分理解需求和约束条件。

**核心原则**：先理解，再动手。

## 权限

| 操作 | 允许 |
|------|------|
| 读代码 | YES |
| 写代码/计划/运行命令 | NO |

## 工作流程

### 1. 需求理解

- 用户的核心目标是什么？
- 需要实现什么功能？
- 有哪些隐含的需求？
- 如有不明确，使用 AskUserQuestion 询问

### 2. 约束识别

**技术约束**：技术栈、现有代码结构、性能要求、安全要求

**业务约束**：时间限制、资源限制、兼容性要求

### 3. 现有代码分析（如需修改）

读取相关文件 -> 理解现有设计 -> 识别影响范围

### 4. 验收标准确定

- 功能验收标准
- 测试验收标准
- 代码质量标准

## 产出：需求理解报告

> 输出格式模板见 `prompts.md` 第一节

## 阶段转移条件

1. 核心目标明确
2. 功能需求清晰
3. 约束条件识别完成
4. 验收标准确定
5. 待澄清问题已解决

## 提示语

```
>>> ANALYZE 阶段（只读模式）
正在深度分析需求...

<<< ANALYZE 阶段完成
需求理解报告已生成，准备进入 PLAN 阶段。
```

---

# 二、PLAN 阶段：计划与任务拆分

## 阶段目标

将需求拆分为原子任务，生成可执行的任务清单。

**核心原则**：任务粒度 2-5 分钟，每个任务有明确验证方式，正确设置依赖关系。

## 权限

| 操作 | 允许 |
|------|------|
| 读代码 / 写计划文件 / TaskCreate | YES |
| 写代码 / 运行命令 | NO |

## 工作流程

### 1. 任务拆分

**拆分原则**：每个任务 2-5 分钟可完成，任务之间低耦合，可并行的尽量并行。

**任务结构**：
```yaml
subject: 任务标题（命令式）
description: |
  详细描述（做什么、改哪个文件、验证方式）
activeForm: 进行时描述
metadata:
  estimated_loc: 30
  file_path: 文件路径
  operation: create/modify/delete
```

### 2. 生成外置计划文件

> 文件模板见 `resources.md` 第四节

**文件位置**：`.claude/work-plans/{timestamp}-{name}.md`

### 3. 创建 TaskCreate 任务池

```
TaskCreate(subject="任务标题", description="详细描述", activeForm="进行时描述")
TaskUpdate(taskId="2", addBlockedBy=["1"])  # 设置依赖
```

### 4. 依赖关系分析

- **顺序依赖**：任务 B 必须在任务 A 之后
- **数据依赖**：任务 B 需要任务 A 的输出
- **数据流依赖**（outputs/inputs）：任务 B 的 `inputs` 显式引用任务 A 的 `outputs`（如 "T1.1.1 的 User 实体类"）。冲突检测时会据此做依赖感知排序，而非被动移除
- **资源依赖**：任务 A 和 B 修改同一文件
- **集成依赖**：任务 A 的产出（接口/组件）需要被同批次任务 B 使用
- 无依赖的任务可以并行执行

### 5. 集成预告预检（并行任务必做）

> 当同一批次存在集成依赖时，必须为消费方任务生成集成预告，避免并行 subagent 间的上下文断裂。

**识别方法**：检查同批次并行任务是否存在"生产者-消费者"关系：
- 任务 A 产出一个接口/服务（如 DistributedLockService）
- 任务 B 的实现逻辑中需要使用该接口

**处理方式**：
1. 不要求串行（因为接口签名在设计阶段已确定）
2. 在消费方任务的 executor prompt 中注入**集成预告**：

```
### 集成预告（同批次任务产出）
以下组件由同批次其他任务实现，你的代码应注入并使用它们：
- {组件名} ({接口路径}): {方法签名} — 用途: {在你的代码中如何使用}
```

3. 消费方 subagent 必须按预告注入并使用声明的组件，不得自行实现替代方案

## 阶段转移条件

1. 外置计划文件已生成
2. 所有任务已通过 TaskCreate 创建
3. 依赖关系已正确设置
4. 每个任务有明确的验证方式

## 提示语

```
>>> PLAN 阶段（计划模式）
正在拆分任务...

<<< PLAN 阶段完成
- 外置计划文件：.claude/work-plans/xxx.md
- 任务总数：N
- 可并行任务：M
准备进入 EXECUTE 阶段。
```

---

# 三、EXECUTE 阶段：并行执行

## 阶段目标

高效并行执行任务，实现代码。

**核心原则**：最多 10 个 subagent 并发，Ralph 模式不完成不停止，失败自动重试。

## 权限

全部允许：读写代码、TaskUpdate、运行测试、Task 派发

## 核心算法：Ultrapilot 并行执行

```python
MAX_CONCURRENT = 10
MAX_RETRY = 3

while True:
    tasks = TaskList()

    executable = [
        t for t in tasks
        if t.blockedBy == [] and t.status == 'pending'
    ]

    if not executable:
        if all(t.status == 'completed' for t in tasks):
            break
        elif any(t.status == 'in_progress' for t in tasks):
            wait_for_running_tasks()
            continue
        else:
            handle_failed_tasks(tasks)
            continue

    batch = executable[:MAX_CONCURRENT]

    # 冲突检测：同一文件被多个任务修改时，仅保留首个任务，其余降级到下一批次
    conflicts = check_file_conflicts(batch)
    if conflicts:
        for group in conflicts:
            # 检查冲突任务间是否有 inputs/outputs 数据依赖关系
            if has_data_dependency(group):  # 任务 B 的 inputs 引用任务 A 的 outputs
                sorted_group = sort_by_dependency(group)  # 按依赖拓扑排序
                # 依赖任务串行执行（不移除，按顺序排入当前批次）
                batch = [sorted_group[0]] + [t for t in batch if t not in group]
                # 后续依赖任务在下一批次中按依赖顺序执行
            else:
                # 无依赖关系：保持现有逻辑（保留首个，其余推迟）
                keep_ids = {group[0].id}
                batch = [t for t in batch if t.id not in {c.id for c in group[1:]}]

    parallel_dispatch(batch)

    for task in batch:
        TaskUpdate(task.id, status='in_progress')

    results = wait_for_results()
    for task, result in zip(batch, results):
        if result.success:
            TaskUpdate(task.id, status='completed')
        else:
            TaskUpdate(task.id, status='pending')
            increment_retry_count(task)
```

### 依赖感知排序（冲突检测增强）

冲突检测发现多任务修改同一文件时，额外检查 inputs/outputs 数据依赖：

1. **有数据依赖**（任务 B 的 `inputs` 引用任务 A 的 `outputs`）：按依赖拓扑排序，串行执行（不移除，按顺序排入批次）
2. **无数据依赖**：保持现有逻辑（保留首个，其余推迟到下一批次）

> `outputs`/`inputs` 字段定义见 `shared-rules/data-contracts.md` planner → code-writer / work-mode 契约

## 并行派发方法

**关键**：在一条消息中发送多个 Task 工具调用

**必须使用自定义 Agent**（默认 subagent 不继承 skills）：

> Agent 角色表见 `SKILL.md` 内部 Agent 角色节

```
Task(
  subagent_type="cc-executor",
  max_turns=10,
  description="执行任务 1",
  prompt="[任务详细描述]"
)
Task(
  subagent_type="cc-executor",
  max_turns=10,
  description="执行任务 2",
  prompt="[任务详细描述]"
)
```

**重要**：每个 executor prompt 中必须注入 `📂 Workspace: {workspace_path}`，确保 subagent 在正确的 workspace 目录下读写 plan.md 等会话文件，避免覆盖其他会话的数据。

> 任务 Prompt 模板见 `prompts.md` 第二节

## Ralph 持久模式

**触发**：用户使用 `ralph` 关键词，或 `/cc-ralph` 命令

**行为**：通过 Stop Hook 进程级硬约束，所有任务完成才停止。

### Stop Hook 拦截机制

Claude 尝试停止时，Stop Hook 自动触发：

1. 检查是否在 Ralph 模式（标志文件存在？）
2. 安全检查（迭代次数 < 20？运行时间 < 60min？）
3. **三条件门控**：
   - 条件 1：`last_assistant_message` 包含 `STARK_COMPLETE`
   - 条件 2：plan.md 中无 ⬜ 和 🔄 标记（plan.md 位于 workspace 目录，Stop Hook 从 `${RALPH_PREFIX}-plan` 标志文件读取正确路径）
   - 条件 3：`git diff` 验证有实际代码变更（含 staged 和近 30 分钟内 commit）
   - 三条件同时满足 → 放行（正常完成）
   - 任一不满足 → Block + 重注入 prompt

### Reinjection Prompt（重注入）

Stop Hook Block 时自动注入：

```
继续工作。你之前的输出不包含 completion promise。

📋 请重新阅读：
1. Spec：{spec_path}（如有）或 {plan_path}（## Spec 章节）
2. 当前进度：{plan_path}（查看 ⬜ 任务）

📌 规则：
- 找到下一个 ⬜ 任务并执行
- 执行时标记 ⬜ → 🔄，完成后 🔄 → ✅
- 所有任务完成后输出 STARK_COMPLETE
- 当前迭代：{N}/{max}，已运行 {X}min
```

每 5 轮（可通过 `STARK_RALPH_COMPACT_INTERVAL` 调整）额外追加 compact 提示。

### Completion Promise

workspace 目录下的 plan.md 中无 ⬜ 和 🔄 标记时，输出：`STARK_COMPLETE`（plan.md 路径由 `${RALPH_PREFIX}-plan` 标志文件记录）

### 安全机制

| 机制 | 默认值 | 环境变量 |
|------|--------|---------|
| 最大迭代 | 20 轮 | `STARK_RALPH_MAX_ITERATIONS` |
| 超时保护 | 180 分钟 | `STARK_RALPH_TIMEOUT_MINUTES` |
| 自动 compact | 每 5 轮 | `STARK_RALPH_COMPACT_INTERVAL` |
| 手动取消 | `/cc-ralph --cancel` | - |
| 项目隔离 | PWD hash 前缀 | - |
| 会话隔离 | PID 存活检查 | - |

### 启动/取消

- 启动：`/cc-ralph`（创建标志文件 + 读取 workspace 下的 plan.md + 开始执行）
- 取消：`/cc-ralph --cancel`（清理标志文件，进度保留在 workspace 下的 plan.md）

## 状态流转

```
pending -> in_progress -> completed
                      -> failed -> (retry) -> pending
                               -> failed_permanent
```

## 阶段转移条件

1. 所有任务状态为 `completed` 或 `failed_permanent`
2. 执行日志已记录
3. 代码已保存

## 提示语

```
>>> EXECUTE 阶段（并行执行模式）
Ralph 模式：已启用（不完成不停止）
最大并发：10 个 subagent

执行进度：3/8 完成

<<< EXECUTE 阶段完成
- 总任务数：8 | 成功：8 | 失败：0 | 总耗时：xxx
准备进入 SUMMARIZE 阶段。
```

---

# 四、SUMMARIZE 阶段：汇总报告

## 阶段目标

生成执行报告，便于追溯和复盘。

## 权限

| 操作 | 允许 |
|------|------|
| 读代码 / 写报告文件 / 运行测试 | YES |
| 写代码 | NO |

## 工作流程

1. **统计任务完成情况**：总数、完成、失败、跳过
2. **汇总代码变更**：`git diff` / `git status` 统计新增/修改/删除文件和行数
3. **分析失败任务**：记录原因、分析根因、提出改进建议
4. **生成执行报告**：写入 `.claude/work-reports/{timestamp}-{name}.md`
5. **强制触发代码审查**：调用 cc-code-reviewer

> 报告输出格式见 `prompts.md`（执行日志模板）

## 强制审查规则

- work-mode 执行完成后**必须**触发 cc-code-reviewer
- 变更行数 > 300 LOC 时，必须深度审查
- 涉及事务/并发代码时，必须专项审查

## 审查失败回路

```
SUMMARIZE.review:
  → 触发 cc-code-reviewer
  → 审查结果 status == "PASS" → 完成
  → 审查结果 status == "BLOCKED" → 进入修复回路

SUMMARIZE.review_failed:
  1. 从 reviewer 的 blocking_issues 提取修复任务列表
  2. 回到 EXECUTE（仅执行修复任务，不重新执行已成功任务）
  3. 修复完成后重新 SUMMARIZE（增量审查修复部分）
  4. 最多 2 轮修复回路，之后请求人工介入

  修复任务状态管理：
  - 为每个阻断问题 TaskCreate 新建修复任务，ID 格式 `{原任务ID}-fix-{N}`
  - 修复任务完成后标记 completed，重新进入 SUMMARIZE 审查

状态流转:
  SUMMARIZE → review(PASS) → 完成
  SUMMARIZE → review(BLOCKED) → EXECUTE(修复) → SUMMARIZE → review
                                                          → 最多重复 2 轮
```

## 提示语

```
>>> SUMMARIZE 阶段
正在生成执行报告...

<<< 干活模式执行完成！
完整报告：.claude/work-reports/xxx.md
计划文件：.claude/work-plans/xxx.md
正在触发强制代码审查...
```

### 分支收尾检查清单

SUMMARIZE 完成后，执行以下检查：
- [ ] 全量测试通过（`mvn test` 或对应命令）
- [ ] PR 描述包含变更摘要和测试计划
- [ ] 无遗留的 WIP commit（squash 或 rebase）
- [ ] 相关 Jira/任务状态已更新

---

# 五、错误处理工作流

## 任务状态机

> **层级区分**：以下状态机描述的是**单个 Task 的状态流转**。Stop Hook（§Ralph 持久模式）在**工作流层面**运作，通过 plan.md 全局状态和 STARK_COMPLETE token 控制整体终止。

```
pending ---------> in_progress
  |                    |-- 成功 -> completed
  |                    |-- 失败 -> failed -> 重试/abandoned
  |                    |-- 超时 -> timeout -> 重试/abandoned
  |-- 依赖失败 ------> blocked
```

## 重试策略

| 重试次数 | 等待时间 | 行为 |
|---------|---------|------|
| 1 | 1 秒 | 立即重试 |
| 2 | 3 秒 | 短暂等待 |
| 3 | 10 秒 | 最后尝试 |
| > 3 | - | 标记为 abandoned |

**可重试**：网络超时、文件锁定、资源不可用、编译错误

**不可重试**：权限不足、文件不存在、语法错误、逻辑错误

## 超时阈值

> 超时权威值定义于 `SKILL.md` 执行超时标准章节，此处不重复列出。

## 人工介入触发条件

| 条件 | 描述 |
|------|------|
| 重试耗尽 | retry_count >= 3 |
| 不可重试错误 | SYNTAX_ERROR, LOGIC_ERROR |
| 批次全部失败 | 一批任务中 > 50% 失败 |
| 总超时 | 总执行时间 > 180 分钟 |

## 人工介入后恢复选项

| 选项 | 行为 |
|------|------|
| 重试 | 重置 retry_count，failed -> pending |
| 跳过 | 标记 abandoned，记录到技术债务 |
| 取消 | 终止 work-mode，保存当前进度，生成部分报告 |

## 错误处理配置参考

```yaml
error_handling:
  retry:
    max_retries: 3
    backoff: [1, 3, 10]
    retryable_errors: ["NETWORK_TIMEOUT", "FILE_LOCKED", "RESOURCE_BUSY", "COMPILATION_ERROR"]
  timeout:
    task_timeout_minutes: 15
    batch_timeout_minutes: 20
    total_timeout_minutes: 60
    allow_extension: true
    extension_minutes: 2
  human_intervention:
    trigger_on_retry_exhausted: true
    trigger_on_batch_failure_rate: 0.5
    trigger_on_total_timeout: true
```

## 错误处理与恢复

> 任务失败时的简单恢复策略

### 失败处理

| 失败范围 | 处理方式 |
|---------|---------|
| 单任务失败 | 重试该任务（最多 3 次），不影响其他任务 |
| 组内多任务失败（≥ 50%） | 暂停当前组，询问用户是否继续 |
| 关键任务失败 | 立即暂停，等待用户决策 |

### 恢复操作

失败任务的文件变更通过 `git checkout -- {affected_files}` 撤销，仅回退失败任务涉及的文件。执行前必须通过 AskUserQuestion 确认。

**禁止**：`git reset --hard`（会丢失所有进度）

## 最佳实践

- **预检查**：执行前确认目标文件存在、无未提交冲突、基础依赖就绪
- **检查点**：每 5 个任务后验证编译状态、变更合理性、无冲突
- **失败阈值**：< 20% 继续 | 20-50% 警告 | > 50% 暂停分析
