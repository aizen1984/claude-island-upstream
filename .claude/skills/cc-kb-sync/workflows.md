# cc-kb-sync 工作流

> EXTRACT → VERIFY → LOCATE → WRITE 四阶段详细流程

---

## Phase 1: EXTRACT（从会话提炼知识）

### 1.1 识别有价值内容

回扫当前对话，识别 assistant 消息中的：
- **结论段**：加粗文本、BLUF（Bottom Line Up Front）
- **证据链**：标记为 SLS-N / SQL-N / CODE-N 的证据
- **调用链图**：箭头图（`A → B → C`）
- **SQL 模板**：可复用的查询语句
- **配置发现**：环境变量、配置项值
- **架构洞察**：跨模块交互、设计模式、状态流转

**排除内容**：
- 用户的临时讨论、假设、试探性提问
- 已被否定的错误方向
- 纯工具输出（原始日志、原始 SQL 结果）——只保留分析结论

### 1.2 分类与结构化

按知识分类矩阵归类每条发现：

| 知识类型 | 识别特征 | Vault 目标 |
|---------|---------|-----------|
| 排障记录 | 有根因+证据链+修复方案 | `运维/排障/排障记录/` |
| 排障手册 | 通用排查流程（非单次事件） | `运维/排障/` |
| 基线补充 | 发现基线文档缺失的状态流转/调用链/表关系 | `基线文档/{域}基线.md` |
| 数据流分析 | 完整的数据写入/读取链路追踪 | `辅助资料/数据分析/` |
| 运维分析 | 统计分析、口径修正、成功率等 | `运维/` |

结构化为 `knowledge_items[]`：

```yaml
- id: "K1"
  type: "排障记录"
  title: "退款回调状态码解析错误导致退款失败"
  content: |
    {结构化 Markdown 内容}
  evidence:
    - "SLS-1: xxx logstore 2026-04-03 10:00 traceId=abc123"
    - "SQL-1: SELECT ... FROM refund_order WHERE ..."
    - "CODE-1: RefundCallbackService.java:145"
  confidence: "high"  # high/medium/low
  related_files:       # 用于 VERIFY 阶段
    - "src/main/java/cn/.../RefundCallbackService.java"
```

### 1.3 用户确认

向用户展示提取结果（表格形式）：

```markdown
## 📋 提取结果

| # | 类型 | 标题 | 置信度 | 保留？ |
|---|------|------|--------|-------|
| K1 | 排障记录 | 退款回调状态码解析错误 | high | ✅ |
| K2 | 基线补充 | 退款域异步回调流程 | medium | ✅ |
```

**门控**：用户确认后进入 Phase 2。用户可增删改条目。无有价值内容时提示并终止。

---

## Phase 2: VERIFY（验证准确性）

### 2.1 验证分级决策

| 条件 | 级别 | 操作 |
|------|------|------|
| confidence=high + 证据充分（≥2 条 evidence） | V0 | 跳过验证 |
| 涉及代码路径/调用链/表关系 | V1 | 派发 subagent |
| 架构级结论/跨模块交互 | V2 | 派发 subagent + 交叉检查基线 |
| confidence=low | V1+ | 强制验证 |

### 2.2 派发 Code Verifier subagent

从每条 knowledge_item 的 `content` 中提取可验证的事实陈述（claims）。

**Prompt 组装**（参考 `prompts.md`）：

```yaml
knowledge_items:
  - id: "K1"
    title: "退款回调状态码解析错误"
    claims:
      - claim: "RefundCallbackService.handleCallback() 在 :145 行解析 statusCode"
        files: ["src/main/java/.../RefundCallbackService.java"]
      - claim: "statusCode=3 表示退款成功，但代码中映射为失败"
        files: ["src/main/java/.../RefundStatusEnum.java"]
project_root: "/Users/caochen/IdeaProjects/vipship"
```

**Subagent 配置**：
- subagent_type: `general-purpose`
- 工具: Read, Grep, Glob（只读）
- max_turns: 5

### 2.3 处理验证结果

| 结果 | 操作 |
|------|------|
| ✅ confirmed | 保留，进入 LOCATE |
| 🔧 corrected | 应用修正后展示给用户确认，确认后进入 LOCATE |
| ❌ rejected | 从 knowledge_items 移除，告知用户原因 |

