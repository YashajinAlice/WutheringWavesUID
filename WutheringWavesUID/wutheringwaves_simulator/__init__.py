import re
from typing import Any, List

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ..utils.button import WavesButton
from ..wutheringwaves_config import PREFIX
from .simulator_core import simulate_gacha
from .draw_simulator import draw_simulator_card

sv_simulator = SV("waves模擬抽卡", area="GROUP")


@sv_simulator.on_fullmatch(("十連", "十连", "抽卡", "模擬抽卡", "模拟抽卡"))
async def send_simulator_gacha(bot: Bot, ev: Event):
    """模擬抽卡"""
    await bot.logger.info("[鳴潮] 開始執行模擬抽卡")

    # 判斷是角色還是武器抽卡（默認角色）
    gacha_type = "role"

    # 執行抽卡
    gacha_result = await simulate_gacha(ev.user_id, ev.bot_id, gacha_type)

    if not gacha_result:
        return await bot.send("模擬抽卡失敗，請稍後再試")

    # 繪製卡片
    # 獲取用戶名稱，sender 可能是字典
    user_name = "未知用戶"
    if ev.sender:
        if isinstance(ev.sender, dict):
            user_name = ev.sender.get(
                "nickname", ev.sender.get("user_name", "未知用戶")
            )
        else:
            user_name = getattr(
                ev.sender, "nickname", getattr(ev.sender, "user_name", "未知用戶")
            )

    img = await draw_simulator_card(gacha_result, user_name)

    if isinstance(img, str):
        await bot.send(img)
    else:
        buttons: List[Any] = [WavesButton("再次抽卡", "十連")]
        await bot.send_option(img, buttons)


@sv_simulator.on_fullmatch(("武器十連", "武器十连", "武器抽卡"))
async def send_weapon_simulator_gacha(bot: Bot, ev: Event):
    """武器模擬抽卡"""
    await bot.logger.info("[鳴潮] 開始執行武器模擬抽卡")

    gacha_type = "weapon"

    # 執行抽卡
    gacha_result = await simulate_gacha(ev.user_id, ev.bot_id, gacha_type)

    if not gacha_result:
        return await bot.send("模擬抽卡失敗，請稍後再試")

    # 繪製卡片
    # 獲取用戶名稱，sender 可能是字典
    user_name = "未知用戶"
    if ev.sender:
        if isinstance(ev.sender, dict):
            user_name = ev.sender.get(
                "nickname", ev.sender.get("user_name", "未知用戶")
            )
        else:
            user_name = getattr(
                ev.sender, "nickname", getattr(ev.sender, "user_name", "未知用戶")
            )

    img = await draw_simulator_card(gacha_result, user_name)

    if isinstance(img, str):
        await bot.send(img)
    else:
        buttons: List[Any] = [WavesButton("再次抽卡", "武器十連")]
        await bot.send_option(img, buttons)
