# 资源与参考合集

---

# 一、模式选择详情

> 根据输入自动判断使用哪种执行模式

## 模式判断

```
输入包含 Epic/Story/Task 结构？
  否 -> 模式 A（独立使用，完整流程）
  是 -> 有 2+ 可并行 Epic？
         否 -> 模式 B（Planner 调用，跳过分析）
         是 -> 模式 B（降级，模式 C 已废弃）
```

## 模式 A：独立使用（默认）

用户直接请求"写代码"等。执行：需求分析 -> SOLID 预检 -> 任务执行 -> 汇报

## 模式 B：被 cc-planner 调用

输入包含已拆解任务清单，来自 planner EXECUTE 阶段。跳过需求分析直接执行。

**输入格式**：
```yaml
source: cc-planner
phase: EXECUTE
tdd_mode: true
tasks:
  - id: T1.1.1
    title: "定义 LoginRequest DTO"
    file: "src/main/java/com/xxx/dto/LoginRequest.java"
    estimated_loc: 20
    code_skeleton: |
      @Data
      public class LoginRequest { ... }
  - id: T1.1.2
    title: "实现密码验证逻辑"
    file: "src/main/java/com/xxx/service/AuthService.java"
    estimated_loc: 30
    test_first:
      test_file: "src/test/java/com/xxx/service/AuthServiceTest.java"
      test_cases:
        - name: "shouldAuthenticateWithValidCredentials"
          given: "有效用户名和密码"
          when: "调用 authenticate()"
          then: "返回 JWT token"
```

## ~~模式 C：并行 Worktree 执行~~ （已废弃）

> 模式 C 已废弃。大型并行场景使用模式 B + 并发执行工作流（workflows.md 第三章）替代。满足原模式 C 条件时自动降级为模式 B。

## 与 cc-work-mode 的边界

| 条件 | 选择 |
|------|------|
| 任务数 < 5 / 需要需求分析 | cc-code-writer |
| 任务数 >= 5 且已明确 / 说"干活"/"ralph" | cc-work-mode |

---

# 二、快速参考

> 80% 的问题都能在这里找到答案

## 核心原则速查

| 原则 | 说明 |
|------|------|
| Fresh Subagent | 每个任务新 agent，完成后销毁 |
| Unified Review | P0-P5 全维度一次性审查（P0-P1 阻断 + P2+ 建议） |
| SOLID 预检 | 新建类时：职责单一？扩展需改代码？能 Mock？ |
| TDD | RED -> GREEN -> REFACTOR |
| Ask Before Guess | 不明确就问，不要猜 |

## 审查边界速查

| 场景 | 审查方式 |
|------|---------|
| 文件 <= 2，LOC <= 100 | 统一审查（内置） |
| 文件 > 5 或 LOC > 300 | 必须深度审查（外部 code-reviewer） |
| 安全/支付/核心业务 | 必须深度审查 |

## Subagent 派发速查

```
Implementer:      Task(subagent_type: "cc-cw-implementer",      max_turns: 10, prompt: "...")
Unified Reviewer: Task(subagent_type: "cc-cw-unified-reviewer", max_turns: 8,  prompt: "...")
```

- Implementer 提示词 -> prompts.md 第一章
- Unified Reviewer 提示词 -> prompts.md 第二章

## 并发规则速查

**可以并发**：独立 CRUD、不同实体的 C/S/R、多个独立审查
**必须顺序**：有依赖的任务、同文件多处修改、测试依赖实现

## 常见问题

- **code-writer vs work-mode**：任务 < 5 或需需求分析 -> code-writer；>= 5 且明确 -> work-mode
- **跳过需求分析**：输入含已拆解任务且来自 planner EXECUTE
- **统一审查 vs 九维度**：统一审查是内置（P0-P1阻断+P2+建议）；九维度是独立深度审查（PR/重构）

---

# 三、Skill 路由配置

> 关键词到 cc-java-backend 模块的映射。通过 `Skill(skill: "cc-java-backend")` 加载。

## 路由表

> 路由目标均为 `cc-java-backend` 的 `standards-core.md`、`standards-infra.md`、`patterns-concurrency.md`、`patterns-design.md` 中的具体章节。
> 通过 `Skill(skill: "cc-java-backend")` 加载后，按需阅读对应章节。

### 数据访问

| 关键词 | 目标文件 → 章节 |
|-------|----------------|
| 查询/Condition/筛选/SQL/Mapper/N+1 | `standards-core.md` → 数据访问章节 |
| 批量/500/分批/分页/PageHelper/大文件 | `standards-core.md` → 批量操作与分页章节 |
| 事务/Transaction/@Transactional/AopContext/建表 | `standards-core.md` → 事务管理章节 |

### 并发

| 关键词 | 目标文件 → 章节 |
|-------|----------------|
| 分布式锁/DistributedLock/幂等 | `patterns-concurrency.md` → 分布式锁章节 |
| 线程池/ThreadPool/异步/@Async | `patterns-concurrency.md` → 线程池章节 |
| 限流/ILimiter/QPS | `patterns-concurrency.md` → 限流器章节 |
| 熔断/CircuitBreaker/Resilience4j | `patterns-concurrency.md` → 熔断器章节 |
| ThreadLocal/上下文传递 | `patterns-concurrency.md` → ThreadLocal 章节 |
| ConfPlus/热更新/@AppConf | `patterns-concurrency.md` → ConfPlus 章节 |

### 设计模式

| 关键词 | 目标文件 → 章节 |
|-------|----------------|
| 枚举/Enum/fromCode/状态机/isTerminal | `patterns-design.md` → 枚举设计章节 |
| 策略模式/Strategy/工厂/Factory | `patterns-design.md` → 策略模式章节 |
| 缓存工厂/computeIfAbsent | `patterns-design.md` → 缓存工厂章节 |
| 模板方法/抽象基类/hook | `patterns-design.md` → 模板方法章节 |
| 默认方法/interface default | `patterns-design.md` → 工厂接口章节 |
| 责任链/过滤器链 | `patterns-design.md` → 责任链章节 |

### API / 代码质量 / 其他

| 关键词 | 目标文件 → 章节 |
|-------|----------------|
| Controller/API/RESTful/DTO/Swagger/@Valid | `standards-core.md` → API 设计章节 |
| 异常/CjjClientException/日志/DRY/重试 | `standards-core.md` → 代码质量章节 |
| 分层/架构/包名 | `standards-core.md` → 分层架构章节 |
| AOP/切面/@LogRecord/多数据源/权限 | `standards-infra.md` → AOP 章节 |
| OSS/上传/下载 | `standards-infra.md` → OSS 章节 |
| 单元测试/JUnit/Mockito/Given-When-Then | `standards-infra.md` → 单元测试章节 |

---

## 路由算法

提取关键词匹配路由表。无匹配则参考 `standards-quickref.md` 和 `patterns-quickref.md`。

## 审查时额外加载

| 变更类型 | 额外加载 |
|---------|---------|
| Controller | `standards-core.md` → API 设计章节 |
| Service（事务/查询） | `standards-core.md` → 事务管理章节 / 数据访问章节 |
| 枚举/状态机 | `patterns-design.md` → 枚举设计章节 |
| 并发 | `patterns-concurrency.md` → 全文 |
