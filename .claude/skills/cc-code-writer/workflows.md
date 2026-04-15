# 工作流合集

---

# 一、需求分析工作流

> 将用户需求转化为可执行的技术任务列表

## 工作流程

```
用户需求 -> 1.理解需求 -> 2.识别不明确点(有疑问?->询问) -> 2.5.SOLID预检
         -> 3.拆解任务 -> 4.分析依赖 -> 5.确定Skill路由 -> 6.输出计划
```

---

## 步骤详解

### 步骤 1：理解需求

阅读需求描述，识别核心业务目标、涉及实体和操作，查看现有代码。

**输出**：
```
## 需求理解
**业务目标**：{一句话描述}
**涉及实体**：{实体1, 实体2, ...}
**核心操作**：{操作1, 操作2, ...}
```

### 步骤 2：识别不明确点

**检查清单**：输入参数？输出结果？边界条件？错误处理？权限？性能？

如有不明确点，使用 `AskUserQuestion` 询问用户。

### 步骤 2.5：SOLID 设计预检

> 涉及**新建类/接口**时必须执行

| SOLID | 检查问题 | 不通过时的行动 |
|-------|---------|---------------|
| **S** 单一职责 | 这个类/方法只做一件事吗？ | 拆分为多个类/方法 |
| **O** 开闭原则 | 新增类型需要改已有代码吗？ | 设计策略接口 + 工厂 |
| **L** 里氏替换 | 子类能完全替换父类吗？ | 考虑用组合替代继承 |
| **I** 接口隔离 | 接口方法都会被使用吗？ | 拆分为多个小接口 |
| **D** 依赖倒置 | 依赖的是接口还是具体类？ | 提取接口，注入依赖 |

**设计思考模板**：

```markdown
## SOLID 设计预检

### 待设计的核心类/接口
| 类名 | 职责 | SRP 检查 |
|------|------|---------|
| {ClassName} | {单一职责描述} | 职责单一 / 需拆分 |

### 扩展性设计（OCP）
- [ ] 是否存在多种类型/策略？-> 是 -> 设计策略接口
- [ ] 未来可能新增类型？-> 是 -> 使用工厂模式

### 依赖设计（DIP）
| 类 | 依赖 | 依赖类型 | 是否可 Mock |
|----|------|---------|------------|
| {Service} | {Repository} | 接口 | 是 |

### 设计决策
- **策略接口**：{是否需要} - {原因}
- **工厂模式**：{是否需要} - {原因}
```

**快速判断**：
```
1. 会变成"上帝类"？ 2. 新增功能要改现有代码？ 3. 能轻松 Mock？
任一答案不理想 -> 需要重新设计
```

### 步骤 2.6：反重复管道检查

> **新增策略实现类 / implements 已有接口时必须执行**（与 2.5 串行，不可跳过）

**触发条件**：任务涉及「新建类 implements 已有接口」或「新增策略/适配器实现」

```
已有实现 ──┐
            ├─→ 逐步对比 ──→ 相同步骤 > 50%? ──→ 是 → ⛔ 禁止直接 implements
新实现草稿 ─┘                                          必须先提取基类/共享管道
                                         └─→ 否 → ✅ 继续
```

**必须执行的 4 步检查**：

| # | 检查 | 方法 | 不通过时行动 |
|---|------|------|-------------|
| 1 | **共性扫描** | 将新实现与已有实现逐行对比，标记相同步骤 | 相同 > 50% → 提取基类或共享管道（Template Method），差异点变钩子 |
| 2 | **抽象粒度** | 问：接口包裹了整条流程，还是只定义了变化点？ | 接口包裹整条流程但变化点仅 1-2 步 → 用 Template Method 把变化点抽成钩子 |
| 3 | **职责归属** | 新方法加到某类前，问：调用者是谁？和类的主要调用者一样吗？ | 调用者不同 → 方法不属于这个类，拆到独立组件 |
| 4 | **第三供应商测试** | 假设再来一个新供应商，数要新建/修改几个文件、复制多少行 | 复制行数 > 20 行 → 抽象不够，回到步骤 1 重新设计 |

**输出**（表格 + 结论，与 2.5 同格式）：

