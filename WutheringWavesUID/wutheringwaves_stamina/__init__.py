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
    if user and user.platform == "international":
        # 國際服體力查詢
        return await bot.send(await draw_international_stamina_img(bot, ev, user))
    else:
        # 國服體力查詢
        if waves_api.is_net(uid):
            return await bot.send(ERROR_CODE[WAVES_CODE_098])
        return await bot.send(await draw_stamina_img(bot, ev))


@scheduler.scheduled_job("interval", minutes=stamina_push_interval)
async def waves_daily_info_notice_job():
    if stamina_push_interval == 0:
        return
    result = await get_notice_list()
    if not result:
        return
    logger.debug(f"鸣潮推送开始：{result}")
    await send_board_cast_msg(result, "resin")
