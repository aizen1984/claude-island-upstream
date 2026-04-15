# 数禾 Java 后端开发规范（核心）

> 从 standards.md 章节 1-5 蒸馏的公司特有规范。通用知识已删除，完整代码模板见 `templates/templates-service-controller.md` 与 `templates/templates-repo-exception.md`

---

## 一、分层架构与代码结构

### 1.1 多模块项目结构

```
{项目名}/
├── {项目名}-common/              # 公共模块（被其他模块依赖）
│   └── cn.caijiajia.{项目名}.common/
│       ├── req/              # 请求 DTO
│       ├── resp/             # 响应 DTO
│       ├── bo/               # 业务对象
│       ├── dto/              # 数据传输对象
│       ├── vo/               # 值对象
│       └── enums/            # 枚举类
│
├── {项目名}/                      # 主服务模块（Web 应用）
│   └── cn.caijiajia.{项目名}/
│       ├── controller/       # 控制器层
│       ├── services/         # 业务逻辑层
│       ├── repository/       # 数据访问层
│       ├── mapper/           # MyBatis Mapper
│       ├── domain/           # 实体类
│       └── configuration/    # 配置类
│
└── {项目名}-job/                  # 定时任务模块（可选）
    └── cn.caijiajia.{项目名}.job/
```

**模块依赖**：job → 主服务 → common（上层依赖下层，禁止反向）

### 1.2 分层架构与注入规则

```
Controller  →  只能注入 Service（禁止注入 Repository/Mapper）
Service     →  只能注入 Repository、其他 Service（禁止注入 Mapper）
Repository  →  继承 BaseRepository<Domain, Mapper>，自动拥有 baseMapper
Mapper      →  继承 BaseMapper<Domain>
```

### 1.3 包结构

```
cn.caijiajia.{项目名}
├── controller/{模块名}/           XxxController.java
├── services/{模块名}/             XxxService.java
│   ├── config/                   XxxConfPlusConfig.java
│   └── task/executor/
├── repository/{模块名}/           XxxRepository.java
├── mapper/                       XxxMapper.java
├── domain/                       Xxx.java
└── configuration/                Configs.java
```

```java
// ✅ 正确
package cn.caijiajia.myapp.services.order;

// ❌ 错误 - 禁止使用 com
package com.caijiajia.myapp.services;
```

### 1.4 common 模块规则

```
cn.caijiajia.{项目名}.common/
├── req/{模块名}/         # Controller 入参：XxxCreateReq, XxxQueryReq
├── resp/{模块名}/        # Controller 出参：XxxDetailResp, XxxListResp
├── bo/{模块名}/          # 业务对象（Service 间传递）
├── dto/{模块名}/         # 数据传输对象（Service 间传递）
├── vo/{模块名}/          # 值对象（不可变）
├── enums/               # 枚举类（全局共享，不按模块分）
└── constants/           # 常量类（可选）
```

> req/resp 只服务 Controller | Service 间用 Bo/Dto | 枚举直接放 enums/ | 禁止统一 dto/ 目录 | common 无业务逻辑

### 1.5 命名规范

> **优先完整单词**：表名、类名、方法名、变量名优先使用完整单词拼写，避免自造缩写。
> - ✅ `ProjectApplication`、`calculateTotalAmount`
> - ❌ `ProjApp`、`calcTotalAmt`
> - 允许的缩写：行业公认（`id`、`url`、`http`、`dto`、`ip`）+ 团队统一约定的常见缩写（`info`、`config`、`msg`、`param`、`impl`、`util`、`app`、`repo`）

**类命名**：

| 类型 | 后缀 | 示例 |
|------|------|------|
| Controller | Controller | ProjectController |
| Service | Service | ProjectService |
| Repository | Repository | ProjectRepository |
| Mapper | Mapper | ProjectMapper |
| Domain | 无 | Project |
| Request DTO | Req | ProjectCreateReq |
| Response DTO | Resp | ProjectResp |
| 配置类 | Config / ConfPlusConfig | TaskExecutorConfig |
| 枚举 | Type / Status | TaskType, FileStatus |

