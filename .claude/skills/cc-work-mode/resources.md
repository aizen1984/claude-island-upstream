# cc-work-mode 资源与模板

---

# 一、错误处理示例

> 错误处理策略和配置详见 `workflows.md` 第五节

## 单任务失败处理

```
任务执行结果：
- Task 1: 成功
- Task 2: 成功
- Task 3: 失败（编译错误）
- Task 4: 成功
- Task 5: 成功

处理：
1. 检测到缺少 import
2. 自动添加 `import lombok.extern.slf4j.Slf4j;`
3. 重新编译 -> 成功
```

## 批量失败处理（> 50% 失败）

```markdown
## 批量失败警告

失败率过高（60%），暂停执行

### 失败原因分析
- 3 个任务失败原因相同：缺少基础依赖

### 建议操作
1. 先解决共性问题（添加基础依赖）
2. 回滚已失败任务的变更
3. 重新执行全部任务

是否继续？[Y/N]
```

## 冲突处理

```markdown
## 冲突检测

发现文件冲突：
- CommonUtils.java 被 Task 2、Task 3 同时修改

### 解决方案
将 Task 2、Task 3 改为顺序执行：
1. 先执行 Task 2
2. Task 2 完成后执行 Task 3

### 调整后执行计划
- 并行：Task 1, 4, 5
- 顺序：Task 2 -> Task 3
```

## 回滚机制

> **注意**：以下 git 操作已通过 work-mode 激活隐式授权（详见 workflows.md 第五节）。执行前必须通过 AskUserQuestion 向用户确认。

```bash
# 任务级回滚（仅回退指定文件）
git checkout -- {affected_files}

# 批量回滚（整个 work-mode）
BEFORE_COMMIT=$(git rev-parse HEAD)
# ... 执行 work-mode ...
git stash push -m "work-mode rollback"  # 如需回滚，暂存当前变更
```

## 错误报告格式

```markdown
## work-mode 执行报告

### 执行概况
- 总任务数：10 | 成功：8 | 失败：2 | 成功率：80%

### 失败任务详情

#### Task 3: OrderService 添加日志
- 错误类型：编译错误
- 错误信息：`Cannot resolve symbol 'Logger'`
- 建议操作：手动添加 `@Slf4j` 注解

#### Task 7: PaymentService 添加日志
- 错误类型：超时
- 自动修复：重试成功

### 建议
1. 手动修复 Task 3
2. 执行 code-reviewer 审查成功任务
```

---

# 二、内部 Agent 调用代码示例

> Agent 角色表见 `SKILL.md` 内部 Agent 角色节

## cc-executor（EXECUTE 阶段主力）

```python
Task(
    subagent_type="cc-executor",
    prompt="""
    实现任务：创建 UserService.createUser 方法

    目标文件：src/main/java/.../UserService.java

    需求：
    1. 参数校验
    2. 保存用户
    3. 返回用户 ID

    遵循规范：cc-java-backend
    """,
    description="实现 UserService.createUser"
)
```

## cc-researcher（ANALYZE 阶段）

```python
Task(
    subagent_type="cc-researcher",
    prompt="""
    快速分析以下代码结构：
    - 目标目录：src/main/java/.../user/
    - 分析内容：现有接口、方法签名、依赖关系
    - 输出格式：结构化报告
    """,
    description="分析 user 模块代码结构"
)
```

## cc-reviewer（SUMMARIZE 阶段）

```python
Task(
    subagent_type="cc-reviewer",
    prompt="""
    审查变更代码：
    - 变更文件：[file_list]
    - 审查模式：阻断式（work-mode 强制）
    - 重点检查：事务、并发、安全

    输出格式：review_result YAML
    """,
    description="审查 work-mode 变更代码"
)
```

## preload_skills 实现机制

> preload_skills 通过 `.claude/agents/*.md` 文件的 frontmatter `skills` 字段实现。

### 配置位置

每个内部 Agent 对应一个 `.claude/agents/{agent-name}.md` 文件：

