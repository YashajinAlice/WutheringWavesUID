"""
背景管理器 - 處理用戶自定義背景
"""

import os
from pathlib import Path
from typing import Union, Optional

from gsuid_core.logger import logger

from .payment_manager import payment_manager


class BackgroundManager:
    """背景管理器"""

    def __init__(self):
        self.default_bg_path = Path("WutheringWavesUID/utils/texture2d/bg.png")
        self.user_bg_dir = Path("WutheringWavesUID/utils/texture2d/user_backgrounds")
        self.user_bg_dir.mkdir(parents=True, exist_ok=True)

    def get_user_background_path(self, user_id: str) -> Optional[Path]:
        """
        獲取用戶背景圖片路徑

        Args:
            user_id: 用戶ID

        Returns:
            背景圖片路徑，如果沒有則返回None
        """
        try:
            # 檢查是否為Premium用戶
            if not payment_manager.is_premium_user(user_id):
                return None

            # 檢查用戶自定義背景
            user_bg_file = self.user_bg_dir / f"{user_id}_bg.png"
            if user_bg_file.exists():
                return user_bg_file

            return None

        except Exception as e:
            logger.error(f"[背景管理器] 獲取用戶背景路徑失敗: {e}")
            return None

    def get_background_path(self, user_id: str) -> Path:
        """
        獲取背景圖片路徑（優先使用用戶自定義背景）

        Args:
            user_id: 用戶ID

        Returns:
            背景圖片路徑
        """
        try:
            # 嘗試獲取用戶自定義背景
            user_bg = self.get_user_background_path(user_id)
            if user_bg:
                return user_bg

            # 使用默認背景
            return self.default_bg_path

        except Exception as e:
            logger.error(f"[背景管理器] 獲取背景路徑失敗: {e}")
            return self.default_bg_path

    def has_custom_background(self, user_id: str) -> bool:
        """
        檢查用戶是否有自定義背景

        Args:
            user_id: 用戶ID

        Returns:
            是否有自定義背景
        """
        try:
            if not payment_manager.is_premium_user(user_id):
                return False

            user_bg_file = self.user_bg_dir / f"{user_id}_bg.png"
            return user_bg_file.exists()

        except Exception as e:
            logger.error(f"[背景管理器] 檢查自定義背景失敗: {e}")
            return False

    def delete_user_background(self, user_id: str) -> bool:
        """
        刪除用戶自定義背景

        Args:
            user_id: 用戶ID

        Returns:
            是否成功刪除
        """
        try:
            user_bg_file = self.user_bg_dir / f"{user_id}_bg.png"
            if user_bg_file.exists():
                user_bg_file.unlink()
                logger.info(f"[背景管理器] 刪除用戶 {user_id} 的自定義背景")
                return True

            return False

        except Exception as e:
            logger.error(f"[背景管理器] 刪除用戶背景失敗: {e}")
            return False

    def get_background_info(self, user_id: str) -> dict:
        """
        獲取背景信息

        Args:
            user_id: 用戶ID

        Returns:
            背景信息字典
        """
        try:
            has_custom = self.has_custom_background(user_id)
            bg_path = self.get_background_path(user_id)

            return {
                "has_custom_background": has_custom,
                "background_path": str(bg_path),
                "background_name": bg_path.name,
                "is_default": bg_path == self.default_bg_path,
                "file_exists": bg_path.exists(),
            }

        except Exception as e:
            logger.error(f"[背景管理器] 獲取背景信息失敗: {e}")
            return {
                "has_custom_background": False,
                "background_path": str(self.default_bg_path),
                "background_name": self.default_bg_path.name,
                "is_default": True,
                "file_exists": self.default_bg_path.exists(),
            }

    def validate_background_file(self, file_path: Union[str, Path]) -> bool:
        """
        驗證背景文件是否有效

        Args:
            file_path: 文件路徑

        Returns:
            是否有效
        """
        try:
            file_path = Path(file_path)

            # 檢查文件是否存在
            if not file_path.exists():
                return False

            # 檢查文件大小（限制為10MB）
            if file_path.stat().st_size > 10 * 1024 * 1024:
                return False

            # 檢查文件擴展名
            valid_extensions = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
            if file_path.suffix.lower() not in valid_extensions:
                return False

            return True

        except Exception as e:
            logger.error(f"[背景管理器] 驗證背景文件失敗: {e}")
            return False

    def get_available_backgrounds(self) -> list:
        """
        獲取所有可用的背景文件

        Returns:
            背景文件列表
        """
        try:
            backgrounds = []

            # 添加默認背景
            if self.default_bg_path.exists():
                backgrounds.append(
                    {
                        "name": "默認背景",
                        "path": str(self.default_bg_path),
                        "type": "default",
                    }
                )

            # 添加用戶自定義背景
            for bg_file in self.user_bg_dir.glob("*_bg.png"):
                user_id = bg_file.stem.replace("_bg", "")
                backgrounds.append(
                    {
                        "name": f"用戶 {user_id} 背景",
                        "path": str(bg_file),
                        "type": "custom",
                        "user_id": user_id,
                    }
                )

            return backgrounds

        except Exception as e:
            logger.error(f"[背景管理器] 獲取可用背景失敗: {e}")
            return []


# 創建全局背景管理器實例
background_manager = BackgroundManager()
