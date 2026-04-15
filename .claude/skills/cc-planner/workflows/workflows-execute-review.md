## execute

# Phase 3: 执行工作流（Execute）

> 并行模式选择参考 `cc-work-mode/agent-teams-rules.md` §15.7：Subagent 与 Agent Teams 不可混用

> **目标**：严格按计划执行，及时验证，记录偏差 | **权限**：全权限 + 微询问

| 操作 | 允许 |
|------|------|
| 读取/修改/创建代码、运行测试、写五文件持久化（文件位于 workspace，`$STARK_SESSION_DIR`） | Y |

---

## 前置检查

进入 EXECUTE 前必须确认：

| 任务复杂度 | 前置条件 | 检查方式 |
|-----------|---------|---------|
| 小型（<= 2 文件，单模块） | 用户已确认 PLAN | `{workspace}/plan.md` 已确认 |
| 中型/大型（标准路径） | DESIGN-REVIEW 已通过 | `{workspace}/session.yaml` 中 `design_review_status = "approved"` |
| 中型/大型（设计文档驱动路径） | RESEARCH 对抗验证通过 + 改动设计文档已写入 vault + **PLAN 阶段 plan↔设计自检通过** | `{workspace}/session.yaml` 中 `research_path = "design-doc-driven"` 且 `design_review_status = "skipped"` 且 `{workspace}/plan.md` 头部含 `design_alignment_checked: true` |

**中型/大型任务未通过设计评审（标准路径）或对抗验证（设计文档驱动路径）时，禁止进入 EXECUTE。**

### 上下文管理说明

RESEARCH+PLAN 阶段的中间推理（代码阅读、方案比较）对 EXECUTE 无用，但**无需手动清理**：
- **策略 2-4**（subagent 执行）：每个 subagent 天然拥有 fresh context，不继承主 agent 的 R+I+P 上下文
- **策略 1**（主 agent 直接执行）：仅用于小型任务（1-2 文件），上下文消耗有限
- **auto-compaction**：当主 agent 上下文接近限制时自动触发，`post-compact-inject.js` 从 plan.md 恢复进度

用户仍可在任意时刻手动执行 `/compact` 或 `/cc-handoff`，但在无人模式（Ralph）下不需要人工干预。

---

## 任务执行策略

```
任务类型判断
├── 分析/研究型（产出为文档/报告）
│     ├── >= 2 个独立任务 → 策略 0: planner 自身并行（最多 10 并发 + 实时勾选）
│     └── < 2 个 → 策略 1: 主 agent 顺序执行
└── 代码开发型（产出为源代码）
      ├── 用户要求 ralph 或 任务>=3 且预估>15min → 策略 4: Ralph 持久模式（自动集成 REVIEW）
      ├── >= 5 且独立（未选策略 4）→ 策略 3: 委托 work-mode
      ├── < 5 或有依赖 → 策略 2: 委托 code-writer
      └── 简单（1-2 文件）→ 策略 1: 主 agent 直接实现
```

| 特征 | 分析型（策略 0） | 开发型（策略 2/3） | Ralph 持久（策略 4） |
|------|---------------------|-----------------|---------------------|
| 产出 | 文档/报告/清单 | 源代码/配置文件 | 源代码 + REVIEW 报告 |
| 操作 | 只读 + 写文档 | 创建/修改文件 | 创建/修改 + 自动验证 |
| 失败影响 | 信息缺失可补 | 代码冲突需回滚 | 自动修复循环 |
| **委托日志（⛔ 强制）** | 无（自身派发）| `🔗 cc-planner.EXECUTE → cc-code-writer/cc-work-mode \| 原因: [策略2/3]` | `🔗 cc-planner.EXECUTE → /cc-ralph \| 原因: 策略4 (任务≥3 且 预估>15min)` |

---

## 任务执行循环

### 选择任务

```yaml
选择规则:
  1. 选择无依赖或依赖已完成的任务
  2. 如有多个可选，按计划顺序
  3. 一次只执行一个任务
```

### 执行循环：Read → Do → Write

