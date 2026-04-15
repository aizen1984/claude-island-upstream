---
name: cc-java-backend
description: 提供数禾Java后端编码规范（Spring Boot+MyBatis+BaseRepository+Condition API+事务+分布式锁）。不独立执行开发任务。用于编码规范咨询、代码实现参考，作为底层规范支撑
user-invocable: false
allowed-tools: Read, Grep, Glob
paths: "**/*.java, **/pom.xml"
---

## Gotchas

> 基础陷阱见全局规则 java-backend-standards.md，以下仅列 Skill 专有陷阱。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | CAS 更新和额外字段更新拆成两条 SQL | 第二条无条件 UPDATE 绕过乐观锁保护 | 合并为一条 SQL |
| 2 | `lock()` 后未在 `finally` 中 `unlock()` | 异常时锁永不释放，后续请求全部阻塞 | `finally { if (locked) unlock(); }` |
| 3 | ThreadLocal 未在 `finally` 中 `clear()` | 线程池复用时上下文串号，数据错乱 | `try { init(); doLogic(); } finally { clear(); }` |
| 4 | 枚举用 `ordinal()` 存数据库 | 枚举成员重排后历史数据全部错乱 | 使用显式 `code` 字段 + `fromCode()` |

# 数禾 Java 后端开发规范

> 基于公司实际项目架构抽象的通用开发指南，适用于所有基于 Spring Boot + MyBatis + BaseMapper/BaseRepository 架构的项目

## Overview

**定位**：规范库，可由关键词直接触发，也可被 cc-code-writer / cc-code-reviewer 等隐式依赖加载。

---

## When to Use

- 编写/修改 Java 代码（Controller、Service、Repository、Mapper）
- 设计接口、方法、查询逻辑
- 处理事务、并发、批量操作
- 使用公司框架（Condition API、DistributedLock、ConfPlus）

## When Not to Use

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 系统级架构设计 | cc-design | 本 Skill 是编码规范库，不做架构设计 |
| 任务规划 | cc-planner | 本 Skill 不做任务拆解和规划 |
| 代码审查 | cc-code-reviewer | 本 Skill 提供规范参考，不主动执行审查 |

---

## 协作关系

- **被依赖**: cc-code-writer、cc-code-reviewer、cc-work-mode、cc-design、cc-planner、cc-tdd、cc-api-analyzer（隐式依赖）
- **委托给**: 无（规范库，不主动触发）

> 隐式依赖定义见 `skill-rules.json` 各 skill 的 `implicitDependencies` 字段

---

## 资源加载指导

