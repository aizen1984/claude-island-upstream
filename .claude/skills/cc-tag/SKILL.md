---
name: cc-tag
description: 创建feature tag并自动关联JIRA需求描述。不做代码审查、不部署。用于打tag、创建feature标签
argument-hint: "[review <id>] 或 <需求号> <功能描述>"
disable-model-invocation: true
allowed-tools: Bash(python .claude/skills/cc-tag/*), Bash(basename*), Bash(git*)
---

# Feature Tag & Code Review

## Overview

cc-tag 是一个**工具型 Skill**，支持两个子命令：

| 子命令 | 说明 | 用法 |
|--------|------|------|
| **打 tag**（默认） | 创建 feature tag，自动检测项目/分支 | `/cc-tag REQ-34449 "功能描述"` |
| **review** | 独立执行代码评审通过 | `/cc-tag review 140385` |

---

脚本目录：`.claude/skills/cc-tag/`（相对项目根目录）

## 当前环境

- 项目: !`basename $(pwd) 2>/dev/null || echo '未知'`
- 分支: !`git branch --show-current 2>/dev/null || echo '未知'`

## 操作分发

收到 `$ARGUMENTS` 后，**先判断子命令**：

### 判断规则

- 第一个参数是 `review` → **评审通过模式**
- 否则 → **打 tag 模式**

### 打 tag 模式

自动检测 app_name 和 feature_name：

1. **app_name**：取当前目录名（`basename $(pwd)`）
2. **feature_name**：取当前 git 分支名（`git branch --show-current`）
3. **req_id**：用户必须提供
4. **story**：用户必须提供

> 用户只需输入：`/cc-tag REQ-34449 "功能描述"`
> 如果用户显式指定了 app_name 或 feature_name，以用户指定的为准。

| 用户输入 | 执行命令 |
|----------|----------|
| `<req_id> <story>` | `python .claude/skills/cc-tag/create.py <自动app> <自动branch> <req_id> <story>` |
| `<app> <branch> <req_id> <story>` | `python .claude/skills/cc-tag/create.py <app> <branch> <req_id> <story>` |

### 评审通过模式

| 用户输入 | 执行命令 |
|----------|----------|
| `review <code_review_id>` | `python .claude/skills/cc-tag/review.py <code_review_id>` |

> 需求描述（desc）自动从 JIRA detail 接口查询，无需手动传入。

## 示例

```bash
# 打 tag（自动检测 app_name 和 feature_name）
python .claude/skills/cc-tag/create.py vipship feature_common_release REQ-34449 "common"

# 独立评审通过
python .claude/skills/cc-tag/review.py 140385
```

## 参数

### 打 tag 参数

| 参数 | 说明 | 来源 |
|------|------|------|
| `app_name` | 应用名 | 自动：`basename $(pwd)` |
| `feature_name` | 分支名 | 自动：`git branch --show-current` |
| `req_id` | JIRA 需求号 | **用户输入** |
| `story` | 功能描述/备注 | **用户输入** |

### 评审通过参数

| 参数 | 说明 | 来源 |
|------|------|------|
| `code_review_id` | 代码评审 ID | **用户输入**（打 tag 时会返回） |

## 自动填充字段

以下字段由脚本自动处理，无需用户输入：

| 字段 | 来源 |
|------|------|
| `desc` | 自动查询 JIRA detail 接口的 `summary` |
| `label` | 自动拼接 `req_id:desc` |
| `value` / `key` / `jiraId` | 均等于 `req_id` |
| `codeAnalysis` | 固定 `true` |
| `user` | 从 `config.yaml` 读取 |

## 历史记录

- 存储：项目级 `history.jsonl`（同目录，已 gitignore）
- 打 tag 前自动展示同 app+branch 的历史
- 打 tag 后自动记录（含 codeReviewId）
- 上限 10 条，超出自动淘汰最旧记录
- 独立查看：`python .claude/skills/cc-tag/history.py [app] [branch]`

## 不适用场景

**不适用场景**：

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 代码审查（非评审通过操作） | cc-code-reviewer | 本 Skill 只做评审通过操作，不做代码质量审查 |
| 代码部署/发布 | 运维平台 | 本 Skill 只创建 tag，不触发部署 |
| 需求规划/任务拆解 | cc-planner | 本 Skill 只打 tag 和管理评审 |

---

## 协作关系

- **接收自**: user（直接打 tag 或评审请求）
- **委托给**: 无（独立工具 Skill）

## 完整工作流

### 打 tag 流程

1. **自动检测**：获取当前项目名和分支名
2. **确认参数**：**必须**向用户展示所有参数并等待确认：
   ```
   即将打 tag，请确认参数：
   - 应用: <app_name>
   - 分支: <feature_name>
   - 需求: <req_id>
   - 功能描述: <story>
   确认执行？
   ```
   用户确认后才执行，用户可修正任何参数。
3. **创建 Tag**：调用 `create.py`（内部自动查询 JIRA summary），输出 API 返回的 JSON
4. **交互确认**：如果返回结果包含 `codeReview.codeReviewId`，**必须询问用户**"是否通过代码评审？"
5. **评审通过**：用户确认后，调用 `review.py <codeReviewId>`

### 评审通过流程（独立）

1. **执行评审**：直接调用 `review.py <code_review_id>`
2. **展示结果**：输出是否成功

## Gotchas

> 从实际使用中积累的常见陷阱。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 未确认参数就直接调用 create.py | app_name/feature_name 自动检测可能不符合预期（如在错误目录执行） | 打 tag 前必须展示所有参数等待用户确认，用户可修正 |
| 2 | 打 tag 成功后忘记询问用户是否通过评审 | codeReviewId 丢失，需要从历史记录或 API 返回中重新查找 | 打 tag 返回 codeReviewId 后必须主动询问"是否通过代码评审？" |
| 3 | 在非项目目录下执行导致 app_name/branch 检测错误 | 自动检测的 `basename $(pwd)` 和 `git branch` 不是目标项目 | 确认当前工作目录是目标项目根目录，或手动指定 app_name 和 feature_name |
