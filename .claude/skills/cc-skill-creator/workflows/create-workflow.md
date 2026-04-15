# Skill Creation Workflow（6 步详细流程）

> 来源：从 `cc-skill-creator/SKILL.md` 提取的完整创建流程。SKILL.md 保留步骤摘要。

## Skill Naming

- Use lowercase letters, digits, and hyphens only; normalize user-provided titles to hyphen-case (e.g., "Plan Mode" -> `plan-mode`).
- When generating names, generate a name under 64 characters (letters, digits, hyphens).
- Prefer short, verb-led phrases that describe the action.
- Namespace by tool when it improves clarity or triggering (e.g., `gh-address-comments`, `linear-address-issue`).
- Name the skill folder exactly after the skill name.

## Step 1: Understanding the Skill with Concrete Examples

Skip this step only when the skill's usage patterns are already clearly understood. It remains valuable even when working with an existing skill.

To create an effective skill, clearly understand concrete examples of how the skill will be used. This understanding can come from either direct user examples or generated examples that are validated with user feedback.

For example, when building an image-editor skill, relevant questions include:

- "What functionality should the image-editor skill support? Editing, rotating, anything else?"
- "Can you give some examples of how this skill would be used?"
- "What would a user say that should trigger this skill?"
- "Does this skill need to call any MCP tools or external services?"

To avoid overwhelming users, avoid asking too many questions in a single message.

## Step 2: Planning the Reusable Skill Contents

To turn concrete examples into an effective skill, analyze each example by:

1. Considering how to execute on the example from scratch
2. Identifying what scripts, references, and assets would be helpful when executing these workflows repeatedly
3. **领域知识注入**：若 Skill 涉及特定技术栈，从对应规范库提取关键规则作为检查项或参考引用，而非假设 Agent 自带领域知识

   **判定标准**：Skill 输出涉及"对/错"判断（审查、校验、生成代码）-> 必须注入；仅做信息组织（文档、图表）-> 可选

   **示例**：创建一个"Java API 审查"Skill：
   - 从 `cc-java-backend/SKILL.md` 核心红线提取 Top 5 检查项
   - 在 SKILL.md 的 checklist 中引用：`> 核心检查项见 cc-java-backend 核心红线（Top 10）`
   - 在 prompts.md 的 subagent prompt 中嵌入关键规则原文（如事务 rollbackFor、分层注入规则）

To establish the skill's contents, analyze each concrete example to create a list of the reusable resources to include: scripts, references, and assets.

## Step 3: Initializing the Skill

Skip this step only if the skill being developed already exists.

```bash
scripts/init_skill.py <skill-name> --path <output-directory> [--resources scripts,references,assets] [--examples]
```

Examples:

```bash
scripts/init_skill.py my-skill --path skills/public
scripts/init_skill.py my-skill --path skills/public --resources scripts,references
```

The script creates the skill directory, generates a SKILL.md template with proper frontmatter, and optionally creates resource directories.

## Step 4: Edit the Skill

When editing the skill, remember that it is being created for another instance of Claude to use. Include information that would be beneficial and non-obvious.

### Start with Reusable Skill Contents

Start with the reusable resources identified above: `scripts/`, `references/`, and `assets/` files. Added scripts must be tested by actually running them.

### Update SKILL.md

**Frontmatter**: Write `name` and `description`. Description is the primary triggering mechanism -- include both what the Skill does and specific triggers/contexts.

**CSO 规则（Claude Search Optimization）**：description **禁止摘要工作流**。SP 实验验证：当 description 摘要了 Skill 流程时，Claude 会用 description 替代阅读完整 SKILL.md，导致流程被简化执行。description 只写触发条件。

```
BAD: "dispatches subagent per task with code review between tasks"
BAD: "write test first, watch it fail, write minimal code, refactor"
GOOD: "Use when executing implementation plans with independent tasks"
GOOD: "Use when implementing any feature or bugfix, before writing code"
```

**Body**: Write instructions for using the skill and its bundled resources.

## Step 5: Validate and Register the Skill

### Validate

```bash
scripts/quick_validate.py <path/to/skill-folder>
```

The script checks: YAML frontmatter format, naming conventions, description quality.

**Dry-Run 验证**（推荐）：用 1 个真实场景端到端测试新建 Skill 的完整链路：
1. 模拟触发：确认 skill-rules.json 的 keywords/intentPatterns 能匹配预期用户输入
2. 模拟加载：按资源加载矩阵读取对应文件，确认无缺失引用
3. 模拟执行：用一个简单测试场景走完核心流程，确认步骤可操作、输出格式正确

**纪律性 Skill 额外要求**：如果新建的 Skill 属于纪律性类型（强制规则、TDD、审查等），必须附带至少 1 个压力场景测试——描述一个 Agent 想违规的场景（含时间/沉没成本等压力），验证 Skill 能抵抗合理化。

### Register

详见 [references/registration-checklist.md](../references/registration-checklist.md)

## Step 6: Iterate

After testing the skill, users may request improvements. Often this happens right after using the skill, with fresh context of how the skill performed.

**Iteration workflow:**

1. Use the skill on real tasks
2. Notice struggles or inefficiencies
3. Identify how SKILL.md or bundled resources should be updated
4. Implement changes and test again
