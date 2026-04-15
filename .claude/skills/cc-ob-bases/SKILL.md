---
name: cc-ob-bases
description: 创建和编辑Obsidian Bases(.base文件)的视图、过滤器、公式和汇总。不操作普通Markdown笔记、不处理frontmatter属性。用于结构化数据视图、Dataview替代、数据库式笔记查询
allowed-tools: Read, Write, Edit, Grep, Glob
argument-hint: "[.base 文件路径]"
paths: ["**/*.base"]
---

# Obsidian Bases 操作

> 本 Skill 源自 [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) 的 obsidian-bases，已适配本体系元数据层。

## Gotchas

> 从设计和 kepano 原始 Troubleshooting 章节提炼的常见陷阱。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | Duration 类型直接 `.round()` | 报错，Duration 不支持 number 方法 | 先访问 `.days` `.hours` 等字段再 round：`(now() - file.ctime).days.round(0)` |
| 2 | 属性可能为空却未用 `if()` 守护 | 笔记不含该属性时公式崩溃 | 所有属性访问用 `if(prop, ...)` 守护：`if(due_date, (date(due_date) - today()).days, "")` |
| 3 | 公式含双引号时未用单引号包裹 | YAML 解析失败 | 单引号包外层：`'if(done, "Yes", "No")'` |
| 4 | YAML 特殊字符未引号包裹 | `displayName: Status: Active` 解析失败（冒号冲突） | 含 `:{}[],&*#?|-<>=!%@` 的字符串必须引号：`"Status: Active"` |
| 5 | `order` 或 `properties` 引用未定义的 `formula.X` | 静默失败，视图空白 | 确保 `formulas:` 段中已定义对应 formula |
| 6 | 手动编辑 `.base` 文件后未在 Obsidian 中验证 | YAML 错误到运行时才发现 | 写入后建议用户在 Obsidian 中打开确认渲染 |
| 7 | View 的 `filters` 与全局 `filters` 都定义导致混淆 | 过滤结果不符合预期 | 全局 filters 先应用，view filters 在其基础上进一步过滤（AND 关系） |
| 8 | 金额/数字字段用 `Number` 却存入字符串 | 汇总公式（Sum/Average）失效 | frontmatter 中数字字段不要加引号，或用 `number(value)` 转换 |

---

## 协作关系

- **接收自**: user（直接触发，当用户提到 `.base` 文件、创建数据库视图、Obsidian Bases 等）
- **委托给**: 无
- **隐式依赖**: 无（Bases 是 Obsidian 原生功能，无第三方插件依赖）
- **与 cc-diagram 的区别**: cc-diagram 生成 Mermaid 可视化图表，cc-ob-bases 生成 Obsidian 动态数据视图（从 vault 笔记实时查询）

---

## 适用场景

| 场景 | 示例 |
|------|------|
| 创建任务追踪视图 | 从 `#task` 标签的笔记中筛选待办，按优先级分组展示 |
| 创建阅读清单 | 从 `#book` 笔记中筛选状态为"to-read"的，按作者排序 |
| Daily Notes 索引 | 列出近 30 天 daily notes，显示字数估算和星期几 |
| 项目看板 | 按 status 字段分组展示项目笔记 |
| 替代 Dataview 查询 | 比 Dataview 更原生（无需插件），性能更好 |

## 不适用场景

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 编辑普通 Markdown 笔记 | 直接 Edit 工具 | Bases 专门处理 `.base` 文件 |
| 修改 frontmatter 属性 | 直接 Edit 工具 | Bases 只读笔记属性，不修改 |
| 一次性数据查询 | Grep / obsidian CLI | Bases 创建持久化视图，不适合一次性查询 |
| Mermaid 流程图/架构图 | cc-diagram | Bases 是数据视图，非可视化图表 |
| 生成静态报告 | cc-design / cc-ob-aggregate | Bases 是动态视图，不生成静态文档 |

---

## 工作流程

1. **创建文件**: 在 vault 中创建 `.base` 扩展名文件，内容为有效 YAML
2. **定义范围**: 添加 `filters` 选择哪些笔记进入视图（按标签/文件夹/属性/日期）
3. **添加公式**（可选）: 在 `formulas` 段定义计算属性
4. **配置视图**: 添加一个或多个视图（`table`/`cards`/`list`/`map`），用 `order` 指定显示哪些属性
5. **验证语法**: 检查 YAML 有效性 + 所有引用的属性和公式存在 + YAML 引号规则
6. **在 Obsidian 中测试**: 打开 `.base` 文件确认视图正确渲染

---

## Schema 速查

