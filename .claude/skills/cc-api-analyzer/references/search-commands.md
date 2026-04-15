# 快速参考：搜索命令

## 一、接口发现

```
# 查找所有 Controller 文件
Glob(pattern="src/main/java/cn/caijiajia/**/*Controller.java")

# 查找所有 Controller 类（含 @RestController）
Grep(pattern="@(Controller|RestController)", glob="*.java", path="src/main/java/")

# 查找所有接口映射
Grep(pattern="@(RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)", glob="*.java", path="src/main/java/")

# 提取 Controller 方法签名（含上下文）
Grep(pattern="@(GetMapping|PostMapping|PutMapping|DeleteMapping)", glob="*.java", path="src/main/java/", output_mode="content", -A=2)
```

## 二、调用链追踪

```
# Controller → Service 依赖
Grep(pattern="(private|final).*Service\s+\w+", glob="*Controller.java", path="src/main/java/", output_mode="content")

# Service → Repository/Mapper 依赖
Grep(pattern="(private|final).*(Repository|Mapper)\s+\w+", glob="*Service*.java", path="src/main/java/", output_mode="content")

# Repository → Table（XML 中的表名）
Grep(pattern="(from|into|update|join)\s+\w+", glob="*.xml", path="src/main/resources/", output_mode="content")

# 实体表名注解（JPA @Table 和 MyBatis-Plus @TableName）
Grep(pattern="@(Table|TableName|Entity)", glob="*.java", path="src/main/java/", output_mode="content", -A=1)
```

## 三、表关系提取

```
# 查找所有实体类和表名（含 @TableName）
Grep(pattern="@(Entity|Table|TableName)", glob="*.java", path="src/main/java/", output_mode="content", -A=1)

# 提取表名值
Grep(pattern="@(Table|TableName)\\(.*name\\s*=", glob="*.java", path="src/main/java/", output_mode="content")

# 查找 JPA 关联关系
Grep(pattern="@(OneToMany|ManyToOne|ManyToMany|OneToOne)", glob="*.java", path="src/main/java/", output_mode="content", -A=2)

# 查找外键定义
Grep(pattern="@(JoinColumn|JoinTable)", glob="*.java", path="src/main/java/", output_mode="content", -A=1)
```

## 四、SQL 分析

```
# 查找 Mapper XML 文件
Glob(pattern="src/main/resources/**/*Mapper.xml")

# 从 XML 提取表名
Grep(pattern="(from|into|update|join)\\s+\\w+", glob="*Mapper.xml", path="src/main/resources/", output_mode="content")

# 查找 Condition/BaseRepository 查询（数禾特有）
Grep(pattern="(findByCondition|baseRepository|BaseMapper)", glob="*.java", path="src/main/java/", output_mode="content", -A=3)
```

## 五、常用分析模式

| 模式 | 步骤 |
|------|------|
| 单接口追踪 | 定位 Controller → 找 Service → 找 Repository → 提取表 |
| 批量接口分析 | 列出所有 Controller → 提取接口 → 逐个追踪 → 汇总 → ER 图 |
| 表关系分析 | 找实体类 → 提取表名字段 → 分析关联注解 → ER 图 |

## 六、输出模板

### 接口清单格式

```markdown
| 方法 | 路径 | HTTP | 功能 |
|------|------|------|------|
| getUser | /api/user/{id} | GET | 获取用户详情 |
```

### 调用链格式

```markdown
UserController.getUser(id)
    └── UserService.getUserById(id)
        └── UserRepository.findById(id)
            └── Table: t_user [SELECT]
```

### 表关系格式

```markdown
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| dept_id | BIGINT | 外键 → t_department.id |
```

## 七、错误处理

| 问题 | 解决方案 |
|------|---------|
| 找不到 Service 调用 | 搜索接口名（可能使用了接口而非实现类） |
| 调用链断裂 | 检查配置文件（动态代理或反射） |
| 表名不匹配 | 检查 SQL 语句（别名或动态表名） |
| 动态 SQL | 检查 `<if>` 和 `<choose>` 标签 |
| 多数据源 | 检查 `@DS` 注解 |
| 找不到 @Table 注解 | 尝试 @TableName（MyBatis-Plus） |