```markdown
## 反重复管道检查

| 维度 | 结果 | 阻断? |
|------|------|-------|
| 共性比例 | {X}%（{相同步骤}/{总步骤}：{列出相同步骤名}） | > 50% → ⛔ |
| 抽象粒度 | 接口包裹{整条流程/仅变化点}，变化点 {N} 个（{列出}） | 整条流程 + 变化 ≤ 2 → ⛔ |
| 职责归属 | {一致 / 存在混合调用者：回调 vs 出站} | 混合 → ⚠️ |
| 第三供应商 | 新增 {N} 文件，复制 {N} 行 | > 20 行 → ⛔ |

**结论**：{直接 implements / 需先重构：提取 AbstractXxx，钩子为 buildXxx() + parseXxx()}
```

> **核心原则：看到已有接口不要当作圣旨，先问它切得对不对。**

**传递给 Implementer**：当步骤 2.6 通过（直接 implements）时，必须在 Implementer 的 `EXISTING_PATTERNS` 中附带已有实现的**管道步骤摘要**（来自上表的"共性比例"行），使 Implementer 能执行实现时的二次确认。

### 步骤 3：拆解技术任务

**原则**：每个任务独立可测试，粒度为1个方法/类/功能点，按 Repository -> Service -> Controller 拆解。
```
### 任务 {N}：{任务名称}
**类型**：[新增/修改/删除] | **层级**：[Controller/Service/Repository/其他]
**文件**：{预期的文件路径}
**描述**：{具体要做什么}
**验收标准**：{标准列表}
```

### 步骤 4：分析任务依赖

| 依赖类型 | 示例 | 处理方式 |
|---------|------|---------|
| 代码依赖 | Service 调用 Repository | Repository 先执行 |
| 数据依赖 | 方法B 需要方法A 的返回值 | A 先执行 |
| 文件依赖 | 同一文件的多处修改 | 顺序执行避免冲突 |
| **集成依赖** | **Service 需要使用同批次实现的 Lock 组件** | **并发执行，但在 prompt 中注入集成预告** |
| 无依赖 | 独立的 CRUD 方法 | 可并发执行 |

> **集成依赖说明**：当任务 A 的产出（接口/类）需要被同批次任务 B 的实现使用时，属于集成依赖。不要求串行执行（因为 A 的接口签名在设计阶段已确定），但必须在 B 的 Implementer prompt 中注入**集成预告**，声明 A 将产出的接口名称、方法签名和使用场景，使 B 的实现预留集成点。
>
> **集成预告模板**（填入 Implementer prompt 的上下文合约）：
> ```
> ### 集成预告（同批次任务产出）
> 以下组件由同批次其他任务实现，你的代码应注入并使用它们：
> - {组件名} ({接口路径}): {方法签名} — 用途: {在你的代码中如何使用}
> ```

### 步骤 5：确定 Skill 路由

提取关键词，匹配 `resources.md` 第三章路由表，确定加载模块。

### 步骤 6：输出任务计划

```markdown
## 任务执行计划

### 需求概述
{需求的一句话描述}

### 任务列表
| # | 任务名称 | 类型 | 层级 | 依赖 | 可并发 |
|---|---------|------|------|------|--------|

### 执行顺序
**第1批（并发）**：任务列表
**第2批（顺序）**：任务列表（依赖关系）

### Skill 路由表
| 任务 | 加载模块 |
|------|---------|

### 预计产出
- 新增文件：{列表}
- 修改文件：{列表}
```

---

## 下一步

- **Bug Fix** -> 第 1.5 章 Bug Fix 通道
- **单任务** -> 第二章任务执行工作流
- **多任务** -> 第三章并发执行工作流

---

# 一-B、Bug Fix 通道

> Bug 修复必须先重现，再修复。未重现不可进入修复循环。

## 铁律

```
未重现的 Bug 不可修复。先写失败测试或确认重现步骤。
```

## Bug Fix 流程

```
1. 重现（REPRODUCE-first）
   ├─ 能写失败测试 → 编写失败测试，运行确认 RED
   └─ 不能写测试（环境/外部依赖）→ 记录精确重现步骤 + 实际 vs 预期
2. 定位根因（Root Cause）
   ├─ 读错误信息/堆栈 → 追溯调用链 → 定位源头
   └─ 不要在症状点修复，追溯到源头
3. 修复（最小改动）
   ├─ 只改根因，不顺手"优化"
   ├─ 一次只改一个变量
   └─ 派发 Implementer（可选）：填充 `TDD_MODE.test_file_path` 指向步骤 1 的失败测试
        → 复用 prompts.md 变体 A（阅读测试 → GREEN → REFACTOR → 自检）
4. 验证
   ├─ 失败测试变 GREEN
   └─ 全量测试无回归
```

