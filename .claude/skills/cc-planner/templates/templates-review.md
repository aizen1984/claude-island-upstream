# 评审与任务模板

> 包含设计评审模板、审查报告模板和 Task 模板库

---

## design-review-prompt-template

# 设计评审提示模板

> 用于 DESIGN-REVIEW 阶段展示评审提示

```markdown
## 设计评审

### 设计文档摘要
| 项目 | 内容 |
|------|------|
| 模块数 | N |
| 接口数 | M |
| 数据表数 | K |
| 事务边界 | [描述] |
| 风险项 | [描述] |

### 文档位置
📄 `doc/cc-design/[功能名称]_技术设计.md`

### 请选择
- ✅ **通过** — 进入 EXECUTE 阶段
- 🔄 **需要修改** — 请说明修改意见
- ❌ **终止** — 结束整个 planner 流程
```

---

## review-report-template

# 审查报告模板

> 用于 REVIEW 阶段生成完成报告

```markdown
# 审查报告

## 功能: [功能名称]

### 审查概况
| 项目 | 状态 |
|------|------|
| 审查时间 | YYYY-MM-DD HH:mm |
| 计划任务数 | N |
| 完成任务数 | M |
| 测试用例数 | K |

### 综合评估
**完成状态**: 通过 / 有条件通过 / 不通过

### 后续行动
| 行动 | 优先级 | 负责人 |
|------|--------|--------|
```

---

## review-qa-rounds-template

> 仅在启用三轮 QA 深化时使用。追加到审查报告末尾。

### QA 轮次汇总

| 轮次 | 焦点 | 发现问题 | 修复任务 | 加权总分 | 结论 |
|------|------|---------|---------|---------|------|
| Round 1 | 功能完整性 | {n} 个 | {m} 个 | {score} | PASS/NEED_FIX/SKIP |
| Round 2 | 交互深度 | {n} 个 | {m} 个 | {score} | PASS/NEED_FIX/SKIP |
| Round 3 | 边界情况 | {n} 个 | {m} 个 | {score} | PASS/NEED_FIX/SKIP |

### 评分趋势

| 维度 | R1 | R2 | R3 | 趋势 |
|------|----|----|----|----- |
| 功能正确性 | {s} | {s} | {s} | {↑/↓/→} |
| 代码质量 | {s} | {s} | {s} | {↑/↓/→} |
| 安全与数据完整性 | {s} | {s} | {s} | {↑/↓/→} |
| 测试覆盖 | {s} | {s} | {s} | {↑/↓/→} |
| **加权总分** | **{s}** | **{s}** | **{s}** | **{↑/↓/→}** |

### 回归事件（如有）

| 轮次 | 下降维度 | 原因分析 |
|------|---------|---------|

---

## task-templates

# 数禾 Task 模板库

> 标准化 Task 模板，用于 cc-planner 的任务分解

---

## Task 粒度标准

> 任务粒度标准见 `shared-rules/task-tracking-rules.md`

---

## Task 基础模板

```yaml
task:
  id: "T{epic}.{story}.{seq}"
  type: "{type}"  # dto | service | repository | controller | test | config
  subject: "{subject}"
  description: |
    {type 特定内容，见差异表}

  target_files:
    - "{file_path}"

  acceptance_criteria:
    - {criteria}

  test_first: {见差异表}
  estimated_loc: {见差异表}
```

---

## Task 类型差异表

| 类型 | subject 模式 | description 要点 | target_files | test_first | LOC |
|------|------------|----------------|-------------|-----------|-----|
| dto | 创建 {Entity}DTO | 字段列表 + 注解要求（@Data/@NotNull/Swagger） | dto/{Entity}DTO.java | 不需要 | 20-40 |
| service | 实现 {Svc}.{method} | 方法签名 + 业务逻辑 + 异常处理 | service/ + impl/ | **必须** | 30-50 |
| repository | 实现 {Repo}.{method} | 方法签名 + 查询条件 | repository/ + mapper.xml | 可选 | 15-30 |
| controller | 实现 {Ctrl}.{method} | API 定义 + 请求参数 + 响应格式 | controller/ | 推荐 | 25-40 |
| test | 编写 {TestClass} | 测试方法列表 + Mock 依赖 + GWT 结构 | test/ | 不需要 | 50-100 |
| config | 添加 {config} 配置 | 配置项列表 + 默认值 | application.yml + config/ | 不需要 | 15-30 |

---

## Task 依赖关系示例

```yaml
epic: "E1-用户模块"
stories:
  - id: "S1.1"
    name: "用户创建功能"
    tasks:
      - id: "T1.1.1"
        subject: "创建 CreateUserRequest DTO"
        blocked_by: []

      - id: "T1.1.2"
        subject: "创建 UserDTO"
        blocked_by: []

      - id: "T1.1.3"
        subject: "实现 UserRepository.findByEmail"
        blocked_by: []

      - id: "T1.1.4"
        subject: "实现 UserService.createUser"
        blocked_by: ["T1.1.1", "T1.1.2", "T1.1.3"]

      - id: "T1.1.5"
        subject: "实现 UserController.createUser"
        blocked_by: ["T1.1.4"]

      - id: "T1.1.6"
        subject: "编写 UserServiceTest"
        blocked_by: ["T1.1.4"]
```
