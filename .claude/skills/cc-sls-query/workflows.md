# cc-sls-query 工作流程

> 从 SKILL.md 拆分的详细工作流程。核心概念见 [SKILL.md](SKILL.md)。

---

## 前置检查

执行查询前，先确认阿里云 SLS MCP 服务可用（检查 `mcp__sh_aliyun_observability__sls_execute_sql_query` 工具是否存在）。

如果 MCP 服务不可用，提示用户添加配置：

```json
"sh_aliyun_observability": {
  "type": "sse",
  "url": "http://mcp.dmz.prod.caijj.net/mcp/sh_aliyun_observability",
  "headers": {
    "X-CJJ-MCP-API-KEY": "用户Token，在智能平台上面申请",
    "x-cjj-mcp-name": "sh_aliyun_observability"
  }
}
```

## 参数解析

从用户自然语言输入中提取以下参数：

**必需参数**：
- **环境** (environment)：开发/sit/预发/生产
- **集群** (cluster)：数禾/重庆小贷/中禾信
- **日志类型** (logType)：应用日志/k8s事件/k8s日志（默认：应用日志）

**可选参数**（仅应用日志）：
- **应用** (context)：应用名称
- **制品号** (appVersion)：制品版本号
- **日志等级** (level)：ERROR/WARN/INFO/DEBUG
- **TraceId** (traceId)：链路追踪 ID
- **主机** (host)：Pod 主机名
- **灰度组** (grayLane)：灰度组名称

**可选参数**（所有日志类型）：
- **时间范围**：起始时间 / 结束时间（默认最近 15 分钟）
- **手动 query**：用户自定义查询语句（优先级最高）

## 环境映射

| 用户输入 | 标准值 | project |
|---------|--------|---------|
| "开发环境", "开发", "dev" | dev | huanbei-dev-log-test |
| "sit" | sit | huanbei-sit-logs |
| "pre", "预发", "预发布" | pre | huanbei-pre-logs |
| "生产", "生产环境", "prod" | prod | huanbei-prod-logs |

## 集群映射

| 用户输入 | 标准值 |
|---------|--------|
| "数禾", "shuhe" | 数禾 |
| "重庆小贷", "cqxd" | 重庆小贷 |
| "中禾信", "zhx" | 中禾信 |

## 操作分发

收到 `$ARGUMENTS` 后，判断用户意图并选择对应 MCP 工具：

| 用户意图 | MCP 工具 | 说明 |
|----------|---------|------|
| 查询日志（给了具体参数） | `mcp__sh_aliyun_observability__sls_execute_sql_query` | 核心查询 |
| 自然语言描述查询需求 | `mcp__sh_aliyun_observability__sls_translate_text_to_sql_query` → 再执行查询 | 先翻译再执行 |
| 不确定 logStore 结构/字段 | `mcp__sh_aliyun_observability__sls_describe_logstore` | 查看索引字段 |
| 不确定有哪些 logStore | `mcp__sh_aliyun_observability__sls_list_logstores` | 列出日志库 |
| 查询报错需诊断 | `mcp__sh_aliyun_observability__sls_diagnose_query` | 诊断查询语法 |

### 核心查询参数

```
工具: mcp__sh_aliyun_observability__sls_execute_sql_query
参数:
  - project: 环境映射得到的 project
  - logStore: logStore 计算得到的值
  - query: 拼接或用户手动指定的查询语句
  - fromTimestampInSeconds: 开始时间戳（秒）
  - toTimestampInSeconds: 结束时间戳（秒）
  - regionId: cn-beijing（固定值）
```

### 时间处理

- 用户指定时间时，使用 `Bash(date -j -f "%Y-%m-%d %H:%M:%S" "2025-11-26 09:40:00" +%s)` 转换为时间戳
- 用户说"最近N分钟/小时"时，用 `Bash(date +%s)` 获取当前时间戳后计算
- 未指定时间时，默认查询最近 15 分钟

## 完整工作流

