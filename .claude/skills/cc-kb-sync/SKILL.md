---
name: cc-kb-sync
description: 从当前会话提炼有价值发现并验证后写入Obsidian知识库对应位置。不做排障、不做代码修改。用于排障后沉淀、代码分析后归档、架构洞察同步知识库
allowed-tools: Read, Write, Edit, Grep, Glob, Agent, Bash
---

# 会话知识同步

## Gotchas

> 从设计和预期使用中积累的常见陷阱。每次发现新问题时追加。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 跳过用户确认直接写入 vault | 写入错误或不需要的内容 | 每个阶段门控都需用户确认（EXTRACT/LOCATE/WRITE） |
| 2 | 提取用户的临时讨论或假设 | 未验证的假设被写入知识库 | 只提取 assistant 的结论性内容，排除被否定的方向 |
| 3 | 往基线文档写入时破坏已有结构 | 基线导航索引失效 | 基线只做 append_section，不修改已有章节 |
| 4 | 新建文件后忘记更新首页 domain_map | 新文件无法被检索协议找到 | Phase 4 强制检查并更新 search_index |
| 5 | YAML frontmatter 格式错误 | Obsidian 解析失败 | 使用固定模板 + 写入后 Read 读回验证 |
| 6 | 验证 subagent 超出范围探索 | 上下文溢出、耗时过长 | prompt 限定文件范围，max_turns=5 |
| 7 | 会话无有价值发现时强行提取 | 产生幻觉知识 | Phase 1 识别为空时提示用户并终止 |
| 8 | 项目推断错误（仓库名≠vault 目录名） | 写入到错误的项目目录 | 推断后向用户确认项目名 |
| 9 | 会话经过 compaction 后 EXTRACT 遗漏早期发现 | 有价值的早期结论丢失 | 提示用户手动补充，或建议在 compaction 前触发 cc-kb-sync |
| 10 | 多条 knowledge_items 追加到同一基线文件 | 第二次 Edit 的锚点因第一次写入偏移而失效 | 同文件多条目必须串行执行，每次 Edit 后重新 Read 刷新锚点 |
| 11 | append_section/update_section 前未备份 | vault 无 git，Write/Edit 不可逆，写错无法回滚 | Phase 4.1 先 `cp {target} {target}.bak.$(date +%Y%m%dT%H%M)`，失败立即停止 |
| 12 | Phase 3 定位直接用 Grep 跳过 obsidian CLI | 绕过 vault 全文索引 + 语义排序，准确率显著低 | 遵守五级定位：CLI → 同义词重试 → domain_map → Grep → 目录兜底（详见 workflows.md §3.2）|
| 13 | 混淆 raw→wiki 编译 ingest 与会话知识同步 | 错把外部文档（论文/博客/剪报）当作会话发现处理 | cc-kb-sync 只做"会话中的发现→知识库"；外部源的 raw→wiki 编译流程见 `通用/方法论/数禾Vault-Schema约定.md` 第 3 节，落到 `{项目}/辅助资料/_raw/` 后交由 `cc-ob-lint`（**规划中，尚未实现**）或扩展处理 |

---

## 概述

cc-kb-sync 将当前会话中产生的有价值发现（排障结论、代码分析、架构洞察等）提炼、验证后写入 Obsidian 知识库的正确位置。

**核心价值**：会话中的临时发现 → 验证过的持久化知识

**四阶段流程**：EXTRACT（提炼）→ VERIFY（验证）→ LOCATE（定位）→ WRITE（写入）

> 详细流程见 [workflows.md](workflows.md)

---

## 协作关系

- **接收自**: user（直接触发，通常在排障/分析会话结束后）
- **委托给**: 无（不调用其他 Skill）
- **内部 subagent**: general-purpose（Code Verifier，用于 VERIFY 阶段）
- **复用**: 全局 CLAUDE.md 的 Vault 检索协议（L0/L1/L2）

### ⛔ 强制可观测性日志

cc-kb-sync **不调用其他 Skill**（无 🔗 委托日志），但 VERIFY 阶段会派发 SubAgent，必须输出：