## 3-Fix 架构质疑规则

连续 3 次修复尝试均失败时：

```
⚠️ 3 次修复失败 → 停止修复，质疑架构：
- 这个模式本身是否合理？
- 每次修复是否揭示了不同位置的新问题？
- 是否需要重构而非打补丁？

→ 上报用户，讨论是否需要架构变更，不要尝试第 4 次修复。
```

## Bug Fix 完成后→统一审查衔接

Bug Fix 通道的步骤 4（验证）通过后，**必须进入统一审查流程**，不可跳过：

```
Bug Fix 步骤 4 验证通过
    ↓
步骤 4.5: 进入第二章「任务执行工作流」的统一审查流程
    ├─ 步骤 4（Unified Reviewer）：P0-P5 全维度审查
    │   检查重点：修复是否引入规范违规 + 回归风险 + 测试是否充分
    └─ 通过后 → 步骤 5：标记完成 + 提交
```

**Bug Fix 审查的特殊规则**：
- Unified Reviewer 聚焦修复代码本身，不扩散到未修改的旧代码
- 必须确认：失败测试已变 GREEN + 全量测试无回归
- 快速审查通道判断依据 `shared-rules/skill-quality.md` 审查跳过条件（< 50 LOC 单文件且不涉及 P0 关键词 → 仅 P0-P1 维度）

---

# 二、任务执行工作流

> 单个任务的完整执行流程：（TDD 模式：测试先行 ->）实现 -> 统一审查

## 标准模式流程

```
1.预提取规范 -> 1.2.验收预审(条件) -> 2.派发Implementer -> 3.等待完成
    -> 4.统一审查 -> 4.1.反馈记录(被动)
    -> 5.通过? -否-> P0-P1:修复->返回4 / P2+:记录技术债务 -是-> 6.标记完成
```

## TDD 模式流程（默认，除非代码属于豁免类型或用户显式跳过）

```
1.加载Skill -> 1.2.验收预审(条件) -> 1.5.TDD预处理(RED) -> 2.Implementer(含测试上下文)
    -> 2.5.GREEN验证 -> 4.统一审查 -> 4.1.反馈记录(被动) -> 5.5.REFACTOR(可选) -> 6.完成
```

---

## 步骤详解

### 步骤 1：Lead 预提取规范上下文

Lead 读取 `cc-java-backend/SKILL.md`，按任务关键词按需加载模块（参考 `resources.md` 第三章路由表），**提取规范要点后嵌入 subagent prompt**。禁止让 subagent 自行调用 Skill 加载规范。

#### 1.0.1 Java 项目首任务检测（自动触发）

当任务涉及 **新建 Java 项目骨架** 或 **新建模块包结构** 时，自动执行：
1. 读取 `cc-java-backend/standards-quickref.md` 的"分层架构"和"包名与 DTO"章节
2. 将包名规范（`cn.caijiajia.xxx.*`）、DTO 目录规范（`req/`、`resp/`）嵌入 Implementer prompt 的 CONVENTIONS 字段
3. 触发关键词：`新建项目`、`骨架`、`scaffold`、`初始化`、`new module`

### 步骤 1.2：验收清单预审（条件触发）

> **触发条件**：task.acceptance_criteria 数量 ≥ 3 **或** task.estimated_loc ≥ 100。不满足则跳过，直接进入步骤 1.5。

**目的**：在编码前让 Lead 验证 AC 的可测性和完整性，避免"写完才发现方向错了"的返工。

**流程**：

1. Lead 从 task 的 `acceptance_criteria` 生成验收检查清单：

```markdown
## 验收检查清单（步骤 1.2 生成）

| # | AC 条目 | 验证方式 | 边界条件 | 可测性 |
|---|---------|---------|---------|--------|
| 1 | {AC描述} | test / manual / log | {边界条件列表} | ✅ / ⚠️ 需澄清 |
```

2. **可测性检查**：
   - ✅ 可自动测试 → 正常继续
   - ⚠️ 模糊/不可测 → Lead 标注原因，降级为手动验证或请求用户澄清
   - 所有 AC 均 ⚠️ → 阻断，请求用户补充验收标准

3. **边界条件补充**：Lead 为每个 AC 补充至少 1 个边界条件（null/empty/max/并发等）