**门控**：所有条目处理完毕（confirmed/corrected+用户确认/rejected）后进入 Phase 3。

---

## Phase 3: LOCATE（定位知识库写入位置）

### 3.1 确定目标项目

```
当前工作目录 → git remote → 提取仓库名 → 映射到 vault 项目目录
例：/Users/caochen/IdeaProjects/vipship → vipship → /Users/caochen/tools/shuhe-kb/数禾项目/vipship/
```

如果无法推断（不在 git 仓库内或仓库名无对应 vault 目录），询问用户。

### 3.2 五级定位（对齐全局 CLAUDE.md 检索协议 L0）

> **铁律**：Level 1-3 是"先 CLI 后退化"的三步渐进路由（符合全局 L0），禁止跳过 Level 1 直接 Grep。Level 4-5 仅在 L0 全部无命中时使用。
>
> **每步必须打印日志**（参考 `shared-rules/observability-logs.md`）：
> ```
> 📖 知识库 [{项目名}] ✓ 命中 Level{N} | 关键词: {xxx} | 命中文件: {path}
> 📖 知识库 [{项目名}] ⚠️ Level{N} 无命中 | 下一步: Level{N+1}
> ```

**Level 1: obsidian CLI 全文检索（首选）**

```bash
# 提取 knowledge_item.title + content 中的关键词（2-5 个核心名词）
obsidian search "query=<关键词>" "format=json" "limit=10" --vault "数禾项目"

# 或按 tag 精准定位（基线文档通常带 #退款域/#订单支付域 等域 tag）
obsidian search "query=tag:#<域名>" "format=json" --vault "数禾项目"
```

- 返回 JSON 文件路径列表 → 选 score 最高且位于 `{vault项目路径}` 内的文件作为候选
- **命中 → 跳到 Phase 3.3 确定 placement**
- 无命中 → Level 2

**Level 2: 同义词重试 CLI（拆词 + 替换）**

```
常见同义词替换表（从全局 CLAUDE.md §知识库复用）：
  扣钱 → 扣款 | 退钱 → 退款 | 福利 → 权益
  跑批 → 定时任务 | 券 → 优惠券 | 续费 → 续约
```

```bash
# 对原关键词拆词 + 替换后重试 CLI
obsidian search "query=<同义词>" "format=json" --vault "数禾项目"
```

- 命中 → 进入 Phase 3.3
- 无命中 → Level 3

**Level 3: 首页 domain_map 退化**

```
1. 读取 {vault项目路径}/首页.md
2. 解析 search_index.domain_map
3. 对每条 knowledge_item 的 title + content 提取关键词
4. 与 domain_map 的 keywords 做交集匹配
5. 命中数最多的条目 → 最佳候选文件
```

**Level 4: Grep 扫描（L0 全无命中时的最后搜索手段）**

```
1. Grep pattern="{关键词}" path="{vault项目路径}" glob="**/*.md"
2. 读取候选文件前 30 行（标题 + frontmatter + 导航索引）
3. 按标题和 tags 判断相关性
```

> **为何 Grep 在 Level 4 而非 Level 1**：obsidian CLI 内置 vault 全文索引 + 权重排序 + tag 语义；Grep 是字符串扫描，无语义、无排序，准确率显著低。当 CLI 全链路无命中时 Grep 才作为兜底。

**Level 5: 目录规则兜底**

按知识类型直接映射（见 Phase 1 分类表），不再搜索。例如：排障记录始终写入 `运维/排障/`。

### 3.3 确定 placement

对每条 knowledge_item 产出定位决策：

| 知识类型 | 默认 placement | 条件变更 |
|---------|---------------|---------|
| 排障记录 | `new_file` | 始终新建 |
| 基线补充 | `append_section` | 找到目标基线文件时追加；未找到则询问用户 |
| 数据流分析 | `new_file` | 始终新建 |
| 运维分析 | `new_file` | 始终新建 |
| 排障手册 | `new_file` | 已有同类手册时改为 `append_section` |

**文件名生成规则**：
- 排障记录：`{YYYYMMDD}-{摘要简称}-{traceId后8位}.md`
- 数据流分析：`{主题描述}.md`
- 运维分析：`{YYYYMMDD}-{分析标题}.md`
- 排障手册：`{故障类型}排障手册.md`

### 3.4 用户确认

