# 工作流合集

---

# 一、RED-GREEN-REFACTOR 详细流程

> TDD 三阶段循环的详细执行规则

## RED 阶段（写失败测试）

### 流程

1. 根据需求确定**一个**行为点（Vertical Slicing，一次一个）
2. 编写测试方法，命名描述业务行为（`should{行为}When{条件}`）
3. 使用 Given-When-Then 结构组织测试代码
4. 运行测试，**确认失败**

### 验证标准

| 检查项 | 预期 |
|--------|------|
| 测试是否失败 | **必须失败**（编译错误或断言失败） |
| 失败原因 | 方法不存在 / 返回值不符合预期 |
| 测试是否只测一个行为 | 一个测试方法只验证一个行为点 |

### RED 阶段禁止

- ❌ 测试通过（说明测试没有验证新行为，需修正测试）
- ❌ 同时写多个测试（违反 Vertical Slicing）
- ❌ 测试名称不描述行为（如 `test1`、`testMethod`）

### RED 运行命令

```bash
# 单个测试类
mvn test -Dtest=XxxServiceTest -pl {module}

# 单个测试方法
mvn test -Dtest=XxxServiceTest#shouldRejectWhenStockInsufficient -pl {module}
```

### RED 证据存档

> 成功标准第 2 条"RED 阶段测试确实失败（有失败日志证据）"的取证协议。SKILL.md 成功标准直接引用本节。

**存储位置**：`{workspace}/tdd-evidence/{slice}-red.log`

- `{workspace}`：当前 Task workspace 根目录（cc-work-mode 派发时由 executor 提供；单独使用时为项目根）
- `{slice}`：Vertical Slice 标识，通常取测试方法名的 camelCase，如 `calculateDiscount`、`rejectWhenStockInsufficient`

**命名约定**：

| 文件 | 内容 |
|------|------|
| `{slice}-red.log` | RED 阶段 `mvn test` 的失败输出（完整 stack trace + 失败断言） |
| `{slice}-green.log`（可选） | GREEN 阶段通过后的 `mvn test` 输出，用于对比 |

**生成命令**：

```bash
mkdir -p {workspace}/tdd-evidence
mvn test -Dtest=XxxServiceTest#shouldRejectWhenStockInsufficient -pl {module} \
  2>&1 | tee {workspace}/tdd-evidence/rejectWhenStockInsufficient-red.log
# 期望退出码非 0（BUILD FAILURE），退出码 0 说明 RED 阶段测试未失败，需修正测试
```

**审查阶段如何验证**：

- code-writer 统一审查（workflows.md 第二章 步骤 4）会 `grep -l "BUILD FAILURE\|AssertionError" {workspace}/tdd-evidence/*-red.log` 确认每个 slice 至少一条失败证据
- 若 `{workspace}/tdd-evidence/` 目录不存在或无 `-red.log`，审查阶段报告"RED 证据缺失"并要求补齐
- 豁免情形：DTO/配置/枚举等 `tdd-guard` 豁免路径任务无需生成证据

**清理**：Task 完成后证据日志随 workspace 一起清理；持久化需求由调用方显式 copy 到 artifacts 目录。

### 编译失败降级策略

当 `mvn test -Dtest=` 因模块内**其他文件**编译错误而失败时（非本次修改的文件），按以下顺序降级：

```bash
# 1. 优先：只编译测试类及其直接依赖（跳过无关文件的编译错误）
mvn test -Dtest=XxxServiceTest -pl {module} -Dmaven.compiler.failOnError=false

# 2. 若仍失败：提示用户在 IDEA 中右键运行
#    IDEA 的增量编译可以绕过无关文件的编译错误
```

**判断规则**：
- 编译错误出现在**本次修改的文件** → 正常修复，不降级
- 编译错误出现在**其他无关文件** → 降级，并告知用户：
  `"⚠️ 模块存在无关文件编译错误，建议在 IDEA 中右键运行 {TestClass} 验证"`

---

## GREEN 阶段（最小实现）

### 流程

1. 阅读失败的测试，理解需要实现什么行为
2. 写**最小代码**让测试通过（不多写一行）
3. 运行测试，**确认通过**

### 验证标准

| 检查项 | 预期 |
|--------|------|
| 测试是否通过 | **必须通过** |
| 实现是否最小 | 没有测试未覆盖的逻辑分支 |
| 是否引入新依赖 | 仅引入测试要求的依赖 |

### GREEN 阶段禁止

- ❌ 提前实现"未来可能需要"的功能
- ❌ 添加测试未覆盖的错误处理
- ❌ 重构代码（留给 REFACTOR 阶段）

