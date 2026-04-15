# 非 Java 语言审查指南

> 从 SKILL.md 移出的详细流程，SKILL.md 仅保留语言适用性表格。

---

## 非 Java 审查流程

1. **语言检测**：阶段 0 识别目标代码语言（文件扩展名 / import 语句 / 框架标识）
2. **声明降级**：报告开头声明「以下审查基于通用维度，Java 专项规则已跳过。」
3. **仅执行通用维度**：安全（注入防护/敏感数据）、数据完整性（事务边界/竞态）、架构（SRP/OCP/DIP）、性能（N+1/缓存）
4. **跳过 Java 专项**：不检查 @Transactional、#{} vs ${}、Spring 分层、MyBatis 规范、Javadoc 格式等
5. **适配修复建议**：修复方案使用目标语言的等效方案（如 Python 用 `with` 替代 try-with-resources）
