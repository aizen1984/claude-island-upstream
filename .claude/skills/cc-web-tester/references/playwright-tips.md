# Playwright MCP 使用技巧

## 核心工具选择

| 工具 | 用途 | 何时使用 |
|------|------|---------|
| `browser_snapshot` | 获取无障碍树（文本） | **优先使用**，分析页面结构和元素 |
| `browser_take_screenshot` | 截图（图片） | 失败用例截图、用户审核 |
| `browser_click` | 点击元素 | 导航、按钮操作 |
| `browser_type` | 输入文本 | 表单填写 |
| `browser_fill_form` | 批量填表 | 多字段表单一次填写 |
| `browser_select_option` | 下拉选择 | select/combobox |
| `browser_navigate` | 跳转 URL | 直接导航到已知页面 |
| `browser_navigate_back` | 后退 | 返回上级页面 |
| `browser_press_key` | 键盘操作 | Enter 提交、Escape 关闭 |
| `browser_wait_for` | 等待 | 等待文本出现/消失、等待加载 |
| `browser_tabs` | 标签页管理 | 子 agent 使用独立 tab |
| `browser_console_messages` | 获取控制台日志 | 辅助判断失败原因（JS 报错） |
| `browser_network_requests` | 获取网络请求 | 检测 API 4xx/5xx 辅助定位 |
| `browser_install` | 安装浏览器 | 首次使用时浏览器未安装 |

## snapshot vs screenshot

- **snapshot**（无障碍树）：返回文本格式的页面结构，包含元素 ref、角色、名称、状态。**所有分析和元素定位基于 snapshot**
- **screenshot**（截图）：返回图片。仅用于人工审核和失败记录，**不要用 screenshot 做页面分析**

## 元素定位

snapshot 返回的每个元素都有 `ref` 属性，用于后续操作：

```
1. browser_snapshot → 获取元素列表
2. 从结果中找到目标元素的 ref（如 ref="e15"）
3. browser_click(ref="e15") 或 browser_type(ref="e15", text="...")
```

**注意**：
- ref 在页面变化后可能失效，操作前需重新 snapshot
- 隐藏元素不在 snapshot 中（需先滚动/展开）
- Shadow DOM 内的元素不可见

## 表单填写

**单字段**：
```
browser_type(ref="字段ref", text="内容")
```

**多字段批量**（推荐，减少 API 调用）：
```
browser_fill_form(fields=[
  {name: "名称", type: "textbox", ref: "e10", value: "测试"},
  {name: "类型", type: "combobox", ref: "e12", value: "A类"},
  {name: "启用", type: "checkbox", ref: "e14", value: "true"}
])
```

## SPA 页面切换检测

SPA 应用点击导航后 URL 可能不变。判断页面是否切换：

```
1. 操作前 snapshot → 记录关键内容摘要
2. 执行操作（click）
3. browser_wait_for(time=1) → 等待渲染
4. 操作后 snapshot → 比对内容
5. 内容明显变化 → 视为新页面
```

## 等待策略

| 场景 | 方法 |
|------|------|
| 等待特定文本出现 | `browser_wait_for(text="保存成功")` |
| 等待加载完成 | `browser_wait_for(textGone="加载中...")` |
| 等待固定时间 | `browser_wait_for(time=2)` — 仅作为兜底 |
| 等待弹窗 | `browser_wait_for(text="确认删除")` |

**原则**：优先用 text/textGone 等条件等待，time 等待仅在无法判断条件时使用。

## 常见坑点

### 1. 弹窗/对话框

浏览器原生对话框（alert/confirm/prompt）需要用 `browser_handle_dialog`：
```
browser_handle_dialog(accept=true)           // 确认
browser_handle_dialog(accept=false)          // 取消
browser_handle_dialog(accept=true, promptText="输入内容")  // prompt
```

**注意**：必须在触发对话框的操作**之前**或**立即之后**调用，否则可能错过。

