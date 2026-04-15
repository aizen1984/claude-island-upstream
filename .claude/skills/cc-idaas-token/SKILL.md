---
name: cc-idaas-token
description: 获取指定用户的x-token（sit/prod环境），用于模拟身份调试API。不查数据、不改配置。用于以其他用户身份调试Moka网关后的API
argument-hint: [用户租户账号ID 或 用户姓名]
disable-model-invocation: true
allowed-tools: Bash(python .claude/skills/cc-idaas-token/*)
---

# idaas Token 获取

## Overview

cc-idaas-token 是一个**工具型 Skill**，通过 idaas session toggle 接口，用自己的 x-token 切换到目标用户，获取其 x-token。

**前置条件**：Chrome 插件（X-Token Grabber）已抓取自己的 x-token 到 `~/x-token/moka-{env}-x-token.json`。

---

## When to Use

**适用场景**：获取其他用户的 token、以其他用户身份调接口

**不适用场景**：

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 获取自己的 token | Chrome 插件（X-Token Grabber） | 直接抓取更简单，无需 toggle |
| 查询数据库数据 | sql | 本 Skill 只获取 token，不查数据 |
| 查询应用日志 | cc-sls-query | 本 Skill 只获取 token，不查日志 |

---

脚本目录：`.claude/skills/cc-idaas-token/`（相对项目根目录）

## 操作分发

收到 `$ARGUMENTS` 后，判断意图：

| 用户意图 | 执行命令 |
|----------|----------|
| 给了租户账号 ID（UUID 格式） | `python .claude/skills/cc-idaas-token/get_token.py "<userId>"` |
| 给了 ID + 要验证身份 | `python .claude/skills/cc-idaas-token/get_token.py "<userId>" --verify` |
| 指定 prod 环境 | 加 `--env prod` |
| 给了用户姓名（中文名） | 先搜索 → 确认用户 → 自动 toggle（见下方流程） |
| 只搜索用户不要 token | `python .claude/skills/cc-idaas-token/search_user.py "<姓名>"` |

> 默认 sit 环境。用户提到 prod/生产 时加 `--env prod`。

### 姓名 → token 完整流程

当用户给的是姓名而非 UUID 时：
1. `python .claude/skills/cc-idaas-token/search_user.py "<姓名>"` 搜索用户
2. 如果唯一匹配，直接用返回的 `userId` 调 `get_token.py`
3. 如果多个匹配，列出候选让用户确认
4. 如果无匹配，提示用户检查姓名

## 示例

```bash
# 按姓名搜索用户
python .claude/skills/cc-idaas-token/search_user.py "俞亮亮"

# SIT 环境获取目标用户 token（默认）
python .claude/skills/cc-idaas-token/get_token.py "0cb4c4e8-de15-4bec-9c90-ef615e887c40"

# PROD 环境
python .claude/skills/cc-idaas-token/get_token.py "0cb4c4e8-de15-4bec-9c90-ef615e887c40" --env prod

# 获取并验证身份
python .claude/skills/cc-idaas-token/get_token.py "0cb4c4e8-de15-4bec-9c90-ef615e887c40" --verify
```

## 参数

### get_token.py

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `user_id` | 目标用户租户账号 ID（必填） | - |
| `--env` | 环境（sit/prod） | sit |
| `--verify` | 获取后验证 token 对应的用户信息 | false |
| `--config` | 自定义配置文件路径 | config.yaml |

### search_user.py

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `name` | 用户姓名（必填，支持模糊搜索） | - |
| `--env` | 环境（sit/prod） | sit |
| `--size` | 返回数量 | 10 |
| `--config` | 自定义配置文件路径 | config.yaml |

## 协作关系

- **接收自**: user（直接请求）
- **委托给**: 无（独立工具 Skill，用户搜索通过 idaas API 完成）

## Gotchas

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 用 importUsers 的 id 调 toggle | 返回"账号不存在" | 必须用 o_system_check_api 审计日志的 userId |
| 2 | 自己的 token 过期 | toggle 返回 401 | 重新用 Chrome 插件访问对应环境页面刷新 token |
| 3 | 用 Authorization: Bearer 传 token | 认证失败 | idaas 使用自定义 header `x-token` |
