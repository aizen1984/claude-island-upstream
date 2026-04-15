---
name: cc-python
description: 提供Python编码规范（FastAPI/Django+SQLAlchemy/ORM+async/await+类型系统+安全）。不独立执行开发任务。用于编码规范咨询、代码实现参考，作为底层规范支撑
user-invocable: false
allowed-tools: Read, Grep, Glob
paths: "**/*.py, **/pyproject.toml, **/requirements*.txt"
---

## Gotchas

> 基础陷阱（可变默认参数 / 裸 except / eval / pickle / yaml / subprocess / f-string SQL / async 阻塞 / 漏 await）见全局规则 `~/.claude/rules/python-standards.md`，以下仅列框架/ORM/生态专有陷阱。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | SQLAlchemy Session 跨线程/跨任务共享 | 并发操作导致数据错乱、连接泄漏 | Session-per-thread / AsyncSession-per-task；FastAPI 用 `Depends` |
| 2 | FastAPI `Depends` 链循环依赖 | 启动时 `RecursionError` 或请求挂起 | 抽出公共依赖到第三个 provider |
| 3 | Pydantic V1→V2：`class Config: orm_mode = True` 未改 | ORM 对象字段无法解析，序列化字段缺失（无报错） | `model_config = ConfigDict(from_attributes=True)`；用 `bump-pydantic` 批量迁移 |
| 4 | Celery `task_always_eager=True` 误用在生产 | 任务同步阻塞请求线程，失去队列/重试能力 | 仅限测试启用；生产 `assert not app.conf.task_always_eager` |

# Python 编码规范

> 通用 Python 后端开发指南，适用于 FastAPI / Django + SQLAlchemy / Django ORM 架构

## Overview

**定位**：规范库，可由关键词直接触发，也可被 cc-code-writer / cc-code-reviewer 等隐式依赖加载。

---

## When to Use

- 编写/修改 Python 后端代码（视图、服务层、数据访问层）
- 处理异步编程、ORM、Pydantic 验证

## When Not to Use

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 系统级架构设计 | cc-design | 本 Skill 是编码规范库，不做架构设计 |
| 任务规划 | cc-planner | 本 Skill 不做任务拆解和规划 |
| 代码审查 | cc-code-reviewer | 本 Skill 提供规范参考，不主动执行审查 |

---

## 协作关系

- **被依赖**: cc-code-writer、cc-code-reviewer、cc-work-mode、cc-design、cc-planner、cc-tdd、cc-api-analyzer、cc-troubleshoot（隐式依赖）
- **委托给**: 无（规范库，不主动触发）

---

## 资源加载指导

| 条件 | 加载文件 | 不加载 |
|------|---------|--------|
| 首次激活（速查） | SKILL.md Gotchas + [standards-quickref.md](standards-quickref.md) | patterns-async.md, patterns-orm.md |
| FastAPI / async 项目 | [patterns-async.md](patterns-async.md) | patterns-orm.md（除非同时涉及 ORM） |
| Django / ORM 项目 | [patterns-orm.md](patterns-orm.md) | patterns-async.md（除非同时涉及 async） |
| 通用 Python | SKILL.md 类型系统 + 安全 + 按需加载子文件 | — |

---

## 类型系统规范

| # | 规则 | 说明 |
|---|------|------|
| 1 | 外部输入用 Pydantic，内部用 dataclass | Pydantic 负责验证+序列化，dataclass 负责结构化 |
| 2 | 禁止 `Dict[str, Any]` 做函数签名 | 用 TypedDict 或 Pydantic model |

---

## 安全规范

> 基础安全规则（eval/pickle/yaml/subprocess）见全局规则 python-standards.md。

| # | 规则 | 说明 |
|---|------|------|
| 1 | 禁止 `assert` 做运行时校验 | `-O` 模式下被移除 |
| 2 | hash 比较用 `hmac.compare_digest()` | 防时序攻击 |
| 3 | 禁止硬编码数据库 URL/密钥 | 用 `pydantic-settings` BaseSettings + 环境变量 |

---

## 推荐工具

- Ruff 作为唯一 linter+formatter：`select = ["E", "F", "B", "S", "UP", "ASYNC", "RUF"]`
