# Phase 1: EXPLORE（界面功能分析）

**执行者**：主 agent

## 1.1 登录等待

```
1. browser_navigate 打开目标 URL
   - 如报错提示浏览器未安装 → 执行 browser_install() 后重试
2. browser_snapshot 检查页面状态
3. 判断是否需要登录：
   - 页面包含"登录"/"Login"按钮或表单 → 需要登录
   - 页面显示 401/403 或"未授权"提示 → 需要登录
   - 页面正常显示业务内容 → 无需登录
4. 如需登录：
   a. 告知用户："检测到需要登录，请在浏览器中完成登录操作"
   b. AskUserQuestion 等待用户确认登录完成
   c. browser_snapshot 验证：页面不再包含登录表单
   d. 验证失败 → 重新提示用户
5. 记录登录状态到功能分析报告头部
```

## 1.1.5 范围确认（Scope Confirmation）

登录完成（或无需登录）后，执行快速扫描并询问用户锁定测试范围：

```
1. browser_snapshot 获取当前页面无障碍树
2. 快速识别页面的功能区域结构：
   - 顶部导航栏 / 菜单项
   - 侧边栏 Tab / 菜单项
   - 主内容区的功能分区
   - 其他明显的功能入口（卡片、快捷操作等）
3. 向用户呈现识别结果，格式：

   已识别以下功能区域：
   1. [顶部导航] 首页 | 订单管理 | 商品管理 | 系统设置
   2. [侧边栏] 全部订单 | 待审核 | 已完成 | 已取消
   3. [主区域] 数据概览卡片 + 操作快捷入口

   请告诉我需要测试哪些区域？（可多选，如"1,2"或"全部"）

4. AskUserQuestion 等待用户回复
5. 根据用户回复确定 explore_scope：
   - 用户选择具体区域 → 仅探索选定区域对应的导航入口
   - 用户回复"全部" → 不限制，等同于当前行为
   - 用户补充说明（如"只测新增和编辑功能"）→ 记录为功能级过滤条件
6. 将确认的范围记录到功能分析报告头部的「测试范围」字段
```

**跳过条件**：当 `scope_confirmation=false` 或 planner 委托且已提供 scope 参数时，自动跳过此步骤。

## 1.2 BFS + DFS 探索

```
BFS 阶段（广度扫描）：
1. browser_snapshot 获取首页无障碍树
2. 识别顶层导航元素：
   - navigation 角色的元素
   - menu/menubar 角色的元素
   - tab/tablist 角色的元素
   - 侧边栏中的 link 列表
3. **范围过滤**：如 explore_scope 非"全部"，仅保留用户选定的导航入口
4. 记录所有顶层入口 → 建立站点地图骨架

DFS 阶段（深度探索）：
对每个顶层入口：
1. browser_click 进入子页面
2. browser_snapshot 获取页面结构
3. 提取并记录（静态分析）：
   - 页面路径（URL 或导航路径）
   - 可交互元素清单（button/link/textbox/combobox/checkbox）
   - 表单字段（名称、类型、是否必填）
   - 表格结构（列名、是否可排序）
   - 子导航入口
3.5 主动交互确认（如 explore_interactive=true）：
   对识别出的 L1/L2 白名单元素逐一交互确认（最多 explore_max_interactions 次/页）
   之后条件触发 L3（见 §1.3 L3-创建白名单，独立计数，不占 explore_max_interactions 配额）
   - 点击触发按钮 → 条件等待 → snapshot → 提取弹窗/表单详情 → 关闭/恢复
   - 将发现的信息合并到步骤 3 的提取结果中（更新操作模式和元素字段）
   - **每次 click 后检查新 Tab**（如 explore_new_tab=true）：见步骤 3.6
3.6 新 Tab 探索（如 explore_new_tab=true，嵌入步骤 1/3.5 的每次 click 后执行）：
   a. browser_tabs() 获取当前 Tab 列表，与 click 前数量比较
   b. 如 Tab 数量增加 → 新 Tab 被打开
   c. browser_tabs(action="select", index=新Tab索引) 切换到新 Tab
   d. browser_snapshot 获取新 Tab 页面结构
      - 如 snapshot 为空 → 执行 §1.3.5 snapshot 降级策略
   e. 按 §1.5 提取页面信息（来源标记为"从{父页面}点击{按钮}打开新Tab"）
   f. 递归执行步骤 3～3.5 探索新 Tab 页面内的交互元素
   g. browser_tabs(action="close") 关闭新 Tab → 自动回到原 Tab
   h. 如未检测到新 Tab → 检查页面内容是否变化（SPA 内跳转），按常规处理
3.7 业务链路识别：
   每页探索完成后，判断跨页面链路片段：
   a. 检查当前页面的操作是否产生页面跳转（Create→Detail、Edit→配置页等）
   b. 检查按钮点击是否打开新 Tab 指向关联页面
   c. 记录链路片段到内存链路队列：{源页面, 触发操作, 目标页面, 链路类型}
   d. 链路类型：CRUD / 发布 / 审批 / 配置
4. 递归探索子页面（深度 +1）
5. 返回上级：
   - 如当前页面是通过新 Tab 打开的 → 已在 3.6g 中 close，无需 navigate_back
   - 否则 → browser_navigate_back 返回上级
```