### GREEN 失败重试

```
测试失败 → 分析失败原因 → 修复实现（不改测试）→ 重新运行
最多重试 3 次，超过则标记阻塞，请求人工介入
```

---

## REFACTOR 阶段（优化结构）

### 触发条件

GREEN 通过后，检查以下任一条件：
- 代码重复（两处以上相同逻辑）
- 方法过长（> 20 行）
- 命名不清晰
- 违反 SOLID 原则

**如果没有重构需求，跳过此阶段。**

### 流程

1. 识别重构点
2. 每次只做**一个小改动**
3. 改完立即运行测试
4. 测试通过 → 继续下一个改动
5. 测试失败 → **立即回退**本次改动

### REFACTOR 阶段禁止

- ❌ 改变行为（只改结构）
- ❌ 一次大规模重构（小步前进）
- ❌ 测试失败时继续重构

---

## 循环节奏

```
一个 Slice 的完整循环：

  RED → 运行测试（失败✓）
    → GREEN → 运行测试（通过✓）
      → REFACTOR（可选）→ 运行测试（通过✓）
        → 提交（wip: TDD-{slice描述}）
          → 下一个 Slice
```

---

# 二、测试反模式清单

> 编写测试时必须避免的反模式

## 结构反模式

| 反模式 | 说明 | 正确做法 |
|--------|------|---------|
| **先实现后补测试** | 失去 TDD 核心价值，测试容易成为实现的镜像 | 严格 RED-GREEN-REFACTOR 顺序 |
| **测试实现细节** | 绑定内部实现，重构时大量测试失败 | 测试输入→输出行为 |
| **过度 Mock** | Mock 了被测类的内部方法 | 只 Mock 外部依赖 |
| **巨型测试** | 一个测试验证多个行为 | 一个测试一个行为 |
| **测试间依赖** | 测试 B 依赖测试 A 的执行结果 | 每个测试独立，自包含 |

### 反模式：先写实现再补测试

Bad:
```java
// 先写了 Service 实现，再回来补测试——只验证了 happy path，断言弱
@Test
void testCreate() {
    service.create(dto);
    verify(repository).save(any());  // 只验证调用，不验证结果
}
```

Good:
```java
// RED 阶段先写测试，定义期望行为，再去实现
@Test
void shouldCreateAndReturnId() {
    CreateDto dto = new CreateDto("test");
    Long result = service.create(dto);
    assertThat(result).isNotNull();
    assertThat(repository.findById(result)).isPresent();  // 验证真实持久化
}
```

### 反模式：测试 Mock 行为而非真实行为

Bad:
```java
// 测试绑定了内部实现细节，重构后测试必然失败
@Test
void shouldNotify() {
    service.process(order);
    verify(notifier).send(eq("SMS"), eq(order.getPhone()), anyString());
    verify(repository).updateStatus(order.getId(), "NOTIFIED");
}
```

Good:
```java
// 测试只关心可观测的业务结果，不关心内部如何编排
@Test
void shouldMarkAsNotifiedAfterProcess() {
    service.process(order);
    Order updated = repository.findById(order.getId());
    assertThat(updated.getStatus()).isEqualTo("NOTIFIED");
    // 通知是否真的发出，通过集成测试或 stub 收件箱验证
}
```

## 命名反模式

| 反模式 | 示例 | 正确做法 |
|--------|------|---------|
| 技术命名 | `testCalculate` | `shouldCalculateDiscountForVipUser` |
| 编号命名 | `test1`, `test2` | 描述具体行为 |
| 否定命名 | `testNotFail` | `shouldSucceedWhenInputValid` |

## Mock 反模式

| 反模式 | 说明 | 正确做法 |
|--------|------|---------|
| Mock 值对象 | Mock 了 DTO/Entity | 直接 new 或用工厂方法 |
| Mock 被测类 | `@Spy` 被测类部分方法 | 重新设计类结构 |
| 验证 getter | `verify(obj).getName()` | 用 assertThat 验证结果 |
| when-thenReturn 链过长 | 超过 3 层 Mock 链 | 简化依赖关系或提取 helper |

## Java 特有反模式

| 反模式 | 说明 | 正确做法 |
|--------|------|---------|
| 不用 @ExtendWith | 用 @RunWith(MockitoJUnitRunner) | 用 JUnit5 的 @ExtendWith(MockitoExtension.class) |
| 手动 new Mock | `Mockito.mock(Foo.class)` 在每个方法里 | 用 @Mock 注解 + @InjectMocks |
| 忽略异常测试 | 不测异常路径 | 用 assertThrows 验证异常 |
| 硬编码测试数据 | 数字/字符串散落在测试中 | 提取常量或工厂方法 |

