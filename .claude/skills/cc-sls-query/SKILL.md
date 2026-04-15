---
name: cc-sls-query
description: 查询阿里云SLS各环境日志（应用日志/k8s日志/k8s事件）。不做综合排障、不查数据库。用于生产日志排查、错误追踪、traceId检索
argument-hint: [查询描述，如"生产环境数禾 bettercds ERROR日志 最近1小时"]
allowed-tools: Read, Bash
---

# SLS 日志查询

## Overview

cc-sls-query 是一个**工具型 Skill**，通过阿里云 SLS MCP 服务查询数禾各环境的应用日志、k8s 日志和 k8s 事件。支持自然语言输入，自动完成环境映射、query 拼接和 MCP 工具调用。

## When to Use

**适用场景**：查询线上应用日志、通过 traceId 检索、查询 k8s 事件/日志、自然语言查询

**不适用场景**：

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 查看本地日志文件 | 直接用 Read 工具 | 本 Skill 通过 SLS MCP 查远程日志 |
| 查询数据库数据 | sql | 本 Skill 只查 SLS 日志，不查数据库 |
| ARMS 链路分析/火焰图 | ARMS 相关 MCP 工具 | 本 Skill 不做性能 profiling |
| 综合生产排障 | cc-troubleshoot | 本 Skill 只查日志，不做多源交叉验证 |

---

## 日志类型与 logStore 计算

**应用日志**：

| 集群 | logStore |
|-----|----------|
| 数禾 | spring-syslog |
| 重庆小贷 | spring-syslog-cqxd |
| 中禾信 | spring-syslog-zhx |

**k8s 事件/日志**：

| project | 日志类型 | logStore |
|---------|---------|----------|
| huanbei-prod-logs | k8sevent | k8s-events |
| huanbei-prod-logs | k8slog | k8s-logs |
| huanbei-pre-logs | k8slog | k8s-log |
| huanbei-sit-logs | k8sevent | k8s-events |
| huanbei-sit-logs | k8slog | k8s-logs |
| huanbei-dev-log-test | k8sevent | k8s-events |
| huanbei-dev-log-test | k8slog | k8s-logs |

## 日志字段说明（应用日志）

| 字段 | 含义 | 搜索用途 |
|------|------|---------|
| `msg1` | 日志正文（`log.info/warn/error` 输出的消息体） | 搜关键词、异常信息、业务描述 |
| `stackTrace` | 异常堆栈（仅异常日志有值） | 搜 Exception 类名；`stackTrace:*` 过滤有堆栈的日志 |
| `logger` | Java 类全限定名 | 定位出错模块；GROUP BY 统计 TOP 出错类 |
| `context` | 应用名（Spring 应用上下文名） | 精确到某个应用 |
| `level` | 日志等级：ERROR/WARN/INFO/DEBUG | 按严重程度过滤 |
| `traceId` | 分布式链路追踪 ID | 跨应用还原完整调用链（查询时**不加 context 限制**） |
| `uid` | 用户 ID（业务字段，日志中打印） | 定位特定用户的操作日志 |
| `host` | Pod 主机名 | 定位特定 Pod 的日志 |
| `grayLane` | 灰度泳道名 | 灰度发布时只查特定灰度组 |
| `appVersion` | 制品版本号 | 对比版本间错误差异 |
| `thread` | 线程名 | 异步任务、线程池问题排查 |
| `line` | 代码行号 | 配合 logger 快速定位代码位置 |
| `serverIP` / `nodeIP` | 服务 IP / 节点 IP | 网络层问题排查 |
| `logtime` | 可读时间（如 `2026-03-24 14:21:00.884`） | 展示用 |
| `__time__` | UNIX 时间戳（秒） | SQL 分析中的时间计算（需 `from_unixtime` 转换） |

---

## 资源加载指导

| 场景 | 加载文件 |
|------|---------|
| 查询流程/环境选择/集群路由 | [workflows.md](workflows.md) |
| 查询模板/示例 | [templates.md](templates.md) |
| 遇到需求模糊时 | `shared-rules/inquiry-protocol.md` |

## 协作关系

- **接收自**: user（直接查询请求）
- **委托给**: 无（独立工具 Skill）

## 安全规则

- **只读查询**：仅支持 SLS 日志查询，禁止修改日志配置
- **禁止写操作**：本 Skill 仅用于查询，禁止 Write/Edit 代码文件
- **区域固定**：所有查询使用 cn-beijing 区域
- **时间单位**：时间戳使用秒为单位
- **Query 格式**：严格遵循 SLS 查询语法

## Gotchas

> 从实际使用中积累的常见陷阱。每次发现新问题时追加。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 通配符 `*` 放在词开头（如 `*abc`） | 查询无效/报错 | 通配符只能放词中间或末尾 |
| 2 | traceId 查询时加了 context 限制 | 只看到单应用日志，丢失跨应用链路 | traceId 查询**不加 context 限制** |
| 3 | `in` 用大写 `IN` | 语法错误 | `in` 必须小写 |
| 4 | 查询结果为空就放弃 | 可能只是过滤条件太严 | 依次放宽：level → 时间范围 → 检查应用名拼写 |
| 5 | 401/SessionExpired 后反复重试 | 浪费时间 | 提示用户重启 Claude Code 会话或刷新 Token |
