from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.aps import scheduler
from gsuid_core.logger import logger

from ..utils.waves_api import waves_api
from .notice_stamina import get_notice_list
from ..utils.waves_send_msg import send_board_cast_msg
from ..utils.database.models import WavesBind, WavesUser
from ..wutheringwaves_config import WutheringWavesConfig
from ..utils.error_reply import ERROR_CODE, WAVES_CODE_098, WAVES_CODE_103
from .draw_waves_stamina import (
    draw_stamina_img,
    draw_international_stamina_img,
)

waves_daily_info = SV("waves查询体力")


stamina_push_interval = WutheringWavesConfig.get_config("StaminaPushInterval").data

logger.info(f"[鸣潮] 体力推送间隔设置: {stamina_push_interval} 分钟")


@waves_daily_info.on_fullmatch(
    (
        "每日",
        "mr",
        "实时便笺",
        "便笺",
        "便签",
        "体力",
    )
)
async def send_daily_info_pic(bot: Bot, ev: Event):
    await bot.logger.info(f"[鸣潮]开始执行[每日信息]: {ev.user_id}")
    uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    if not uid:
        return await bot.send(ERROR_CODE[WAVES_CODE_103])

    # 檢查是否為國際服用戶
    user = await WavesUser.get_user_by_attr(ev.user_id, ev.bot_id, "uid", uid)

    # 調試信息
    await bot.logger.info(f"[鸣潮][每日信息]UID: {uid}")
    await bot.logger.info(f"[鸣潮][每日信息]用戶信息: {user}")
    if user:
        await bot.logger.info(f"[鸣潮][每日信息]平台: {user.platform}")

    # 檢查是否為國際服用戶（多種方式）
    is_international = False
    if user and user.platform and user.platform.startswith("international_"):
        is_international = True
        await bot.logger.info(
            f"[鸣潮][每日信息] 检测到国际服用户（platform: {user.platform}）"
        )
    elif user and user.platform and user.platform == "international":
        is_international = True
        await bot.logger.info(
            f"[鸣潮][每日信息] 检测到国际服用户（platform: {user.platform}）"
        )
    elif user and user.uid and user.uid.isdigit() and int(user.uid) >= 200000000:
        is_international = True
        await bot.logger.info(f"[鸣潮][每日信息] 检测到国际服用户（UID: {user.uid}）")
    elif user and user.cookie and len(user.cookie) > 20:
        is_international = True
        await bot.logger.info(
            f"[鸣潮][每日信息] 检测到可能的国际服用户（有有效cookie）"
        )

    if is_international:
        # 國際服體力查詢
        await bot.logger.info(
            f"[鸣潮][每日信息]使用國際服體力查詢，平台: {user.platform}"
        )
        return await bot.send(await draw_international_stamina_img(bot, ev, user))
    else:
        # 國服體力查詢
        if waves_api.is_net(uid):
            await bot.logger.info(
                f"[鸣潮][每日信息]檢測到國際服UID但平台標記錯誤，使用國際服查詢"
            )
            # 如果檢測到是國際服UID但平台標記錯誤，嘗試使用國際服查詢
            if user:
                # 更新平台標記
                await WavesUser.update_data_by_data(
                    select_data={
                        "user_id": ev.user_id,
                        "bot_id": ev.bot_id,
                        "uid": uid,
                    },
                    update_data={"platform": "international"},
                )
                return await bot.send(
                    await draw_international_stamina_img(bot, ev, user)
                )
            else:
                return await bot.send(ERROR_CODE[WAVES_CODE_098])
        return await bot.send(await draw_stamina_img(bot, ev))


@scheduler.scheduled_job("interval", minutes=stamina_push_interval)
async def waves_daily_info_notice_job():
    logger.info(f"[鸣潮] 体力推送任务开始执行 (间隔: {stamina_push_interval} 分钟)")

    if stamina_push_interval == 0:
        logger.info("[鸣潮] 体力推送间隔设置为0，跳过推送")
        return

    result = await get_notice_list()
    if not result:
        logger.info("[鸣潮] 没有需要推送的用户")
        return

    logger.info(f"[鸣潮] 开始推送: {result}")
    await send_board_cast_msg(result, "resin")
    logger.info("[鸣潮] 体力推送任务完成")
