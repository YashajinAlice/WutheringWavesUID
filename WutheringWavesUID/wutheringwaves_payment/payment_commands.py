"""
付費機制指令處理器
"""

import time

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger

from .user_tier_manager import UserTier
from .payment_manager import payment_manager
from .redeem_code_manager import redeem_code_manager

# 創建服務
sv_payment = SV("鳴潮付費機制", pm=1)
sv_redeem = SV("鳴潮兌換碼", pm=0)


@sv_payment.on_command(("我的会员", "会员状态", "查看会员"))
async def check_membership_status(bot: Bot, ev: Event):
    """查看会员状态"""
    at_sender = True if ev.group_id else False

    user_id = ev.user_id
    limits_info = payment_manager.get_user_limits_info(user_id)

    if limits_info["is_premium"]:
        # Premium用戶
        expire_date = limits_info.get("expire_date", "永久")
        message = f"🎉 您目前是 **Premium 會員**！\n\n"
        message += f"📅 到期時間：{expire_date}\n\n"
        message += "✨ Premium 會員專享功能：\n"
        message += "• 自定義面板圖\n"
        message += "• 自定義每日圖角色\n"
        message += "• 無限制UID綁定\n"
        message += "• 自定義推送體力通知頻道\n"
        message += "• 無冷卻限制\n"
        message += "• OCR使用PRO線路\n"
        message += "• 無限制的解析系統\n"
    else:
        # 一般用戶
        message = f"👤 您目前是 **一般用戶**\n\n"
        message += "📊 當前限制：\n"
        message += f"• 分析冷卻：{limits_info['cooldowns']['analyze']} 秒\n"
        message += f"• 查詢冷卻：{limits_info['cooldowns']['query']} 秒\n"
        message += f"• 解析冷卻：{limits_info['cooldowns']['parse']} 秒\n"
        message += f"• 最大綁定UID數：{limits_info['max_bind_num']} 個\n\n"
        message += "💎 升級 Premium 會員享受更多功能！\n"
        message += f"💰 價格：{payment_manager.get_premium_price()} 台幣/月"

    await bot.send(message, at_sender)


@sv_payment.on_command(("付费说明", "会员说明", "Premium说明"))
async def payment_info(bot: Bot, ev: Event):
    """付费说明"""
    at_sender = True if ev.group_id else False

    if not payment_manager.is_payment_system_enabled():
        message = "ℹ️ 付費系統目前尚未啟用\n"
        message += "所有功能均可正常使用，無任何限制"
        return await bot.send(message, at_sender)

    price = payment_manager.get_premium_price()

    message = "💎 **鳴潮機器人 Premium 會員**\n\n"
    message += f"💰 價格：{price} 台幣/月\n\n"
    message += "📋 **一般用戶功能**：\n"
    message += "• OCR免費線路\n"
    message += "• 分析面板冷卻5分鐘（分析失敗則不計入）\n"
    message += "• 綁定UID數：1個\n"
    message += "• 默認面板圖\n"
    message += "• 默認推送體力通知頻道\n"
    message += "• 每日、卡片查詢冷卻3分鐘\n"
    message += "• 解析系統冷卻3分鐘（失敗則不計入）\n\n"
    message += "✨ **Premium 會員專享**：\n"
    message += "• 自定義面板圖\n"
    message += "• 自定義每日圖角色\n"
    message += "• 綁定UID：不限制\n"
    message += "• 自定義推送體力通知頻道\n"
    message += "• 無冷卻限制\n"
    message += "• OCR使用PRO線路\n"
    message += "• 無限制的解析系統\n\n"
    message += "💡 付費機制不會影響正常使用，所有功能依然可用！\n"
    message += "📞 如需購買請聯繫管理員"

    await bot.send(message, at_sender)


@sv_redeem.on_command(("兑换", "使用兑换码"))
async def use_redeem_code(bot: Bot, ev: Event):
    """使用兑换码"""
    at_sender = True if ev.group_id else False

    # 解析兌換碼
    code = ev.text.strip()
    if not code:
        return await bot.send(
            "❌ 請提供兌換碼！\n" "用法：兌換 [兌換碼]\n" "示例：兌換 ABC123DEF456",
            at_sender,
        )

    user_id = ev.user_id
    success, message = payment_manager.use_redeem_code(code, user_id)

    if success:
        # 獲取更新後的會員信息
        limits_info = payment_manager.get_user_limits_info(user_id)
        expire_date = limits_info.get("expire_date", "永久")

        message += f"\n\n🎉 恭喜！您現在是 Premium 會員！\n"
        message += f"📅 到期時間：{expire_date}"

    await bot.send(message, at_sender)


