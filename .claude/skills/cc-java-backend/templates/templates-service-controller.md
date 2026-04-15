# Service 与 Controller 方法模板

## 一、Service 方法模板

### 1. CRUD 完整 Service 模板

```java
@Slf4j
@Service
public class ProjectService {

    @Autowired
    private ProjectRepository projectRepository;

    // ==================== 创建 ====================

    /**
     * 创建项目
     *
     * @param req 创建请求
     * @return 项目 ID
     * @throws CjjClientException 409 - 项目名称已存在
     */
    public Long create(ProjectCreateReq req) {
        // 1. 唯一性校验
        boolean exists = projectRepository.existsByName(req.getName());
        if (exists) {
            throw new CjjClientException(409, "项目名称已存在: " + req.getName());
        }

        // 2. 构建实体
        Project project = Project.builder()
            .name(req.getName())
            .description(req.getDescription())
            .status(ProjectStatus.ACTIVE.getCode())
            .creator(SecurityUtils.getCurrentUser())
            .updater(SecurityUtils.getCurrentUser())
            .build();

        // 3. 保存并返回
        projectRepository.save(project);
        log.info("创建项目成功: projectId={}, name={}", project.getId(), project.getName());
        return project.getId();
    }

    // ==================== 查询单个 ====================

    /**
     * 根据 ID 获取项目详情
     *
     * @param id 项目 ID
     * @return 项目详情
     * @throws CjjClientException 404 - 项目不存在
     */
    public ProjectResp getById(Long id) {
        Project project = projectRepository.findById(id);
        if (project == null) {
            throw new CjjClientException(404, "项目不存在，ID: " + id);
        }
        return BeanUtil.copyProperties(project, ProjectResp.class);
    }

    // ==================== 分页查询 ====================

    /**
     * 分页查询项目列表
     *
     * @param req 查询条件
     * @return 分页结果
     */
    public PageInfo<ProjectResp> list(ProjectQueryReq req) {
        // 1. 启动分页
        PageHelper.startPage(req.getPageNum(), req.getPageSize());

        // 2. 构建查询条件
        Condition<Project> condition = new Condition<>(Project.class);
        if (StringUtils.isNotEmpty(req.getName())) {
            condition.and().andLike(Project::getName, fuzzyLike(req.getName()));
        }
        if (req.getStatus() != null) {
            condition.and().andEqual(Project::getStatus, req.getStatus());
        }

        // 3. 排序
        Hints<Project> hints = new Hints<Project>()
            .addSort(Project::getCreatedAt, Direction.DESC);

        // 4. 执行查询
        List<Project> list = projectRepository.findAllByConditionHints(condition, hints);

        // 5. 转换返回
        PageInfo<Project> pageInfo = new PageInfo<>(list);
        return PageInfo.of(
            BeanUtil.copyToList(pageInfo.getList(), ProjectResp.class),
            pageInfo.getTotal()
        );
    }

    // ==================== 更新 ====================

    /**
     * 更新项目
     *
     * @param id  项目 ID
     * @param req 更新请求
     * @throws CjjClientException 404 - 项目不存在
     * @throws CjjClientException 409 - 项目名称已存在
     */
    public void update(Long id, ProjectUpdateReq req) {
        // 1. 查询并校验存在
        Project project = projectRepository.findById(id);
        if (project == null) {
            throw new CjjClientException(404, "项目不存在，ID: " + id);
        }

        // 2. 名称唯一性校验（排除自身）
        if (StringUtils.isNotEmpty(req.getName()) && !req.getName().equals(project.getName())) {
            boolean exists = projectRepository.existsByName(req.getName());
            if (exists) {
                throw new CjjClientException(409, "项目名称已存在: " + req.getName());
            }
        }

        // 3. 更新字段
        if (StringUtils.isNotEmpty(req.getName())) {
            project.setName(req.getName());
        }
        if (req.getDescription() != null) {
            project.setDescription(req.getDescription());
        }
        project.setUpdater(SecurityUtils.getCurrentUser());

        // 4. 保存
        projectRepository.update(project);
        log.info("更新项目成功: projectId={}", id);
    }

    // ==================== 删除 ====================

    /**
     * 删除项目
     *
     * @param id 项目 ID
     * @throws CjjClientException 404 - 项目不存在
     * @throws CjjClientException 409 - 项目有关联数据无法删除
     */
    public void delete(Long id) {
        // 1. 查询并校验存在
        Project project = projectRepository.findById(id);
        if (project == null) {
            throw new CjjClientException(404, "项目不存在，ID: " + id);
        }

        // 2. 检查关联数据
        boolean hasRelatedData = checkRelatedData(id);
        if (hasRelatedData) {
            throw new CjjClientException(409, "项目有关联数据，无法删除，ID: " + id);
        }

        // 3. 软删除
        projectRepository.deleteById(id);
        log.info("删除项目成功: projectId={}", id);
    }

    // ==================== 私有方法 ====================

    // fuzzyLike() 实现见下方 Repository 模板（3.1 节），Service 中直接调用 Repository 的方法或复制同一实现

    private boolean checkRelatedData(Long projectId) {
        // 检查关联数据的逻辑
        return false;
    }
}
```

