"""
Premium功能指令處理器
"""

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger

from .payment_manager import payment_manager
from .premium_features import premium_features

# 創建服務
sv_premium = SV("鳴潮Premium功能", pm=0)


@sv_premium.on_command(("Premium设置", "Premium功能", "会员功能"))
async def premium_settings_menu(bot: Bot, ev: Event):
    """Premium设置菜单"""
    at_sender = True if ev.group_id else False

    user_id = ev.user_id

    # 檢查是否為Premium用戶
    if not payment_manager.is_premium_user(user_id):
        price = payment_manager.get_premium_price()
        message = (
            "❌ 您不是Premium會員！\n\n"
            "✨ Premium會員專享功能：\n"
            "• 自定義面板圖\n"
            "• 自定義每日圖角色\n"
            "• 無限制UID綁定\n"
            "• 自定義推送體力通知頻道\n"
            "• 無冷卻限制\n"
            "• OCR使用PRO線路\n"
            "• 無限制的解析系統\n\n"
            f"💎 升級Premium會員享受更多功能！\n"
            f"💰 價格：{price} 台幣/月\n"
            "📞 如需購買請聯繫管理員"
        )
        return await bot.send(message, at_sender)

    # 獲取Premium功能狀態
    feature_status = premium_features.get_premium_feature_status(user_id)
    user_settings = premium_features.get_premium_user_settings(user_id)

    message = "🎉 **Premium會員專享功能**\n\n"
    message += "✨ 可用功能：\n"
    message += f"• 自定義面板圖：{'✅' if feature_status['custom_panel'] else '❌'}\n"
    message += (
        f"• 自定義每日圖角色：{'✅' if feature_status['custom_daily'] else '❌'}\n"
    )
    message += (
        f"• 自定義推送頻道：{'✅' if feature_status['custom_push_channel'] else '❌'}\n"
    )
    message += (
        f"• 無限制解析系統：{'✅' if feature_status['unlimited_parse'] else '❌'}\n"
    )
    message += f"• OCR PRO線路：{'✅' if feature_status['pro_ocr'] else '❌'}\n"
    message += (
        f"• 無冷卻限制：{'✅' if feature_status['unlimited_cooldown'] else '❌'}\n"
    )
    message += (
        f"• 無限制UID綁定：{'✅' if feature_status['unlimited_bind'] else '❌'}\n\n"
    )

    if user_settings:
        message += "⚙️ 當前設置：\n"
        message += f"• 面板類型：{user_settings.get('custom_panel', '默認')}\n"
        message += (
            f"• 每日圖角色：{user_settings.get('custom_daily_character', '默認')}\n"
        )
        message += f"• 推送頻道：{user_settings.get('custom_push_channel', '默認')}\n\n"

    message += "📋 可用指令：\n"
    message += "• 設置面板 [類型] - 設置自定義面板\n"
    message += "• 設置每日角色 [角色] - 設置每日圖角色\n"
    message += "• 設置推送頻道 [頻道] - 設置推送頻道\n"
    message += "• 設置背景圖片 [圖片] - 設置自定義背景圖片\n"
    message += "• 設置背景URL [URL] - 設置自定義背景URL\n"
    message += "• 查看面板選項 - 查看可用面板類型\n"
    message += "• 查看角色選項 - 查看可用角色\n"
    message += "• 查看背景信息 - 查看當前背景設置\n"

    await bot.send(message, at_sender)


@sv_premium.on_prefix(("设置面板", "自定义面板"))
async def set_custom_panel(bot: Bot, ev: Event):
    """设置自定义面板"""
    at_sender = True if ev.group_id else False

    panel_type = ev.text.strip()
    if not panel_type:
        # 顯示可用選項
        options = premium_features.get_custom_panel_options(ev.user_id)
        if not options:
            return await bot.send("❌ 您沒有權限使用此功能！", at_sender)

        message = "🎨 可用面板類型：\n" + "\n".join(
            [f"• {option}" for option in options]
        )
        return await bot.send(message, at_sender)

    success, message = premium_features.set_custom_panel(ev.user_id, panel_type)
    await bot.send(message, at_sender)