# 管理員指令
@sv_payment.on_prefix(("添加Premium", "添加会员"))
async def add_premium_user(bot: Bot, ev: Event):
    """添加Premium用户（管理员）"""
    at_sender = True if ev.group_id else False

    # 解析命令參數
    args = ev.text.strip().split()

    if len(args) < 1:
        return await bot.send(
            "[鳴潮] 用法：添加Premium <user_id> [月數]\n"
            "示例：\n"
            "• 添加Premium 123456789 1  # 1個月\n"
            "• 添加Premium 123456789 12 # 12個月(1年)\n"
            "• 添加Premium 123456789    # 永久",
            at_sender,
        )

    user_id = args[0]

    # 解析月數
    months = None
    if len(args) >= 2:
        try:
            months = int(args[1])
            if months <= 0:
                return await bot.send("[鳴潮] 月數必須大於0！", at_sender)
        except ValueError:
            return await bot.send("[鳴潮] 月數必須是數字！", at_sender)

    # 添加Premium用戶
    success = payment_manager.add_premium_user(user_id, months)

    if success:
        duration_text = "永久" if months is None else f"{months}個月"
        await bot.send(
            f"[鳴潮] 已添加用戶 {user_id} 為Premium會員！期限：{duration_text}",
            at_sender,
        )
    else:
        await bot.send("[鳴潮] 添加Premium用戶失敗！", at_sender)


@sv_payment.on_prefix(("移除Premium", "移除会员"))
async def remove_premium_user(bot: Bot, ev: Event):
    """移除Premium用户（管理员）"""
    at_sender = True if ev.group_id else False

    # 解析命令參數
    user_id = ev.text.strip()
    if not user_id:
        return await bot.send(
            "[鳴潮] 用法：移除Premium <user_id>\n" "示例：移除Premium 123456789",
            at_sender,
        )

    # 移除Premium用戶
    success = payment_manager.remove_premium_user(user_id)

    if success:
        await bot.send(f"[鳴潮] 已移除用戶 {user_id} 的Premium會員資格！", at_sender)
    else:
        await bot.send(f"[鳴潮] 用戶 {user_id} 不是Premium會員或移除失敗！", at_sender)


@sv_payment.on_command(("Premium用户列表", "会员列表", "查看Premium"))
async def list_premium_users(bot: Bot, ev: Event):
    """查看Premium用户列表（管理员）"""
    at_sender = True if ev.group_id else False

    premium_users = payment_manager.get_premium_users_list()

    if not premium_users:
        return await bot.send("[鳴潮] 目前沒有Premium用戶！", at_sender)

    # 格式化用戶列表
    current_time = time.time()
    user_list = []
    expired_count = 0

    for user_id, info in premium_users.items():
        if info.get("permanent", False):
            user_list.append(f"• {user_id} - 永久會員")
        else:
            expire_time = info.get("expire_time", 0)
            if expire_time > current_time:
                expire_date = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(expire_time)
                )
                user_list.append(f"• {user_id} - 到期：{expire_date}")
            else:
                expired_count += 1
                user_list.append(f"• {user_id} - 已過期")

    message = f"[鳴潮] Premium用戶列表（共 {len(premium_users)} 人）：\n" + "\n".join(
        user_list
    )
    if expired_count > 0:
        message += f"\n\n⚠️ 有 {expired_count} 個用戶已過期，建議清理"

    await bot.send(message, at_sender)