### 2. 页面加载未完成

点击导航后立即 snapshot 可能获取到旧页面。解决：
```
browser_click(ref="导航ref")
browser_wait_for(time=1)  // 或等待特定文本
browser_snapshot()
```

### 3. 元素不可见

可能原因：
- 需要滚动页面才能看到 → `browser_evaluate(function="() => window.scrollTo(0, document.body.scrollHeight)")`
- 在折叠面板/Tab 中 → 先点击展开
- 在 Shadow DOM 中 → 标记为"不可测试"

### 4. 子 agent 并行时的浏览器冲突

多个子 agent 共享同一浏览器。解决方案：

**方案 A：独立 Tab**（推荐）
```
每个子 agent 启动时：
1. browser_tabs(action="new") → 创建新 tab
2. 在新 tab 中执行测试
3. 完成后 browser_tabs(action="close") → 关闭 tab
```

**方案 B：串行执行**
```
子 agent 不使用 run_in_background，按顺序逐批执行
```

### 5. 截图文件命名

截图统一命名为 `TC-{编号}-result.png`，存入 `screenshots/` 目录：
```
browser_take_screenshot(filename="{输出目录}/screenshots/TC-015-result.png")
```

### 5.5 下载文件路径控制

导出/下载操作的文件必须保存到 `evidence/downloads/` 目录，禁止使用默认下载路径（会污染 `.playwright-mcp/` 等非测试目录）：

```
// 方案：在触发下载前，通过 browser_run_code 设置下载路径
async (page) => {
  const client = await page.context().newCDPSession(page);
  await client.send('Browser.setDownloadBehavior', {
    behavior: 'allow',
    downloadPath: '{输出目录}/测试报告/evidence/downloads'
  });
}
```

如 CDP 不可用，则在下载后将文件从默认路径移动到 `evidence/downloads/`。

### 6. 调试辅助：控制台和网络请求

用例失败时，除截图外可通过控制台日志和网络请求辅助定位原因：

```
// 获取控制台错误（辅助判断 JS 异常）
browser_console_messages(level="error")

// 获取网络请求（辅助判断 API 失败）
browser_network_requests(includeStatic=false)
```

**使用场景**：
- 页面功能异常但 UI 无报错提示 → 检查 console error
- 操作后数据未更新 → 检查网络请求是否返回 4xx/5xx

### 7. 首次使用：浏览器安装

如果 Playwright 浏览器未安装，工具调用会报错。解决：
```
browser_install()  // 自动安装配置的浏览器
```

建议在 Phase 1 首次 `browser_navigate` 失败时自动执行。

### 8. 图标按钮识别

纯图标按钮（无文本、无 aria-label）无法从 snapshot 中判断用途。使用 `browser_evaluate` 读取 DOM 属性：

```
browser_evaluate(() => {
  const buttons = document.querySelectorAll('button:not([aria-label])');
  return [...buttons].map(b => ({
    class: b.className,
    title: b.title,
    dataTooltip: b.dataset?.tooltip,
    innerHTML: b.innerHTML.substring(0, 100)
  }));
})
```

常见 class 名与操作对应：
- `anticon-edit` / `anticon-form` → 编辑（L1 白名单）
- `anticon-delete` / `anticon-close` → 删除（X-禁止）
- `anticon-plus` / `anticon-plus-circle` → 新增（L1 白名单）
- `anticon-eye` → 查看（L1 白名单）
- `anticon-more` / `anticon-ellipsis` → 更多（L1 白名单）

### 9. Dropdown 菜单操作

```
1. browser_click(ref) 触发下拉菜单
2. browser_wait_for(time=0.5) 等待菜单渲染
3. browser_snapshot 找到 role=menu 的元素及其 menuitem 子元素
4. 记录菜单项名称后 browser_press_key("Escape") 关闭
```

注意：不要点击菜单项中的危险操作（删除/发布等），仅记录菜单结构。

### 10. 条件等待（替代固定 wait）

