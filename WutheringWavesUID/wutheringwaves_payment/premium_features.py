"""
Premium專屬功能管理器
"""

import time
from typing import Any, Dict, List, Optional

from gsuid_core.logger import logger

from .user_tier_manager import UserTier
from .payment_manager import payment_manager


class PremiumFeatures:
    """Premium專屬功能管理器"""

    def __init__(self):
        self.payment_manager = payment_manager

    def check_premium_access(self, user_id: str, feature: str) -> tuple[bool, str]:
        """
        檢查用戶是否有權限使用Premium功能

        Args:
            user_id: 用戶ID
            feature: 功能名稱

        Returns:
            (是否有權限, 錯誤消息)
        """
        # 如果付費系統未啟用，所有用戶都可以使用所有功能
        if not self.payment_manager.is_payment_system_enabled():
            return True, ""

        # 檢查是否為Premium用戶
        if not self.payment_manager.is_premium_user(user_id):
            feature_names = {
                "custom_panel": "自定義面板圖",
                "custom_daily": "自定義每日圖角色",
                "custom_push_channel": "自定義推送體力通知頻道",
                "unlimited_parse": "無限制解析系統",
                "pro_ocr": "OCR PRO線路",
                "unlimited_cooldown": "無冷卻限制",
                "unlimited_bind": "無限制UID綁定",
            }

            feature_name = feature_names.get(feature, feature)
            price = self.payment_manager.get_premium_price()

            return False, (
                f"❌ {feature_name}功能需要Premium會員！\n"
                f"💎 升級Premium會員享受更多功能\n"
                f"💰 價格：{price} 台幣/月\n"
                f"📞 如需購買請聯繫管理員"
            )

        return True, ""

    def get_custom_panel_options(self, user_id: str) -> List[str]:
        """
        獲取自定義面板選項（Premium專屬）

        Args:
            user_id: 用戶ID

        Returns:
            面板選項列表
        """
        has_access, error_msg = self.check_premium_access(user_id, "custom_panel")
        if not has_access:
            return []

        # 返回Premium用戶可用的自定義面板選項
        return [
            "經典面板",
            "暗黑面板",
            "彩色面板",
            "簡約面板",
            "動態面板",
            "自定義背景",
            "自定義URL背景",
        ]

    def get_custom_daily_options(self, user_id: str) -> List[str]:
        """
        獲取自定義每日圖角色選項（Premium專屬）

        Args:
            user_id: 用戶ID

        Returns:
            角色選項列表
        """
        has_access, error_msg = self.check_premium_access(user_id, "custom_daily")
        if not has_access:
            return []

        # 這裡可以返回Premium用戶可用的自定義角色選項
        return ["暗主", "白芷", "秧秧", "桃祈", "維里奈", "卡卡羅", "忌炎", "凌陽"]

    def get_custom_push_channel_options(self, user_id: str) -> List[str]:
        """
        獲取自定義推送頻道選項（Premium專屬）

        Args:
            user_id: 用戶ID

        Returns:
            頻道選項列表
        """
        has_access, error_msg = self.check_premium_access(
            user_id, "custom_push_channel"
        )
        if not has_access:
            return []

        # 這裡可以返回Premium用戶可用的自定義推送頻道選項
        return ["默認頻道", "私人頻道", "群組頻道", "自定義頻道"]

    def set_custom_panel(self, user_id: str, panel_type: str) -> tuple[bool, str]:
        """
        設置自定義面板（Premium專屬）

        Args:
            user_id: 用戶ID
            panel_type: 面板類型

        Returns:
            (是否成功, 消息)
        """
        has_access, error_msg = self.check_premium_access(user_id, "custom_panel")
        if not has_access:
            return False, error_msg

        # 檢查是否為自定義背景類型
        if panel_type in ["自定義背景", "自定義URL背景"]:
            return (
                False,
                f"❌ 請使用專門的指令設置{panel_type}：\n• 設置背景圖片 [圖片] - 設置自定義背景圖片\n• 設置背景URL [URL] - 設置自定義背景URL",
            )

        # 這裡可以實現實際的面板設置邏輯
        # 例如保存到數據庫或配置文件
        logger.info(f"[Premium功能] 用戶 {user_id} 設置自定義面板: {panel_type}")
        return True, f"✅ 已設置自定義面板為：{panel_type}"

    def set_custom_background(
        self, user_id: str, background_data: str
    ) -> tuple[bool, str]:
        """
        設置自定義背景圖片（Premium專屬）

        Args:
            user_id: 用戶ID
            background_data: 背景圖片數據（base64或文件路徑）

        Returns:
            (是否成功, 消息)
        """
        has_access, error_msg = self.check_premium_access(user_id, "custom_panel")
        if not has_access:
            return False, error_msg

        try:
            # 這裡可以實現實際的背景圖片保存邏輯
            # 例如保存到用戶專屬目錄或數據庫
            import os
            from pathlib import Path

            # 創建用戶專屬背景目錄
            user_bg_dir = Path("WutheringWavesUID/utils/texture2d/user_backgrounds")
            user_bg_dir.mkdir(parents=True, exist_ok=True)

            # 保存背景圖片
            bg_file = user_bg_dir / f"{user_id}_bg.png"

            # 如果是base64數據，解碼並保存
            if background_data.startswith("data:image"):
                import base64

                # 移除data:image/png;base64,前綴
                base64_data = background_data.split(",")[1]
                with open(bg_file, "wb") as f:
                    f.write(base64.b64decode(base64_data))
            else:
                # 假設是文件路徑，複製文件
                import shutil

                shutil.copy2(background_data, bg_file)

            logger.info(f"[Premium功能] 用戶 {user_id} 設置自定義背景圖片: {bg_file}")
            return True, f"✅ 已設置自定義背景圖片！\n📁 背景文件：{bg_file.name}"

        except Exception as e:
            logger.error(f"[Premium功能] 設置自定義背景失敗: {e}")
            return False, f"❌ 設置自定義背景失敗：{str(e)}"

    async def set_custom_background_url(
        self, user_id: str, background_url: str
    ) -> tuple[bool, str]:
        """
        設置自定義背景URL（Premium專屬）

        Args:
            user_id: 用戶ID
            background_url: 背景圖片URL

        Returns:
            (是否成功, 消息)
        """
        has_access, error_msg = self.check_premium_access(user_id, "custom_panel")
        if not has_access:
            return False, error_msg

        try:
            # 驗證URL格式
            import re

            url_pattern = re.compile(
                r"^https?://"  # http:// or https://
                r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
                r"localhost|"  # localhost...
                r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
                r"(?::\d+)?"  # optional port
                r"(?:/?|[/?]\S+)$",
                re.IGNORECASE,
            )

            if not url_pattern.match(background_url):
                return False, "❌ 請提供有效的圖片URL！"

            # 下載並保存背景圖片
            import os
            from pathlib import Path

            # 創建用戶專屬背景目錄
            user_bg_dir = Path("WutheringWavesUID/utils/texture2d/user_backgrounds")
            user_bg_dir.mkdir(parents=True, exist_ok=True)

            # 使用現有的下載工具
            try:
                from gsuid_core.utils.download_resource.download_file import (
                    download,
                )

                # 下載圖片
                bg_file = user_bg_dir / f"{user_id}_bg.png"
                result = await download(
                    background_url,
                    user_bg_dir,
                    f"{user_id}_bg.png",
                    tag="[Premium背景]",
                )

                # 檢查下載結果
                if not isinstance(result, int) or result != 200:
                    if result == 404:
                        # 檢查是否為Discord URL
                        if "cdn.discordapp.com" in background_url:
                            return False, (
                                "❌ Discord圖片URL已過期！\n"
                                "🔧 Discord圖片鏈接會自動過期，請嘗試：\n"
                                "1. 📎 **直接發送圖片文件**（推薦）\n"
                                "2. 🔗 使用其他圖片分享服務：\n"
                                "   • Imgur: https://imgur.com/\n"
                                "   • ImgBB: https://imgbb.com/\n"
                                "   • Postimg: https://postimg.cc/\n"
                                "3. 📤 重新上傳圖片到Discord獲取新鏈接"
                            )
                        else:
                            return False, (
                                "❌ 圖片URL已過期或無效！\n"
                                "💡 建議解決方案：\n"
                                "1. 直接發送圖片文件\n"
                                "2. 使用其他圖片分享服務（如imgur、imgbb等）\n"
                                "3. 檢查URL是否正確"
                            )
                    else:
                        return False, f"❌ 下載圖片失敗！HTTP狀態碼：{result}"

                # 檢查文件大小（限制為10MB）
                if bg_file.exists() and bg_file.stat().st_size > 10 * 1024 * 1024:
                    bg_file.unlink()  # 刪除過大文件
                    return False, "❌ 圖片文件過大！最大支持10MB。"

                # 驗證圖片文件
                from PIL import Image

                try:
                    img = Image.open(bg_file)
                    img.verify()  # 驗證圖片完整性
                except Exception:
                    bg_file.unlink()  # 刪除無效文件
                    return False, "❌ 下載的圖片文件無效！"

                logger.info(
                    f"[Premium功能] 用戶 {user_id} 設置自定義背景URL: {background_url}"
                )
                return (
                    True,
                    f"✅ 已設置自定義背景圖片！\n🔗 來源URL：{background_url}\n📁 文件：{bg_file.name}",
                )

            except Exception as e:
                return False, f"❌ 下載圖片失敗：{str(e)}"

        except Exception as e:
            logger.error(f"[Premium功能] 設置自定義背景URL失敗: {e}")
            return False, f"❌ 設置自定義背景URL失敗：{str(e)}"

    def get_custom_background_info(self, user_id: str) -> Dict[str, Any]:
        """
        獲取用戶自定義背景信息

        Args:
            user_id: 用戶ID

        Returns:
            背景信息字典
        """
        has_access, _ = self.check_premium_access(user_id, "custom_panel")
        if not has_access:
            return {}

        try:
            from pathlib import Path

            # 檢查是否有自定義背景文件
            user_bg_dir = Path("WutheringWavesUID/utils/texture2d/user_backgrounds")
            bg_file = user_bg_dir / f"{user_id}_bg.png"

            background_info = {
                "has_custom_bg": bg_file.exists(),
                "bg_file_path": str(bg_file) if bg_file.exists() else None,
                "bg_file_name": bg_file.name if bg_file.exists() else None,
            }

            return background_info

        except Exception as e:
            logger.error(f"[Premium功能] 獲取自定義背景信息失敗: {e}")
            return {}

    def set_custom_daily_character(
        self, user_id: str, character: str
    ) -> tuple[bool, str]:
        """
        設置自定義每日圖角色（Premium專屬）

        Args:
            user_id: 用戶ID
            character: 角色名稱

        Returns:
            (是否成功, 消息)
        """
        has_access, error_msg = self.check_premium_access(user_id, "custom_daily")
        if not has_access:
            return False, error_msg

        # 這裡可以實現實際的角色設置邏輯
        logger.info(f"[Premium功能] 用戶 {user_id} 設置自定義每日圖角色: {character}")
        return True, f"✅ 已設置自定義每日圖角色為：{character}"

    def set_custom_push_channel(self, user_id: str, channel: str) -> tuple[bool, str]:
        """
        設置自定義推送頻道（Premium專屬）

        Args:
            user_id: 用戶ID
            channel: 頻道名稱

        Returns:
            (是否成功, 消息)
        """
        has_access, error_msg = self.check_premium_access(
            user_id, "custom_push_channel"
        )
        if not has_access:
            return False, error_msg

        # 這裡可以實現實際的頻道設置邏輯
        logger.info(f"[Premium功能] 用戶 {user_id} 設置自定義推送頻道: {channel}")
        return True, f"✅ 已設置自定義推送頻道為：{channel}"

    def get_premium_user_settings(self, user_id: str) -> Dict[str, Any]:
        """
        獲取Premium用戶設置

        Args:
            user_id: 用戶ID

        Returns:
            用戶設置字典
        """
        has_access, _ = self.check_premium_access(user_id, "custom_panel")
        if not has_access:
            return {}

        # 這裡可以從數據庫或配置文件讀取用戶的Premium設置
        # 目前返回默認值
        return {
            "custom_panel": "經典面板",
            "custom_daily_character": "暗主",
            "custom_push_channel": "默認頻道",
            "pro_ocr_enabled": True,
            "unlimited_parse_enabled": True,
        }

    def update_premium_user_settings(
        self, user_id: str, settings: Dict[str, Any]
    ) -> tuple[bool, str]:
        """
        更新Premium用戶設置

        Args:
            user_id: 用戶ID
            settings: 設置字典

        Returns:
            (是否成功, 消息)
        """
        has_access, error_msg = self.check_premium_access(user_id, "custom_panel")
        if not has_access:
            return False, error_msg

        # 這裡可以實現實際的設置更新邏輯
        # 例如保存到數據庫或配置文件
        logger.info(f"[Premium功能] 用戶 {user_id} 更新設置: {settings}")
        return True, "✅ Premium設置已更新"

    def get_premium_feature_status(self, user_id: str) -> Dict[str, bool]:
        """
        獲取Premium功能狀態

        Args:
            user_id: 用戶ID

        Returns:
            功能狀態字典
        """
        is_premium = self.payment_manager.is_premium_user(user_id)

        return {
            "custom_panel": is_premium,
            "custom_daily": is_premium,
            "custom_push_channel": is_premium,
            "unlimited_parse": is_premium,
            "pro_ocr": is_premium,
            "unlimited_cooldown": is_premium,
            "unlimited_bind": is_premium,
        }


# 創建全局Premium功能管理器實例
premium_features = PremiumFeatures()
