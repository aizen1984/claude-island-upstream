# 逆向文档生成工作流（/reverse-engineer）

## 目标

从现有代码生成 PRD 和技术文档，填补文档缺失。

**核心原则**：推断标记，验证确认，**quote grounding 三件套强制落地**

> ⚠️ 所有文档输出必须遵循 [../templates.md](../templates.md) 中的「文档表达原则」：一句话先行、结构可视化、表格优于段落、粗体做路标。文档开头必须包含「快速熟悉」章节。

---

## ⛔ Quote Grounding 三件套（强制，全工作流贯穿）

本工作流遵守 `shared-rules/data-report-protocol.md` 的 quote grounding 协议。**frontmatter 声明 ≠ 落地，必须在每个 Phase 产出中物理执行以下三件套：**

| 件数 | 机制 | 触发时机 | 示例 |
|------|------|---------|------|
| ① `<quote file line>` | 每条 `[推断]` / `[确定]` 结论必须附代码原文引用 | Phase 2 PRD / Phase 3 技术文档 / Phase 3.5 图表备注 | `[推断] 订单创建幂等 <quote file="OrderServiceImpl.java" line="45">if (orderMapper.selectByBizNo(bizNo) != null) return existing;</quote>` |
| ② `<no-match>` 声明 | 某类结论找不到代码依据时必须显式声明，不允许沉默省略 | Phase 4 一致性检查 / 待确认清单 | `<no-match reason="取消订单后的库存回退在代码中未发现对应逻辑">库存回退机制</no-match>` |
| ③ `[REMOVED:no-quote]` 标记 | Phase 4 自审时，扫描所有 `[推断]`，**无 quote 的一律改成 `[REMOVED:no-quote]` 并移入待确认清单** | Phase 4 自审阶段强制执行 | `~~[推断] 订单锁定时长 30 分钟~~ → [REMOVED:no-quote] 原推断无代码支持` |

**硬约束**：
- Phase 2/3/3.5 的任何 `[推断]` 或 `[确定]` 结论**必须**同行附 `<quote file="..." line="...">原文</quote>`，否则不得进入 Phase 4
- Phase 4 自审是强制阶段，**不可跳过**；自审未通过不得进入 Phase 5
- 正向设计路径**不受约束**（设计来自需求，无代码源头）

---

## 工作流程总览

```
Phase 1: 范围发现 → Phase 2: PRD 生成 → Phase 3: 技术文档生成 → Phase 3.5: 图表生成 → Phase 4: 代码验证 → Phase 5: 输出验证
```

---

## 逆向复杂度分级

| 规模 | 判定条件 | Phase 路径 |
|------|---------|-----------|
| 小型 | 单 Service/单入口，≤5 文件 | Phase 1 范围发现 → Phase 3 技术文档 → Phase 5 输出（跳过 PRD 和图表） |
| 中型 | 单模块多 Service，6-15 文件 | 完整 6 Phase |
| 大型 | 跨模块，>15 文件 | 完整 6 Phase + cc-api-analyzer 深度集成 |

> 逆向文档目的若为"给新人看"（文档化），完成后不委托 cc-planner；若为"准备重构"，委托 cc-planner 拆解任务。

---

## 强制任务跟踪

工作流启动时创建所有 Phase 任务：

```javascript
TaskCreate({ subject: "发现代码范围", activeForm: "正在发现代码范围", ... })
TaskCreate({ subject: "生成逆向 PRD", activeForm: "正在生成逆向 PRD", ... })
TaskCreate({ subject: "生成技术文档", activeForm: "正在生成技术文档", ... })
TaskCreate({ subject: "生成 Mermaid 图表", activeForm: "正在生成图表", ... })
TaskCreate({ subject: "验证代码一致性", activeForm: "正在验证代码一致性", ... })
TaskCreate({ subject: "输出并验证文档", activeForm: "正在输出逆向文档", ... })
```

每个 Phase 开始前 `TaskUpdate(in_progress)`，完成后 `TaskUpdate(completed)`。

---

## Phase 1: 范围发现

### 入口点识别

```yaml
Java 后端入口点:
  1. Controller 类
  2. @Scheduled 定时任务
  3. MQ 消费者
  4. RPC 接口

分析顺序: Controller → Service → Repository → Entity
```