## 1.3 主动交互确认规则

> 仅在 `explore_interactive=true` 时生效（步骤 3.5）

### 白名单分类（默认拒绝原则：不在白名单内的按钮一律禁止触发）

**L1-查看白名单**：
- 名称包含：新增|添加|创建|新建|+ → 打开弹窗观察（不填写不保存）
- 名称包含：编辑|修改 → 打开预填充表单观察（不修改不保存）
- 名称包含：查看|详情|查看详情 → 打开详情页/弹窗
- 名称包含：更多|...|展开 → 展开菜单
- aria-expanded=false 的可折叠元素 → 展开
- 数据集合区域（列表/表格/卡片/树等）中的数据项本身 → 每种集合点击第 1 条非操作按钮的数据项，观察是否触发导航/弹窗/新 Tab；如无反应则记录"数据项不可点击"

**L2-切换白名单**：
- role=tab 且非 selected → 切换
- 视图切换按钮组（列表/卡片/网格图标）→ 切换

**L3-创建白名单**（仅 `explore_l3_create=true` 时生效）：
- 触发条件：L1 发现 Create 入口（弹窗/抽屉/跳转新页面均可） + session 内 L3 次数 < `explore_l3_max_per_session` + 保存后可能跳转未知页面
- 执行规则：
  1. 用 `E2E-EXPLORE-` 前缀填写必填字段（如名称填 `E2E-EXPLORE-探索测试`）
  2. 保存/确认 → 跟踪页面跳转或新 Tab
     - 弹窗/抽屉形式：保存后弹窗关闭，在原页面定位新数据
     - 跳转新页面形式：在新页面完成填写 → 保存 → 跟踪后续跳转/回到列表
  3. 写后回探：如保存后停留在原页面（列表刷新/无跳转），在数据集合中定位刚创建的数据项（通过 `E2E-EXPLORE-` 前缀匹配），对该数据项执行 L1-数据项探测（点击数据项本身，观察导航行为）；如发现新页面 → 按 §1.5 提取（来源标记为"L3写后回探"）→ 返回列表
  4. 如跳转到新页面 → 按 §1.5 提取（来源标记为"L3创建跳转"）
  5. 如打开新 Tab → 按步骤 3.6 处理
  6. 记录清理指令到内存：`{数据标识, 创建页面, 清理方式(删除按钮/API/手动)}`
- L3 不占用 `explore_max_interactions` 配额，独立计数
- L3 创建的数据必须可识别（`E2E-EXPLORE-` 前缀），便于后续清理

**X-禁止**：一切写操作（删除/发布/保存/提交/确认/导入/导出）+ 无法识别的操作。例外：L3 允许的受控创建（仅在 explore_l3_create=true 时）

### 执行流程

按 L1→L2→L3（条件触发）顺序执行，L1+L2 合计最多 `explore_max_interactions` 次，L3 独立计数（最多 `explore_l3_max_per_session` 次/session）：

```
1. 记录当前页面 URL 和 snapshot 状态
2. 从 snapshot 中匹配白名单元素（优先 L1，其次 L2）
3. 对每个匹配元素：
   a. browser_click(ref) 触发交互
   b. 条件等待（见下方策略）
   c. browser_snapshot 检测变化
   d. 如出现弹窗/抽屉/菜单 → 提取表单字段/按钮/选项等信息
   e. 关闭/恢复（见下方降级策略）
   f. browser_snapshot 确认恢复成功
4. 将发现的信息合并到页面提取结果中
```

### 条件等待策略（替代固定 wait）

```
优先：browser_wait_for(textGone="加载中", timeout=5000)
次选：browser_wait_for(textGone="Loading", timeout=5000)
兜底：browser_wait_for(time=1)（无 loading 标识时使用）
```

