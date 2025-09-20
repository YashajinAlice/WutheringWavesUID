import re
import time

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger

from .wutheringwaves_config import WutheringWavesConfig

sv_subscriber_management = SV("訂閱用戶管理", pm=1)


@sv_subscriber_management.on_prefix(("添加分析订阅", "添加订阅用户"))
async def add_analyze_subscriber(bot: Bot, ev: Event):
    """添加分析冷却订阅用户"""
    at_sender = True if ev.group_id else False

    # 解析命令参数
    # 使用 on_prefix 时，ev.text 只包含参数部分，不包含指令
    args = ev.text.strip().split()

    # 調試信息
    logger.debug(f"[订阅管理] 原始文本: '{ev.text}'")
    logger.debug(f"[订阅管理] 解析参数: {args}, 长度: {len(args)}")

    if len(args) < 1:
        return await bot.send(
            "[鸣潮] 用法：添加订阅用户 <user_id> [月数]\n"
            "示例：\n"
            "• 添加订阅用户 123456789 1  # 1个月\n"
            "• 添加订阅用户 123456789 12 # 12个月(1年)\n"
            "• 添加订阅用户 123456789    # 永久\n",
            at_sender,
        )

    user_id = args[0]

    # 解析月数
    months = None
    if len(args) >= 2:
        try:
            months = int(args[1])
            if months <= 0:
                return await bot.send("[鸣潮] 月数必须大于0！\n", at_sender)
        except ValueError:
            return await bot.send("[鸣潮] 月数必须是数字！\n", at_sender)

    # 获取当前订阅用户列表
    subscribers = WutheringWavesConfig.get_config("AnalyzeCooldownSubscribers").data
    if not isinstance(subscribers, dict):
        # 兼容舊格式：將列表轉換為字典格式
        if isinstance(subscribers, list):
            logger.info(f"[订阅管理] 轉換舊格式列表為新格式字典: {subscribers}")
            old_subscribers = subscribers
            subscribers = {}
            for user_id_old in old_subscribers:
                subscribers[user_id_old] = {"permanent": True, "expire_time": 0}
            # 保存轉換後的格式
            WutheringWavesConfig.set_config("AnalyzeCooldownSubscribers", subscribers)
            logger.info(f"[订阅管理] 已轉換並保存新格式: {subscribers}")
        else:
            subscribers = {}

    # 检查用户是否已经是订阅用户
    if user_id in subscribers:
        current_info = subscribers[user_id]
        if current_info.get("permanent", False):
            return await bot.send(
                f"[鸣潮] 用户 {user_id} 已经是永久订阅用户了！\n", at_sender
            )
        else:
            expire_time = current_info.get("expire_time", 0)
            if expire_time > time.time():
                expire_date = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(expire_time)
                )
                return await bot.send(
                    f"[鸣潮] 用户 {user_id} 已经是订阅用户，到期时间：{expire_date}\n",
                    at_sender,
                )

    # 计算到期时间
    if months is None:
        # 永久订阅
        subscribers[user_id] = {"permanent": True, "expire_time": 0}
        duration_text = "永久"
    else:
        # 限时订阅
        expire_time = time.time() + (months * 30 * 24 * 60 * 60)  # 30天/月
        subscribers[user_id] = {"permanent": False, "expire_time": expire_time}
        expire_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expire_time))
        duration_text = f"{months}个月（到期：{expire_date}）"

    # 保存配置
    WutheringWavesConfig.set_config("AnalyzeCooldownSubscribers", subscribers)

    # 調試信息：驗證保存結果
    saved_data = WutheringWavesConfig.get_config("AnalyzeCooldownSubscribers").data
    logger.debug(f"[订阅管理] 保存後驗證 - 數據: {saved_data}")
    logger.debug(f"[订阅管理] 保存後驗證 - 類型: {type(saved_data)}")

    logger.info(f"[订阅管理] 添加分析订阅用户: {user_id}, 期限: {duration_text}")
    await bot.send(
        f"[鸣潮] 已添加用户 {user_id} 为分析订阅用户！期限：{duration_text}\n",
        at_sender,
    )


@sv_subscriber_management.on_prefix(("移除分析订阅", "移除订阅用户"))
async def remove_analyze_subscriber(bot: Bot, ev: Event):
    """移除分析冷却订阅用户"""
    at_sender = True if ev.group_id else False

    # 解析命令参数
    # 使用 on_prefix 时，ev.text 只包含参数部分
    args = ev.text.strip().split()
    if len(args) < 1:
        return await bot.send(
            "[鸣潮] 用法：移除订阅用户 <user_id>\n" "示例：移除订阅用户 123456789\n",
            at_sender,
        )

    user_id = args[0]

    # 获取当前订阅用户列表
    subscribers = WutheringWavesConfig.get_config("AnalyzeCooldownSubscribers").data
    if not isinstance(subscribers, dict):
        subscribers = {}

    if user_id not in subscribers:
        return await bot.send(f"[鸣潮] 用户 {user_id} 不是订阅用户！\n", at_sender)

    # 从订阅列表移除用户
    del subscribers[user_id]
    WutheringWavesConfig.set_config("AnalyzeCooldownSubscribers", subscribers)

    logger.info(f"[订阅管理] 移除分析订阅用户: {user_id}")
    await bot.send(f"[鸣潮] 已移除用户 {user_id} 的分析订阅！\n", at_sender)


