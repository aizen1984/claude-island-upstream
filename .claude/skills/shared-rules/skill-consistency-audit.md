# Skill 仓库一致性审计清单

> **加载时机**：对 skill 仓库做一致性审计（如 `/cc-planner "检查 skill 内部描述/引用不一致"`）时，由 RESEARCH 阶段加载。
>
> **目的**：在不读 27 个 SKILL.md 全文的前提下，按 4 维度快速定位一致性问题；并沉淀本仓库历史上出现过的**幽灵引用反模式**，供未来审计复用。
>
> **适用仓库**：本清单专属于**管理 skill 的仓库**（如 my_claude）。业务项目不管理 skill，无需加载。

---

## 一、两条核心原则

### 1.1 协作矩阵双向对齐

> skill 的"协作关系"段声明必须**两边互相呼应**。单边声明 = 断链。

**规则**：如果 SKILL A 声明「委托给 B」，B 必须在其协作段声明「接收自 A」；反之亦然。

**例外**：如果 A 与 B 不是 Skill 激活关系而是**规则引用关系**（例如 code-writer 只是"遵循 reviewer 的规则"而不激活 reviewer Skill），必须**明确声明为"规则被引用（非 Skill 激活）"**，不得写成"接收自"伪装成真实调用。

**反例（本仓库历史踩坑）**：

```
cc-code-writer/SKILL.md L47 原文：
  "内置审查...不是调用 cc-code-reviewer Skill"    ← A 方否认 Skill 调用

cc-code-reviewer/SKILL.md L69 原文：
  "接收自: cc-code-writer（统一审查门控）"         ← B 方却声明"接收"
                                                    ↑ 两边矛盾
```

**正例（修复后）**：

```
cc-code-reviewer/SKILL.md L69-70：
  - **接收自**: user、cc-work-mode（SUMMARIZE subagent）
  - **规则被引用（非 Skill 激活）**: cc-code-writer 的"内置审查"subagent
    遵循本 Skill 规则，但不走 Skill 激活路径

cc-code-writer/SKILL.md L47：
  - **内置审查**: ...遵循 cc-code-reviewer Skill 的规则
    但不走其 Skill 激活路径——详见 cc-code-reviewer/SKILL.md "接收自/规则被引用" 段
```

### 1.2 幽灵引用必须加类型标签

> 出现 `cc-xxx` 形式的名字时，必须明确**它是哪类实体**。

**三类实体**：

| 类型 | 何时使用 | 调用方式 | 标签示例 |
|------|---------|---------|---------|
| **Skill** | hook 激活或用户 `/xxx` 触发 | skill-activation-prompt | `` `cc-code-reviewer`（**Skill**）`` |
| **subagent_type** | 只能通过 Task 工具 `subagent_type` 调用 | Agent tool | `` `cc-executor`（**内部 subagent_type**）`` |
| **planned** | 名字有了，代码还未实现 | 暂不可调用 | `` `cc-ob-lint`（**规划中，尚未实现**）`` |

**反例（本仓库历史踩坑）**：

```
cc-work-mode/SKILL.md L12 原文：
  "quote grounding 由委托方（cc-code-reviewer / cc-executor）负责"
  ↑ 两个名字混一起，读者可能误以为 cc-executor 也是独立 Skill
```

**正例（修复后）**：

```
cc-work-mode/SKILL.md L12：
  "由 cc-code-reviewer（**Skill**）负责，
   或由 cc-executor（**内部 subagent_type**，见下方"内部 Agent 角色"段）负责"
```

---

## 二、四维度审计 Checklist

### 维度 A：metadata 一致性

目标：`skill-rules.json` 中心注册表 ↔ 磁盘目录 ↔ 各 SKILL.md frontmatter 三处对齐。

| # | 检查项 | grep/脚本 |
|---|-------|---------|
| A1 | rules.json.skills ↔ 磁盘目录（无缺失/冗余） | Python 读 JSON + `ls .claude/skills/` diff |
| A2 | rules.json.description ↔ SKILL.md frontmatter.description（语义一致） | 逐 skill 遍历对比 |
| A3 | SKILL.md frontmatter.name ↔ 目录名 ↔ rules.json key | frontmatter 解析 |
| A4 | `tiers` / `priorityOrder` / `combinationRules` / `_forbiddenCombinations_implementedBy` 中的 skill 名全部在 `skills` dict 中存在 | 解析 JSON 顶层块 |
| A5 | frontmatter 必填字段（name, description）完整 | grep `^name:` `^description:` |

### 维度 B：内部文件/锚点引用

目标：各 SKILL.md 引用的本 skill 内部 md 文件/锚点真实存在。

| # | 检查项 | 方法 |
|---|-------|------|
| B1 | `](workflows/xxx.md)` 等本目录内引用，文件真实存在 | 正则 `\]\([^)http][^)]+\.md[^)]*\)` 提取 + 文件存在判断 |
| B2 | `](workflows/xxx.md#anchor)` 锚点在目标文件中真实存在 | grep 目标文件 `^#.*anchor` |
| B3 | 资源加载表里列的文件都存在 | 抽查每个 SKILL.md 的"资源加载"表 |
| B4 | 孤儿文件（skill 目录下存在但 SKILL.md 未引用） | 默认不处理（多为子资源，如 `templates/` `references/` `patterns-*`） |

