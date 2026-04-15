# 设计模式规范

> SOLID 原则 + 策略/工厂/模板方法/责任链/默认方法/缓存工厂/枚举

---

## 设计模式选择指南

| 场景 | 推荐模式/原则 | 说明 |
|------|-------------|------|
| 类职责过多 | **SRP（单一职责）** | 拆分为多个小类 |
| if-else 分支过多 | **OCP（开闭原则）+ 策略模式** | 用枚举定义类型 + 工厂获取 |
| 继承设计问题 | **LSP（里氏替换）** | 优先使用组合而非继承 |
| 接口过于臃肿 | **ISP（接口隔离）** | 拆分为多个小接口 |
| 高层依赖低层实现 | **DIP（依赖倒置）** | 注入接口而非实现 |
| 多种算法/行为可切换 | 策略模式 | 用枚举定义类型 + 工厂获取 |
| 创建成本高的对象 | 缓存工厂 | ConcurrentHashMap + computeIfAbsent |
| 相似流程不同细节 | 模板方法 | 抽象基类 + 钩子方法 |
| 复杂对象构建 | 建造者模式 | Lombok @Builder |
| 统一入口 | 门面模式 | Service 协调多个组件 |
| 状态/类型定义 | 枚举 | code + name + fromCode() |
| 多步骤数据处理 | 责任链模式 | 抽象过滤器 + Spring 自动收集 |
| 接口方法可选实现 | 默认方法 | interface default method |

---

## 1.1 SOLID 原则检查点

> Claude 已内置 SOLID 通用知识，此处仅保留公司特有检查标准

| 原则 | 公司检查点 | 违反信号 |
|------|-----------|---------|
| **S** 单一职责 | Service < 500 行，方法 < 50 行 | 一个类有多个变化原因；用事件驱动解耦 |
| **O** 开闭 | 新增类型用策略模式，不改 if-else | 添加新功能需要修改现有代码 |
| **L** 里氏替换 | 子类不破坏父类契约；优先组合而非继承 | VIP 子类意外改变父类行为 |
| **I** 接口隔离 | 接口 < 5 个方法 | 实现类有空实现或抛 UnsupportedOperationException |
| **D** 依赖倒置 | 注入接口不注入实现 | 高层模块直接 new 低层实现；无法 Mock 测试 |

---

## 1.2 策略模式 + 工厂模式

> 策略枚举 + 策略接口 + 工厂管理策略实例。< 5 类型用 switch，>= 5 用策略工厂。

### 核心结构

```
StrategyEnum  <───  StrategyFactory
                         │
                    Strategy Interface
                         │
          ┌──────────────┼──────────────┐
     StrategyImplA  StrategyImplB  StrategyImplC
```

### 1. 策略枚举

> 枚举模板见 1.7 枚举设计。策略枚举需包含 code + description + fromCode()。

### 2. 策略接口

```java
public interface PaymentStrategy {

    PaymentResult pay(Order order, PaymentConfig config);

    /** 用于工厂注册 */
    PaymentType getPaymentType();

    /** 默认校验，可覆盖 */
    default void validateConfig(PaymentConfig config) {
        if (config == null) {
            throw new IllegalArgumentException("配置不能为空");
        }
        if (config.getPaymentType() != getPaymentType()) {
            throw new IllegalArgumentException("配置类型与当前策略不匹配");
        }
    }
}
```

### 3. 策略工厂（Spring 自动注入 + Map 注册）

```java
@Slf4j
@Component
public class PaymentStrategyFactory {

    private final Map<PaymentType, PaymentStrategy> registry = new HashMap<>();

    @Autowired
    private List<PaymentStrategy> strategies;

    @PostConstruct
    public void init() {
        if (strategies != null && !strategies.isEmpty()) {
            for (PaymentStrategy strategy : strategies) {
                PaymentType type = strategy.getPaymentType();
                registry.put(type, strategy);
                log.info("已注册策略: {}", type.getDescription());
            }
        }
        log.info("策略工厂初始化完成，共注册 {} 个策略", registry.size());
    }

    public PaymentStrategy getStrategy(PaymentType type) {
        PaymentStrategy strategy = registry.get(type);
        if (strategy == null) {
            throw new IllegalArgumentException("不支持的支付类型: " + type.getDescription());
        }
        return strategy;
    }
}
```

