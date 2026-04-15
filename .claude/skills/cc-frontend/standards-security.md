# 前端安全规范

> cc-frontend 子文件：安全防护规范。导航回 [SKILL.md](SKILL.md)。

---

## 安全规范

| # | 规则 | 危险等级 | 说明 |
|---|------|---------|------|
| 1 | `dangerouslySetInnerHTML` 必须消毒 | 极高 | `DOMPurify.sanitize(html)` |
| 2 | 禁止 `eval` / `new Function` | 极高 | 用户输入绝不 eval |
| 3 | `href` 未校验协议 | 高 | 拒绝 `javascript:` / `data:` |
| 4 | Token 存 localStorage | 高 | XSS 可窃取 → HttpOnly Cookie |
| 5 | 环境变量暴露密钥 | 高 | `VITE_` / `NEXT_PUBLIC_` 前缀会暴露到客户端，密钥不加前缀 |
| 6 | 无 Content Security Policy (CSP) | 中 | 无法阻止注入脚本，建议至少配置 `script-src 'self'` |
| 7 | `target="_blank"` 无 `rel` | 中 | 反向 tabnabbing → `rel="noopener noreferrer"` |

### 示例：dangerouslySetInnerHTML 安全防御

错误（XSS 漏洞）：

```tsx
function Comment({ html }: { html: string }) {
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}
```

正确：

```tsx
import DOMPurify from 'dompurify';
function Comment({ html }: { html: string }) {
  const clean = DOMPurify.sanitize(html, { ALLOWED_TAGS: ['b', 'i', 'a'] });
  return <div dangerouslySetInnerHTML={{ __html: clean }} />;
}
```
