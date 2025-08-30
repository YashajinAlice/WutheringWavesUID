import re
from typing import Any, List

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger

from ..utils.button import WavesButton
from ..wutheringwaves_config import PREFIX
from .simulator_logic import GachaSimulator
from .draw_simulator_card import SimulatorCardDrawer

sv_simulator = SV("waves模拟抽卡")
sv_simulator_help = SV("waves模拟抽卡帮助")


@sv_simulator.on_regex(r"^(～|~|鸣潮)?(武器)?(十连|单抽)$", block=True)
async def simulator(bot: Bot, ev: Event):
    """模拟抽卡"""
    try:
        logger.info("[鸣潮]开始执行 模拟抽卡")

        # 解析命令
        msg = ev.raw_text
        gacha_type = "weapon" if "武器" in msg else "role"
        is_single = "单抽" in msg

        # 创建模拟器
        simulator = GachaSimulator()
        drawer = SimulatorCardDrawer()

        # 获取用户名
        user_name = ev.sender.get("nickname", "未知用户") if ev.sender else "未知用户"

        if is_single:
            # 执行单抽
            gacha_results = await simulator.simulate_single_gacha(
                str(ev.user_id), gacha_type
            )
            # 获取用户数据
            user_data = simulator.get_user_data(str(ev.user_id), gacha_type)
            # 获取池子名称
            config = (
                simulator.role_config
                if gacha_type == "role"
                else simulator.weapon_config
            )
            pool_name = config["pool_name"]
            # 绘制卡片
            card_bytes = await drawer.draw_single_simulator_card(
                gacha_results[0],
                pool_name,
                user_name,
                user_data["five_star_time"],
            )
        else:
            # 执行十连抽卡
            gacha_results = await simulator.simulate_gacha(str(ev.user_id), gacha_type)
            # 获取用户数据
            user_data = simulator.get_user_data(str(ev.user_id), gacha_type)
            # 获取池子名称
            config = (
                simulator.role_config
                if gacha_type == "role"
                else simulator.weapon_config
            )
            pool_name = config["pool_name"]
            # 绘制卡片
            card_bytes = await drawer.draw_simulator_card(
                gacha_results,
                pool_name,
                user_name,
                user_data["five_star_time"],
            )

        # 发送结果
        await bot.send(card_bytes)
        return True

    except Exception as e:
        logger.exception(f"模拟抽卡失败: {e}")
        await bot.send("模拟抽卡失败，请稍后再试")
        return False


@sv_simulator_help.on_fullmatch("模拟抽卡帮助")
async def send_simulator_help(bot: Bot, ev: Event):
    """发送模拟抽卡帮助"""
    help_text = f"""
【鸣潮模拟抽卡】使用说明

📋 指令列表：
• {PREFIX}十连 - 角色十连抽卡
• {PREFIX}武器十连 - 武器十连抽卡
• {PREFIX}单抽 - 角色单抽
• {PREFIX}武器单抽 - 武器单抽
• {PREFIX}模拟抽卡帮助 - 查看帮助

🎯 功能特点：
• 完全模拟真实抽卡概率
• 支持大小保底机制
• 记录用户抽卡历史
• 生成精美抽卡结果图

💡 使用提示：
• 每次抽卡都会记录保底进度
• 支持角色池和武器池
• 概率完全按照官方设定
"""
    await bot.send(help_text)