### 4. 具体策略 + 协调器

```java
// 具体策略：@Component + implements 策略接口 + getPaymentType() 返回枚举值
@Component
public class AliPayStrategy implements PaymentStrategy {
    @Autowired private AlipayClient alipayClient;

    @Override
    public PaymentResult pay(Order order, PaymentConfig config) {
        validateConfig(config);
        AlipayResponse response = alipayClient.execute(buildRequest(order, config));
        return response.isSuccess() ? PaymentResult.success(response.getTradeNo())
                                    : PaymentResult.fail(response.getSubMsg());
    }

    @Override
    public PaymentType getPaymentType() { return PaymentType.ALIPAY; }
}

// 协调器（门面）：统一入口，委托给工厂获取策略
@Service
public class PaymentService {
    @Autowired private PaymentStrategyFactory strategyFactory;

    public PaymentResult pay(Order order, PaymentConfig config) {
        return strategyFactory.getStrategy(config.getPaymentType()).pay(order, config);
    }
}
```

### 检查清单

策略枚举 + 策略接口 + 策略工厂 + 具体策略 + 协调器

---

## 1.3 模板方法模式

> 抽象基类定义执行骨架，子类实现具体逻辑

### 实现模板（批量任务执行器）

```java
@Slf4j
public abstract class AbstractBatchTaskExecutor {

    @Autowired
    protected DistributedLock distributedLock;

    /** 模板方法（final 不可覆盖） */
    public final void execute(Task task, List<TaskDetail> details) {
        String lockKey = buildLockKey(task);
        boolean locked = false;
        try {
            locked = distributedLock.lock(lockKey, 30, TimeUnit.MINUTES);
            if (!locked) {
                throw new CjjClientException(409, "任务正在处理中");
            }
            beforeExecute(task, details);    // 钩子（可选覆盖）
            doExecute(task, details);         // 抽象（子类必须实现）
            afterExecute(task, details);      // 钩子（可选覆盖）
        } finally {
            if (locked) { distributedLock.unlock(lockKey); }
        }
    }

    protected abstract void doExecute(Task task, List<TaskDetail> details);
    public abstract String getTaskType();

    protected void beforeExecute(Task task, List<TaskDetail> details) {
        log.info("开始执行任务: taskId={}, type={}", task.getId(), getTaskType());
    }

    protected void afterExecute(Task task, List<TaskDetail> details) {
        log.info("任务执行完成: taskId={}", task.getId());
    }

    protected String buildLockKey(Task task) {
        return "task:" + getTaskType() + ":" + task.getId();
    }
}
```

子类只需实现 `doExecute()` 和 `getTaskType()`，可选覆盖 `beforeExecute()` / `afterExecute()` 钩子。

### 模式要点

- **final 模板方法**：定义执行骨架，不可覆盖
- **abstract 抽象方法**：子类必须实现的核心逻辑
- **protected 钩子方法**：可选覆盖的扩展点
- **统一资源管理**：锁、事务等在基类统一管理

---

## 1.4 责任链模式（过滤器链）

> 抽象基类 + Spring 自动收集，新增过滤器无需修改执行器

### 1. 抽象基类

```java
public abstract class AbstractBtnFilter {

    protected static final int DEFAULT_ORDER = 100;
    private int order = DEFAULT_ORDER;

    /** 执行过滤逻辑 */
    public abstract void doFilter(List<ExperimentVo> list);

    public int getOrder() { return order; }
    protected void setOrder(int order) { this.order = order; }
}
```

### 2. 具体过滤器实现

