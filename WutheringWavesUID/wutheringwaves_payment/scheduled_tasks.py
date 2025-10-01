"""
付費機制定時任務
"""

import time

from gsuid_core.aps import scheduler
from gsuid_core.logger import logger

from .payment_manager import payment_manager


@scheduler.scheduled_job("cron", hour=2, minute=0)
async def clean_expired_payment_data():
    """每天凌晨2點清理過期的付費數據"""
    try:
        logger.info("[付費機制] 開始清理過期數據...")

        result = payment_manager.clean_expired_data()

        if result["premium_users"] > 0 or result["redeem_codes"] > 0:
            logger.info(
                f"[付費機制] 清理完成 - "
                f"過期Premium用戶: {result['premium_users']} 個, "
                f"過期兌換碼: {result['redeem_codes']} 個"
            )
        else:
            logger.info("[付費機制] 沒有過期數據需要清理")

    except Exception as e:
        logger.error(f"[付費機制] 清理過期數據失敗: {e}")


@scheduler.scheduled_job("cron", hour=1, minute=0)
async def check_premium_expiration():
    """每天凌晨1點檢查Premium用戶到期情況"""
    try:
        logger.info("[付費機制] 開始檢查Premium用戶到期情況...")

        premium_users = payment_manager.get_premium_users_list()
        current_time = time.time()
        expiring_soon = []
        expired_today = []

        for user_id, info in premium_users.items():
            if info.get("permanent", False):
                continue  # 永久用戶跳過

            expire_time = info.get("expire_time", 0)
            if expire_time <= current_time:
                # 已過期
                expired_today.append(user_id)
            elif expire_time <= current_time + (7 * 24 * 60 * 60):  # 7天內到期
                # 即將到期
                expiring_soon.append((user_id, expire_time))

        if expiring_soon:
            logger.info(f"[付費機制] 有 {len(expiring_soon)} 個Premium用戶即將到期")
            for user_id, expire_time in expiring_soon:
                expire_date = time.strftime("%Y-%m-%d", time.localtime(expire_time))
                logger.info(f"[付費機制] 用戶 {user_id} 將於 {expire_date} 到期")

        if expired_today:
            logger.info(f"[付費機制] 有 {len(expired_today)} 個Premium用戶今日到期")
            for user_id in expired_today:
                logger.info(f"[付費機制] 用戶 {user_id} 已到期")

        logger.info("[付費機制] Premium用戶到期檢查完成")

    except Exception as e:
        logger.error(f"[付費機制] 檢查Premium用戶到期情況失敗: {e}")