1. Read `{workspace}/spec.md` 目标段 + `{workspace}/plan.md` 当前任务段（注意力刷新；若无 `{workspace}/spec.md` 则读 `{workspace}/plan.md` Spec 段）。**如本次为主 agent 接管 subagent 执行结果（策略 2/3/4 退出后），同时扫描 `{workspace}/progress.md` 末尾是否有 `[DEV-*-SYNC-NEEDED]` 标记，命中则按"plan.md 下游字段同步规则"补做同步后再开始新任务**
2. 找到首个 ⬜ 任务，Edit `{workspace}/plan.md`: ⬜ → 🔄
3. 实现代码
4. **Smoke Check**（只检查"是否明显坏了"，不检查"是否足够好"）：
   - 编译/构建通过（`mvn compile` / `npm run build` / 对应语言命令）
   - 关键 import/依赖存在（新增的类、方法、配置项能被引用方找到）
   - 函数有实现体（非空壳；禁止 TODO/FIXME 作为方法体唯一内容——方法内注释性 TODO 允许保留）
   - 不通过 → 当场修复后重新 smoke check（**最多 2 次**；仍不通过 → 进入 3-Strike 协议，当前任务 Strike +1）
   - 通过 → 进入 Step 5
   - **执行主体**：策略 1 由主 agent 执行；策略 2/3 由 code-writer subagent 内部执行（其已有"验证优先"约束）；策略 4 由 ralph 执行循环负责
   - **与 REVIEW 的边界**：smoke check 验证单任务级别的"能不能跑"；REVIEW Step 1-2 验证全量交付级别的"对不对"和"好不好"。smoke check 通过不代表可跳过 REVIEW
5. Edit `{workspace}/plan.md`: 🔄 → ✅（成功）或 ❌（失败，附原因）
6. 每完成 3 个任务后追加 `{workspace}/progress.md`
7. 阶段切换 / 任务阻塞 / 会话结束 / REPLAN 时更新 `{workspace}/session.yaml`
8. 所有任务完成后汇总报告

**注意力刷新**：Step 1 的 Read `{workspace}/spec.md` + `{workspace}/plan.md` 是无条件的，每个任务都执行。
这是文件驱动的核心优势 —— 执行循环自带注意力管理，无需额外规则。

**并行分析模式下**：每轮批次完成后统一更新 `{workspace}/progress.md` 和 `{workspace}/plan.md` 中的 emoji 状态。

---

## 策略 4: Ralph 持久模式（Planner 全周期集成）

> 通过 handoff 信号文件协议将 planner EXECUTE 和 ralph-loop 打通，实现 EXECUTE → REVIEW → 修复 的闭环。

### 触发条件（任一即可）

- 用户确认 PLAN 时明确要求 ralph / 持久执行 / "不完成不停止"
- 代码开发型任务 >= 3 且预估总耗时 > 15 分钟

### 启动步骤

1. 确保 `{workspace}/plan.md` 已写入且含 Spec 章节
2. 推荐：在 plan.md 头部添加 `**final_verify**: \`编译/测试命令\``（ralph 完成时自动执行）
3. **⛔ 输出委托日志**（强制，启动 ralph 之前）：
   ```
   🔗 cc-planner.EXECUTE → /cc-ralph | 原因: 策略4 (任务≥3 且 预估>15min)
     ↳ LIFECYCLE_MODE=planner-execute
     ↳ Handoff 等待: ${STARK_SESSION_DIR}/.ralph-handoff
   ```
4. 执行以下 bash 设置 lifecycle 模式并启动 ralph：
   ```bash
   export LIFECYCLE_MODE="planner-execute"
   ```
5. 执行 `/cc-ralph`（ralph 自动从 workspace 复制五文件，启动循环）
6. ralph Stop Hook 管理执行循环，直到所有 ⬜ 任务完成

### ralph 完成后：Handoff 检测

ralph 退出后，**立即检查** handoff 信号文件：

```bash
cat "${STARK_SESSION_DIR}/.ralph-handoff" 2>/dev/null
```