@sv_subscriber_management.on_command(
    ("查看订阅用户", "订阅用户列表", "查看订阅", "订阅列表")
)
async def list_analyze_subscribers(bot: Bot, ev: Event):
    """查看分析冷却订阅用户列表"""
    at_sender = True if ev.group_id else False

    # 获取当前订阅用户列表
    subscribers = WutheringWavesConfig.get_config("AnalyzeCooldownSubscribers").data

    # 調試信息
    logger.debug(f"[订阅管理] 查看列表 - 原始数据: {subscribers}")
    logger.debug(f"[订阅管理] 查看列表 - 数据类型: {type(subscribers)}")

    if not isinstance(subscribers, dict):
        logger.warning(
            f"[订阅管理] 配置数据格式错误，期望dict，实际: {type(subscribers)}"
        )
        # 兼容舊格式：將列表轉換為字典格式
        if isinstance(subscribers, list):
            logger.info(f"[订阅管理] 轉換舊格式列表為新格式字典: {subscribers}")
            old_subscribers = subscribers
            subscribers = {}
            for user_id in old_subscribers:
                subscribers[user_id] = {"permanent": True, "expire_time": 0}
            # 保存轉換後的格式
            WutheringWavesConfig.set_config("AnalyzeCooldownSubscribers", subscribers)
            logger.info(f"[订阅管理] 已轉換並保存新格式: {subscribers}")
        else:
            subscribers = {}

    if not subscribers:
        logger.info("[订阅管理] 订阅用户列表为空")
        return await bot.send("[鸣潮] 目前没有订阅用户！\n", at_sender)

    # 格式化用户列表
    current_time = time.time()
    user_list = []
    expired_count = 0

    for user_id, info in subscribers.items():
        if info.get("permanent", False):
            user_list.append(f"• {user_id} - 永久订阅")
        else:
            expire_time = info.get("expire_time", 0)
            if expire_time > current_time:
                expire_date = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(expire_time)
                )
                user_list.append(f"• {user_id} - 到期：{expire_date}")
            else:
                expired_count += 1
                user_list.append(f"• {user_id} - 已过期")

    message = f"[鸣潮] 分析订阅用户列表（共 {len(subscribers)} 人）：\n" + "\n".join(
        user_list
    )
    if expired_count > 0:
        message += f"\n\n⚠️ 有 {expired_count} 个用户已过期，建议清理"
    message += "\n"

    await bot.send(message, at_sender)


@sv_subscriber_management.on_command(("清空订阅用户", "清空订阅列表"))
async def clear_analyze_subscribers(bot: Bot, ev: Event):
    """清空分析冷却订阅用户列表"""
    at_sender = True if ev.group_id else False

    # 清空订阅列表
    WutheringWavesConfig.set_config("AnalyzeCooldownSubscribers", {})

    logger.info("[订阅管理] 清空分析订阅用户列表")
    await bot.send("[鸣潮] 已清空所有分析订阅用户！\n", at_sender)


@sv_subscriber_management.on_command(("清理过期订阅", "清理过期用户"))
async def clean_expired_subscribers(bot: Bot, ev: Event):
    """清理过期的订阅用户"""
    at_sender = True if ev.group_id else False

    # 获取当前订阅用户列表
    subscribers = WutheringWavesConfig.get_config("AnalyzeCooldownSubscribers").data
    if not isinstance(subscribers, dict):
        subscribers = {}

    if not subscribers:
        return await bot.send("[鸣潮] 目前没有订阅用户！\n", at_sender)

    # 清理过期用户
    current_time = time.time()
    expired_users = []
    active_users = {}

    for user_id, info in subscribers.items():
        if info.get("permanent", False):
            # 永久用户保留
            active_users[user_id] = info
        else:
            expire_time = info.get("expire_time", 0)
            if expire_time > current_time:
                # 未过期用户保留
                active_users[user_id] = info
            else:
                # 过期用户记录
                expired_users.append(user_id)

    if not expired_users:
        return await bot.send("[鸣潮] 没有过期的订阅用户需要清理！\n", at_sender)

    # 保存清理后的列表
    WutheringWavesConfig.set_config("AnalyzeCooldownSubscribers", active_users)

    logger.info(f"[订阅管理] 清理过期订阅用户: {expired_users}")
    await bot.send(f"[鸣潮] 已清理 {len(expired_users)} 个过期订阅用户！\n", at_sender)
