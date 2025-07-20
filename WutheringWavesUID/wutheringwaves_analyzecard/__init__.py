from gsuid_core.bot import Bot
from gsuid_core.sv import SV
from gsuid_core.models import Event

from .cardOCR import async_ocr
from .changeEcho import change_echo, change_weapon_resonLevel
import re
import asyncio
from async_timeout import timeout


waves_discord_bot_card_analyze = SV("waves分析discord_bot卡片")
waves_change_sonata_and_first_echo = SV("waves修改首位声骸与套装")
waves_change_weapon_reson_level = SV("waves修改武器精炼", priority=5, pm=1)


@waves_discord_bot_card_analyze.on_command(
    ("分析卡片", "卡片分析", "dc卡片", "fx", "分析"), block=True
)
async def analyze_card(bot: Bot, ev: Event):
    """处理 Discord 上的图片分析请求。"""
    # 指令与图片链接同时发送时
    if ev.text.strip():
        raw_data = ev.content[0].data

        # 直接匹配完整URL（直到遇到空格或右括号为止）
        url_pattern = r'https?://[^\s)>]+'  # 排除空格、右括号和大于号等常见终止符
        urls = re.findall(url_pattern, raw_data)

        first_url = urls[0] if urls else ""

        # 覆盖原数据
        ev.content[0].data = first_url
        await async_ocr(bot, ev)
        return

    # 指令与图片同时发送时
    if ev.image:
        await async_ocr(bot, ev)
        return

    try:
        at_sender = True if ev.group_id else False
        await bot.send("[鸣潮] 请在30秒内发送一张dc官方bot生成的卡片图或图片链接\n(分辨率尽可能为1920*1080，过低可能导致识别失败)", at_sender)
        async with timeout(30):
            while True:
                resp = await bot.receive_resp(timeout=30)
                if resp is not None:
                    ev = resp
                    break
    except asyncio.TimeoutError:
        await bot.send("[鸣潮] 等待超时，discord卡片分析已关闭", at_sender)
        return

    await async_ocr(bot, ev)

@waves_change_sonata_and_first_echo.on_regex(
    r"^改(?P<char>[\u4e00-\u9fa5]+?)(套装(?P<sonata>[0-9\u4e00-\u9fa5]+?)?)?(?P<echo>声骸.*)?$",
    block=False,
)
async def change_sonata_and_first_echo(bot: Bot, ev: Event):
    """处理国际服本地识别结果的声骸相关"""
    match = re.search(
        r"^.*改(?P<char>[\u4e00-\u9fa5]+?)(套装(?P<sonata>[0-9\u4e00-\u9fa5]+?)?)?(?P<echo>声骸.*)?$",
        ev.raw_text,
    )

    if not match:
        return
    ev.regex_dict = match.groupdict()

    await change_echo(bot, ev)

@waves_change_weapon_reson_level.on_regex(
    r"^改(\d+)([\u4e00-\u9fa5]+)?武器(\d+)$",
    block=False,
)
async def change_weapon_reson_level(bot: Bot, ev: Event):
    """处理国际服本地识别结果的武器精炼相关"""
    match = re.search(
        r"^.*改(?P<waves_id>\d+)(?P<char>[\u4e00-\u9fa5]+)?武器(?P<reson_level>(\d+))$",
        ev.raw_text,
    )
    if not match:
        return
    ev.regex_dict = match.groupdict()
    waves_id = ev.regex_dict.get("waves_id")
    char = ev.regex_dict.get("char")
    reson_level = int(ev.regex_dict.get("reson_level"))

    if not waves_id or len(waves_id) != 9:
        return await bot.send("[鸣潮] 输入用户uid有误! 参考命令：ww改123456789长离武器3")
    if char is  None:
        return await bot.send("[鸣潮] 未输入的角色名称有误! 参考命令：ww改uid(所有/长离)武器3")
    if reson_level < 1 or reson_level > 5:
        return await bot.send("[鸣潮] 输入的武器精炼等级有误!支持范围：[1,5] 参考命令：ww改uid长离武器3")

    img = await change_weapon_resonLevel(waves_id, char, reson_level)
    await bot.send(img)