**方法命名**：

| 操作 | 命名 | 示例 |
|------|------|------|
| 查询单个 | getById / findById | getById(Long id) |
| 查询列表 | list / listBy* | listByProjectId(Long id) |
| 创建 | create / save | create(CreateReq req) |
| 更新 | update / modify | update(Long id, UpdateReq req) |
| 删除 | delete / remove | delete(Long id) |
| 批量操作 | batch* | batchInsert(List list) |
| 统计 | count* | countByStatus(String status) |
| 检查 | exists* / check* | existsByName(String name) |

---

## 二、代码质量规范

### 2.1 可读性规则

多条件判断必须封装为语义化方法：

| 场景 | 是否封装 |
|------|---------|
| 2个以上条件组合 | 必须，封装为 `isXxx()` / `hasXxx()` / `canXxx()` |
| 业务规则判断 | 必须，如 `canSubmitOrder()` |
| 单个简单判断 | 不需要 |

命名前缀：`isXxx()`(状态) | `hasXxx()`(存在性) | `canXxx()`(权限) | `shouldXxx()`(业务规则)

#### 2.1.1 可读性模式（必须遵循）

以下四种模式用于提升代码可读性，写代码时主动应用，不要留给审查阶段。

**模式 1：提取查询方法**

MyBatis Example / Condition 查询逻辑不应内联在业务方法中，必须封装为 Repository 层的语义方法。

```java
// ❌ 查询逻辑内联在 Service 方法中
public void processIssuePlan(Long planId) {
    EquityIssueLogExample example = new EquityIssueLogExample();
    example.createCriteria().andPlanIdEqualTo(planId).andDeletedAtIsNull();
    example.setOrderByClause("created_at DESC");
    List<EquityIssueLog> logs = mapper.selectByExample(example);
    EquityIssueLog latest = logs.isEmpty() ? null : logs.get(0);
    // ... 业务逻辑 ...
}

// ✅ 封装为 Repository 语义方法
public void processIssuePlan(Long planId) {
    EquityIssueLog latest = equityIssueLogRepository.findLatestActiveLog(planId);
    // ... 业务逻辑 ...
}
```

判定标准：Example/Condition 构建 ≥ 3 行，或包含排序/分页/聚合逻辑时，必须提取到 Repository。

**模式 2：Guard Clause（卫语句早返回）**

用早返回处理前置条件和简单路径，避免主逻辑被嵌套包裹。

```java
// ❌ 深层嵌套
if (req != null) {
    User user = findUser(req.getUserId());
    if (user != null) {
        if (user.isActive()) {
            // 20行主逻辑...
        } else { return Result.fail("未激活"); }
    } else { return Result.fail("不存在"); }
} else { return Result.fail("请求为空"); }

// ✅ Guard Clause 早返回
if (req == null) return Result.fail("请求为空");
User user = findUser(req.getUserId());
if (user == null) return Result.fail("不存在");
if (!user.isActive()) return Result.fail("未激活");
// 主逻辑在最外层，无嵌套
```

原则：先处理异常/简单路径并 return，主逻辑保持在最低缩进层级。

**模式 3：语义辅助方法**

复杂的状态比较、枚举判断、条件表达式应封装为语义方法，让业务意图一目了然。

```java
// ❌ 内联枚举比较
if (EquityIssueStatusEnum.ISSUED.name().equals(log.getIssueStatus())) { ... }

// ✅ 语义辅助方法
if (hasStatus(log, EquityIssueStatusEnum.ISSUED)) { ... }

private boolean hasStatus(EquityIssueLog log, EquityIssueStatusEnum status) {
    return status.name().equals(log.getIssueStatus());
}
```

适用场景（对 §2.1 的扩展）：
- 枚举值与字符串字段的比较（`Enum.name().equals(field)`）
- 包含 null 检查 + 阈值判断的复合条件
- 同一判断在方法内出现 2 次以上