```yaml
# 全局过滤器（应用到所有视图）
filters:
  and: []
  or: []
  not: []

# 公式定义（跨视图共享）
formulas:
  formula_name: 'expression'

# 属性配置（显示名/设置）
properties:
  property_name:
    displayName: "Display Name"
  formula.formula_name:
    displayName: "Formula Display Name"

# 自定义汇总公式
summaries:
  custom_summary_name: 'values.mean().round(3)'

# 视图定义（一个或多个）
views:
  - type: table | cards | list | map
    name: "View Name"
    limit: 10
    groupBy:
      property: property_name
      direction: ASC | DESC
    filters:
      and: []
    order:
      - file.name
      - property_name
      - formula.formula_name
    summaries:
      property_name: Average
```

---

## 过滤器语法

### 过滤器结构

```yaml
# 单条件
filters: 'status == "done"'

# AND - 所有条件为真
filters:
  and:
    - 'status == "done"'
    - 'priority > 3'

# OR - 任一条件为真
filters:
  or:
    - 'file.hasTag("book")'
    - 'file.hasTag("article")'

# NOT - 排除匹配项
filters:
  not:
    - 'file.hasTag("archived")'

# 嵌套组合
filters:
  or:
    - file.hasTag("tag")
    - and:
        - file.hasTag("book")
        - file.hasLink("Textbook")
    - not:
        - file.hasTag("book")
        - file.inFolder("Required Reading")
```

### 操作符

| 操作符 | 含义 |
|--------|------|
| `==` | 等于 |
| `!=` | 不等于 |
| `>` `<` `>=` `<=` | 数值比较 |
| `&&` | 逻辑与 |
| `\|\|` | 逻辑或 |
| `!` | 逻辑非 |

---

## 属性系统

### 三种属性类型

1. **笔记属性**（Note Properties）- 来自 frontmatter：`note.author` 或 `author`
2. **文件属性**（File Properties）- 文件元数据：`file.name`, `file.mtime` 等
3. **公式属性**（Formula Properties）- 计算值：`formula.my_formula`

### 文件属性参考

| 属性 | 类型 | 说明 |
|------|------|------|
| `file.name` | String | 文件名 |
| `file.basename` | String | 不含扩展名的文件名 |
| `file.path` | String | 完整路径 |
| `file.folder` | String | 所在文件夹 |
| `file.ext` | String | 扩展名 |
| `file.size` | Number | 字节数 |
| `file.ctime` | Date | 创建时间 |
| `file.mtime` | Date | 修改时间 |
| `file.tags` | List | 所有标签 |
| `file.links` | List | 内部链接 |
| `file.backlinks` | List | 反向链接 |
| `file.embeds` | List | 嵌入 |
| `file.properties` | Object | 所有 frontmatter 属性 |

### `this` 关键字

- 在主内容区：指 base 文件自身
- 嵌入时：指嵌入它的文件
- 侧边栏：指主内容区的活动文件

---

## 公式语法

公式在 `formulas` 段定义，用于从属性计算值。

```yaml
formulas:
  # 简单算术
  total: "price * quantity"

  # 条件逻辑
  status_icon: 'if(done, "✅", "⏳")'

  # 字符串格式化
  formatted_price: 'if(price, price.toFixed(2) + " 元")'

  # 日期格式化
  created: 'file.ctime.format("YYYY-MM-DD")'

  # 自创建以来的天数（用 .days 访问 Duration）
  days_old: '(now() - file.ctime).days'

  # 距离截止日的天数
  days_until_due: 'if(due_date, (date(due_date) - today()).days, "")'
```

### 常用函数

完整列表见 [references/FUNCTIONS_REFERENCE.md](references/FUNCTIONS_REFERENCE.md)（涵盖 Date/String/Number/List/File/Link/Object/RegExp 所有类型）。

| 函数 | 签名 | 说明 |
|------|------|------|
| `date()` | `date(string): date` | 解析字符串为日期（`YYYY-MM-DD HH:mm:ss`）|
| `now()` | `now(): date` | 当前日期和时间 |
| `today()` | `today(): date` | 当前日期（时间部分 = 00:00:00） |
| `if()` | `if(condition, trueResult, falseResult?)` | 条件 |
| `duration()` | `duration(string): duration` | 解析 duration 字符串 |
| `file()` | `file(path): file` | 获取文件对象 |
| `link()` | `link(path, display?): Link` | 创建链接 |

### Duration 类型（重要陷阱）

两个日期相减返回 **Duration 类型**（不是数字）。

**Duration 字段**: `duration.days`, `duration.hours`, `duration.minutes`, `duration.seconds`, `duration.milliseconds`