4. **传递**：清单附加到 Implementer prompt 的 `ACCEPTANCE_CHECKLIST` 字段

### 步骤 1.5：TDD 预处理（默认执行，豁免类型跳过）

#### 1.5.1 创建测试文件

```java
@Slf4j
public class AuthServiceTest extends BaseMock {
    @InjectMocks private AuthService authService;
    @Mock private UserRepository userRepository;
    @Mock private JwtService jwtService;

    @Test
    public void shouldAuthenticateWithValidCredentials() {
        // Given
        when(userRepository.findByUsername("admin")).thenReturn(Optional.of(buildUser()));
        // When
        String token = authService.authenticate("admin", "password");
        // Then
        assertNotNull(token);
        verify(jwtService).generateToken(any());
    }

    @Test
    public void shouldThrowExceptionWhenPasswordInvalid() {
        when(userRepository.findByUsername("admin")).thenReturn(Optional.of(buildUser()));
        assertThrows(AuthenticationException.class,
            () -> authService.authenticate("admin", "wrong_password"));
    }

    private User buildUser() { /* 测试数据工厂方法 */ }
}
```

#### 1.5.2 RED - 运行测试（验证失败）

```bash
mvn test -Dtest=AuthServiceTest -pl {module}
# 预期：测试失败（方法不存在）。测试通过则说明测试有问题，需修正。
```

> **编译失败降级**：若因模块内其他无关文件编译错误导致 `mvn test` 失败，提示用户：
> `"⚠️ 模块存在无关文件编译错误，建议在 IDEA 中右键运行 {TestClass} 验证"`
> 详细降级策略见 `cc-tdd/workflows.md` → 编译失败降级策略

#### 1.5.3 准备实现上下文

Lead **必须**将以下字段填入 Implementer prompt 的 `TDD_MODE` 上下文合约段（见 `prompts.md:107-118` 选填上下文表）：

| 字段 | 值 | 来源 |
|------|------|------|
| `TDD_MODE.tdd_mode` | `true` | Lead 本步骤激活 |
| `TDD_MODE.test_first` | `true`（Java Service/工具类/Bug Fix） / `false`（其他）| 见 cc-tdd 决策表 |
| `TDD_MODE.test_file_path` | 步骤 1.5.1 创建的测试文件绝对路径 | Lead 本步骤产出 |

**契约铁律**：未填充 `test_file_path` 时 Implementer 变体 A 无法执行（会走变体 B 免测试模式）。Lead 漏填即破坏 TDD 流程。

同时在 prompt 的自然语言描述段向 Implementer 说明："测试文件已创建于 {test_file_path}，当前状态 RED，你的职责是最小实现使其通过"。

### 步骤 2：派发 Implementer Subagent

读取 `prompts.md` 第一章 Implementer 提示词，填充模板变量（含步骤 1.5.3 的 `TDD_MODE` 字段）后派发：

```
Task(
  subagent_type: "cc-cw-implementer",
  max_turns: 10,
  prompt: "{完整的 implementer 提示词}",
  description: "实现 {任务名称}"
)
```

### 步骤 2.5：GREEN - 验证测试通过（仅 TDD 模式）

```python
result = run_tests()
if result.all_pass:
    goto 步骤3
else:
    修复次数 += 1
    if 修复次数 > 3:
        AskUserQuestion("测试仍未通过，是否需要人工介入？")
    else:
        Task(subagent_type: "cc-cw-implementer", max_turns: 10, prompt: "以下测试失败，请修复：\n{错误信息}", description: "修复测试失败")
        goto 步骤2.5
```

### 步骤 3：等待实现完成

子 agent 有问题 -> 传递给用户澄清。实现完成 -> 记录报告，进入审查。

### 步骤 4：统一审查（Unified Review）

读取 `prompts.md` 第二章 Unified Reviewer 提示词，派发审查：

```
Task(
  subagent_type: "cc-cw-unified-reviewer",
  max_turns: 8,
  prompt: "{完整的 unified reviewer 提示词}",
  description: "统一审查 {任务名称}"
)
```

```python
if status == "PASS": goto 步骤4.5
else:
    P0-P1 高置信度 -> 必须修复 -> 修复后 goto 步骤4
    P2+ 建议级 -> 记录到技术债务（.claude/tech-debt.md），不阻塞
    最多 3 次重试，超过请求人工介入
```

#### 步骤 4.1：审查反馈记录（被动触发）

