# Repository 查询与异常处理模板

## 一、Repository 查询模板

### 1. Repository 基础模板

```java
@Repository
public class ProjectRepository extends BaseRepository<Project, Long> {

    // ==================== 基础查询 ====================

    /**
     * 根据名称查询
     */
    public Project findByName(String name) {
        Condition<Project> condition = new Condition<>(Project.class);
        condition.and().andEqual(Project::getName, name);
        return findOneByCondition(condition);
    }

    /**
     * 根据名称判断是否存在
     */
    public boolean existsByName(String name) {
        Condition<Project> condition = new Condition<>(Project.class);
        condition.and().andEqual(Project::getName, name);
        return countByCondition(condition) > 0;
    }

    // ==================== 条件查询 ====================

    /**
     * 根据状态查询列表
     */
    public List<Project> findByStatus(Integer status) {
        Condition<Project> condition = new Condition<>(Project.class);
        condition.and().andEqual(Project::getStatus, status);

        Hints<Project> hints = new Hints<Project>()
            .addSort(Project::getCreatedAt, Direction.DESC);

        return findAllByConditionHints(condition, hints);
    }

    // 复杂条件查询：模糊/精确/时间范围组合 → 参考 Service 模板 1.1 分页查询或 1.5 Condition 查询模板

    // ==================== 批量查询 ====================

    /**
     * 根据 ID 列表查询
     */
    public List<Project> findByIds(List<Long> ids) {
        if (CollectionUtils.isEmpty(ids)) {
            return Collections.emptyList();
        }

        Condition<Project> condition = new Condition<>(Project.class);
        condition.and().andIn(Project::getId, ids);
        return findAllByCondition(condition);
    }

    /**
     * 根据 ID 列表查询并转为 Map
     */
    public Map<Long, Project> findMapByIds(List<Long> ids) {
        List<Project> list = findByIds(ids);
        return list.stream().collect(Collectors.toMap(
            Project::getId,
            Function.identity(),
            (v1, v2) -> v1
        ));
    }

    // 统计查询: countByCondition(condition) — 同 existsByName 模式

    // ==================== 私有方法 ====================

    /**
     * 模糊查询转义（每个 Repository 必备，标准实现）
     * Service 层如需使用，直接复制此方法
     */
    private String fuzzyLike(String str) {
        if (str == null || str.isEmpty()) {
            return "%%";
        }
        String escaped = str.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_");
        return "%" + escaped + "%";
    }
}
```

### 2. 批量统计查询模板（避免 N+1）

```java
// ==================== Mapper 层 ====================

@Select({
    "<script>",
    "SELECT project_id, COUNT(*) as count ",
    "FROM task ",
    "WHERE project_id IN ",
    "<foreach collection='projectIds' item='id' open='(' separator=',' close=')'>",
    "#{id}",
    "</foreach>",
    "GROUP BY project_id",
    "</script>"
})
List<Map<String, Object>> batchCountByProjectIds(@Param("projectIds") List<Long> projectIds);

// ==================== Repository 层 ====================

/**
 * 批量统计项目任务数
 *
 * @param projectIds 项目 ID 列表
 * @return Map<项目ID, 任务数>
 */
public Map<Long, Long> batchCountTaskByProjectIds(List<Long> projectIds) {
    if (CollectionUtils.isEmpty(projectIds)) {
        return Collections.emptyMap();
    }

    List<Map<String, Object>> results = baseMapper.batchCountByProjectIds(projectIds);

    return results.stream().collect(Collectors.toMap(
        row -> ((Number) row.get("project_id")).longValue(),
        row -> ((Number) row.get("count")).longValue()
    ));
}

// ==================== Service 层使用 ====================

/**
 * 填充任务数量（避免 N+1）
 */
private void fillTaskCount(List<ProjectResp> projects) {
    if (CollectionUtils.isEmpty(projects)) {
        return;
    }

    // 1. 收集 ID
    List<Long> projectIds = projects.stream()
        .map(ProjectResp::getId)
        .collect(Collectors.toList());

    // 2. 批量查询统计（1 次 SQL）
    Map<Long, Long> countMap = taskRepository.batchCountTaskByProjectIds(projectIds);

    // 3. 填充数据（O(1) 查找）
    projects.forEach(project ->
        project.setTaskCount(countMap.getOrDefault(project.getId(), 0L))
    );
}
```