### 弹窗关闭四级降级

```
1. browser_press_key("Escape") → snapshot 验证弹窗是否消失
2. snapshot 找 X/关闭/取消按钮 → click → snapshot 验证
3. browser_evaluate(() => document.querySelector('.ant-modal-wrap')?.click()) → snapshot 验证
4. browser_navigate(currentURL) 强制恢复
```

### 图标按钮识别兜底

无名称无文本的按钮（纯图标），通过 `browser_evaluate` 读取 DOM 属性：
```
browser_evaluate(() => {
  const btn = document.querySelector('[ref="eXX"]') || document.querySelectorAll('button')[N];
  return { class: btn?.className, title: btn?.title, ariaLabel: btn?.getAttribute('aria-label'), tooltip: btn?.dataset?.tooltip };
})
```
根据 class 名（如 anticon-edit、anticon-delete、anticon-plus）判断按钮类型，再匹配白名单。

### 信息合并规则

发现的信息直接更新现有字段，不新增字段：
- `操作模式`：括号内补充具体信息
  - 探索前：`Create(新增按钮+弹窗表单)`
  - 探索后：`Create(新增按钮→Modal, 字段: 名称(text/必填)/类型(select)/描述(textarea))`
- `元素.表单`：合并弹窗/抽屉内发现的表单字段
- `操作`：补充通过交互确认的操作项

### Token 控制

| 控制项 | 限制 |
|--------|------|
| 每页交互次数 | 最多 explore_max_interactions 次（L1+L2 合计），L3 独立计数不占此配额 |
| 同名元素合并 | 多个同名按钮只取第一个非 disabled 的 |
| Tab 切换上限 | 最多 5 个 Tab |
| 弹窗内 snapshot | 每个弹窗仅 snapshot 一次 |

## 1.3.5 snapshot 降级策略

> 当 `snapshot_fallback=true` 且 snapshot 返回空白/无有效内容时（常见于微前端 qiankun 子应用），按以下四级降级：

```
Level 1: browser_wait_for(time=2) → 重试 browser_snapshot
         - 等待微前端子应用挂载完成
         - 如仍为空 → 进入 Level 2

Level 2: browser_take_screenshot → 视觉分析页面结构
         - 从截图中识别���面布局、按钮文字、表单区域
         - 记录可见的功能区域和操作入口
         - 精度降低但可获得页面概览

Level 3: browser_evaluate 获取 DOM 概要
         - 查询模板：
           browser_evaluate(() => {
             const summary = {
               buttons: [...document.querySelectorAll('button')].map(b => b.textContent?.trim()).filter(Boolean),
               links: [...document.querySelectorAll('a')].map(a => ({ text: a.textContent?.trim(), href: a.href })).filter(l => l.text),
               inputs: [...document.querySelectorAll('input,textarea,select')].map(i => ({ type: i.type, name: i.name || i.placeholder, id: i.id })),
               headings: [...document.querySelectorAll('h1,h2,h3,h4')].map(h => h.textContent?.trim()),
               tabs: [...document.querySelectorAll('[role="tab"]')].map(t => t.textContent?.trim()),
               tree: [...document.querySelectorAll('[role="treeitem"]')].map(t => t.textContent?.trim().substring(0, 50))
             };
             return summary;
           })
         - 基于 DOM 概要构造等效的页面信息提取结果

Level 4: 标记「snapshot降级」继续，不中断探索
         - 该页面标注降级级别和原因
         - 后续交互使用 browser_evaluate(() => el.click()) 替代 ref click
         - 降级页面交互次数减半（explore_max_interactions / 2）
```

**降级页面交互方式**：ref 不可用时，通过 CSS 选择器 + `browser_evaluate` 操作元素：
```
browser_evaluate(() => document.querySelector('button.ant-btn-primary')?.click())
```

## 1.4 探索边界控制

| 规则 | 说明 |
|------|------|
| 最大深度 | 达到 max_depth 停止递归 |
| 最大页面数 | 达到 max_pages 停止探索 |
| 同域限制 | 仅探索与目标 URL 同域的页面，外部链接记录但不跟进 |
| 内容去重 | snapshot 内容相似度 > 90% 的页面视为重复，跳过 |
| SPA 检测 | URL 未变但 snapshot 内容变化 → 视为新页面 |
| 分批处理 | 每探索 explore_batch_size 个页面，将结果追加写入文件 |
| 主动交互开关 | explore_interactive=false 时跳过步骤 3.5 |

## 1.5 页面信息提取模式

