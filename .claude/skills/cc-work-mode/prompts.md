# cc-work-mode 提示词模板

---

# 一、ANALYZE 阶段提示词

> 阶段工作流详见 `workflows.md` 第一节

## 输入要求

```yaml
# 必须
user_request: string  # 用户的原始请求

# 可选
context_files: string[]  # 相关代码文件路径
existing_docs: string[]  # 现有文档
constraints: string[]  # 已知约束条件
```

## 输出格式：需求理解报告

```markdown
## 需求理解报告

**生成时间**: {timestamp}
**分析阶段**: ANALYZE

---

### 1. 核心目标
[一句话描述用户想要什么]

### 2. 功能需求
- [ ] 功能 1：[描述]
- [ ] 功能 2：[描述]

### 3. 技术约束
| 约束类型 | 具体内容 |
|---------|---------|
| 技术栈 | [Spring Boot / MyBatis / ...] |
| 性能要求 | [QPS / 响应时间 / ...] |
| 安全要求 | [认证 / 授权 / ...] |

### 4. 业务约束
- [业务约束 1]

### 5. 影响范围（如涉及现有代码）
| 文件/模块 | 影响类型 | 影响描述 |
|----------|---------|---------|
| `path/to/file.java` | 修改 | [具体影响] |

### 6. 验收标准
| 类型 | 验收标准 |
|------|---------|
| 功能验收 | [标准描述] |
| 测试验收 | [覆盖率要求] |
| 代码质量 | [规范要求] |

### 7. 待澄清问题
| 问题 | 状态 | 答案 |
|------|------|------|
| [问题 1] | RESOLVED | [用户回答] |

### 8. 风险识别
| 风险 | 影响程度 | 缓解措施 |
|------|---------|---------|
| [风险 1] | HIGH/MEDIUM/LOW | [措施] |

---

**阶段转移检查**:
- [x] 核心目标明确
- [x] 功能需求清晰
- [x] 约束条件识别完成
- [x] 验收标准确定
- [x] 待澄清问题已解决

**结论**: 准备进入 PLAN 阶段
```

## 示例

```
用户请求: 帮我实现用户批量导入功能，支持 Excel 文件上传，需要校验数据并返回导入结果

输出:
- 核心目标：实现用户批量导入功能，支持 Excel 文件上传、数据校验、结果反馈
- 功能需求：Excel 上传接口、数据解析、校验（必填/格式/唯一性）、批量插入、结果返回
- 技术约束：Spring Boot + MyBatis，支持 10000 条/次，支持 .xlsx/.xls
- 风险：大文件 OOM（流式解析+分批）、并发导入冲突（分布式锁）
```

---

# 二、PLAN 阶段提示词

> 阶段工作流详见 `workflows.md` 第二节

## 输入要求

```yaml
# 必须（来自 ANALYZE 阶段产出）
analysis_report: string  # 需求理解报告全文
core_goal: string        # 一句话核心目标
requirements: string[]   # 功能需求列表
constraints: string[]    # 技术+业务约束
acceptance_criteria: string[]  # 验收标准

# 可选
existing_task_list: object[]  # 来自 planner 的预拆解（如有）
```

## 输出格式：外置计划文件

> 文件位置：`.claude/work-plans/{timestamp}-{name}.md`

```markdown
# 工作计划：{任务名称}

> 创建时间：{timestamp}
> 模式：cc-work-mode
> 来源：ANALYZE 阶段产出

---

## 一、需求摘要

**核心目标**: {从 ANALYZE 继承}
**功能需求**: {从 ANALYZE 继承}
**约束条件**: {从 ANALYZE 继承}
**验收标准**: {从 ANALYZE 继承}

---

## 二、任务清单

| # | 任务 | 文件 | 操作 | 预估 | 依赖 | 验证方式 |
|---|------|------|------|------|------|---------|
| T1 | {标题} | {路径} | create/modify | 3min | - | {如何验证} |
| T2 | {标题} | {路径} | modify | 5min | T1 | {如何验证} |

---

## 三、并行分组

### 第 1 批（并行）
- T1, T3, T5（无相互依赖，无文件冲突）

### 第 2 批（等待第 1 批完成）
- T2（依赖 T1）, T4（依赖 T3）

### 第 3 批
- T6（依赖 T2, T4）

---

## 四、风险识别

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| {风险} | HIGH/MEDIUM | {措施} |

---

**计划检查清单**:
- [ ] 每个任务 2-5 分钟粒度
- [ ] 每个任务有明确验证方式
- [ ] 依赖关系正确标注
- [ ] 并行分组无文件冲突
- [ ] 总预估时间合理
```