### 3. 条件更新模板

```java
/**
 * 条件更新状态
 */
public int updateStatusByIds(List<Long> ids, Integer status) {
    if (CollectionUtils.isEmpty(ids)) {
        return 0;
    }

    Condition<Project> condition = new Condition<>(Project.class);
    condition.and().andIn(Project::getId, ids);

    Project updateEntity = Project.builder()
        .status(status)
        .updater(SecurityUtils.getCurrentUser())
        .build();

    return baseMapper.update(updateEntity, condition);
}

// 更多条件变体（andNotEqual、andIn 等）同上模式，替换 condition 条件即可
```

---

## 二、异常处理模板

### 1. 标准异常抛出模板

> 异常状态码速查表和基础用法详见 `standards-core.md` 异常体系章节，以下仅列出模板骨架

```java
// 客户端异常 (4xx)：400 参数校验 | 404 资源不存在 | 409 状态冲突 | 403 权限不足
throw new CjjClientException(400, "参数错误: 名称不能为空");
throw new CjjClientException(404, "项目不存在，ID: " + id);
throw new CjjClientException(409, "项目名称已存在: " + name);

// 服务端异常 (5xx)：外部调用包装
try {
    return externalClient.call(req);
} catch (TimeoutException e) {
    throw new CjjServerException(500, "外部服务调用超时: " + serviceName, e);
} catch (Exception e) {
    throw new CjjServerException(500, "外部服务调用失败: " + serviceName, e);
}
```

### 2. 校验工具类模板

```java
import lombok.experimental.UtilityClass;

/**
 * 参数校验工具类
 */
@UtilityClass
public class ValidationUtils {

    /**
     * 校验非空
     *
     * @param value   值
     * @param message 错误消息
     * @throws CjjClientException 400 - 参数为空
     */
    public static void requireNonNull(Object value, String message) {
        if (value == null) {
            throw new CjjClientException(400, message);
        }
    }

    /**
     * 校���字符串非空
     *
     * @param value   字符串值
     * @param message 错误消息
     * @throws CjjClientException 400 - 字符串为空
     */
    public static void requireNotBlank(String value, String message) {
        if (StringUtils.isBlank(value)) {
            throw new CjjClientException(400, message);
        }
    }

    /**
     * 校验集合非空
     *
     * @param collection 集合
     * @param message    错误消息
     * @throws CjjClientException 400 - 集合为空
     */
    public static void requireNotEmpty(Collection<?> collection, String message) {
        if (CollectionUtils.isEmpty(collection)) {
            throw new CjjClientException(400, message);
        }
    }

    /**
     * 校验资源存在
     *
     * @param resource     资源对象
     * @param resourceName 资源名称
     * @param id           资源 ID
     * @throws CjjClientException 404 - 资源不存在
     */
    public static void requireExists(Object resource, String resourceName, Object id) {
        if (resource == null) {
            throw new CjjClientException(404,
                String.format("%s不存在，ID: %s", resourceName, id));
        }
    }

    /**
     * 校验资源不存在（唯一性校验）
     *
     * @param exists       是否存在
     * @param resourceName 资源名称
     * @param fieldValue   字段值
     * @throws CjjClientException 409 - 资源已存在
     */
    public static void requireNotExists(boolean exists, String resourceName, Object fieldValue) {
        if (exists) {
            throw new CjjClientException(409,
                String.format("%s已存在: %s", resourceName, fieldValue));
        }
    }
}
```

### 3. 使用校验工具类

```java
// 参数校验 → ValidationUtils.requireNotBlank(req.getName(), "项目名称不能为空");
// 唯一性校验 → ValidationUtils.requireNotExists(exists, "项目名称", req.getName());
// 资源存在校验 → ValidationUtils.requireExists(project, "项目", id);
```

### 4. 自定义业务异常模板

