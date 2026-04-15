---
name: cc-diagram
description: 生成Mermaid图表（流程图/序列图/ER图/类图等15种），内置防错规则和选型决策树。不分析接口调用链。用于可视化架构、流程、数据关系、统计分析
allowed-tools: Read, Grep, Glob, Write
argument-hint: "[图表类型，如 流程图 / 序列图 / ER图]"
paths: ["**/*.mmd", "**/*.mermaid"]
---

# Mermaid 图表专家

## Overview

支持 15 种 Mermaid 图表生成，内置 9 条防错规则 + 5 项验证检查 + 统一色彩语义 + 信息密度控制，确保语法正确、可渲染、重点突出。

**适用场景**：流程图、序列图、类图、状态图、ER 图、甘特图、思维导图、统计分析可视化

**不适用场景**：

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 图片格式输出（PNG/SVG 等） | Mermaid 渲染工具 | 本 Skill 只生成 Mermaid 代码，不输出图片文件 |
| UI 设计图/原型图 | Figma 等设计工具 | Mermaid 不支持 UI 级别的视觉设计 |
| 工程图纸/CAD | 专业 CAD 软件 | 超出 Mermaid 图表能力范围 |
| 接口调用链分析+ER图 | cc-api-analyzer | cc-api-analyzer 追踪调用链后自动委托 diagram 生成 ER 图 |

## Gotchas

> 从实际使用中积累的常见陷阱。>200 行文件置于前部（primacy effect）。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 节点文本含特殊字符（`:()[]{}@;,`）未用双引号包裹 | Mermaid 解析失败，图表无法渲染 | 含特殊字符的节点文本必须用双引号包裹（防错规则 1） |
| 2 | 单张图表节点数超过 15 个 | 图表过于密集，认知负荷过高，重点不突出 | 拆分为多张子图，或用 subgraph 分组，核心节点控制在 5 个以内 |
| 3 | 跳过资源加载直接凭记忆写模板 | 语法细节出错（如 classDiagram 关系符号、erDiagram 基数写法） | 必须先 Read 对应的 `templates/` 文件获取正确语法模板 |
| 4 | 生成图表后未执行防错验证清单 | 交付的图表在 Mermaid 渲染器中报错 | 生成后逐项检查防错验证清单（9 条规则 + 5 项检查） |
| 5 | subgraph 嵌套层级过深或节点 ID 与 Title 混淆 | 外部节点无法引用 subgraph 内节点，或渲染器解析失败 | subgraph 嵌套不超过 2 层，ID 和 Title 分开声明 |
| 6 | 接收 cc-api-analyzer 数据格式不匹配 | ER 图渲染失败或关系丢失 | 接收前验证 entities/relationships YAML 结构，缺失字段提示调用方补充 |
| 7 | 统计分析结果用大段文字描述而非图表 | 用户需要反复阅读才能理解分布/趋势/对比 | 应用图优先原则：占比→pie、趋势→timeline、对比→flowchart+subgraph |
| 8 | 大型图表试图一张图展示所有细节 | 渲染超大/无法一屏阅读/重点淹没 | 按分阶段展开策略：总览图(L0) → 详情图(L1) → 交叉关系图(L2) |
| 9 | beta 图表类型漏写 `-beta` 后缀或忽略版本要求 | 渲染器不识别，图表无法生成 | xychart-beta/sankey-beta/architecture-beta 必须带 `-beta`；radar(v11.6+)/quadrantChart(v10.3+) 无需 `-beta` 但有最低版本要求 |
| 10 | 统计报告只有图表没有 SQL 或只有结论没有推理 | 数据不可验证、因果不可追溯 | 每个数据论点必须三件套：图表（可视化）+ SQL（可验证）+ 逻辑描述（统计什么+想证明+结论） |
| 11 | 引用块（`>`）多行内容之间没有空行 | Obsidian 合并成一段，排版挤在一起 | `>` 引用块内多行之间必须用 `>` + 空行分隔（`>\n>\n> 下一行`），否则 Obsidian 渲染为同一段 |

---

## 协作关系

- **接收自**: cc-api-analyzer（ER 图数据）、cc-design（架构图需求）
- **委托给**: 无（终端工具 Skill）
- **隐式依赖**: 无

> 详细协作矩阵见 `shared-rules/skill-orchestration.md` 第二章

