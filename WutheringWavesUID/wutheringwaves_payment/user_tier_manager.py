"""
用戶等級管理系統
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from gsuid_core.logger import logger

from ..wutheringwaves_config import WutheringWavesConfig


class UserTier:
    """用戶等級枚舉"""

    FREE = "free"  # 一般用戶
    PREMIUM = "premium"  # Premium用戶


class UserTierManager:
    """用戶等級管理器"""

    def __init__(self):
        # 延遲導入以避免循環依賴
        self.data_dir = Path(__file__).parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        self.premium_users_file = self.data_dir / "premium_users.json"

    def _get_config(self):
        from ..wutheringwaves_config import WutheringWavesConfig

        return WutheringWavesConfig

    def _load_premium_users(self) -> Dict[str, Any]:
        """從JSON文件加載Premium用戶數據"""
        try:
            if not self.premium_users_file.exists():
                return {}
            with open(self.premium_users_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[用戶等級] 加載Premium用戶數據失敗: {e}")
            return {}

    def _save_premium_users(self, premium_users: Dict[str, Any]) -> bool:
        """保存Premium用戶數據到JSON文件"""
        try:
            with open(self.premium_users_file, "w", encoding="utf-8") as f:
                json.dump(premium_users, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"[用戶等級] 保存Premium用戶數據失敗: {e}")
            return False

    def is_premium_user(self, user_id: str) -> bool:
        """
        檢查用戶是否為Premium用戶

        Args:
            user_id: 用戶ID

        Returns:
            是否為Premium用戶
        """
        try:
            premium_users = self._load_premium_users()
            if not isinstance(premium_users, dict):
                return False

            if user_id not in premium_users:
                return False

            user_info = premium_users[user_id]

            # 永久Premium用戶
            if user_info.get("permanent", False):
                return True

            # 限時Premium用戶
            expire_time = user_info.get("expire_time", 0)
            if expire_time > time.time():
                return True

            # 已過期，自動清理
            self._remove_expired_user(user_id)
            return False

        except Exception as e:
            logger.error(f"[用戶等級] 檢查Premium用戶失敗: {e}")
            return False

    def get_user_tier(self, user_id: str) -> str:
        """
        獲取用戶等級

        Args:
            user_id: 用戶ID

        Returns:
            用戶等級 (free/premium)
        """
        return UserTier.PREMIUM if self.is_premium_user(user_id) else UserTier.FREE

    def add_premium_user(self, user_id: str, months: Optional[int] = None) -> bool:
        """
        添加Premium用戶

        Args:
            user_id: 用戶ID
            months: 月數，None表示永久

        Returns:
            是否成功
        """
        try:
            premium_users = self._load_premium_users()
            if not isinstance(premium_users, dict):
                premium_users = {}

            # 計算到期時間
            if months is None:
                # 永久Premium
                premium_users[user_id] = {
                    "permanent": True,
                    "expire_time": 0,
                    "added_time": time.time(),
                }
            else:
                # 限時Premium - 累加時間而不是覆蓋
                current_time = time.time()
                additional_seconds = months * 30 * 24 * 60 * 60  # 30天/月

                # 檢查用戶是否已經是Premium用戶
                if user_id in premium_users:
                    user_info = premium_users[user_id]

                    # 如果用戶是永久Premium，保持永久
                    if user_info.get("permanent", False):
                        premium_users[user_id] = {
                            "permanent": True,
                            "expire_time": 0,
                            "added_time": user_info.get("added_time", current_time),
                        }
                    else:
                        # 累加到現有時間
                        existing_expire_time = user_info.get(
                            "expire_time", current_time
                        )
                        # 如果現有時間已過期，從當前時間開始計算
                        if existing_expire_time < current_time:
                            new_expire_time = current_time + additional_seconds
                        else:
                            # 累加到現有到期時間
                            new_expire_time = existing_expire_time + additional_seconds

                        premium_users[user_id] = {
                            "permanent": False,
                            "expire_time": new_expire_time,
                            "added_time": user_info.get("added_time", current_time),
                        }
                else:
                    # 新用戶，直接設置到期時間
                    expire_time = current_time + additional_seconds
                    premium_users[user_id] = {
                        "permanent": False,
                        "expire_time": expire_time,
                        "added_time": current_time,
                    }

            # 保存到JSON文件
            if not self._save_premium_users(premium_users):
                return False

            logger.info(f"[用戶等級] 添加Premium用戶: {user_id}, 月數: {months}")
            return True

        except Exception as e:
            logger.error(f"[用戶等級] 添加Premium用戶失敗: {e}")
            return False

    def remove_premium_user(self, user_id: str) -> bool:
        """
        移除Premium用戶

        Args:
            user_id: 用戶ID

        Returns:
            是否成功
        """
        try:
            premium_users = self._load_premium_users()
            if not isinstance(premium_users, dict):
                return False

            if user_id in premium_users:
                del premium_users[user_id]
                # 保存到JSON文件
                if self._save_premium_users(premium_users):
                    logger.info(f"[用戶等級] 移除Premium用戶: {user_id}")
                    return True
                else:
                    return False

            return False

        except Exception as e:
            logger.error(f"[用戶等級] 移除Premium用戶失敗: {e}")
            return False

    def get_premium_expire_time(self, user_id: str) -> Optional[float]:
        """
        獲取Premium用戶到期時間

        Args:
            user_id: 用戶ID

        Returns:
            到期時間戳，永久用戶返回None
        """
        try:
            premium_users = self._load_premium_users()
            if not isinstance(premium_users, dict):
                return None

            if user_id not in premium_users:
                return None

            user_info = premium_users[user_id]
            if user_info.get("permanent", False):
                return None

            return user_info.get("expire_time", 0)

        except Exception as e:
            logger.error(f"[用戶等級] 獲取到期時間失敗: {e}")
            return None

    def get_premium_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取Premium用戶信息

        Args:
            user_id: 用戶ID

        Returns:
            用戶信息字典
        """
        try:
            premium_users = self._load_premium_users()
            if not isinstance(premium_users, dict):
                return None

            if user_id not in premium_users:
                return None

            return premium_users[user_id].copy()

        except Exception as e:
            logger.error(f"[用戶等級] 獲取Premium信息失敗: {e}")
            return None

    def list_premium_users(self) -> Dict[str, Dict[str, Any]]:
        """
        獲取所有Premium用戶列表

        Returns:
            Premium用戶字典
        """
        try:
            premium_users = self._load_premium_users()
            if not isinstance(premium_users, dict):
                return {}

            return premium_users.copy()

        except Exception as e:
            logger.error(f"[用戶等級] 獲取Premium用戶列表失敗: {e}")
            return {}

    def clean_expired_users(self) -> int:
        """
        清理過期的Premium用戶

        Returns:
            清理的用戶數量
        """
        try:
            premium_users = self._load_premium_users()
            if not isinstance(premium_users, dict):
                return 0

            current_time = time.time()
            expired_users = []
            active_users = {}

            for user_id, info in premium_users.items():
                if info.get("permanent", False):
                    # 永久用戶保留
                    active_users[user_id] = info
                else:
                    expire_time = info.get("expire_time", 0)
                    if expire_time > current_time:
                        # 未過期用戶保留
                        active_users[user_id] = info
                    else:
                        # 過期用戶記錄
                        expired_users.append(user_id)

            if expired_users:
                # 保存到JSON文件
                self._save_premium_users(active_users)
                logger.info(f"[用戶等級] 清理過期Premium用戶: {expired_users}")

            return len(expired_users)

        except Exception as e:
            logger.error(f"[用戶等級] 清理過期用戶失敗: {e}")
            return 0

    def _remove_expired_user(self, user_id: str):
        """內部方法：移除過期用戶"""
        try:
            premium_users = self._load_premium_users()
            if isinstance(premium_users, dict) and user_id in premium_users:
                del premium_users[user_id]
                # 保存到JSON文件
                self._save_premium_users(premium_users)
                logger.info(f"[用戶等級] 自動移除過期用戶: {user_id}")
        except Exception as e:
            logger.error(f"[用戶等級] 移除過期用戶失敗: {e}")

    def auto_cleanup_expired_users(self):
        """自動清理過期用戶（可在定時任務中調用）"""
        try:
            cleaned_count = self.clean_expired_users()
            if cleaned_count > 0:
                logger.info(f"[用戶等級] 自動清理了 {cleaned_count} 個過期Premium用戶")
            return cleaned_count
        except Exception as e:
            logger.error(f"[用戶等級] 自動清理過期用戶失敗: {e}")
            return 0

    def get_premium_stats(self) -> Dict[str, Any]:
        """獲取Premium用戶統計信息"""
        try:
            premium_users = self._load_premium_users()
            if not isinstance(premium_users, dict):
                return {"total": 0, "permanent": 0, "temporary": 0, "expired": 0}

            current_time = time.time()
            total = len(premium_users)
            permanent = 0
            temporary = 0
            expired = 0

            for user_id, info in premium_users.items():
                if info.get("permanent", False):
                    permanent += 1
                else:
                    expire_time = info.get("expire_time", 0)
                    if expire_time > current_time:
                        temporary += 1
                    else:
                        expired += 1

            return {
                "total": total,
                "permanent": permanent,
                "temporary": temporary,
                "expired": expired,
            }
        except Exception as e:
            logger.error(f"[用戶等級] 獲取Premium統計失敗: {e}")
            return {"total": 0, "permanent": 0, "temporary": 0, "expired": 0}


# 創建全局用戶等級管理器實例
user_tier_manager = UserTierManager()