```java
/**
 * 业务流程执行异常 - 携带执行上下文，支持重试
 */
@Setter
@Getter
public class BizExecutionException extends CjjException {
    private String bizKey;
    private Map<String, Object> context;
    private Integer delaySeconds;  // 重试延迟（秒）

    public BizExecutionException(int code, String message) {
        super(500, code, message);
    }

    public BizExecutionException(int code, String message, String bizKey) {
        super(500, code, message + ", bizKey=" + bizKey);
        this.bizKey = bizKey;
    }

    public BizExecutionException withContext(Map<String, Object> context) {
        this.context = context;
        return this;
    }

    public BizExecutionException withDelay(Integer delaySeconds) {
        this.delaySeconds = delaySeconds;
        return this;
    }
}

// 使用: throw new BizExecutionException(1001, "处理失败", bizKey).withContext(ctx).withDelay(60);
```

---

## 三、枚举定义模板

> 完整枚举设计规范（业务方法、带执行顺序、字符串 Code 版本、反例）详见 `patterns-design.md` 枚举设计章节

```java
@Getter
@AllArgsConstructor
public enum StatusEnum {
    DRAFT(0, "草稿"),
    PROCESSING(1, "处理中"),
    COMPLETED(2, "已完成"),
    FAILED(3, "失败");

    private final int code;
    private final String name;

    public static StatusEnum fromCode(int code) {
        for (StatusEnum status : values()) {
            if (status.code == code) {
                return status;
            }
        }
        throw new IllegalArgumentException("Unknown status code: " + code);
    }
}
```

**必要元素**: `code` + `name` + `fromCode()` + `@Getter`，业务方法 `isTerminal()` / `canTransitionTo()` 按需添加

---

## 四、日志记录模板

> 日志级别规范和禁忌详见 `standards-core.md` 日志规范章节

```java
log.info("createOrder start, userId={}, productId={}", userId, productId);   // INFO: 关键节点
log.warn("getData empty, bizId={}", bizId);                                   // WARN: 可恢复
log.error("createOrder failed, userId={}", userId, e);                        // ERROR: 必须带异常对象
```

---

## 五、模板快速查找表

| 场景 | 模板位置 |
|------|---------|
| 写 Service CRUD | templates-service-controller.md 一.1 |
| 批量操作 | templates-service-controller.md 一.2 |
| 事务操作 | templates-service-controller.md 一.3 |
| 加分布式锁 | templates-service-controller.md 一.4 |
| 构建查询条件 | templates-service-controller.md 一.5 |
| 写 Controller | templates-service-controller.md 二.1 |
| 文件上传/下载 | templates-service-controller.md 二.2/二.3 |
| 写 Repository | 本文件 一.1 |
| 避免 N+1 | 本文件 一.2 |
| 条件更新 | 本文件 一.3 |
| 抛异常 | 本文件 二.1 |
| 参数校验工具 | 本文件 二.2 |
| 枚举定义 | 本文件 三 |
| 日志写法 | 本文件 四 |

### 模板使用步骤

1. 找到对应场景的模板
2. 复制模板代码
3. 替换实体名称（Project -> 你的实体）
4. 根据业务调整字段和逻辑
5. 添加完整的 JavaDoc 注释

---

## 六、PR 前自查清单

### 基础规范

- [ ] 包名使用 `cn.caijiajia.*`
- [ ] DTO 分离到 `req/` 和 `resp/` 目录
- [ ] Controller 只注入 Service
- [ ] Service 只注入 Repository
- [ ] 方法不超过 50 行，嵌套不超过 3 层

### 数据访问

- [ ] 列表查询有分页（PageHelper.startPage）
- [ ] 批量操作有分批（500 条，Lists.partition）
- [ ] 无循环内查库（N+1）
- [ ] SQL 无 SELECT *，字段有 AS 映射
- [ ] 多表写入有 @Transactional(rollbackFor = Exception.class)

### 异常日志

- [ ] 客户端错误用 CjjClientException(4xx)，服务端用 CjjServerException(500)
- [ ] 日志使用占位符 `log.info("key={}", value)`
- [ ] ERROR 日志带异常对象
- [ ] 无异常吞掉（catch 后必须 throw 或 log.error）

### 设计模式

- [ ] 枚举有 code/name 字段和 fromCode() 方法
- [ ] 多分支考虑策略模式
- [ ] 幂等操作有分布式锁

> 完整红线规则详见 `standards-quickref.md`