**模式 4：翻转 if-else 减少嵌套**

当 if 分支是简短处理（< 5 行）而 else 分支是主逻辑（> 10 行）时，翻转条件。

```java
// ❌ 短分支在前，长分支被 else 包裹
if (isValid) {
    return success;  // 2行
} else {
    // 20行主逻辑（被迫缩进一层）
}

// ✅ 翻转：短分支早返回
if (!isValid) return success;
// 20行主逻辑（最外层）
```

注意：如果两个分支长度相当（都 > 10 行），不适用翻转，应考虑提取方法。

### 2.2 量化标准

- 方法行数：设计目标 <= 40 行，审查阈值 <= 50 行
- 类字段不超过 10 个，超过则拆分
- 条件嵌套不超过 3 层，使用卫语句提前返回
- public 方法必须有完整 Javadoc（见下方 §2.2.1）
- 继承方法必须加 @Override

#### 2.2.1 public 方法注释规范

所有 public 方法（含接口方法）必须有 Javadoc，包含：功能描述 + `@param` + `@return` + `@throws`（如有）。

```java
// ✅ 正确
/**
 * 根据发放计划批量发放权益，跳过已发放的计划
 *
 * @param planIds 发放计划ID列表，不能为空
 * @param operatorId 操作人ID
 * @return 实际成功发放的计划数量
 * @throws CjjClientException 当 planIds 为空时抛出 400
 */
public int batchIssueEquity(List<Long> planIds, Long operatorId) {

// ❌ 错误 — 无注释或注释无意义
public int batchIssueEquity(List<Long> planIds, Long operatorId) {
/** 批量发放 */  // 没有参数和返回值说明
public int batchIssueEquity(List<Long> planIds, Long operatorId) {
```

**豁免**：简单 getter/setter、`toString()`、`equals()`/`hashCode()` 不强制要求。

### 2.3 异常体系

```java
import cn.caijiajia.mvc.exceptions.CjjClientException;  // 客户端错误 4xx
import cn.caijiajia.mvc.exceptions.CjjServerException;  // 服务端错误 5xx
```

**用法**：

```java
// 客户端错误 - 按 HTTP 语义选状态码
throw new CjjClientException(400, "参数错误: 名称不能为空");
throw new CjjClientException(404, "项目不存在，ID: " + projectId);
throw new CjjClientException(409, "项目名称已存在: " + name);

// 服务端错误 - 必须带原始异常
throw new CjjServerException(500, "外部服务调用失败", e);

// 模式 1：资源校验 - 查空即抛
Resource resource = repository.findById(id);
if (resource == null) throw new CjjClientException(404, "资源不存在，ID: " + id);

// 模式 2：外部调用包装 - catch 分类转译
try { return externalClient.call(req); }
catch (TimeoutException e) { throw new CjjServerException(500, "调用超时", e); }
catch (Exception e) { throw new CjjServerException(500, "调用失败", e); }
```

**异常红线**：
- 禁止吞掉异常（空 catch）
- 禁止状态码混用（参数错误用 400，不能用 500）
- 禁止暴露堆栈给客户端
- 自定义业务异常继承 `CjjException`，构造中调用 `super(500, code, message)`

### 2.4 工具类规范

使用 `@UtilityClass`（自动私有构造 + final 类 + 静态方法），所有方法必须处理 null 输入、无副作用。

### 2.5 日志规范

```java
// @Slf4j 注解 + 占位符（禁止字符串拼接）
log.info("处理文件: fileId={}, projectId={}", fileId, projectId);
log.error("处理失败: id={}", id, e);  // 异常必须带 Throwable
log.info("批量完成: 总数={}, 成功={}, 失败={}, 耗时={}ms", total, success, fail, duration);
```

级别：INFO(流程/结果) | WARN(空数据/降级) | ERROR(异常+堆栈) | DEBUG(调试)

> 禁止：循环内打印详细日志 | 记录敏感信息（密码/密钥/Token/身份证/手机号）

### 2.6 禁止魔法值

