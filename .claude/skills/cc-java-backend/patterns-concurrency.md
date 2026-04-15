# 并发与分布式规范

> 分布式锁、线程池、限流、熔断、ConfPlus 动态配置、ThreadLocal

---

## 2.1 分布式锁

> 使用 DistributedLock 实现分布式锁保护。基础用法见 `patterns-quickref.md`。

### 锁 Key 命名规范

```java
// 格式: {业务域}:{操作类型}:{资源ID}
"task:progress:" + taskId       // 任务进度更新锁
"task:complete:" + taskId       // 任务完成收尾锁
"resume:detail:" + detailId     // 回调恢复锁
"file:upload:" + fileId         // 文件上传锁
```

### 常见场景

均使用标准模式（try-lock-finally-unlock），典型场景：

| 场景 | lockKey | 超时 | 特点 |
|------|---------|------|------|
| 回调幂等保护 | `resume:detail:{id}` | 10s | lock后先检查状态，已处理则跳过 |
| 进度更新保护 | `task:progress:{id}` | 30s | 从DB查实际完成数再更新 |
| 任务完成收尾 | `task:complete:{id}` | 60s | 统计+更新+通知 |

### 超时时间选择

| 场景 | 超时时间 |
|------|---------|
| 简单状态更新 | 10秒 |
| 进度统计更新 | 30秒 |
| 复杂业务逻辑 | 60秒 |
| 批量处理 | 120秒 |

### 注意事项

- `lock()` 后必须在 `finally` 中 `unlock()`
- 用 `boolean locked` 标志位判断是否获取成功
- 锁粒度尽量细（按资源 ID，不要锁全局）

---

## 2.2 线程池配置

> ThreadPoolTaskExecutor 配置与使用指南。简版 Bean 配置见 `patterns-quickref.md`。

### 标准配置模板（通过 ConfPlus 动态配置）

```java
@Configuration
public class TaskExecutorConfig {
    @Autowired private AppConfPlusConfig config;

    @Bean("taskExecutorPool")
    public ThreadPoolTaskExecutor taskExecutorPool() {
        PoolSettings settings = config.getThreadPoolConfig().getTaskExecutor();
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(settings.getCorePoolSize());
        executor.setMaxPoolSize(settings.getMaxPoolSize());
        executor.setQueueCapacity(settings.getQueueCapacity());
        executor.setThreadNamePrefix("task-exec-");
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        // 优雅关闭
        executor.setKeepAliveSeconds(300);
        executor.setAllowCoreThreadTimeOut(true);
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(120);
        executor.initialize();
        return executor;
    }
}
```

### 推荐配置

| 场景 | 核心线程 | 最大线程 | 队列容量 |
|------|---------|---------|---------|
| 任务恢复 | 5 | 10 | 50 |
| 通用任务 | 10 | 20 | 100 |
| 高并发Detail | 20 | 100 | 1000 |
| IO密集型 | CPU*2 | CPU*4 | 500 |
| CPU密集型 | CPU+1 | CPU*2 | 100 |

### CompletableFuture 使用

```java
// 并行执行
List<CompletableFuture<Result>> futures = items.stream()
    .map(item -> CompletableFuture.supplyAsync(() -> process(item), executor))
    .toList();

List<Result> results = futures.stream()
    .map(CompletableFuture::join)
    .toList();

// 带超时
try {
    return future.get(30, TimeUnit.SECONDS);
} catch (TimeoutException e) {
    future.cancel(true);
    throw new CjjServerException(500, "任务执行超时");
}
```

### 多业务线程池

每种业务配独立线程池，通过 `@Qualifier("xxxExecutor")` 注入使用。

| 业务类型 | Bean 名称 | 核心配置 |
|---------|-----------|---------|
| 通用异步 | taskExecutor | 10-20线程，200队列 |
| 报表/导出 | reportExecutor | 5-10线程，50队列，长超时 |
| 外部回调 | callbackExecutor | 20-50线程，500队列，短超时 |
| 定时调度 | scheduledExecutor | ThreadPoolTaskScheduler, 5线程 |
| IO密集 | ioExecutor | CPU*2-4线程 |
| CPU密集 | cpuExecutor | CPU+1线程 |