| Agent 文件 | skills 配置 | 工具权限 |
|-----------|------------|---------|
| `cc-executor.md` | `skills: [cc-java-backend]` | Read, Edit, Write, Bash, Grep, Glob |
| `cc-researcher.md` | （无预加载） | Read, Grep, Glob, Bash |
| `cc-reviewer.md` | `skills: [cc-code-reviewer]` | Read, Grep, Glob, Bash |

### 工作原理

1. work-mode 通过 `Task(subagent_type="cc-executor", ...)` 派发任务
2. Claude Code 自动加载 `.claude/agents/cc-executor.md`
3. Agent 文件中的 `skills` 字段指定预加载的 Skill
4. Subagent 启动时自动注入对应 Skill 的上下文

### 注意事项

- 省略 `model` 字段即自动继承父会话的模型设置
- `tools` 字段控制工具白名单（最小权限原则）
- 这些 Agent 不能通过 `Skill("cc-executor")` 调用，只能作为 work-mode 内部角色使用

---

# 三、并行派发示例

## 完整示例：为 5 个 Service 类添加日志

```
用户请求："帮我给 UserService、OrderService、ProductService、PaymentService、NotificationService 添加方法入参出参日志"
```

### EXECUTE 阶段派发

```
// 创建任务跟踪
TaskCreate(subject="UserService 添加日志", ...)
TaskCreate(subject="OrderService 添加日志", ...)
TaskCreate(subject="ProductService 添加日志", ...)
TaskCreate(subject="PaymentService 添加日志", ...)
TaskCreate(subject="NotificationService 添加日志", ...)

// 并行派发（单条消息包含 5 个 Task 工具调用）
Task(subagent_type="cc-executor", prompt="修改 UserService...", run_in_background=true)
Task(subagent_type="cc-executor", prompt="修改 OrderService...", run_in_background=true)
Task(subagent_type="cc-executor", prompt="修改 ProductService...", run_in_background=true)
Task(subagent_type="cc-executor", prompt="修改 PaymentService...", run_in_background=true)
Task(subagent_type="cc-executor", prompt="修改 NotificationService...", run_in_background=true)
```

### subagent Prompt 模板

```markdown
## 任务
为 {ServiceName} 添加方法入参出参日志

## 文件
{file_path}

## 要求
1. 在每个 public 方法入口添加 log.info("method={}, params={}", ...)
2. 在每个 public 方法出口添加 log.info("method={}, result={}", ...)
3. 敏感字段（password, token）需脱敏

## 规范
遵循 cc-java-backend 日志规范

## 完成标准
- 代码可编译
- 日志格式统一
- 无敏感信息泄露
```

## 任务依赖处理

```
执行顺序（有依赖时）：
1. 先执行无依赖任务（如：创建基础工具类）
2. 完成后并行执行依赖该任务的后续任务
```

## 分批执行（任务 > 10）

### 完整流程

```
# 假设 15 个任务，按并行分组派发

# ===== 第 1 批：T1-T5（无依赖，可并行）=====

# 1. 标记任务开始
TaskUpdate(taskId="1", status="in_progress")
TaskUpdate(taskId="2", status="in_progress")
...TaskUpdate(taskId="5", status="in_progress")

# 2. 并行派发（单条消息包含多个 Task 调用）
Task(subagent_type="cc-executor", description="T1: ...", prompt="...", run_in_background=true)
Task(subagent_type="cc-executor", description="T2: ...", prompt="...", run_in_background=true)
...（最多 10 个并行）

# 3. 等待所有 subagent 完成（系统自动通知）

# 4. 逐个检查结果，更新任务状态
TaskUpdate(taskId="1", status="completed")  # 成功
TaskUpdate(taskId="3", status="pending")     # 失败 → 重置为 pending 等待重试

# ===== 第 2 批：T6-T10（依赖第 1 批）=====
# 检查 blockedBy 是否已满足
TaskList()  # 查看哪些任务已 unblock
# 重复上述派发流程

# ===== 第 3 批：T11-T15 =====
# 同上
```

### 结果汇聚

