# 数禾 Java 后端开发规范（基础设施）

> 单元测试、消息队列、远程调用、定时任务、文件存储、AOP、启动配置

---

## 六、单元测试规范

### 6.1 测试基类

继承 `BaseMock`（`@ExtendWith(MockitoExtension.class)` + `@ActiveProfiles("local")`），通过 `generatorObject(TypeReference, path)` 从 `test/resources/{模块名}/` 加载 JSON 测试数据。

### 6.2 测试类结构（Given-When-Then）

```java
@Slf4j
public class ProjectServiceTest extends BaseMock {
    private static final String PROJECT_REQ_JSON = "project/ProjectReq.json";

    @InjectMocks private ProjectService projectService;
    @Mock private ProjectRepository projectRepository;

    @Test
    public void shouldCreateProjectSuccessfully() {
        // Given
        ProjectCreateReq req = generatorObject(new TypeReference<ProjectCreateReq>() {}, PROJECT_REQ_JSON);
        when(projectRepository.save(any(Project.class))).thenReturn(Project.builder().id(1L).build());
        // When
        Long projectId = projectService.create(req);
        // Then
        assertNotNull("项目ID不应为空", projectId);
        verify(projectRepository, times(1)).save(any(Project.class));
    }

    @Test
    public void shouldThrowExceptionWhenProjectNotFound() {
        when(projectRepository.findById(anyLong())).thenReturn(Optional.empty());
        assertThrows(CjjClientException.class, () -> projectService.getById(1L));
    }
}
```

### 6.3 规则速查

- 只 Mock **外部依赖**（Repository、其他 Service、FeignClient），不 Mock 被测类本身
- 测试数据用 JSON 文件（`test/resources/{模块名}/`）或工厂方法（`buildXxx()`）
- **命名**：`should...When...` 或 `test{Method}_{场景}_{期望}`，类名 = 被测类 + Test
- **覆盖**：正常流程、边界条件（空值/null）、异常场景、分支覆盖
- **集成测试**：`@SpringBootTest` + `@ActiveProfiles("local")` + `@Disabled`（需真实数据库时移除）

---

## 七、基础设施

### 7.1 自定义注解与 AOP 切面

**操作日志 @LogRecord**：

```java
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface LogRecord {
    OperationEnum action();  // CREATE/UPDATE/DELETE/ENABLE/DISABLE/PUBLISH/ROLLBACK
    TargetEnum target();
    String bizKey() default "";  // SpEL 表达式，如 "#result.id"
    String content();            // SpEL，如 "'创建实验: ' + #req.name"
}

// 切面：@Around -> proceed -> SpEL解析 -> 保存 OperationLog
// 使用：@LogRecord(action = CREATE, target = EXPERIMENT, bizKey = "#result.id", content = "...")
```

**其他注解**：

| 场景 | 注解 | 通知类型 | 说明 |
|------|------|---------|------|
| 操作日志 | @LogRecord | @Around | SpEL 解析内容 |
| 数据源切换 | @WithDynamicDataSource("slave") | @Around | `@Order(1)` 在事务之前，DataSourceContextHolder 切换，finally 恢复 |
| 权限校验 | @RequirePermission({"xxx:create"}) | @Before | 支持 AND/OR 逻辑 |
| 性能监控 | @TimeMonitor(threshold = 5000) | @Around | 超阈值告警 |

### 7.2 OSS 文件存储

**使用公司封装的 OssService**（不直接用阿里云 SDK）：

```java
import cn.caijiajia.cloud.service.oss.api.OssService;
import cn.caijiajia.cloud.service.oss.api.model.Mimetypes;
```

**API 签名**：

| 操作 | API | 参数 |
|------|-----|------|
| 上传 | `uploadFile(bucket, prefix, fileName, stream, mimeType)` | 5 个参数 |
| 下载 | `downloadFile(bucket, ossPath)` | bucket + 完整路径 |
| 删除 | `delete(bucket, ossPath)` | bucket + 完整路径 |
| 存在 | `doesObjectExist(bucket, ossPath)` | bucket + 完整路径 |

**使用模式**：`@Value("${caijiajia.aliyun.oss.objStore.bucketName}")` 注入 bucket，`uploadFile` 返回 boolean 判断成功，失败抛 `CjjServerException`。上传必须用 try-with-resources 管理 InputStream。

