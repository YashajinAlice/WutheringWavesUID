"""
鳴潮助手網站模組
獨立於機器人功能，不影響現有服務
"""

from .config import config
from .app import create_app

__all__ = ["create_app", "config"]
