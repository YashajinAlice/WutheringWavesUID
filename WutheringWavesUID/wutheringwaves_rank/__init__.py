import re

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger

from .darw_rank_card import draw_rank_img
from .slash_rank import draw_all_slash_rank_card
from .draw_all_rank_card import draw_all_rank_card
from ..wutheringwaves_config import WutheringWavesConfig
from .slash_rank_international import draw_international_slash_rank_card
from .draw_international_total_rank import draw_international_total_rank_img
from .draw_bot_rank_card import draw_bot_rank_img, draw_bot_rank_img_by_chain

sv_waves_rank_list = SV("ww角色排行")
sv_waves_rank_all_list = SV("ww角色总排行", priority=1)
sv_waves_rank_bot_list = SV("ww角色bot排行", priority=1)
sv_waves_rank_international = SV("ww國際服排行", priority=0)
sv_waves_slash_international = SV("ww无尽bot排行", priority=1)
sv_waves_slash_rank = SV("ww无尽排行", priority=1)


@sv_waves_rank_list.on_regex("^[\u4e00-\u9fa5]+(?:排行|排名)$", block=True)
async def send_rank_card(bot: Bot, ev: Event):
    # 正则表达式
    match = re.search(r"(?P<char>[\u4e00-\u9fa5]+)(?:排行|排名)", ev.raw_text)
    if not match:
        return
    ev.regex_dict = match.groupdict()
    char = match.group("char")

    if not ev.group_id:
        return await bot.send("请在群聊中使用")

    if not char:
        return

    rank_type = "伤害"
    if "评分" in char:
        rank_type = "评分"
    char = char.replace("伤害", "").replace("评分", "")

    im = await draw_rank_img(bot, ev, char, rank_type)

    if isinstance(im, str):
        at_sender = True if ev.group_id else False
        await bot.send(im, at_sender)
    if isinstance(im, bytes):
        await bot.send(im)


@sv_waves_rank_bot_list.on_regex("^[\u4e00-\u9fa5]+(?:bot排行|bot排名)$", block=True)
async def send_bot_rank_card(bot: Bot, ev: Event):
    botData = WutheringWavesConfig.get_config("botData").data
    if not botData:
        return await bot.send("[鸣潮] 未开启bot排行")
    # 正则表达式
    match = re.search(
        r"(?P<char>[\u4e00-\u9fa5]+)(?:bot排行|bot排名)",
        ev.raw_text,
    )
    if not match:
        return
    ev.regex_dict = match.groupdict()
    char = match.group("char")

    if not char:
        return

    rank_type = "伤害"
    if "评分" in char:
        rank_type = "评分"
    char = char.replace("伤害", "").replace("评分", "")

    im = await draw_bot_rank_img(bot, ev, char, rank_type)

    if isinstance(im, str):
        at_sender = True if ev.group_id else False
        await bot.send(im, at_sender)
    if isinstance(im, bytes):
        await bot.send(im)


@sv_waves_rank_bot_list.on_regex(
    r"^[\u4e00-\u9fa5]+(?:\d+链)(?:bot排行|bot排名)$", block=True
)
async def send_bot_rank_card_by_chain(bot: Bot, ev: Event):
    """按鏈數顯示bot排行"""
    botData = WutheringWavesConfig.get_config("botData").data
    if not botData:
        return await bot.send("[鸣潮] 未开启bot排行")

    # 正则表达式匹配 {角色}{鏈數}鏈bot排行
    match = re.search(
        r"(?P<char>[\u4e00-\u9fa5]+)(?P<chain>\d+)链(?:bot排行|bot排名)",
        ev.raw_text,
    )
    if not match:
        return

    char = match.group("char")
    chain = int(match.group("chain"))

    if not char:
        return

    if chain < 0 or chain > 6:
        return await bot.send("[鸣潮] 鏈數必須在0-6之間")

    rank_type = "伤害"
    if "评分" in char:
        rank_type = "评分"
    char = char.replace("伤害", "").replace("评分", "")

    im = await draw_bot_rank_img_by_chain(bot, ev, char, rank_type, chain)

    if isinstance(im, str):
        at_sender = True if ev.group_id else False
        await bot.send(im, at_sender)
    if isinstance(im, bytes):
        await bot.send(im)


