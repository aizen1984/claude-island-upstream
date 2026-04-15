# Java 后端开发规范速查

> 规则名 + 一句话说明 + 详见链接。完整规范含代码示例见对应文件。

---

## 分层架构

Controller 只注入 Service，Service 只注入 Repository，Repository 继承 BaseRepository，禁止跨级注入和反向依赖。Controller 层薄（参数接收 + 校验 + 委托 Service + 包装返回），禁止包含业务逻辑，所有业务逻辑下沉到 Service。
> 详见 standards-core.md 一、分层架构与代码结构 (§1.2) + 三、API 设计规范 (§3.1)

## 包名与 DTO

包名必须 `cn.caijiajia.xxx.*`，Request DTO 放 `req/`，Response DTO 放 `resp/`，禁止统一放 `dto/`。
> 详见 standards-core.md 一、分层架构与代码结构 (§1.3, §1.4)

## 命名规范

类名后缀：Controller / Service / Repository / Mapper / Req / Resp；方法名：getById / list / create / update / delete / batch*。优先完整单词，禁止自造缩写。
> 详见 standards-core.md §1.5

## 异常处理

客户端错误用 `CjjClientException(4xx, msg)`，服务端错误用 `CjjServerException(500, msg, e)`。禁止吞掉异常、状态码混用、暴露堆栈。
> 详见 standards-core.md §2.3

## 可读性规则

多条件判断封装为 `isXxx()` / `hasXxx()` / `canXxx()`；方法 <= 50 行；嵌套 <= 3 层；public 方法必须完整注释。查询逻辑封装到 Repository 语义方法；Guard Clause 早返回减少嵌套；枚举比较和复合条件提取为辅助方法。
> 详见 standards-core.md §2.1, §2.1.1, §2.2

## 日志规范

使用 `@Slf4j` + 占位符，禁止字符串拼接。异常必须带 Throwable。禁止循环内详细日志和记录敏感信息。
> 详见 standards-core.md §2.5

## 工具类规范

使用 `@UtilityClass`，所有方法处理 null 输入、无副作用。
> 详见 standards-core.md §2.4

## 禁止魔法值

禁止未命名字面量（数字/字符串），必须提取为常量或枚举。本类独用→`private static final`，多类共享→`constants/`包，有限枚举集→枚举类。`0/1/-1/""`除外。
> 详见 standards-core.md §2.6

## 字符串/枚举比较

字符串和枚举比较必须使用 `equals()`，常量在前（`STATUS.equals(var)`），禁止 `==`。
> 详见 standards-core.md §2.1

## 金额精度

金额计算禁止 `double`/`float`，必须使用 `BigDecimal`，构造用 String 参数（`new BigDecimal("0.1")`）。禁止 `BigDecimal(double)` 构造。
> 详见 standards-core.md §2.1

## 依赖注入

禁止 `@Autowired` 字段注入，使用 `@RequiredArgsConstructor` 构造器注入。
> 详见 standards-core.md §1.2

## MyBatis 参数安全

`#{param}` = PreparedStatement 参数绑定（**安全**，不要误报为注入）；`${param}` = 字符串拼接（**危险**，需确认参数来源可信）。
> 详见 standards-core.md §4（数据访问）

## Controller 返回值

禁止返回 `Map<String, Object>`，必须使用 `Result<XxxResp>` 强类型 DTO。弱类型返回值无法校验字段、无法生成 API 文档。
> 详见 standards-core.md §3.1（API 设计）

## 事务规则

必须 `@Transactional(rollbackFor = Exception.class)`；本类调用用 `AopContext.currentProxy()`；事务方法必须 public 非 final；禁止事务中调用外部服务。涉及分布式锁时，锁在事务外层（lock-then-transact），幂等场景用 SET NX EX 替代锁。
> 详见 standards-core.md 五、事务管理与建表规范 (§5.1, §5.2, §5.3)

## 性能红线

列表必须分页 `PageHelper.startPage()`；批量 > 500 用 `Lists.partition` 分批；禁止循环查库（N+1）；禁止 `SELECT *`。
> 详见 standards-core.md §4.8, §4.9, §4.10

## 数据访问

查询用 Condition API；批量插入用 `batchInsert()`；更新用 `updateByCondition()`；分页用 `PageHelper.startPage()` + `PageInfo`。每个 Repository 必备 `fuzzyLike()` 方法。
> 详见 standards-core.md 四、数据访问层规范 (§4.1-§4.10)

## 枚举设计

必须有 `code` 和 `name` 字段，必须提供 `fromCode()` 静态方法，禁止使用 `ordinal()`。
> 详见 patterns-design.md §1.7

## API 设计

RESTful 风格 GET/POST/PUT/DELETE；分页参数 pageNum 默认 1、pageSize 默认 20、最大 100；参数校验用 JSR-303 注解；返回值用 `Result<T>` 封装。
> 详见 standards-core.md 三、API 设计规范 (§3.1-§3.6)

## 建表审计字段

所有新建表必须包含：creator, updater, created_by, updated_by, created_at, updated_at。
> 详见 standards-core.md §5.3

## 单元测试

继承 `BaseMock`，Given-When-Then 结构，只 Mock 外部依赖，测试数据用 JSON 文件或工厂方法，覆盖正常/边界/异常。
> 详见 standards-infra.md 六、单元测试规范 (§6.1-§6.3)