| 信号内容 | 含义 | 下一步 |
|---------|------|--------|
| `ralph-complete` | 所有任务 ✅ + 验证通过 | 进入 REVIEW 阶段 |
| `ralph-failed:stall:N` | 连续 N 轮无进展 | 进入修复流程 |
| `ralph-failed:error:N` | 同一错误重复 N 次 | 进入修复流程 |
| `ralph-failed:timeout:Nmin` | 超时退出 | 进入修复流程 |
| `ralph-failed:iterations:N` | 迭代次数达上限 | 进入修复流程 |
| 文件不存在 | ralph 被手动取消或异常 | 询问用户下一步 |

检测完毕后删除信号文件：`rm -f "${STARK_SESSION_DIR}/.ralph-handoff"`

### 修复流程（ralph-failed 时）

1. 读取 `{workspace}/plan.md` 中 ❌ 和剩余 ⬜ 任务
2. 分析失败原因（结合 handoff 信号和 plan.md 状态）
3. 由 planner（不是 ralph）创建修复任务追加到 plan.md 末尾（⬜ 状态）
4. 修复任务 <= 2 → 主 agent 直接修复（策略 1）
5. 修复任务 > 2 → 重新设置 `LIFECYCLE_MODE=planner-execute`，重新 `/cc-ralph`
6. **最多 2 轮修复循环**（第 3 次失败 → 报告问题，交还用户）

### REVIEW 自动触发

ralph-complete 后自动进入本文件的 REVIEW 阶段（见下方）。REVIEW 不通过时：

1. 基于 REVIEW 发现创建修复任务（⬜），追加到 plan.md
2. 修复任务 <= 2 → 主 agent 直接修复
3. 修复任务 > 2 → 重新 ralph 持久模式
4. 修复后重新 REVIEW
5. **最多 2 轮 REVIEW-fix 循环**（第 3 次不通过 → 交还用户）

### 与其他策略的关系

- 策略 4 内部的任务执行仍遵循 Read → Do → Write 循环、3-Strike 错误协议、偏差处理规则
- ralph 内部禁止修改 plan.md 结构，只能更新 ⬜→🔄→✅ 标记
- 修复任务的创建权仅在 planner 手中（ralph 退出后）

---

## 3-Strike 错误协议（任务级）

> 单个任务内的错误处理策略，在触发 REPLAN 之前使用

| 尝试 | 策略 | 动作 |
|------|------|------|
| 第 1 次 | 诊断修复 | 读错误信息，分析根因，针对性修复 |
| 第 2 次 | 换方法 | 同样错误？换工具/换库/换实现路径 |
| 第 3 次 | 重新思考 | 质疑假设，搜索方案，考虑是否任务拆分有误 |
| 3 次后 | 上报 | 标记任务阻塞 → 触发 REPLAN-004 |

**核心规则**：`if action_failed: next_action != same_action`

与偏差处理的关系：3-Strike 处理**实现错误**（编译失败、测试不通过）；偏差处理处理**计划偏离**（新增方法、改接口签名）。

---

## Planner Orchestrator 并行调度

### 触发条件（全部满足）

1. 任务类型为**分析/研究型**
2. 任务数量 >= 2
3. 任务间互相独立（无 blockedBy 依赖）
4. 用户未明确要求委托给其他 Skill

### 核心调度算法

```python
MAX_CONCURRENT = 10

while True:
    Read {workspace}/plan.md  # 解析任务状态
    executable = [t for t in tasks if t.blocked_by == [] and t.status == '⬜']

    if not executable:
        if all_completed: break
        elif any_in_progress: wait; continue
        else: break

    batch = executable[:MAX_CONCURRENT]

    # 批量标记进行中
    Edit {workspace}/plan.md: 对应行 ⬜ → 🔄

    # 并行派发（Agent 工具仅此处使用）
    Agent(subagent_type="general-purpose", prompt="...", run_in_background=true)
    ...

    # 收集结果
    for task, result in collect_results(batch):
        Edit {workspace}/plan.md: 🔄 → ✅（成功）或 ❌（失败）

    append_progress(round, batch, results)  # 追加 {workspace}/progress.md
```

