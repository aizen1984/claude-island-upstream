# Java 后端安全规范

> 基于阿里巴巴 Java 手册安全规约 + OWASP Top 10 2025，适配数禾技术栈

---

## 一、SQL 注入防护

```java
// ✅ #{} 参数化绑定（PreparedStatement，自动转义）
@Select("SELECT * FROM project WHERE id = #{id}")
Project findById(@Param("id") Long id);

// ❌ ${} 字符串拼接（直接拼入 SQL，注入风险）
@Select("SELECT * FROM project WHERE id = ${id}")
```

**动态表名/列名**：必须白名单校验后才能使用 `${}`，禁止直接拼接用户输入。

**Condition API** 天然防注入（参数化查询），优先使用。动态排序配合 `SqlShieldUtil.filterSpecialCharacters()`。

> 详见 standards-core.md §4.1, §4.2

---

## 二、XSS 防护

```java
// ✅ 输出到页面的用户输入必须转义
String safeContent = HtmlUtils.htmlEscape(userInput);
// ✅ 富文本使用白名单 HTML 标签
String safeHtml = Jsoup.clean(rawHtml, Whitelist.basicWithImages());
```

规则：用户输入不可信 -> 入库前校验格式 -> 输出时转义 -> 富文本白名单过滤

---

## 三、敏感数据脱敏

### 3.1 日志脱敏（强制）

```java
// ❌ 禁止打印明文
log.info("用户: 手机={}, 身份证={}", phone, idCard);
// ✅ 脱敏后打印
log.info("用户: 手机={}, 身份证={}", DesensitizedUtil.mobilePhone(phone),
         DesensitizedUtil.idCardNum(idCard, 4, 4));
```

常用脱敏：`mobilePhone()` -> 138\*\*\*\*5678 | `idCardNum(s, 4, 4)` -> 3201\*\*\*\*5678 | `bankCard()` -> 6222 \*\*\*\* 1234

### 3.2 接口返回脱敏

Service 层返回前调用 `DesensitizedUtil` 脱敏。敏感接口使用 `@HttpLogControlConfig(excludesFromAll = {HttpLogItem.responseBody})` 排除响应体日志。

---

## 四、接口鉴权

```java
// ✅ 所有对外接口经 Moka 网关鉴权，内部权限用注解
@RequiresPermissions("project:create")
@PostMapping
public Result<Long> create(@RequestBody @Valid CreateProjectReq req) { ... }
```

- **内部 Feign 调用**：通过 header 标识来源（`X-Internal-Source`）+ 网关白名单验证
- **批量操作限流**：batch 接口单次上限 <= 500，防止恶意大批量请求

---

## 五、文件上传安全

```java
// ✅ 完整校验流程
private static final Set<String> ALLOWED_TYPES = Set.of("image/jpeg", "image/png", "application/pdf");

public void upload(MultipartFile file) {
    if (!ALLOWED_TYPES.contains(file.getContentType())) {  // 1. MIME 白名单
        throw new CjjClientException(400, "不支持的文件类型");
    }
    // 2. 文件名 sanitize（防路径遍历），3. 存储路径服务端生成（禁止用户控制）
    String safeName = file.getOriginalFilename().replaceAll("[.]{2,}|[/\\\\]", "_");
    ossService.uploadFile(bucket, prefix, safeName, file.getInputStream(), mimeType);
}
```

> OSS 上传详见 standards-infra.md §7.2

---

## 六、其他安全要求

| 场景 | 规则 |
|------|------|
| 密码/密钥 | 禁止硬编码，使用 ConfPlus 配置中心或环境变量 |
| HTTPS | 生产环境全量 HTTPS，禁止 HTTP 明文传输 |
| 序列化 | 禁止 Java 原生序列化（`ObjectInputStream`），使用 JSON |
| 正则表达式 | 避免 ReDoS：禁止用户输入直接作为正则 |
| 错误信息 | 禁止暴露堆栈/SQL/内部路径给客户端（CjjException 统一处理） |
| CSRF | POST/PUT/DELETE 通过 Moka 网关 Token 校验防护 |

---

## 七、常见陷阱

| # | 陷阱 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | MyBatis 用 `${}` 拼接用户输入 | SQL 注入，数据泄露 | `#{}` 或 Condition API |
| 2 | 日志打印手机号/身份证明文 | 敏感数据泄露 | `DesensitizedUtil` 脱敏 |
| 3 | 接口未加权限校验 | 越权访问 | `@RequiresPermissions` + Moka 网关 |
| 4 | 文件上传只校验扩展名 | 恶意文件绕过 | MIME 白名单 + 大小限制 |
| 5 | 密钥硬编码在代码中 | 代码泄露即密钥泄露 | ConfPlus / 环境变量 |
| 6 | catch 后返回原始 message | 暴露内部实现 | CjjException 统一包装 |
| 7 | 用户输入直接拼接日志 | 日志注入（CRLF） | `@Slf4j` 占位符 `{}` |
| 8 | 批量接口无数量限制 | DB 压力 | 单次上限 500 |