---

# 三、与 code-writer / work-mode 联动协议

## 联动模式

cc-tdd 提供**规则**，code-writer / work-mode 提供**编排**。

### 与 code-writer 联动

当 code-writer 进入 TDD 模式（用户要求 TDD 或任务含 `test_first`）：

1. code-writer 读取 `cc-tdd/SKILL.md` 获取 TDD 原则和 test_first 决策表
2. code-writer 按需读取本文件获取 RED/GREEN/REFACTOR 详细规则
3. code-writer 按自身 workflows.md 步骤 1.5/2.5/4.5 编排执行
4. code-writer 的 Implementer subagent prompt 中嵌入 TDD 验证标准

**职责边界**：

| 由 cc-tdd 定义 | 由 code-writer 执行 |
|-------------------|-------------------|
| RED/GREEN/REFACTOR 规则 | subagent 派发时机和顺序 |
| test_first 决策表 | 测试文件创建和运行 |
| 验证标准（何为合格的 RED/GREEN/REFACTOR） | savepoint 管理和审查失败回退 |
| **GREEN 失败重试规则（最多 3 次，本文件为权威源）** | **重试的执行编排（何时触发、如何调度）** |
| 反模式清单 | 审查失败回退 |
| Java 测试规范（命名/Mock/断言） | 测试代码的实际编写 |

### 与 work-mode 联动

work-mode 的 EXECUTE 阶段执行带 `test_first` 的任务时：

1. work-mode 读取 `cc-tdd/SKILL.md` 获取 TDD 原则
2. work-mode 在任务 prompt 中嵌入 TDD 规则摘要
3. 每个并发 agent 按 RED-GREEN-REFACTOR 循环执行

### 与 planner 联动

planner 在 PLAN 阶段为任务标记 `test_first` 时：

1. 引用 cc-tdd 的 test_first 决策表判断哪些任务需要 TDD
2. 在 {workspace}/plan.md 任务条目中设置 `test_first: { test_file, test_cases }`（workspace 路径见 shared-rules/session-workspace.md）
3. 不自行维护 test_first 决策规则的副本

---

# 四、Hook 激活与停用

## tdd-guard.js 工作原理

`tdd-guard.js` 是 PreToolUse Hook，拦截 Write|Edit 工具调用。

### 激活流程

```
cc-tdd Skill 被激活
  → Claude 创建 .claude/tdd-session-active 文件（内容：时间戳）
  → 后续 Write/Edit 调用触发 tdd-guard.js
  → Hook 检查被编辑文件是否有对应测试
```

### 停用流程

```
TDD 任务全部完成 + 代码已提交
  → Claude 删除 .claude/tdd-session-active 文件
  → Hook 检测不到激活文件，自动跳过
```

### Hook 检查逻辑

```
输入：tool_input.file_path

1. .claude/tdd-session-active 不存在？→ 放行
2. 文件不匹配 src/main/java/**/*.java？→ 放行
3. 文件匹配豁免路径？→ 放行
   豁免：**/dto/** | **/config/** | **/enums/** | **/entity/** | **/model/** | **/constants/** | **/common/**
3.5. 内容豁免：纯数据类？→ 放行
   检测 @Data/@Getter/@Setter/@Builder/@NoArgsConstructor/@AllArgsConstructor 注解
   且无业务方法（排除 get/set/is/hashCode/equals/toString/builder 等标准方法）
4. 推导测试文件路径：
   src/main/java/a/b/Foo.java → src/test/java/a/b/FooTest.java
5. 测试文件存在？→ 放行
6. 测试文件不存在 → 输出警告：
   "⚠️ TDD Guard: {Foo.java} 没有对应测试文件 {FooTest.java}，TDD 模式下请先写测试"
```

### 注意事项

- Hook 通过 `hookSpecificOutput.additionalContext` **注入 TDD 提醒**到对话，不 `deny` 不硬阻止；模型可能忽略提醒，因此 Lead 仍需在审查环节核查"测试是否先行"
- 提醒消息格式：`🧪 TDD 提醒: {Foo.java} 没有对应测试文件 {FooTest.java}（或测试文件为空）。建议先写测试再写实现。`
- Hook 无法在 skill 管理仓库（my_claude）测试，需在目标 Java 项目中验证
- 豁免路径可根据目标项目约定调整