### subagent prompt 模板

```markdown
你是一个分析专家。请分析以下目标并输出结构化结果。

## 分析目标
{task_description}

## 输出格式
{output_format}

## 约束
- 只读操作 + 写文档，不修改源代码
- 只分析本 prompt 中指定的目标，不要扩展分析范围
- 输出必须包含结构化摘要
- 遇到问题标记为 ❌ 并说明原因，不要重试
- 幻觉防护：引用的类名、方法名、路径必须来自本 prompt 或 Read 工具确认，禁止编造
- 生成内容不超过 200 行
- Write 工具守卫：禁止一次性写入超过 200 行文件，超过时先写骨架再 Edit 填充
```

### `{workspace}/plan.md` 实时状态同步

| 触发点 | plan.md 动作 | emoji 变化 |
|--------|-------------|-----------|
| 批次开始前 | 批量更新状态列 | ⬜ → 🔄 |
| 单任务完成时 | 更新该行 + 填写结果 | 🔄 → ✅ |
| 单任务失败时 | 更新该行 + 填写原因 | 🔄 → ❌ |

### 暂停与恢复

- 用户请求暂停 → 等待当前批次完成 → 保存检查点到 `{workspace}/plan.md`
- 会话中断 → 下次恢复时将 🔄 重置为 ⬜，从第一个 ⬜ 继续

### 与现有机制的交互

| 机制 | 并行分析模式下的行为 |
|------|---------------------|
| REPLAN-001（连续 2 失败） | 不触发（标记 ❌ 跳过，不构成"连续失败"） |
| REPLAN-002/003/004 | 正常触发 |
| 微询问 | 不适用（subagent 遇到问题直接标记 ❌） |
| `{workspace}/progress.md` | 每轮批次完成后追加执行日志 |

---

## 自动重规划机制

### 重规划触发器

```yaml
replan_triggers:
  - id: "REPLAN-001"
    condition: "连续 2 个任务验证失败"
    severity: "HIGH"

  - id: "REPLAN-002"
    condition: "执行 Task N 时发现依赖未完成的 Task M"
    severity: "MEDIUM"
    auto_fix: true

  - id: "REPLAN-003"
    condition: "单个任务执行时间超过预估 200%"
    severity: "MEDIUM"

  - id: "REPLAN-004"
    condition: "遇到无法解决的技术障碍"
    severity: "HIGH"

  - id: "REPLAN-005"
    condition: "用户在 EXECUTE 阶段提出需求变更"
    severity: "HIGH"
    action: "暂停当前任务 → 评估变更影响范围 → 微调/局部重规划/完全重规划"
```

### 重规划决策

```
触发条件满足？
├─ NO  → 继续执行
└─ YES → 进入重规划评估
    ├─ A. 微调：调整单个任务，继续执行
    ├─ B. 局部重规划：重规划受影响任务
    └─ C. 完全重规划：回到 PLAN 阶段
```

---

## 执行期微询问

### 微询问 vs 完整 INQUIRE

| 维度 | 微询问 | 完整 INQUIRE |
|------|--------|--------------|
| 触发时机 | EXECUTE 阶段中 | RESEARCH 后 |
| 范围 | 仅当前 Task | 整个功能 |
| 目的 | 澄清实现细节 | 澄清需求和方案 |
| 影响 | 不改变整体计划 | 可能改变整体方案 |
| 中断程度 | 最小化 | 阶段性停止 |

### 微询问格式

```markdown
## 微询问 (Task N)

**上下文**: 正在实现 [任务描述]
**问题**: [具体问题]

**选项**:
- A. [选项 A 描述]
- B. [选项 B 描述]

**我的建议**: [如果有]
```

### 限制
- 单任务最多询问 2 次
- 不适用于需要改变整体方案的情况
- 超过限制会暂停任务，评估计划充分性

---

## 偏差处理（五条规则）

> 借鉴自 create-plans 的偏差规则，明确哪些自动处理，哪些需询问

### 偏差规则表

