# 数据生命周期与智能编排

## 标题索引

| 章节 | 说明 |
|------|------|
| 数据生命周期 | 测试数据的创建/使用/清理策略 |
| 智能编排规则 | Phase 3 批次分组的依赖感知算法 |
| 组件操作 Playbook | Ant Design/Element UI 等常见组件的操作速查 |

---

# 数据生命周期

## 依赖标注字段

每条用例在 JSON 中可选标注：

```json
{
  "id": "TC-016",
  "title": "新增-正常创建",
  "pattern": "Create",
  "data_lifecycle": {
    "creates": "自动化测试智能体",
    "depends": null,
    "consumes": null
  }
}
```

| 字段 | 说明 | 示例 |
|------|------|------|
| `creates` | 此用例创建的测试数据名 | `"自动化测试智能体"` |
| `depends` | 此用例依赖哪条用例的产出 | `"TC-016"` |
| `consumes` | 此用例会清理哪条用例创建的数据 | `"TC-016"` |

## 三种数据策略

### A. 闭环型（推荐）

同一批次内完成 Create → Use → Delete 全生命周期：

```
Batch N:
  TC-016(Create, creates="X") → TC-022(Update, depends="TC-016")
  → TC-023(Update, depends="TC-016") → TC-025(Delete, consumes="TC-016")
```

好处：批次间零耦合，测试数据自动清理。

### B. 已有数据型

用例依赖环境已有数据（如"HEEL错误分析"），不创建不清理。

好处：简单，无副作用。
风险：依赖环境稳定性。

### C. 显式清理型

用例创建数据但本批次不删除（如添加知识库后不移除）。

```
Batch 结果末尾追加：
## 待清理数据
- 知识库: "知识库组织权限测试"（TC-035 添加）
- 插件: "获取测试文档数据"（TC-037 添加）
```

主 agent 汇总时派发 cleanup batch 统一清理。

## Phase 2 标注流程

```
1. 识别 Create 用例 → 标注 creates
2. 识别 Update/Delete 用例 → 检查是否操作 Create 创建的数据
   - 是 → 标注 depends/consumes
   - 否（操作已有数据）→ 不标注
3. 生成依赖图
4. 闭环检查：每个 creates 是否有对应的 consumes？
   - 有 → 闭环型，编排到同一批次
   - 无 → 显式清理型，在最后追加 cleanup batch
```

---

# 智能编排规则

## 概述

Phase 3 分组不再仅按优先级排序，而是综合依赖关系和优先级。

## 编排算法

```
输入：用例列表（含 pattern、data_lifecycle、priority）
输出：有序批次列表

Step 1: 构建依赖图
  - 从 data_lifecycle.depends/consumes 提取依赖关系
  - 构建 DAG（有向无环图）

Step 2: 识别闭环链
  - 找出所有 creates→depends→...→consumes 的链路
  - 每条链路作为一个"闭环组"

Step 3: 闭环组内排序
  - 按拓扑顺序排列（Create → Update → Delete）
  - 同级按优先级排序

Step 4: 独立用例填充
  - 将无依赖的用例按优先级排序
  - 用独立用例填充闭环组的剩余槽位（每批 execute_batch_size 条）

Step 5: 剩余独立用例按优先级分批
  - P0 → P1 → P2 → P3

Step 6: 追加 cleanup batch（如有显式清理型数据）
```

## 编排示例

原始用例（以智能体管理为例）：

```
闭环组 A：TC-016(Create) → TC-022(Update) → TC-023(Update) → TC-025(Delete)
闭环组 B：TC-011(Bookmark) → TC-012(Bookmark)  # 收藏→取消收藏
独立用例：TC-001, TC-002, ..., TC-045（无依赖）
```

编排结果：

```
Batch 1: [TC-016, TC-022, TC-023, TC-025, TC-026]  ← 闭环组 A + 关联的取消删除
Batch 2: [TC-001, TC-004, TC-013, TC-030, TC-011]  ← P0 + 收藏起点
Batch 3: [TC-012, TC-002, TC-003, TC-007, TC-008]  ← 取消收藏 + P1 独立
...
Batch N (cleanup): [清理 TC-035 知识库, 清理 TC-037 插件]
```

---

# 组件操作 Playbook

子 agent 执行时参考，减少试错和工具调用。

## Ant Design 组件

### Modal（模态弹窗）
```
打开：click 触发按钮 → wait(1s) → snapshot（确认弹窗出现）
关闭：click 右上角 X(.ant-modal-close) 或 按 Escape
确认：click "确认/OK" 按钮
取消：click "取消/Cancel" 按钮
```

### Drawer（抽屉）
```
打开：click 触发按钮 → wait(1s) → snapshot
关闭：click 右上角 X(.ant-drawer-close) 或 按 Escape
操作同 Modal
```

### Form（表单）
```
单字段：browser_type(ref, text)
多字段：browser_fill_form 批量填写（推荐，减少调用）
清空字段：click 字段 → Ctrl+A → Backspace
```

