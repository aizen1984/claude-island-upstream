# cc-sls-query 查询模板

> 从 SKILL.md 拆分的查询模板集。按场景分类。

---

## SLS 查询语法

SLS 查询语句由**搜索语句**和可选的 **SQL 分析语句**组成，用管道符 `|` 分割：

```
搜索语句 | SQL分析语句
```

- 搜索语句可单独使用（过滤日志）
- SQL 分析语句必须跟在搜索语句后（统计分析）
- SQL 部分不需要 FROM 和 WHERE 子句，默认分析当前 logStore

### 搜索语法

| 语法 | 说明 | 示例 |
|------|------|------|
| `field:value` | 字段精确匹配 | `level:ERROR` |
| `and` | 与（默认） | `level:ERROR and context:vipship` |
| `or` | 或 | `level:ERROR or level:WARN` |
| `not` | 非 | `not level:INFO` |
| `()` | 优先级 | `(context:vipship or context:bettercds) and level:ERROR` |
| `""` | 短语/特殊字符 | `msg1:"connection refused"` |
| `*` `?` | 通配符（仅词中间或末尾） | `msg1:timeout*`、`host:vipship-a-?` |
| `>` `>=` `<` `<=` | 数值比较 | `request_time>50` |
| `in` | 范围（必须小写） | `status in [500 599]` |
| `field:*` | 字段存在 | `stackTrace:*`（有堆栈的日志） |
| `not field:*` | 字段不存在 | `not stackTrace:*` |

### 常用字段拼接规则

**仅当用户未手动指定 query 时**，按以下规则拼接。使用 ` and ` 连接各条件：

| 参数 | query 片段 |
|------|-----------|
| context | `context:{应用名}` |
| appVersion | `appVersion: {制品号}` |
| level | `level:{ERROR/WARN/INFO/DEBUG}` |
| traceId | `traceId:{追踪ID}` |
| host | `host:{主机名}` |
| grayLane | `grayLane:{灰度组}` |

**日志等级映射**：`"错误"/"error" → ERROR`、`"警告"/"warn" → WARN`、`"信息"/"info" → INFO`、`"调试"/"debug" → DEBUG`

### 查询注意事项

- 通配符 `*` `?` 不能放在词开头（`*abc` 无效）
- `in` 必须小写，`AND`/`OR`/`NOT` 大小写均可
- 短语查询用双引号：`msg1:"file not found"`
- SQL 部分默认返回 100 行，需要更多用 `LIMIT`
- 字段名含特殊字符需双引号包裹：`"request-method":GET`

---

## 常用分析查询模式（搜索 | SQL）

| 场景 | query |
|------|-------|
| 统计 ERROR 数量 | `context:vipship and level:ERROR \| SELECT count(*) as cnt` |
| 按类分组 TOP10 | `context:vipship and level:ERROR \| SELECT logger, count(*) as cnt GROUP BY logger ORDER BY cnt DESC LIMIT 10` |
| 按时间趋势 | `context:vipship and level:ERROR \| SELECT date_format(from_unixtime(__time__), '%H:%i') as t, count(*) as cnt GROUP BY t ORDER BY t` |
| 关键词搜索 | `context:vipship and msg1:NullPointerException` |
| 模糊匹配 | `context:vipship and msg1:timeout*` |
| 排除干扰 | `context:vipship and level:ERROR not msg1:heartbeat` |
| 有堆栈的错误 | `context:vipship and level:ERROR and stackTrace:*` |
| 多应用查询 | `(context:vipship or context:bettercds) and level:ERROR` |
| SQL like 模糊 | `context:vipship \| SELECT * FROM log WHERE msg1 like '%OutOfMemory%'` |

---

## 场景示例

### 场景 1: 查询应用错误日志
```
用户: 查询生产环境数禾集群 bettercds 应用的错误日志，最近1小时

处理流程:
1. 环境: 生产 → prod → project: huanbei-prod-logs
2. 集群: 数禾 → logStore: spring-syslog
3. 生成 query: context:bettercds and level:ERROR
4. 时间范围: 最近1小时
5. 调用 sls_execute_sql_query
6. 展示结果
```

### 场景 2: 查询 k8s 事件
```
用户: 查询 sit 环境重庆小贷集群的 k8s 事件

处理流程:
1. 环境: sit → project: huanbei-sit-logs
2. 日志类型: k8sevent → logStore: k8s-events
3. query: 不生成（非应用日志）
4. 时间范围: 默认最近15分钟
5. 调用 sls_execute_sql_query
6. 展示结果
```

### 场景 3: 通过 TraceId 查询
```
用户: 查询生产环境数禾集群 traceId 为 abc123 的日志

处理流程:
1. 环境: 生产 → prod → project: huanbei-prod-logs
2. 集群: 数禾 → logStore: spring-syslog
3. 生成 query: traceId:abc123
4. 时间范围: 默认最近15分钟
5. 调用 sls_execute_sql_query
6. 展示结果
```