| 时机 | 必须输出 |
|------|---------|
| Phase 2 VERIFY 派发 Code Verifier subagent | `🤖 general-purpose ← cc-kb-sync.VERIFY \| 任务: 验证 [knowledge_item_title]` |

> 注：Phase 4 WRITE 写入 vault 文件不需要专门日志——Claude Code 内置 Write 工具调用本身已可见。
> 注：cc-kb-sync 通常作为**下游被动接收者**——上游 skill（如 cc-troubleshoot 完成排障后）会输出 `🔗 cc-troubleshoot.REPORT → cc-kb-sync \| 原因: 沉淀根因到知识库`，cc-kb-sync 自身不需要重复输出该 🔗。
> 详细日志格式见 `shared-rules/observability-logs.md` §2 运行时日志格式（含 Agent 派发与 Skill 委托）

### 与 migrate-docs 的区别

| 维度 | migrate-docs | cc-kb-sync |
|------|-------------|---------|
| 输入 | 代码仓库中的已有文档文件 | 当前会话上下文中的发现 |
| 操作 | 文件级搬运 | 知识提炼 + 验证 + 章节级写入 |
| 粒度 | 整个文件 | 章节/段落 |

两者独立触发，不互相委托。

---

## 适用场景

| 场景 | 示例 |
|------|------|
| 排障后沉淀 | cc-troubleshoot 排完障，`沉淀到知识库` 保存根因和排查流程 |
| 代码分析后归档 | cc-api-analyzer 分析完，`同步知识库` 保存数据流发现 |
| 架构洞察补充基线 | 深入代码分析发现基线缺失的状态流转 |
| 运维分析归档 | 数据分析会话结束后保存分析结论 |

## 不适用场景

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 搬运代码仓库内已有文档 | migrate-docs | cc-kb-sync 不做文件级搬运 |
| 从 PDF/PPT 提取知识 | shuhe:knowledge-extraction | cc-kb-sync 只从会话上下文提取 |
| 排障本身 | cc-troubleshoot | cc-kb-sync 只沉淀结果，不做排障 |
| 修改代码 | cc-code-writer | cc-kb-sync 只写知识库，不改代码 |
| 从零创建基线文档 | cc-design → migrate-docs | cc-kb-sync 只做增量补充 |

---

## 知识分类矩阵

| 知识类型 | 识别特征 | Vault 目标目录 | 默认 placement |
|---------|---------|---------------|---------------|
| 排障记录 | 有根因+证据链+修复方案 | `运维/排障/排障记录/` | new_file |
| 排障手册 | 通用排查流程（非单次事件） | `运维/排障/` | new_file 或 append |
| 基线补充 | 基线缺失的状态流转/调用链/表关系 | `基线文档/{域}基线.md` | append_section |
| 数据流分析 | 完整数据写入/读取链路 | `辅助资料/数据分析/` | new_file |
| 运维分析 | 统计分析、口径修正 | `运维/` | new_file |

---

## 四阶段摘要

### Phase 1: EXTRACT（提炼）

回扫当前对话，从 assistant 消息中识别结论、证据链、调用链图、SQL 模板、配置发现、架构洞察。

按知识分类矩阵归类为 `knowledge_items[]`，每条含：type、title、content、evidence、confidence、related_files。

**门控**：向用户展示提取结果表格，确认后继续。

### Phase 2: VERIFY（验证）

根据置信度和内容类型分级验证：

| 条件 | 级别 | 方式 |
|------|------|------|
| confidence=high + ≥2 条证据 | V0 | 跳过，用户确认即可 |
| 涉及代码路径/调用链/表关系 | V1 | 派发 Code Verifier subagent |
| 架构级结论/跨模块 | V2 | subagent + 交叉检查基线 |

Subagent 配置：general-purpose，只读工具（Read/Grep/Glob），max_turns=5。

> Prompt 模板见 [prompts.md](prompts.md)

