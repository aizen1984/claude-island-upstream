# 前端规范速查表

> 32 项核心规则 = SKILL.md Top 12 红线 + 20 项分领域速查的索引，按领域分组。详细说明见 SKILL.md 对应章节。

## 一、React Hooks

| # | 规则 | 速查 |
|---|------|------|
| 1 | useEffect 完整依赖 | `exhaustive-deps` 不 disable |
| 2 | useEffect 必须 cleanup | `return () => { ... }` |
| 3 | Hook 顶层调用 | 不在条件/循环中 |
| 4 | 函数式 setState | `prev => prev + 1` |
| 5 | 不可变更新 | `[...arr, item]` |
| 6 | fetch 用 AbortController | `{ signal: controller.signal }` |

## 二、Vue 3

| # | 规则 | 速查 |
|---|------|------|
| 7 | 不解构 reactive | `toRefs(state)` |
| 8 | 原始类型用 ref | `ref('hello')` |
| 9 | 不替换整个 reactive | 修改属性 |
| 10 | Props 用 toRefs | `toRefs(props)` |
| 11 | 可变默认值工厂函数 | `() => []` |

## 三、TypeScript

| # | 规则 | 速查 |
|---|------|------|
| 12 | strict: true | 必开 |
| 13 | noUncheckedIndexedAccess | 索引自动 `\| undefined` |
| 14 | 禁止 any | 用 `unknown` |
| 15 | 类型守卫替代 as | `is` / `in` / `instanceof` |
| 16 | as const 替代 enum | 兼容性更好 |

## 四、安全

| # | 规则 | 速查 |
|---|------|------|
| 17 | innerHTML 必须消毒 | `DOMPurify.sanitize()` |
| 18 | 禁止 eval | 绝对禁止 |
| 19 | href 校验协议 | 拒绝 `javascript:` |
| 20 | Token 不存 localStorage | HttpOnly Cookie |
| 21 | 环境变量不暴露密钥 | 密钥不加 `VITE_` 前缀 |
| 22 | target="_blank" 加 rel | `rel="noopener noreferrer"` |

## 五、性能

| # | 规则 | 速查 |
|---|------|------|
| 23 | 路由 lazy loading | `React.lazy` + `Suspense` |
| 24 | 长列表虚拟化 | `react-window` |
| 25 | 按需 import | `from 'lodash/debounce'` |
| 26 | 图片 lazy + srcset | `loading="lazy"` |
| 27 | 搜索框 debounce | `useDeferredValue` |

## 六、无障碍

| # | 规则 | 速查 |
|---|------|------|
| 28 | 语义化标签 | `<button>` 不是 `<div onClick>` |
| 29 | 图片 alt | 必须 |
| 30 | 表单 label | `htmlFor` 关联 |
| 31 | 自定义组件 ARIA | `role` + `aria-expanded` + 键盘导航 |
| 32 | 颜色对比度 | WCAG AA ≥ 4.5:1 |