代码中禁止出现未命名的字面量（数字、字符串），必须提取为常量或枚举。

```java
// ❌ 魔法值
if (status == 3) { ... }
if ("REFUND_SUCCESS".equals(type)) { ... }
Thread.sleep(5000);
if (retryCount > 3) { ... }

// ✅ 常量/枚举
private static final int STATUS_COMPLETED = 3;
private static final long RETRY_INTERVAL_MS = 5000L;
private static final int MAX_RETRY_COUNT = 3;

if (status == STATUS_COMPLETED) { ... }
if (RefundTypeEnum.SUCCESS.getCode().equals(type)) { ... }
Thread.sleep(RETRY_INTERVAL_MS);
if (retryCount > MAX_RETRY_COUNT) { ... }
```

**常量放置规则**：
- 仅本类使用 → `private static final` 放本类顶部
- 多类共享 → 放 `constants/` 包下对应常量类
- 有限枚举集 → 优先用枚举类（带 `code` + `name` + `fromCode()`）

**豁免**：`0`、`1`、`-1`、`""`、`null` 等上下文含义明确的除外。

删除 @Deprecated 方法、未使用 import、注释掉的代码。

---

## 三、API 设计规范

### 3.1 Controller 基础结构

**核心原则**：Controller 层薄（参数接收 + 校验 + 委托 Service + 包装返回），**禁止包含业务逻辑**。所有业务逻辑必须下沉到 Service 层。

```java
@Api("业务模块名称")
@RestController
@RequestMapping("模块路径")
@Slf4j
public class XxxController {
    @Autowired
    private XxxService xxxService;
}
```

> Controller 方法体只允许：参数校验（`@Valid` / `validateParams()`）、单次 Service 调用、返回值包装。出现 if-else 业务判断、循环处理、多次 Service 调用编排等，说明逻辑应下沉到 Service。

**路由设计模式**：

```java
@RequestMapping("fine-tune/project")           // 简单资源路由
@RequestMapping("{projectId}/fine-tune/training")  // 带路径参数
@RequestMapping("easydataset/project")          // 子模块路由
```

### 3.2 HTTP 方法映射

| 操作 | HTTP 方法 | 路径模式 | 示例 |
|------|----------|---------|------|
| 查询列表 | GET | `/resources` | `GET /decisions` |
| 查询单个 | GET | `/resources/{id}` | `GET /questions/{id}` |
| 创建 | POST | `/resources` | `POST /documentSets` |
| 更新 | PUT | `/resources/{id}` | `PUT /decisions/{decisionKey}` |
| 删除 | DELETE | `/resources/{id}` | `DELETE /documentSets/{id}` |
| 批量删除 | POST | `/resources/batch-delete` | `POST /file/batch-delete` |

```java
// ✅ RESTful 风格
@GetMapping("list")
@GetMapping("{id}")
@PostMapping
@PutMapping("{id}")
@DeleteMapping("{id}")
@PostMapping("batch-delete")

// ❌ 禁止动词式路径
@GetMapping("getProject")
@PostMapping("createProject")
```

### 3.3 参数传递

| 注解 | 用途 | 示例 |
|------|------|------|
| `@PathVariable` | 资源 ID | `@GetMapping("{id}") getById(@PathVariable Long id)` |
| `@RequestParam` | 过滤/分页/排序 | `@RequestParam(value="status", required=false)` |
| `@RequestBody @Valid` | 创建/更新 | `create(@RequestBody @Valid CreateReq req)` |
| DTO 查询参数（推荐） | 多条件查询 | `list(@Valid ProjectQueryReq req)` |

> 分页规范：pageNum 默认 1，pageSize 默认 20，必须限制最大值 100

### 3.4 JSR-303 参数校验

```java
@Data
public class CreateProjectReq {
    @NotBlank(message = "项目名称不能为空")
    private String projectName;

    @NotNull(message = "项目类型不能为空")
    private String projectType;

    @Size(max = 200, message = "描述不能超过200字符")
    private String description;
}
```

