---
name: cc-tdd
description: 强制RED-GREEN-REFACTOR循环的TDD开发模式（仅Java后端），通过Hook提醒测试先行。不跳过测试直接写实现、不适用于Python/前端/脚本。用于关键业务逻辑开发、重构、Bug回归测试
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
paths: "**/*.java"
---

# 数禾 TDD 单测驱动开发

> TDD 规则的唯一真实来源。提供 RED-GREEN-REFACTOR 原则、test_first 决策表、Java 测试规范和反模式清单。通过 PreToolUse Hook 提醒测试先行（advisory 模式，非 deny 阻止）。

## Overview

cc-tdd 有两个角色：**规范定义**（RED-GREEN-REFACTOR 规则、test_first 决策表、反模式清单）和 **TDD 入口**（用户直接请求 TDD 时，协调 code-writer 执行）。编码实现始终由 code-writer/cc-work-mode 完成，tdd 不直接写业务代码。

> **Hook 强度说明**：`tdd-guard.js` 为 advisory 模式——通过 `additionalContext` 注入提醒，而非 `deny` 阻止写操作。"强制"体现在 Skill prompt 规则与 code-writer 审查阶段的反模式检查，而非 Hook 层硬拦截。依赖模型自觉遵循 RED-GREEN-REFACTOR 循环。

**用户直接请求 TDD 时的行为**：联动 cc-code-writer，由 code-writer 创建 `.claude/tdd-session-active` 并按 TDD 流程执行 → 完成后统一审查并删除 sentinel 文件。

**核心机制**：
- Skill prompt 规则：定义 RED-GREEN-REFACTOR 循环、验证标准、反模式
- PreToolUse Hook（tdd-guard.js）：拦截未写测试就改源码的行为

---

## When to Use

**适用场景**：用户明确要求 TDD / 测试驱动、关键业务逻辑开发、复杂算法实现、重构（先补测试再改代码）、Bug Fix（先写失败测试重现 bug，再修复）

## When Not to Use

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 简单 CRUD 无业务逻辑 | cc-code-writer | 无复杂逻辑，测试驱动收益低 |
| DTO / 配置类 / 枚举 | cc-code-writer | 编译即验证，属于 Hook 豁免路径 |
| 纯前端 / 脚本 | cc-code-writer | TDD 规则面向 Java 后端 |
| 已有充分测试的 hotfix | cc-code-writer | 已有测试覆盖，直接修复即可 |

---

## 协作关系

- **接收自**: user（直接请求）、cc-planner（任务含 test_first）
- **联动**: cc-code-writer（TDD 模式编排）、cc-work-mode（批量 TDD 执行）
- **隐式依赖**: cc-java-backend（Java 测试规范基础）
- **被引用**: planner（test_first 决策表）、code-writer（TDD 验证标准）

> 详细协作矩阵见 `shared-rules/skill-orchestration.md` 第二章

---

## 资源加载指导

| 场景 | 加载文件 | 读取范围 | 不加载 |
|------|---------|---------|--------|
| RED/GREEN/REFACTOR 详细流程 | [workflows/tdd-workflow.md](workflows/tdd-workflow.md) 第一章 | L1-L80 | 第二~四章 |
| 反模式清单 | [workflows/tdd-workflow.md](workflows/tdd-workflow.md) 第二章 | 按标题定位 | 第一、三、四章 |
| 与 code-writer/cc-work-mode 联动 | [workflows/tdd-workflow.md](workflows/tdd-workflow.md) 第三章 | 按标题定位 | 第一、二、四章 |
| Hook 激活/停用 | [workflows/tdd-workflow.md](workflows/tdd-workflow.md) 第四章 | 按标题定位 | 第一~三章 |

---

## 核心原则（摘要）

```
RED（写失败测试，确认失败）→ GREEN（最小实现，确认通过）→ REFACTOR（优化结构，确认仍通过）→ 提交
```

**铁律**：RED 必须失败、GREEN 只写最小实现、REFACTOR 只改结构不改行为。纵切式 Vertical Slicing（一次一个测试+实现）。测试行为非实现（验证输入→输出，不绑定内部调用）。

