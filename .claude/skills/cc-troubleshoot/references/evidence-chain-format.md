# 证据链追踪格式

> cc-troubleshoot skill 的证据链追踪规范。INVESTIGATE 阶段和 GATHER 阶段加载。

---

## 一、Evidence Item 格式

每条查询/分析操作记录为一个 Evidence Item，格式如下：

```
### [类型-序号] 标题

- **输入来源**:
  - 参数1: 值 ← 来源（evidence ID / 用户输入 / 假设 HN）
  - 参数2: 值 ← 来源
- **查询/操作**:
  ```
  实际执行的查询语句 或 file:line 引用
  ```
- **预期结果**: 基于假设，预期应该看到什么
- **实际结果**: 实际观察到的数据（关键字段摘要）
- **结论**: 证实 HN / 否定 HN / 引出新线索 → 下一步 evidence ID
```

### 类型前缀

| 前缀 | 含义 | 来源工具 |
|------|------|---------|
| SLS | SLS 日志查询 | cc-sls-query MCP tools |
| SQL | 数据库查询 | sql skill scripts |
| CFG | 配置查询 | cfg skill scripts |
| CODE | 源码分析 | Read/Grep/Glob |
| VAULT | 知识库检索 | Vault L0/L1/L2 |

### 输入来源标注规则（强制）

- 每个查询参数必须标注 `← {来源}`
- 合法来源：`用户输入`、`假设 HN`、`{evidence ID} 结果`、`{evidence ID}.{字段名}`
- **禁止**出现来源不明的参数——如果参数来源不清楚，先标注 `← ❓待确认`，在 VERIFY 阶段补全

---

## 二、假设编号

排障开始时形成的假设使用 `H1, H2, H3...` 编号：

```
**初始假设**：
- H1: [最可能] 退款渠道返回失败
- H2: [次可能] 数据库状态不一致
- H3: [低可能] 配置错误导致走错分支
```

每条 Evidence Item 的结论必须关联到假设（证实/否定/引出新假设）。

---

## 三、依赖链可视化

GATHER 阶段必须输出证据依赖链的箭头图：

```
SLS-1（ERROR日志）
  ├─→ SQL-1（查订单状态）← uid, orderId from SLS-1
  │     └─→ CODE-1（确认状态枚举）← status=3 from SQL-1
  └─→ SLS-2（traceId追踪）← traceId from SLS-1
        └─→ CODE-2（渠道调用逻辑）← 异常类 from SLS-2
              └─→ CFG-1（渠道配置）← configKey from CODE-2
```

---

## 四、完整示例

### 场景：用户退款失败

**初始假设**：
- H1: 退款渠道返回拒绝
- H2: 订单状态不允许退款
- H3: 退款金额校验失败

---

### [SLS-1] 查询退款 ERROR 日志

- **输入来源**:
  - context: vipship ← 用户输入
  - level: ERROR ← 排障标准（先查错误）
  - time: 2026-03-30 10:00~11:00 ← 用户输入
  - 关键词: "退款" ← 用户输入
- **查询**:
  ```
  context:vipship and level:ERROR and msg1:"退款"
  | SELECT logtime, msg1, uid, traceId, stackTrace LIMIT 20
  ```
- **预期结果**: 找到退款相关的 ERROR 日志
- **实际结果**: 3 条记录，uid=123456, orderId=ORD789, traceId=abc123def, msg1="退款失败: 渠道返回余额不足"
- **结论**: 初步证实 H1（渠道拒绝），需进一步确认数据库状态 → SQL-1

---

### [SQL-1] 查询退款订单状态

- **输入来源**:
  - uid: 123456 ← SLS-1.uid
  - order_id: ORD789 ← SLS-1.orderId（从 msg1 解析）
- **查询**:
  ```sql
  SELECT id, uid, order_id, refund_status, refund_amount, channel_code,
         create_time, update_time
  FROM refund_order
  WHERE uid = 123456 AND order_id = 'ORD789'
  ```
- **预期结果**: refund_status 应为失败状态
- **实际结果**: refund_status=3, refund_amount=5000, channel_code='ALIPAY', update_time='2026-03-30 10:15:23'
- **结论**: 数据库确认退款失败（status=3），需确认枚举含义 → CODE-1

---

### [CODE-1] 确认退款状态枚举

- **输入来源**:
  - refund_status=3 ← SQL-1.refund_status
- **操作**:
  ```
  RefundStatusEnum.java:45 — CHANNEL_REJECTED(3, "渠道拒绝")
  ```
- **预期结果**: status=3 对应渠道拒绝
- **实际结果**: 确认 3=CHANNEL_REJECTED
- **结论**: ✅ 证实 H1。数据库状态与日志一致，渠道确实拒绝了退款 → SLS-2 追踪完整调用链

---

### [SLS-2] traceId 跨应用追踪

- **输入来源**:
  - traceId: abc123def ← SLS-1.traceId
  - **注意**: 不加 context 过滤，跨应用追踪
- **查询**:
  ```
  traceId:abc123def | SELECT logtime, context, level, msg1 ORDER BY logtime
  ```
- **预期结果**: 看到完整调用链，包含渠道交互细节
- **实际结果**: 5 条记录，调用链 vipship → payment-gateway → alipay-channel，alipay-channel 返回 "INSUFFICIENT_BALANCE"
- **结论**: ✅ 根因确认——支付宝渠道返回余额不足。→ CODE-2 确认重试逻辑

---

### [CODE-2] 确认渠道失败处理逻辑

- **输入来源**:
  - 渠道返回码: INSUFFICIENT_BALANCE ← SLS-2 结果
- **操作**:
  ```
  ChannelRefundHandler.java:128 — handleRefundResponse()
  ChannelRefundHandler.java:156 — 判断 responseCode 是否在 retryableCodeList 中
  ```
- **预期结果**: INSUFFICIENT_BALANCE 不在可重试列表中
- **实际结果**: 确认 INSUFFICIENT_BALANCE 被归类为终态失败，不重试
- **结论**: ✅ 代码逻辑正确，退款失败是合理的业务结果

---

### 证据依赖链

```
SLS-1（ERROR日志: 退款失败）
  ├─→ SQL-1（订单状态: refund_status=3）← uid, orderId from SLS-1
  │     └─→ CODE-1（枚举确认: 3=CHANNEL_REJECTED）← status from SQL-1
  └─→ SLS-2（traceId追踪: 渠道返回 INSUFFICIENT_BALANCE）← traceId from SLS-1
        └─→ CODE-2（处理逻辑: 终态失败不重试）← responseCode from SLS-2
```

### 交叉验证

| 结论 | 证据来源 | 验证状态 |
|------|---------|---------|
| 退款被渠道拒绝 | SLS-1 + SQL-1 + CODE-1 | ✅ 已验证（3 源） |
| 拒绝原因是余额不足 | SLS-2 + CODE-2 | ✅ 已验证（2 源） |
| 系统处理逻辑正确 | CODE-2 | ❓ 单源（需确认是否应支持重试） |
