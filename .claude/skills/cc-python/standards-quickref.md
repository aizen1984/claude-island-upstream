# Python 规范速查表

> 28 项核心规则，按领域分组。详细说明见 SKILL.md 对应章节。

## 一、致命陷阱（必须避免）

| # | 规则 | 速查 |
|---|------|------|
| 1 | 可变默认参数 | `items=None` 不是 `items=[]` |
| 2 | 裸 except | `except Exception as e:` |
| 3 | 静默吞异常 | `logger.error()` + `raise` |
| 4 | eval/exec 外部输入 | `ast.literal_eval()` |
| 5 | pickle 不可信数据 | 用 JSON |
| 6 | yaml 无 SafeLoader | `yaml.safe_load()` |
| 7 | subprocess shell=True | `shell=False` + 参数列表 |

## 二、异步编程

| # | 规则 | 速查 |
|---|------|------|
| 8 | async 中禁止同步阻塞 | `httpx.AsyncClient` / `run_in_executor()` |
| 9 | 必须 await 协程 | 漏 await = 静默失败 |
| 10 | create_task 保留引用 | `task = create_task(coro)` |
| 11 | 限制并发数 | `asyncio.Semaphore(N)` |
| 12 | 禁止嵌套 asyncio.run() | 用 `await` 或 `create_task()` |

## 三、类型系统

| # | 规则 | 速查 |
|---|------|------|
| 13 | public 函数类型注解 | 参数 + 返回值 |
| 14 | 禁止 Dict[str, Any] | 用 TypedDict / Pydantic |
| 15 | 外部输入 Pydantic | 内部用 dataclass |
| 16 | Literal 替代魔法字符串 | `Literal["active", "inactive"]` |

## 四、ORM / 数据库

| # | 规则 | 速查 |
|---|------|------|
| 17 | 禁止 N+1 | `select_related()` / `joinedload()` |
| 18 | 禁止无条件全表查询 | filter + limit |
| 19 | Session 用 with 管理 | `with Session() as session:` |
| 20 | 批量用 bulk 方法 | `bulk_create(batch_size=500)` |
| 21 | 金额用 Decimal | `Decimal("0.1")` |

## 五、安全

| # | 规则 | 速查 |
|---|------|------|
| 22 | SQL 参数化 | `execute("... %s", (val,))` |
| 23 | 禁止硬编码密钥 | 环境变量 |
| 24 | 禁止 assert 做校验 | `if not x: raise ValueError` |
| 25 | hash 比较防时序攻击 | `hmac.compare_digest()` |

## 六、项目结构

| # | 规则 | 速查 |
|---|------|------|
| 26 | pyproject.toml 统一配置 | 替代 setup.py |
| 27 | Ruff 唯一 linter | `select = ["E","F","B","S","UP","ASYNC"]` |
| 28 | pytest + conftest 分层 | patch where it's used |
