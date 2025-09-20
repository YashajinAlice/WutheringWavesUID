from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger

from .wutheringwaves_config import WutheringWavesConfig

sv_subscriber_management = SV("訂閱用戶管理", pm=1)


@sv_subscriber_management.on_command(("添加分析订阅", "添加订阅用户"))
async def add_analyze_subscriber(bot: Bot, ev: Event):
    """添加分析冷却订阅用户"""
    at_sender = True if ev.group_id else False

    # 获取用户ID
    user_id = str(ev.user_id)

    # 获取当前订阅用户列表
    subscribers = WutheringWavesConfig.get_config("AnalyzeCooldownSubscribers").data

    if user_id in subscribers:
        return await bot.send(f"[鸣潮] 用户 {user_id} 已经是订阅用户了！\n", at_sender)

    # 添加用户到订阅列表
    subscribers.append(user_id)
    WutheringWavesConfig.set_config("AnalyzeCooldownSubscribers", subscribers)

    logger.info(f"[订阅管理] 添加分析订阅用户: {user_id}")
    await bot.send(f"[鸣潮] 已添加用户 {user_id} 为分析订阅用户！\n", at_sender)


@sv_subscriber_management.on_command(("移除分析订阅", "移除订阅用户"))
async def remove_analyze_subscriber(bot: Bot, ev: Event):
    """移除分析冷却订阅用户"""
    at_sender = True if ev.group_id else False

    # 获取用户ID
    user_id = str(ev.user_id)

    # 获取当前订阅用户列表
    subscribers = WutheringWavesConfig.get_config("AnalyzeCooldownSubscribers").data

    if user_id not in subscribers:
        return await bot.send(f"[鸣潮] 用户 {user_id} 不是订阅用户！\n", at_sender)

    # 从订阅列表移除用户
    subscribers.remove(user_id)
    WutheringWavesConfig.set_config("AnalyzeCooldownSubscribers", subscribers)

    logger.info(f"[订阅管理] 移除分析订阅用户: {user_id}")
    await bot.send(f"[鸣潮] 已移除用户 {user_id} 的分析订阅！\n", at_sender)


@sv_subscriber_management.on_command(("查看订阅用户", "订阅用户列表"))
async def list_analyze_subscribers(bot: Bot, ev: Event):
    """查看分析冷却订阅用户列表"""
    at_sender = True if ev.group_id else False

    # 获取当前订阅用户列表
    subscribers = WutheringWavesConfig.get_config("AnalyzeCooldownSubscribers").data

    if not subscribers:
        return await bot.send("[鸣潮] 目前没有订阅用户！\n", at_sender)

    # 格式化用户列表
    user_list = "\n".join([f"• {user_id}" for user_id in subscribers])
    message = f"[鸣潮] 分析订阅用户列表（共 {len(subscribers)} 人）：\n{user_list}\n"

    await bot.send(message, at_sender)


@sv_subscriber_management.on_command(("清空订阅用户", "清空订阅列表"))
async def clear_analyze_subscribers(bot: Bot, ev: Event):
    """清空分析冷却订阅用户列表"""
    at_sender = True if ev.group_id else False

    # 清空订阅列表
    WutheringWavesConfig.set_config("AnalyzeCooldownSubscribers", [])

    logger.info("[订阅管理] 清空分析订阅用户列表")
    await bot.send("[鸣潮] 已清空所有分析订阅用户！\n", at_sender)
