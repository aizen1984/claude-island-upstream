---
name: cc-sql
description: 执行数据库只读查询（SELECT/SHOW/DESCRIBE），返回结构化结果。不修改数据、不分析调用链、不画ER图。用于查表结构、查数据、验证SQL
argument-hint: [SQL语句 或 操作指令]
allowed-tools: Bash(python .claude/skills/cc-sql/*)
---

# 数据库查询

通过 Moka Firekylin API 执行只读 SQL 查询，支持 prod（默认）/ sit 环境。脚本目录：`.claude/skills/cc-sql/`

## When Not to Use

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 设计 ER 图 | cc-api-analyzer + cc-diagram | 本 Skill 只执行 SQL 查询，不分析调用链和表关系 |
| 修改数据（INSERT/UPDATE/DELETE） | - | 仅支持只读操作，写操作被安全规则禁止 |
| 综合生产排障 | cc-troubleshoot | 本 Skill 只查数据，不做多源交叉验证 |

## 操作分发

收到 `$ARGUMENTS` 后，判断用户意图并选择对应脚本：

| 用户意图 | 执行命令 |
|----------|----------|
| 给了 SQL 语句（SELECT/SHOW/EXPLAIN） | `query.py "$ARGUMENTS"` |
| 想看有哪些库 | `databases.py` |
| 想看某库有哪些表 / 按关键字搜索 | `tables.py [--filter <关键字>]` |
| 想看某表的字段 | `columns.py <表名>` |
| 想看表完整结构（字段+索引） | `describe.py <表名>` |
| 管理索引缓存（状态/清理） | `cache.py <status\|clear>` |

> 所有脚本均以 `python .claude/skills/cc-sql/` 为前缀执行。用户用自然语言描述时，先 `describe.py --indexes-only` 查索引，再基于索引列构造 WHERE。

## 示例

```bash
# 直接执行 SQL（默认 prod）
python .claude/skills/cc-sql/query.py "SELECT id, uid FROM vip_order_log ORDER BY id DESC LIMIT 5"

# 查询 SIT 环境
python .claude/skills/cc-sql/query.py --env sit "SELECT id, uid FROM vip_order_log LIMIT 5"

# 搜索表 / 查看结构 / 只查索引
python .claude/skills/cc-sql/tables.py --filter order
python .claude/skills/cc-sql/describe.py vip_order_log
python .claude/skills/cc-sql/describe.py --indexes-only vip_order_log

# 缓存管理
python .claude/skills/cc-sql/cache.py status
python .claude/skills/cc-sql/cache.py clear --table vip_order_log
```

## 安全规则（摘要）

- **只读**：仅 SELECT / SHOW / DESCRIBE / EXPLAIN
- **禁止 SELECT ***：必须指定具体列名
- **自动 LIMIT 1000**、**聚合必须带 WHERE + 索引列**、**禁止 DDL/DML**

> 完整安全规则、参数列表、索引预检机制详见 `references/safety-rules.md`

## 结果展示格式

展示必须为「SQL 在上，数据在下」：

```
**SQL：**
```sql
SELECT id, status FROM vip_order_log WHERE uid = 123 LIMIT 5
```

**数据：**
| id | status |
|----|--------|
| 1  | 1      |
```

## 资源加载指导

| 场景 | 加载文件 |
|------|---------|
| 遇到需求模糊时 | `shared-rules/inquiry-protocol.md` |
| 查看完整参数/安全规则/索引机制 | `references/safety-rules.md` |

## 协作关系

- **接收自**: user（直接查询请求）
- **委托给**: 无（独立工具 Skill）

---

## Gotchas

> 从实际使用中积累的常见陷阱。每次发现新问题时追加。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 对 prod 环境执行写操作 | 被安全检查拦截或造成数据损坏 | prod 环境仅支持 SELECT/SHOW/DESCRIBE，写操作只在 sit 环境 |
| 2 | 查询未设置超时 | 大表全扫描拖垮数据库 | 默认超时 30s，复杂查询建议加 LIMIT |
| 3 | 跨库 JOIN 查询 | Firekylin API 不支持跨库，查询报错 | 分开查询后在本地合并结果 |
| 4 | 大表 WHERE 条件未命中索引 | 全表扫描导致查询超时 | 先 `describe.py --indexes-only` 查索引，WHERE 条件优先使用索引列。`query.py` 自动预检并警告 |
| 5 | 每次查询都远程获取索引 | 额外 API 调用增加延迟 | 索引自动缓存到 `~/.cache/claude-sql/`（24h 有效）。异常时 `cache.py clear` 清理 |
| 6 | 自然语言转 SQL 不看索引 | 构造的 WHERE 不命中索引 | 必须先 `describe.py --indexes-only` 查索引，再基于索引列构造 WHERE |
