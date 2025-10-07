"""
OCR管理器 - 根據用戶等級分配不同的OCR線路
"""

import logging
from typing import List, Tuple, Optional

from .payment_manager import payment_manager
from ..wutheringwaves_config import WutheringWavesConfig

logger = logging.getLogger(__name__)


class OCRManager:
    """OCR管理器 - 管理不同用戶等級的OCR線路"""

    def __init__(self):
        # 免費線路API keys列表
        self.free_keys = [
            "K87115869688957",  # 原始免費key
            "K81457457688957",
            "K82846373288957",
            "K82808869488957",
            "K82766743188957",
            "K88154355588957",
            "K85254905088957",
        ]
        self.current_free_key_index = 0  # 當前使用的免費key索引
        self.pro_keys = []  # PRO線路API keys

    def get_user_ocr_config(self, user_id: str) -> Tuple[str, int]:
        """
        根據用戶等級獲取OCR配置
        現在所有用戶都使用PRO線路，但免費用戶有冷卻限制

        Returns:
            Tuple[str, int]: (API_KEY, ENGINE_NUM)
        """
        try:
            # 所有用戶都使用PRO線路
            return self._get_pro_ocr_config()

        except Exception as e:
            logger.error(f"[鳴潮] OCR配置獲取失敗: {e}")
            # 發生錯誤時使用免費線路作為備用
            return self._get_free_ocr_config()

    def get_fallback_ocr_config(self) -> Tuple[str, int]:
        """
        獲取備用OCR配置，當主要配置失敗時使用
        """
        api_key_list = WutheringWavesConfig.get_config("OCRspaceApiKeyList").data

        if api_key_list:
            # 嘗試使用任何可用的key
            for key in api_key_list:
                if key and key.strip():
                    logger.info(f"[鳴潮] 使用備用key: {key[:10]}...")
                    # 根據key類型決定引擎
                    if key.startswith("K"):
                        return key, 2  # 免費key使用engine 2
                    else:
                        return key, 3  # PRO key使用engine 3

        # 切換到下一個免費key
        self._switch_to_next_free_key()
        current_key = self.free_keys[self.current_free_key_index]
        logger.info(
            f"[鳴潮] 使用備用免費key ({self.current_free_key_index + 1}/{len(self.free_keys)}): {current_key[:10]}..."
        )
        return current_key, 2

    def _switch_to_next_free_key(self):
        """切換到下一個免費key"""
        self.current_free_key_index = (self.current_free_key_index + 1) % len(
            self.free_keys
        )
        logger.info(f"[鳴潮] 切換到下一個免費key，索引: {self.current_free_key_index}")

    def get_available_free_keys(self) -> List[str]:
        """獲取所有可用的免費keys"""
        return self.free_keys.copy()

    def _get_free_ocr_config(self) -> Tuple[str, int]:
        """獲取免費線路配置"""
        # 首先嘗試使用配置的API keys中的免費key
        api_key_list = WutheringWavesConfig.get_config("OCRspaceApiKeyList").data

        if api_key_list:
            # 優先使用以K開頭的免費key
            for key in api_key_list:
                if key and key.startswith("K"):
                    logger.info(f"[鳴潮] 使用配置的免費key: {key[:10]}...")
                    return key, 2  # 免費key使用engine 2

        # 使用輪詢機制選擇免費key
        current_key = self.free_keys[self.current_free_key_index]
        logger.info(
            f"[鳴潮] 使用免費key ({self.current_free_key_index + 1}/{len(self.free_keys)}): {current_key[:10]}..."
        )
        return current_key, 2  # 免費線路使用engine 2

    def _get_pro_ocr_config(self) -> Tuple[str, int]:
        """獲取PRO線路配置"""
        # 從配置中獲取PRO API keys
        api_key_list = WutheringWavesConfig.get_config("OCRspaceApiKeyList").data

        if not api_key_list:
            logger.warning("[鳴潮] PRO OCR API keys未配置，使用免費線路")
            return self._get_free_ocr_config()

        # 優先使用以K開頭的免費key，如果沒有則使用第一個key
        for key in api_key_list:
            if key and key.startswith("K"):
                return key, 2  # 免費key使用engine 2

        # 如果沒有免費key，使用第一個key並設置為PRO模式
        if api_key_list:
            return api_key_list[0], 3  # PRO模式使用engine 3

        # 如果沒有配置任何key，使用默認免費key
        return self._get_free_ocr_config()

    def get_available_keys(self, user_id: str) -> List[str]:
        """
        獲取用戶可用的API keys列表

        Returns:
            List[str]: 可用的API keys
        """
        try:
            is_premium = payment_manager.is_premium_user(user_id)

            if is_premium:
                # Premium用戶可以使用所有配置的keys
                api_key_list = WutheringWavesConfig.get_config(
                    "OCRspaceApiKeyList"
                ).data
                if api_key_list:
                    return [key for key in api_key_list if key]
                else:
                    return self.free_keys.copy()
            else:
                # 一般用戶只能使用免費key
                return self.free_keys.copy()

        except Exception as e:
            logger.error(f"[鳴潮] 獲取可用keys失敗: {e}")
            return self.free_keys.copy()

    def get_engine_info(self, user_id: str) -> str:
        """
        獲取用戶的引擎信息

        Returns:
            str: 引擎描述
        """
        try:
            is_premium = payment_manager.is_premium_user(user_id)

            if is_premium:
                return "PRO線路 (高精度識別，無冷卻限制)"
            else:
                return "PRO線路 (高精度識別，330秒冷卻)"

        except Exception as e:
            logger.error(f"[鳴潮] 獲取引擎信息失敗: {e}")
            return "PRO線路 (高精度識別，330秒冷卻)"


# 創建全局OCR管理器實例
ocr_manager = OCRManager()