对每个页面 snapshot，立即提取以下结构化信息后丢弃原始 snapshot：

```
页面: [名称] ([URL或导航路径])
描述: [一句话描述页面用途]
来源: [导航进入 / 从{父页面}点击{按钮}打开新Tab / L3创建跳转]
关联页面: [点击{按钮}→{页面名称}]（可选，有跨页面链路时填写）
操作模式: [识别出的操作模式标签，逗号分隔]（降级页面追加标记：⚠️[snapshot降级:Level N]）
元素:
  - 导航: [导航项列表]
  - 表单: [字段名(类型/必填)] ...
  - 按钮: [按钮名称列表]
  - 表格: [列名列表] + 分页器(有/无, 总条数, 每页条数, 当前页码)
  - 链接: [可点击链接列表]
操作: [可执行的操作列表]
```

**编码清洗（强制）**：提取文本后立即检查是否含 `U+FFFD`（�）或其他 Unicode 替换字符。如发现则删除该字符并在原位插入 `[编码损失]` 标记。降级提取（Level 2/3）的文本需逐段检查，确保所有中文字符完整无截断。

**操作模式识别（强制）**：必须对照 [references/operation-patterns-modes.md](../references/operation-patterns-modes.md) 模式总览表的 15 种模式定义，根据页面元素识别匹配的操作模式。每个页面必须标注 `**操作模式**: [Read, Create, Update, Delete, Toggle, ...]`，禁止留空或省略。

**操作模式确认标记**：主动交互确认前后格式对比：
```
# 探索前（静态分析，基于 snapshot 推测）：
操作模式: Read(列表+搜索+分页), Create(新增按钮+弹窗表单), Delete(删除按钮)

# 探索后（主动交互确认，括号内包含具体字段信息）：
操作模式: Read(列表+搜索+分页), Create(新增按钮→Modal, 字段: 名称(text/必填)/类型(select)/描述(textarea)), Update(编辑按钮→Drawer, 预填充表单同Create), Delete(删除按钮)
```

## 1.6 产出检查清单

写入产出文件前，必须逐项检查：

| 检查项 | 要求 |
|--------|------|
| 操作模式字段 | 每个页面必须包含 `操作模式` 字段，且至少标注一个模式 |
| 模式格式 | 必须使用 `模式名(识别依据)` 格式，如 `Read(列表+搜索+分页)` |
| 模式来源 | 必须对照 operation-patterns-modes.md 的 15 种模式定义识别，禁止自造模式名 |
| 页面完整性 | 每个页面必须包含：名称、URL/路径、描述、操作模式、元素、操作 |
| 主动交互覆盖 | 如 explore_interactive=true，有新增/编辑按钮的页面其操作模式应包含具体字段信息 |
| 新 Tab 覆盖 | 所有通过新 Tab 打开的页面必须被探索或标注降级原因 |
| 降级标记 | snapshot 为空的页面必须标注降级级别（⚠️[snapshot降级:Level N]） |
| 编码完整性 | 文件不含乱码字符（�/U+FFFD），降级提取的文本需逐段检查可读性 |
| 业务链路 | 如识别到跨页面链路，必须在报告中列出 |
| L3 清理记录 | 如执行了 L3 受控创建，必须记录清理指令（数据标识、创建页面、清理方式） |

## 1.6.5 业务链路合并

所有页面探索完成后，合并链路片段为完整业务链路：

```
1. 从内存链路队列中取出所有链路片段
2. 串联规则：按页面跳转关系关联
   - 同一源页面的多个链路片段归并
   - 目标页面 = 另一片段的源页面 → 串联为更长链路
3. 链路类型标注：
   - CRUD：Create→Detail→Edit→Delete
   - 发布：Edit→Preview→Publish
   - 审批：Submit→Review→Approve
   - 配置：Create→Config→Save
4. 覆盖状态标注：
   - 已探索 ✅：链路中所有页面均已被 DFS 或新 Tab 探索
   - 待确认 ❓：链路中存在未探索的页面（如降级页面、超出深度限制）
   - 受限跳过 ⏭️：链路涉及 X-禁止操作（如导出/删除），探索阶段不触发，Phase 3 执行阶段验证
5. 将合并后的链路列表写入功能分析报告的「业务链路」章节
```

## 1.7 产出

写入 `{输出目录}/功能分析报告.md`，模板见 [templates.md](templates.md) 功能分析报告章节。

写入完成后 → AskUserQuestion 请用户确认 → 门控通过后进入 Phase 2。