优先使用条件等待，避免不必要的固定延迟：

```
# 等待 loading 消失（最常用）
browser_wait_for(textGone="加载中", timeout=5000)
browser_wait_for(textGone="Loading", timeout=5000)

# 等待弹窗标题出现
browser_wait_for(text="新增", timeout=3000)

# 兜底：无法判断条件时
browser_wait_for(time=1)
```

### 11. 微前端 snapshot 降级

**现象**：qiankun 等微前端子应用页面，`browser_snapshot` 返回空白。

**速查**：四级降级 Level 1(wait重试) → Level 2(screenshot) → Level 3(evaluate DOM) → Level 4(标记继续)。
降级页面用 CSS 选择器 + `browser_evaluate(() => el.click())` 替代 ref 操作。

> 完整降级流程、DOM 概要查询模板、降级交互方式详见 workflows.md §1.3.5

### 12. 新 Tab 探索

click 后可能打开新 Tab（`target="_blank"` / `window.open()`），需检测处理。

**速查**：click 前记录 Tab 数 → click → browser_tabs() 比较 → 如增加则切换/探索/关闭回原 Tab。

> 完整流程详见 workflows.md §1.2 步骤 3.6（Phase 1）和 §3.2 子 agent prompt（Phase 3）

### 13. browser_run_code 批量模式

> **定位**：特定场景的加速手段，不是全局替代。优先使用 ref 方式，仅在下列适用场景中使用 run_code。

**适用场景**：

| 场景 | 示例 | 收益 |
|------|------|------|
| 导航+等待组合 | navigate → waitForLoadState → snapshot | 3 次调用 → 1 次 |
| 弹窗关闭降级序列 | Escape → 找按钮 → 点遮罩 → 强制导航 | 4 次调用 → 1 次 |
| 已知页面的固定操作 | 登录填写（用户名+密码+点击） | 5 次调用 → 1 次 |
| 多字段清空 | 逐个字段 Ctrl+A → Backspace | N*2 次 → 1 次 |

**不适用场景**：

| 场景 | 原因 |
|------|------|
| 表单填写+验证 | 需要中间 snapshot 确认字段状态 |
| 闭环链执行（Create→Edit→Delete） | 每步需 snapshot 验证数据变化 |
| 首次探索未知页面 | 不知道选择器，必须用 snapshot+ref |
| 需要条件分支的操作 | run_code 内无法根据页面状态做 LLM 决策 |

**选择器优先级**（run_code 内无 ref，需用选择器）：

> 与 operation-patterns-execution.md "选择器优先级" 表保持一致

```
1. 角色选择器: page.getByRole('button', {name:'保存'}) ← 语义明确，推荐
2. 文本选择器: page.getByText('保存成功')           ← 直观，同名文本可能冲突
3. CSS 选择器: page.locator('.ant-btn-primary')     ← 兜底，依赖样式类名
⚠️ 禁止使用 data-testid（真实业务系统中几乎不存在）
```

**示例：导航+等待**
```javascript
browser_run_code(`
  await page.goto('${url}');
  await page.waitForLoadState('networkidle');
`)
// 之后仍需 browser_snapshot 获取页面结构
```

**示例：弹窗关闭降级**
```javascript
browser_run_code(`
  // 四级降级合并为一次调用
  try {
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
    const modal = page.locator('.ant-modal-wrap');
    if (await modal.isVisible()) {
      const closeBtn = page.locator('.ant-modal-close');
      if (await closeBtn.isVisible()) {
        await closeBtn.click();
      } else {
        await modal.click({ position: { x: 1, y: 1 } });
      }
    }
  } catch(e) {
    await page.goto(currentUrl);
  }
`)
```

**示例：多字段清空**
```javascript
browser_run_code(`
  const inputs = page.locator('input[type="text"], textarea');
  const count = await inputs.count();
  for (let i = 0; i < count; i++) {
    await inputs.nth(i).click();
    await page.keyboard.press('Control+A');
    await page.keyboard.press('Backspace');
  }
