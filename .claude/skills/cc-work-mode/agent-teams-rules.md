# Agent Teams 集成规范

> **加载时机**：使用 Agent Teams 时加载。Agent Teams（实验特性）与现有 Skill/Subagent 体系的集成规则。
> 启用条件：`settings.json` 中 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"`

---

## 15.1 两种并行机制定位

| 机制 | 定位 | 通信模式 | 适用场景 |
|------|------|---------|---------|
| **Subagent**（Task 工具） | 单 session 内子进程 | 单向回报 | 已拆解的独立任务、串行流水线 |
| **Agent Teams**（TeamCreate） | 多独立 session | 双向通信 + 共享任务列表 | 需讨论/对抗/协调的复杂任务 |

**核心原则：互补而非替代。**

## 15.2 场景选择矩阵

| 场景特征 | 选择 Subagent | 选择 Agent Teams |
|---------|:------------:|:---------------:|
| 任务已拆解、彼此独立 | **Y** | |
| 串行依赖（A 完成才能 B） | **Y** | |
| 有预设结论需验证/对抗（需推理隔离） | **Y** | |
| 需要队友间实时讨论/质疑 | | **Y** |
| 无预设答案的开放探索（bug 根因、方案选型） | | **Y** |
| 跨模块需协调接口约定 | | **Y** |
| 方案对抗评估 | | **Y** |
| Token 敏感（控成本） | **Y** | |

## 15.3 现有 Skill 与 Agent Teams 的适配关系

| Skill/流程 | 推荐机制 | 理由 |
|-----------|---------|------|
| cc-work-mode（EXECUTE 10并发） | **Subagent** | 任务已拆解、独立执行、不需通信 |
| cc-code-writer（实现+审查链） | **Subagent** | 严格顺序依赖 |
| cc-api-analyzer（四阶段流水线） | **Subagent** | 发现→分析→汇总→展示是流水线 |
| cc-planner（RESEARCH 阶段） | **Subagent** | 研究发现需对抗验证，推理隔离优先 |
| cc-code-reviewer（深度审查） | **Subagent** | 审查结论需对抗验证，推理隔离优先 |
| 对抗验证（adversarial-verification） | **Subagent** | 验证方必须独立判断，Teams 双向通信会破坏推理隔离 |
| 跨模块大型重构 | **Agent Teams** | 模块间需实时同步 |
| 技术方案对抗评估 | **Agent Teams** | 多方案并行论证，无预设立场 |
| 复杂 bug 根因排查 | **Agent Teams** | 多假设并行，无预设答案 |

## 15.4 队友上下文继承

Agent Teams 队友启动时**自动继承**：