**条件加载**：`@ConditionalOnProperty(name = "feature.enable", havingValue = "true")` 按需创建线程池。

**线程池监控**：注入 `Map<String, ThreadPoolTaskExecutor>`，定时打印活跃/队列/完成数。

---

## 2.3 限流器模式

> 使用 ILimiter 接口 + Guava Cache 实现限流。接口定义见 `patterns-quickref.md`。

### 限流器管理器（工厂 + 缓存）

```java
@Slf4j
@Component
public class LimiterManager {
    @Autowired private RedissonClient redissonClient;

    // Guava Cache 缓存限流器实例，1天过期
    private static final Cache<String, ILimiter> cache = CacheBuilder.newBuilder()
            .expireAfterAccess(1, TimeUnit.DAYS).build();

    public ILimiter getLimiter(String key, int maxPermits) {
        if (maxPermits <= 0) return new NoLimiter();  // 空对象模式
        try {
            return cache.get(key, () -> createLimiter(key, maxPermits));
        } catch (ExecutionException e) {
            return new NoLimiter();  // 降级
        }
    }
}
```

### 使用示例

```java
ILimiter limiter = limiterManager.getLimiter("api:" + apiKey, config.getQps());
if (!limiter.permitMillis(1000)) {
    throw new CjjClientException(429, "请求过于频繁");
}
try { return doCall(request); } finally { limiter.release(); }
```

### 要点

- **空对象模式**：maxPermits <= 0 时返回 NoLimiter，避免 null 判断
- **缓存复用**：Guava Cache 缓存限流器实例
- **降级兜底**：创建失败返回 NoLimiter，保证服务可用
- **释放许可**：finally 中调用 release()

---

## 2.4 熔断器模式（Resilience4j）

> 使用 Resilience4j 实现熔断保护。简版注解用法见 `patterns-quickref.md`。

### 核心注解

```java
@Target({ElementType.METHOD})
@Retention(RetentionPolicy.RUNTIME)
public @interface BizBreaker {
    /**
     * 熔断器名称
     * 支持 SpEL 表达式，如 "#req.bizKey"
     */
    String breakerName();
}
```

### 实现架构

```
@BizBreaker注解 -> AOP拦截器(SpEL解析breakerName) -> BizBreakerProcessor -> CircuitBreakerRegistry(版本化缓存) -> 业务执行/降级
```

**核心组件**：
- `BizBreakerInterceptor`：AOP 切面，SpEL 解析动态熔断器名称，`@Order(-1)` 优先执行
- `BizBreakerProcessor`：管理 CircuitBreakerRegistry（ConcurrentHashMap 按版本缓存），`Try.ofSupplier` + `recover` 降级
- `BizBreakerRegister`：`@ConfigurationProperties(prefix = "breaker.resilience4j")` 配置类

### 配置示例（application.yml）

```yaml
breaker:
  resilience4j:
    version: "1.0"
    failureRateThreshold: 50          # 失败率 > 50% 触发熔断
    slowCallRateThreshold: 100        # 慢调用率阈值
    slowCallDurationThreshold: 60     # 慢调用判定时间（秒）
    minimumNumberOfCalls: 10          # 最小调用次数
    slidingWindowSize: 100            # 滑动窗口大小
    recordExceptions:
      - java.lang.RuntimeException
    ignoreExceptions:
      - cn.caijiajia.mvc.exceptions.CjjClientException
```

### 使用示例

```java
@BizBreaker(breakerName = "external-api")          // 固定名称
public ApiResponse callExternalApi(ApiRequest req) { return restTemplate.postForObject(...); }

@BizBreaker(breakerName = "#req.bizKey")            // 动态名称（SpEL，按 bizKey 隔离）
public Result process(ProcessRequest req) { return doProcess(req); }
```

### 要点

