# 五、ER 图模板（erDiagram）

> ER 图规范详见 `cc-api-analyzer/references/er-guide.md`，本模板为简化版

## 骨架模板

```mermaid
erDiagram
    %% entity1: 业务描述
    entity1 ||--o{ entity2 : "entity2_id"

    entity1 {
        bigint id PK
        varchar name
        datetime created_at
    }

    %% entity2: 业务描述
    entity2 {
        bigint id PK
        bigint entity1_id FK
        tinyint status
    }
```

---

## 业务示例（多表关联）

```mermaid
erDiagram
    %% ========== 用户模块 ==========

    %% user: 用户主表，存储平台注册用户信息
    user ||--o{ order : "user_id"
    user {
        bigint id PK
        varchar username UK
        varchar email UK
        varchar password_hash
        tinyint status
        datetime created_at
        datetime updated_at
    }

    %% ========== 订单模块 ==========

    %% order: 订单主表，存储用户订单信息
    order ||--|{ order_item : "order_id"
    order {
        bigint id PK
        bigint user_id FK
        varchar order_no UK
        decimal total_amount
        tinyint status
        datetime created_at
        datetime paid_at
    }

    %% order_item: 订单明细表，存储订单商品信息
    order_item }|--|| product : "product_id"
    order_item {
        bigint id PK
        bigint order_id FK
        bigint product_id FK
        int quantity
        decimal unit_price
        decimal subtotal
    }

    %% product: 商品表
    product {
        bigint id PK
        varchar name
        varchar sku UK
        decimal price
        int stock
        tinyint status
    }
```

---

## 语法速查

| 语法 | 含义 |
|------|------|
| `\|\|` | 恰好一个（必须） |
| `o\|` | 零或一个（可选） |
| `}o` | 零或多个 |
| `}\|` | 一个或多个 |
| `PK` / `FK` / `UK` | 主键 / 外键 / 唯一键 |

**常用类型**：`bigint`(ID), `int`(数量), `tinyint`(状态), `varchar`(文本), `decimal`(金额), `datetime`(时间), `json`

**规范**：表名小写、外键命名 `表名_id`、关系标签用 FK 列名（`user_id`、`order_id`），禁止泛化词（`has`、`contains`、`places`）。建议添加业务注释（`%% 表名: 业务描述`），表较多时按模块分组

# 六、甘特图模板（gantt）

## 骨架模板

```mermaid
gantt
    title 项目开发计划
    dateFormat YYYY-MM-DD
    excludes weekends

    section 需求阶段
    需求调研         :done, req1, 2026-01-01, 3d
    需求评审         :done, req2, after req1, 1d

    section 开发阶段
    后端开发         :crit, dev1, after req2, 10d
    前端开发         :dev2, after req2, 8d
    联调测试         :dev3, after dev1, 5d

    section 里程碑
    需求冻结         :milestone, m1, 2026-01-05, 0d
    上线发布         :milestone, m2, 2026-02-05, 0d
```

---

## 语法速查

| 语法/标记 | 含义 |
|-----------|------|
| `dateFormat YYYY-MM-DD` | 日期格式 |
| `axisFormat %m/%d` | 显示格式 |
| `done` / `active` / `crit` / `milestone` | 已完成/进行中/关键/里程碑 |
| `:id, 2026-01-01, 7d` | 日期+天数 |
| `:id, after task1, 3d` | 前置依赖 |
| `excludes weekends` | 排除周末 |

**常见问题**：日期必须用 ISO 格式（`YYYY-MM-DD`），避免任务依赖循环，里程碑持续时间为 `0d`。详见 `resources.md`。

# 七、思维导图模板（mindmap）

## 骨架模板

```mermaid
mindmap
  root((系统名称))
    模块A
      功能A1
        子功能A1a
        子功能A1b
      功能A2
    模块B
      功能B1
      功能B2
        子功能B2a
    模块C
      功能C1
```

---

## 业务示例（电商系统模块拆解）

```mermaid
mindmap
  root((电商平台))
    用户域
      注册登录
      会员等级
        普通会员
        VIP 会员
      收货地址
    商品域
      商品管理
        上架下架
        库存管理
      分类体系
      搜索推荐
    交易域
      购物车
      订单
        创建
        支付
        退款
      优惠券
    运营域
      活动配置
      数据分析
      消息推送
```

---

## 语法速查

| 语法 | 形状 |
|------|------|
| `文本` | 默认矩形 |
| `((文本))` | 圆形（通常根节点） |
| `[文本]` | 方形 |
| `)文本(` | 云形 |
| `))文本((` | 爆炸形 |
| `{{文本}}` | 六边形 |

**规范**：用缩进表示层级，保持一致的缩进风格（2或4空格），每级节点不超过7个

**常见问题**：缩进必须一致（空格或Tab不能混用），特殊字符用引号包裹。详见 `resources.md`。