### 数据契约

**输入（接收自 cc-api-analyzer/cc-design 时）**：

| 字段 | 来源 | 说明 |
|------|------|------|
| entities | cc-api-analyzer Phase 3 | 表/实体列表（名称+字段） |
| relationships | cc-api-analyzer Phase 3 | 表间关系（1:N/M:N + FK 字段） |
| 图表类型 | 调用方指定 | flowchart/sequenceDiagram/erDiagram/classDiagram 等 |
| 业务上下文 | 调用方传入 | 用于标注和分组的领域信息 |

**输出**：Mermaid 代码块（含 classDef 样式声明 + 图例表格 + 备注）

> 完整字段定义见 `shared-rules/data-contracts.md` 和 `templates/templates-visual-examples.md`

---

## 资源加载指导

| 场景 | 加载文件 | 读取范围 | 不加载 |
|------|---------|---------|--------|
| 不确定用哪种图表 | 本文件 选型决策树 | 选型决策树章节 | templates/（待选型确定后再加载） |
| 视觉配色/classDef 声明/标注方式 | `templates/templates-visual-examples.md` | 全量 | 其他 templates/ |
| 生成流程图/序列图 | `templates/templates-flow-seq.md` | 全量 | class-state, er-gantt-mind, pie-timeline-c4 |
| 生成类图/状态图 | `templates/templates-class-state.md` | 全量 | flow-seq, er-gantt-mind, pie-timeline-c4 |
| 生成 ER 图/甘特图/思维导图 | `templates/templates-er-gantt-mind.md` | 全量 | flow-seq, class-state, pie-timeline-c4 |
| 生成饼图/时间线/C4 架构图 | `templates/templates-pie-timeline-c4.md` | 全量 | flow-seq, class-state, er-gantt-mind |
| 渲染失败/语法错误排查 | `resources.md` 常见错误章节 | 按标题定位 | templates/ |
| 样式/主题配置 | `resources.md` 样式配置章节 | 按标题定位 | templates/ |
| 统计分析/数据可视化 | `templates/templates-pie-timeline-c4.md` + `templates-visual-examples.md` 第四章 | 全量 + 信息密度控制章节 | class-state, er-gantt-mind |
| 生成 xychart/sankey/architecture/quadrant/radar | `templates/templates-new-charts.md` | 全量 | 其他 templates/ |
| 写入 Obsidian 的数据图表 | `templates/templates-new-charts.md`（Charts 插件章节） | Charts 插件模板部分 | Mermaid xychart 部分 |
| 遇到需求模糊时 | `shared-rules/inquiry-protocol.md` | 全量 | templates/, resources.md |

## 图优先原则

> **核心**：能用图表说清楚的，不用文字段落描述。图表是一等公民，文字是辅助。

### 渲染引擎选择（按输出目标）

| 输出目标 | 数据图表（折线/柱状/饼图/雷达） | 结构图表（流程/序列/类图/状态/ER/架构） |
|---------|---------------------------|----------------------------------|
| **写入 Obsidian（知识库）** | **Obsidian Charts**（`chart` 代码块，Chart.js，原生图例+断线+交互） | **Mermaid**（`mermaid` 代码块） |
| **对话输出 / 非 Obsidian** | Mermaid xychart-beta + HTML 图例 | Mermaid |

> 判断依据：写入路径含 `shuhe-kb/` 或 `tools/` → Obsidian 目标 → 数据图表用 Charts 插件
> **降级**：Charts 插件不可用时，退化为 Mermaid xychart-beta + 数据表格（不生成 `chart` 代码块）

**触发判断**：当回复中涉及以下内容时，优先用图表表达：

| 内容类型 | 图表化方式 | 文字仅保留 |
|---------|----------|-----------|
| 数据分布/占比 | pie（Obsidian: `chart` type:pie） | 一句话结论 + 数据来源说明 |
| 趋势/变化/对比 | xychart-beta / Obsidian Charts type:line（数值）/ timeline（里程碑） | 变化原因分析 |
| 流程/步骤/决策 | flowchart（始终 Mermaid） | 关键步骤的补充说明 |
| 架构/模块关系 | C4 / architecture-beta / flowchart / classDiagram（始终 Mermaid） | 技术决策备注 |
| 状态流转 | stateDiagram-v2（始终 Mermaid） | 触发条件的业务规则 |
| 实体关系 | erDiagram（始终 Mermaid） | 索引/分表策略说明 |