`)
```

**错误处理**：run_code 内任何步骤失败会抛出异常，整块代码终止。失败时：
1. 检查 browser_console_messages 获取错误信息
2. 回退到逐步 ref 模式重试
3. 记录失败原因到 batch evidence

### 14. click 超时处理

**现象**：`browser_click(ref="eXXX")` 报 `TimeoutError: locator.click: Timeout 5000ms exceeded`，但日志显示元素已 visible、enabled、stable。

**根因**：Playwright actionability check 的最后一步"元素接收指针事件"失败——元素被其他元素遮挡（遮罩层、tooltip、popover、loading spinner 等），导致点击无法到达目标。`browser_click` 无 timeout 参数，固定 5000ms 且不可配置。

**三级降级策略**：

```
Level 1: 清除遮挡 → 重试 ref click
  ├── browser_press_key("Escape")           ← 关闭可能的 popover/tooltip
  ├── browser_wait_for(time=1)              ← 等待动画/遮罩消失
  ├── browser_snapshot()                    ← 重新获取 ref（页面可能已变化）
  └── browser_click(ref="新ref")            ← 用新 ref 重试

Level 2: JS 强制点击（跳过 actionability check）
  └── browser_run_code(`
        const el = document.querySelector('[aria-ref="eXXX"]');
        if (!el) {
          // aria-ref 不可用时，用选择器兜底
          const target = document.querySelector('按实际选择器');
          target?.click();
        } else {
          el.click();
        }
      `)
  ⚠️ JS click 不做 actionability check，可能点击到不可见元素

Level 3: Playwright locator + 自定义 timeout
  └── browser_run_code(`
        await page.locator('[aria-ref="eXXX"]').click({ timeout: 15000 });
      `)
  或用角色/文本选择器：
      browser_run_code(`
        await page.getByRole('button', { name: '目标按钮' }).click({ timeout: 15000 });
      `)
  ⚠️ aria-ref 是 Playwright MCP 注入的属性，run_code 中不一定存在，优先用角色/文本选择器
```

**选择指南**：

| 情况 | 推荐级别 |
|------|---------|
| 偶发超时（页面加载慢、动画未完） | Level 1 |
| 确认有遮罩但无法关闭 | Level 2 |
| 需要更长等待时间 | Level 3 |
| Level 1 重试仍失败 | Level 2 → Level 3 |

**在子 agent prompt 中引用**：子 agent 执行用例时遇到 click 超时，按 Level 1→2→3 降级处理，不直接标记为 BLOCKED。

---

### 15. 视觉验证（可选）

> 配置项 `visual_verify: false`（默认关闭）。用户可选开启，用于捕获 DOM 检查无法发现的视觉问题。

**适用场景**：

| 场景 | 说明 |
|------|------|
| 微前端 snapshot 降级 | snapshot 为空时，screenshot + vision 替代 DOM 分析 |
| 关键断言的二次确认 | 表单提交后验证成功提示是否真的可见（非被遮挡） |
| 布局问题检测 | 元素重叠、样式错乱等 DOM 无法反映的问题 |

**不适用场景**：常规通过/失败判定（snapshot 已足够）

**使用方式**：
```
1. 完成操作步骤（使用 snapshot+ref 或 run_code）
2. browser_take_screenshot 截图
3. 将截图作为 vision 输入，让 LLM 判断：
   - 预期元素是否在视觉上可见？
   - 是否有遮挡、错位、样式异常？
   - Toast/提示是否确实显示？
4. 结合 snapshot 文本验证 + vision 视觉验证，给出最终判定
```

**与 snapshot 降级的关系**：
- workflows.md §1.3.5 Level 2 已使用 screenshot 做视觉分析
- visual_verify 扩展此能力到 Phase 3 执行阶段
- 降级页面（Level 2+）自动启用视觉验证，无需额外配置
