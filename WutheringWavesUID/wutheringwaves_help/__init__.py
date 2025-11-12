from typing import Any, List

from PIL import Image

from gsuid_core.bot import Bot
from gsuid_core.help.utils import register_help
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..utils.button import WavesButton
from ..wutheringwaves_config import PREFIX
from .change_help import get_change_help
from .get_help import ICON, get_help

sv_waves_help = SV("waves帮助")
sv_waves_change_help = SV("waves替换帮助")


@sv_waves_help.on_fullmatch(f"帮助")
async def send_help_img(bot: Bot, ev: Event):
    buttons: List[Any] = [
        WavesButton("登录", "登录"),
        WavesButton("查看特征码", "查看"),
        WavesButton("切换特征码", "切换"),
        WavesButton("体力", "mr"),
        WavesButton("刷新面板", "刷新面板"),
        WavesButton("练度统计", "练度统计"),
    ]
    await bot.send_option(await get_help(ev.user_pm), buttons)


@sv_waves_help.on_fullmatch(("ヘルプ", "help"))
async def send_help_img_ja(bot: Bot, ev: Event):
    buttons: List[Any] = [
        WavesButton("ログイン", "登录"),
        WavesButton("確認", "查看"),
        WavesButton("切り替え", "切换"),
        WavesButton("スタミナ", "mr"),
        WavesButton("パネル更新", "刷新面板"),
        WavesButton("練度統計", "练度统计"),
    ]
    await bot.send_option(await get_help(ev.user_pm, lang="ja"), buttons)


@sv_waves_change_help.on_fullmatch((f"替换帮助", f"面板替换帮助"))
async def send_change_help_img(bot: Bot, ev: Event):
    await bot.send(await get_change_help(ev.user_pm))


@sv_waves_change_help.on_fullmatch(("置換ヘルプ", "パネル置換ヘルプ"))
async def send_change_help_img_ja(bot: Bot, ev: Event):
    await bot.send(await get_change_help(ev.user_pm, lang="ja"))


register_help("WutheringWavesUID", f"{PREFIX}帮助", Image.open(ICON))
