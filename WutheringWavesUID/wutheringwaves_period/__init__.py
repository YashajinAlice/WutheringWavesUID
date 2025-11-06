from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..utils.waves_api import waves_api
from ..utils.database.models import WavesBind
from ..utils.error_reply import ERROR_CODE, WAVES_CODE_103, WAVES_CODE_098
from .draw_period import draw_period_img

sv_period = SV("waves资源简报")


@sv_period.on_command(
    (
        "星声",
        "星声统计",
        "简报",
        "资源简报",
    ),
    block=True,
)
async def send_period(bot: Bot, ev: Event):
    uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    if not uid:
        return await bot.send(ERROR_CODE[WAVES_CODE_103])
    
    # 檢查UID是否在黑名單中
    from ..utils.util import check_uid_banned_and_send
    
    if await check_uid_banned_and_send(bot, ev, uid):
        return
    
    if waves_api.is_net(uid):
        return await bot.send(ERROR_CODE[WAVES_CODE_098])

    await bot.send(await draw_period_img(bot, ev))