**不适合图表化的场景**：纯文本解释（概念定义）、代码片段展示、SQL 输出结果。

---

## 统计报告表达方法论（强制）

> 基于 Assertion-Evidence 模式（McKinsey 金字塔 + Tufte 数据墨水 + Knaflic 数据叙事）。
> **核心**：结论先行 → 证据支撑 → 一句解读。每个论点只承载一个核心发现。

### 单个数据论点结构（Assertion-Evidence）

```
### {断言标题}（含数字和方向，如"weapp 关闭导致 T0 率下降 1.6pp"）

> **查了什么**：一句话（数据源+维度+时间范围）
> **想证明**：一句话（推理目的）

{摘要表格}（3-5 行关键拐点，红绿标变化方向）

{图表}（全区间趋势可视化，图内自解释）

> **结论**：一句话关键发现 + 下一步行动建议

> [!note]- 📊 查询 SQL（Obsidian）/ <details>（普通 md）
> ` ` `sql
> SELECT ... -- 完整可执行，带字段注释
> ` ` `
```

**⛔ 断言标题**：标题本身传递结论，禁止描述性标题
- ❌ `### 2.1 渠道拆解分析` → ✅ `### 2.1 weapp 关闭移除 28% 分母，T0 率降 1.6pp`
- ❌ `### 2.4 CANCEL 率变化` → ✅ `### 2.4 CANCEL 率从 78% 降至 39%，边际用户涌入稀释 T0 率`

### 表格 vs 图表选择标准

| 场景 | 用图表 | 用表格 |
|------|--------|--------|
| 读者需要什么 | 趋势感知、模式识别、快速对比 | 精确数值、自行验算、多维度交叉 |
| 数据特点 | 连续时间序列、分布、占比 | 少量关键行（<10 行）、混合度量单位 |
| 受众 | 决策者/管理层（3 秒看懂） | 分析师（需要逐行核对） |

**判断口诀**：读者需要「精确值」→ 表格，需要「趋势感知」→ 图表。**两者同时出现时各司其职**。

### 表格与图表协同规则

| 组件 | 职责 | 做什么 | 不做什么 |
|------|------|--------|---------|
| **摘要表格** | 关键拐点 + 精确值 + 变化方向 | 3-5 行拐点，红绿标注变化 | 不列全部日期（那是 SQL 的事） |
| **图表** | 全区间趋势形态 | 所有数据点的连续可视化 | 不在节点上堆满数字 |
| **SQL** | 完整数据源 + 可验证 | 折叠块，复制即可跑 | 不直接展示（折叠） |

### 表格色彩语义（突出数据变化，强制）

> 不只标"变化"列 — **变化的数值本身也标色**，让整行因果链一眼串起来。

**四色体系**（Obsidian 内联 HTML）：

| 颜色 | 语义 | 用于 | HTML |
|------|------|------|------|
| <span style="color:red">**红色**</span> | 下降/恶化/异常 | 指标下降、人数骤降、负面变化 | `<span style="color:red">` |
| <span style="color:green">**绿色**</span> | 上升/恢复/好转 | 指标回升、恢复正常、正面变化 | `<span style="color:green">` |
| <span style="color:#2196F3">**蓝色**</span> | 基线/参照/锚定 | 基线值、对照组、锚定数据 | `<span style="color:#2196F3">` |
| **黑色（默认）** | 无变化/中性 | 稳定期数据、无方向性信息 | 不标色 |

> 普通 md 不支持内联 HTML 时：🔴 下降 / 🟢 上升 / 🔵 基线

**标色范围**：不只标"变化"列，**所有发生变化的数值都标色**：

```markdown
| 场景 | weapp 成功人数 | hb 成功人数 | 总 T0 率 | 变化 |
|------|-------------|-----------|---------|------|
| <span style="color:#2196F3">**3/10 基线**</span> | <span style="color:#2196F3">773×83.6% = 646</span> | <span style="color:#2196F3">1,948×80.4% = 1,566</span> | <span style="color:#2196F3">**81.3%**</span> | — |
| 假设只有 weapp 变 | <span style="color:red">500×76.8% = 384</span> | 1,948×80.4% = 1,566 | 79.7% | <span style="color:red">**-1.6pp**</span> |
| 假设只有 hb 变 | 773×83.6% = 646 | <span style="color:red">1,763×78.6% = 1,386</span> | 80.1% | <span style="color:red">**-1.2pp**</span> |
| **实际（两者都变）** | <span style="color:red">500×76.8% = 384</span> | <span style="color:red">1,763×78.6% = 1,386</span> | <span style="color:red">**78.2%**</span> | <span style="color:red">**-3.1pp**</span> |
```