## 拆分规则

### 粒度标准
- **合适**：单文件的单一职责修改（2-5 分钟）
- **过粗**：跨多文件的复合操作 → 继续拆分
- **过细**：单行修改 → 合并到相关任务

### 并行识别三条件
1. 无数据依赖（输出不依赖其他任务输出）
2. 无文件冲突（不修改同一文件）
3. 无顺序依赖（逻辑上独立）

### 依赖类型标注
- `blockedBy: [T1]` — 必须等 T1 完成
- `sameFile: [T3]` — 修改同文件，需顺序执行
- `（空）` — 可并行

---

## Executor Anti-Pattern 防护

> 通用约束见 `shared-rules/subagent-budget.md` 通用 Anti-Pattern 清单（唯一真实来源）

### 通用强制约束
1. **范围限制**: 不要广泛探索代码库。只读取/处理 prompt 中指定的目标文件。
2. **幻觉防护**: 引用的类名、方法名、路径必须来自 prompt 或 Read 工具确认。禁止编造不存在的类或方法。
3. **失败处理**: 同一操作失败 2 次后换方法或标记失败并停止，禁止无限重试。
4. **输出限制**: 单次文本回复不超过 200 行。超出时优先保留结论，压缩过程。
5. **Write 工具守卫**: 禁止用 Write 工具一次性写入超过 200 行的文件。超过时必须：
   - 优先用 Edit 工具（只传 diff，token 消耗极低）
   - 若是新建大文件：先 Write 骨架（< 100 行），再用 Edit 逐段填充
   - 若无法拆分：标记任务失败，由 Lead 主会话直接完成

### Executor 额外约束
1. **超时意识**: 本任务必须在 15 分钟内完成。如果 10 分钟内无法完成，立即输出当前进度并标记未完成部分。
2. **单文件原则**: 本任务只创建/修改 1 个文件。如需修改多个文件，只处理主文件，其余标记为后续任务。
3. **TDD 联动**: 任务标记含 `test_first: true` 时，遵循 `cc-tdd/SKILL.md` 的 RED-GREEN-REFACTOR 循环（先写失败测试→最小实现→重构）。Executor 启动时检查 `.claude/tdd-session-active` 是否存在，不存在则创建；所有 test_first 任务完成后由 Lead 删除。tdd-guard.js Hook 会通过 additionalContext 提醒未写测试就改源码的行为（非硬阻止，依赖模型自觉）。
4. **大文件策略**: 生成新文件超过 150 行时，采用「骨架+填充」模式：
   Step 1: Write 类定义 + 方法签名 + import（骨架，< 100 行）
   Step 2: 用 Edit 逐个填充方法体
   绝不用 Write 一次性输出完整大文件。

---

# 三、EXECUTE 阶段提示词

> 阶段工作流详见 `workflows.md` 第三节

## 输入要求

```yaml
# 必须
task_list:
  - id: string
    subject: string
    description: string
    target_files: string[]
    blockedBy: string[]
    verification: string
    estimated_loc: number  # 10-50 行

# 可选
ralph_mode: boolean  # 默认 true
max_concurrent: number  # 默认 10
max_retry: number  # 默认 3
```

## 执行日志输出格式

```markdown
## 执行日志

**开始时间**: {start_time}
**执行模式**: Ralph 持久模式
**最大并发**: 10

---

### 第 1 轮并行执行

**时间**: {timestamp}
**派发任务**: T1, T2, T3, T4, T5

| 任务 ID | 任务标题 | 状态 | 耗时 | 备注 |
|--------|---------|------|------|------|
| T1 | [标题] | COMPLETED | 2m30s | - |
| T2 | [标题] | FAILED | - | 原因：xxx |

**本轮结果**: 4/5 成功

---

## 执行汇总

| 指标 | 数值 |
|------|------|
| 总任务数 | 8 |
| 成功数 | 8 |
| 失败数 | 0 |
| 重试次数 | 1 |
| 总耗时 | 12m30s |

**结论**: 所有任务执行完成，准备进入 SUMMARIZE 阶段
```

## 任务 Prompt 模板

### Executor Prompt 模板

> 详见 `.claude/agents/cc-executor.md`，本 Skill 运行时自动加载该 Agent 定义。

**Workspace 注入（强制）**：每个 executor prompt 开头必须包含：

```
📂 Workspace: {workspace_path}
```

