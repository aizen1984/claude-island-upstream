# Skill 协作编排规则

> **加载时机**：每次 Skill 激活时加载。激活由 Hook 自动处理，本文聚焦协作和边界。

---

## 一、激活优先级与冲突解决

| Tier | Skill | 说明 |
|------|-------|------|
| guardrail | cc-code-reviewer | 最高优先级，质量守护 |
| core-workflow | cc-design, cc-planner, cc-work-mode, cc-tdd, cc-code-writer | 核心开发流程 |
| standalone | cc-think-first, cc-adversarial | 独立方法论，可被其他 Skill 内联引用 |
| analysis-tool | cc-api-analyzer, cc-diagram, cc-troubleshoot, cc-kb-sync, cc-ob-*, sql, cfg, cc-sls-query 等 | 分析与工具 |
| meta-tool | cc-skill-creator, eval | Skill 创建管理 |
| domain-standard | cc-java-backend, cc-python, cc-frontend | 规范库（最低优先级） |

冲突解决：高 Tier 覆盖低 Tier。组合关键词按 `skill-rules.json` 的 `combinationRules` 处理（clarify/auto/chain）。用户明确指定优先于关键词匹配。

---

## 二、边界决策表

| 关键判断 | 选择 |
|---------|------|
| 设计文档/PRD | cc-design（不支持迭代循环） |
| 计划/规划/拆解/需要迭代验证 | cc-planner（支持 Evaluator-Optimizer 迭代循环） |
| 写代码/实现（< 5 任务），或需要需求分析 | cc-code-writer |
| 批量/并行（≥ 5 任务且已明确，不需需求分析） | cc-work-mode |
| 理清思路但不需完整规划 | cc-think-first（深度分析后可升级到 planner）|
| 有结论要验证 | cc-adversarial |
| 没答案要找/开放探索 | Agent Teams |
| "分析接口" | cc-api-analyzer（需 ER 图时自动委托 diagram）|
| code-writer 内置审查 vs 独立审查 | 前者自动触发、当前任务范围；后者手动、可跨模块、九维度深度 |

---

## 三、禁止协作

| 禁止链路 | 替代方案 |
|---------|---------|
| design → code-writer | design → planner → code-writer |
| work-mode → work-mode | 由 planner 统一调度 |
| code-reviewer → code-writer | reviewer 返回结果 → 原调用方修复 |
| code-writer → code-writer | 由 planner 统一调度 |
| planner PLAN → EXECUTE（未确认） | 用户确认后进入 EXECUTE |
| planner 多阶段并行 | RESEARCH → INQUIRE → PLAN → EXECUTE → REVIEW 顺序执行 |
| eval/troubleshoot → code-writer | 输出报告 → 用户决定修复方案 |

---

## 四、链路循环检测

- 单次用户请求 Skill 工具调用上限：**6 次**
- 同一 Skill 最多 **2 次**（第 3 次硬停）
- SubAgent 嵌套最多 **2 层**

---

## 五、可观测性

激活后输出 `📋 使用模板` + `🔧 已激活能力` + `📂 资源加载`。详细日志格式见 `observability-logs.md`。

---

## 六、运行时已知约束

- **Agent Teams vs Subagent 选择**：有答案要验证 → Subagent，没答案要找 → Teams
- **Agent Teams shutdown**：SendMessage shutdown_request 后 agents 可能不响应，TeamDelete 因"active members"失败，只能等超时
- **Task + run_in_background 与 TeamCreate 不可混用**：会导致 `[Request interrupted by user]`，二选一

---

## 七、预思考协议

执行类 Skill（work-mode/code-writer/planner/design/skill-creator）启动前执行预思考。三级分流：L0 Skip / L1 Quick / L2 Deep。完整框架见 `cc-think-first/SKILL.md`。
