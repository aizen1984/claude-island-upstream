# ORM / 数据库规范

## 通用 ORM 规则

| # | 规则 | 错误 | 正确 |
|---|------|------|------|
| 1 | 禁止循环查库（N+1） | `for u in users: u.orders` | Django: `select_related()` / `prefetch_related()`；SQLAlchemy: `joinedload()` |
| 2 | 禁止无条件全表查询 | `User.objects.all()` | 必须带 filter + limit |
| 3 | Session 必须在 with 中关闭 | `session = Session(); session.query(...)` | `with Session() as session:` |
| 4 | 批量操作用 bulk 方法 | 循环 `save()` | `bulk_create(objects, batch_size=500)` |
| 5 | 金额用 Decimal | `price * 0.1` | `Decimal("0.1") * price` |
| 6 | Django filter 禁止展开用户输入 | `filter(**request.GET.dict())` | 白名单字段 + 显式构建 |

## Django 专项

- 信号（signals）不做重业务逻辑 — 显式调用 service 方法