此路径决定 plan.md、spec.md 等会话文件的读写位置。**⛔ 未注入 workspace 路径时必须报错停止，禁止 fallback 到项目根目录。**

### 前置产出注入（有依赖时）

当任务有 `inputs` 字段时，在 Executor Prompt 中注入已完成前置任务的产出信息：

```
📥 前置产出:
- {前置任务ID}: {产出描述} → {产出文件路径}（已完成 ✅）
```

此上下文帮助 executor 理解前置任务的产出，避免重复实现或接口不一致。
无 `inputs` 时不注入此部分。

> `outputs`/`inputs` 字段定义见 `shared-rules/data-contracts.md` planner → code-writer / work-mode 契约

### 测试任务（cc-executor 测试模式）

```markdown
# 数禾代码执行者（测试模式）

你是一个专注的测试编写者，负责为指定代码编写单元测试。

## 核心原则

1. **测试优先**：严格遵循 Given-When-Then 模式
2. **覆盖全面**：正常流程、边界条件、异常场景
3. **遵循规范**：继承 BaseMock 基类，使用 Mockito

## 任务信息

**任务 ID**: {task.id}
**被测类**: {task.target_class}

## 详细描述

{task.description}

## 测试要求

- 继承 BaseMock 基类
- 使用 @Mock 和 @InjectMocks
- 覆盖率 > 80%
- 遵循 Given-When-Then 模式

## 输出格式

## 执行结果

**状态**: COMPLETED / FAILED

**新增测试文件**:
- `path/to/XxxServiceTest.java`

**测试覆盖**:
- [x] 正常流程
- [x] 边界条件
- [x] 异常场景

**备注**: (如有)
```

## 状态管理

> 任务状态机及重试策略详见 `workflows.md` 第五节

---

# 四、SUMMARIZE 阶段提示词

> 阶段工作流详见 `workflows.md` 第四节

## 输入要求

```yaml
# 必须（来自 EXECUTE 阶段）
execution_log: string      # 执行日志（各批次结果）
task_results: object[]     # 每个任务的状态和产出
plan_file_path: string     # 外置计划文件路径

# 自动获取
git_diff: string           # git diff --stat 变更摘要
git_status: string         # git status 文件列表
```

## 步骤 1：生成执行报告

> 报告写入：`.claude/work-reports/{timestamp}-{name}.md`

```markdown
# 执行报告：{任务名称}

> 生成时间：{timestamp}
> 计划文件：{plan_file_path}

---

## 执行结果

| 指标 | 数值 |
|------|------|
| 总任务数 | {total} |
| 成功 | {completed} |
| 失败 | {failed} |
| 跳过 | {skipped} |
| 成功率 | {rate}% |
| 总耗时 | {duration} |

## 代码变更

| 类型 | 数量 |
|------|------|
| 新增文件 | {new_files} |
| 修改文件 | {modified_files} |
| 净增行数 | {lines_added} |
| 净删行数 | {lines_deleted} |

## 失败任务分析

（如有失败任务，逐个分析原因和建议）

| 任务 | 原因 | 处理方式 | 状态 |
|------|------|---------|------|
| {task} | {reason} | 重试/跳过 | {final_status} |

## 变更文件清单

{git status 输出}
```

## 步骤 2：触发强制代码审查

```
Task(
  subagent_type="cc-reviewer",
  description="审查 work-mode 变更代码",
  prompt="审查以下变更文件（阻断式模式）：\n{变更文件列表}\n\n变更行数 > 300 LOC 时启用深度审查，涉及事务/并发代码时必须专项审查。"
)
```

## 步骤 3：审查结果处理

```
审查结果 == "PASS":
  → 输出完成报告，work-mode 结束

审查结果 == "BLOCKED":
  → 提取 blocking_issues
  → 为每个 issue 创建修复任务（TaskCreate）
  → 回到 EXECUTE（仅执行修复任务，不重新执行已成功任务）
  → 修复完成后重新 SUMMARIZE（增量审查修复部分）
  → 最多 2 轮修复回路，之后请求人工介入
```

## 提示语

```
>>> SUMMARIZE 阶段
正在生成执行报告...

<<< 执行报告已生成
报告文件：.claude/work-reports/{timestamp}-{name}.md
正在触发强制代码审查...

>>> 审查结果：PASS
<<< 干活模式执行完成！

>>> 审查结果：BLOCKED（N 个阻断性问题）
<<< 进入修复回路（第 M/2 轮）
```