@sv_premium.on_prefix(("设置每日角色", "自定义每日角色"))
async def set_custom_daily_character(bot: Bot, ev: Event):
    """设置自定义每日图角色"""
    at_sender = True if ev.group_id else False

    character = ev.text.strip()
    if not character:
        # 顯示可用選項
        options = premium_features.get_custom_daily_options(ev.user_id)
        if not options:
            return await bot.send("❌ 您沒有權限使用此功能！", at_sender)

        message = "👥 可用角色：\n" + "\n".join([f"• {option}" for option in options])
        return await bot.send(message, at_sender)

    success, message = premium_features.set_custom_daily_character(
        ev.user_id, character
    )
    await bot.send(message, at_sender)


@sv_premium.on_prefix(("设置推送频道", "自定义推送频道"))
async def set_custom_push_channel(bot: Bot, ev: Event):
    """设置自定义推送频道"""
    at_sender = True if ev.group_id else False

    channel = ev.text.strip()
    if not channel:
        # 顯示可用選項
        options = premium_features.get_custom_push_channel_options(ev.user_id)
        if not options:
            return await bot.send("❌ 您沒有權限使用此功能！", at_sender)

        message = "📢 可用推送頻道：\n" + "\n".join(
            [f"• {option}" for option in options]
        )
        return await bot.send(message, at_sender)

    success, message = premium_features.set_custom_push_channel(ev.user_id, channel)
    await bot.send(message, at_sender)


@sv_premium.on_command(("查看面板選項", "面板選項"))
async def show_panel_options(bot: Bot, ev: Event):
    """查看可用面板選項"""
    at_sender = True if ev.group_id else False

    options = premium_features.get_custom_panel_options(ev.user_id)
    if not options:
        return await bot.send("❌ 您沒有權限使用此功能！", at_sender)

    message = "🎨 可用面板類型：\n" + "\n".join([f"• {option}" for option in options])
    await bot.send(message, at_sender)


@sv_premium.on_command(("查看角色選項", "角色選項"))
async def show_character_options(bot: Bot, ev: Event):
    """查看可用角色選項"""
    at_sender = True if ev.group_id else False

    options = premium_features.get_custom_daily_options(ev.user_id)
    if not options:
        return await bot.send("❌ 您沒有權限使用此功能！", at_sender)

    message = "👥 可用角色：\n" + "\n".join([f"• {option}" for option in options])
    await bot.send(message, at_sender)


@sv_premium.on_command(("查看推送頻道選項", "推送頻道選項"))
async def show_channel_options(bot: Bot, ev: Event):
    """查看可用推送頻道選項"""
    at_sender = True if ev.group_id else False

    options = premium_features.get_custom_push_channel_options(ev.user_id)
    if not options:
        return await bot.send("❌ 您沒有權限使用此功能！", at_sender)

    message = "📢 可用推送頻道：\n" + "\n".join([f"• {option}" for option in options])
    await bot.send(message, at_sender)


@sv_premium.on_prefix(("设置背景图片", "自定义背景图片"))
async def set_custom_background(bot: Bot, ev: Event):
    """设置自定义背景图片"""
    at_sender = True if ev.group_id else False

    try:
        # 首先檢查是否有圖片附件
        image_urls = []

        # 檢查 ev.image_list (圖片列表)
        if hasattr(ev, "image_list") and ev.image_list:
            image_urls.extend(ev.image_list)

        # 檢查 ev.image (單個圖片)
        if hasattr(ev, "image") and ev.image:
            image_urls.append(ev.image)

        # 檢查 content 中的圖片
        if hasattr(ev, "content") and ev.content:
            for content in ev.content:
                if (
                    content.type in ["img", "image"]
                    and content.data
                    and isinstance(content.data, str)
                    and content.data.startswith("http")
                ):
                    image_urls.append(content.data)

        # 檢查文本中是否包含URL
        if hasattr(ev, "text") and ev.text:
            import re

            # 更寬鬆的URL模式，包括Discord URL
            url_pattern = r"https?://[^\s]+\.(?:png|jpg|jpeg|gif|bmp|webp)(?:\?[^\s]*)?"
            urls = re.findall(url_pattern, ev.text, re.IGNORECASE)
            image_urls.extend(urls)

        # 如果沒有找到任何圖片
        if not image_urls:
            return await bot.send(
                "❌ 請提供背景圖片！\n"
                "📝 使用方法：\n"
                "• 直接發送圖片文件\n"
                "• 使用圖片URL（如imgur、imgbb等）\n"
                "⚠️ 注意：Discord圖片鏈接會過期，建議使用其他圖片分享服務",
                at_sender,
            )

        # 使用第一個找到的圖片
        image_url = image_urls[0]

        # 調用設置背景功能
        success, message = await premium_features.set_custom_background_url(
            ev.user_id, image_url
        )

        await bot.send(message, at_sender)

    except Exception as e:
        await bot.send(f"❌ 處理背景圖片失敗：{str(e)}", at_sender)