> **触发条件**：用户对审查结论表示异议时。包括：驳回 P0-P1 阻断（"这个不是问题"）、主动采纳 P2+ 建议（"这个确实要改"）、事后报告漏检（"上线后发现 bug，审查没查出来"）。
> **不主动询问**：Lead 不在审查后主动问用户"你觉得审查结果如何"，避免打断流程。仅在用户主动反馈时触发。

**流程**：
1. 识别用户反馈类型：`adopted`（采纳建议）/ `rejected`（驳回阻断）/ `missed_bug`（漏检）
2. 记录到 `cc-code-reviewer/calibration-examples.md` 的"审查反馈日志"表
3. 格式：`| {日期} | {task_id} | {reviewer_score} | {user_action} | {dimension} | {reason} |`

**数据流**：反馈记录 → 校准迭代循环 → prompt/样本更新 → 审查质量提升

#### 评分追踪（量化评分基础设施就绪后启用）

当 Unified Reviewer 返回包含 `score` 字段的输出时：

1. **记录 baseline**：首次审查的 `score.weighted_total` 作为 baseline
2. **重试对比**：如果是重试（retry_count > 0），对比 `current_score vs baseline_score`
   - current < baseline → 输出 `[REGRESSION] 修复引入新问题，请检查变更`
   - current >= baseline → 正常继续
3. **评分历史传递**：评分记录附加到审查报告，供 planner REVIEW 三轮 QA 参考

> 注意：此功能仅在审查 prompt 包含"综合评分"要求时生效。否则不输出 score 字段，此段逻辑自动跳过。

### 步骤 4.5：REFACTOR（仅 TDD 模式，可选）

代码重复/方法过长/命名不清晰 -> 执行重构。**原则**：只改结构不改行为，每次小改动后运行测试，失败立即回退。

### 步骤 5：标记完成

更新 TaskUpdate，输出完成报告。

---

## 修复循环控制

统一审查最大 3 次重试。仅 P0-P1 阻断问题触发重试，P2+ 记录技术债务不阻塞。超过 3 次则报告用户请求人工介入。详见第四章。

---

# 三、并发执行工作流

> 多个独立任务的并发执行策略

## 工作流程

```
任务列表
    |
1. 依赖分析 -> 分组
    |
2. 对每个组：
    |- 并发派发 Implementer
    |- 等待全部完成
    |- 并发派发 Unified Reviewer
    |- 处理审查结果（P0-P1 修复，P2+ 记录技术债务）
    |- 创建保存点提交
    |
3. 进入下一组
    |
4. 所有组完成 -> 汇报结果
```

---

## 步骤详解

### 步骤 1：依赖分析与分组

```python
def analyze_dependencies(tasks):
    groups = []
    remaining = tasks.copy()
    completed = set()
    while remaining:
        current_group = [t for t in remaining if all(d in completed for d in t.dependencies)]
        if not current_group: raise Error("发现循环依赖")
        for t in current_group:
            remaining.remove(t); completed.add(t.id)
        groups.append(current_group)
    return groups
```

### 步骤 1.5：文件冲突检测（并发模式必做）

在派发 Implementer 前，检查同组任务的目标文件是否重叠：

```
file_map = {}  # file → [task_ids]
for task in current_group:
    for file in task.target_files:
        file_map.setdefault(file, []).append(task.id)

conflicts = {f: ids for f, ids in file_map.items() if len(ids) > 1}
if conflicts:
    # 冲突文件的任务降级为顺序执行
    # 在 Implementer prompt 中标注"仅修改 L{start}-L{end} 行范围"
```

### 步骤 2：并发执行组内任务

**2.1** 在单个消息中发送多个 Task 调用（并发派发 Implementer）。冲突任务顺序化。
**2.2** 收集结果，失败任务单独处理
**2.3** 并发派发 Unified Reviewer
**2.4** 处理审查结果（P0-P1 修复阶段顺序执行避免并发冲突，P2+ 记录技术债务不阻塞）

### 步骤 2.6：保存点提交

当前组全部审查通过后创建保存点：

```bash
git add {组内所有修改的文件}
git commit -m "wip: 完成组{N} - {组描述}"
```

**用途**：回退（`git reset --soft savepoint-group-{N-1}`）、中断恢复、最终整理提交

### 步骤 3-4：循环执行 + 汇报

当前组完成+保存点提交 -> 下一组。所有组完成后输出汇报：