| 规则 ID | 偏差类型 | 处理方式 | 示例 |
|--------|---------|---------|------|
| **DEV-001** | 自动修复 Bug | **自动处理** + 记录 `progress.md` + **同步 plan.md 下游字段**（见下） | 发现损坏的行为 → 立即修复 |
| **DEV-002** | 添加缺失关键项 | **自动处理** + 记录 `progress.md` + **同步 plan.md 下游字段**（见下） | 安全/正确性缺口 → 立即添加 |
| **DEV-003** | 修复阻塞问题 | **自动处理** + 记录 `progress.md` + **同步 plan.md 下游字段**（见下） | 无法继续执行 → 立即修复 |
| **DEV-004** | 架构级变更 | **停止并询问用户** | 重大结构变更 → 等待确认 |
| **DEV-005** | 增强建议 | **记录但不实现** | 锦上添花项 → 创建 TODO，继续执行 |

### 偏差规则详解

#### DEV-001: 自动修复 Bug
- **条件**：执行任务时发现现有代码的损坏行为
- **动作**：立即修复，不中断流程
- **记录**：在 `{workspace}/progress.md` 记录"[DEV-001] 修复了 X 的 Bug"
- **示例**：空指针异常、逻辑错误、边界条件未处理

#### DEV-002: 添加缺失关键项
- **条件**：发现安全/正确性缺口
- **动作**：立即添加，不中断流程
- **记录**：在 `{workspace}/progress.md` 记录"[DEV-002] 添加了 X 以确保正确性"
- **示例**：参数校验、权限检查、事务边界

#### DEV-003: 修复阻塞问题
- **条件**：无法继续执行当前任务
- **动作**：立即修复阻塞，继续执行
- **记录**：在 `{workspace}/progress.md` 记录"[DEV-003] 修复阻塞：X"
- **示例**：缺失依赖、编译错误、配置缺失

#### DEV-004: 架构级变更（需询问）
- **条件**：需要重大结构变更
- **动作**：**停止执行**，使用微询问机制询问用户
- **记录**：在 `{workspace}/progress.md` 记录"[DEV-004] 等待用户确认：X"
- **示例**：修改公共接口签名、新增模块、改变数据模型
- **询问格式**：
  ```markdown
  ## 架构变更确认 (Task N)

  **发现问题**: [问题描述]
  **建议变更**: [变更内容]
  **影响范围**: [受影响的文件/模块]

  **选项**:
  - A. 同意变更，继续执行
  - B. 拒绝变更，寻找替代方案
  - C. 暂停任务，回到 PLAN 重新规划
  ```

#### DEV-005: 增强建议（记录但不实现）
- **条件**：发现可以优化但非必需的改进点
- **动作**：记录到 `{workspace}/findings.md` 的"增强建议"章节，**不实现**
- **记录**：`[DEV-005] 建议: X`
- **示例**：性能优化建议、代码重构建议、新增可选功能

### plan.md 下游字段同步规则（DEV-001/002/003 共用）

> **目的**：防止 DEV 自动修复改变了任务的实际产出（DTO 字段、方法签名、接口形状），但 plan.md 中下游任务的 `inputs` / `outputs` / `code_skeleton` 仍引用旧产出，导致错误**感染**后续任务（cascade error）。

#### 触发条件

DEV-001/002/003 自动修复完成后，检查本次修复是否改变了以下任一项：
- 当前任务的 `outputs` 字段所声明的产出（如 DTO 多了字段、方法多了参数、接口签名变了）
- 当前任务影响的代码实体（类名/方法名/字段名/常量）

**任一项命中** → 必须执行同步步骤。**均未命中**（如修复仅是内部逻辑、注释、空值校验等不改变接口形状） → 跳过。

#### 同步步骤

1. **扫描下游引用**：在 plan.md 中搜索引用了当前任务的下游任务：
   - `inputs:` 字段含 "T{当前任务ID} 的"
   - `code_skeleton:` 中出现了被改变的类名/方法名/字段名
   - `depends_on:` 含当前任务 ID
