"""
增強版冷卻管理器 - 支持付費機制
"""

import time
from typing import Dict, Tuple, Optional

from gsuid_core.logger import logger


class EnhancedCooldownManager:
    """增強版冷卻管理器 - 支持付費機制"""

    def __init__(self, cooldown_type: str = "analyze"):
        """
        初始化冷卻管理器

        Args:
            cooldown_type: 冷卻類型 (analyze/query/parse)
        """
        self.cooldown_type = cooldown_type
        # 存儲用戶冷卻時間 {user_id: last_success_time}
        self._cooldowns: Dict[str, float] = {}
        # 存儲用戶失敗次數 {user_id: failure_count}
        self._failures: Dict[str, int] = {}

    def _get_cooldown_duration(self, user_id: str) -> int:
        """
        獲取用戶的冷卻時間

        Args:
            user_id: 用戶ID

        Returns:
            冷卻時間（秒）
        """
        try:
            # 嘗試導入付費管理器
            from ..wutheringwaves_payment.payment_manager import (
                payment_manager,
            )

            # 如果付費系統啟用，使用付費管理器的冷卻時間
            if payment_manager.is_payment_system_enabled():
                return payment_manager.get_cooldown_time(user_id, self.cooldown_type)

        except ImportError:
            # 如果付費模組未安裝，使用默認值
            pass
        except Exception as e:
            logger.error(f"[冷卻系統] 獲取冷卻時間失敗: {e}")

        # 默認冷卻時間
        default_cooldowns = {
            "analyze": 300,  # 5分鐘
            "query": 180,  # 3分鐘
            "parse": 180,  # 3分鐘
            "ocr": 300,  # 5分鐘
        }
        return default_cooldowns.get(self.cooldown_type, 300)

    def _is_premium_user(self, user_id: str) -> bool:
        """
        檢查是否為Premium用戶

        Args:
            user_id: 用戶ID

        Returns:
            是否為Premium用戶
        """
        try:
            # 嘗試導入付費管理器
            from ..wutheringwaves_payment.payment_manager import (
                payment_manager,
            )

            # 如果付費系統啟用，檢查Premium狀態
            if payment_manager.is_payment_system_enabled():
                return payment_manager.is_premium_user(user_id)

        except ImportError:
            # 如果付費模組未安裝，檢查舊的訂閱系統
            pass
        except Exception as e:
            logger.error(f"[冷卻系統] 檢查Premium用戶失敗: {e}")

        # 回退到舊的訂閱系統
        return self._is_legacy_subscriber(user_id)

    def _is_legacy_subscriber(self, user_id: str) -> bool:
        """
        檢查是否為舊版訂閱用戶（向後兼容）

        Args:
            user_id: 用戶ID

        Returns:
            是否為訂閱用戶
        """
        try:
            from ..wutheringwaves_config import WutheringWavesConfig

            subscribers = WutheringWavesConfig.get_config(
                "AnalyzeCooldownSubscribers"
            ).data

            # 兼容舊格式（列表）
            if isinstance(subscribers, list):
                return user_id in subscribers

            # 新格式（字典）
            if not isinstance(subscribers, dict):
                return False

            if user_id not in subscribers:
                return False

            user_info = subscribers[user_id]

            # 永久訂閱
            if user_info.get("permanent", False):
                return True

            # 限時訂閱
            expire_time = user_info.get("expire_time", 0)
            if expire_time > time.time():
                return True

            # 已過期
            return False

        except Exception as e:
            logger.error(f"[冷卻系統] 檢查舊版訂閱用戶失敗: {e}")
            return False

    def can_use(self, user_id: str) -> Tuple[bool, Optional[float]]:
        """
        檢查用戶是否可以使用功能

        Args:
            user_id: 用戶ID

        Returns:
            (是否可以使用, 剩餘冷卻時間)
        """
        # Premium用戶無冷卻限制
        if self._is_premium_user(user_id):
            logger.debug(f"[冷卻系統] Premium用戶 {user_id} 無視冷卻")
            return True, None

        current_time = time.time()
        cooldown_duration = self._get_cooldown_duration(user_id)

        if user_id not in self._cooldowns:
            return True, None

        last_use_time = self._cooldowns[user_id]
        elapsed_time = current_time - last_use_time

        if elapsed_time >= cooldown_duration:
            return True, None
        else:
            remaining_time = cooldown_duration - elapsed_time
            return False, remaining_time

    def mark_success(self, user_id: str):
        """
        標記用戶成功使用功能（開始冷卻）

        Args:
            user_id: 用戶ID
        """
        current_time = time.time()
        self._cooldowns[user_id] = current_time

        # 重置失敗計數
        if user_id in self._failures:
            del self._failures[user_id]

        cooldown_duration = self._get_cooldown_duration(user_id)
        logger.debug(
            f"[冷卻系統] 用戶 {user_id} 成功使用{self.cooldown_type}功能，開始冷卻 {cooldown_duration} 秒"
        )

    def mark_failure(self, user_id: str):
        """
        標記用戶使用失敗（不開始冷卻）

        Args:
            user_id: 用戶ID
        """
        # 增加失敗計數
        self._failures[user_id] = self._failures.get(user_id, 0) + 1

        logger.debug(
            f"[冷卻系統] 用戶 {user_id} 使用{self.cooldown_type}功能失敗，不開始冷卻（失敗次數：{self._failures[user_id]}）"
        )

    def get_remaining_time(self, user_id: str) -> Optional[float]:
        """
        獲取用戶剩餘冷卻時間

        Args:
            user_id: 用戶ID

        Returns:
            剩餘冷卻時間（秒），如果沒有冷卻則返回 None
        """
        # Premium用戶無冷卻限制
        if self._is_premium_user(user_id):
            return None

        current_time = time.time()
        cooldown_duration = self._get_cooldown_duration(user_id)

        if user_id not in self._cooldowns:
            return None

        last_use_time = self._cooldowns[user_id]
        elapsed_time = current_time - last_use_time

        if elapsed_time >= cooldown_duration:
            return None
        else:
            return cooldown_duration - elapsed_time

    def clear_cooldown(self, user_id: str):
        """
        清除用戶冷卻時間

        Args:
            user_id: 用戶ID
        """
        if user_id in self._cooldowns:
            del self._cooldowns[user_id]
            logger.debug(
                f"[冷卻系統] 清除用戶 {user_id} 的{self.cooldown_type}冷卻時間"
            )

    def get_cooldown_message(self, user_id: str) -> str:
        """
        獲取冷卻提示消息

        Args:
            user_id: 用戶ID

        Returns:
            冷卻提示消息
        """
        remaining_time = self.get_remaining_time(user_id)
        if remaining_time is None:
            return ""

        remaining_seconds = int(remaining_time)
        cooldown_type_names = {"analyze": "分析", "query": "查詢", "parse": "解析"}
        type_name = cooldown_type_names.get(self.cooldown_type, "功能")

        return f"⏰ {type_name}功能冷卻中，請等待 {remaining_seconds} 秒後再試"

    def get_failure_count(self, user_id: str) -> int:
        """
        獲取用戶失敗次數

        Args:
            user_id: 用戶ID

        Returns:
            失敗次數
        """
        return self._failures.get(user_id, 0)

    def reset_failure_count(self, user_id: str):
        """
        重置用戶失敗次數

        Args:
            user_id: 用戶ID
        """
        if user_id in self._failures:
            del self._failures[user_id]
            logger.debug(
                f"[冷卻系統] 重置用戶 {user_id} 的{self.cooldown_type}失敗次數"
            )


# 創建全局冷卻管理器實例
analyze_cooldown_manager = EnhancedCooldownManager("analyze")
query_cooldown_manager = EnhancedCooldownManager("query")
parse_cooldown_manager = EnhancedCooldownManager("parse")
ocr_cooldown_manager = EnhancedCooldownManager("ocr")
