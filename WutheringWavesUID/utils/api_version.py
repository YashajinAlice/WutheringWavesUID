"""
API版本控制配置文件
統一管理所有API相關的版本號
"""

# API版本號
API_VERSION = "1.1.0"

# 版本信息
VERSION_INFO = {"version": API_VERSION, "status": "active", "message": "API運行正常"}


def get_api_version() -> str:
    """獲取API版本號"""
    return API_VERSION


def get_version_info() -> dict:
    """獲取完整版本信息"""
    return VERSION_INFO.copy()
