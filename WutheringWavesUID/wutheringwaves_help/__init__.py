from typing import Any, List

from PIL import Image
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.help.utils import register_help
from gsuid_core.sv import SV, get_plugin_available_prefix

from .get_help import ICON, get_help
from ..utils.button import WavesButton
from .change_help import get_change_help

PREFIX = get_plugin_available_prefix("WutheringWavesUID")

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

    # 檢查是否為Premium用戶，添加Premium專用按鈕
    try:
        from ..wutheringwaves_payment.payment_manager import payment_manager

        if payment_manager.is_premium_user(str(ev.user_id)):
            buttons.extend(
                [
                    WavesButton("Premium綁定狀態", "Premium綁定狀態"),
                    WavesButton("Premium設置", "Premium設置"),
                ]
            )
    except ImportError:
        pass
    except Exception:
        pass

    await bot.send_option(await get_help(ev.user_pm), buttons)


@sv_waves_change_help.on_fullmatch((f"替换帮助", f"面板替换帮助"))
async def send_change_help_img(bot: Bot, ev: Event):
    await bot.send(await get_change_help(ev.user_pm))


register_help("WutheringWavesUID", f"{PREFIX}帮助", Image.open(ICON))
