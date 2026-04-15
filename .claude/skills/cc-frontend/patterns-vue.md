# Vue 3 编码规范

> cc-frontend 子文件：Vue 3 Composition API 规范。导航回 [SKILL.md](SKILL.md)。

---

## Vue 3 Composition API 规范

| # | 规则 | 说明 |
|---|------|------|
| 1 | 不解构 reactive | 用 `toRefs(state)` 保持响应性 |
| 2 | 原始类型用 ref | `reactive('hello')` 无效 → `ref('hello')` |
| 3 | 不整体替换 reactive | 修改属性而非重赋值 |
| 4 | Props 用 toRefs | `const { msg } = toRefs(props)` |
| 5 | watch deep 嵌套 | `watch(state, handler, { deep: true })` |
| 6 | composable 顶层调用 | 不在条件/循环中 |
| 7 | defineProps 可变默认值用工厂 | `withDefaults(defineProps<Props>(), { items: () => [] })` |

### 示例：reactive 解构陷阱

错误（响应性丢失）：

```vue
<script setup lang="ts">
import { reactive } from 'vue';
const state = reactive({ msg: 'hello', count: 0 });
const { msg, count } = state;  // msg/count 变成普通值，模板不会更新
</script>
```

正确：

```vue
<script setup lang="ts">
import { reactive, toRefs } from 'vue';
const state = reactive({ msg: 'hello', count: 0 });
const { msg, count } = toRefs(state);  // 保持响应性
// 模板中直接用 {{ msg }} {{ count }}，脚本中用 msg.value / count.value
</script>
```
