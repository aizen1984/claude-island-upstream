# cc-api-analyzer 报告模板

> 数据契约（cc-api-analyzer → cc-diagram）的字段定义见 `shared-rules/data-contracts.md`，本文件仅保留报告模板。

---

# 单接口分析报告模板

## 接口分析：{Method}

### 基本信息

| 属性 | 值 |
|------|------|
| **Controller** | {ControllerName} |
| **方法** | {MethodName} |
| **HTTP** | {HttpMethod} |
| **路径** | {Path} |
| **文件** | {FilePath}:{LineNumber} |

### 方法签名

```java
{方法签名，包含注解}
```

### 调用链

```
{Controller}.{method}()
  → {Service1}.{method1}()
    → {Repository1}.{method1}()
    → {Service2}.{method2}()
      → {Repository2}.{method2}()
```

**调用深度**: {N} 层

### 涉及表

| 表名 | 操作 | 关键字段 | 备注 |
|------|------|---------|------|
| {table_name} | {SELECT/INSERT/UPDATE/DELETE} | {field1, field2} | {备注} |

### 业务逻辑描述

**核心职责**: {一句话描述}

**执行步骤**:
1. {步骤1}
2. {步骤2}

### 关键逻辑

| 维度 | 内容 |
|------|------|
| **事务边界** | {是否有 @Transactional，作用范围} |
| **幂等处理** | {有/无，实现方式} |
| **异常处理** | {主要异常类型和处理方式} |
| **校验逻辑** | {入参校验规则} |

### 依赖服务

| Service | 用途 |
|---------|------|
| {ServiceName} | {用途描述} |

### 数据流

```
入参: {RequestDTO}
  ↓
处理: {核心处理逻辑}
  ↓
出参: {ResponseDTO/Entity}
```

### 潜在风险（如有）

| 风险 | 说明 | 建议 |
|------|------|------|
| {风险类型} | {说明} | {建议} |

---

**分析时间**: {timestamp}
**分析状态**: 完成 / 部分完成

---

# 汇总报告模板

## 概览

| 指标 | 数值 |
|------|------|
| **扫描范围** | {范围描述} |
| **总接口数** | {N} |
| **分析成功** | {M} |
| **成功率** | {P}% |
| **涉及表数** | {T} |
| **识别关系** | {R} |

## ER 图

```mermaid
erDiagram
    {完整 ER 图内容}
```

## 按模块分类

### {模块名称}

| 方法 | HTTP | 路径 | 涉及表 | 核心逻辑 |
|------|------|------|--------|---------|
| {method} | {GET/POST} | {path} | {tables} | {逻辑描述} |

## 表使用热度

| 排名 | 表名 | 引用次数 | 主要操作 | 关联模块 |
|------|------|---------|---------|---------|
| 1 | {table} | {count} | {operations} | {modules} |

## 表操作分布

| 表名 | SELECT | INSERT | UPDATE | DELETE |
|------|--------|--------|--------|--------|
| {table} | {n} | {n} | {n} | {n} |

## 未成功分析的接口

| 接口 | 原因 | 建议 |
|------|------|------|
| {Controller.method} | {原因} | {建议} |

## 附录

### 文件列表

| 文件 | 说明 |
|------|------|
| `.api-analysis/er-diagram.md` | ER 图 |
| `.api-analysis/api-summary.md` | 本汇总文档 |
| `.api-analysis/reports/` | 单接口分析报告目录 |

---

**生成时间**: {timestamp}
