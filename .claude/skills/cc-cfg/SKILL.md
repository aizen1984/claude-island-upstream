---
name: cc-cfg
description: 查询simbusiness配置中心的配置项值（prod环境只读）。不修改配置、不查数据库。用于查配置项值、排查配置问题、查看@ConfElement对应内容
argument-hint: [配置key 或 查询描述]
allowed-tools: Bash(python*)
---

# 配置中心查询

## Overview

cfg 是一个**工具型 Skill**，提供配置中心（simbusiness）只读查询能力。通过 Moka 网关查询 prod 环境配置。

## When to Use

**适用场景**：查询配置值（按 key 精确查询）、查看配置内容（JSON 格式展示）

**不适用场景**：

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 修改配置 | 配置中心管理后台 | 本 Skill 仅支持只读查询，禁止写操作 |
| 查询数据库数据 | sql | 本 Skill 只查配置中心，不查数据库 |
| 综合生产排障 | cc-troubleshoot | 本 Skill 只查配置，不做多源交叉验证 |

---

脚本目录：`.claude/skills/cc-cfg/`（相对项目根目录）

## 当前默认配置

- 应用: !`python -c "import yaml; print(yaml.safe_load(open('.claude/skills/cc-cfg/config.yaml'))['defaults']['app_name'])" 2>/dev/null || echo 'vipship'`

## 操作分发

收到 `$ARGUMENTS` 后，执行查询：

| 用户意图 | 执行命令 |
|----------|----------|
| 给了配置 key | `python .claude/skills/cc-cfg/query.py "<key>"` |
| 给了配置 key + 应用名 | `python .claude/skills/cc-cfg/query.py "<key>" -a <appName>` |

> 如果用户用自然语言描述（如"查下优惠券模板配置"），根据上下文推断配置 key，确认后执行。

## 示例

```bash
# 查询配置（默认 appName=vipship）
python .claude/skills/cc-cfg/query.py "coupon_template_external_config"

# 指定应用名
python .claude/skills/cc-cfg/query.py "abconfig_datasparrow_dp_ds" -a abconfig
```

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `key` | 配置 key（必填） | - |
| `-a, --app` | 应用名 | vipship |
| `--config` | 自定义配置文件路径 | config.yaml |

## 代码中的配置引用

当在 Java 代码中看到 `@ConfElement` 注解时，`name` 属性值就是配置中心的 key：

```java
@ConfElement(name = "vipship_equity_supplier_config")
private String equitySupplierConfig;
```

此时可主动用 cfg skill 查询该配置的实际值，帮助理解业务逻辑。

## 资源加载指导

| 场景 | 加载文件 |
|------|---------|
| 遇到需求模糊时 | `shared-rules/inquiry-protocol.md` |

## 协作关系

- **接收自**: user（直接查询请求）
- **委托给**: 无（独立工具 Skill）

## 安全规则

- **只读**：仅支持查询，不修改任何配置

## 完整工作流

1. **解析意图**：根据 `$ARGUMENTS` 提取配置 key 和可选的应用名
2. **执行查询**：调用 `query.py`
3. **展示结果**：解读 JSON 输出，用自然语言总结配置内容

## Gotchas

> 从实际使用中积累的常见陷阱。

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 配置 key 拼写错误或大小写不一致 | API 返回空结果，误以为配置不存在 | 先在代码中搜索 `@ConfElement(name = "...")` 确认准确 key |
| 2 | 查询时未指定正确的 appName | 返回其他应用的同名配置或查不到 | 确认 `@ConfElement` 所在项目对应的 appName，用 `-a` 参数显式指定 |
| 3 | 将查询结果中的 JSON 字符串当作最终值 | 配置值可能是嵌套 JSON 字符串（转义过的），直接使用会解析出错 | 注意区分原始字符串和解析后的 JSON 对象，必要时二次 parse |
