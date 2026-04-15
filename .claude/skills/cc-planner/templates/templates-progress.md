# 进度与发现模板

> 包含执行进度模板、研究发现模板和会话元数据模板

---

## progress-template

# [功能名称] 执行进度

> 此文件采用**追加模式**，记录每个会话的执行日志

---

## 会话记录

### 会话 1: {{timestamp}}

**开始时间**: HH:mm
**结束时间**: HH:mm

#### 完成的任务

| 任务 | 开始 | 结束 | 备注 |
|------|------|------|------|
| Task 1 | 10:00 | 10:05 | 无偏差 |
| Task 2 | 10:05 | 10:12 | 新增辅助方法 |

#### 偏差记录

- **[Task 2]** 原计划: 实现 A 方法, 实际: 实现 A+B 方法
  - 原因: 发现需要辅助方法进行数据转换
  - 评估: 正向偏差，提高代码可读性

#### 验证结果

```bash
$ mvn test -Dtest=XxxTest
[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

#### 会话断点

- **最后修改的文件**: `src/xxx/Xxx.java:45`
- **未完成的任务**: Task 3 进行中 (60%)
- **下次继续点**: 完成 `validateInput()` 方法
- **阻塞问题**: 无

---

## 总结统计

| 指标 | 值 |
|------|-----|
| 总会话数 | 2 |
| 计划任务数 | 4 |
| 实际任务数 | 4 |
| 偏差数 | 1 |
| 总耗时 | 30 min |

---

## findings-template

# [功能名称] 研究发现

> 此文件记录 RESEARCH 阶段的所有发现，作为持久化知识库

---

## 代码理解

### 相关模块

| 模块 | 位置 | 职责 |
|------|------|------|
| UserService | `service/user/` | 用户业务逻辑 |
| AuthService | `service/auth/` | 认证授权 |
| UserRepository | `repository/` | 用户数据访问 |

### 项目结构

```
src/main/java/com/xxx/
├── controller/
│   └── UserController.java
├── service/
│   ├── UserService.java
│   └── impl/
│       └── UserServiceImpl.java
├── repository/
│   └── UserRepository.java
└── dto/
    ├── UserRequest.java
    └── UserResponse.java
```

### 现有模式

| 模式 | 描述 | 示例 |
|------|------|------|
| Controller | RESTful + Result 封装 | `Result.success(data)` |
| Service | 接口 + Impl 分离 | `@Service` 在 Impl |
| Repository | Condition API 查询 | `findByCondition()` |
| Transaction | Service 层注解 | `@Transactional` |
| Exception | 全局异常处理 | `@ControllerAdvice` |

### 可复用组件

| 组件 | 位置 | 用途 | 如何使用 |
|------|------|------|---------|
| BaseService | `core/service/` | CRUD 基础 | 继承 |
| PageResult | `core/dto/` | 分页封装 | 直接使用 |
| ExcelUtil | `util/excel/` | Excel 处理 | 静态方法 |

---

## 决策记录

### 决策 1: [决策标题]

**时间**: {{timestamp}}
**背景**: [为什么需要做这个决策]

**选项分析**:
| 选项 | 优点 | 缺点 |
|------|------|------|
| A: [方案 A] | [优点] | [缺点] |
| B: [方案 B] | [优点] | [缺点] |

**决定**: 选择 **[方案 X]**
**原因**: [理由]

---

## 约束条件

### 技术约束

| 约束 | 详情 | 影响 |
|------|------|------|
| 框架版本 | Spring Boot 2.7.x | 不能使用 3.x 特性 |
| JDK 版本 | JDK 11 | 不能使用 17 特性 |
| 数据库 | MySQL 5.7 | 注意 JSON 函数兼容性 |

### 业务约束

| 约束 | 详情 | 处理方式 |
|------|------|---------|
| 数据权限 | 按部门隔离 | 使用 DataScope 注解 |
| 操作权限 | 按角色控制 | 使用 @PreAuthorize |

### 性能要求

| 指标 | 要求 | 备注 |
|------|------|------|
| 响应时间 | < 500ms | P99 |
| 并发量 | 100 QPS | 峰值 |
| 批量大小 | 1000 条/批 | 导入导出 |

---

## 风险识别

| 风险 | 可能性 | 影响 | 缓解措施 | 状态 |
|------|--------|------|---------|------|
| 数据量大导致超时 | 中 | 高 | 分批处理 | 待处理 |
| 并发冲突 | 低 | 中 | 乐观锁 | 已考虑 |

---

## 待澄清问题

### 高优先级（必须澄清）

1. **[模糊点 1]**: [描述]
   - 可能性 A: [方案 A]
   - 可能性 B: [方案 B]
   - 建议: [推荐方案及原因]

### 中优先级（建议澄清）

2. **[模糊点 2]**: [描述]

### 低优先级（可选澄清）

3. **[模糊点 3]**: [描述]

---

## 用户确认记录

### 确认时间: {{timestamp}}

### 理解确认
**我的理解**：[功能目标总结]
**用户回复**：[确认/修正内容]

### 需求确认
| 问题 | 用户回答 |
|------|---------|

### 设计决策
| 决策点 | 用户选择 | 原因/备注 |
|--------|---------|----------|

### 约束确认
| 约束类型 | 具体要求 |
|---------|---------|

---

## 待确认问题（遗留）

- [ ] **问题 1**: [问题描述]
  - 选项 A: ... / 选项 B: ...
  - 建议: 选项 A

---

## 参考资料

- [相关文档链接]

---

## session-yaml-template

# 会话元数据模板（session.yaml）

> 记录当前会话状态、阶段进度和关键元数据

```yaml
# 会话元数据
session_id: "sess-{YYYYMMDD}-{feature-slug}"
workspace: "{STARK_SESSION_DIR}"
created_at: "YYYY-MM-DD HH:mm"
updated_at: "YYYY-MM-DD HH:mm"
status: "active"  # active | paused | completed | abandoned