### 依赖分析输出

```markdown
### 入口点
| 类型 | 类名 | 职责 |
|------|------|------|

### 核心类调用链
```
OrderController
    ├── OrderService (核心业务)
    │       ├── OrderRepository
    │       ├── UserService
    │       └── PaymentService
    └── OrderDTO
```

### 范围确认
| # | 文件 | 类型 | 重要性 |
|---|------|------|--------|
```

详细 Scope Discoverer 提示词见 [../prompts.md](../prompts.md)

### 失败处理

| 失败场景 | 处理方式 |
|---------|---------|
| 未找到入口点 | 扩大搜索范围（包路径、注解扫描），仍无结果则询问用户指定入口 |
| 调用链过深（>5 层） | 截断分析，标记深层依赖为"待展开"，询问用户是否继续 |
| 代码混淆/无法解析 | 标记为"不可分析"，基于可分析部分继续 |

---

## Phase 2: PRD 生成

### 功能推断策略

```yaml
推断来源:
  1. 类名和方法名 → 功能目的
  2. API 路径和参数 → 用户操作
  3. 业务逻辑代码 → 业务规则
  4. 异常处理 → 边界条件
  5. 注释和日志 → 补充说明

标记规则:
  确定: 直接从代码获取
  推断: 根据代码推测（需确认）
  待确认: 无法确定（需业务方确认）
```

### PRD 生成模板

> ⛔ 每条 `[确定]` / `[推断]` 结论**必须**附 `<quote file="..." line="...">原文片段</quote>`；找不到原文的打 `[REMOVED:no-quote]` 并移入待确认清单（见文件顶部"Quote Grounding 三件套"）。

```markdown
# [功能名称] PRD（逆向生成）

> 本文档由代码逆向生成，标记 [推断] 的内容需要业务方确认
> Quote Grounding: 所有结论均附代码原文引用，无引用的条目已打 [REMOVED:no-quote] 移入待确认清单

## 1. 功能概述
- [确定] 创建订单的入口是 POST /api/orders <quote file="OrderController.java" line="28">@PostMapping("/api/orders") public Result create(@RequestBody OrderDTO dto)</quote>
- [推断] 业务目的是支撑 C 端下单主流程 <quote file="OrderController.java" line="15">// 订单中心 - 对外 HTTP 门面</quote>

## 2. 用户场景
#### 场景 1: 创建订单
**触发**: 用户点击「下单」 <quote file="OrderController.java" line="28">@PostMapping("/api/orders")</quote>
**流程**: 校验用户 → 检查库存 → 创建订单 → 发 MQ <quote file="OrderServiceImpl.java" line="45-72">userService.checkUser(); productService.checkStock(); orderMapper.insert(order); orderMQ.sendCreated(order);</quote>
**结果**: 返回订单号 <quote file="OrderServiceImpl.java" line="75">return Result.success(order.getOrderNo());</quote>

## 3. 业务规则
### [确定] 从代码提取的规则
| 规则 | 代码位置 | 原文引用 |
|------|---------|---------|
| 订单创建幂等 | `OrderServiceImpl:45` | `<quote file="OrderServiceImpl.java" line="45">if (orderMapper.selectByBizNo(bizNo) != null) return existing;</quote>` |
| 库存扣减失败整单回滚 | `OrderServiceImpl:60` | `<quote file="OrderServiceImpl.java" line="60">catch (StockException e) { throw new BizException("库存不足"); }</quote>` |

### [待确认] / [REMOVED:no-quote] 不确定的规则
| 问题 | 相关代码 | 状态 | 可能的解释 |
|------|---------|------|-----------|
| quantity 默认值是否为 1？ | `OrderServiceImpl:45` | [待确认] | 代码无显式默认值 |
| ~~订单锁定时长 30 分钟~~ | N/A | **[REMOVED:no-quote]** | 原推断无代码支持，移入待确认 |

## 4. 待确认清单
| # | 问题 | 优先级 | 备注 | 状态 |
|---|------|--------|------|------|
| 1 | quantity 默认值是否为 1？ | 中 | 代码未给默认 | [待确认] |
| 2 | 订单锁定时长是否为 30 分钟？ | 中 | Phase 4 自审无 quote 依据 | [REMOVED:no-quote] |
```

