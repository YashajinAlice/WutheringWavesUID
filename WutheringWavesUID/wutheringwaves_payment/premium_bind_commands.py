"""
Premium用戶綁定賬號指令處理器
"""

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger

from .payment_manager import payment_manager
from .premium_bind_manager import premium_bind_manager

# 創建服務
sv_premium_bind = SV("鳴潮Premium綁定", pm=0)


@sv_premium_bind.on_command(("Premium綁定狀態", "Premium綁定信息", "綁定狀態"))
async def premium_bind_status(bot: Bot, ev: Event):
    """查看Premium綁定狀態"""
    at_sender = True if ev.group_id else False
    user_id = str(ev.user_id)
    bot_id = ev.bot_id

    try:
        # 檢查是否為Premium用戶
        if not payment_manager.is_premium_user(user_id):
            return await bot.send(
                "❌ 此功能僅限Premium用戶使用！\n"
                "💎 升級Premium會員享受更多綁定賬號權限！",
                at_sender,
            )

        # 獲取綁定狀態信息
        status_info = await premium_bind_manager.get_bind_status_info(user_id, bot_id)

        # 獲取綁定列表
        bind_list = await premium_bind_manager.get_bind_list(user_id, bot_id)

        # 構建消息
        message = f"💎 **Premium用戶綁定狀態**\n\n"
        message += f"**用戶等級**: {status_info['user_tier']}\n"
        message += (
            f"**當前綁定**: {status_info['current_count']}/{status_info['max_count']}\n"
        )
        message += f"**剩餘額度**: {status_info['remaining']}\n\n"

        if bind_list:
            message += "**已綁定賬號**:\n"
            for i, bind_info in enumerate(bind_list, 1):
                formatted_info = premium_bind_manager.format_bind_info(bind_info)
                message += f"{i}. {formatted_info}\n"
        else:
            message += "**暫無綁定賬號**\n"

        message += f"\n💡 使用 `綁定<UID>` 來綁定新賬號"

        await bot.send(message, at_sender)

    except Exception as e:
        logger.error(f"[鳴潮] Premium綁定狀態查詢失敗: {e}")
        await bot.send("❌ 查詢綁定狀態失敗，請稍後再試", at_sender)


@sv_premium_bind.on_command(("Premium綁定列表", "綁定列表"))
async def premium_bind_list(bot: Bot, ev: Event):
    """查看Premium綁定列表"""
    at_sender = True if ev.group_id else False
    user_id = str(ev.user_id)
    bot_id = ev.bot_id

    try:
        # 檢查是否為Premium用戶
        if not payment_manager.is_premium_user(user_id):
            return await bot.send(
                "❌ 此功能僅限Premium用戶使用！\n"
                "💎 升級Premium會員享受更多綁定賬號權限！",
                at_sender,
            )

        # 獲取綁定列表
        bind_list = await premium_bind_manager.get_bind_list(user_id, bot_id)

        if not bind_list:
            return await bot.send("📋 暫無綁定賬號", at_sender)

        # 構建消息
        message = f"📋 **Premium綁定列表** (共{len(bind_list)}個)\n\n"

        for i, bind_info in enumerate(bind_list, 1):
            formatted_info = premium_bind_manager.format_bind_info(bind_info)
            message += f"**{i}.** {formatted_info}\n"

        await bot.send(message, at_sender)

    except Exception as e:
        logger.error(f"[鳴潮] Premium綁定列表查詢失敗: {e}")
        await bot.send("❌ 查詢綁定列表失敗，請稍後再試", at_sender)


@sv_premium_bind.on_command(("Premium綁定限制", "綁定限制"))
async def premium_bind_limit(bot: Bot, ev: Event):
    """查看Premium綁定限制"""
    at_sender = True if ev.group_id else False
    user_id = str(ev.user_id)
    bot_id = ev.bot_id

    try:
        # 獲取綁定狀態信息
        status_info = await premium_bind_manager.get_bind_status_info(user_id, bot_id)

        # 構建消息
        message = f"📊 **綁定限制信息**\n\n"
        message += f"**用戶等級**: {status_info['user_tier']}\n"
        message += f"**最大綁定數**: {status_info['max_count']}\n"
        message += f"**當前綁定數**: {status_info['current_count']}\n"
        message += f"**剩餘額度**: {status_info['remaining']}\n\n"

        if status_info["is_premium"]:
            message += "💎 **Premium用戶特權**:\n"
            message += "• 無冷卻限制\n"
            message += "• 高精度OCR識別\n"
            message += "• 自定義面板背景\n"
            message += "• 更多綁定賬號額度\n"
        else:
            message += "🔒 **一般用戶限制**:\n"
            message += "• 查詢功能有冷卻限制\n"
            message += "• 使用標準OCR識別\n"
            message += "• 綁定賬號數量有限\n\n"
            message += "💎 **升級Premium享受更多特權！**"

        await bot.send(message, at_sender)

    except Exception as e:
        logger.error(f"[鳴潮] Premium綁定限制查詢失敗: {e}")
        await bot.send("❌ 查詢綁定限制失敗，請稍後再試", at_sender)
