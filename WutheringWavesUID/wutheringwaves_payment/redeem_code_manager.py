"""
兌換碼管理系統
"""

import os
import json
import time
import string
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

from gsuid_core.logger import logger


class RedeemCodeManager:
    """兌換碼管理器"""

    def __init__(self):
        self.code_length = 12  # 兌換碼長度
        self.expire_days = 3  # 兌換碼有效期（天）
        # 設置JSON文件路徑
        self.data_dir = Path(__file__).parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        self.redeem_codes_file = self.data_dir / "redeem_codes.json"

    def _load_redeem_codes(self) -> Dict[str, Any]:
        """
        從JSON文件加載兌換碼數據

        Returns:
            兌換碼數據字典
        """
        try:
            if not self.redeem_codes_file.exists():
                return {}

            with open(self.redeem_codes_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[兌換碼] 加載兌換碼數據失敗: {e}")
            return {}

    def _save_redeem_codes(self, redeem_codes: Dict[str, Any]) -> bool:
        """
        保存兌換碼數據到JSON文件

        Args:
            redeem_codes: 兌換碼數據字典

        Returns:
            是否保存成功
        """
        try:
            with open(self.redeem_codes_file, "w", encoding="utf-8") as f:
                json.dump(redeem_codes, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"[兌換碼] 保存兌換碼數據失敗: {e}")
            return False

    def generate_redeem_code(self) -> str:
        """
        生成兌換碼

        Returns:
            兌換碼字符串
        """
        # 使用大小寫字母和數字生成兌換碼
        characters = string.ascii_letters + string.digits
        code = "".join(secrets.choice(characters) for _ in range(self.code_length))
        return code

    def create_redeem_code(
        self, months: int = 1, target_user_id: Optional[str] = None
    ) -> str:
        """
        創建兌換碼

        Args:
            months: Premium月數
            target_user_id: 指定用戶ID（可選）

        Returns:
            生成的兌換碼
        """
        try:
            redeem_codes = self._load_redeem_codes()

            # 生成唯一兌換碼
            while True:
                code = self.generate_redeem_code()
                if code not in redeem_codes:
                    break

            # 計算到期時間
            expire_time = time.time() + (self.expire_days * 24 * 60 * 60)

            # 創建兌換碼信息
            redeem_codes[code] = {
                "months": months,
                "target_user_id": target_user_id,
                "created_time": time.time(),
                "expire_time": expire_time,
                "used": False,
                "used_by": None,
                "used_time": None,
                "unlimited": target_user_id is None,  # 不限數量（通用兌換碼）
                "use_count": 0,  # 使用次數
                "max_uses": (
                    999999 if target_user_id is None else 1
                ),  # 通用兌換碼不限次數，指定用戶只能1次
                "used_users": [],  # 已使用用戶列表
            }

            # 保存到JSON文件
            if not self._save_redeem_codes(redeem_codes):
                logger.error("[兌換碼] 保存兌換碼數據失敗")
                return ""

            logger.info(
                f"[兌換碼] 創建兌換碼: {code}, 月數: {months}, 目標用戶: {target_user_id}"
            )
            return code

        except Exception as e:
            logger.error(f"[兌換碼] 創建兌換碼失敗: {e}")
            return ""

    def use_redeem_code(self, code: str, user_id: str) -> tuple[bool, str]:
        """
        使用兌換碼

        Args:
            code: 兌換碼
            user_id: 使用用戶ID

        Returns:
            (是否成功, 消息)
        """
        try:
            redeem_codes = self._load_redeem_codes()

            if code not in redeem_codes:
                return False, "兌換碼不存在"

            code_info = redeem_codes[code]

            # 檢查用戶是否已經使用過此兌換碼
            used_users = code_info.get("used_users", [])
            if user_id in used_users:
                return False, "您已經領取過此兌換碼，無法重複領取"

            # 檢查是否過期
            current_time = time.time()
            if current_time > code_info.get("expire_time", 0):
                return False, "兌換碼已過期"

            # 檢查是否指定用戶
            target_user_id = code_info.get("target_user_id")
            if target_user_id and target_user_id != user_id:
                return False, "此兌換碼不適用於您的帳號"

            # 添加用戶到已使用列表
            used_users.append(user_id)
            code_info["used_users"] = used_users
            code_info["use_count"] = len(used_users)
            code_info["used_by"] = user_id  # 記錄最後使用用戶
            code_info["used_time"] = current_time

            # 保存到JSON文件
            if not self._save_redeem_codes(redeem_codes):
                return False, "兌換碼系統保存失敗"

            # 添加Premium用戶
            months = code_info.get("months", 1)
            from .user_tier_manager import user_tier_manager

            success = user_tier_manager.add_premium_user(user_id, months)

            if success:
                logger.info(f"[兌換碼] 用戶 {user_id} 成功使用兌換碼 {code}")
                return True, f"兌換成功！您已獲得 {months} 個月的Premium會員資格"
            else:
                # 如果添加Premium失敗，回滾兌換碼狀態
                code_info["used"] = False
                code_info["used_by"] = None
                code_info["used_time"] = None
                self._save_redeem_codes(redeem_codes)
                return False, "兌換失敗，請聯繫管理員"

        except Exception as e:
            logger.error(f"[兌換碼] 使用兌換碼失敗: {e}")
            return False, "兌換失敗，請稍後再試"

    def get_redeem_code_info(self, code: str) -> Optional[Dict[str, Any]]:
        """
        獲取兌換碼信息

        Args:
            code: 兌換碼

        Returns:
            兌換碼信息字典
        """
        try:
            redeem_codes = self._load_redeem_codes()

            if code not in redeem_codes:
                return None

            return redeem_codes[code].copy()

        except Exception as e:
            logger.error(f"[兌換碼] 獲取兌換碼信息失敗: {e}")
            return None

    def list_redeem_codes(self, show_used: bool = False) -> List[Dict[str, Any]]:
        """
        獲取兌換碼列表

        Args:
            show_used: 是否顯示已使用的兌換碼

        Returns:
            兌換碼列表
        """
        try:
            redeem_codes = self._load_redeem_codes()

            current_time = time.time()
            code_list = []

            for code, info in redeem_codes.items():
                # 檢查是否已達到使用次數限制（僅對指定用戶兌換碼）
                use_count = info.get("use_count", 0)
                max_uses = info.get("max_uses", 1)
                is_fully_used = (
                    max_uses < 999999 and use_count >= max_uses
                )  # 通用兌換碼不會被標記為已使用

                # 過濾已完全使用的兌換碼（僅對指定用戶兌換碼）
                if not show_used and is_fully_used:
                    continue

                # 過濾過期的兌換碼
                if current_time > info.get("expire_time", 0):
                    continue

                code_info = {
                    "code": code,
                    "months": info.get("months", 1),
                    "target_user_id": info.get("target_user_id"),
                    "created_time": info.get("created_time", 0),
                    "expire_time": info.get("expire_time", 0),
                    "used": is_fully_used,
                    "used_by": info.get("used_by"),
                    "used_time": info.get("used_time"),
                    "use_count": use_count,
                    "max_uses": max_uses,
                    "used_users": info.get("used_users", []),
                }
                code_list.append(code_info)

            return code_list

        except Exception as e:
            logger.error(f"[兌換碼] 獲取兌換碼列表失敗: {e}")
            return []

    def delete_redeem_code(self, code: str) -> bool:
        """
        刪除兌換碼

        Args:
            code: 兌換碼

        Returns:
            是否成功
        """
        try:
            redeem_codes = self._load_redeem_codes()

            if code in redeem_codes:
                del redeem_codes[code]
                if not self._save_redeem_codes(redeem_codes):
                    return False
                logger.info(f"[兌換碼] 刪除兌換碼: {code}")
                return True

            return False

        except Exception as e:
            logger.error(f"[兌換碼] 刪除兌換碼失敗: {e}")
            return False

    def clean_expired_codes(self) -> int:
        """
        清理過期的兌換碼

        Returns:
            清理的兌換碼數量
        """
        try:
            redeem_codes = self._load_redeem_codes()

            current_time = time.time()
            expired_codes = []
            active_codes = {}

            for code, info in redeem_codes.items():
                # 保留未過期的兌換碼
                if current_time <= info.get("expire_time", 0):
                    active_codes[code] = info
                else:
                    expired_codes.append(code)

            if expired_codes:
                self._save_redeem_codes(active_codes)
                logger.info(f"[兌換碼] 清理過期兌換碼: {expired_codes}")

            return len(expired_codes)

        except Exception as e:
            logger.error(f"[兌換碼] 清理過期兌換碼失敗: {e}")
            return 0


# 創建全局兌換碼管理器實例
redeem_code_manager = RedeemCodeManager()