### 失败处理

| 失败场景 | 处理方式 |
|---------|---------|
| 推断信息不足 | 标记为"待确认"比例超过 50% 时，暂停并请求用户补充业务上下文 |
| 功能边界模糊 | 提供 2-3 种边界划分方案，请用户选择 |

---

## Phase 3: 技术文档生成

### API 文档生成

```markdown
## API 文档（逆向生成）

### 接口清单
| 方法 | 路径 | 描述 | 状态 |
|------|------|------|------|
| POST | /api/orders | 创建订单 | [确定] |

### POST /api/orders
**来源**: `OrderController.createOrder()`

**请求参数**:
| 字段 | 类型 | 必填 | 说明 | 来源 |
|------|------|------|------|------|
| userId | Long | 是 | 用户ID | [确定] @RequestBody |

**业务逻辑**:
1. 校验用户存在 (`UserService.checkUser()`)
2. 校验库存充足 (`ProductService.checkStock()`)
3. 创建订单记录 (`OrderRepository.insert()`)

**异常情况**:
| 异常码 | 触发条件 | 来源 |
|--------|---------|------|
| 1001 | 用户不存在 | [确定] |
```

### 数据模型文档

> ⛔ 每个字段的 `[确定]` / `[推断]` 必须在「原文引用」列给出 `<quote file line>`；无引用的字段一律标 `[REMOVED:no-quote]` 并移入待确认清单。

```markdown
## 数据模型（逆向生成）

### Order 表
**来源**: `Order.java` + `order` 表

| 字段 | 类型 | 说明 | 状态 | 原文引用 |
|------|------|------|------|---------|
| id | bigint | 主键 | [确定] | `<quote file="Order.java" line="12">@Id @GeneratedValue private Long id;</quote>` |
| user_id | bigint | 用户ID | [确定] | `<quote file="Order.java" line="15">@Column(name="user_id") private Long userId;</quote>` |
| created_at | datetime | 创建时间 | [确定] | `<quote file="Order.java" line="22">@CreatedDate @Column(name="created_at") private LocalDateTime createdAt;</quote>` |
| ~~deleted_flag~~ | ~~tinyint~~ | ~~软删除~~ | **[REMOVED:no-quote]** | 代码中未发现 @Column 或字段定义，原推断移入待确认 |

**索引**:
- [确定] PRIMARY KEY (id) <quote file="Order.java" line="12">@Id @GeneratedValue</quote>
- [推断] idx_user_id (user_id) <quote file="OrderMapper.xml" line="34">WHERE user_id = #{userId}</quote>（高频 WHERE 条件推断必有索引，需 DBA 确认）
- <no-match reason="未在 DDL / Mapper 中发现 order_no 查询">idx_order_no</no-match>
```

### 失败处理

| 失败场景 | 处理方式 |
|---------|---------|
| 表结构无法获取 | 标记为"待补充"，基于 Entity 类推断表结构 |
| 接口参数推断不准确 | 标记为"推断"，附代码位置供确认 |

---

## Phase 3.5: 图表生成（委托 cc-diagram）

> Phase 3 技术文档完成后，委托 cc-diagram 生成 Mermaid 图表嵌入逆向文档。规则与正向设计工作流的 Phase 3.5 相同，参见 [workflows-forward.md](workflows-forward.md)「Phase 3.5: 图表生成」章节。

### 逆向场景差异

- 图表数据来源为**代码分析结果**而非需求设计，需在图表备注中标注 `[逆向生成]`
- 类图中标注 `[确定]`（代码直接提取）和 `[推断]`（推断的关系）
- ER 图中的表关系如果是推断的，备注标注 `[推断]`

---

## Phase 4: 代码验证（含 Quote Grounding 自审）

### ⛔ 自审阶段（强制，先自审后一致性检查）

**目的**：强制扫描 Phase 2/3 产出的所有 `[推断]` / `[确定]` 结论，确认每一条都有 `<quote file line>` 支撑；无支撑的条目按以下规则处理。

**自审执行步骤**：