# 阶段状态
current_phase: "RESEARCH"  # RESEARCH | INQUIRE | PLAN | DESIGN | DESIGN-REVIEW | EXECUTE | REVIEW | EVALUATE
phase_history:
  - phase: "RESEARCH"
    started_at: "YYYY-MM-DD HH:mm"
    completed_at: "YYYY-MM-DD HH:mm"

# 复杂度与设计
complexity: "小型"  # 小型 | 中型 | 大型
design_doc_path: ""  # 中型/大型时填写，如 "doc/cc-design/xxx_技术设计.md"
design_review_status: ""  # pending | approved | rejected | skipped


# 委托状态（planner → design 时使用）
delegation:
  active: false  # 是否正在委托给其他 Skill
  target_skill: ""  # 被委托的 Skill 名称，如 "cc-design"
  delegated_at: ""  # 委托开始时间
  expected_output: ""  # 期望产出，如 "doc/cc-design/xxx_技术设计.md"

# 恢复信息（plan.md 的 🔄 状态即为上次中断任务，此处仅补充说明）
recovery:
  last_checkpoint: ""  # 最后检查点时间
  checkpoint_note: ""  # 恢复时的提示信息

# === 迭代循环模式（仅 evaluator-optimizer 时使用） ===
iteration_mode: "single-pass"  # single-pass | evaluator-optimizer
iteration:
  current: 0                   # 当前迭代轮次（0 = 未开始）
  max: 5                       # 最大迭代轮次（来自 goal.md）
  goal_file: "goal.md"         # 目标文件路径（相对于 workspace）
  status: "running"            # running | completed | stagnated | timeout | user-stopped
  history:                     # 每轮评估记录
    - iteration: 1
      started_at: "YYYY-MM-DD HH:mm"
      completed_at: "YYYY-MM-DD HH:mm"
      evaluation_result: "FAIL"       # PASS | FAIL
      weighted_score: 3.2             # 加权总分（0-5）
      regression_depth: "PLAN"        # 回退到哪个阶段（RESEARCH | PLAN）
      strategy_applied: "refine"      # 本轮策略（refine | pivot）
      feedback_summary: "..."         # 评估反馈摘要（一句话）
      key_changes: ["..."]            # 本轮主要改动
  bias_events: []                   # 偏差检测事件记录（P4 meta-evaluation）
  # 示例:
  # - iteration: 3
  #   trigger: "R1"
  #   criteria_arbitrated:
  #     - criterion: "代码可读性"
  #       original_score: 4.5
  #       audit_score: 2.8
  #       arbitrated_score: 2.8
  #   original_weighted_total: 4.2
  #   arbitrated_weighted_total: 3.5
  r2_cooldown_until: 0              # R2 冷却期截止轮次（0=无冷却）
```