业务校验：Controller 中 `@Validated` + 私有 `validateParams()` 方法，不满足时 `throw new CjjClientException(400, "原因")`

### 3.5 返回值规范

| 场景 | 返回类型 |
|------|---------|
| 无返回值 | `void` |
| 单个/列表 | `Resp` / `List<Resp>` |
| 分页 | `Page<Resp>` (pageNum, pageSize, totalNums, items) |
| 操作结果 | `CommonResp` (success, message) |
| 文件流 | `void` + HttpServletResponse |

**Result<T> 统一返回封装**：

```java
@GetMapping("/{id}")
public Result<UserVO> getUser(@PathVariable Long id) {
    return Result.success(userService.getById(id));
}
```

### 3.6 Swagger 与日志脱敏

- Controller 类加 `@Api("模块名")`，方法加 `@ApiOperation("描述")`
- 敏感接口使用 `@HttpLogControlConfig(excludesFromAll = {HttpLogItem.responseBody})` 排除响应体日志

---

## 四、数据访问层规范

### 4.1 Condition API 查询

```java
import cn.caijiajia.dal.jdbc.mybatis.plus.dto.Condition;
import cn.caijiajia.dal.jdbc.mybatis.plus.mapper.hints.Direction;
import cn.caijiajia.dal.jdbc.mybatis.plus.mapper.hints.Hints;

Condition<Resource> condition = new Condition<>(Resource.class);

// 等值 / 模糊 / IN / 范围 / NULL / NOT IN / 比较 / 不等于
condition.and().andEqual(Resource::getProjectId, projectId);
condition.and().andLike(Resource::getName, fuzzyLike(keyword));
condition.and().andIn(Resource::getId, idList);
condition.and().andBetween(Resource::getScore, min, max);
condition.and().andIsNull(Resource::getDeletedAt);
condition.and().andIsNotNull(Resource::getStatus);
condition.and().andNotIn(Resource::getStatus, excludeStatusList);
condition.and().andGreaterThan(Resource::getScore, minScore);
condition.and().andLessThan(Resource::getUpdatedAt, timeoutThreshold);
condition.and().andNotEqual(Resource::getStatus, excludeStatus);
```

### 4.2 排序（Hints）

```java
// 方法引用（推荐，类型安全）
Hints<Resource> hints = new Hints<Resource>()
    .addSort(Resource::getCreatedAt, Direction.DESC)
    .addSort(Resource::getId, Direction.ASC);
List<Resource> list = baseMapper.findAllByConditionHints(condition, hints);

// 动态排序（需防注入）
hints.addSort(SqlShieldUtil.filterSpecialCharacters(sortField),
              Direction.valueOf(sortDirection.toUpperCase()));
```

### 4.3 OR 条件组合

```java
Condition<Experiment> condition = new Condition<>(Experiment.class);
QueryCondition<Experiment> queryCondition = condition.and()
    .andEqual(Experiment::getStatus, StatusEnum.ACTIVE.getCode())
    .andLike(Experiment::getName, fuzzyLike(keyword));
queryCondition.orLike(Experiment::getCode, fuzzyLike(keyword));
```

### 4.4 条件更新

```java
Condition<Category> condition = new Condition<>(Category.class);
condition.and().andIn(Category::getId, ids);
Category updateEntity = Category.builder()
    .enabled(true)
    .updater(SecurityUtils.getCurrentUser())
    .build();
baseMapper.update(updateEntity, condition);
```

> 实体字段为 null 不更新；避免全表更新；记得更新审计字段

### 4.5 fuzzyLike 转义（每个 Repository 必备）

```java
private String fuzzyLike(String str) {
    if (str == null || str.isEmpty()) return "%%";
    String escaped = str.replace("\\", "\\\\")
            .replace("%", "\\%").replace("_", "\\_");
    return "%" + escaped + "%";
}
```

### 4.6 MyBatis Example 查询

适用于已有 MyBatis Generator 生成 Example 类的场景：

