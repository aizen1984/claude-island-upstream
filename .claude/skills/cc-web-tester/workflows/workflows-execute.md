# Phase 3: EXECUTE（模拟测试执行）

## 3.1 主 agent：智能编排与分组派发

详细编排算法见 [references/operation-patterns-execution.md](../references/operation-patterns-execution.md) 智能编排规则章节。

```
1. 读取「测试用例/测试用例.json」（xmind 同步后的最新数据）
2. 按 priority_filter 过滤（默认 P0,P1,P2）
3. ⚠️ **智能编排（强制，禁止按用例编号顺序直接分组）**：
   a. 从 data_lifecycle 字段提取所有 creates/depends/consumes 非空的用例
   b. 构建闭环链（creates→depends→consumes），每条链作为一个闭环组
   c. 闭环组内按拓扑排序（Create 在前，Delete 在后）→ 放入 **Batch 1..N**
   d. 独立用例（所有 data_lifecycle 全为 null 的用例）按优先级 P0→P1→P2 排序
   e. 用独立用例填充闭环组的剩余槽位，溢出的独立用例按 execute_batch_size 分到后续 Batch
   f. 如有「显式清理型」测试数据，在最后追加 cleanup batch
   **编排自检**：输出编排方案后，逐条验证：
   - 闭环组是否在 Batch 1（或最早的 Batch）？
   - 闭环组内 Create 是否在 Delete 之前？
   - 是否有未分配的用例？
4. 按 execute_batch_size 分组（默认 5 条/批）
5. 确定输出目录：{输出目录}/测试报告/evidence/
6. 为每个批次构造子 agent prompt（见下方），附带组件操作 Playbook 提示
7. 按批次顺序启动子 agent（run_in_background: false，串行执行）
   - 串行避免多 agent 共享浏览器实例导致冲突
   - 如用户明确要求并行：每个子 agent 需先 browser_tabs(action="new") 创建独立 tab
8. 等待当前批次完成后启动下一批次
9. 读取 evidence/batch-*.md 汇总报告
```

**编排示例**：
```
闭环组: TC-016(Create) → TC-022(Update) → TC-023(Update) → TC-025(Delete)
→ 编排到 Batch 1，闭环内数据自动清理

独立用例: TC-001, TC-004, TC-013, TC-030 ...
→ 按优先级填充后续 Batch
```

## 3.1.5 测试数据命名规范

测试过程中创建的数据必须遵循安全命名规则，避免目标系统字符校验拦截：

| 阶段 | 前缀 | 示例 |
|------|------|------|
| Phase 1 探索（L3） | `E2E-EXPLORE-` | `E2E-EXPLORE-探索测试` |
| Phase 3 执行（Create 用例） | `E2E-TEST-` | `E2E-TEST-自动化测试数据集` |

**安全字符集**：仅使用字母、数字、横线(`-`)、下划线(`_`)、中文。

**禁止字符**：`[](){}<>!@#$%^&*+=|\\/"':;,?` 等特殊字符。多数业务系统的名称字段有字符白名单校验，使用安全字符集可避免创建失败。

## 3.2 子 agent prompt 模板

Agent 调用参数：`max_turns: 30`，`subagent_type: "general-purpose"`

