# 数据契约注册表

> **加载时机**：Skill 间数据传递时。所有协作数据格式在此集中定义，各 SKILL.md 仅引用本表。

## 统一 ID 格式

全链路使用 `T{epic}.{story}.{seq}` 格式（如 T1.2.3），禁止使用其他格式。

## planner → code-writer / work-mode

```yaml
source: "cc-planner"
id_format: "T{epic}.{story}.{seq}"
required_fields:
  - id: string          # 如 "T1.2.3"
  - subject: string     # 祈使句，如"实现用户登录接口"
  - target_files: string[]
  - acceptance_criteria: string[]
  - estimated_loc: number
optional_fields:
  - description: string
  - dependencies: string[]  # 其他任务 ID
  - test_first: { test_file: string, test_method: string }
  - spec_path: string | null  # spec.md 路径。code-writer Spec Reviewer 据此读取 AC 做验证
  - outputs: string[]       # 本任务产出描述（如 "UserService 接口"、"LoginDTO 定义"）
  - inputs: string[]        # 本任务依赖的前置产出（如 "T1.1.1 的 User 实体类"）
```

## code-writer / work-mode → code-reviewer

```yaml
source: "cc-code-writer" | "cc-work-mode"
required_fields:
  - changed_files: string[]     # 变更文件列表
  - change_type: "new" | "modify" | "mixed"
  - review_mode: "unified" | "blocking"  # 统一审查 | 阻断式强制
optional_fields:
  - task_id: string
  - commit_hash: string
```

## code-reviewer → code-writer / work-mode

```yaml
source: "cc-code-reviewer"
required_fields:
  - status: "PASS" | "BLOCKED" | "WARN"   # 审查结果状态
  - blocking_issues: { location: string, dimension: string, description: string, fix_suggestion: string, confidence: "high"|"medium"|"low" }[]  # P0-P1 阻断级问题
  - suggestion_issues: { location: string, dimension: string, description: string, confidence: "high"|"medium"|"low" }[]  # P2-P5 建议级问题
optional_fields:
  - positive_feedback: string[]           # 正面反馈（做得好的地方）
  - tech_debt_items: string[]             # 技术债务记录
  - score:                                    # Phase 1 量化评分（可选，审查 prompt 含"综合评分"时输出）
      functionality: number                   # 1-5 功能正确性
      quality: number                         # 1-5 代码质量
      security: number                        # 1-5 安全与数据完整性
      testing: number                         # 1-5 测试覆盖
      weighted_total: number                  # 加权总分
      round_number: number                    # QA 轮次号（1/2/3）
      prev_weighted_total: number | null      # 上轮加权总分（首轮为 null）
      regression_warning: string | null       # 回归警告（本轮 < 上轮时填充）
  insights:                                   # 策略进化循环用（evolution loop 模式时输出）
    - dimension: string                       # 对应审查维度
      pattern: string                         # 反复出现的问题模式
      frequency: number                       # 跨轮次出现次数
      severity: string                        # P0-P5
      root_cause: string                      # 指向策略缺失，非代码 bug
  review_feedback:                              # 评估器回溯闭环用（用户反馈审查结论时输出）
    - task_id: string                           # 关联任务 ID
      reviewer_score: number | null             # 审查时的加权总分（无评分时 null）
      user_action: "adopted" | "rejected" | "missed_bug"  # 用户采纳 | 用户驳回 | 上线后发现漏检
      dimension: string | null                  # 涉及维度（rejected/missed_bug 时填充）
      reason: string                            # 用户反馈原因（简述）
      timestamp: string                         # ISO 8601 日期（YYYY-MM-DD）
```

## code-writer 内部: round_contract（evolution loop 模式）

> 详细协议见 `shared-rules/evolution-loop-protocol.md`

```yaml
source: "cc-code-writer (internal)"
required_fields:
  - round_number: number
  - focus_dimension: string             # 本轮重点审查维度
  - weight_overrides:                   # 评分权重覆盖（默认全 1.0）
      functionality: number
      quality: number
      security: number
      testing: number
  - strategy_amendments: string[]       # 本轮注入的策略修正规则
optional_fields:
  - rationale: string                   # 选择该 focus 的理由
```

## cc-api-analyzer → cc-diagram

```yaml
source: "cc-api-analyzer"
required_fields:
  - entities: { name: string, fields: { name: string, type: string, is_pk: boolean, is_fk: boolean, fk_ref: string, comment: string }[], comment: string, module: string }[]
  - relationships: { from: string, to: string, type: "one-to-one"|"one-to-many"|"many-to-many", label: string }[]
optional_fields:
  - modules: { name: string, tables: string[] }[]
  - output_format: "mermaid"
_note: "字段定义为最小必要集，cc-api-analyzer 输出时按此契约构建数据"
```

## cc-tdd → code-writer / work-mode

```yaml
source: "cc-tdd"
required_fields:
  - tdd_mode: boolean        # 是否启用 TDD 模式
  - test_first: boolean      # 是否测试先行
  - test_file_path: string   # 已创建的测试文件路径
optional_fields:
  - test_class_name: string  # 测试类名
  - test_methods: string[]   # 测试方法名列表
```

## code-writer / work-mode → cc-tdd

```yaml
source: "cc-code-writer" | "cc-work-mode"
required_fields:
  - implementation_file_path: string   # 实现文件路径
  - test_result: "pass" | "fail"       # 测试执行结果
optional_fields:
  - failure_message: string            # 测试失败时的错误信息
  - changed_files: string[]            # 实现涉及的变更文件
```