```markdown
## 并发执行完成报告

### 执行统计
| 指标 | 数值 |
|------|------|
| 总任务数 / 执行组数 / 成功 / 失败 / 修复次数 | {values} |

### 任务详情
| # | 任务 | 状态 | 审查结果 | 备注 |
|---|------|------|---------|------|
```

---

## 并发控制策略

```python
MAX_CONCURRENT_TASKS = 10  # 同时最多派发10个子agent

# 冲突检测：同一文件被多个任务修改 -> 顺序执行
def check_file_conflicts(tasks):
    file_to_tasks = {}
    for task in tasks:
        for file in task.target_files:
            if file in file_to_tasks: return (file_to_tasks[file], task)
            file_to_tasks[file] = task
    return None
```

---

## 示例：实现订单服务

```
组1（并发）：Repository.findById() + save()
    -> 审查 -> git commit "wip: 完成组1 - OrderRepository CRUD"

组2（并发）：Service.create() + query()
    -> 审查 -> git commit "wip: 完成组2 - OrderService 业务逻辑"

组3（顺序）：Controller
    -> 审查 -> git commit "wip: 完成组3 - OrderController API"
```

---

## 错误处理

| 场景 | 处理 |
|------|------|
| 单任务失败 | 标记失败，继续其他任务 |
| 审查 3 次失败 | `git reset --soft savepoint-group-{N-1}` + 提示用户（详见第四章） |
| 整组失败 | 回退保存点 + 提示用户 |
| 超时（5分钟） | 标记 timeout |

---

# 四、审查结果处理 — 双模式

> 审查返回后的闭环处理。支持两种模式：Fix Loop（降级选项）和 Strategy Evolution（默认）。

**审查接收原则**：对 reviewer 的每条意见，必须先评估技术合理性再决定是否修改。禁止无理由接受所有意见——reviewer 可能缺少上下文或判断有误，此时应附理由推回而非盲目修复。

## 模式选择

```
审查结果返回
  ├─ PASS → 完成
  ├─ BLOCKED/WARN
  │    ├─ 首次审查（无 ROUND_CONTRACT）→ 模式 A（Fix Loop，快速尝试）
  │    │    Fix Loop 失败后（第 2 轮），Lead 注入 ROUND_CONTRACT → 进入模式 B
  │    ├─ Reviewer 未输出任何 insight → 模式 A（无 insight 驱动的 evolution 是空转）
  │    ├─ 用户 --fix-only 或"直接修" → 模式 A
  │    └─ 其他情况（默认）→ 模式 B（Strategy Evolution）
```

---

## 模式 A：Fix Loop（首次审查 + 降级选项）

### 数据契约

> 数据结构定义见 `shared-rules/data-contracts.md` 中的 `code-reviewer → code-writer` 字段。

### 重试策略

| 审查次数 | 处理方式 |
|---------|---------|
| 第 1 次不通过 | 根据 fix_suggestion 自动修复 |
| 第 2 次不通过 | 自动修复 + 扩大上下文 + 检查是否应升级到模式 B |
| 第 3 次不通过 | 回退保存点 + 人工介入 |

### 修复执行流程

1. 解析：P0/P1 → must_fix，其他 → optional_fix
2. 修复：读取 fix_suggestion → 定位文件 → 应用修复 → 重新测试
3. 重新审查：传递 retry_count + 1

**原则**：P0/P1 不得跳过 | 记录修复历史 | 第 2 次扩展上下文 | 第 3 次立即升级

### 人工介入提示模板

```markdown
**审查循环超过 3 次，需要人工介入**

| 问题 | 严重度 | 修复尝试 | 最后失败原因 |
|------|--------|---------|-------------|
| {issue_description} | {severity} | {attempts} | {last_failure_reason} |

请选择：
- [ ] 继续修复（提供新的修复思路）
- [ ] 切换到 Strategy Evolution 模式（从策略层面重新生成）
- [ ] 跳过此问题（记录到技术债务）
- [ ] 取消任务
```

---

## 模式 B：Strategy Evolution Loop（opt-in）

> 详细协议见 `shared-rules/evolution-loop-protocol.md`。本章定义 code-writer 内的具体执行流程。

### 激活与初始化

```yaml
# 首次激活时，Lead 创建 $STARK_SESSION_DIR/strategy.yaml
domain: "coding"
task_id: "{当前任务ID}"
amendments: []
insights_log: []
round_contracts: []
convergence:
  current_round: 1
  scores: []
  status: "evolving"
```