```java
@Component
public class StatusBtnFilter extends AbstractBtnFilter {
    public StatusBtnFilter() { setOrder(10); }  // 最先执行

    @Override
    public void doFilter(List<ExperimentVo> list) {
        for (ExperimentVo vo : list) {
            if (vo.getStatus() == ExperimentStatus.RUNNING.getCode()) {
                vo.setShowStopBtn(true);
                vo.setShowStartBtn(false);
            }
        }
    }
}

@Component
public class PermissionBtnFilter extends AbstractBtnFilter {
    @Autowired private PermissionService permissionService;
    public PermissionBtnFilter() { setOrder(20); }  // 状态过滤后

    @Override
    public void doFilter(List<ExperimentVo> list) { /* 权限过滤逻辑 */ }
}
// 新增过滤器：TimeWindowBtnFilter(order=30) 等，无需修改执行器
```

### 3. 过滤器执行器

```java
@Slf4j
@Component
public class OprBtnCalculator implements InitializingBean {
    @Autowired private List<AbstractBtnFilter> btnFilters;

    @Override
    public void afterPropertiesSet() {
        if (btnFilters != null) btnFilters.sort(Comparator.comparingInt(AbstractBtnFilter::getOrder));
    }

    public void buildOprButtons(List<ExperimentVo> list) {
        if (list == null || list.isEmpty()) return;
        for (ExperimentVo vo : list) { vo.setShowEditBtn(true); vo.setShowDeleteBtn(true); }
        for (AbstractBtnFilter filter : btnFilters) { filter.doFilter(list); }
    }
}
// 使用: @Autowired OprBtnCalculator -> oprBtnCalculator.buildOprButtons(voList)
```

### 检查清单

```
抽象基类定义 order + doFilter()
具体实现 @Component（新增无需修改执行器）
执行器 List<AbstractFilter> 自动注入 + InitializingBean 排序
```

---

## 1.5 工厂接口 + 默认方法

> 接口默认方法实现可选覆盖的工厂模式

```java
public interface BizFlowFactory {

    // --- 核心方法（子类必须实现） ---
    BizFlowTask newBizFlow(BizFlowReq executeReq);
    BizFlowTask restoreBizFlow(String bizSerial);
    BizFlowTask restoreBizFlow(String bizKey, String bizSerial);
    BizFlowTask restoreBizFlow(String bizKey, String bizSerial, String currentProcessBeanName);
    BizflowResp runBizFlow(BizFlowReq executeReq);

    // --- 默认方法（可选覆盖） ---

    /** 恢复请求构建（大部分实现类不需要） */
    default BizFlowReq resumeBizFlowReq(String bizSerial) {
        throw new BizFlowExecutionException(
            ExceptionCodeConstant.RUN_BIZ_FLOW_ERROR_CODE,
            "当前工厂不支持 resumeBizFlowReq 操作"
        );
    }

    /** 避免死锁的状态更新（特定场景需要时覆盖） */
    default void updateBizFlowExecStatusAvoidDeadLock(BizFlowTask task, BizFlowStatus status) {
        // 空实现
    }

    /** 检查流程是否正在运行 */
    default boolean isRunning(String bizKey, String bizSerial) {
        return false;
    }

    /** 获取流程超时时间（秒） */
    default int getTimeoutSeconds() {
        return 300;  // 默认 5 分钟
    }
}
```

### 检查清单

```
核心方法不提供默认实现（强制子类实现）
可选方法提供合理的默认实现（不依赖实现类内部状态）
```

---

## 1.6 缓存工厂模式

> ConcurrentHashMap + computeIfAbsent 缓存高成本对象

