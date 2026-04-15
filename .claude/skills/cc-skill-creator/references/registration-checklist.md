# Skill 注册检查清单

> 来源：从 `cc-skill-creator/SKILL.md` 提取的完整注册规范。SKILL.md 保留注册步骤摘要。

## 注册总览

If the project has a skill registration system (e.g., `skill-rules.json`, `skill-orchestration.md`), follow the project's checklist to register the new skill. This typically includes:

1. Adding the skill entry to the activation rules
2. Updating collaboration matrices if the skill interacts with others
3. Declaring implicit dependencies
4. Verifying cross-file consistency

## skill-rules.json 注册规范

在本项目中，新 Skill 必须在 `skill-rules.json` 中注册。各字段赋值规则如下：

### `type` 字段（Skill 类型）

| 值 | 适用场景 |
|------|---------|
| guardrail | 质量守护（代码审查、TDD 等） |
| workflow | 工作流（开发、设计、规划等） |
| agent | Agent 驱动（自主决策型） |
| analysis | 分析工具（API 分析、代码分析等） |
| tool | 终端工具（SQL、配置查询等） |
| meta-tool | 元工具（Skill 创建器自身） |
| domain | 领域规范（Java 后端规范等） |
| methodology | 独立方法论协议（cc-think-first 等） |

### `tier` 字段（Skill 层级）

| 值 | 适用场景 |
|------|---------|
| guardrail | 守护类 Skill |
| core-workflow | 核心工作流 Skill |
| analysis-tool | 分析工具类 Skill |
| meta-tool | 元工具类 Skill |
| domain-standard | 领域规范类 Skill |
| standalone | 独立方法论 Skill（可被其他 Skill 内联引用） |

### `promptTriggers` 设计指导

- `keywords`：至少 5 个，包含中英文关键词，覆盖用户常用表达
- `intentPatterns`：至少 2 个正则表达式，覆盖常见问句/指令模式
- 避免与已有 Skill 的 keywords 重叠 -- 注册前检查 `skill-rules.json` 中其他 skill 的 keywords
- 示例：
  ```json
  "promptTriggers": {
    "keywords": ["代码审查", "review", "CR", "code review", "审查代码"],
    "intentPatterns": ["审查.*代码", "review.*code|PR"]
  }
  ```

### `skipConditions` 设计指导

- 列出明确不适用的场景关键词，防止误触发
- 示例：`["仅讨论", "不需要审查", "跳过review"]`

### `implicitDependencies` 赋值

- 如果新 Skill 涉及 Java 代码操作，添加 `["cc-java-backend"]`
- 根据实际依赖关系添加其他 Skill

### `fileTriggers`（可选）

- `pathPatterns`：匹配文件路径的正则，如 `["\\.java$", "pom\\.xml$"]`
- `contentPatterns`：匹配文件内容的正则，如 `["@Controller", "@Service"]`

## 协作矩阵更新

新 Skill 创建后，需要在 `shared-rules/skill-orchestration.md` 的协作矩阵中补充条目，声明与现有 Skill 的协作关系（触发、委托、被依赖）。