2. **逐个评估**：对每个匹配的下游任务，判断字段是否需要更新：
   - `outputs/inputs` 表述变化 → Edit 更新文字描述
   - `code_skeleton` 的 import / 字段 / 方法签名变化 → Edit 更新骨架（仅改受影响的行，不重写整段）
   - `verification` 的命令引用了改变的类名 → Edit 更新命令
3. **记录到 progress.md**：
   ```
   [DEV-{ID}-SYNC] 同步 plan.md: 任务 T{X} 修改影响下游 [T{Y}, T{Z}]，已更新 inputs/outputs/code_skeleton
   ```
4. **影响范围超阈值升级 DEV-004**：受影响下游任务 > 3 个 → 视为架构级变更，停止并按 DEV-004 询问用户（不要静默批量改 plan.md）

#### subagent 兜底（无 plan.md 写权限时）

如果 executor 是 subagent（策略 2/3/4，按设计不能改 plan.md 结构），同步步骤改为**追加 progress.md 一条 SYNC-NEEDED 标记**：
```
[DEV-{ID}-SYNC-NEEDED] 任务 T{X} 修改影响下游 [T{Y}], 主 agent 接管时需更新 plan.md
```
主 agent 在下一次进入 EXECUTE 循环 Step 1（Read spec.md + plan.md）时检测 SYNC-NEEDED 标记并补做同步。

### 偏差严重度判断

| 偏差类型 | 严重度 | 判断依据 |
|---------|--------|---------|
| 小偏差（DEV-001/002/003） | LOW | 自动处理 + 同步 plan.md 受影响下游任务字段 |
| 中偏差（DEV-005） | MEDIUM | 记录备用，不影响当前执行 |
| 大偏差（DEV-004） | HIGH | 可能影响整体方案，需用户决策 |

### 与 3-Strike 的关系

- **3-Strike** 处理**实现错误**（编译失败、测试不通过）
- **偏差规则** 处理**计划偏离**（与原计划不��的情况）

两者可同时生效：
```
任务执行 → 发现问题
├── 实现错误（编译/测试失败）→ 3-Strike 协议
└── 计划偏离（需要额外工作）→ 五条偏差规则
```

---

## 会话恢复

```markdown
## 会话恢复检查

**从 `{workspace}/plan.md`**: 找到首个 ⬜ 或 🔄 任务（🔄 = 上次中断）
**从 `{workspace}/progress.md`**: 会话断点 / 未完成进度 / 下次继续点

是否从上次断点继续？[是/否]
```

---

## 阶段完成标准

- [ ] 所有计划任务已完成
- [ ] 编译通过 + 单元测试通过
- [ ] 偏差已记录并评估
- [ ] `{workspace}/progress.md` 已更新（含会话断点）
- [ ] `{workspace}/plan.md` 恢复检查点已更新

---

## review

# Phase 4: 审查工作流（Review）

> **目标**：证据优先，验证驱动 | **权限**：只读 + 运行测试（禁止修改代码）

| 操作 | 允许 |
|------|------|
| 读取代码、运行测试/构建、写五文件持久化（文件位于 workspace，`$STARK_SESSION_DIR`） | Y |
| 修改代码 | - |

### 进入 REVIEW 的路径

1. **主 agent 直接执行后**：EXECUTE 在主 agent 内完成所有任务，自然进入
2. **Ralph handoff**：`${STARK_SESSION_DIR}/.ralph-handoff` 内容为 `ralph-complete`
3. **用户手动触发**：用户在 EXECUTE 完成后说"进入审查"

**进入 REVIEW 时**，强制重读 `{workspace}/plan.md` 和 `{workspace}/spec.md`（ralph 执行后 context 可能过期）。

---

## 工作流程

### Step 1: Spec 验收 + 计划符合性检查

#### 1.1 Spec 验收（对照 `{workspace}/spec.md`）
Read `{workspace}/spec.md` 的 AC 列表，逐条验证（若无 `spec.md`，退化为 `{workspace}/plan.md` 中内联的验收标准）：
- 运行验证命令 / 检查日志 / 执行 SQL
- 勾选 `{workspace}/spec.md` 中已满足的 AC checkbox
- 未满足的 AC 记录原因，决定是否需要补充任务