## cc-planner (contract-negotiation) → spec.md（Sprint Contract 协商）

> 详细协商流程见 `cc-planner/workflows/workflows-plan.md` Step 5。

```yaml
source: "cc-planner (contract-negotiation)"
context: "cc-planner PLAN Step 5.2 派发的 Evaluator subagent 审查 Sprint Contract"
required_fields:
  - verdict: "APPROVE" | "REVISE"                # 总体判定
  - approved_behaviors: string[]                  # 确认通过的 TB 编号，如 ["TB-1", "TB-3"]
  - challenged_behaviors:                         # 需修订的 TB
      - tb_id: string                             # TB 编号
        dimension: "可测性" | "完整性" | "防作弊" | "阈值合理性"  # 四维审查中哪个维度有问题
        reason: string                            # 挑战原因
        suggested_revision: string                # 建议修订内容
  - additional_testable_behaviors:                # Evaluator 补充的新 TB
      - behavior: string                          # 行为描述
        verification_method: string               # 验证方法
        type: "rules-based" | "llm-as-judge"      # 验证类型
        rationale: string                         # 为什么需要补充（遗漏的边界/风险）
optional_fields:
  - risk_notes: string[]                          # 实现范围中的风险提示
  - rules_based_ratio: number                     # 当前 rules-based 占比（低于 50% 时警告）
```

## 其他协作契约

> 以下契约字段较少，采用紧凑表格形式。完整使用示例参考各 Skill 的 prompts.md。

| 契约方向 | source | required_fields | optional_fields |
|---------|--------|-----------------|-----------------|
| design → planner | `"cc-design"` | `document_path`: string, `document_type`: "PRD"\|"技术设计"\|"逆向文档", `complexity`: "小型"\|"中型"\|"大型"\|"超大型" | `summary`: string |
| planner → design | `"cc-planner"` | `task_context`: string, `scope`: string[], `complexity`: "中型"\|"大型"\|"超大型" | `existing_docs`: string[] |
| design → cc-diagram | `"cc-design"` | `diagram_type`: "flowchart"\|"sequenceDiagram"\|"classDiagram"\|"erDiagram"\|"stateDiagram-v2", `diagram_data`: string, `highlights`: { `core`: string[], `newAdd`: string[], `extensionPoints`: string[] } | `title`: string |
| design → cc-api-analyzer | `"cc-design"` | `controllers`: string[], `analysis_scope`: "full"\|"partial" | `focus_methods`: string[] |
| sql（独立使用） | `"user"` | `database`: string, `query`: string（仅 SELECT/SHOW/EXPLAIN/DESCRIBE） | `limit`: number |
| cfg（独立使用） | `"user"` | `key`: string（配置 key 名称） | `env`: string（环境：test/prod） |
| cc-ob-session-log → vault | `"user"` | `date`: string (YYYY-MM-DD), `session_goal`: string, `status`: "completed"\|"in_progress"\|"blocked", `work_summary`: string[], `next_context`: string | `decisions`, `discoveries`, `errors_fixed`, `tool_usage`（全部 object[]）|
| cc-ob-spark → vault | `"user"` \| `"cc-ob-aggregate"` | `scan_range`: string, `notes_scanned`: number, `clusters`: object[]（含 theme/notes/keywords/insight/action）| `tensions`, `isolated_notes`, `action_items` |
| cc-ob-aggregate → vault | `"user"` | `aggregation_type`: "weekly"\|"monthly", `date_range`: string, `covered_dates`: string[], `patterns`: object[], `insights`: object[], `next_focus`: object | `trend_analysis`, `strategic_reflection`, `with_spark`: boolean |

## Obsidian 知识飞轮契约补充

### cc-ob-session-log → cc-ob-aggregate（隐式契约，通过 vault 文件传递）

```yaml
# cc-ob-aggregate 通过读取 vault/daily-notes/*.md 消费 session-log 产出
source: "vault/daily-notes/YYYY-MM-DD.md"
required_frontmatter_fields:
  - date: string (YYYY-MM-DD)
  - type: "daily_note"
  - sessions: number         # 当日会话数
required_body_structure:
  - "## 会话记录" 章节
  - 每个会话条目含: 目标/状态/工作摘要/下次上下文
optional_body_sections:
  - "## 今日上下文"          # 级联上下文注入（来自 obsidian-claude-pkm 社区洞察）
  - "## 今日统计"
```

### vault/daily-notes/ → cc-ob-spark（可选消费）

```yaml
# cc-ob-spark 可扫描 vault 任意笔记，不限于 daily notes
source: "vault/daily-notes/*.md" 或 vault 其他 .md 文件
required_inputs:
  - file_paths: string[]     # 扫描的文件列表
  - scan_range: string       # 时间范围描述 (e.g. "14天")
optional_inputs:
  - project_filter: string   # 项目聚焦
  - domain_filter: string    # 领域聚焦（按 tag 或目录）
  - tensions_only: boolean   # 仅检测生产性张力
```

### cc-ob-aggregate 去重契约（covered_dates）

```yaml
# 新聚合报告生成前，扫描已有同类型报告的 covered_dates，跳过已覆盖日期
scan_path: "vault/weekly-reviews/" | "vault/monthly-reviews/"
existing_report_frontmatter:
  - covered_dates: string[]  # 已覆盖的 daily note 日期
dedup_behavior:
  - 读取时跳过已在其他报告 covered_dates 中的日期
  - 新报告 frontmatter 写入本次覆盖的日期范围
```
