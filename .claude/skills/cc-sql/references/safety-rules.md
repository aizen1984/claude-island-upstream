# SQL Skill 安全规则与参数详解

> 主文档: `../SKILL.md`。此文件包含安全规则详细说明、参数完整列表、索引预检机制。

## 环境配置

| 环境 | URL | 默认实例 | 默认库 |
|------|-----|---------|--------|
| prod（默认） | moka.dmz.prod.caijj.net | dscommerce | vipship |
| sit | moka.dmz.sit.caijj.net | cjjloan | vipship |

- Token 加载优先级: config.yaml > 环境变量 `MOKA_TOKEN_FILE` > 默认路径 `~/x-token/moka-prod-x-token.json`
- 环境切换：用户提到 sit/SIT 时，所有脚本加 `--env sit`

## 安全规则详细说明

- **只读**：仅允许 SELECT / SHOW / DESCRIBE / EXPLAIN
- **禁止 SELECT ***：必须指定具体列名
- **自动 LIMIT**：无 LIMIT 的 SELECT 自动追加 LIMIT 1000
- **禁止无条件聚合**：COUNT/SUM/AVG/MIN/MAX/GROUP BY 必须包含 WHERE 条件，且条件字段应为索引字段，禁止全表统计
- **禁止 DDL/DML**：INSERT / UPDATE / DELETE / DROP 等一律拒绝

## 通用参数

所有脚本共享以下参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--env` | 环境（prod/sit） | prod |
| `-i, --instance` | 实例名（覆盖环境默认值） | 按环境 |
| `-d, --database` | 库名（覆盖环境默认值） | 按环境 |
| `--format` | 输出格式 json / table | json |

`query.py` 额外参数：

| 参数 | 说明 |
|------|------|
| `--limit` | 覆盖最大行数（默认 1000） |
| `--file` | 从文件读取 SQL |
| `--no-index-check` | 跳过索引预检（默认开启） |

`describe.py` 额外参数：

| 参数 | 说明 |
|------|------|
| `--indexes-only` | 只显示索引信息 |

`tables.py` / `databases.py` 额外参数：

| 参数 | 说明 |
|------|------|
| `--filter` | 模糊过滤关键字 |

`cache.py` 参数：

| 参数 | 说明 |
|------|------|
| `action` | 操作类型：`status`（查看缓存状态）/ `clear`（清理缓存） |
| `--table` | 指定表名（仅 clear 时有效，不指定则清全部） |

## 索引预检与缓存

大表查询超时的根因通常是 WHERE 条件未命中索引导致全表扫描。索引预检自动解决这个问题。

**自动行为**（`query.py` 执行 SELECT 时）：
1. 从 SQL 解析表名
2. 查本地缓存 `~/.cache/claude-sql/`（文件+内存两级）
3. 未命中 -> 自动 `SHOW INDEX`，结果写入缓存（默认 24h 有效）
4. 比对 WHERE 条件列与索引列，不匹配则 stderr 输出警告
5. 结果 JSON 附带 `index_check` 字段，含索引详情和匹配分析

**手动预热**（推荐大表场景）：
```bash
# 先查索引（自动缓存），再构造 SQL
python .claude/skills/cc-sql/describe.py --indexes-only <表名>
```

**缓存配置**（`config.yaml`）：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `cache.enabled` | 启用索引预检 | true |
| `cache.dir` | 缓存目录 | ~/.cache/claude-sql |
| `cache.ttl` | 缓存有效期（秒） | 86400（24h） |

**索引优先策略**（构造 SQL 时必须遵循）：
- 自然语言转 SQL 前，先用 `describe.py --indexes-only` 查索引
- WHERE 条件**优先使用索引列**，避免全表扫描
- 多条件查询时，最左前缀原则：联合索引 `(a, b, c)` 必须从 `a` 开始
- 看到 `index_check.warning` 时，主动调整 SQL 用索引列替代