| 组件 | 继承方式 | 备注 |
|------|---------|------|
| CLAUDE.md | 自动读取 | 项目规则、Skill 激活规则全部生效 |
| Skills | 全部可用 | 队友可通过 Skill 工具调用 |
| agents/*.md | 通过 Task 可用 | 队友可在内部派发 subagent |
| MCP servers | 自动继承 | |
| permissions | 继承 lead | deny 列表对队友也生效 |

**注意**：`UserPromptSubmit` hook 仅在人工输入时触发。队友自主行动（SendMessage/认领任务）时不触发 skill-activation-prompt.sh，但队友已加载 CLAUDE.md 中的规则。

## 15.5 Hooks 配置

| Hook | 脚本 | 行为 |
|------|------|------|
| `TeammateIdle` | `teammate-idle.js` | exit(2) 提醒队友认领下一个任务 |
| `TaskCompleted` | `task-completed.js` | exit(0) 宽松模式（可切换为 exit(2) 严格质量门控） |

## 15.6 权限预审批

项目级 `settings.json` 中的 `permissions.allow/deny` 对所有队友生效：
- **allow**：文件操作、常用 git、构建工具、Web 工具、Skill 调用
- **deny**：force push、push to main/master、hard reset、rm -rf

> 预审批是 Agent Teams 顺畅运行的前提。未预审批的操作会导致队友卡在权限确认上（无人批准）。

## 15.7 ⛔ 两种并行模式不可混用

> **Task(run_in_background) 与 TeamCreate 是互斥的执行模式，不可在同一任务中混用。**
> 混用会导致 `[Request interrupted by user]` 错误。

| 模式 | 调度方式 | 特征 |
|------|---------|------|
| **Subagent 模式** | `Task(run_in_background=true)`，不传 `team_name` | 单向回报，Lead 轮询结果 |
| **Agent Teams 模式** | `TeamCreate` → `Task(team_name=..., name=...)`，**不传** `run_in_background` | 双向通信，共享任务列表 |

**禁止组合**：
```
# ⛔ 错误：同时使用 team_name 和 run_in_background
Task(subagent_type="...", team_name="my-team", run_in_background=true, ...)

# ✅ 正确：Agent Teams 模式，不传 run_in_background
Task(subagent_type="...", team_name="my-team", name="worker-1", ...)

# ✅ 正确：Subagent 模式，不传 team_name
Task(subagent_type="...", run_in_background=true, ...)
```

**选择原则**：根据任务特征选择模式，不要在 Skill workflow 中硬编码执行模式。

## 15.8 团队规模与任务粒度建议

| 维度 | 建议值 | 说明 |
|------|--------|------|
| 队友数量 | 3-5 | 平衡并行与协调开销 |
| 每队友任务数 | 5-6 | 保持忙碌且可重分配 |
| 总任务数 | 队友数 × 5-6 | 如 3 人 team → 15-18 个任务 |
| 任务粒度 | 自包含 + 明确交付物 | 一个函数、一个测试文件、一份评审报告 |
| 任务拆分原则 | 单任务 30-50 LOC / 1-2 文件 | 太小不值得协调，太大缺少检查点 |
| 文件归属 | 每队友独占 | 避免两人改同一文件 |
| Token 开销 | 3-4x 单 session | 复杂任务的时间收益通常值得 |

**两阶段法**（社区推荐，指 Plan+Execute 两阶段，非审查模式）：
1. **Plan 先行（便宜）**：用 planner 或 plan mode 规划任务，产出任务清单
2. **Team 执行（贵但快）**：将任务清单交给 Agent Team 并行执行

> 先 plan 后 team 提供了一个低成本的审查检查点，避免直接投入高 token 成本的 team 执行。

## 15.9 与现有审查流程的关系

Agent Teams 的任务完成后，仍需走现有审查链路：

```
Agent Teams 产出代码
  ├─ 简单场景 → 直接触发 cc-code-reviewer（建议式）
  └─ 通过 work-mode/code-writer 产出 → 遵循对应的统一审查/阻断式审查
```

Agent Teams 不改变审查规则，只是改变了协作方式。

## 15.10 Delegate Mode 使用建议

创建 Agent Team 后，**立即启用 Delegate Mode（Shift+Tab）**：

| 项目 | 说明 |
|------|------|
| 启用方式 | 创建 team 后按 Shift+Tab |
| 作用 | 限制 Lead 只使用协调工具（TaskCreate/SendMessage/TaskUpdate） |
| 解决的问题 | 防止 Lead 抢队友的实现任务，导致角色混乱 |
| 何时关闭 | 所有队友完成后，Lead 需要做最终整合时 |

**Lead 在 Delegate Mode 下的职责**：
- 任务分配与重分配
- 进度监控（Ctrl+T 查看任务列表）
- 队友间协调（转发信息、解决冲突）
- 结果整合与汇总

## 15.11 竞争假设调试模式

当 bug 根因不明时，使用 **竞争假设模式** 让多个队友并行验证不同理论并相互反驳：

```
创建假设对抗团队：
  Lead: 协调者，收集最终结论
  队友 A: 假设 1（如：数据库连接泄漏）
  队友 B: 假设 2（如：线程安全问题）
  队友 C: 假设 3（如：外部服务超时）

工作流：
  1. 各队友独立调查自己的假设
  2. 发现证据后 broadcast 给其他队友
  3. 其他队友尝试反驳（找反例）
  4. 最后存活的假设 = 最可能的根因
```

**触发条件**：
- planner RESEARCH 阶段识别到复杂 bug（多种可能原因）
- 复杂度评分 7+ 且问题类型为"调试/排查"
- 用户明确要求"多角度排查"

**与现有 Skill 的集成**：
- planner RESEARCH → 识别 3+ 个可能原因 → 建议创建假设对抗团队
- 每个队友可使用 sql/cc-cfg 工具辅助验证
- 最终结论写入 findings.md

## 15.12 Plan→Team 显式集成

planner 与 Agent Teams 的集成路径：

```
planner.PLAN 完成 → 复杂度评分（对应 skill-quality.md §一 复杂度分级）
  ├─ 0-3（小型: ≤50 LOC, 1-3 任务）  → Lead 直接执行（不创建 team）
  ├─ 4-6（中型: 51-300 LOC, 4-7 任务） → Subagent 模式（Task + run_in_background）
  └─ >= 7（大型/超大型: >300 LOC, 8+ 任务或跨 3+ 模块） → 建议创建 Agent Teams
              ├─ 用户确认 → TeamCreate
              ├─ 分配队友 → 每人 5-6 任务
              ├─ 启用 Delegate Mode
              └─ 队友完成 → 走审查流程（§15.9）
```

**planner 自动建议 Team 的条件**（全部满足）：
1. 复杂度评分 >= 7
2. 任务数 >= 8
3. 任务间存在跨模块协调需求（如前后端联调、接口约定同步）
4. 用户未明确指定执行模式

## 15.13 已知限制

| 限制 | 表现 | 应对 |
|------|------|------|
| **shutdown 响应不可靠** | `SendMessage(shutdown_request)` 发出后队友可能不响应，持续发送 idle 通知；`TeamDelete` 也会因"active members"失败 | 目前无可靠解决办法，只能等超时自动退出 |
| **队友不触发 UserPromptSubmit hook** | 队友自主行动（SendMessage/认领任务）时不触发 `skill-activation-prompt.sh` | 队友已继承 CLAUDE.md 规则，手动 Skill 调用仍可用；不影响功能，但跳过了 hook 层的匹配日志 |