```
你是一个网页功能测试执行者。

目标 URL: {url}
输出文件: {输出目录}/测试报告/evidence/batch-{N}.md
截图目录: {输出目录}/测试报告/evidence/screenshots/

执行以下测试用例，将结果写入输出文件：

{该批次的用例列表，从测试用例.md 中截取}

执行规则：
1. 对每条用例：browser_navigate 到目标页面 → 按步骤执行 → snapshot 验证
2. 每条用例执行完最后一步后，无论结果如何，browser_take_screenshot 截图存入截图目录（文件名: TC-{编号}-result.png）
3. 失败用例额外在失败点截图（文件名: TC-{编号}-fail.png），与 result 截图可能不同
4. 如配置 screenshot_on_step=true，在关键步骤（表单填写后、按钮点击后、页面跳转后）额外截图（文件名: TC-{编号}-step-{M}.png）
5. 连续 {stop_on_consecutive_failures} 条失败则停止，标记剩余为"跳过"
6. ⚠️ **输出文件格式（必须严格遵循）**：先写文件头，再逐条写用例结果

**文件头（必须在第一条用例之前写入）**：
# Batch {N} 执行结果

- **执行时间**: {当前日期 YYYY-MM-DD}
- **目标URL**: {url}
- **用例范围**: TC-{起始编号} ~ TC-{结束编号}
- **结果**: 通过 [X] | 失败 [Y] | 阻塞 [Z] | 跳过 [W]
- **停止原因**: {正常完成|连续失败暂停|max_turns 耗尽}

---

**每条用例格式**：

### TC-{编号}: {描述} [{通过|失败|阻塞|跳过}]
- **预期结果**: {从用例复制}
- **实际结果**: {具体描述实际看到的内容，不能只写"符合预期"}
- **执行数据**:
  - 输入数据: {填写的表单值、选择的选项等，如："姓名=张三, 手机=13800138000"}
  - 关键响应: {页面提示文案、toast 内容、跳转 URL 等}
  - 数据变化: {列表新增/修改了哪条记录、状态从X变为Y等；无数据变化时写"无"}
  ⚠️ 三段结构（输入数据/关键响应/数据变化）必须完整，不可省略任何段
- **结果截图**: screenshots/TC-{编号}-result.png
- **失败截图**: {screenshots/TC-{编号}-fail.png 或 无}
- **步骤截图**: {screenshots/TC-{编号}-step-*.png 列表 或 无}
- **备注**: {失败原因/阻塞原因或空}

⚠️ 文件头中的「结果」统计必须在所有用例执行完毕后回填准确数字。先写占位符，最后用 Edit 工具回填。

行为约束：
1. 单条用例操作失败 2 次后直接标记为"失败"，不再重试
2. 元素定位失败时先 snapshot 刷新 ref，仍失败则标记为"阻塞"
2.5. click 超时（TimeoutError 5000ms）时按三级降级处理，不直接标记为失败：
   Level 1: Escape 清除遮挡 → wait(1s) → 重新 snapshot → 用新 ref 重试
   Level 2: browser_run_code JS 强制 click（跳过 actionability check）
   Level 3: browser_run_code + 自定义 timeout（如 15000ms）
   详见 playwright-tips.md §14
3. 只操作目标 URL 同域页面，不跟进外部链接
4. 结果必须写入输出文件，不要仅在对话中输出
5. 实际结果必须具体描述页面上观察到的内容（如"页面显示成功提示'保存成功'"），禁止写"符合预期"或"通过"等模糊表述
6. 通过判定必须基于 snapshot 内容与预期结果的逐条比对，不可凭操作无报错就判定通过
7. 本批次如有闭环链（Create→Update→Delete），按序执行，确保前一步创建的数据供后续步骤使用
8. 如有 cleanup 清单，在 batch 结果末尾追加「## 待清理数据」章节
9. 如配置 visual_verify=true，在关键断言点（表单提交后、状态变更后）额外 screenshot + vision 验证，结果记录到备注
10. 微前端降级页面（snapshot 为空）自动启用视觉验证，无需额外配置
11. 测试数据命名：创建操作的实体名使用 `E2E-TEST-` 前缀，仅用安全字符集（见 §3.1.5）
12. 文件上传准备：如用例步骤包含文件上传，执行前在 evidence/fixtures/ 生成最小合规 fixture 文件：
    - JSONL → 1 行: `{"messages":[{"role":"user","content":"test"},{"role":"assistant","content":"ok"}]}`
    - CSV → 表头+1 行数据
    - 其他格式 → 参考上传区域提示的格式要求生成
    - 使用 browser_file_upload 注入文件，不依赖 fileChooser 对话框
13. 下载/导出路径控制：如用例涉及导出/下载操作，执行前通过 browser_run_code 设置下载路径到 evidence/downloads/（详见 playwright-tips.md §5.5），禁止使用浏览器默认下载路径

执行模式选择：
- 默认使用 snapshot+ref 逐步模式（精确可靠）
- 以下场景可用 browser_run_code 批量加速：
  a. 导航+等待组合（navigate→wait→snapshot 合并前两步）
  b. 弹窗关闭降级序列（四级降级合并为一次 run_code）
  c. 多字段清空（逐个清空合并为一次循环）
- run_code 选择器优先级：getByRole > getByText > CSS locator（禁止 data-testid）
- run_code 失败时回退到逐步 ref 模式，记录失败原因
- ⚠️ 禁止在以下场景使用 run_code：表单填写验证、闭环链执行、首次探索未知页面

组件操作参考（减少试错）：
- Modal/Drawer: click 触发 → wait(1s) → snapshot，关闭用 X 或 Escape
- Form: 优先 browser_fill_form 批量填写
- Select: click 展开 → wait(0.5s) → click 选项
- rc-md-editor: click 编辑区 → browser_evaluate(execCommand insertText) 或 browser_type
- Popconfirm: 操作前 Escape 关闭残留气泡
- 新 Tab: browser_tabs 管理，完成后 close 回原 Tab
- Toast: 操作后 wait(1s) → snapshot 捕获，3 秒内消失
```

## 3.3 失败处理

| 场景 | 处理 |
|------|------|
| 单条失败 | 失败点截图(fail.png) + 结果截图(result.png) + 记录原因，继续下一条 |
| 连续 N 条失败 | 停止该批次，剩余标记为"跳过"，原因："连续失败暂停" |
| 页面崩溃/无响应 | 截图留证 + 标记为"阻塞"，尝试 browser_navigate 恢复，继续下一条 |
| 元素找不到 | 截图留证 + 标记为"阻塞"，记录 snapshot 中可见元素，继续下一条 |
| click 超时(5000ms) | 三级降级：Escape清遮挡→JS强制click→自定义timeout，详见 playwright-tips.md §14 |
| run_code 执行失败 | 记录错误信息 + 回退到逐步 ref 模式重试该用例，仍失败则标记为"失败" |

