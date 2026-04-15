# 三、类图模板（classDiagram）

## 骨架模板

```mermaid
classDiagram
    class ClassName {
        +String publicField
        -int privateField
        #double protectedField
        +publicMethod() void
        -privateMethod() String
        #protectedMethod(param) int
    }
```

---

## 业务示例（含继承/实现/组合/关联）

```mermaid
classDiagram
    class BaseEntity {
        <<abstract>>
        #Long id
        #Date createTime
        #Date updateTime
    }

    class UserController {
        -UserService userService
        +getUser(Long) ResponseEntity
        +createUser(UserDTO) ResponseEntity
    }

    class UserService {
        <<interface>>
        +getById(Long) User
        +create(UserDTO) User
    }

    class UserServiceImpl {
        -UserRepository userRepository
        +getById(Long) User
        +create(UserDTO) User
    }

    class User {
        -String name
        -List~Address~ addresses
    }

    class Address {
        -String city
        -String street
    }

    class UserRepository {
        <<interface>>
        +findById(Long) Optional~User~
        +save(User) User
    }

    User --|> BaseEntity : extends
    UserController --> UserService : uses
    UserServiceImpl ..|> UserService : implements
    UserServiceImpl --> UserRepository : uses
    User *-- Address : contains
```

---

## 设计模式示例（策略模式）

```mermaid
classDiagram
    class OrderService {
        -DiscountStrategy discountStrategy
        +calculatePrice(Order) BigDecimal
        +setStrategy(DiscountStrategy) void
    }

    class DiscountStrategy {
        <<interface>>
        +calculate(Order) BigDecimal
    }

    class VipDiscountStrategy {
        +calculate(Order) BigDecimal
    }

    class CouponDiscountStrategy {
        -CouponService couponService
        +calculate(Order) BigDecimal
    }

    class NoDiscountStrategy {
        +calculate(Order) BigDecimal
    }

    OrderService --> DiscountStrategy : uses
    VipDiscountStrategy ..|> DiscountStrategy
    CouponDiscountStrategy ..|> DiscountStrategy
    NoDiscountStrategy ..|> DiscountStrategy
```

---

## 语法速查

| 语法 | 含义 |
|------|------|
| `+`/`-`/`#`/`~` | public/private/protected/package |
| `<\|--` | 继承 |
| `..\|>` | 实现 |
| `*--` | 组合（强拥有） |
| `o--` | 聚合（弱拥有） |
| `-->` | 关联 |
| `..>` | 依赖 |
| `"1"`/`"*"`/`"1..*"`/`"0..1"` | 基数标注 |
| `<<interface>>` / `<<abstract>>` | 类型标注 |
| `~Type~` | 泛型（如 `List~User~`） |

---

# 四、状态图模板（stateDiagram-v2）

## 骨架模板

```mermaid
stateDiagram-v2
    [*] --> State1
    State1 --> State2 : 事件
    State2 --> [*]
```

---

## 业务示例（含嵌套状态）

```mermaid
stateDiagram-v2
    [*] --> Draft : 创建草稿

    Draft --> Submitted : 提交
    Draft --> Deleted : 删除

    Submitted --> UnderReview : 开始审批

    state UnderReview {
        [*] --> Level1
        Level1 --> Level2 : 一级通过
        Level1 --> ReviewRejected : 一级驳回
        Level2 --> Level3 : 二级通过
        Level2 --> ReviewRejected : 二级驳回
        Level3 --> [*] : 三级通过
        Level3 --> ReviewRejected : 三级驳回
        ReviewRejected --> [*]
    }

    UnderReview --> Approved : 审批通过
    UnderReview --> Rejected : 审批驳回

    Rejected --> Draft : 修改重提
    Rejected --> Cancelled : 放弃申请

    Approved --> [*]
    Cancelled --> [*]
    Deleted --> [*]
```

---

## 语法速查

| 语法 | 含义 |
|------|------|
| `[*]` | 开始/结束状态 |
| `state name {}` | 复合状态（嵌套，最多3层） |
| `<<choice>>` / `<<fork>>` / `<<join>>` | 选择/分叉/合并 |
| `State1 --> State2 : 事件` | 基本转换 |
| `State1 --> State2 : 事件 [守卫] / 动作` | 完整转换 |
| `note right of State1 : 文字` | 注释 |

**规范**：始终用 `stateDiagram-v2`，状态名用 PascalCase 或全大写