### 2. 批量操作模板

```java
/**
 * 批量创建
 *
 * @param reqList 创建请求列表
 * @return 创建的 ID 列表
 */
@Transactional(rollbackFor = Exception.class)
public List<Long> batchCreate(List<ItemCreateReq> reqList) {
    if (CollectionUtils.isEmpty(reqList)) {
        return Collections.emptyList();
    }

    // 1. 转换实体
    List<Item> items = reqList.stream()
        .map(req -> Item.builder()
            .name(req.getName())
            .creator(SecurityUtils.getCurrentUser())
            .build())
        .collect(Collectors.toList());

    // 2. 分批插入（超过 500 条分批）
    if (items.size() > 500) {
        Lists.partition(items, 500).forEach(batch ->
            itemMapper.batchInsert(batch));
    } else {
        itemMapper.batchInsert(items);
    }

    log.info("批量创建完成: 数量={}", items.size());
    return items.stream().map(Item::getId).collect(Collectors.toList());
}

/**
 * 批量删除（分批逻辑同上 batchCreate）
 */
@Transactional(rollbackFor = Exception.class)
public void batchDelete(List<Long> ids) {
    if (CollectionUtils.isEmpty(ids)) {
        return;
    }
    Lists.partition(ids, 500).forEach(batch ->
        itemRepository.deleteByIds(batch));
    log.info("批量删除完成: 数量={}", ids.size());
}
```

### 3. 事务方法模板

```java
/**
 * 需要事务的复合操作
 *
 * @param req 请求参数
 * @throws CjjClientException 业务异常
 */
@Transactional(rollbackFor = Exception.class)
public void complexOperation(OperationReq req) {
    // 1. 操作表 A
    tableARepository.save(entityA);

    // 2. 操作表 B
    tableBRepository.save(entityB);

    // 3. 操作表 C
    tableCRepository.updateStatus(id, status);

    log.info("复合操作完成: id={}", req.getId());
}

/**
 * 本类调用事务方法（必须使用 AopContext）
 */
public void outerMethod(Long id) {
    // 业务逻辑...

    // 本类调用事务方法，必须通过代理
    ((ProjectService) AopContext.currentProxy()).transactionalMethod(id);
}

@Transactional(rollbackFor = Exception.class)
public void transactionalMethod(Long id) {
    // 事务操作...
}
```

### 4. 分布式锁模板

> 锁 Key 命名规范、超时时间选择、常见场景详见 `patterns-concurrency.md` 分布式锁章节

```java
@Autowired
private DistributedLock distributedLock;

public void processWithLock(String taskId) {
    String lockKey = "task:process:" + taskId;
    boolean locked = false;
    try {
        locked = distributedLock.lock(lockKey, 30, TimeUnit.MINUTES);
        if (!locked) {
            throw new CjjClientException(409, "任务正在处理中，请稍后重试");
        }
        doProcess(taskId);
    } finally {
        if (locked) {
            distributedLock.unlock(lockKey);
        }
    }
}
```

### 5. Condition 查询模板

```java
private Condition<Entity> buildCondition(QueryReq req) {
    Condition<Entity> condition = new Condition<>(Entity.class);
    condition.and()
        .andEqual(Entity::getStatus, req.getStatus())
        .andLike(Entity::getName, fuzzyLike(req.getName()))
        .andIn(Entity::getType, req.getTypes())
        .andBetween(Entity::getCreateTime, req.getStartTime(), req.getEndTime());
    return condition;
}

private Hints<Entity> buildHints(QueryReq req) {
    return new Hints<Entity>()
        .addSort(Entity::getCreatedAt, Direction.DESC);
}
```

**适用场景**: 条件查询、筛选接口

---

## 二、Controller 方法模板

### 1. 完整 Controller 模板

