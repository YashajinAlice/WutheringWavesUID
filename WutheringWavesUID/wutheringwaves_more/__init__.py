from pathlib import Path

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img

from ..utils.at_help import ruser_id
from ..utils.hint import error_reply
from .draw_poker import draw_poker_img
from ..utils.waves_api import waves_api
from ..utils.database.models import WavesBind
from ..utils.error_reply import WAVES_CODE_098, WAVES_CODE_103

sv_waves_poker = SV("waves查询牌局")
sv_waves_64 = SV("waves64")
sv_waves_xianren = SV("waves展示闲人威风")


@sv_waves_poker.on_command(
    ("poker", "牌局", "扑克", "激斗", "打牌", "荣耀之丘"),
    block=True,
)
async def send_poker(bot: Bot, ev: Event):
    user_id = ruser_id(ev)
    uid = await WavesBind.get_uid_by_game(user_id, ev.bot_id)
    if not uid:
        return await bot.send(error_reply(WAVES_CODE_103))
    if waves_api.is_net(uid):
        return await bot.send(error_reply(WAVES_CODE_098))

    im = await draw_poker_img(ev, uid, user_id)
    if isinstance(im, str):
        at_sender = True if ev.group_id else False
        return await bot.send(im, at_sender)
    elif isinstance(im, bytes):
        return await bot.send(im)


@sv_waves_64.on_fullmatch("64", block=True)
async def send_64_image(bot: Bot, ev: Event):
    """發送64圖片"""
    # 圖片路徑
    image_path = Path(__file__).parent.parent / "utils" / "texture2d" / "image.png"

    if not image_path.exists():
        return await bot.send("[鸣潮] 圖片文件不存在！")

    # 轉換並發送圖片
    img = await convert_img(image_path)
    await bot.send(img)


@sv_waves_xianren.on_fullmatch("展示闲人威风", block=True)
async def send_xianren_image(bot: Bot, ev: Event):
    """發送展示闲人威风圖片"""
    # 圖片路徑
    image_path = Path(__file__).parent / "texture2d" / "001.png"

    if not image_path.exists():
        return await bot.send("[鸣潮] 圖片文件不存在！")

    # 轉換並發送圖片
    img = await convert_img(image_path)
    await bot.send(img)
