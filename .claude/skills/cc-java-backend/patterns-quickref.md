# 设计模式速查

> 规则名 + 一句话说明 + 详见链接。完整模式含代码示例见对应文件。

---

## 策略模式

策略枚举 + 策略接口（`getType()` + `process()`）+ 策略工厂（Spring `@Autowired List` 注入 + Map 注册）+ 协调器。< 5 类型用 switch，>= 5 用策略工厂。
> 详见 patterns-design.md §1.2

## 工厂模式

简单工厂：枚举 + switch（< 5 个类型）。策略工厂：Spring 注入 + Map（>= 5 个类型）。
> 详见 patterns-design.md §1.2

## 模板方法模式

抽象基类定义 `final` 执行骨架，子类实现 `abstract` 核心逻辑，`protected` 钩子方法可选覆盖。统一资源管理（锁、事务）在基类。
> 详见 patterns-design.md §1.3

## 责任链模式（过滤器链）

抽象基类定义 `order` + `doFilter()`，具体过滤器 `@Component` 实现，执行器 `List<AbstractFilter>` 自动注入 + `InitializingBean` 排序。新增过滤器无需修改执行器。
> 详见 patterns-design.md §1.4

## 工厂接口 + 默认方法

核心方法不提供默认实现（强制子类实现），可选方法提供合理 `default` 实现（不依赖实现类内部状态）。
> 详见 patterns-design.md §1.5

## 缓存工厂模式

`ConcurrentHashMap` + `computeIfAbsent` 缓存高成本对象，提供 `clearCache()` 支持配置刷新。
> 详见 patterns-design.md §1.6

## 分布式锁

`distributedLock.lock(key, timeout)` / `unlock(key)`，必须 try-finally，用 `locked` 标志位防止误 unlock。锁 Key 格式：`{业务域}:{操作类型}:{资源ID}`。
> 详见 patterns-concurrency.md §2.1

## 线程池

`@Bean ThreadPoolTaskExecutor`：core/max/queue/prefix/rejectPolicy，每种业务配独立线程池，通过 `@Qualifier` 注入。
> 详见 patterns-concurrency.md §2.2

## 限流与熔断

限流：`ILimiter` 接口 + `permitMillis()` / `release()`，`NoLimiter` 空对象模式降级，`LimiterManager` 通过 Guava Cache 缓存实例。熔断：`@BizBreaker(breakerName = "xxx")` + fallbackMethod，失败率 > 50% 触发。
> 详见 patterns-concurrency.md §2.3, §2.4

## ConfPlus 配置中心

`@AppConf` + `@ConfElement(name = "key")`，所有字段必须有默认值，集合初始化为空集合，嵌套对象必须有无参构造。
> 详见 patterns-concurrency.md §2.5

## ThreadLocal 规范

`static final ThreadLocal` + `init()` / `get()` / `clear()` 三方法。必须 finally 中调用 `clear()`，异步场景手动传递上下文。
> 详见 patterns-concurrency.md §2.6

## SOLID 速查

| 原则 | 检查点 |
|------|--------|
| S 单一职责 | Service < 500 行，方法 < 50 行 |
| O 开闭 | 新增类型用策略模式，不改 if-else |
| L 里氏替换 | 子类不破契约，优先组合而非继承 |
| I 接口隔离 | 接口 < 5 方法，无空实现 |
| D 依赖倒置 | 注入接口不注入实现 |

> 详见 patterns-design.md §1.1

## 枚举设计

必须：code 字段 + name 字段 + `fromCode()` + `@Getter`。按需：业务方法 `isTerminal()` / `canTransitionTo()`。禁止使用 `ordinal()`。
> 详见 patterns-design.md §1.7
