---
name: cc-web-tester
description: 通过Playwright MCP执行网页功能自动化测试，输出测试报告。不写后端代码、不做API测试。用于验收测试、回归测试、UI功能验证
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Write, Bash, Agent, mcp__playwright__*
report_generation: true
report_protocol: data-report-protocol
report_protocol_mode: full
---

> **Report Generation 声明**（data-report-protocol Iter 22）：本 skill 生成功能分析报告 + 测试用例 + 测试报告。**特殊约定**：测试报告的 quote grounding 形式映射到 `evidence/` 目录的真实证据文件——每个 pass/fail 判定必须附 `<evidence type="screenshot|dom-snapshot|fixture" path="evidence/batch-N/..."/>` 标签（quote 等效形式）。代码 quote 不适用（cc-web-tester 不读源码），但 Phase 1 功能分析报告中提到的 DOM 元素必须附 `<dom-snapshot path="..."/>`。找不到 evidence 支持的 finding 必须删除并标记 `[REMOVED:no-evidence]`。

# 网页功能自动化测试

**三阶段工作流**：界面探索 → 用例生成 → 模拟执行，主 agent 协调 + 子 agent 执行测试。

---

## When to Use

**适用场景**：
- 用户提供 URL，要求测试网页功能
- 需要对 Web 页面生成测试用例
- 需要通过 Playwright MCP 自动化执行功能测试
- 验收测试、回归测试的辅助手段

**不适用场景**：

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 单元测试 / API 接口测试 | JUnit、Postman | 本 Skill 通过浏览器测试 UI 功能，不测后端接口 |
| 性能测试 / 压力测试 | JMeter、k6 | 本 Skill 做功能验证，不做性能基准测试 |
| 代码审查 | cc-code-reviewer | 本 Skill 测试网页功能，不审查代码质量 |
| 无 Playwright MCP 环境 | - | 本 Skill 依赖 Playwright MCP，无环境无法执行 |

---

## 三阶段总览

```
主 agent（协调者 + 文档撰写者）
├── Phase 1: EXPLORE — 主 agent 执行
│   └── 登录等待 → BFS+DFS 探索 → 模式识别 → 产出：功能分析报告.md → 用户确认
├── Phase 2: GENERATE — 主 agent 执行
│   └── 读取报告 → 设计用例 → 产出：测试用例.xmind + .md → 用户编辑 xmind
├── Phase 2.5: SYNC — 主 agent 执行
│   └── 检测 xmind 修改 → 反向同步 → 用户确认
└── Phase 3: EXECUTE — 子 agent 执行
    └── 按 batch 分组 → Agent(test-batch-N) → 汇总 → 测试报告.md + .xmind
```

**阶段门控**：每阶段产出完成 + 用户确认后才进入下一阶段。禁止跳过确认、禁止未回收全部 batch 就生成报告。

详细流程见 [workflows.md](workflows.md)（索引） → `workflows/` 子目录各阶段文件。

---

## 产出文件目录

```
{项目根}/doc/test/{网站标识}/
# 网站标识：URL 域名，点号→短横线（如 admin.foo.cn → admin-foo-cn）
├── 功能分析报告.md              ← Phase 1
├── 测试用例/                    ← Phase 2
│   ├── 测试用例.md / .json / .xmind
└── 测试报告/                    ← Phase 3
    ├── 测试报告.md / .json / .xmind
    └── evidence/                ← 执行证据（batch-N.md + screenshots/ + fixtures/ + downloads/）
```

---

## 已知限制

| 类别 | 说明 |
|------|------|
| Shadow DOM / iframe | 无障碍树无法穿透，跨域 iframe 内元素不可交互 |
| 认证 | 需用户在浏览器中手动登录（Phase 1 含登录等待步骤） |
| 动态内容 / SPA | 懒加载、无限滚动可能遗漏；SPA 基于 snapshot 内容差异判断页面切换 |
| 微前端 | qiankun 等子应用 snapshot 可能为空，启用 snapshot_fallback 降级（截图+DOM 概要） |
| AI 误判 | 通过/失败判断存在误判，报告需人工复核 |
| 浏览器共享 | 子 agent 并行时共享浏览器实例，默认串行执行避免冲突 |
| L3 创建数据残留 | 受控创建的测试数据需手动删除，报告中记录清理方式 |

---

## 资源加载指导

| 场景 | 加载文件 |
|------|---------|
| 进入任一阶段 | [workflows.md](workflows.md) 对应章节 |
| 生成文档时 | [templates.md](templates.md) 对应模板 |
| Phase 1 模式识别 / Phase 2 用例设计 | [references/operation-patterns-modes.md](references/operation-patterns-modes.md) |
| Phase 3 批次编排 | [references/operation-patterns-execution.md](references/operation-patterns-execution.md) |
| Phase 3 子 agent 执行 | [references/operation-patterns-execution.md](references/operation-patterns-execution.md) 组件操作 Playbook |
| 生成 xmind 时 | [scripts/generate-xmind.py](scripts/generate-xmind.py) |
| xmind 反向同步时 | [scripts/xmind-to-json.py](scripts/xmind-to-json.py) + [scripts/json-to-md.py](scripts/json-to-md.py) |
| 首次使用 Playwright MCP | [references/playwright-tips.md](references/playwright-tips.md) |
| 遇到需求模糊时 | `shared-rules/inquiry-protocol.md` |

---

## 协作关系

| 关系 | 对象 | 说明 |
|------|------|------|
| 接收自 | user | 直接提供 URL 触发 |
| 接收自 | cc-planner | 规划中的测试任务 |
| 独立运行 | - | 不委托其他 Skill |

### 数据契约（planner 委托时）

**输入**：url（必填）、scope（可选）、priority_filter（可选）

**输出**：report_path、total、passed、failed、blocked、pass_rate

---

## Gotchas

> 从实际使用中积累的常见陷阱。每次发现新问题时追加。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | Playwright MCP snapshot 超时 | 页面未完全加载时截图/快照不完整 | snapshot 前等待网络空闲或关键元素可见，失败时重试一次 |
| 2 | 表单填充前未等待元素可交互 | fill 操作失败或填入错误的输入框 | 使用 browser_wait_for 等待目标元素可见且可交互后再操作 |
| 3 | 跨页面导航后使用旧 DOM 引用 | 元素定位失败或操作到错误元素 | 页面导航后重新 snapshot 获取新的 DOM 结构 |