| AC | 描述 | 状态 | 验证证据 |
|----|------|------|---------|

#### 1.2 计划符合性检查（对照 `{workspace}/plan.md`）

```markdown
## 计划符合性检查

### 任务完成对比
| # | 计划任务 | 实现状态 | 符合性 |
|---|---------|---------|--------|

### 偏差分析
| 任务 | 计划内容 | 实际内容 | 偏差类型 | 评估 |
|------|---------|---------|---------|------|
```

### Step 2: 运行测试验证

```yaml
必须遵守:
  1. 必须实际运行测试（禁止口头断言）
  2. 必须记录测试输出
  3. 必须覆盖修改的代码
```

### Step 3: 代码质量审查 — 迭代 QA 深化

> 三轮 QA 是**可选增强**，仅在以下条件全满足时启用：
> - 中型/大型任务（LOC > 100 或任务数 > 5）
> - 用户未说"快速审查"或"跳过深度 QA"
> 不满足条件时，退回现有单次 code-reviewer 审查模式。

#### 前置依赖检查

三轮 QA 依赖 Phase 1 的评分基础设施。入口处强制检查：

```yaml
前置检查:
  - 检查 code-reviewer/prompts.md 是否包含"综合评分"章节
  - 存在 → 正常启用三轮 QA
  - 不存在 → 退回单次审查模式 + 输出警告 "[QA] 评分基础设施（Phase 1）未就绪，退回单次审查"
```

#### 与 code-writer 统一审查的边界

- code-writer 统一审查是**编码阶段**即时审查（每个任务完成后，P0-P1阻断+P2+建议）
- planner 三轮 QA 是**REVIEW 阶段**整体质量深化（所有任务完成后，关注交付质量）
- 两者在不同阶段运行，不重复

#### 与 Ralph REVIEW-fix 循环的关系

- Ralph 的"最多 2 轮 REVIEW-fix 循环"（本文件行 128-137）是**故障恢复**（代码无法运行/编译）
- 三轮 QA 是**质量深化**（代码能运行但质量可提升）
- 执行顺序：Ralph 修复循环 → 三轮 QA（代码至少能跑的前提下）

#### 三轮 QA 流程

```yaml
Round 1（功能完整性）:
  焦点: Spec AC 逐条验证 + 测试实际运行
  评分维度: 功能正确性 + 测试覆盖
  调用: 派发 code-reviewer subagent，prompt 中包含"请输出综合评分（轮次 1）"
  判断顺序: 先检查通过条件 → 通过后再检查快速退出 → 未通过则进入修复（不检查快速退出）
  通过条件: 功能正确性 >= 4 且测试覆盖 >= 3
  快速退出: 加权总分 >= 4.0 且 安全与数据完整性 >= 3 → 跳过 Round 2/3，直接 Step 4
  未通过: 创建修复任务 → 执行修复 → 重评 Round 1（最多 1 次重评）
  重评仍不通过: 带 NEED_FIX 状态继续 Round 2（Round 2 覆盖其焦点维度，可能修复 Round 1 遗留）
  轮次间传递: 每轮传递该轮最终分数（修复后的分数，而非初始分数）

Round 2（交互深度）:
  焦点: 边界条件 + 异常路径 + 数据完整性 + AI 生成反模式
  评分维度: 安全与数据完整性 + 代码质量 + AI 反模式
  调用: 派发 code-reviewer subagent，prompt 中包含"请输出综合评分（轮次 2，上轮总分 X.X）"
  通过条件: 安全与数据完整性 >= 4 且代码质量 >= 3 且 AI 反模式 >= 3
  快速退出: 加权总分 >= 4.0 且 AI 反模式 >= 3 → 跳过 Round 3
  未通过: 创建修复任务 → 执行修复 → 重评 Round 2（最多 1 次重评）

  AI 反模式检查清单（AI 反模式维度评分依据）:
    - 过度抽象: 单次使用的 helper/util/wrapper，不必要的接口层
    - 过度防御: 不可能发生的场景也加 null check/try-catch/fallback
    - 模板气味: 千篇一律的结构（每个类都有 builder+factory+strategy）
    - 注释噪音: 对自解释代码加 docstring/行内注释，或注释重复代码语义
    - 过度配置化: 把固定值抽成配置项/环境变量，"万一以后要改"
    - 评分标准: 5=零反模式 4=1-2处轻微 3=有明显反模式但不影响功能 2=反模式影响可维护性 1=严重过度工程

Round 3（边界情况）:
  焦点: 性能、设计模式、代码简化
  评分维度: 加权总分
  调用: 派发 code-reviewer subagent，prompt 中包含"请输出综合评分（轮次 3，上轮总分 X.X）"
  通过条件: 加权总分 >= 3.5
  P4/P5 问题: 记录到 {workspace}/tech-debt.md，不阻断
```