### 单轮执行流程

```
Round N:

1. Round Contract 生成（Lead 执行）
   ├─ 分析 insights_log，选择 frequency 最高且未 resolved 的 dimension 作为 focus
   ├─ 生成 weight_overrides（focus 维度 × 1.5，其余 1.0）
   ├─ 收集 amendments[] 中 validated=false 的 rule
   └─ 写入 strategy.yaml 的 round_contracts[]

2. Implementer 派发
   ├─ 注入 STRATEGY_AMENDMENTS（从 round_contract.strategy_amendments 提取）
   ├─ Round 1：正常派发
   ├─ Round N>1 且上轮 score < 3.0：prompt 中标注"从头生成，不要在上轮基础上 patch"
   └─ Round N>1 且上轮 score >= 3.0：prompt 中标注"在上轮基础上改进"

3. Reviewer 评审
   ├─ 注入 ROUND_CONTRACT（含 weight_overrides + focus_dimension + rationale）
   ├─ 标准审查输出 + Insights 章节
   └─ 评分按 weight_overrides 计算 weighted_total

4. Insight Extraction（Lead 执行）
   ├─ 解析 Reviewer 的 insights[]
   ├─ 与 insights_log 比对：新 insight → frequency=1 | 已有 → frequency+1 | 消失 → resolved
   └─ 更新 strategy.yaml

5. Strategy Evolution（Lead 执行）
   ├─ 筛选 frequency ≥ 2 的 insight → 生成 amendment
   ├─ 已 resolved 的 insight 对应 amendment → validated=true
   └─ 更新 strategy.yaml

6. Convergence Check
   ├─ scores[] 追加本轮 weighted_total
   ├─ max_rounds（5）达到 → status="max_rounds"，输出最佳轮次产出
   ├─ 连续 2 轮 score 提升 < 5% → status="converged"
   ├─ 连续 2 轮无新 insight → status="converged"
   └─ 否则 → 继续 Round N+1
```

### 收敛后输出

```markdown
## Strategy Evolution 完成

**状态**：{converged | max_rounds}
**最佳轮次**：Round {N}（score: {best_score}）
**总轮次**：{total_rounds}

### 累积策略修正（可考虑毕业为持久规则）
| # | 规则 | 来源 insight | 置信度 | 已验证 |
|---|------|-------------|--------|--------|
| 1 | {rule} | {dimension}: {pattern} | {confidence} | {validated} |

### 未解决的 Insights（需人工决策）
| # | 维度 | 模式 | 出现次数 |
|---|------|------|---------|
| 1 | {dimension} | {pattern} | {frequency} |

**建议**：置信度=high 且已验证的 amendment 可写入 SKILL.md gotchas 或 shared-rules 成为持久规则。
```

### 策略毕业提示

Evolution loop 结束时，Lead 检查是否有满足毕业条件的 amendment（confidence=high + validated=true），如有则提示用户：

```markdown
以下策略修正已被验证有效，是否写入持久位置？
| 规则 | 建议位置 |
|------|---------|
| {rule} | cc-code-writer/SKILL.md gotchas 第 {N} 条 |
```

---

# 五、TDD 模式工作流

> **TDD 原则、验证规则、触发条件、反模式清单的唯一真实来源**：`cc-tdd/SKILL.md` 和 `cc-tdd/workflows.md`。
>
> 本章仅说明 code-writer 的 TDD **编排流程**（何时派 subagent、重试逻辑）。详细步骤见第二章步骤 1.5/2.5/4.5。

## TDD 模式激活（默认开启）

**TDD 默认对所有可测试代码启用**，仅以下情况跳过：
- 用户显式说"不需要测试"/"跳过TDD"/"不用TDD"
- 代码属于豁免类型：DTO/Config/Entity/Enum/Model/Constants/Common 等纯数据类
- 纯配置修改（如 application.yml、pom.xml）

激活流程：

1. 读取 `cc-tdd/SKILL.md` 获取 TDD 原则和 test_first 决策表
2. 按需读取 `cc-tdd/workflows.md` 获取 RED/GREEN/REFACTOR 详细规则
3. 创建 `.claude/tdd-session-active` 文件激活 Hook 守护
4. 按步骤 1.5/2.5/4.5 执行 RED-GREEN-REFACTOR 编排
5. 任务完成后删除 `.claude/tdd-session-active`
