# 任务跟踪规则

> **加载时机**：任务管理时（CLAUDE.md 强制规则引用）。适用范围：所有 Skills 和 CLAUDE.md

---

## 跟踪级别

| 子任务数 | 级别 | 行为 |
|---------|------|------|
| 1-3 | 轻量 | 文本列出进度即可 |
| 4-7 | 标准 | 必须创建任务跟踪（模式 A 或 B） |
| > 7 | 完整 | 任务跟踪 + 文件持久化（{workspace}/progress.md） |

## 触发条件

当请求涉及以下场景时，**必须**先创建任务跟踪（标准/完整级别）：
- 涉及 4+ 个子任务的任务
- 需要修改多个文件的任务
- 需要多个 Skill 链式协作的任务
- 用户明确要求"计划"、"规划"、"分析"等

**轻量级别**（1-3 个子任务）：直接文本列出子任务和进度。

---

## 两种跟踪模式

### 模式 A：Task 驱动（默认）

**适用 Skill**：cc-work-mode、cc-design、cc-api-analyzer、cc-code-writer、其他所有 Skill

```
Step 1: TaskCreate 创建任务清单
  - 每个子任务一个 Task
  - 包含 subject + description + activeForm
  - 设置任务依赖关系（blockedBy）
  ↓
Step 2: TaskUpdate(in_progress) 标记开始
  - 一次只执行一个任务（work-mode 并行执行除外，最多 10 个）
  ↓
Step 3: 执行任务
  ↓
Step 4: TaskUpdate(completed) 标记完成
  ↓
Step 5: 循环直到所有任务完成（TaskList 检查）
  ↓
Step 6: 汇总报告
```

#### TaskCreate 调用规范

```javascript
TaskCreate({
  subject: "任务标题（祈使句）",      // 如：实现用户登录接口
  description: "详细描述 + 文件路径 + 验证方式",
  activeForm: "正在执行 xxx"          // 如：正在实现登录接口
})
```

#### 行为规范

```
✅ 复杂任务必须先 TaskCreate
✅ 执行前必须 TaskUpdate(in_progress)
✅ 完成后必须 TaskUpdate(completed)
✅ 所有任务完成后必须汇总
❌ 复杂任务不创建 Task 就开始执行
❌ 多个任务同时标记 in_progress（并行分析除外）
```

---

### 模式切换：委托场景

planner（模式 B）委托任务给 work-mode/code-writer（模式 A）时的状态归属：

```
planner {workspace}/plan.md: 委托任务行 ⬜ → 🔄
  └→ 更新 session.yaml delegation（active=true）
  └→ 被委托 Skill 内部用 TaskCreate/TaskUpdate（模式 A）
  └→ 被委托 Skill 完成，Agent 工具返回结果
planner {workspace}/plan.md: 🔄 → ✅（成功）或 ❌（失败）
  └→ 更新 session.yaml delegation（active=false）
```

**规则**：
- planner 的 {workspace}/plan.md 一个 emoji 行 = 被委托方的整个执行周期（可能对应多个 Task）
- 被委托方的成功/失败由 Agent 返回值决定，planner 据此更新 {workspace}/plan.md
- 被委托方内部的 Task 状态对 planner 不可见，planner 只关心最终结果

---

### 模式 B：文件驱动（planner 专用）

**适用 Skill**：cc-planner

{workspace}/plan.md 是任务状态的**唯一数据源**（workspace 路径见 session-workspace.md）。Agent 工具仅在需要并行 agent 派发时使用。

```
Step 1: 写 {workspace}/plan.md（含任务表，每行一个任务，状态 ⬜）
  ↓
Step 2: Read {workspace}/spec.md 目标 + {workspace}/plan.md 首个 ⬜ 任务（无 {workspace}/spec.md 则读 {workspace}/plan.md Spec 段）
  ↓
Step 3: Edit {workspace}/plan.md: ⬜ → 🔄（标记开始）
  ↓
Step 4: 执行任务
  ↓
Step 5: Edit {workspace}/plan.md: 🔄 → ✅（成功）或 ❌（失败，附原因）
  ↓
Step 6: 每完成 3 个任务 → 追加 {workspace}/progress.md
  ↓
Step 7: 循环直到所有任务 ✅ 或有明确 ❌ 说明
  ↓
Step 8: 汇总报告
```

#### Agent 工具使用场景（仅限）

| 场景 | 用法 |
|------|------|
| 分析型并行（>= 2 个独立任务） | Agent 工具派发多个并行 agent |
| 对抗验证 | Agent 工具派发独立验证 agent |
| 其他所有场景 | **不使用 Task/Agent 并行工具** |

#### 行为规范

```
✅ 复杂任务必须先写 {workspace}/plan.md（含任务表）
✅ 每个任务完成后立即更新 {workspace}/plan.md 状态
✅ 每 3 个任务追加 {workspace}/progress.md
✅ 所有任务完成后必须汇总
❌ 不写 {workspace}/plan.md 就开始执行
❌ 执行过程中不更新 {workspace}/plan.md 状态
❌ 非并行场景使用 Task 工具
```

---

## 任务粒度标准

> 本表定义**单个 Task 的实现规模**指标。项目复杂度分级见 `skill-quality.md`，Subagent 上下文层面的粒度约束见 `subagent-budget.md`。

| 指标 | 最小值 | 标准值 | 最大值 |
|------|--------|--------|--------|
| 代码行数 | 10 行 | 30 行 | 50 行 |
| 文件数 | 1 个 | 1 个 | 2 个 |
| 方法数 | 1 个 | 2 个 | 3 个 |
