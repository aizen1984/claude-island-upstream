# API 分析器工作流

> 四阶段工作流 + 进度追踪

---

# Phase 1: 接口发现工作流（批量扫描）

## 目标

扫描指定范围内的所有 Controller，提取所有 API 入口，生成分析计划。

## Step 1: 确定扫描范围

### 输入模式识别

| 模式 | 用户输入示例 | 处理方式 |
|------|-------------|---------|
| **目录模式** | `分析 /path/to/controller/` | `Glob: "/path/**/*Controller.java"` |
| **列表模式** | `分析 OrderController, UserController` | 逐个 `Glob: "**/{Name}.java"` |
| **单文件模式** | `分析 OrderController` | `Glob: "**/{Name}.java"` |

**输出 Controller 清单**：

```markdown
## Controller 清单

| # | Controller | 文件路径 |
|---|------------|---------|
| 1 | OrderController | /path/to/OrderController.java |

**总计**: {N} 个 Controller
```

## Step 2: 提取 API 注解

搜索 `@RequestMapping`、`@GetMapping`、`@PostMapping`、`@PutMapping`、`@DeleteMapping`、`@PatchMapping`，提取方法名、HTTP 方法、路径、行号。

## Step 3: 生成接口清单

```markdown
## 接口发现报告

**扫描范围**: {目录或文件}
**发现接口数**: {N}

### 接口清单

| # | Controller | 方法 | HTTP | 路径 | 位置 |
|---|------------|------|------|------|------|
| 1 | OrderController | createOrder | POST | /api/orders | :25 |
```

## Step 4: 规划分析批次

- 每批最多 **10** 个接口（并发限制）
- 同一 Controller 的接口优先放同一批

## Step 5: 确认并进入 Phase 2

```
发现 {N} 个接口，将分 {M} 批进行分析。是否开始？[Y/n]
```

**子 Agent 提示词**：使用 `prompts.md` 中 Scanner Agent 部分。
**输出文件**：`.api-analysis/discovery-report.md`

---

# Phase 2: 接口分析工作流

## 目标

并行分析每个接口，追踪调用链，提取表信息，生成独立分析报告。

## 并行执行策略

- 最大并发 agent 数：**10**
- 单接口最大分析深度：**5 层**调用
- 每个接口使用独立子 agent

**Task 调用约束**：所有 Task 调用必须设置 `max_turns`（分析任务：5，复杂实现：10）

## Analyzer Agent 任务

每个 Analyzer 子 agent 负责：

1. **追踪调用链**：Controller → Service → Repository，递归直到 Repository 层或外部调用
2. **识别数据库表**：从 `@TableName`、Mapper XML、SQL 语句提取
3. **记录业务逻辑**：核心职责、关键步骤、事务边界、异常处理
4. **生成分析报告**：使用 `resources.md` 模板，保存到 `.api-analysis/reports/{Controller}_{Method}.md`

**子 Agent 提示词**：使用 `prompts.md` 中 Analyzer Agent 部分。

## 批次执行与状态报告

每批次完成后输出：

```markdown
## 批次 {N} 执行状态

| 接口 | 状态 | 调用深度 | 涉及表 |
|------|------|---------|--------|
| OrderController.createOrder | 成功 | 3 | 4 |
| OrderController.getOrder | 成功 | 2 | 2 |
```

## 异常处理与重试

| 失败类型 | 重试次数 | 降级策略 |
|---------|---------|---------|
| 文件读取失败 | 2 | 标记"文件不可读"，跳过 |
| 调用链断裂 | 1 | 记录断点位置，标记"部分完成" |
| 超时（> 2min） | 1 | 减少追踪深度（3层）后重试 |
| XML 解析失败 | 1 | 跳过 XML，仅从代码提取表 |

**原则**：单个接口失败不阻塞其他接口。批次失败率 > 50% 时暂停并报告用户。

## 进入 Phase 3 条件

- 所有批次执行完成
- 至少 80% 接口分析成功
- 失败率 > 20%：暂停向用户报告

---

# Phase 3: 汇总生成工作流

## 目标

读取所有分析报告，提取表关系，生成 ER 图和 API 汇总文档。

## 核心步骤

### Step 1: 读取分析报告

读取 `.api-analysis/reports/` 下所有报告，提取表名、操作类型、字段信息、接口关联。

### Step 2: 推断表关系

> **详细推断规则见** `prompts.md` Aggregator Agent 部分

### Step 3: 生成 ER 图

> **ER 图格式规范见** `resources.md`

**关键规则**：
- 关系标签使用 FK 列名（禁止 "has"、"contains"）
- FK 字段标注 `FK "→ target.column"`
- 按业务模块分组

**保存到**：`.api-analysis/er-diagram.md`

### Step 4: 生成 API 汇总

按模块分组，包含概览统计、方法列表、表使用热度、失败接口。

**保存到**：`.api-analysis/api-summary.md`

### Step 5: 进入 Phase 4

**必须立即进入 Phase 4 展示报告**，不能只保存文件就结束。

**子 Agent 提示词**：使用 `prompts.md` 中 Aggregator Agent 部分。

---

# Phase 4: 展示报告工作流

## 核心原则

**必须直接向用户展示结果，不能只保存文件！**

## 展示模板

```markdown
## API 分析完成

### 汇总统计

| 指标 | 数值 |
|------|------|
| 分析范围 | {描述} |
| Controller 数量 | {N} |
| 接口数量 | {M} |
| 涉及表数 | {T} |
| 表关系数 | {R} |

---

### ER 图

\`\`\`mermaid
erDiagram
    {完整的 ER 图内容}
\`\`\`

---

### 表使用热度

| 排名 | 表名 | 引用次数 | 主要操作 |
|------|------|---------|---------|
| 1 | {table} | {count} | {ops} |

---

### 文件归档

| 文件 | 路径 |
|------|------|
| ER 图 | `.api-analysis/er-diagram.md` |
| API 汇总 | `.api-analysis/api-summary.md` |
| 详细报告 | `.api-analysis/reports/` ({N} 个文件) |
```

## 常见错误

| 错误 | 正确做法 |
|------|---------|
| 只说"文件已保存" | 必须直接展示 ER 图和汇总 |
| ER 图只有部分表 | 必须包含所有分析到的表 |
| 不展示 Mermaid 代码块 | 必须展示完整 Mermaid 代码 |

---

# 进度追踪

## TaskCreate/TaskUpdate 示例

### Phase 1 开始时

```
TaskCreate(subject="扫描 Controller", activeForm="正在扫描 Controller", description="扫描指定范围内的所有 Controller 文件")
TaskCreate(subject="生成分析计划", activeForm="正在生成分析计划", description="提取 API 注解，生成接口清单和批次计划")
TaskCreate(subject="并行分析接口", activeForm="正在分析接口", description="并行分析每个接口的调用链和表信息")
TaskCreate(subject="汇总生成 ER 图", activeForm="正在生成 ER 图", description="读取分析报告，推断表关系，生成 ER 图")
TaskCreate(subject="展示报告", activeForm="正在展示报告", description="向用户展示完整分析结果")
```

### Phase 切换时

```
TaskUpdate(taskId="1", status="completed")
TaskUpdate(taskId="3", status="in_progress")
```

## 使用原则

1. **Phase 切换时更新**：每进入新阶段时更新状态
2. **批次完成时更新**：Phase 2 每批次完成后更新进度
3. **状态流转**：pending → in_progress → completed