```java
XxxExample example = new XxxExample();
example.createCriteria().andUidEqualTo(uid).andStatusEqualTo("OPEN").andDeletedAtIsNull();
example.setOrderByClause("created_at DESC");
```

常用方法：`selectByExample` | `selectByExampleWithBLOBs` | `countByExample` | `updateByExampleSelective` | `deleteByExample`

选择：已有 Example 类 -> Example | 复杂动态 SQL / 跨表 -> Condition API

> LIKE 必须加通配符 | IN 传空列表导致 SQL 错误需先检查 isNotEmpty

### 4.7 Mapper 自定义 SQL 场景

| 场景 | Condition API | 自定义 SQL |
|------|--------------|-----------|
| 单表简单查询 | 用 Condition | -- |
| 批量统计 GROUP BY | -- | 用自定义 SQL |
| 多表 JOIN | -- | 用自定义 SQL |
| 批量更新 | -- | 用自定义 SQL |

**字段映射红线**：

```java
// ✅ 必须使用 AS 映射
@Select("SELECT id, order_id AS orderId, created_at AS createdAt FROM ...")

// ❌ 禁止 SELECT *
// ❌ 缺少 AS 映射会导致字段为 null
```

### 4.8 N+1 问题

> 审查检查点：循环/lambda/forEach 内是否有数据库查询？解决方案：批量查询 + Map 缓存。完整模板见 `templates/templates-repo-exception.md`

Bad:
```java
// ❌ 循环中逐条查库，N 条数据产生 N 次 SQL
List<OrderResp> respList = orders.stream().map(order -> {
    User user = userRepository.findById(order.getUserId());  // 每次循环查一次
    OrderResp resp = new OrderResp();
    resp.setUserName(user.getName());
    return resp;
}).collect(Collectors.toList());
```

Good:
```java
// ✅ 批量查询后 Map 映射，只产生 1 次 SQL
List<Long> userIds = orders.stream().map(Order::getUserId).distinct().collect(Collectors.toList());
Map<Long, User> userMap = userRepository.findByIds(userIds).stream()
        .collect(Collectors.toMap(User::getId, Function.identity()));

List<OrderResp> respList = orders.stream().map(order -> {
    User user = userMap.get(order.getUserId());
    OrderResp resp = new OrderResp();
    resp.setUserName(user != null ? user.getName() : null);
    return resp;
}).collect(Collectors.toList());
```

### 4.9 批量操作

每批 500 条，大于 500 条必须分批（`Lists.partition(list, 500)`）。

```java
// 批量插入
Hints<Resource> hints = new Hints<Resource>().ignoreNullValue(false);
baseMapper.saveAllByHints(batch, hints);

// 批量删除
Condition<Resource> condition = new Condition<>(Resource.class);
condition.and().andIn(Resource::getId, ids);
baseMapper.delete(condition);
```

### 4.10 分页查询

```java
PageHelper.startPage(req.getPageNum(), req.getPageSize());  // 必须在查询之前
Condition<Entity> condition = new Condition<>(Entity.class);
// ... 构建条件 ...
List<Entity> list = baseMapper.findAllByConditionHints(condition, hints);
PageInfo<Entity> pageInfo = new PageInfo<>(list);
return PageInfo.of(BeanUtil.copyToList(pageInfo.getList(), Resp.class), pageInfo.getTotal());
```

---

## 五、事务管理与建表规范

### 5.1 事务红线

```java
// ✅ 必须指定 rollbackFor
@Transactional(rollbackFor = Exception.class)

// ❌ 裸 @Transactional 禁止
```

**需要事务的场景**：多表写入 | 联动删除 | 状态更新 + 数据保存

**事务边界**：Controller 不管事务，事务在 Service 层。事务方法只包含数据库操作，不要包含外部调用。

### 5.2 事务陷阱

**陷阱1：本类调用事务不生效（AOP 代理问题）**

> 强制规范：本类调用事务方法，必须使用 `AopContext.currentProxy()`