**标色规则**：
- 基线行全部蓝色（锚定参照物）
- 变化的单元格标红/绿（不变的保持黑色 → 对比之下立刻看出哪些列动了）
- 结果列（如总 T0 率）跟随方向标色
- 同一行内只标**发生变化的数值**，未变的留黑 → 读者一眼看出「这行改了什么」

### 信噪比原则（Tufte Data-Ink Ratio）

- **每个视觉元素必须有理由**：加一个元素前问「删掉它信息会丢失吗？」——不会则删
- **一图一观点**：一张图表只表达一个核心发现，禁止一图多义
- **去装饰**：无 3D 效果、无装饰线、无多余网格线、无无意义颜色

### 报告叙事规则

> SCQA 结构、N1-N8 认知科学驱动规则、自检方法详见 [references/report-narrative-rules.md](references/report-narrative-rules.md)。

**三件套要求**：

| 组件 | 必须 | 标准 |
|------|------|------|
| **图表** | ✅ | 展示全区间数据趋势，图内自解释（标题含指标名、图例清晰） |
| **摘要表格** | ✅ | 3-5 行关键拐点，红绿标变化方向，精确数值可读 |
| **SQL/数据来源** | ✅ | 完整可执行 SQL（复制即可跑）、带字段注释。Obsidian: 用 Callout 折叠（`> [!note]- 📊 查询 SQL`）；普通 md: 用 `<details>`。非数据库场景（API/CSV/日志）：标明数据来源、查询方式、时间范围 |
| **逻辑描述** | ✅ | 用 `> **统计什么** + **想证明**` 两行说清目的，结论用 `>` 引用块一句话总结 |

**⛔ 诚实原则（最高优先级）**：

> 报告中的每一句断言都必须有数据支撑。没有数据就不要写。不确定就标注不确定。

- **每句话问自己**：这句话的数据依据是什么？能指向哪一行表格/哪条 SQL 结果？指不出来就删掉或标注为假设
- **禁止无证据断言**：如"用户质量高""效果显著""明显改善" — 必须跟具体数字（多高？显著到什么程度？改善了几个 pp？）
- **不确定就说不确定**：用 `⚠️ 假设`/`待验证`/`推测` 显式标注，不要把推测写成结论
- **衍生数字必须展示计算过程**：如 `262/273 = 95.9%`，不要直接写 95.9% 让读者不知道怎么来的
- **反事实/估算标注方法论**：如"反事实法估算"要说清假设条件，让读者能质疑

**反模式**（禁止）：
- ❌ 只有图表没有 SQL → 数据不可验证
- ❌ 只有 SQL 没有图表 → 结论不直观
- ❌ 只有结论没有推理过程 → 读者无法判断因果方向
- ❌ SQL 用 `SELECT *` 或省略 WHERE 条件 → 违反全局 CLAUDE.md 完整性规则
- ❌ 数字无出处 → 每个数字必须可追溯到表格行或 SQL 结果

---

## 统计分析场景选型

> 统计分析的结果应结合统计学概念，用最合适的图表呈现。

| 统计场景 | 推荐图表 | 统计学原理 | 示例 |
|---------|---------|-----------|------|
| 分类占比（某维度各类别份额） | **pie** | 离散分布/频率分布 | 渠道来源占比、错误类型分布 |
| 流程漏斗（只看各步转化率） | **flowchart TD** | 转化分析/漏斗模型 | 注册→激活→付费（只看百分比） |
| 同维度对比（A vs B 单指标） | **flowchart LR** + subgraph 分组 | 对比分析 | 方案 A/B 性能单项对比、版本间差异 |
| 时间演进（里程碑/趋势） | **timeline** | 时间序列 | 系统迭代历程、指标月度变化 |
| 任务排期与依赖 | **gantt** | 关键路径/甘特分析 | 项目排期、任务依赖关系 |
| 因果/归因拆解 | **mindmap** | 根因分析/鱼骨图思维 | 故障原因拆解、指标波动归因 |
| 系统架构分层 | **C4Context/C4Container** | 分层抽象 | 微服务架构、系统边界 |
| 柱状/折线趋势（数值型对比） | **xychart-beta**（简单）/ **Obsidian Charts**（复杂多线/有缺口） | 连续分布/时间序列 | QPS 趋势、月度指标对比、版本性能对比 |
| 流量漏斗（追踪流失去向） | **sankey-beta** | 流量守恒/桑基分析 | 用户流失路径、资金流向（关心"流失到哪"） |
| 多维能力评估（雷达对比） | **radar** | 多维度对比 | 方案评分、团队能力、服务健康度 |