@sv_waves_rank_all_list.on_regex(
    "^[\u4e00-\u9fa5]+(?:总排行|总排名)(\d+)?$", block=True
)
async def send_all_rank_card(bot: Bot, ev: Event):
    # 正则表达式
    match = re.search(
        r"(?P<char>[\u4e00-\u9fa5]+)(?:总排行|总排名)(?P<pages>(\d+))?",
        ev.raw_text,
    )
    if not match:
        return
    ev.regex_dict = match.groupdict()
    char = match.group("char")
    pages = match.group("pages")

    if not char:
        return

    if pages:
        pages = int(pages)
    else:
        pages = 1

    if pages > 5:
        pages = 5
    elif pages < 1:
        pages = 1

    rank_type = "伤害"
    if "评分" in char:
        rank_type = "评分"
    char = char.replace("伤害", "").replace("评分", "")

    im = await draw_all_rank_card(bot, ev, char, rank_type, pages)

    if isinstance(im, str):
        at_sender = True if ev.group_id else False
        await bot.send(im, at_sender)
    if isinstance(im, bytes):
        await bot.send(im)


@sv_waves_rank_international.on_regex(
    r"^[\u4e00-\u9fa5]+(?:总排|总行|總排|總行)(\d+)?$",
    block=True,
)
async def send_international_total_rank_card(bot: Bot, ev: Event):
    """國際服總排行指令"""
    if not ev.group_id:
        return await bot.send("请在群聊中使用")

    botData = WutheringWavesConfig.get_config("botData").data
    if not botData:
        return await bot.send("[鸣潮] 未开启bot排行")

    # 正则表达式
    match = re.search(
        r"(?P<char>[\u4e00-\u9fa5]+)(?:总排|总行|總排|總行)(?P<pages>(\d+))?",
        ev.raw_text,
    )
    if not match:
        return
    ev.regex_dict = match.groupdict()
    char = match.group("char")
    pages = match.group("pages")

    if not char:
        return

    if pages:
        pages = int(pages)
    else:
        pages = 1

    if pages > 5:
        pages = 5
    elif pages < 1:
        pages = 1

    rank_type = "伤害"
    if "评分" in char:
        rank_type = "评分"
    char = char.replace("伤害", "").replace("评分", "")

    im = await draw_international_total_rank_img(bot, ev, char, rank_type, pages)

    if isinstance(im, str):
        at_sender = True if ev.group_id else False
        await bot.send(im, at_sender=at_sender)
    else:
        at_sender = True if ev.group_id else False
        await bot.send(im, at_sender=at_sender)


@sv_waves_slash_international.on_regex("^无尽排行$", block=True)
async def send_international_slash_rank_card(bot: Bot, ev: Event):
    """国际服无尽bot排行指令"""
    if not ev.group_id:
        return await bot.send("请在群聊中使用")

    # 解析页数参数
    match = re.search(r"(\d+)", ev.raw_text)
    if match:
        limit = int(match.group(1))
    else:
        limit = 20

    limit = max(limit, 1)  # 最小为1
    limit = min(limit, 50)  # 最大为50

    try:
        im = await draw_international_slash_rank_card(bot, ev, limit)

        if isinstance(im, str):
            at_sender = True if ev.group_id else False
            await bot.send(im, at_sender)
        if isinstance(im, bytes):
            await bot.send(im)
    except Exception as e:
        logger.exception(f"国际服无尽排行卡片生成失败: {e}")
        await bot.send("国际服无尽排行卡片生成失败，请检查API服务是否正常运行")


@sv_waves_slash_rank.on_regex("^无尽排名$", block=True)
async def send_slash_rank_card(bot: Bot, ev: Event):
    """无尽排名指令"""
    if not ev.group_id:
        return await bot.send("请在群聊中使用")

    try:
        im = await draw_all_slash_rank_card(bot, ev)

        if isinstance(im, str):
            at_sender = True if ev.group_id else False
            await bot.send(im, at_sender)
        if isinstance(im, bytes):
            await bot.send(im)
    except Exception as e:
        logger.exception(f"无尽排行卡片生成失败: {e}")
        await bot.send("无尽排行卡片生成失败，请检查API服务是否正常运行")