```java
@Slf4j
@Component
public class ChatModelFactory {
    @Value("${langchain4j.open-ai.chat-model.base-url}") private String baseUrl;
    @Value("${langchain4j.open-ai.chat-model.api-key}") private String apiKey;
    @Value("${langchain4j.open-ai.chat-model.model-name}") private String defaultModelName;

    private final ConcurrentHashMap<String, ChatModel> cache = new ConcurrentHashMap<>();

    /** 核心方法：获取或创建（computeIfAbsent 保证原子性） */
    public ChatModel getOrCreate(String modelName) {
        String effective = (modelName != null && !modelName.trim().isEmpty()) ? modelName.trim() : defaultModelName;
        return cache.computeIfAbsent(effective, name -> {
            log.info("创建 ChatModel: modelName={}", name);
            return OpenAiChatModel.builder().baseUrl(baseUrl).apiKey(apiKey).modelName(name).build();
        });
    }

    public ChatModel getDefault() { return getOrCreate(null); }
    public void clearCache() { cache.clear(); }  // 配置刷新时调用
}
```

### 要点

- `ConcurrentHashMap` + `computeIfAbsent` = 线程安全的原子性获取或创建
- `clearCache()` 支持配置刷新
- 记录创建日志便于排查

---

## 1.7 枚举设计

> 标准枚举模板与业务方法设计

### 标准模板（int code）

```java
@Getter
public enum TaskStatus {

    PROCESSING(0, "处理中", "#1677FF"),
    COMPLETED(1, "已完成", "success"),
    FAILED(2, "失败", "error"),
    INTERRUPTED(3, "已中断", "#b8babf");

    private final int code;       // 数据库存储值
    private final String name;    // 中文名称
    private final String color;   // 前端显示颜色（可选）

    TaskStatus(int code, String name, String color) {
        this.code = code;
        this.name = name;
        this.color = color;
    }

    public static TaskStatus fromCode(int code) {
        for (TaskStatus status : values()) {
            if (status.code == code) { return status; }
        }
        throw new IllegalArgumentException("Unknown status code: " + code);
    }

    public boolean isTerminal() {
        return this == COMPLETED || this == INTERRUPTED;
    }

    public boolean canTransitionTo(TaskStatus target) {
        switch (this) {
            case PROCESSING:
                return target == COMPLETED || target == FAILED || target == INTERRUPTED;
            case FAILED:
                return target == PROCESSING;  // 可重试
            default:
                return false;  // 终态不可转换
        }
    }
}
```

### 字符串 code 版本

与 int code 结构相同，字段类型改为 `String code`，`fromCode()` 用 `equals()` 比较。可用 `@AllArgsConstructor` 替代手写构造函数。

### 带执行顺序的枚举（流程步骤）

在标准模板基础上增加 `int order` 字段，额外提供：
- `next()` -- 查找 `order + 1` 对应的枚举值
- `isFinal()` -- 判断是否为最终步骤

### 枚举必要元素

| 元素 | 必须 | 说明 |
|------|------|------|
| code 字段 | 必须 | 数据库存储值 |
| name 字段 | 必须 | 中文显示名称 |
| fromCode() | 必须 | 静态查找方法 |
| @Getter | 必须 | Lombok 注解 |
| 业务方法 | 按需 | isTerminal(), canTransitionTo() |
| color 字段 | 按需 | 前端显示时添加 |

### 枚举反例

```java
// 禁止：使用 ordinal()（顺序不稳定）
int dbValue = status.ordinal();
// 正确：使用明确的 code
int dbValue = status.getCode();

// 禁止：业务逻辑分散
if (status == COMPLETED || status == INTERRUPTED) { }
// 正确：封装为枚举方法
if (status.isTerminal()) { }
```

### 枚举业务方法设计原则

| 方法类型 | 命名模式 | 示例 |
|---------|---------|------|
| 类型判断 | `isXxx()` | `isRun()`, `isGray()` |
| 状态判断 | `isTerminal()`, `isSuccessful()` | 终态、成功态判断 |
| 比较方法 | `greaterThan()`, `lessThan()` | 带 priority 字段的优先级比较 |
| 转换方法 | `next()`, `previous()` | 带 order 字段的流程步骤转换 |

### 检查清单

```
code 字段 + name 字段 + fromCode() + @Getter
按需: 业务方法 isTerminal() / canTransitionTo()
禁止使用 ordinal()
```
