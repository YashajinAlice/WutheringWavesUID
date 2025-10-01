"""
Premium用戶綁定賬號管理器
"""

import time
from typing import Dict, List, Tuple, Optional

from gsuid_core.logger import logger

from .payment_manager import payment_manager
from ..utils.database.models import WavesBind, WavesUser


class PremiumBindManager:
    """Premium用戶綁定賬號管理器"""

    def __init__(self):
        self.max_bind_num_premium = 10  # Premium用戶最大綁定數量

    def get_user_bind_limit(self, user_id: str) -> int:
        """
        獲取用戶綁定限制

        Args:
            user_id: 用戶ID

        Returns:
            最大綁定數量
        """
        try:
            if payment_manager.is_premium_user(user_id):
                return self.max_bind_num_premium
            else:
                return payment_manager.get_max_bind_num(user_id)
        except Exception as e:
            logger.error(f"[鳴潮] 獲取綁定限制失敗: {e}")
            return 1  # 默認限制

    async def get_user_bind_count(self, user_id: str, bot_id: str) -> int:
        """
        獲取用戶當前綁定數量

        Args:
            user_id: 用戶ID
            bot_id: 機器人ID

        Returns:
            當前綁定數量
        """
        try:
            binds = await WavesBind.get_all_bind_by_game(user_id, bot_id)
            return len(binds) if binds else 0
        except Exception as e:
            logger.error(f"[鳴潮] 獲取綁定數量失敗: {e}")
            return 0

    async def can_bind_more(self, user_id: str, bot_id: str) -> Tuple[bool, str]:
        """
        檢查用戶是否可以綁定更多賬號

        Args:
            user_id: 用戶ID
            bot_id: 機器人ID

        Returns:
            (是否可以綁定, 提示信息)
        """
        try:
            current_count = await self.get_user_bind_count(user_id, bot_id)
            max_count = self.get_user_bind_limit(user_id)

            if current_count >= max_count:
                if payment_manager.is_premium_user(user_id):
                    return False, f"已達到Premium用戶綁定上限（{max_count}個）"
                else:
                    return (
                        False,
                        f"已達到綁定上限（{max_count}個），升級Premium可綁定更多賬號！",
                    )

            return True, ""

        except Exception as e:
            logger.error(f"[鳴潮] 檢查綁定限制失敗: {e}")
            return False, "檢查綁定限制失敗"

    async def get_bind_status_info(self, user_id: str, bot_id: str) -> Dict:
        """
        獲取用戶綁定狀態信息

        Args:
            user_id: 用戶ID
            bot_id: 機器人ID

        Returns:
            綁定狀態信息
        """
        try:
            current_count = await self.get_user_bind_count(user_id, bot_id)
            max_count = self.get_user_bind_limit(user_id)
            is_premium = payment_manager.is_premium_user(user_id)

            return {
                "current_count": current_count,
                "max_count": max_count,
                "is_premium": is_premium,
                "remaining": max_count - current_count,
                "user_tier": "Premium用戶" if is_premium else "一般用戶",
            }

        except Exception as e:
            logger.error(f"[鳴潮] 獲取綁定狀態失敗: {e}")
            return {
                "current_count": 0,
                "max_count": 1,
                "is_premium": False,
                "remaining": 1,
                "user_tier": "一般用戶",
            }

    async def get_bind_list(self, user_id: str, bot_id: str) -> List[Dict]:
        """
        獲取用戶綁定列表

        Args:
            user_id: 用戶ID
            bot_id: 機器人ID

        Returns:
            綁定列表
        """
        try:
            binds = await WavesBind.get_all_bind_by_game(user_id, bot_id)
            if not binds:
                return []

            bind_list = []
            for bind in binds:
                bind_info = {
                    "uid": bind.uid,
                    "bind_time": bind.bind_time,
                    "is_active": True,
                }
                bind_list.append(bind_info)

            return bind_list

        except Exception as e:
            logger.error(f"[鳴潮] 獲取綁定列表失敗: {e}")
            return []

    def format_bind_info(self, bind_info: Dict) -> str:
        """
        格式化綁定信息顯示

        Args:
            bind_info: 綁定信息

        Returns:
            格式化的字符串
        """
        try:
            bind_time = bind_info.get("bind_time", 0)
            if bind_time:
                time_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(bind_time))
            else:
                time_str = "未知"

            return f"UID: {bind_info.get('uid', 'N/A')} (綁定時間: {time_str})"

        except Exception as e:
            logger.error(f"[鳴潮] 格式化綁定信息失敗: {e}")
            return f"UID: {bind_info.get('uid', 'N/A')}"


# 創建全局Premium綁定管理器實例
premium_bind_manager = PremiumBindManager()