```markdown
## 📍 写入定位

| # | 知识条目 | 操作 | 目标路径 |
|---|---------|------|---------|
| K1 | 退款回调状态码解析错误 | 新建文件 | 运维/排障/排障记录/20260403-退款回调解析错误-abc12345.md |
| K2 | 退款域异步回调流程 | 追加章节 | 基线文档/退款域基线.md → "## 异步回调流程" |
```

**门控**：用户确认后进入 Phase 4。

---

## Phase 4: WRITE（执行写入 + 更新索引）

### 4.1 写入执行

> ⛔ **铁律：vault 无 git，Write/Edit 不可逆，append_section 和 update_section 必须先备份。**
> 备份命名约定：`{target}.bak.{YYYYMMDDTHHMM}`，例 `退款域基线.md.bak.20260408T2150`。
> new_file 无需备份（文件原本不存在，失败时 rm 即可）。

按 placement 类型选择操作：

**new_file**（无需备份）：
1. 从 `references/templates.md` 选择对应模板
2. 填充模板变量（标题、日期、tags、内容）
3. `Write` 工具写入 `{vault绝对路径}/{目标路径}`
4. `Read` 工具读回验证格式正确

**append_section**（先备份）：
1. **先备份**：`Bash(cp "{target}" "{target}.bak.$(date +%Y%m%dT%H%M)")` — 失败立即停止，不执行后续步骤
2. `Read` 目标文件，找到插入锚点（最后一个同级章节后、或文件末尾）
3. 按 `references/templates.md` 的"基线补充章节"模板格式化内容
4. `Edit` 工具在锚点位置插入新章节
5. `Read` 工具读回验证插入正确
6. 写入成功后，备份文件永久保留在 vault 中。Phase 4.3 报告中需列出所有 .bak 文件路径，便于用户手动清理

**update_section**（罕见，仅当用户明确要求更新已有章节；先备份）：
1. **先备份**：同 append_section 的 Step 1
2. `Read` 目标文件，定位目标章节的起止范围
3. `Edit` 工具替换章节内容（保留章节标题）
4. `Read` 工具读回验证
5. 备份文件保留规则同上

> **回滚流程**：若用户确认写入错误，`Bash(cp "{target}.bak.{timestamp}" "{target}")` 即可恢复。

### 4.2 首页索引更新

**仅 new_file 需要检查**：

1. `Read` `{vault项目路径}/首页.md`
2. 检查 `search_index.domain_map` 是否已有覆盖新文件关键词的条目
3. 如果没有，在 `domain_map` 末尾追加新条目：
   ```yaml
   - keywords: [关键词1, 关键词2]
     file: {相对路径}
     summary: "{一句话描述}"
   ```
4. `Edit` 工具更新首页
5. `Read` 工具读回验证 YAML 格式正确

### 4.3 写入报告

```markdown
## ✅ 写入完成

| # | 知识条目 | 操作 | 目标路径 | 备份路径 | 状态 |
|---|---------|------|---------|---------|------|
| K1 | 退款回调状态码解析错误 | 新建 | 运维/排障/排障记录/20260403-... | — (new_file) | ✅ 成功 |
| K2 | 退款域异步回调流程 | 追加 | 基线文档/退款域基线.md | 基线文档/退款域基线.md.bak.20260408T2150 | ✅ 成功 |

**首页索引**: 新增 1 条 domain_map 条目（K1）

**回滚说明**：若发现 K2 写入有误，执行 `cp {备份路径} {目标路径}` 即可恢复。
```

---

## 异常处理

| 异常 | 处理 |
|------|------|
| vault 项目目录不存在 | 询问用户是否创建，提供模板 |
| 首页.md 不存在 | 提醒用户先创建首页（引用通用模板路径） |
| 目标基线文件不存在 | 改为 `new_file` 放入 `辅助资料/`，提示用户后续可整合到基线 |
| YAML frontmatter 格式破坏 | 回滚 Edit，用 Write 重写整个 frontmatter 块 |
| subagent 验证超时 | 标记对应条目为 "未验证"，用户决定是否仍写入 |
| 无有价值发现 | Phase 1 提示用户并终止 |

---

## `--dry-run` 模式

用户传入 `--dry-run` 时：
- Phase 1-3 正常执行
- Phase 4 只展示"将会写入的内容预览"，不实际执行写入
- 预览格式：展示每个文件的完整 Markdown 内容 + 目标路径