**要求**：路径规范 `{模块名}/{类型}/{业务ID}/{文件名}` | 文件名必须 sanitize（替换 `..`、`/`、`\`） | 区分 4xx/5xx | 频繁使用时封装 `XxxOssService`

### 7.3 RabbitMQ 消息队列

**Producer**：继承 `BaseProducer`，注入 `CjjRabbitTemplate`。发送前检查开关 -> 设置 Trigger -> try-catch 发送。

```java
// 消息体必须包含 uid 和 trigger
msg.setTrigger(MsgTopic.OPEN_VIP_SUCC_TRIGGER);
rabbitTemplate.convertAndSend(MsgTopic.OPEN_VIP_SUCC_EXCHANGE, null, msg);
```

**Consumer**：分布式锁 + Redis 幂等标记（业务唯一键），失败 throw 异常触发 MQ 重试。

```java
String key = "BORROWING_BACK:" + msg.getOrderNo();
try {
    distributedLock.lock(key);
    if (StringUtils.isNotBlank(redisClient.get(key))) return; // 已处理
    doProcess(msg);
    redisClient.set(key, "DONE");
} catch (Exception e) { throw e; } // 重试
finally { distributedLock.unlock(key); }
```

**命名规范**：Exchange `{service}.exchange.{action}` | Trigger `{service}.trigger.{action}` | Queue `{service}.queue.{action}`

### 7.4 Feign 微服务调用

**FeignClient 接口定义**：

```java
@FeignClient(name = "vipship", path = "/vipship")
public interface VipshipFeignClient {
    @GetMapping("/getVipAccountInfo/{uid}")
    VipAccountInfoResp getVipAccountInfoResp(@PathVariable("uid") String uid);

    @PostMapping("/vipship/open")
    OpenVipAccountResp openVipAccount(@RequestBody OpenVipAccountReq req);
}
```

**Delegator 封装层（推荐）**：Service 不直接调用 FeignClient，通过 Delegator 统一处理异常/日志/降级。

```
Controller -> Service -> Delegator -> FeignClient -> 远程服务
```

```java
@Component
@Slf4j
public class ListHubDelegator {
    @Autowired private ListhubApiFeignClient listhubApiFeignClient;

    public boolean saveContent(SaveListContentReq req) {
        try {
            listhubApiFeignClient.saveOrUpdateContent(req);
            return true;
        } catch (Exception e) {
            log.warn("saveContent failed, domain:{}", req.getDomain(), e);
            return false;  // 操作类返回 false，查询类返回 null
        }
    }
}
```

**注意**：`@PathVariable` 必须指定参数名 `@PathVariable("id")`；超时通过 `feign.client.config.{service}.readTimeout` 配置。

### 7.5 定时任务（SchedulerPlus）

**核心原则**：Job 层薄（参数解析 + 调 Service + 返回 JobResult），Service 层厚（所有业务逻辑）。

```java
@Slf4j
@JobInfo
public class DeductV2Job extends JobExecutor {
    @Resource private DeductJobService deductJobService;

    @Override
    public JobResult execute(String jobScheduleId, String externalData) {
        try {
            deductJobService.doDeductJob(jobScheduleId, externalData);
            return JobResult.success();
        } catch (CjjClientException e) {
            log.warn("Job 业务异常, jobScheduleId:{}", jobScheduleId);
            return new JobResult(e.getCode(), e.getMessage());
        } catch (Exception e) {
            log.error("Job 系统异常, jobScheduleId:{}", jobScheduleId, e);
            return new JobResult(JobCodeMessages.EXECUTE_JOB_ERROR_CODE, e.getMessage());
        }
    }
}
```

**幂等**：`jobRecordService.isExecuted(jobScheduleId)` 检查 + 执行后 `markExecuted()`。

### 7.6 日期处理（DateUtil + Joda-Time）

```java
// 格式常量
DateUtil.YYYY_MM_DD       // "yyyy-MM-dd"
DateUtil.NORMAL_FORMAT    // "yyyy-MM-dd HH:mm:ss"

// 日期计算（基于 Joda-Time DateTime）
Date after7Days = DateUtil.plusDay(now, 7);
Date before30Days = DateUtil.minusDay(now, 30);

// 格式转换
Date date = DateUtil.convert2Date("2024-01-15");        // String -> Date
String str = DateUtil.getNormalFormatStr(date);          // Date -> String

// 边界处理
Date start = DateUtil.getStartDateTimeOfDay(date);      // 00:00:00
Date end = DateUtil.getEndTimeOfThisDay(date);           // 23:59:59
long ttlSeconds = DateUtil.timesSecondsLeft();           // 到次日的秒数
```

禁止使用 `SimpleDateFormat` 共享实例（线程不安全），使用 DateUtil 工具类。

### 7.7 Spring Boot 启动配置

**JDK 17 模块化参数**（遇到 `InaccessibleObjectException` 时添加）：

```
--add-opens java.base/java.lang=ALL-UNNAMED --add-opens java.base/java.lang.reflect=ALL-UNNAMED --add-opens java.base/java.util=ALL-UNNAMED --add-opens java.base/java.nio=ALL-UNNAMED
```

**Profile**：`local`(开发) / `dev`(联调) / `test`(测试) / `uat`(验收) / `prod`(生产)

**启动命令**：

```bash
mvn spring-boot:run -pl {{MODULE}} -Dspring-boot.run.profiles={{PROFILE}} -Dspring-boot.run.jvmArguments="{{JVM_OPTS}}"
java {{JVM_OPTS}} -jar {{JAR}} --spring.profiles.active={{PROFILE}}
```
