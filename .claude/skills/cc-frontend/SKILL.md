---
name: cc-frontend
description: 提供前端编码规范（React/Vue+TypeScript+Hooks+安全+性能+无障碍）。不独立执行开发任务。用于编码规范咨询、代码实现参考，作为底层规范支撑
user-invocable: false
allowed-tools: Read, Grep, Glob
paths: "**/*.ts, **/*.tsx, **/*.vue, **/*.jsx, **/*.js, **/tsconfig*.json, **/package.json"
---

## Gotchas

| # | 严重度 | 陷阱 | 后果 | 正确做法 |
|---|--------|------|------|---------|
| 1 | P0 | `useEffect` 依赖数组缺失（stale closure） | 读到旧值，bug 难复现 | 遵循 `exhaustive-deps`，禁止 eslint-disable |
| 2 | P0 | `useEffect` 无依赖数组 + 内部 setState | 无限渲染循环，页面卡死 | 始终提供依赖数组 |
| 3 | P0 | `useEffect` 未返回 cleanup | 订阅/定时器泄漏，内存持续增长 | `return () => { clearInterval(id); controller.abort(); }` |
| 4 | P1 | 异步操作（fetch/WebSocket/EventSource）未在 cleanup 中取消 | 竞态条件 + 已卸载组件 setState 警告 | fetch: `AbortController`; WebSocket: `ws.close()`; EventSource: `es.close()` |
| 5 | P0 | `dangerouslySetInnerHTML` 未消毒 | XSS 漏洞 | `DOMPurify.sanitize(html)` |
| 6 | P1 | 解构 `reactive()` 对象 | Vue 3 响应性丢失，模板不更新 | `toRefs(state)` 解构或用 `ref()` |
| 7 | P2 | 动态拼接 Tailwind 类名（`bg-${color}-500`） | JIT 扫描不到，生产样式丢失 | 完整类名映射 `{ red: 'bg-red-500' }` |
| 8 | P1 | `setState(count + 1)` 连续调用 | 只生效一次（批处理） | 函数式更新 `setState(prev => prev + 1)` |
| 9 | P1 | 列表用 `index` 作 `key` | diff 错位，state 混乱 | 稳定唯一标识符 `item.id` |
| 10 | P0 | Token 存 `localStorage` | XSS 可窃取 | `HttpOnly + Secure + SameSite` Cookie |
| 11 | P2 | `target="_blank"` 未加 `rel="noopener"` | 反向 tabnabbing | `rel="noopener noreferrer"` |
| 12 | P2 | 全量 `import _ from 'lodash'` | 打包体积膨胀 | 按需 `import debounce from 'lodash/debounce'` |

# 前端编码规范

> 通用前端开发指南，适用于 React / Vue 3 / TypeScript 项目

## Overview

**唯一真源**：本 Skill 是前端规则唯一真源。`~/.claude/rules/frontend-standards.md` 仅为激活提示，不承载规则正文。可由关键词直接触发，也可被 cc-code-writer / cc-code-reviewer 等隐式依赖加载。

---

## When to Use

- 编写/修改前端代码（React 组件、Vue 组件、TypeScript 逻辑）
- 处理安全（XSS、CSRF、Token 存储）、性能优化
- 配置 TypeScript strict 模式

## When Not to Use

| 场景 | 应改用 | 原因 |
|------|--------|------|
| 系统级架构设计 | cc-design | 本 Skill 是编码规范库，不做架构设计 |
| 任务规划 | cc-planner | 本 Skill 不做任务拆解和规划 |
| 代码审查执行 | cc-code-reviewer | 本 Skill 提供规范参考，不主动执行审查 |
| 创意 UI 设计/视觉风格/交互稿 | frontend-design | 本 Skill 是规范库，不做设计创意 |
| 批量并行任务 | cc-work-mode | 本 Skill 不编排 subagent |

---

## 协作关系

- **被依赖**: cc-code-writer、cc-code-reviewer、cc-work-mode、cc-design、cc-planner、cc-tdd、cc-api-analyzer、cc-troubleshoot（隐式依赖）
- **委托给**: 无（规范库，不主动触发）

### 被隐式依赖时的行为（契约表）

| 调用方场景 | 关键词识别 | 推荐加载范围 | 明确不加载 |
|----------|-----------|------------|-----------|
| cc-code-writer React 任务 | `useEffect` / `useState` / `.tsx` | `patterns-react.md` + `standards-quickref.md` | patterns-vue.md, standards-security.md |
| cc-code-writer Vue 任务 | `setup()` / `ref()` / `reactive()` / `.vue` | `patterns-vue.md` + `standards-quickref.md` | patterns-react.md, standards-security.md |
| cc-code-writer TS strict 迁移 | `strict` / `any` / `tsconfig` | SKILL.md TypeScript 章节 | 框架专项文件 |
| cc-code-reviewer 安全审查 | `XSS` / `CSRF` / `Token` / `innerHTML` | `standards-security.md` | patterns-react.md, patterns-vue.md |
| cc-code-reviewer 规则编号查询 | "规则 #17" / "第 23 条" | `standards-quickref.md` | SKILL.md 正文 |
| cc-troubleshoot stale closure | `useEffect` 依赖 / 闭包 | `patterns-react.md` + `evaluation_cases.md` | 其他领域 |

**契约**：调用方按关键词路由加载；不得整文件 Read 避免污染上下文。

---

## 资源加载指导

| 条件 | 加载文件 | 不加载 |
|------|---------|--------|
| 首次激活（速查） | SKILL.md Gotchas + `standards-quickref.md` | 子文件 |
| React 项目 | `patterns-react.md`（Hooks + 性能 + 测试） | patterns-vue.md, standards-security.md |
| Vue 3 项目 | `patterns-vue.md`（Composition API） | patterns-react.md, standards-security.md |
| 安全/XSS/CSRF | `standards-security.md` | 框架专项文件 |
| TypeScript 配置 | SKILL.md TypeScript 章节 | 框架专项文件 |
| 场景化排障 | `evaluation_cases.md` 对应场景 | 其他领域文件 |

**文件清单**（6 文件）：`SKILL.md`（导航 + Gotchas）、`patterns-react.md`（React + 性能 + 测试）、`patterns-vue.md`（Vue 3）、`standards-security.md`（安全）、`standards-quickref.md`（32 项速查，含无障碍 + CSS）、`evaluation_cases.md`（5 场景验证）。

---

## TypeScript 严格模式

| # | 配置 | 作用 |
|---|------|------|
| 1 | `strict: true` | 开启所有严格类型检查 |
| 2 | `noUncheckedIndexedAccess: true` | 索引访问自动加 `undefined` |
| 3 | `exactOptionalPropertyTypes: true` | 区分"省略"和"undefined" |
| 4 | `noImplicitReturns: true` | 禁止隐式 undefined 返回 |

**排查**：`grep -r 'any' src/ --include='*.ts' --include='*.tsx'` 排查残留 any 声明。