1. `Grep -rn "\[推断\]|\[确定\]" <本次逆向产出文档>` 列出所有标注条目
2. 对每一条检查右侧是否有 `<quote file="..." line="...">` 标签
3. **无 quote 的处理规则**：
   - 改写为 `[REMOVED:no-quote]` 标记，加删除线 `~~原内容~~`
   - 同步追加到 `### 待确认清单` 下，优先级默认为"中"
   - 若属于整类缺失（例如"所有异常处理"都无引用），补一条 `<no-match reason="...">类别名</no-match>` 声明
4. 产出「Quote Grounding 自审报告」（见下方模板）

### Quote Grounding 自审报告（模板）

```markdown
### Quote Grounding 自审报告

| 指标 | 数值 |
|------|------|
| 总 [推断] 条数 | 12 |
| 总 [确定] 条数 | 18 |
| 附 quote 条数 | 27 |
| [REMOVED:no-quote] 条数 | 3 |
| <no-match> 声明条数 | 1 |
| Grounding 覆盖率 | 27/30 = 90% |

**未通过项（移入待确认清单）**：
- [REMOVED:no-quote] ~~订单锁定时长 30 分钟~~ — 原推断无代码支持
- [REMOVED:no-quote] ~~deleted_flag 字段用于软删除~~ — 代码中未发现字段定义
- [REMOVED:no-quote] ~~订单取消后自动退款~~ — 未在 OrderService 找到退款调用

**类别缺失**：
- <no-match reason="OrderService 中未发现任何 try-catch 细分异常码">异常码体系</no-match>

**通过判据**：
- Grounding 覆盖率 ≥ 80% 方可进入 Phase 5
- < 80% 必须返回 Phase 2/3 补充原文引用或主动删除推断
```

### 一致性检查

```markdown
## 代码验证报告

### 一致性检查（含 Quote Grounding 维度）
| 检查项 | 状态 | 说明 | 原文依据 |
|--------|------|------|---------|
| API 路径 | 通过 | 与 Controller 一致 | `<quote file="OrderController.java" line="28">@PostMapping("/api/orders")</quote>` |
| 参数定义 | 通过 | 与 DTO 一致 | `<quote file="OrderDTO.java" line="12">private Long userId; private Long productId;</quote>` |
| 业务逻辑 | 警告 | 库存回退逻辑未找到 | `<no-match reason="OrderService 取消分支未调用 ProductService.rollbackStock">库存回退</no-match>` |
| Quote Grounding 覆盖率 | 通过 | 90% ≥ 80% 门槛 | 见"Quote Grounding 自审报告" |

### 待确认清单
| # | 问题 | 相关代码 | 状态 | 优先级 |
|---|------|---------|------|--------|
| 1 | quantity 默认值是否为 1？ | `OrderServiceImpl:45` | [待确认] | 中 |
| 2 | 订单锁定时长 30 分钟？ | N/A | [REMOVED:no-quote] | 中 |
| 3 | deleted_flag 软删除？ | N/A | [REMOVED:no-quote] | 低 |

### 不确定推断（已通过自审的 [推断]）
| 推断内容 | 依据 | 原文引用 | 置信度 |
|---------|------|---------|--------|
| idx_user_id 存在 | 高频 WHERE | `<quote file="OrderMapper.xml" line="34">WHERE user_id = #{userId}</quote>` | 高 |

### 验证结论
- **完成度**: 85%
- **Grounding 覆盖率**: 90%（阈值 80%，通过）
- **待确认项**: 3 项（含 2 个 [REMOVED:no-quote]）
- **建议**: 与业务方确认待确认清单后定稿
```

### 失败处理

| 失败场景 | 处理方式 |
|---------|---------|
| 一致性检查大量不通过（>30%） | 暂停输出，返回 Phase 3 修正文档 |
| 代码变更频繁（分析期间代码被修改） | 提示用户在稳定分支上重新分析 |

---

## Phase 5: 输出验证

> 输出确认流程同设计文档工作流 Phase 5，见 [workflows-forward.md](workflows-forward.md)

---

## 与 cc-api-analyzer 集成

```yaml
从 cc-api-analyzer 复用:
  - 接口追踪能力
  - 表关系分析
  - 调用链分析

扩展能力:
  - PRD 推断生成
  - 业务规则提取
  - 待确认清单
