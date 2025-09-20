import time
from typing import Dict, Optional

from gsuid_core.logger import logger


class CooldownManager:
    """冷卻管理器"""

    def __init__(self):
        # 存儲用戶冷卻時間 {user_id: last_success_time}
        self._cooldowns: Dict[str, float] = {}
        # 冷卻時間（秒）
        self.cooldown_duration = 25

    def can_use(
        self, user_id: str, is_subscriber: bool = False
    ) -> tuple[bool, Optional[float]]:
        """
        檢查用戶是否可以使用功能

        Args:
            user_id: 用戶ID
            is_subscriber: 是否為訂閱用戶

        Returns:
            (是否可以使用, 剩餘冷卻時間)
        """
        # 订阅用户无视冷却
        if is_subscriber:
            logger.debug(f"[冷却系统] 订阅用户 {user_id} 无视冷却")
            return True, None

        current_time = time.time()

        if user_id not in self._cooldowns:
            return True, None

        last_use_time = self._cooldowns[user_id]
        elapsed_time = current_time - last_use_time

        if elapsed_time >= self.cooldown_duration:
            return True, None
        else:
            remaining_time = self.cooldown_duration - elapsed_time
            return False, remaining_time

    def mark_success(self, user_id: str):
        """
        標記用戶成功使用功能（開始冷卻）

        Args:
            user_id: 用戶ID
        """
        current_time = time.time()
        self._cooldowns[user_id] = current_time
        logger.debug(
            f"[冷卻系統] 用戶 {user_id} 成功使用功能，開始冷卻 {self.cooldown_duration} 秒"
        )

    def mark_failure(self, user_id: str):
        """
        標記用戶使用失敗（不開始冷卻）

        Args:
            user_id: 用戶ID
        """
        logger.debug(f"[冷卻系統] 用戶 {user_id} 使用失敗，不開始冷卻")
        # 失敗不更新冷卻時間

    def get_remaining_time(self, user_id: str) -> Optional[float]:
        """
        獲取用戶剩餘冷卻時間

        Args:
            user_id: 用戶ID

        Returns:
            剩餘冷卻時間（秒），如果沒有冷卻則返回 None
        """
        current_time = time.time()

        if user_id not in self._cooldowns:
            return None

        last_use_time = self._cooldowns[user_id]
        elapsed_time = current_time - last_use_time

        if elapsed_time >= self.cooldown_duration:
            return None
        else:
            return self.cooldown_duration - elapsed_time

    def clear_cooldown(self, user_id: str):
        """
        清除用戶冷卻時間

        Args:
            user_id: 用戶ID
        """
        if user_id in self._cooldowns:
            del self._cooldowns[user_id]
            logger.debug(f"[冷卻系統] 清除用戶 {user_id} 的冷卻時間")

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
        return f"⏰ 分析功能冷卻中，請等待 {remaining_seconds} 秒後再試"

    def is_subscriber(self, user_id: str) -> bool:
        """
        檢查用戶是否為訂閱用戶

        Args:
            user_id: 用戶ID

        Returns:
            是否為訂閱用戶
        """
        try:
            import time

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
            logger.error(f"[冷却系统] 检查订阅用户失败: {e}")
            return False


# 创建全局冷却管理器实例
analyze_cooldown_manager = CooldownManager()