@sv_premium.on_prefix(("设置背景URL", "自定义背景URL"))
async def set_custom_background_url(bot: Bot, ev: Event):
    """设置自定义背景URL"""
    at_sender = True if ev.group_id else False

    background_url = ev.text.strip()
    if not background_url:
        return await bot.send(
            "❌ 請提供背景圖片URL！\n"
            "用法：設置背景URL [URL]\n"
            "示例：設置背景URL https://example.com/bg.png",
            at_sender,
        )

    success, message = await premium_features.set_custom_background_url(
        ev.user_id, background_url
    )
    await bot.send(message, at_sender)


@sv_premium.on_command(("查看背景信息", "背景信息"))
async def show_background_info(bot: Bot, ev: Event):
    """查看当前背景设置"""
    at_sender = True if ev.group_id else False

    user_id = ev.user_id

    # 檢查是否為Premium用戶
    if not payment_manager.is_premium_user(user_id):
        return await bot.send("❌ 您不是Premium會員！", at_sender)

    # 獲取背景信息
    background_info = premium_features.get_custom_background_info(user_id)

    if not background_info:
        return await bot.send("❌ 無法獲取背景信息！", at_sender)

    message = "🖼️ **當前背景設置**\n\n"

    if background_info.get("has_custom_bg"):
        message += "✅ 已設置自定義背景\n"
        message += f"📁 背景文件：{background_info.get('bg_file_name', '未知')}\n"
        message += f"📂 文件路徑：{background_info.get('bg_file_path', '未知')}\n"
    else:
        message += "❌ 未設置自定義背景\n"
        message += "💡 使用默認背景圖片 (bg.png)\n"

    message += "\n📋 可用指令：\n"
    message += "• 設置背景圖片 [圖片] - 設置自定義背景圖片\n"
    message += "• 設置背景URL [URL] - 設置自定義背景URL\n"
    message += "• 重置背景 - 重置為默認背景"

    await bot.send(message, at_sender)


@sv_premium.on_command(("重置背景", "重置背景设置"))
async def reset_background(bot: Bot, ev: Event):
    """重置背景设置"""
    at_sender = True if ev.group_id else False

    user_id = ev.user_id

    # 檢查是否為Premium用戶
    if not payment_manager.is_premium_user(user_id):
        return await bot.send("❌ 您不是Premium會員！", at_sender)

    try:
        from pathlib import Path

        # 刪除用戶的自定義背景文件
        user_bg_dir = Path("WutheringWavesUID/utils/texture2d/user_backgrounds")
        bg_file = user_bg_dir / f"{user_id}_bg.png"

        if bg_file.exists():
            bg_file.unlink()
            message = "✅ 已重置背景設置！\n💡 現在使用默認背景圖片 (bg.png)"
        else:
            message = "ℹ️ 您沒有設置自定義背景，已使用默認背景圖片 (bg.png)"

        await bot.send(message, at_sender)

    except Exception as e:
        await bot.send(f"❌ 重置背景失敗：{str(e)}", at_sender)


@sv_premium.on_command(("重置Premium设置", "重置设置"))
async def reset_premium_settings(bot: Bot, ev: Event):
    """重置Premium设置"""
    at_sender = True if ev.group_id else False

    user_id = ev.user_id

    # 檢查是否為Premium用戶
    if not payment_manager.is_premium_user(user_id):
        return await bot.send("❌ 您不是Premium會員！", at_sender)

    # 重置為默認設置
    default_settings = {
        "custom_panel": "經典面板",
        "custom_daily_character": "暗主",
        "custom_push_channel": "默認頻道",
        "pro_ocr_enabled": True,
        "unlimited_parse_enabled": True,
    }

    success, message = premium_features.update_premium_user_settings(
        user_id, default_settings
    )

    # 同時重置背景設置
    try:
        from pathlib import Path

        user_bg_dir = Path("WutheringWavesUID/utils/texture2d/user_backgrounds")
        bg_file = user_bg_dir / f"{user_id}_bg.png"
        if bg_file.exists():
            bg_file.unlink()
        message += "\n🖼️ 背景設置已重置為默認"
    except Exception:
        pass

    await bot.send(message, at_sender)