@sv_payment.on_prefix(("新增兑换码", "创建兑换码"))
async def create_redeem_code(bot: Bot, ev: Event):
    """创建兑换码（管理员）"""
    at_sender = True if ev.group_id else False

    # 解析命令參數
    args = ev.text.strip().split()

    if len(args) < 1:
        return await bot.send(
            "[鳴潮] 用法：新增兌換碼 [數量]<單位> [用戶ID]\n"
            "單位：s=秒, m=分, h=時, d=天, M=月\n"
            "示例：\n"
            "• 新增兌換碼           # 不限數量，1個月\n"
            "• 新增兌換碼 30s       # 30秒\n"
            "• 新增兌換碼 5m        # 5分鐘\n"
            "• 新增兌換碼 1h         # 1小時\n"
            "• 新增兌換碼 7d        # 7天\n"
            "• 新增兌換碼 1M        # 1個月\n"
            "• 新增兌換碼 3M 123456 # 3個月，指定用戶\n"
            "• 新增兌換碼 123456    # 不限數量，指定用戶",
            at_sender,
        )

    try:
        # 解析時間和單位
        time_str = args[0]

        # 檢查是否為純數字（可能是用戶ID）
        if time_str.isdigit():
            # 純數字，視為用戶ID，使用默認1個月
            duration_seconds = 30 * 86400  # 1個月
            target_user_id = time_str
        else:
            # 解析時間格式
            if len(time_str) < 2:
                return await bot.send("[鳴潮] 時間格式錯誤！", at_sender)

            unit = time_str[-1].lower()
            value = int(time_str[:-1])

            if value <= 0:
                return await bot.send("[鳴潮] 時間必須大於0！", at_sender)

            # 轉換為秒
            if unit == "s":  # 秒
                duration_seconds = value
            elif unit == "m":  # 分鐘
                duration_seconds = value * 60
            elif unit == "h":  # 小時
                duration_seconds = value * 3600
            elif unit == "d":  # 天
                duration_seconds = value * 86400
            elif unit == "M":  # 月
                duration_seconds = value * 30 * 86400  # 30天為一個月
            else:
                return await bot.send(
                    "[鳴潮] 不支持的單位！支持：s(秒), m(分), h(時), d(天), M(月)",
                    at_sender,
                )

            target_user_id = args[1] if len(args) >= 2 else None

    except ValueError:
        return await bot.send("[鳴潮] 時間格式錯誤！", at_sender)

    # 創建兌換碼
    code = payment_manager.create_redeem_code(duration_seconds, target_user_id)

    if code:
        target_text = (
            f"，指定用戶：{target_user_id}" if target_user_id else "，通用兌換碼"
        )

        # 格式化時間顯示
        if duration_seconds < 60:
            time_display = f"{duration_seconds}秒"
        elif duration_seconds < 3600:
            time_display = f"{duration_seconds // 60}分鐘"
        elif duration_seconds < 86400:
            time_display = f"{duration_seconds // 3600}小時"
        elif duration_seconds < 2592000:  # 30天
            time_display = f"{duration_seconds // 86400}天"
        else:
            time_display = f"{duration_seconds // (30 * 86400)}個月"

        await bot.send(
            f"[鳴潮] 兌換碼創建成功！\n"
            f"兌換碼：{code}\n"
            f"時長：{time_display}{target_text}\n"
            f"有效期：3天",
            at_sender,
        )
    else:
        await bot.send("[鳴潮] 兌換碼創建失敗！", at_sender)


@sv_payment.on_command(("兑换码列表", "查看兑换码"))
async def list_redeem_codes(bot: Bot, ev: Event):
    """查看兑换码列表（管理员）"""
    at_sender = True if ev.group_id else False

    codes = payment_manager.get_redeem_codes_list(show_used=False)

    if not codes:
        return await bot.send("[鳴潮] 目前沒有可用的兌換碼！", at_sender)

    # 格式化兌換碼列表
    code_list = []
    for code_info in codes:
        target_text = (
            f"，指定用戶：{code_info['target_user_id']}"
            if code_info["target_user_id"]
            else "，通用"
        )
        expire_date = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(code_info["expire_time"])
        )

        # 顯示使用次數信息
        use_count = code_info.get("use_count", 0)
        max_uses = code_info.get("max_uses", 1)
        if max_uses >= 999999:  # 通用兌換碼
            use_status = f"（已使用 {use_count} 次）"
        else:  # 指定用戶兌換碼
            use_status = f"（已使用 {use_count}/{max_uses} 次）"

        code_list.append(
            f"• {code_info['code']} - {code_info['months']}個月{target_text}{use_status}，到期：{expire_date}"
        )

    message = f"[鳴潮] 可用兌換碼列表（共 {len(codes)} 個）：\n" + "\n".join(code_list)

    await bot.send(message, at_sender)


@sv_payment.on_command(("清理过期数据", "清理过期"))
async def clean_expired_data(bot: Bot, ev: Event):
    """清理过期数据（管理员）"""
    at_sender = True if ev.group_id else False

    result = payment_manager.clean_expired_data()

    message = f"[鳴潮] 清理完成！\n"
    message += f"• 清理過期Premium用戶：{result['premium_users']} 個\n"
    message += f"• 清理過期兌換碼：{result['redeem_codes']} 個"

    await bot.send(message, at_sender)
