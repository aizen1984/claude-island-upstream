"""Skills 异常定义"""


class SkillError(Exception):
    """Skills 基础异常"""

    def __init__(self, message: str, code: str = "SKILL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class SecurityError(SkillError):
    """SQL 安全校验异常"""

    def __init__(self, message: str):
        super().__init__(message, code="SQL_SECURITY_ERROR")


class SelectStarError(SkillError):
    """SELECT * 检测异常"""

    def __init__(self, message: str = "不允许使用 SELECT *，请指定具体列名"):
        super().__init__(message, code="SELECT_STAR_ERROR")


class AggregateError(SkillError):
    """聚合查询缺少索引条件异常"""

    def __init__(self, message: str = "聚合查询（COUNT/SUM/AVG/MIN/MAX/GROUP BY）必须包含 WHERE 条件且条件字段应为索引字段"):
        super().__init__(message, code="AGGREGATE_ERROR")


class ConnectionError(SkillError):
    """连接/请求异常"""

    def __init__(self, message: str):
        super().__init__(message, code="CONNECTION_ERROR")


class ConfigError(SkillError):
    """配置异常"""

    def __init__(self, message: str):
        super().__init__(message, code="CONFIG_ERROR")
