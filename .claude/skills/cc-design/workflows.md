# 设计工作流

## 工作流索引

| 工作流 | 文件 | 说明 |
|--------|------|------|
| 设计文档生成工作流（/cc-design） | [workflows/workflows-forward.md](workflows/workflows-forward.md) | 正向设计：复杂度分析 → PRD → 技术设计 → 图表 → 审查 → 输出 |
| 逆向文档生成工作流（/reverse-engineer） | [workflows/workflows-reverse.md](workflows/workflows-reverse.md) | 逆向生成：范围发现 → PRD 推断 → 技术文档 → 图表 → 代码验证 → 输出 |

### 核心原则

- **正向设计**：复杂度感知，按需设计，任务跟踪
- **逆向生成**：推断标记，验证确认
- 所有文档输出必须遵循 [templates.md](templates.md) 中的「文档表达原则」
