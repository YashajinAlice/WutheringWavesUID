import random
import asyncio

import httpx
from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.aps import scheduler
from gsuid_core.logger import logger
from gsuid_core.subscribe import gs_subscribe

from ..utils.waves_api import waves_api
from .ann_card import ann_list_card, ann_detail_card
from ..wutheringwaves_config import WutheringWavesConfig

sv_ann = SV("鸣潮公告")
sv_ann_sub = SV("订阅鸣潮公告", pm=3)

task_name_ann = "订阅鸣潮公告"
ann_minute_check: int = WutheringWavesConfig.get_config("AnnMinuteCheck").data

# Discord webhook URL for announcement
DISCORD_ANN_WEBHOOK_URL = "https://discord.com/api/webhooks/1400434071498395798/zuB4ZASdnchG3pfkwNWb59F1OL1YIXWM75lNsASiYaio88mZ8iz31_Nj0svu4e5iTeHC"


async def send_discord_webhook_image(img: bytes):
    """使用 Discord webhook 發送圖片"""
    try:
        async with httpx.AsyncClient() as client:
            files = {"file": ("announcement.png", img, "image/png")}
            response = await client.post(
                DISCORD_ANN_WEBHOOK_URL,
                files=files,
                timeout=30.0,
            )
            response.raise_for_status()
            logger.info("[Discord公告推送] 發送成功")
            return True
    except Exception as e:
        logger.exception(f"[Discord公告推送] 發送失敗: {e}")
        return False


@sv_ann.on_command("公告")
async def ann_(bot: Bot, ev: Event):
    ann_id = ev.text
    if not ann_id:
        img = await ann_list_card()
        return await bot.send(img)

    ann_id = ann_id.replace("#", "")
    if not ann_id.isdigit():
        raise Exception("公告ID不正确")

    img = await ann_detail_card(int(ann_id))
    return await bot.send(img)  # type: ignore


@sv_ann_sub.on_fullmatch("订阅公告")
async def sub_ann_(bot: Bot, ev: Event):
    # 允許 Discord 訂閱（移除 onebot 限制）
    if ev.group_id is None:
        return await bot.send("请在群聊中订阅")
    if not WutheringWavesConfig.get_config("WavesAnnOpen").data:
        return await bot.send("鸣潮公告推送功能已关闭")

    data = await gs_subscribe.get_subscribe(task_name_ann)
    if data:
        for subscribe in data:
            # 檢查 bot_id 和 group_id 是否相同
            if (
                hasattr(subscribe, "bot_id")
                and subscribe.bot_id == ev.bot_id
                and subscribe.group_id == ev.group_id
            ):
                return await bot.send("已经订阅了鸣潮公告！")
            # 兼容舊的檢查方式（僅檢查 group_id）
            elif hasattr(subscribe, "group_id") and subscribe.group_id == ev.group_id:
                # 如果是 onebot 且已有訂閱，則不重複訂閱
                if ev.bot_id == "onebot":
                    return await bot.send("已经订阅了鸣潮公告！")

    await gs_subscribe.add_subscribe(
        "session",
        task_name=task_name_ann,
        event=ev,
        extra_message="",
    )

    logger.info(data)
    await bot.send("成功订阅鸣潮公告!")


@sv_ann_sub.on_fullmatch(("取消订阅公告", "取消公告", "退订公告"))
async def unsub_ann_(bot: Bot, ev: Event):
    # 允許 Discord 取消訂閱（移除 onebot 限制）
    if ev.group_id is None:
        return await bot.send("请在群聊中取消订阅")

    data = await gs_subscribe.get_subscribe(task_name_ann)
    if data:
        for subscribe in data:
            # 檢查 bot_id 和 group_id 是否相同
            if (
                hasattr(subscribe, "bot_id")
                and subscribe.bot_id == ev.bot_id
                and subscribe.group_id == ev.group_id
            ):
                await gs_subscribe.delete_subscribe("session", task_name_ann, ev)
                return await bot.send("成功取消订阅鸣潮公告!")
            # 兼容舊的檢查方式（僅檢查 group_id，且 bot_id 為 onebot）
            elif (
                hasattr(subscribe, "group_id")
                and subscribe.group_id == ev.group_id
                and ev.bot_id == "onebot"
            ):
                await gs_subscribe.delete_subscribe("session", task_name_ann, ev)
                return await bot.send("成功取消订阅鸣潮公告!")
    else:
        if not WutheringWavesConfig.get_config("WavesAnnOpen").data:
            return await bot.send("鸣潮公告推送功能已关闭")

    return await bot.send("未曾订阅鸣潮公告！")


@scheduler.scheduled_job("interval", minutes=ann_minute_check)
async def check_waves_ann():
    if not WutheringWavesConfig.get_config("WavesAnnOpen").data:
        return
    await check_waves_ann_state()


async def check_waves_ann_state():
    logger.info("[鸣潮公告] 定时任务: 鸣潮公告查询..")
    datas = await gs_subscribe.get_subscribe(task_name_ann)
    if not datas:
        logger.info("[鸣潮公告] 暂无群订阅")
        return

    ids = WutheringWavesConfig.get_config("WavesAnnNewIds").data
    new_ann_list = await waves_api.get_ann_list()
    if not new_ann_list:
        return

    new_ann_ids = [x["id"] for x in new_ann_list]
    if not ids:
        WutheringWavesConfig.set_config("WavesAnnNewIds", new_ann_ids)
        logger.info("[鸣潮公告] 初始成功, 将在下个轮询中更新.")
        return

    new_ann_need_send = []
    for ann_id in new_ann_ids:
        if ann_id not in ids:
            new_ann_need_send.append(ann_id)

    if not new_ann_need_send:
        logger.info("[鸣潮公告] 没有最新公告")
        return

    logger.info(f"[鸣潮公告] 更新公告id: {new_ann_need_send}")
    save_ids = sorted(ids, reverse=True)[:50] + new_ann_ids
    WutheringWavesConfig.set_config("WavesAnnNewIds", list(set(save_ids)))

    for ann_id in new_ann_need_send:
        try:
            img = await ann_detail_card(ann_id, is_check_time=True)
            if isinstance(img, str):
                continue

            # ann_detail_card 可能返回 bytes, List[bytes]
            img_list = []
            if isinstance(img, bytes):
                img_list = [img]
            elif isinstance(img, list):
                img_list = [i for i in img if isinstance(i, bytes)]
            else:
                continue

            if not img_list:
                continue

            for subscribe in datas:
                # 檢查是否是 Discord bot 訂閱
                bot_id = getattr(subscribe, "bot_id", None)
                if bot_id and bot_id != "onebot":
                    # Discord 或其他非 onebot，使用 webhook 發送
                    logger.info(f"[鸣潮公告] 使用 webhook 推送給 Discord bot: {bot_id}")
                    for img_bytes in img_list:
                        await send_discord_webhook_image(img_bytes)
                        await asyncio.sleep(random.uniform(0.5, 1.5))
                    await asyncio.sleep(random.uniform(1, 3))
                else:
                    # onebot 或其他，使用原本的方式發送
                    await subscribe.send(img)  # type: ignore
                    await asyncio.sleep(random.uniform(1, 3))
        except Exception as e:
            logger.exception(e)

    logger.info("[鸣潮公告] 推送完毕")