| 条件 | 加载文件 | 读取范围 | 不加载 |
|------|---------|---------|--------|
| 首次激活（速查） | SKILL.md + `standards-quickref.md` + `patterns-quickref.md` | 全量 | standards-core.md, standards-infra.md, standards-security.md, patterns-design.md, patterns-concurrency.md, templates/* |
| 分层架构 / 代码质量 / API / 数据访问 / 事务 | `standards-core.md` | 按标题定位章节 | standards-infra.md, standards-security.md, patterns-design.md, patterns-concurrency.md, templates/* |
| 单元测试 / MQ / Feign / 定时任务 / OSS / AOP | `standards-infra.md` | 按标题定位章节 | standards-core.md, standards-security.md, patterns-design.md, patterns-concurrency.md, templates/* |
| 安全 / SQL 注入 / XSS / 脱敏 / 鉴权 / 文件上传 / 密钥 / 日志 CRLF | `standards-security.md` | 按标题定位章节（一~七节 + 常见陷阱 Top 8） | standards-core.md, standards-infra.md, patterns-design.md, patterns-concurrency.md, templates/* |
| 设计模式 / SOLID / 策略 / 工厂 / 枚举 / 责任链 | `patterns-design.md` | 按标题定位章节 | standards-core.md, standards-infra.md, standards-security.md, patterns-concurrency.md, templates/* |
| 并发 / 分布式锁 / 线程池 / 限流 / ConfPlus | `patterns-concurrency.md` | 按标题定位章节 | standards-core.md, standards-infra.md, standards-security.md, patterns-design.md, templates/* |
| 代码模板 / CRUD 模板 / Service / Controller | `templates/templates-service-controller.md` | 按标题定位章节 | standards-core.md, standards-infra.md, standards-security.md, patterns-design.md, patterns-concurrency.md |
| 代码模板 / Repository / 异常 / 枚举 / PR 自查 | `templates/templates-repo-exception.md` | 按标题定位章节 | standards-core.md, standards-infra.md, standards-security.md, patterns-design.md, patterns-concurrency.md |
| 遇到需求模糊时 | `shared-rules/inquiry-protocol.md` | 全量 | 所有规范文件 |

---

## 被隐式依赖时的行为

- **接收自**: user（直接查询规范）、其他 Skill（隐式依赖自动加载）
- **委托给**: 无（规范库不委托其他 Skill）
- **隐式依赖**: 无

其他 Skill（code-writer、code-reviewer、work-mode、design、planner、tdd）隐式依赖本规范库时，**不触发完整的 java-backend 流程**，而是由调用方按需提取规范内容：

| 调用方 | 交互方式 | 加载范围 |
|--------|---------|---------|
| **code-writer** | Lead 预提取规范要点，嵌入 Implementer subagent prompt 的 CONVENTIONS 字段 | 按任务关键词路由：事务→standards-core.md 事务章节、并发→patterns-concurrency.md、安全/鉴权/脱敏→standards-security.md |
| **code-reviewer** | 审查时参考核心红线、规范速查表与安全陷阱作为检查依据 | 核心红线 + `standards-quickref.md` + 安全审查场景加载 `standards-security.md` 陷阱 |
| **work-mode** | executor subagent 预加载 java-backend 规范 | 同 code-writer |
| **design** | 技术设计时引用分层架构和命名规范 | standards-quickref.md 分层架构段 |
| **planner** | RESEARCH 阶段识别 Java 约束 | 核心红线 + standards-quickref.md |
| **tdd** | 引用 Java 测试规范 | standards-infra.md 单元测试章节 |
| **cc-api-analyzer** | 接口分析时引用分层架构规范 | standards-quickref.md 分层架构段 |

**关键原则**：调用方负责加载和嵌入，java-backend 不主动推送内容。调用方只加载与当前任务相关的章节，不全量加载。

### 数据契约（被隐式依赖时）

| 维度 | 说明 |
|------|------|
| **输入** | 调用方传入的关键词/场景标签（如"事务""并发""分页"），用于路由到对应规范章节 |
| **输出格式** | 规范要点列表（Markdown 列表或嵌入式代码块），由调用方嵌入 subagent prompt 的 CONVENTIONS 字段 |
| **与 code-reviewer 的区别** | java-backend 提供规范原文（what is right）；code-reviewer 输出违规清单（what is wrong）。两者互补不重叠 |

> 完整字段定义见 `shared-rules/data-contracts.md`

---

## 核心红线

| # | 规则 | ❌ 错误 | ✅ 正确 |
|---|------|--------|--------|
| 1 | **禁止循环查库** | `for(id : ids) { repo.findById(id); }` | `repo.findByIdIn(ids)` |
| 2 | **事务必须 rollbackFor** | `@Transactional` | `@Transactional(rollbackFor = Exception.class)` |
| 3 | **分层注入不可跨级** | Controller 注入 Repository | Controller→Service→Repository |
| 4 | **列表必须分页** | `repo.findAll()` 返回全量 | `PageHelper.startPage(pageNum, pageSize)` |
| 5 | **禁止 SELECT \*** | `SELECT * FROM user` | `SELECT id, name, status FROM user` |
| 6 | **禁止字段注入** | `@Autowired private XxService xx;` | `@RequiredArgsConstructor` + `private final XxService xx;` |
| 7 | **金额用 BigDecimal** | `double price = 0.1 * qty` | `new BigDecimal("0.1").multiply(qty)` |

### 补充安全规则

| 规则 | 安全 | 危险 | 说明 |
|------|------|------|------|
| MyBatis 参数化 | `#{param}`（PreparedStatement 参数绑定） | `${param}`（字符串拼接，SQL 注入风险） | `#{}` 是安全的参数化查询，不要误报为注入风险 |
| Controller 返回值 | `Result<XxxResp>`（强类型 DTO） | `Map<String, Object>`（弱类型，无法校验字段） | 禁止 Controller 返回 Map，必须用 Result<DTO> |

## 用户直接查询规范时的行为

当用户问"代码是否符合规范"或"检查规范违规"时，cc-java-backend 按以下流程执行：
1. 读取目标代码文件
2. 逐条对照核心红线，标注违规项
3. 逐条对照 Gotchas 专有陷阱（CAS 合并 SQL / lock-finally / ThreadLocal / 枚举 ordinal）
4. 对照 `standards-quickref.md` 补充检查
5. 输出违规清单（按严重性排序），格式：`| 文件:行号 | 违反规则 | 严重性 | 建议修复 |`

> 深度九维度审查应使用 cc-code-reviewer，本 Skill 仅做规范对照

> 完整规范速查见 `standards-quickref.md`、`patterns-quickref.md`

---

## FAQ

### Q: Condition API 和 MyBatis-Plus 的 QueryWrapper 有什么区别？
公司内部封装的查询构建器，详见 `standards-core.md` 数据访问章节。

### Q: DistributedLock 和 synchronized 的区别？
`synchronized` 只在单 JVM 内有效，分布式场景必须使用 `DistributedLock`，详见 `patterns-concurrency.md` 分布式锁章节。

### Q: Controller 返回值用什么包装？
统一使用 `Result<T>` 包装：
```java
@GetMapping("/{id}")
public Result<UserVO> getUser(@PathVariable Long id) {
    return Result.success(userService.getById(id));
}
```
