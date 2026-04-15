# React 编码规范

> cc-frontend 子文件：React Hooks、性能优化、测试规范。导航回 [SKILL.md](SKILL.md)。

---

## React Hooks 规范

| # | 规则 | 说明 |
|---|------|------|
| 1 | Hook 顶层调用 | 不在 if/for/回调中 |
| 2 | 依赖数组完整 | `exhaustive-deps` |
| 3 | cleanup 返回 | 订阅/定时器/AbortController |
| 4 | 函数式 setState | `setState(prev => prev + 1)` 防批处理丢失 |
| 5 | 不可变更新 | `[...arr, item]` 而非 `arr.push(item)` |
| 6 | useMemo/useCallback | 昂贵计算 `useMemo`，传递回调 `useCallback` |
| 7 | 自定义 Hook 复用逻辑 | `use` 前缀命名 |

### 示例：函数式 setState 批处理陷阱

错误（3 次点击只 +1）：

```tsx
function Counter() {
  const [count, setCount] = useState(0);
  const handleTriple = () => {
    setCount(count + 1);  // 读到闭包中旧 count=0
    setCount(count + 1);  // 还是 0+1
    setCount(count + 1);  // 还是 0+1 → 最终 count=1
  };
  return <button onClick={handleTriple}>+3</button>;
}
```

正确（使用 updater function）：

```tsx
function Counter() {
  const [count, setCount] = useState(0);
  const handleTriple = () => {
    setCount(prev => prev + 1);  // prev=0 → 1
    setCount(prev => prev + 1);  // prev=1 → 2
    setCount(prev => prev + 1);  // prev=2 → 3
  };
  return <button onClick={handleTriple}>+3</button>;
}
```

### 示例：useEffect cleanup + AbortController

错误（组件卸载后 setState 警告 + 竞态）：

```tsx
useEffect(() => {
  fetch(`/api/user/${id}`)
    .then(res => res.json())
    .then(data => setUser(data));
}, [id]);
```

正确：

```tsx
useEffect(() => {
  const controller = new AbortController();
  fetch(`/api/user/${id}`, { signal: controller.signal })
    .then(res => res.json())
    .then(data => setUser(data))
    .catch(e => { if (e.name !== 'AbortError') throw e; });
  return () => controller.abort();
}, [id]);
```

---

### 示例：ESLint exhaustive-deps 配置

```json
{
  "rules": {
    "react-hooks/exhaustive-deps": "error",
    "react-hooks/rules-of-hooks": "error"
  },
  "plugins": ["react-hooks"]
}
```

---

## 性能规范

**Web Vitals 目标**（Google Good 阈值）：LCP < 2.5s、FID < 100ms、CLS < 0.1、首屏 JS < 200KB（gzip）。

| # | 规则 | 说明 |
|---|------|------|
| 1 | 路由级 lazy loading | `React.lazy(() => import('./Page'))` + `Suspense`，可减少首屏 JS 约 40-60% |
| 2 | 长列表虚拟化 | `react-window` / `@tanstack/virtual`，≥ 100 行必须虚拟化 |
| 3 | 按需 import | `import debounce from 'lodash/debounce'`（全量 lodash ~70KB gzip ~24KB） |
| 4 | 图片优化 | `loading="lazy"` + `srcset` + WebP（WebP 比 JPEG 小 25-35%） |
| 5 | 搜索框 debounce | `useDeferredValue` 或 `debounce(fn, 300)`（300ms 为用户感知阈值） |
| 6 | React.memo 优化 | 昂贵子组件 + 稳定 props |
| 7 | CSS 代码分割 | CSS Modules / Tailwind JIT |

---

## 测试规范

| # | 规则 | 说明 |
|---|------|------|
| 1 | 测试用户行为而非实现 | `getByRole('button')` + `userEvent.click()` |
| 2 | 异步用 `findBy` | `await screen.findByText('loaded')` |
| 3 | 优先 getByRole | > getByLabelText > getByText > getByTestId |
| 4 | mock 网络用 msw | `Mock Service Worker` 拦截 |
| 5 | 定时器用 fake timers | `vi.useFakeTimers()` |

**目标覆盖率**：关键路径 100%、整体 ≥ 80%。验证：`npx vitest run --coverage`。
