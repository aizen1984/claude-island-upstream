# 异步编程规范

> 基础陷阱（async 阻塞 / 漏 await）见全局规则 `~/.claude/rules/python-standards.md`。

## 通用异步规则

| # | 规则 | 错误 | 正确 |
|---|------|------|------|
| 1 | async 中禁止同步 ORM | `db.query(User).first()` 在 `async def` 中 | `AsyncSession` + `await session.execute()` |
| 2 | `asyncio.create_task()` 必须保留引用 | `asyncio.create_task(coro)` 不赋值 | `task = asyncio.create_task(coro)` |
| 3 | 并发数必须限制 | `await asyncio.gather(*[fetch(url) for url in urls])` | `asyncio.Semaphore(N)` 限制并发 |
| 4 | 禁止嵌套 `asyncio.run()` | `asyncio.run()` 在已有事件循环中 | `await` 或 `asyncio.create_task()` |
| 5 | async 上下文管理器 | `with aiohttp.ClientSession() as s:` | `async with aiohttp.ClientSession() as s:` |

## FastAPI 专项

| # | 规则 | 正确做法 |
|---|------|---------|
| 1 | I/O 密集用 `async def`，CPU 密集用 `def` | FastAPI 自动将 `def` 放线程池 |
| 2 | DB 依赖必须 `yield` + 关闭 | `try: yield session; finally: await session.close()` |
| 3 | Pydantic V2 用 `model_config` | `model_config = ConfigDict(from_attributes=True)` |
| 4 | BackgroundTasks 仅用于非关键任务 | 异常不传播，关键逻辑在请求中完成 |
| 5 | 配置用 Pydantic BaseSettings | `from pydantic_settings import BaseSettings`，禁止硬编码连接串 |