```
每批次完成后：
1. 收集所有 subagent 返回的执行结果
2. 更新 TaskUpdate（completed / 重置 pending）
3. 更新外置计划文件的执行日志
4. 检查是否有失败任务需要重试（retry_count < 3）
5. 检查下一批的 blockedBy 是否已满足
6. 派发下一批

所有批次完成后：
→ 进入 SUMMARIZE 阶段
```

### 失败率分层处理

```
失败率 < 20%:
  → 自动重试（retry_count < 3 时重置为 pending）
  → 继续执行下一批

失败率 20-50%:
  → 输出警告，分析共性原因
  → 自动重试后继续

失败率 > 50%:
  → 暂停，输出分析报告
  → 询问用户：继续 / 跳过失败任务 / 中止
```

---

# 四、工作计划模板

> 完整计划模板见 `cc-planner/templates.md`（plan-template）。以下为 work-mode 简化版。

```markdown
# 工作计划：{任务名称}

> 创建时间：{timestamp}
> 状态：{status}
> 模式：cc-work-mode

---

## 一、需求摘要

### 核心目标
{一句话描述}

### 功能需求
- [ ] 功能 1
- [ ] 功能 2

### 约束条件
- 技术约束：{约束}
- 业务约束：{约束}

### 验收标准
- [ ] 功能验收
- [ ] 测试验收
- [ ] 代码质量

---

## 二、任务清单

| # | 任务 | 文件 | 操作 | 预估 | 依赖 | 状态 |
|---|------|------|------|------|------|------|
| 1 | {任务 1} | {文件路径} | create | 3min | - | pending |
| 2 | {任务 2} | {文件路径} | modify | 5min | 1 | pending |

---

## 三、执行日志

### 第 N 轮并行执行
- 时间：{timestamp}
- 派发任务：{task_ids}
- 结果：
  - 任务 X：{status}（{notes}）

---

## 四、汇总报告

### 执行结果
| 指标 | 数值 |
|------|------|
| 总任务数 | {total} |
| 完成 | {completed} |
| 失败 | {failed} |
| 成功率 | {rate}% |

### 代码变更
- 新增：{new_files} 文件
- 修改：{modified_files} 文件
- 净增：{lines_added} 行

### 失败任务分析
（如有）

---

## 五、后续行动

- [ ] {action_1}
- [ ] {action_2}
```

---

# 五、Ralph 标志文件管理

> Ralph 持久模式通过标志文件控制 Stop Hook 行为。标志文件带项目隔离前缀，支持多项目并行。

## 标志文件说明

| 文件 | 内容 | 用途 |
|------|------|------|
| `${RALPH_PREFIX}-active` | `active` | Ralph 模式激活标志 |
| `${RALPH_PREFIX}-promise` | `STARK_COMPLETE` | Completion Promise |
| `${RALPH_PREFIX}-iterations` | 迭代计数（0 起） | Stop Hook 递增，超限放行 |
| `${RALPH_PREFIX}-starttime` | Unix 时间戳 | 超时计算用 |
| `${RALPH_PREFIX}-plan` | plan 文件绝对路径 | Stop Hook 定位 workspace 下的 plan.md（支持多会话隔离） |

其中 `RALPH_PREFIX=/tmp/stark-ralph-${PROJECT_HASH}-${UUID}`，`PROJECT_HASH` 由项目路径 md5 前 8 位生成，`UUID` 由 ralph-loop 启动时生成，实现会话级隔离。

> 详细启动/清理流程见 `.claude/commands/cc-ralph.md` 和 `.claude/commands/cc-ralph --cancel.md`，此处不重复模板代码。

## 环境变量配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `STARK_SESSION_DIR` | 无（必须由 session-start.sh 设置） | 会话 session 目录，五文件的存放位置，禁止 fallback |
| `STARK_RALPH_MAX_ITERATIONS` | 20 | 最大迭代轮数 |
| `STARK_RALPH_TIMEOUT_MINUTES` | 180 | 超时分钟数 |
| `STARK_RALPH_COMPACT_INTERVAL` | 5 | compact 提示间隔轮数 |

可在项目 `.claude/settings.json` 的 `env` 中设置，或在 shell profile 中 export。