---

## 执行步骤

1. **判断图优先** → 回复内容是否适合图表化（见图优先原则）
2. **识别图表类型** → 匹配下方选型决策树（统计场景优先参考上方统计选型表）
3. **评估规模** → 预估节点数，>15 按分阶段展开策略处理（见信息密度控制）
4. **提取核心元素** → 节点、关系、层次、时序等
5. **选用模板** → Read `templates/` 对应文件（见资源加载指导）
6. **生成代码** → 应用防错规则 + 视觉重点样式（见下方规范）
7. **验证输出** → 逐项执行防错验证清单 + 视觉重点验证清单
8. **标准化输出** → 按 `resources.md` 输出格式呈现

## 选型决策树（15 种图表）

```
需要展示什么？
├─ 流程/步骤/条件分支 → flowchart
├─ 系统间交互/API调用时序 → sequenceDiagram
├─ 类/接口/继承关系 → classDiagram
├─ 状态转换/生命周期 → stateDiagram-v2
├─ 数据库表/实体关系 → erDiagram
├─ 项目排期/任务依赖 → gantt
├─ 知识结构/功能分解 → mindmap
├─ 占比分析/数据分布 → pie
├─ 发展历程/里程碑回顾 → timeline
├─ 系统架构/容器关系 → C4Context / C4Container
├─ 柱状图/折线图/趋势对比 → xychart-beta（Mermaid v10.7+）
├─ 流量分布/转化漏斗/资金流向 → sankey-beta（Mermaid v10.3+）
├─ 云架构/部署拓扑 → architecture-beta（Mermaid v11.1+）
├─ 优先级矩阵/二维评估 → quadrantChart（Mermaid v10.3+）
├─ 多维对比/能力评估 → radar（Mermaid v11.6+）
└─ 统计分析/数据可视化 → 参考「统计分析场景选型」表（上方）
```

---

## 防错规则（9 条规则 + 5 项验证检查，必须遵守）

| # | 规则 | 错误 | 正确 | 原因 |
|---|------|------|------|------|
| 1 | 特殊字符(`:()[]{}@;,`)必须转义 | `A[Method: getName()]` | `A["Method: getName()"]` | 这些字符是 Mermaid 语法符号，未转义会打断解析 |
| 2 | 避免小写 `end` 作为节点名 | `start --> end` | `start --> End` | `end` 是保留关键字，用于结束 subgraph/alt/loop 块 |
| 3 | subgraph 必须同时有 ID 和 Title | `subgraph "标题"` | `subgraph id["标题"]` | 只有 Title 没有 ID 时，外部无法引用 subgraph 内节点 |
| 4 | note 仅在 sequenceDiagram 和 stateDiagram-v2 中有效 | flowchart/classDiagram 中用 note | flowchart 用 `-.-` 虚线节点 | `note` 仅 sequenceDiagram 和 stateDiagram-v2 支持，flowchart/classDiagram/erDiagram 中不识别 |
| 5 | classDiagram 先定义类再建立关系 | 直接写 `User --> Order` | 先 `class User {}` 再写关系 | 先定义类再建立关系是最佳实践，可避免潜在的版本兼容性问题 |
| 6 | mindmap 缩进必须一致 | Tab 和空格混用 | 统一使用空格（2或4） | Tab/空格混用导致层级解析错乱，图表结构混乱 |
| 7 | 避免 `AND`/`OR` 作为节点文本 | `A["AND gate"]` | `A["and gate"]` 或用 `&amp;` | `AND`/`OR` 是内部逻辑运算符，可能干扰解析 |
| 8 | flowchart 连线后节点名避免以小写 o/x 开头 | `dev---ops` | `dev--- ops` 或 `dev---Ops` | 小写 `o`/`x` 开头会被解析为连线端点符号（圆端/叉端） |
| 9 | 用 classDef + `:::` 替代逐节点 `style` | 每节点写 `style X fill:...` | 定义 `classDef` 后用 `:::className` | 减少代码重复，语义更清晰，维护更方便 |