### Select/Combobox（下拉选择）
```
打开：click 下拉框
选择：wait(0.5s) → snapshot → click 目标选项
关闭（不选）：按 Escape
多选模式：依次 click 多个选项 → 点击弹出层外部关闭
```

### Table（表格）
```
分页-翻页：click 页码数字
分页-跳页：找到跳页 input → type 页码 → Enter
排序：click 列头
展开行：click 展开图标（+/▶）
```

### Switch/Checkbox（开关）
```
切换：直接 click 元素
验证状态：snapshot 检查 [checked] 属性或 is-checked class
即时生效：部分开关无需额外保存
```

### Tabs（标签页）
```
切换：click Tab 标题
验证选中：snapshot 检查 tab [selected] 或 active class
```

### Popconfirm/Popover（气泡确认）
```
触发：click 目标按钮
确认：snapshot → click "确认/确定"
取消：click "取消" 或按 Escape
⚠️ 遮罩层可能拦截其他点击，操作前先 Escape 关闭残留 Popover
```

### Pagination（分页器）
```
翻页：click 页码数字
上/下页：click ◀/▶ 箭头
跳页：find ".ant-pagination-options-quick-jumper input" → type → Enter
验证当前页：snapshot 检查高亮页码
```

## 特殊组件

### rc-md-editor（Markdown 编辑器）
```
⚠️ 直接 browser_type 可能不触发 React state 更新
推荐方案：
  1. click 编辑区域获取焦点
  2. browser_evaluate(() => {
       const ta = document.querySelector('.rc-md-editor textarea');
       ta.focus();
       document.execCommand('insertText', false, '内容');
     })
  3. snapshot 验证内容已填入
备选：click 编辑区 → browser_type（部分情况下可行）
```

### Quill/TinyMCE（富文本编辑器）
```
类似 rc-md-editor，需要 focus 后用 execCommand
或通过编辑器工具栏操作
```

### DatePicker（日期选择器）
```
快捷选项：click 输入框 → snapshot → click 快捷选项（如"最近7天"）
手动选择：click 输入框 → click 起始日期 → click 结束日期
清除：click 清除图标(X)
```

### Upload（上传组件）
```
⚠️ Playwright MCP 不支持文件选择对话框
使用 browser_file_upload(ref, files) 直接注入文件
```

## 通用技巧

### 弹窗/遮罩层冲突
```
操作前 snapshot 检查是否有残留弹窗/遮罩
如有 → 按 Escape 关闭 → 再 snapshot → 继续操作
```

### SPA 页面加载
```
click 导航后 → wait(1-2s) → snapshot
不要立即 snapshot，SPA 渲染需要时间
```

### Toast/Message 验证
```
操作后 → wait(1s) → snapshot
Toast 通常 3 秒后消失，需要及时捕获
如果 snapshot 中未见 toast → 检查 browser_console_messages
可选：snapshot 前先 browser_take_screenshot 留存视觉证据（toast 消失快时推荐）
```

### 新 Tab 操作

click 后可能打开新 Tab（`target="_blank"`、`window.open()`、编辑/详情入口等）。

**速查**：click 前记录 Tab 数 → click → `browser_tabs()` 比较 → 如增加则切换/操作/关闭。

**常见触发新 Tab 的操作**：
- 卡片/列表行点击进入详��/编辑页
- "在新窗口打开"按钮
- 外部链接跳转
- Create 保存后跳转到配置页

> 完整流程详见 workflows.md §1.2 步骤 3.6（Phase 1 探索）和 §3.2（Phase 3 执行）

---

## run_code 加速片段

> 仅用于特定场景的加速，不替代 ref 方式。详见 [playwright-tips.md](../references/playwright-tips.md) §13 适用/不适用场景判断。

### 代码片段速查

> 完整代码示例和适用/不适用场景判断见 [playwright-tips.md](../references/playwright-tips.md) §13，此处仅列场景名称。

| 场景 | 收益 | 代码位置 |
|------|------|---------|
| 弹窗关闭（四级降级合并） | 4 次调用 → 1 次 | playwright-tips.md §13 示例：弹窗关闭降级 |
| 导航+等待+恢复 | 3 次调用 → 1 次 | playwright-tips.md §13 示例：导航+等待 |
| 多字段清空 | N*2 次 → 1 次 | playwright-tips.md §13 示例：多字段清空 |
| 登录填写 | 5 次调用 → 1 次 | playwright-tips.md §13 示例：登录填写 |

### 选择器优先级

run_code 内无 ref 可用，按以下优先级选择定位方式：

| 优先级 | 方式 | 示例 | 说明 |
|--------|------|------|------|
| 1 | 角色选择器 | `page.getByRole('button', {name:'保存'})` | 语义明确，推荐 |
| 2 | 文本选择器 | `page.getByText('保存成功')` | 直观，同名文本可能冲突 |
| 3 | CSS 选择器 | `page.locator('.ant-btn-primary')` | 兜底，依赖样式类名 |

> **禁止**使用 `data-testid` 选择器（真实业务系统中几乎不存在）