**⛔ Duration 不支持 `.round()` `.floor()` `.ceil()`**。必须先访问数值字段（如 `.days`），再应用数字函数。

```yaml
# ✅ 正确
"(date(due_date) - today()).days"
"(now() - file.ctime).days"
"(date(due_date) - today()).days.round(0)"

# ❌ 错误
# "((date(due) - today()) / 86400000).round(0)"  # Duration 不支持除法后 round
```

### 日期算术

```yaml
# Duration 单位: y/year/years, M/month/months, d/day/days,
#                w/week/weeks, h/hour/hours, m/minute/minutes, s/second/seconds
"now() + \"1 day\""       # 明天
"today() + \"7d\""        # 一周后
"now() - file.ctime"      # 返回 Duration
"(now() - file.ctime).days"  # 天数（number）
```

---

## 视图类型

### Table 表格视图

```yaml
views:
  - type: table
    name: "我的表格"
    order:
      - file.name
      - status
      - due_date
    summaries:
      price: Sum
      count: Average
```

### Cards 卡片视图

```yaml
views:
  - type: cards
    name: "画廊"
    order:
      - file.name
      - cover_image
      - description
```

### List 列表视图

```yaml
views:
  - type: list
    name: "简单列表"
    order:
      - file.name
      - status
```

### Map 地图视图

需要 latitude/longitude 属性和 Maps 社区插件。

```yaml
views:
  - type: map
    name: "位置"
```

---

## 默认汇总公式

| 名称 | 输入类型 | 说明 |
|------|---------|------|
| `Average` | Number | 平均值 |
| `Min` | Number | 最小值 |
| `Max` | Number | 最大值 |
| `Sum` | Number | 求和 |
| `Range` | Number/Date | 最大减最小 |
| `Median` | Number | 中位数 |
| `Stddev` | Number | 标准差 |
| `Earliest` | Date | 最早日期 |
| `Latest` | Date | 最晚日期 |
| `Checked` | Boolean | true 计数 |
| `Unchecked` | Boolean | false 计数 |
| `Empty` | Any | 空值计数 |
| `Filled` | Any | 非空计数 |
| `Unique` | Any | 唯一值计数 |

---

## 完整示例

### 任务追踪 Base

```yaml
filters:
  and:
    - file.hasTag("task")
    - 'file.ext == "md"'

formulas:
  days_until_due: 'if(due, (date(due) - today()).days, "")'
  is_overdue: 'if(due, date(due) < today() && status != "done", false)'
  priority_label: 'if(priority == 1, "🔴 高", if(priority == 2, "🟡 中", "🟢 低"))'

properties:
  status:
    displayName: 状态
  formula.days_until_due:
    displayName: "剩余天数"
  formula.priority_label:
    displayName: 优先级

views:
  - type: table
    name: "活跃任务"
    filters:
      and:
        - 'status != "done"'
    order:
      - file.name
      - status
      - formula.priority_label
      - due
      - formula.days_until_due
    groupBy:
      property: status
      direction: ASC
    summaries:
      formula.days_until_due: Average

  - type: table
    name: "已完成"
    filters:
      and:
        - 'status == "done"'
    order:
      - file.name
      - completed_date
```

### Daily Notes 索引

```yaml
filters:
  and:
    - file.inFolder("daily-notes")
    - '/^\d{4}-\d{2}-\d{2}$/.matches(file.basename)'

formulas:
  word_estimate: '(file.size / 5).round(0)'
  day_of_week: 'date(file.basename).format("dddd")'

properties:
  formula.day_of_week:
    displayName: "星期"
  formula.word_estimate:
    displayName: "~字数"

views:
  - type: table
    name: "最近日记"
    limit: 30
    order:
      - file.name
      - formula.day_of_week
      - formula.word_estimate
      - file.mtime
```

---

## 嵌入 Base

在 Markdown 文件中嵌入：

```markdown
![[MyBase.base]]

<!-- 特定视图 -->
![[MyBase.base#View Name]]
```

---

## YAML 引号规则

- 公式含双引号时用**单引号**包裹：`'if(done, "Yes", "No")'`
- 简单字符串用双引号：`"My View Name"`
- 复杂表达式中的嵌套引号需正确转义

---

## 参考资源

- [Bases 官方语法文档](https://help.obsidian.md/bases/syntax)
- [Bases 函数文档](https://help.obsidian.md/bases/functions)
- [Bases 视图文档](https://help.obsidian.md/bases/views)
- [公式文档](https://help.obsidian.md/formulas)
- [完整函数参考](references/FUNCTIONS_REFERENCE.md) - 按需加载