```java
// ❌ 直接调用，事务不生效
this.bindProduct(order);

// ✅ 强制方案
((OrderService) AopContext.currentProxy()).bindProduct(order);
```

必须配置 `@EnableAspectJAutoProxy(exposeProxy = true)`。备选方案：拆分到不同 Service。

**陷阱2**：catch 后未重新 throw，事务不回滚。必须 catch -> log.error -> throw e

**陷阱3**：private/final 方法事务不生效（无法被 CGLIB 代理），必须 public 非 final

### 5.3 事务+并发锁组合规范

> 涉及分布式锁与事务同时使用的场景，必须遵循以下规范

**设计原则**：锁在事务外层，事务在锁内层（lock-then-transact）

**禁止模式**：
```java
// ❌ 事务包裹锁：锁释放时事务可能未提交，并发窗口导致脏读
@Transactional
public void handle() {
    lock.executeWithLock("key", () -> { /* DB操作 */ });
}
```

**推荐模式**：
```java
// ✅ 锁包裹事务：事务提交后锁才释放，无并发窗口
public void handle() {
    lock.executeWithLock("key", () -> {
        doHandleInTransaction(); // 方法级事务
    });
}

@Transactional(rollbackFor = Exception.class)
public void doHandleInTransaction() { /* DB操作 */ }
```

**注意**：`doHandleInTransaction` 通过 Spring 代理调用才生效（同类调用需 `AopContext.currentProxy()` 或拆分到 Helper 类）。

**单数据源简化**：若确认所有操作在同一数据库，`@Transactional` 放在外层方法也可接受（Spring REQUIRED 传播），但需在代码注释中标注「单数据源，事务覆盖锁内所有操作」。

**锁粒度选择**：

| 场景 | 推荐锁 key | 说明 |
|------|-----------|------|
| 库存扣减 | `lock:product:{productId}` | 商品级别 |
| 用户限额+扣减 | `lock:user:{userId}:product:{productId}` | 用户+商品级别 |
| 订单状态变更 | `lock:order:{orderNo}` | 订单级别 |
| 幂等操作 | 用幂等 key 替代锁（SET NX EX） | 比锁更轻量 |

**幂等+事务组合陷阱**：

```java
// ❌ @Transactional 包裹幂等检查：tx commit 失败时 Redis key 残留，永久阻塞重试
@Transactional
public void handle() {
    idempotent.executeIdempotent("key", () -> { /* DB操作 */ });
}

// ✅ 幂等在事务外层，或事务仅包裹 DB 操作
public void handle() {
    idempotent.executeIdempotent("key", () -> {
        doHandleInTransaction(); // 事务在回调内部
    });
}
```

**多字段更新合并规则**：涉及乐观锁更新（CAS）+ 额外字段更新时，合并为一条 SQL，避免两次写入导致 CAS 被绕过：
```sql
-- ✅ 合并：一条 SQL 同时更新状态和额外字段
UPDATE order SET status=?, tracking_no=? WHERE id=? AND status=?
-- ❌ 拆分：先 CAS 更新状态，再无条件更新额外字段
```

### 5.4 建表审计字段

> 所有新建表必须包含以下审计字段，缺一不可

```sql
-- 审计字段模板（直接复制使用）
creator         varchar(150)                            null comment '创建人用户名',
updater         varchar(150)                            null comment '更新人用户名',
created_by      varchar(150)                            null comment '创建人',
updated_by      varchar(150)                            null comment '更新人',
created_at      datetime      default CURRENT_TIMESTAMP not null comment '创建时间',
updated_at      datetime      default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
```

**建表要点**：`id bigint unsigned auto_increment primary key` | `engine=InnoDB charset=utf8mb4 collate=utf8mb4_unicode_ci` | 必建常用索引

**实体类**：`@Data @TableName` + `@TableId(type = IdType.AUTO)` | 审计字段类型 `LocalDateTime`

**赋值规则**：creator/created_by 创建时设置 | updater/updated_by 每次更新设置 | created_at/updated_at 数据库自动管理