**门控**：所有条目 confirmed/corrected（用户确认修正）后继续。rejected 条目移除。

### Phase 3: LOCATE（定位）

**项目识别**：CWD → git remote → vault 项目目录。无法推断时询问。

**五级定位**（对齐全局 CLAUDE.md L0 协议，逐级退化）：
1. `obsidian search` CLI 全文检索（首选，用 vault 全文索引 + tag 语义）
2. 同义词重试 CLI（拆词替换后 retry）
3. 首页 `domain_map` 关键词匹配（CLI 无命中时退化）
4. `Grep` vault 目录扫描（最后搜索手段，无语义排序）
5. 按知识类型直接映射标准目录 → 兜底

> ⛔ 禁止跳过 Level 1-3 直接 Grep。详见 [workflows.md](workflows.md) §3.2。

**门控**：向用户展示"知识条目 → 目标路径 → 操作类型"表格，确认后继续。

### Phase 4: WRITE（写入）

| 操作 | 工具 | 说明 |
|------|------|------|
| new_file | Write（绝对路径） | 从 templates.md 选模板，填充后写入 |
| append_section | Edit（绝对路径） | 在目标文件指定位置插入新章节 |
| update_section | Edit（绝对路径） | 替换目标章节内容（罕见，需用户明确要求） |

> 写入模板见 [references/templates.md](references/templates.md)

写入后强制：
1. Read 读回验证格式正确
2. 检查并更新 `首页.md` 的 `domain_map`（new_file 时）
3. 输出写入报告

---

## 定位策略详解

### 首页 domain_map 匹配

```
读取 {项目}/首页.md → 解析 search_index.domain_map
→ 提取 knowledge_item 的关键词
→ 与 domain_map 每条的 keywords 做交集
→ 命中数最多的 → 最佳候选
```

### 基线追加的锚点选择

读取目标基线文件的标题结构（`## ` 级别），选择最相关的兄弟章节后方插入。如果无明确相关章节，追加到文件末尾。

### 文件名生成

| 类型 | 格式 | 示例 |
|------|------|------|
| 排障记录 | `{YYYYMMDD}-{摘要}-{traceId后8位}.md` | `20260403-退款回调解析错误-abc12345.md` |
| 数据流分析 | `{主题}.md` | `退款异步回调数据流.md` |
| 运维分析 | `{YYYYMMDD}-{标题}.md` | `20260403-退款成功率分析.md` |
| 排障手册 | `{故障类型}排障手册.md` | `退款失败排障手册.md` |

---

## 数据契约

### 输入

| 字段 | 必须 | 说明 |
|------|------|------|
| 会话上下文 | Y | 当前对话中的发现（自动从会话提取） |
| 项目名 | Y | vault 项目目录名（自动推断或用户指定） |
| 指定内容 | N | 用户可手动指定要同步的发现 |
| `--dry-run` | N | 只展示会写入什么，不实际执行 |

### 输出

| 产出物 | 格式 | 说明 |
|--------|------|------|
| 写入报告 | Markdown 表格 | 写入了哪些文件、每个文件的变更摘要 |
| vault 文件 | Obsidian .md | 实际写入/更新的知识库文件 |
| 首页更新 | YAML 追加 | domain_map 新增条目（如有） |

---

## 资源加载指导

| 场景 | 加载文件 | 范围 | 不加载 |
|------|---------|------|--------|
| 所有场景 | SKILL.md | 全文 | — |
| EXTRACT/LOCATE/WRITE | workflows.md | 对应 Phase 章节 | prompts.md |
| VERIFY 阶段 | prompts.md | Code Verifier 章节 | workflows.md WRITE 章节 |
| WRITE 阶段 | references/templates.md | 对应知识类型模板 | 其他类型模板 |

---

## Vault 路径常量

```
VAULT_ROOT = /Users/caochen/tools/shuhe-kb/数禾项目
项目目录   = {VAULT_ROOT}/{项目名}/
首页       = {VAULT_ROOT}/{项目名}/首页.md
模板       = {VAULT_ROOT}/通用/模板/
```
