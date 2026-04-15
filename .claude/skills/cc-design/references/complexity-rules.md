# 设计任务复杂度分级与 Phase 拆分规则

> 本文件从 SKILL.md 提取，包含任务跟踪、Agent 角色、输出配置的详细规则。
> 复杂度分级标准及 Skill 推荐见 `shared-rules/skill-quality.md`

---

## 设计文档生成任务拆分

### 大型任务（6 Phase）

| Phase | Task 主题 | 依赖 |
|-------|----------|------|
| 1 | 分析需求复杂度 | - |
| 2 | 生成 PRD 文档 | Phase 1 |
| 3 | 生成技术设计文档 | Phase 2 |
| 3.5 | 生成 Mermaid 图表（委托 cc-diagram） | Phase 3 |
| 4 | 执行设计审查 | Phase 3.5 |
| 5 | 输出并验证文档 | Phase 4 |

### 中型任务（4 Phase）

| Phase | Task 主题 | 依赖 |
|-------|----------|------|
| 1 | 分析需求复杂度 | - |
| 3 | 生成技术设计文档 | Phase 1 |
| 3.5 | 生成 Mermaid 图表（委托 cc-diagram） | Phase 3 |
| 5 | 输出并验证文档 | Phase 3.5 |

> 跳过 PRD（Phase 2）和独立审查（Phase 4），审查合并到技术设计阶段。图表生成保留。

### 小型任务

按轻量规则文本列出进度即可，无需 TaskCreate。Phase 1 判断为小型后直接退出，建议用户使用 planner 或 code-writer。

### 逆向文档生成任务拆分

| Phase | Task 主题 | 依赖 |
|-------|----------|------|
| 1 | 发现代码范围 | - |
| 2 | 生成逆向 PRD | Phase 1 |
| 3 | 生成技术文档 | Phase 2 |
| 3.5 | 生成 Mermaid 图表（委托 cc-diagram） | Phase 3 |
| 4 | 验证代码一致性 | Phase 3.5 |
| 5 | 输出并验证文档 | Phase 4 |

### 强制行为

- 设计开始前必须 `TaskCreate` 创建所有 Phase 任务
- 每个 Phase 开始/完成时必须 `TaskUpdate`
- 所有 Phase 完成后输出汇总报告
- 所有文档输出必须包含「快速熟悉」章节，并遵循 [templates.md](../templates.md) 文档表达原则

---

## Agent 角色

> 以下角色为 inline prompt 角色（Skill 内部通过 prompt 指令切换），**非**独立 subagent。不通过 Task 工具派发，不在 agent-rules.json 中注册。

| Agent | 职责 | 使用场景 |
|-------|------|---------|
| **designer** | 生成技术设计文档 | 设计文档生成 |
| **scope-discoverer** | 发现代码范围和边界 | 逆向文档生成 |
| **document-reviewer** | 审查文档质量 | 两种场景通用 |
| **code-verifier** | 验证设计与实现一致性 | 逆向文档验证 |

### 设计阶段 SubAgent 派发配置（强制）

> 以下配置针对 design Skill 委托的外部 agent（对抗验证、cc-api-analyzer、cc-diagram），非上述 inline 角色。

设计阶段所有通过 Agent 工具派发的子 agent **必须**使用以下配置：

```yaml
model: opus          # 使用最强模型
effort: max          # 最大努力思考模式（扩展思考）
```

包括但不限于：对抗验证 agent、cc-api-analyzer 委托 agent、cc-diagram 委托 agent。

---

## 输出配置

### 输出目录

所有设计文档按全局 CLAUDE.md 的文档写入规则输出到 Obsidian vault 对应目录：
- PRD/技术方案 -> `vault/{项目名}/需求/{需求编号}-{需求名}/`
- 逆向基线文档 -> `vault/{项目名}/基线文档/`

> **导航索引维护**：修改或新建基线文档后，必须检查并更新该文档头部的「导航索引」表（H2 行号可能因内容变更而偏移）。新建基线文档时需生成导航索引。

### 文件命名

| 文档类型 | 命名格式 | 示例 |
|---------|---------|------|
| PRD | `[功能名称]_PRD.md` | `用户积分系统_PRD.md` |
| 技术设计 | `[功能名称]_技术设计.md` | `用户积分系统_技术设计.md` |
| 逆向文档 | `[组件名称]_逆向文档.md` | `OrderService_逆向文档.md` |

### 必须章节

所有文档（PRD、技术设计、逆向文档）在「文档信息」之后必须包含「快速熟悉」章节。详细结构见 [templates.md](../templates.md) 快速熟悉章节规范。