#### 修复预算

- 3 轮 QA 总修复预算 **max(2, floor(原任务数 × 0.3))**（下限 2 个，防止小项目预算为零）
- 每轮可创建修复任务数 = **min(3, 剩余总预算)**（单轮上限 3 个，但受总预算约束）
- 超出预算 → 记录到 tech-debt，不继续修复
- 全局审查次数上限：所有 code-reviewer 调用（含 code-writer 内部 + planner REVIEW）**总计不超过 20 次**

#### 回归检测

每轮评分写入 `{workspace}/progress.md`，格式：

```markdown
### QA Round {N} 评分
| 维度 | 分数 | vs Round {N-1} |
|------|------|----------------|
| 功能正确性 | {score} | {delta} |
| 代码质量 | {score} | {delta} |
| 安全与数据完整性 | {score} | {delta} |
| 测试覆盖 | {score} | {delta} |
| AI 反模式 | {score} | {delta} |
| **加权总分** | **{score}** | **{delta}** |
```

如果 Round N 加权总分 < Round N-1，在 progress.md 标记 `[REGRESSION]` 并输出警告。

### Step 4: 生成完成报告

引用 `templates/templates-review.md` 模板生成审查报告。如启用了三轮 QA，追加 QA 轮次汇总。

---

## 审查结果分级

```yaml
通过: 任务全部完成 + 测试全部通过 + 无 P0 问题
有条件通过: 任务基本完成 + 测试通过 + 有 P1/P2 问题
不通过: 有任务未完成 / 测试失败 / 有 P0 问题 → 返回 EXECUTE 修复
```

---

## 五文件完整性检查（均位于 `{workspace}/`）

- [ ] `spec.md`: 所有 AC 有明确状态（✅ 或说明） + 变更范围与实际一致
- [ ] `plan.md`: 所有任务状态为 ✅ 或有 ❌ 说明 + 恢复检查点已更新
- [ ] `progress.md`: 所有会话有记录 + 偏差已记录 + 最后会话有断点
- [ ] `findings.md`: 重要决策已记录 + 约束条件已更新
- [ ] `session.yaml`: 会话元数据完整（含阶段状态、设计文档路径）

---

## 阶段完成标准

- [ ] 计划符合性检查完成
- [ ] 测试验证实际执行并通过
- [ ] 代码审查完成
- [ ] 完成报告已生成
- [ ] 五文件完整性检查通过
- [ ] 所有验证都有证据支持

---

## 迭代模式判断（REVIEW 完成后执行）

> REVIEW 完成后，检查是否进入 EVALUATE 阶段。

```yaml
判断逻辑:
  1. 读取 {workspace}/session.yaml 的 iteration_mode 字段
  2. 字段缺失 或 值为 "single-pass" → 正常结束（现有行为，不进入 EVALUATE）
  3. 值为 "evaluator-optimizer" → 进入 EVALUATE 阶段（见 workflows-evaluate.md）
```

**守卫条件**：`iteration_mode` 字段缺失时**视为 `single-pass`**，确保现有单次 RIPER 模式不受任何影响。