### 维度 C：跨 skill + shared-rules 引用

目标：跨界引用的对象真实存在且类型标签正确。

| # | 检查项 | 方法 |
|---|-------|------|
| C1 | 所有 SKILL.md 里出现的 `cc-xxx` 名字，要么在 27 个 skill 清单里，要么带类型标签（subagent/planned） | grep `cc-[a-z-]+` 批量提取 + 白名单对照 |
| C2 | `](shared-rules/xxx.md)` 引用指向真实文件，**禁止** 引用 `.bak.*` | grep `shared-rules/` + 文件存在判断 |
| C3 | 协作矩阵双向对齐（原则 1.1） | 抽查 5-10 组核心关系：planner↔design / planner↔work-mode / work-mode↔reviewer / writer↔reviewer 等 |
| C4 | `skill-orchestration.md` 矩阵 ↔ 各 SKILL.md 协作段一致 | 交叉对照 |

### 维度 D：shared-rules 双源漂移

目标：SKILL.md 不得复制 shared-rules 规则正文（违反 DRY）；合理冗余需加源注释。

| # | 检查项 | 方法 |
|---|-------|------|
| D1 | SKILL.md 是否复制了 shared-rules 的特征性句子/表格 | grep 关键术语（如 `模式 A`、`FLCA`、`STARK_SESSION_DIR`）在多文件命中 |
| D2 | 命中的复制段 diff 源文件：是"冗余一致"还是"已漂移"？ | 内容 diff |
| D3 | 合理冗余（如 subagent 必须静态展开 prompt）是否有 `<!-- Source: ... -->` 注释 + 同步检查清单？ | grep `Source: shared-rules` |

---

## 三、常见陷阱（本仓库历史踩坑）

### 陷阱 1：子 agent 报告误判"断言不存在"

> 派发 Explore agent 做审计时，"断言 X 不存在"类结论最容易漂移（agent 搜索范围不足或误读上下文）。

**案例**：本仓库 Iter 28 的 skill 一致性审计中，agent C 报告"cc-diagram 未声明接收自 cc-design"——实际该文件 L48 已正确声明 `接收自: cc-api-analyzer、cc-design`。

**对策**：Lead 必须对"X 不存在"这类否定性断言独立 grep/Read 验证，不盲信。见 `feedback_agent_report_cross_check.md`。

### 陷阱 2：子 agent 引用行号偏差

> 大文件（> 150 行）中子 agent 返回的行号容易 ±10 行偏移，但**判断往往是对的**。

**案例**：agent C 报告"cc-code-reviewer L78 接收自 cc-code-writer"，实际 L78 是资源加载段，真实 `接收自` 字段在 L69——但两边矛盾的判断正确。

**对策**：不因行号偏差否定整个报告。Lead 用 Grep 重新定位真实行号，保留判断价值。

### 陷阱 3：复制粘贴有"工程正确性"情况

> shared-rules 规则被 SKILL.md 复制**不一定是漂移**——subagent fresh context 无法解析路径引用，Lead 派发 prompt 时必须内联展开。

**案例**：`cc-adversarial/prompts.md` L20-49 复制 `shared-rules/adversarial-verification.md` §四 的 FLCA 评分表——这是故意的，但必须加 `<!-- Source: ... -->` 注释 + 文件末尾"同步检查清单"段，防止未来源文件更新时悄悄漂移。

**对策**：发现复制时先看是否有 subagent 展开需求。如有：加源注释 + 同步清单。如无：直接改为引用。

---

## 四、审计方法（推荐流程）

1. **Step 0**：摸底——`ls .claude/skills/` + Python 读 `skill-rules.json` 顶层结构
2. **Step 1**：并行派发 4 个 Explore agent 分别覆盖维度 A/B/C/D（见 cc-planner RESEARCH 阶段模式）
3. **Step 2**：**Lead cross-check**——对 agent 的关键断言（尤其否定性断言）grep 独立验证（对照陷阱 1-2）
4. **Step 3**：汇总到 `findings.md`，**诚实披露纠偏记录**
5. **Step 4**：按修复优先级 → plan.md → EXECUTE

---

## 五、快速验证命令模板

```bash
cd /path/to/skill-repo

# A. metadata
python3 -c "
import json
data = json.load(open('.claude/skills/skill-rules.json'))
skills_dict = set(data['skills'].keys())
# 对照磁盘目录 + tiers/priorityOrder 等交叉块
"

# C1. 幽灵 skill 引用
grep -rhoE 'cc-[a-z-]+' .claude/skills/*/SKILL.md | sort -u | \
  comm -23 - <(ls .claude/skills/ | grep '^cc-' | sort) | \
  grep -v '^cc-\(executor\|researcher\|reviewer\)$'  # 排除已知 subagent_type

# C2. .bak 引用（零容忍）
grep -rn 'shared-rules/.*\.bak' .claude/skills/ && echo "FAIL: 引用了 .bak 文件"

# D1. 复制粘贴嫌疑
grep -rln 'FLCA\|STARK_SESSION_DIR\|模式 A' .claude/skills/ | grep -v shared-rules
```