---

## 防错验证清单

- [ ] 特殊字符（`:()[]{}@;,`）已用双引号包裹
- [ ] 无小写 `end` 作为节点名
- [ ] subgraph 同时有 ID 和 Title
- [ ] note 仅在 sequenceDiagram 和 stateDiagram-v2 中使用
- [ ] classDiagram 类定义在关系之前
- [ ] mindmap 缩进一致（空格/Tab 不混用）
- [ ] 无 AND/OR 大写作为节点文本
- [ ] flowchart 连线后节点名不以小写 o/x 开头
- [ ] 使用 classDef + `:::` 而非逐节点 `style`（规则 9）
- [ ] 代码块使用 ` ```mermaid ` 标记
- [ ] 单个代码块只包含一个图表声明
- [ ] init 配置（`%%{init:...}%%`）在代码块第一行
- [ ] 甘特图无任务依赖循环
- [ ] 语法符合所有防错规则，逻辑自检无误

---

## 视觉重点规范

> **核心原则**：读者看图 3 秒内就能知道「这张图说的是什么」「重点在哪」「哪些是新的/变的」。
> 认知负荷：核心元素不超过 5 个（4±1 原则），总节点 >15 必须按分阶段展开策略拆图（见 `templates/templates-visual-examples.md` 第四章）。

**5 种 classDef 语义**：`core`（紫/核心入口）、`newAdd`（绿/新增写入）、`external`（蓝/外部依赖）、`readOnly`（黄/读取查询）、`warn`（红/风险异常）。默认样式 = 已有不变。

**强制要求**：
- **⛔ 图内自解释**：每条线/每个分组/每个维度/每个节点的含义必须标注清楚。具体：标题含指标名和对比维度（如"总体 vs hb"）、节点文本含业务含义、xychart 多线保持同图对比（不拆图，在标题+图后注释标明各线含义）、用 subgraph 标题区分分组
- 图表前有一句话说明（含「重点关注什么」）
- 图表后有图例表格（仅列实际使用的样式）
- 至少 1 条辅助备注（设计决策/关键约束/交互说明/业务规则）
- 使用 `classDef` + `:::` 而非逐节点 `style`

> 详细配色声明、各图表标注方式、信息密度控制、备注规范、完整示例见 `templates/templates-visual-examples.md`

---

## 视觉重点验证清单

- [ ] **图内自解释**：每条线/分组/维度的含义可读（标题含指标名+对比维度、节点含业务含义、xychart 多线保持同图+图后注释标明各线、subgraph 标题区分分组）
- [ ] 核心元素已用紫色高亮标注（每张图至少 1 个核心元素；pie/sankey/xychart 不支持 classDef，此条跳过）
- [ ] 新增/变更元素已用绿色标注（如有变更场景）
- [ ] 已有/不变元素使用默认样式（不抢视觉注意力）
- [ ] 图表前有一句话说明（含「重点关注什么」）
- [ ] 图表后有图例表格（仅列实际使用的样式）
- [ ] 扩展点已用虚线/注释标注（如有）
- [ ] 图表包含至少 1 条辅助理解的备注（设计决策/关键约束/交互说明/业务规则）
- [ ] 使用 classDef 而非逐节点 style（规则 9）
- [ ] 核心节点不超过 5 个（4±1 认知负荷原则）
- [ ] 总节点数 ≤15，否则已拆图或用 subgraph 分组

---

## 输出质量标准

- [ ] 图表可在 Mermaid 渲染器中无错误渲染
- [ ] 节点命名清晰有语义（禁止 node1/A/B 等无意义命名）
- [ ] 布局方向符合阅读习惯（流程用 TD/LR，时序用默认）
- [ ] 复杂图表有 subgraph 分组或注释辅助理解
- [ ] 粒度适中（核心逻辑完整，不过度展开细节）
- [ ] 视觉重点验证清单全部通过