## 3.4 主 agent：汇总报告

```
1. 读取所有 evidence/batch-*.md
2. 统计：总数、通过、失败、阻塞、跳过
3. 按优先级分组统计通过率
4. 提取所有失败用例详情
5. 跨批次问题关联：相同问题类型的失败用例归并
6. 生成问题汇总表（按严重程度排序）
7. 提取 remark 信息：从每条用例的 batch evidence 中提取关键观察信息
   （如实际结果摘要、异常提示文案、页面行为差异等），填充到报告 JSON 的 remark 字段
8. 生成「通过用例证据」章节：
   - P0/P1 用例：逐条展开，包含实际结果摘要、执行数据、Markdown 图片内嵌截图
   - P2 用例：折叠显示（<details>），逐条列出实际结果摘要 + Markdown 图片内嵌截图
9. 生成「批次执行明细」章节：
   - 读取每个 batch 文件的完整内容
   - 按批次分组，每个批次用 <details> 折叠
   - 批次标题包含批次描述和通过率（如 "Batch 1: 列表与搜索（5/5 通过）"）
   - 批次内逐条展示：预期结果、实际结果、执行数据、Markdown 图片内嵌截图
   - 不再生成指向 batch 文件的链接表
10. 截图路径规则：
    - 主报告中：`evidence/screenshots/TC-编号-result.png`（相对于报告文件）
    - batch 文件中：`screenshots/TC-编号-result.png`（相对于 evidence/ 目录）
11. 失败用例：预期+实际+双截图（失败点+最终结果）并排内嵌
12. 写入 {输出目录}/测试报告/测试报告.md
```

模板见 [templates.md](templates.md) 测试报告章节。

## 3.5 生成测试报告 XMind

在写入测试报告.md 后，基于测试用例 JSON + batch 结果生成带执行结果标注的 xmind。

```
1. 读取 测试用例/测试用例.json
2. 读取所有 evidence/batch-*.md，解析每条用例的结果（通过/失败/阻塞/跳过）和备注
3. 构造报告 JSON（在测试用例 JSON 基础上，为每条 case 追加 result 和 remark 字段）
4. 将报告 JSON 写入 {输出目录}/测试报告/测试报告.json
5. 执行脚本生成 xmind：
   python3 {skill目录}/scripts/generate-report-xmind.py {输出目录}/测试报告/测试报告.json {输出目���}/测试报告/测试报告.xmind
6. 确认文件生成成功
```

报告 xmind 与测试用例 xmind 的区别：
- 每条用例节点标题追加结果标记（✅/❌/⚠️/⏭️）
- 失败/阻塞用例的 notes 追加实际结果和截图路径
- labels 包含结果状态（通过/失败/阻塞/跳过）

---

# 异常处理

| 阶段 | 异常场景 | 处理策略 |
|------|---------|---------|
| Phase 1 | 目标 URL 不可达（navigate 后 snapshot 无内容或报错） | 提示用户检查 URL 可达性，终止流程 |
| Phase 1 | 探索到 0 个有效页面（仅登录页，登录后仍无业务页面） | 提示用户确认登录状态和权限，终止流程 |
| Phase 3 | 子 agent 无输出（崩溃或 max_turns 耗尽未写入结果文件） | 标记该批次所有用例为"阻塞"，原因："子 agent 执行异常"，继续下一批次 |
| Phase 3 | 子 agent 部分写入后中断 | 读取已写入的结果，未写入的用例标记为"跳过" |
| Phase 2 | 功能分析报告为空或格式异常（缺少页面结构/无法解析） | 提示用户："功能分析报告为空或格式异常，请重新运行 Phase 1"，终止 Phase 2 |
| Phase 2 | 操作模式字段缺失（页面未标注操作模式） | 优先提示用户补充操作模式标注；如用户确认自动推断，则根据页面元素对照 operation-patterns-modes.md 自动识别并标注，推断结果必须请用户确认后继续 |

---

# compact 策略

## 触发时机

| 阶段 | 触发条件 | 操作 |
|------|---------|------|
| EXPLORE | 每完成 explore_batch_size 个页面 | 评估是否需要 compact |
| EXPLORE | 累计探索超过 15 个页面 | 建议 compact |
| GENERATE | 用例数超过 20 条 | 建议 compact |
| EXECUTE | 子 agent 执行，主 agent 无需 compact | - |

## compact 前必做

1. 确认当前批次结果已写入文件
2. 将待探索入口追加到功能分析报告末尾的"待探索入口"章节（格式：`- [ ] [入口名称] ([路径]) — 来源: [父页面]`）
3. 每完成一个入口的探索，将其标记为 `- [x]`（表示已探索）
4. compact 后从文件恢复：读取功能分析报告，已有页面视为已探索，"待探索入口"中未勾选（`- [ ]`）的继续探索

## 提示用户格式

```
已探索 {N} 个页面，上下文较大。建议执行 /compact 压缩上下文后继续。
当前进度已保存到文件，compact 后会自动恢复。
```
