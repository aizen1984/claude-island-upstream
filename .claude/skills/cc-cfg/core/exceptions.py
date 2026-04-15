"""配置查询异常体系"""


class CfgError(Exception):
    """配置查询基础异常"""
    pass


class CfgConnectionError(CfgError):
    """连接/网络/Token 相关异常"""
    pass


class CfgNotFoundError(CfgError):
    """配置不存在"""
    pass