- 熔断器防级联故障（失败率触发），限流器保护系统容量（请求数触发）
- 失败率阈值 50%，最小调用数 10+
- `CjjClientException` 配置 ignoreExceptions
- 熔断后降级返回默认值或缓存

---

## 2.5 ConfPlus 动态配置

> 使用 @AppConf 和 @ConfElement 实现配置热更新

### 基础用法

```java
import cn.caijiajia.confplus.annotations.AppConf;
import cn.caijiajia.confplus.annotations.ConfElement;

@AppConf
@Data
public class AppConfPlusConfig {

    // 基础类型 + 默认值
    @ConfElement(name = "feature_enable_flag")
    private Integer enableFlag = 0;

    // 字符串类型
    @ConfElement(name = "api_base_url")
    private String apiBaseUrl = "https://api.example.com";
}
```

### 增强用法

```java
@AppConf
@Data
public class BizFlowConfigs {
    @ConfElement(name = "auditcore_biz_flow_log")
    private Integer bizFlowLog = 0;                                          // 基础类型

    @ConfElement(name = "variable_journey_apps")
    private List<String> variableJourneyApps = Lists.newArrayList();         // 集合（默认空集合）

    @ConfElement(name = "decision_key_exclusive_delay_topic")
    private Map<String, Integer> delayTopic = Maps.newHashMap();             // Map

    @ConfElement(name = "${spring.application.name}_monitor_number")
    public Integer monitorNumber = 5000;                                     // 动态表达式

    @ConfElement(name = "log_execute_conf")
    private LogExecuteConf logExecuteConf = new LogExecuteConf();            // 嵌套对象（必须有无参构造）
}
```

### 配置规范

| 规则 | 说明 |
|------|------|
| 默认值必填 | 所有字段必须有默认值，防止 null |
| 集合初始化 | List/Map 初始化为空集合，不用 null |
| 嵌套类构造 | 嵌套对象必须有无参构造函数 |
| 命名规范 | 配置名使用下划线分隔，全小写 |
| 动态表达式 | 支持 `${spring.application.name}` 等占位符 |

---

## 2.6 ThreadLocal 使用规范

> 线程上下文传递与内存安全管理。三方法摘要见 `patterns-quickref.md`。

### 标准模式

```java
/**
 * 业务流程通用参数 ThreadLocal 管理器
 * 用于在调用链中传递上下文信息
 */
public class BizFlowCommonParamThreadLocalHelper {

    private static final ThreadLocal<BizFlowCommonParam> COMMON_PARAM = new ThreadLocal<>();

    /** 初始化上下文 */
    public static void init(BizFlowCommonParam param) {
        COMMON_PARAM.set(param);
    }

    /** 获取上下文 */
    public static BizFlowCommonParam get() {
        return COMMON_PARAM.get();
    }

    /** 清理上下文（必须在 finally 中调用） */
    public static void clear() {
        COMMON_PARAM.remove();
    }
}
```

### 使用示例

```java
public void execute(Request req) {
    try {
        BizFlowCommonParamThreadLocalHelper.init(buildParam(req));
        doBusinessLogic();  // 内部通过 get() 获取上下文
    } finally {
        BizFlowCommonParamThreadLocalHelper.clear();
    }
}
```

### 异步场景处理

```java
// 异步任务需要手动传递 ThreadLocal
public void executeAsync(Request req) {
    BizFlowCommonParam currentParam = BizFlowCommonParamThreadLocalHelper.get();
    executor.submit(() -> {
        try {
            BizFlowCommonParamThreadLocalHelper.init(currentParam);
            doAsyncLogic();
        } finally {
            BizFlowCommonParamThreadLocalHelper.clear();
        }
    });
}
```

### 要点

- `static final ThreadLocal` + 提供 `init()`/`get()`/`clear()` 三个方法
- **必须**在 finally 中调用 `clear()`（线程池复用场景尤其重要）
- 异步场景需手动获取并在新线程中重新设置
- 避免存储大对象（防止内存泄漏）