> 详细流程、验证标准、运行命令、失败重试规则见 [workflows/tdd-workflow.md](workflows/tdd-workflow.md) 第一章

---

## test_first 决策表

> 此表为 test_first 的唯一真实来源。planner/code-writer 引用此表，不自行维护副本。
> **适用语言**：Java 后端（由 frontmatter `paths: "**/*.java"` 限定）。Python/前端/脚本任务遵循 cc-code-writer 的通用 TDD 原则，不引用本决策表。

| Task 类型 | test_first | 说明 |
|----------|-----------|------|
| Service 方法 | **必须** | 业务逻辑核心 |
| Controller 端点 | 推荐 | API 契约验证 |
| Repository 方法 | 可选 | 简单 CRUD 不强制 |
| DTO / 配置 / 枚举 | 不需要 | 编译即验证 |
| 工具类（含逻辑） | **必须** | 复杂转换/计算 |
| 工具类（纯委托） | 不需要 | 无独立逻辑 |
| Bug Fix（有明确重现步骤） | **必须** | 先写失败测试重现 bug（RED），再修复（GREEN），确保不回归 |
| Bug Fix（无法写测试重现） | 推荐 | 记录重现步骤，修复后补充回归测试 |

---

## Hook 辅助提醒（advisory，非 blocking）

cc-tdd 配套 `tdd-guard.js`（PreToolUse Hook），在 TDD 模式激活期间**提醒**未写测试就改源码的行为（通过 `additionalContext` 注入，而非 `deny` 阻止）。真正的"强制"来自 Skill 规则 + code-writer 统一审查阶段的反模式拦截。

| 维度 | 设计 |
|------|------|
| 激活条件 | `.claude/tdd-session-active` 文件存在 |
| 检查逻辑 | `src/main/java/a/b/Foo.java` → `src/test/java/a/b/FooTest.java` 是否存在 |
| 豁免路径 | `**/dto/**`、`**/config/**`、`**/enums/**`、`**/entity/**`、`**/model/**`、`**/constants/**`、`**/common/**` |
| 内容豁免 | Lombok 纯数据类（仅含 `@Data`/`@Getter`/`@Setter`/`@Builder`/`@NoArgsConstructor`/`@AllArgsConstructor` 注解，无业务方法）自动放行 |
| 拦截结果 | 建议（additionalContext 提醒，依赖模型自觉）— 详见 workflows/tdd-workflow.md 第四章 |

**TDD 会话生命周期**：

| 调用方 | 激活（创建 `.claude/tdd-session-active`） | 停用（删除） |
|--------|---------------------------------------|------------|
| cc-code-writer | code-writer 在首个 test_first 任务前创建 | 所有 test_first 任务完成且代码提交后删除 |
| cc-work-mode | work-mode executor 继承 code-writer 的会话；若 executor 直接执行 TDD 任务，由 executor 自行创建 | SUMMARIZE 阶段统一删除 |

> **原则**：谁创建谁负责删除。work-mode 的 SUMMARIZE 阶段作为兜底清理点。

> Hook 详细实现见 [workflows/tdd-workflow.md](workflows/tdd-workflow.md) 第四章

---

## 成功标准

- [ ] RED 阶段测试确实失败（失败日志存档于 `{workspace}/tdd-evidence/{slice}-red.log`）
- [ ] 无测试反模式（见 workflows/tdd-workflow.md 第二章）

---

## Gotchas

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | RED 阶段测试直接通过（未失败） | 测试没有验证预期行为 | RED 必须失败，通过则检查断言条件 |
| 2 | 横切式批量写测试再批量实现 | 失去快速反馈循环 | 纵切式：写测试1 → 实现1 → 写测试2 → 实现2 |
| 3 | GREEN 阶段过度实现 | 多余代码无测试覆盖 | 只写让当前测试通过的最小实现 |
| 4 | 忘记删除 `.claude/tdd-session-active` | Hook 持续注入 TDD 提醒 | 谁创建谁删除，work-mode SUMMARIZE 兜底 |
| 5 | REFACTOR 引入新行为无新测试 | 新行为无保护 | 需新行为则回到 RED 开新循环 |
