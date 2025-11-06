from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.aps import scheduler
from gsuid_core.logger import logger

from ..utils.waves_api import waves_api
from .notice_stamina import get_notice_list
from ..utils.database.models import WavesBind
from .draw_waves_stamina import draw_stamina_img
from ..utils.waves_send_msg import send_board_cast_msg
from ..wutheringwaves_config import WutheringWavesConfig
from ..utils.error_reply import ERROR_CODE, WAVES_CODE_098, WAVES_CODE_103

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
    
    # 檢查UID是否在黑名單中
    from ..utils.util import check_uid_banned_and_send
    
    if await check_uid_banned_and_send(bot, ev, uid):
        return
    
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
