"""
付費機制管理器
"""

import time
from typing import Any, Dict, Optional

from gsuid_core.logger import logger

from .redeem_code_manager import RedeemCodeManager
from ..wutheringwaves_config import WutheringWavesConfig
from .user_tier_manager import UserTier, UserTierManager


class PaymentManager:
    """付費機制管理器"""

    def __init__(self):
        # 延遲導入以避免循環依賴
        self.user_tier_manager = UserTierManager()
        self.redeem_code_manager = RedeemCodeManager()

    def _get_config(self):
        from ..wutheringwaves_config import WutheringWavesConfig

        return WutheringWavesConfig

    def is_payment_system_enabled(self) -> bool:
        """
        檢查付費系統是否啟用

        Returns:
            是否啟用
        """
        return self._get_config().get_config("PaymentSystemEnabled").data

    def get_user_tier(self, user_id: str) -> str:
        """
        獲取用戶等級

        Args:
            user_id: 用戶ID

        Returns:
            用戶等級
        """
        return self.user_tier_manager.get_user_tier(user_id)

    def is_premium_user(self, user_id: str) -> bool:
        """
        檢查是否為Premium用戶

        Args:
            user_id: 用戶ID

        Returns:
            是否為Premium用戶
        """
        return self.user_tier_manager.is_premium_user(user_id)

    def get_cooldown_time(self, user_id: str, cooldown_type: str) -> int:
        """
        獲取用戶冷卻時間

        Args:
            user_id: 用戶ID
            cooldown_type: 冷卻類型 (analyze/query/parse/ocr)

        Returns:
            冷卻時間（秒）
        """
        # Premium用戶無冷卻限制
        if self.is_premium_user(user_id):
            return 0

        # 一般用戶使用配置的冷卻時間
        config_key = f"DefaultCooldown{cooldown_type.capitalize()}"
        return self._get_config().get_config(config_key).data

    def get_max_bind_num(self, user_id: str) -> int:
        """
        獲取用戶最大綁定UID數量

        Args:
            user_id: 用戶ID

        Returns:
            最大綁定數量
        """
        # Premium用戶無限制
        if self.is_premium_user(user_id):
            return 999  # 設置一個很大的數字表示無限制

        # 一般用戶使用配置的限制
        return self._get_config().get_config("DefaultMaxBindNum").data

    def can_use_feature(self, user_id: str, feature: str) -> tuple[bool, str]:
        """
        檢查用戶是否可以使用某功能

        Args:
            user_id: 用戶ID
            feature: 功能名稱

        Returns:
            (是否可以使用, 原因)
        """
        # 如果付費系統未啟用，所有用戶都可以使用所有功能
        if not self.is_payment_system_enabled():
            return True, ""

        user_tier = self.get_user_tier(user_id)

        # Premium用戶可以使用所有功能
        if user_tier == UserTier.PREMIUM:
            return True, ""

        # 一般用戶功能限制
        if feature == "custom_panel":
            return False, "自定義面板圖功能需要Premium會員"
        elif feature == "custom_daily":
            return False, "自定義每日圖角色功能需要Premium會員"
        elif feature == "custom_push_channel":
            return False, "自定義推送體力通知頻道功能需要Premium會員"
        elif feature == "unlimited_parse":
            return False, "無限制解析系統功能需要Premium會員"
        elif feature == "pro_ocr":
            return False, "OCR PRO線路功能需要Premium會員"

        # 其他功能一般用戶可以使用
        return True, ""

    def get_premium_price(self) -> int:
        """
        獲取Premium價格

        Returns:
            價格（台幣）
        """
        return self._get_config().get_config("PremiumPrice").data

    def get_user_limits_info(self, user_id: str) -> Dict[str, Any]:
        """
        獲取用戶限制信息

        Args:
            user_id: 用戶ID

        Returns:
            限制信息字典
        """
        user_tier = self.get_user_tier(user_id)
        is_premium = user_tier == UserTier.PREMIUM

        info = {
            "tier": user_tier,
            "is_premium": is_premium,
            "cooldowns": {
                "analyze": self.get_cooldown_time(user_id, "analyze"),
                "query": self.get_cooldown_time(user_id, "query"),
                "parse": self.get_cooldown_time(user_id, "parse"),
                "ocr": self.get_cooldown_time(user_id, "ocr"),
            },
            "max_bind_num": self.get_max_bind_num(user_id),
            "features": {
                "custom_panel": is_premium,
                "custom_daily": is_premium,
                "custom_push_channel": is_premium,
                "unlimited_parse": is_premium,
                "pro_ocr": is_premium,
                "unlimited_cooldown": is_premium,
                "unlimited_bind": is_premium,
            },
        }

        # 如果是Premium用戶，添加到期時間信息
        if is_premium:
            expire_time = self.user_tier_manager.get_premium_expire_time(user_id)
            if expire_time:
                info["expire_time"] = expire_time
                info["expire_date"] = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(expire_time)
                )
            else:
                info["expire_time"] = None
                info["expire_date"] = "永久"

        return info

    def create_redeem_code(
        self, duration_seconds: int = 1, target_user_id: Optional[str] = None
    ) -> str:
        """
        創建兌換碼

        Args:
            duration_seconds: Premium持續時間（秒）
            target_user_id: 指定用戶ID

        Returns:
            兌換碼
        """
        # 將秒數轉換為月數（用於兼容性）
        months = max(1, duration_seconds // (30 * 24 * 3600))  # 至少1個月
        return self.redeem_code_manager.create_redeem_code(months, target_user_id)

    def use_redeem_code(self, code: str, user_id: str) -> tuple[bool, str]:
        """
        使用兌換碼

        Args:
            code: 兌換碼
            user_id: 用戶ID

        Returns:
            (是否成功, 消息)
        """
        return self.redeem_code_manager.use_redeem_code(code, user_id)

    def add_premium_user(self, user_id: str, months: Optional[int] = None) -> bool:
        """
        添加Premium用戶

        Args:
            user_id: 用戶ID
            months: 月數，None表示永久

        Returns:
            是否成功
        """
        return self.user_tier_manager.add_premium_user(user_id, months)

    def remove_premium_user(self, user_id: str) -> bool:
        """
        移除Premium用戶

        Args:
            user_id: 用戶ID

        Returns:
            是否成功
        """
        return self.user_tier_manager.remove_premium_user(user_id)

    def get_premium_users_list(self) -> Dict[str, Dict[str, Any]]:
        """
        獲取Premium用戶列表

        Returns:
            Premium用戶字典
        """
        return self.user_tier_manager.list_premium_users()

    def get_redeem_codes_list(self, show_used: bool = False) -> list:
        """
        獲取兌換碼列表

        Args:
            show_used: 是否顯示已使用的兌換碼

        Returns:
            兌換碼列表
        """
        return self.redeem_code_manager.list_redeem_codes(show_used)

    def clean_expired_data(self) -> Dict[str, int]:
        """
        清理過期數據

        Returns:
            清理結果統計
        """
        premium_cleaned = self.user_tier_manager.clean_expired_users()
        codes_cleaned = self.redeem_code_manager.clean_expired_codes()

        return {"premium_users": premium_cleaned, "redeem_codes": codes_cleaned}


# 創建全局付費機制管理器實例
payment_manager = PaymentManager()
