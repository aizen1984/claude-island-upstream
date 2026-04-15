# cc-frontend Evaluation Cases

> 5 个真实场景，用于验证本 Skill 规则的覆盖能力。每个场景包含：输入 → 应命中规则 → 期望输出。

---

## 场景 1：stale closure 排障（useEffect 依赖缺失）

**输入**（用户求助）：

```tsx
function Search({ query }: { query: string }) {
  const [results, setResults] = useState<string[]>([]);
  useEffect(() => {
    fetch(`/api/search?q=${query}`)
      .then(r => r.json())
      .then(setResults);
  }, []);  // 只在挂载时跑一次
  return <ul>{results.map(r => <li>{r}</li>)}</ul>;
}
```

**应命中规则**：Top 12 #1（stale closure）+ React Hooks #2（依赖数组完整）+ Top 12 #4（fetch 未用 AbortController）。

**期望输出**：
1. 指出 `query` 是 effect 内引用的外部变量但未进依赖数组 → 会永远搜索第一次的 query。
2. 同时指出没有 cleanup，query 快速切换时会产生竞态。
3. 修复代码：依赖数组补 `[query]` + 加 `AbortController` cleanup。

---

## 场景 2：Vue reactive 解构 bug

**输入**：

```vue
<script setup lang="ts">
import { reactive } from 'vue';
const form = reactive({ name: '', email: '' });
const { name, email } = form;
function submit() {
  console.log(name, email);  // 永远是空字符串
}
</script>
<template>
  <input v-model="name" />
  <input v-model="email" />
  <button @click="submit">提交</button>
</template>
```

**应命中规则**：Top 12 #6 + Vue 3 #1（不解构 reactive）+ Vue 3 #4（Props 用 toRefs）。

**期望输出**：
1. 指出 `const { name, email } = form` 拿到的是快照值而非响应引用，v-model 更新不会反映到 submit 读取的变量。
2. 提供两个修复方案：(a) `const { name, email } = toRefs(form)` 后在模板中直接用 `name` / `email`，脚本用 `name.value`；(b) 不解构，直接 `form.name` / `form.email`。
3. 推荐方案 (b)（更简洁，Vue 3 惯用写法）。

---

## 场景 3：XSS 防御代码审查（dangerouslySetInnerHTML）

**输入**（cc-code-reviewer 提交 PR 审查）：

```tsx
function BlogPost({ content }: { content: string }) {
  return <article dangerouslySetInnerHTML={{ __html: content }} />;
}
```

**应命中规则**：Top 12 #5 + 安全规范 #1（dangerouslySetInnerHTML 必须消毒）。

**期望输出**：
1. 标记为 P0 阻断级安全漏洞：用户提交的 content 可能含 `<script>` 或 `onerror` 事件，执行任意 JS。
2. 修复方案：
   - 引入 `dompurify`
   - `DOMPurify.sanitize(content, { ALLOWED_TAGS: ['p','b','i','a','h1','h2','h3','ul','li','code','pre'], ALLOWED_ATTR: ['href','title'] })`
3. 补充：理想方案是服务端存储时就消毒，前端做第二道防线。

---

## 场景 4：TypeScript strict 迁移（any → unknown + 类型守卫）

**输入**：

```ts
function handleApiResponse(res: any) {
  if (res.success) {
    return res.data.items.map((item: any) => item.name);
  }
  return [];
}
```

**应命中规则**：TypeScript 最佳实践（any → unknown） + TypeScript #1（strict: true）+ TypeScript 代码对照。

**期望输出**：
1. 定义具体响应类型：
   ```ts
   interface ApiResponse<T> { success: boolean; data: T; }
   interface Item { name: string; id: number; }
   ```
2. 或使用类型守卫（未知 schema 场景）：
   ```ts
   function isItemList(v: unknown): v is { items: Array<{ name: string }> } {
     return typeof v === 'object' && v !== null && 'items' in v
       && Array.isArray((v as { items: unknown }).items);
   }
   function handleApiResponse(res: unknown) {
     if (typeof res !== 'object' || res === null) return [];
     if (!('success' in res) || !(res as { success: boolean }).success) return [];
     if (!('data' in res) || !isItemList((res as { data: unknown }).data)) return [];
     return (res as { data: { items: { name: string }[] } }).data.items.map(i => i.name);
   }
   ```
3. 推荐运行时用 `zod` / `valibot` schema 校验（更少样板代码）。

---

## 场景 5：React 性能优化（lazy + 虚拟化 + memo）

**输入**（用户反馈首屏 Largest Contentful Paint (LCP) 8s，远超 Google Web Vitals Good 阈值 2.5s；长列表滚动卡顿 FPS < 30）：

```tsx
import { UserList } from './UserList';  // 包含 10000 用户
import { Dashboard } from './Dashboard';  // 大型组件
import { Settings } from './Settings';

function App() {
  const [page, setPage] = useState('list');
  return (
    <>
      {page === 'list' && <UserList users={users} />}
      {page === 'dashboard' && <Dashboard />}
      {page === 'settings' && <Settings />}
    </>
  );
}

function UserList({ users }) {
  return <ul>{users.map(u => <UserCard key={u.id} user={u} />)}</ul>;
}
```

**应命中规则**：性能 #1（路由级 lazy）+ 性能 #2（长列表虚拟化）+ 性能 #6（React.memo）+ Top 12 #9（key 稳定）。

**期望输出**：
1. 路由级代码分割：
   ```tsx
   const UserList = lazy(() => import('./UserList'));
   const Dashboard = lazy(() => import('./Dashboard'));
   const Settings = lazy(() => import('./Settings'));
   // 包 <Suspense fallback={<Spinner />}>
   ```
2. 长列表虚拟化（10000 行不能全渲染）：
   ```tsx
   import { useVirtualizer } from '@tanstack/react-virtual';
   // 只渲染可视区 ~20 行 + 缓冲
   ```
3. UserCard 加 `React.memo`（props 稳定时避免重渲染）。
4. 预期改进：LCP 8s → < 2.5s（Web Vitals Good），滚动 FPS 回到 60，首屏 JS 减少约 40-60%。

---

## 规则覆盖总结

| 场景 | Top 12 红线 | 章节规范 | 代码对照 |
|------|------------|---------|---------|
| 1 stale closure | #1 #3 #4 | React Hooks #1 #2 #3 | useEffect cleanup |
| 2 Vue reactive | #6 | Vue 3 #1 #4 | reactive 解构 |
| 3 XSS 防御 | #5 | 安全 #1 | dangerouslySetInnerHTML |
| 4 TS strict | - | TypeScript 最佳实践 | any → unknown |
| 5 React 性能 | #9 | 性能 #1 #2 #6 | - |

**验证方式**：每次修改本 Skill 后手动 walk through 5 个场景，确认修复建议是否能命中规则并给出具体代码。
