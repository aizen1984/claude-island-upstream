## 分析型 Subagent Anti-Pattern 防护

planner 并行分析模式下派发的 subagent 必须包含：

````
### 强制约束
1. **只读模式**: 禁止修改任何文件。只读取和分析。
2. **范围限制**: 只分析 prompt 中指定的目标，不要扩展分析范围。
3. **输出结构化**: 必须按指定格式输出结果。禁止自由格式。
4. **失败标记**: 遇到无法分析的部分，标记为 ❌ 并说明原因，不要猜测。
5. **幻觉防护**: 引用的类名、方法名、路径必须来自 prompt 或 Read 工具确认。禁止编造不存在的类或方法。
6. **200 行上限**: 文本回复不超过 200 行。超出时优先保留结论，压缩过程。
7. **Write 工具守卫**: 禁止用 Write 工具一次性写入超过 200 行的文件。超过时先 Write 骨架（< 100 行），再用 Edit 逐段填充；若无法拆分则标记失败回退给 Lead。
````

---

# 快速参考（按需加载）

> 本章节为按需加载，非 Core 层。核心规则已在 SKILL.md 中定义。
> 此处仅保留 SKILL.md 未覆盖的独有内容。

---

## 阶段切换命令

| 切换到 | 说明 |
|--------|------|
| `进入研究阶段` | 开始只读分析代码 |
| `进入询问阶段` | 澄清模糊点 |
| `进入规划阶段` | 开始任务拆解 |
| `进入执行阶段` | 开始写代码 |
| `进入审查阶段` | 验证实现结果 |

---

## contract-negotiation-reviewer

> **使用场景**：PLAN Step 5.2 派发 Evaluator subagent 审查 Sprint Contract。
> **数据契约**：输出格式见 `shared-rules/data-contracts.md` 的 `contract-negotiation-agent → spec.md`。

````
你是独立的验收标准审查员。你的目标是在 Generator 开始编码前，确保每个 Testable Behavior (TB) 是可测的、具体的、不可作弊的。

你不是 Generator 的队友——你是质量门控。

## 审查对象
{sprint_contract_section}

## 四维审查（每条 TB 必须逐维度判定）

1. **可测性** — TB 能否用命令/脚本得到明确 PASS/FAIL？
   → "接口正常工作" ❌ 不可测
   → "POST /api/x 返回 200 且 body.id > 0" ✅ 可测
   → "性能良好" ❌ 不可测
   → "P99 延迟 < 200ms（wrk -t4 -c100 -d10s）" ✅ 可测

2. **完整性** — 是否遗漏关键边界？
   检查清单：并发、异常输入、空值/null、回滚、权限、幂等、超时
   → 有遗漏 → 作为 additional_testable_behaviors 补充

3. **防作弊** — Generator 能否用最小努力"通过" TB 但实际未解决问题？
   → 如 "返回 200" 可以用硬编码 mock 通过，但实际未接入数据库 → ❌
   → 加强为 "返回 200 且 body.data 来自数据库（DB 有对应记录）"

4. **阈值合理性** — 阈值是否过松（总能过）或过紧（无法通过）？
   → PASS/FAIL 二值用于功能性 TB（可/不可）
   → 数值阈值用于性能/质量 TB（需有基准参考）

## 约束
- 只读模式：不修改任何文件
- 审查 spec.md 的冲刺合同章节 + plan.md 的任务列表
- 不读取 RESEARCH findings 或方案选择（推理隔离）
- 输出不超过 100 行
- rules-based TB 占比须 >= 50%，不足时在 additional 中补充 rules-based TB

## 输出格式（严格遵守）

### 已确认的 TB
- TB-{N}: ✅ [四维度均通过的理由，一句话]

### 需要修订的 TB
| TB# | 维度 | 问题 | 建议修订 |
|-----|------|------|---------|

### 建议新增的 TB
| # | 行为描述 | 验证方法 | 类型 | 理由 |
|---|---------|---------|------|------|

### 综合判断
- **verdict**: APPROVE / REVISE
- **rules_based_ratio**: {当前 rules-based 占比}%
- **risk_notes**: [实现范围中的风险提示，如有]
````

---

## test_first 场景

> **唯一真实来源**：`cc-tdd/SKILL.md` 的 test_first 决策表。此处不再维护副本，请引用 cc-tdd。

---

## 任务粒度标准

> 详见 `shared-rules/task-tracking-rules.md`

---

## session-recovery

# 会话恢复工作流

> 跨会话保持进度，防止信息丢失

---

## 核心理念

```
Context Window = RAM（易失、有限）
Filesystem = Disk（持久、无限）
→ 重要信息必须写入磁盘
```

---

## 一、断点检测流程

```
新会话开始
    ↓
├─ 1. 检查 session 目录（$STARK_SESSION_DIR，未设置则报错）是否存在活跃会话文件
├─ 2. 扫描 workspace 目录中的进度文件
├─ 3. 读取检查点（progress.md），确定断点位置
└─ 4. 询问用户是否恢复
        ├─ 是 → 从断点继续
        └─ 否 → 重新开始
```

---

## 二、检查点格式

> **唯一恢复源**：plan.md 的 emoji 状态（⬜/🔄/✅/❌）是任务恢复的唯一真实来源。progress.md 仅保留元信息（时间戳、异常日志），不冗余记录任务状态。

### progress.md 检查点