1. **前置检查**：确认 SLS MCP 服务可用，不可用则输出配置指南
2. **解析意图**：从 `$ARGUMENTS` 提取环境、集群、日志类型、过滤条件
3. **参数缺失处理**：必需参数缺失时，友好提示用户补充
4. **计算 project 和 logStore**：按映射表计算
5. **生成 query**：按拼接规则生成（或使用用户手动指定的 query）
6. **确认参数**：展示将要使用的参数供用户确认
7. **执行查询**：调用 MCP 工具
   - **成功**（无 error 字段）→ Step 8
   - **失败** → 跳转「错误恢复」章节按错误类型查策略 → 应用策略后回到 Step 5（重新生成 query）重试
   - **重试上限**：2 次。仍失败则向用户报告原始错误 + 已尝试的恢复策略 + 错误恢复表中的人工建议
8. **展示结果**：格式必须为「查询参数在上，数据在下」：
   ```
   **查询参数：**
   - 环境：生产（huanbei-prod-logs / spring-syslog）
   - 时间：2026-03-24 10:00 ~ 11:00
   - Query：`context:vipship and level:ERROR`

   **结果（共 N 条）：**
   | logtime | context | level | msg1 | logger | host |
   |---------|---------|-------|------|--------|------|
   ```
   - 必须回显实际使用的 Query（便于验证）
   - 优先展示列：`logtime`、`context`、`level`、`msg1`、`logger`、`host`
   - `stackTrace` 内容长，只展示第一行，完整内容放代码块
   - 结果 > 20 条时，优先展示统计摘要（GROUP BY logger），而非列出全部原始日志
   - 结果为 0 条时，主动建议：放宽时间范围 / 去掉 level 过滤 / 检查应用名拼写

### 错误恢复

| 错误场景 | 恢复策略 |
|---------|---------|
| `Column xxx can not be resolved` | 调 `sls_describe_logstore` 查索引字段 → 重构 query |
| 查询语法错误 | 调 `sls_diagnose_query` 诊断 → 修正后重试 |
| 查询超时 | 分级缩减：先缩到 15 分钟 → 仍超时则加 context 过滤 → 仍超时则改用 SQL 聚合代替全量搜索 |
| 结果为空 | 检查应用名拼写 → 放宽 level 过滤 → 扩大时间范围 |
| 权限/认证错误（401/SessionExpired） | 提示用户重启 Claude Code 会话（SSE session 过期），如仍失败则去智能平台刷新 Token |
| project/logStore 不存在 | 调 `sls_list_logstores` 确认可用列表，对比映射表 |
| MCP 服务不可用 | 输出配置指南 |

## 模糊问题排查策略

当用户描述模糊时，**主动构造侦察查询**，不要等用户补充完整信息。

### 切入点决策树

| 用户描述包含 | 搜索策略 |
|-------------|---------|
| 异常类型（timeout、NPE、refused） | 搜 `msg1` 字段 |
| 异常堆栈（Exception、Error 类名） | 搜 `stackTrace` 字段 |
| 业务 ID（订单号、用户 ID、流水号） | 搜 `msg1` 或 `uid` 字段 |
| TraceId | 搜 `traceId` 字段，**不加 context 限制**（跨应用） |
| 特定 Pod / 实例 | 搜 `host` 字段 |
| 灰度场景 | 搜 `grayLane` 字段 |
| 完全不明确 | 先查 `level:ERROR`，再 GROUP BY logger 定位模块 |

### 常见模糊场景→查询策略

| 用户说 | 第一步查询 |
|-------|-----------|
| "为什么超时" | `level:ERROR and (msg1:timeout* or msg1:"read timed out" or msg1:"connection refused")` |
| "有没有 NPE/OOM" | `level:ERROR and stackTrace:NullPointerException` / `stackTrace:OutOfMemoryError` |
| "生产有没有问题" | `level:ERROR \| SELECT logger, count(*) as cnt GROUP BY logger ORDER BY cnt DESC LIMIT 10` |
| "查一下这个用户" | `uid:{用户ID}` 或 `msg1:{用户ID}` |
| "灰度有没有问题" | `level:ERROR and grayLane:{灰度组名}` |
| "某 Pod 挂了" | `host:{Pod名}* and level:ERROR` |

### 跨应用链路排查

1. 用 `traceId:{值}` **不带 context 限制**，查所有应用的该链路日志
2. 按 `__time__` 排序还原调用时序
3. 找到第一个 ERROR 的应用和 spanId，即为故障点
4. 如需补全链路细节，可配合 ARMS trace 查询