```

调用方式：
1. 使用 cc-api-analyzer 分析接口 → 获取 API 清单、调用链、表关系
2. 基于分析结果生成 PRD → 推断功能目的、用户场景
3. 生成技术文档 → 补充 cc-api-analyzer 未覆盖的内容
4. 验证并标记不确定项

### 委托失败恢复

| 委托目标 | 失败场景 | 恢复策略 |
|---------|---------|---------|
| cc-api-analyzer | 接口分析超时或失败 | 降级为手动接口文档编写，标记为"待补充" |
| cc-diagram | 图表生成失败 | 使用文字描述替代，标记为"待补图" |
| cc-planner | 任务拆解失败 | 输出设计文档，提示用户手动使用 planner |

---

## 输出示例

```markdown
# OrderService 逆向文档

## 快速熟悉（3 分钟读完）

### 一句话概括

订单服务负责 **订单全生命周期管理**（创建 → 支付 → 履约 → 取消），通过 **OrderService** 调度，依赖 UserService（用户校验）、ProductService（库存扣减）、MQ（异步通知）。

### 核心架构

```
触发源（HTTP / MQ / Job）
    ↓
OrderController（3 个 HTTP 接口）
    ↓
OrderService（业务调度）
├── UserService.getUser()       ← [外部] 用户校验
├── ProductService.checkStock() ← [外部] 库存检查
├── OrderRepository.insert()    ← 数据持久化
└── OrderMQ.sendCreated()       ← [MQ] 异步通知
        ↓
OrderJob.cleanExpired()         ← [定时] 每天 02:00 清理过期订单
OrderConsumer.onPaySuccess()    ← [MQ] 支付成功回调
```

### 代码全景

| 维度 | 概要 |
|------|------|
| 入口点 | **3 个**（HTTP 1 + Job 1 + MQ Consumer 1） |
| 核心类 | **6 个**（Controller/Service/ServiceImpl/Repository/Entity/DTO） |
| 数据表 | **2 张**（order_main + order_detail） |
| 外部依赖 | **3 个**（UserService、ProductService、Redis） |

### 关键发现

1. **策略模式缺失** [推断]：所有订单类型走同一个 if-else 分支，可能需要重构
2. **异步通知** [确定]：订单创建后通过 MQ 发送通知，消费端是 OrderConsumer
3. **缓存策略** [推断]：订单详情缓存 30min，但未发现缓存失效的主动清理逻辑

> ⚠️ 待确认项共 **2 个**，详见下方"待确认清单"

---

## 范围

| # | 文件 | 类型 | 职责 |
|---|------|------|------|
| 1 | OrderController | Controller | **HTTP 入口**：3 个接口 |
| 2 | OrderService | Service 接口 | 业务抽象 |
| 3 | OrderServiceImpl | Service 实现 | **核心逻辑** |
| 4 | OrderRepository | Repository | 数据访问 |
| 5 | Order | Entity | 数据模型 |
| 6 | OrderDTO | DTO | 传输对象 |

## PRD 摘要

> **一句话**：为用户提供订单创建、查询、取消能力，支撑交易闭环

| 场景 | 触发 | 核心步骤 | 结果 |
|------|------|---------|------|
| 创建订单 | 用户下单 | 校验用户 → 检查库存 → 创建订单 → 异步通知 | 订单生成 |
| 查询订单 | 用户查看 | 读缓存/读库 → 返回详情 | 展示订单 |
| 取消订单 | 用户取消 | 状态校验 → 更新状态 → 库存回退 | 订单关闭 |

## API 清单

| 方法 | 路径 | 描述 | 来源 |
|------|------|------|------|
| POST | /api/orders | **创建订单** | [确定] |
| GET | /api/orders/{id} | 查询订单 | [确定] |
| PUT | /api/orders/{id}/cancel | 取消订单 | [确定] |

## 待确认清单

| # | 问题 | 优先级 | 相关代码 |
|---|------|--------|---------|
| 1 | quantity 默认值是否为 1？ | 中 | `OrderServiceImpl:45` |
| 2 | 订单消息是否异步发送？ | 低 | `OrderMQ.sendCreated()` |

## 下一步

请确认待确认清单，确认后生成最终文档。
```