```yaml
checkpoint:
  session_id: "session-{uuid}"
  timestamp: "2026-02-02T15:30:00Z"
  phase: "EXECUTE"

  last_modified:
    file: "src/main/java/.../UserService.java"
    line: 45

  blockers: []
  # deprecated: resume_hint 已由 plan.md emoji 状态 + 恢复检查点替代，新会话无需写入
  # resume_hint: "继续实现 createUser 方法的参数校验逻辑"
```

> **注意**：文件驱动模式下，任务状态和当前任务信息从 plan.md 的 emoji 状态获取（🔄 = 当前/中断任务），无需在检查点中冗余记录。

### plan.md 恢复检查点

> plan.md 的任务表本身即为恢复检查点。找到首个 ⬜ 或 🔄 任务即可恢复。
> 以下为 plan.md 末尾"恢复检查点"段的格式：

```markdown
## 恢复检查点

- 最后更新: 2026-02-02 15:30
- 当前进行中: Task T1.2.3（🔄 状态）
- 下次继续: 实现 validateInput()
```

---

## 三、恢复确认提示模板

```markdown
## 会话恢复

**检查点时间**: {timestamp}
**当前阶段**: {phase}

**任务进度**:
| 状态 | 数量 |
|------|------|
| 已完成 | {completed} |
| 进行中 | {in_progress} |
| 待执行 | {pending} |

**当前任务**: {current_task.subject}
- 进度: {current_task.progress_percent}%
- 断点: `{last_modified.file}:{last_modified.line}`
- 下一步: {resume_hint}

---
**继续执行?**
- [ ] 是，从断点继续
- [ ] 否，重新开始
- [ ] 查看详细进度
```

---

## 四、会话结束时

### 1. 更新 plan.md 的恢复检查点

```markdown
## 恢复检查点

- 最后更新: 2026-02-01 15:30
- 完成任务: 3/5
- 当前任务: Task 4 (30%)
- 下次继续: 实现 validateInput()
```

### 2. 追加 progress.md 会话断点

```markdown
## 会话断点 - 2026-02-01 15:30

### 本次完成
- Task 3: UserService.createUser

### 进行中
- Task 4: 60% - validateInput() 方法

### 最后修改文件
- src/main/java/xxx/UserService.java:45

### 下次继续
- 完成 validateInput() 的边界检查
```

---

## 批量检查点同步规则

> 详见 SKILL.md「五文件持久化」章节。核心规则：plan.md 实时更新，progress.md 每 3 任务追加，session.yaml 阶段切换时更新。

### 读写决策提示

| 场景 | 动作 | 原因 |
|------|------|------|
| 刚写完文件 | 不需要重读 | 内容还在 context window |
| 查看了图片/PDF/截图 | 立即写 findings.md | 多模态信息在后续轮次丢失 |
| 连续 50+ 工具调用 | 重读 plan.md | 原始目标可能已出注意力窗口 |

---

## task-decomposition-examples

# 任务分解案例集

> **适用场景**：将需求分解为 2-5 分钟粒度的可执行任务

---

## 分解方法论

```
Epic（完整功能模块）
  └── Story（用户可感知的功能点）
        └── Task（2-5 分钟可完成的技术任务）
```

---

## 案例 1：用户注册功能

```markdown
## Epic: 用户注册模块

### Story 1: 验证码发送（预计 15 分钟）
- [Task 1.1] 创建 SmsService 接口 (3 min)
- [Task 1.2] 实现 SmsServiceImpl 调用短信网关 (5 min)
- [Task 1.3] 创建 VerifyCodeService 生成和存储验证码 (4 min)
- [Task 1.4] 编写 SmsService 单元测试 (3 min)

### Story 2: 验证码校验（预计 10 分钟）
- [Task 2.1] VerifyCodeService 添加 verify() 方法 (3 min)
- [Task 2.2] 添加验证码过期和次数限制逻辑 (4 min)
- [Task 2.3] 编写验证码校验单元测试 (3 min)

### Story 3: 用户创建（预计 20 分钟）
- [Task 3.1] 创建 UserRegisterDTO (2 min)
- [Task 3.2] 创建 UserService.register() 方法 (5 min)
- [Task 3.3] 实现手机号唯一性校验 (3 min)
- [Task 3.4] 实现密码加密存储 (3 min)
- [Task 3.5] 创建 RegisterController 接口 (4 min)
- [Task 3.6] 编写注册流程集成测试 (3 min)

### Story 4: 异常处理（预计 10 分钟）
- [Task 4.1] 定义 RegistrationException (2 min)
- [Task 4.2] 添加手机号格式校验 (3 min)
- [Task 4.3] 添加重复注册检测 (3 min)
- [Task 4.4] 配置全局异常处理 (2 min)

总计：13 个任务，预计 55 分钟
```

---

## 分解检查清单

### 粒度检查
| 检查项 | 通过条件 |
|-------|---------|
| 时间估算 | 2-5 分钟 |
| 单一职责 | 只做一件事 |
| 可独立验证 | 完成后可测试 |
| 无隐藏依赖 | 依赖已明确 |

### 常见过粗 → 正确拆分
| 过粗 | 拆分为 |
|------|--------|
| "实现用户模块" | 3-5 个 Story |
| "写 Service 层" | 按方法拆分 |
| "添加所有校验" | 每种校验一个 Task |

### 常见过细 → 正确合并
| 过细 | 合并到 |
|------|--------|
| "定义变量 a" | 方法实现 |
| "添加一行注释" | 相关 Task |
| "import 一个类" | 使用该类的 Task |
