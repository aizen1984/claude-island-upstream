# API 分析器资源

> 搜索命令速查、ER 图生成指南、调用链模式、数据契约、报告模板

## 子文件索引

| 文件 | 说明 | 主要内容 |
|------|------|---------|
| [references/search-commands.md](references/search-commands.md) | 搜索命令速查 | Grep/Glob 命令速查（接口发现、调用链追踪、表关系提取、SQL 分析）、常用分析模式、输出模板格式、错误处理 |
| [references/er-guide.md](references/er-guide.md) | ER 图生成 + 调用链追踪 | 表信息提取（JPA/MyBatis-Plus）、关系识别与标签规范、Mermaid ER 图格式与完整示例、质量检查清单、Controller→Service→Repository 三层调用链追踪、复杂场景（事务/动态SQL/多数据源）、调用链报告模板 |
| [references/data-contracts.md](references/data-contracts.md) | 报告模板 | 单接口分析报告模板、汇总报告模板（数据契约见 `shared-rules/data-contracts.md`） |

## 使用指南

1. **接口发现与追踪**：先查 `search-commands.md` 获取搜索命令，再按 `er-guide.md` 的调用链追踪模式分析
2. **生成 ER 图**：按 `er-guide.md` 的表信息提取 → 关系识别 → Mermaid 格式生成
3. **委托 cc-diagram**：表数量 > 5 时，按 `shared-rules/data-contracts.md` 的 JSON Schema 构造数据后委托
4. **输出报告**：使用 `references/data-contracts.md` 中的单接口/汇总报告模板