```java
@Api("项目管理")
@RestController
@RequestMapping("api/v1/project")
@Slf4j
public class ProjectController {

    @Autowired
    private ProjectService projectService;

    // ==================== 查询 ====================

    @GetMapping("list")
    @ApiOperation("查询项目列表")
    public Page<ProjectResp> list(
        @ApiParam("项目名称") @RequestParam(required = false) String name,
        @ApiParam("状态") @RequestParam(required = false) Integer status,
        @RequestParam(defaultValue = "1") int pageNum,
        @RequestParam(defaultValue = "20") int pageSize) {

        // 限制分页大小
        if (pageSize > 100) {
            pageSize = 100;
        }

        ProjectQueryReq req = ProjectQueryReq.builder()
            .name(name)
            .status(status)
            .pageNum(pageNum)
            .pageSize(pageSize)
            .build();

        return projectService.list(req);
    }

    @GetMapping("{id}")
    @ApiOperation("查询项目详情")
    public ProjectResp getById(@PathVariable Long id) {
        return projectService.getById(id);
    }

    // ==================== 创建 ====================

    @PostMapping
    @ApiOperation("创建项目")
    public CommonResp create(@RequestBody @Valid ProjectCreateReq req) {
        Long projectId = projectService.create(req);
        return CommonResp.successWithId("项目创建成功", projectId);
    }

    // ==================== 更新 ====================

    @PutMapping("{id}")
    @ApiOperation("更新项目")
    public CommonResp update(
        @PathVariable Long id,
        @RequestBody @Valid ProjectUpdateReq req) {
        projectService.update(id, req);
        return CommonResp.success("项目更新成功");
    }

    // ==================== 删除 ====================

    @DeleteMapping("{id}")
    @ApiOperation("删除项目")
    public CommonResp delete(@PathVariable Long id) {
        projectService.delete(id);
        return CommonResp.success("项目删除成功");
    }

    @PostMapping("batch-delete")
    @ApiOperation("批量删除项目")
    public CommonResp batchDelete(@RequestBody @Valid BatchDeleteReq req) {
        projectService.batchDelete(req.getIds());
        return CommonResp.success("批量删除成功");
    }
}
```

### 2. 文件上传 Controller 模板

```java
@PostMapping(value = "upload", consumes = "multipart/form-data")
@ApiOperation("上传文件")
public FileUploadResp upload(
    @RequestParam("projectId") Long projectId,
    @RequestParam("file") MultipartFile file) throws IOException {

    log.info("上传文件: projectId={}, fileName={}, size={}",
        projectId, file.getOriginalFilename(), file.getSize());

    return fileService.upload(projectId, file);
}

@PostMapping(value = "batch-upload", consumes = "multipart/form-data")
@ApiOperation("批量上传文件")
public List<FileUploadResp> batchUpload(
    @RequestParam("projectId") Long projectId,
    @RequestParam("files") MultipartFile[] files) throws IOException {

    log.info("批量上传文件: projectId={}, count={}", projectId, files.length);
    return fileService.batchUpload(projectId, files);
}
```

### 3. 文件下载 Controller 模板

```java
@GetMapping("{id}/download")
@ApiOperation("下载文件")
public void download(
    @PathVariable("id") Long id,
    HttpServletResponse response) throws IOException {

    Map<String, Object> result = fileService.downloadFile(id);

    try (InputStream inputStream = (InputStream) result.get("inputStream")) {
        String fileName = (String) result.get("fileName");
        String contentType = (String) result.getOrDefault(
            "contentType", "application/octet-stream");

        response.setContentType(contentType);
        response.setHeader("Content-Disposition",
            "attachment;filename=" + URLEncoder.encode(fileName, StandardCharsets.UTF_8));

        try (OutputStream os = response.getOutputStream()) {
            inputStream.transferTo(os);
            os.flush();
        }
    }
}
```

### 4. 带路径参数的 Controller 模板

```java
@Api("任务管理")
@RestController
@RequestMapping("{projectId}/task")
@Slf4j
public class TaskController {

    @Autowired
    private TaskService taskService;

    @GetMapping("list")
    @ApiOperation("查询任务列表")
    public Page<TaskResp> list(
        @PathVariable Long projectId,
        @RequestParam(required = false) String name,
        @RequestParam(defaultValue = "1") int pageNum,
        @RequestParam(defaultValue = "20") int pageSize) {

        return taskService.list(projectId, name, pageNum, pageSize);
    }

    @GetMapping("{taskId}")
    @ApiOperation("查询任务详情")
    public TaskResp getById(
        @PathVariable Long projectId,
        @PathVariable Long taskId) {

        return taskService.getById(projectId, taskId);
    }
}
```
