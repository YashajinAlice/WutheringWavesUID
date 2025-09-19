"""
網站配置管理
獨立配置，不影響機器人設置
"""

import os
from typing import Optional

from pydantic_settings import BaseSettings


class WebsiteConfig(BaseSettings):
    """網站配置類"""

    # 基本設置
    app_name: str = "鳴潮助手"
    app_version: str = "1.0.0"
    debug: bool = False

    # 服務器設置
    host: str = "0.0.0.0"
    port: int = 8000

    # 數據庫設置 (使用現有的數據庫，但獨立連接)
    database_url: Optional[str] = None

    # JWT 設置
    jwt_secret_key: str = "waves_website_secret_key_2024"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    # 驗證碼設置
    auth_code_expire_minutes: int = 5
    max_auth_attempts: int = 3

    # 安全設置
    cors_origins: list = ["*"]
    rate_limit_per_minute: int = 60

    # 靜態文件設置
    static_dir: str = "static"
    templates_dir: str = "templates"

    class Config:
        env_file = ".env"
        env_prefix = "WAVES_WEBSITE_"


# 全局配置實例
config = WebsiteConfig()
