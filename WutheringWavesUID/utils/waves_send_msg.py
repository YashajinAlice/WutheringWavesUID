import random
import asyncio

import httpx
from gsuid_core.gss import gss
from gsuid_core.logger import logger
from gsuid_core.segment import MessageSegment
from gsuid_core.subscribe import gs_subscribe
from gsuid_core.utils.database.models import Subscribe
from gsuid_core.utils.boardcast.models import BoardCastMsgDict

task_name_resin = "订阅体力推送"
board_type = {
    "resin": task_name_resin,
}

# Discord webhook URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1421163052702765248/txQGOc76lKGy-rNWCm4k-AiJqfpG-DX6nyU7O1X6dlpyuTOi7Y5wQjVjpPxuU6EhxNOC"


def extract_text_from_messages(messages: list) -> str:
    """將 MessageSegment 列表轉換為純文字字串"""
    text_parts = []
    for msg in messages:
        if isinstance(msg, MessageSegment):
            # MessageSegment 結構：Message(type='text', data='...')
            if hasattr(msg, "type") and msg.type == "text":
                # 文字類型，從 data 屬性獲取文字內容
                if hasattr(msg, "data") and isinstance(msg.data, str):
                    text_parts.append(msg.data)
                else:
                    # data 不存在或不是字串，嘗試轉換
                    text_parts.append(str(getattr(msg, "data", "")))
            else:
                # 非文字類型，跳過或轉換為字串
                if hasattr(msg, "data"):
                    text_parts.append(str(msg.data))
                else:
                    text_parts.append(str(msg))
        elif isinstance(msg, str):
            text_parts.append(msg)
        else:
            text_parts.append(str(msg))
    return "".join(text_parts)


async def send_discord_webhook(content: str):
    """使用 Discord webhook 發送訊息"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                DISCORD_WEBHOOK_URL,
                json={"content": content},
                timeout=10.0,
            )
            response.raise_for_status()
            logger.info(f"[Discord推送] 發送成功: {content[:50]}...")
            return True
    except Exception as e:
        logger.exception(f"[Discord推送] 發送失敗: {e}")
        return False


async def send_board_cast_msg(msgs: BoardCastMsgDict, board_cast_type: str):
    logger.info(f"[推送] {board_cast_type} 任务启动...")
    private_msg_list = msgs["private_msg_dict"]
    group_msg_list = msgs["group_msg_dict"]

    subs = await gs_subscribe.get_subscribe(board_type[board_cast_type])

    def get_bot_self_id(qid, bot_id, target_type, group_id):
        if not subs:
            return ""
        for sub in subs:
            sub: Subscribe
            if sub.user_type != target_type:
                continue
            if target_type == "direct":
                if sub.user_id == qid and sub.bot_id == bot_id:
                    return sub.bot_self_id

            if target_type == "group":
                if sub.group_id == group_id and sub.bot_id == bot_id:
                    return sub.bot_self_id
        return ""

    # 执行私聊推送 - 使用 webhook 發送
    for qid in private_msg_list:
        try:
            for bot_id in gss.active_bot:
                for single in private_msg_list[qid]:
                    # 原本的邏輯：獲取 bot_self_id（保持邏輯不變）
                    bot_self_id = get_bot_self_id(qid, single["bot_id"], "direct", "")
                    # 改為：將訊息轉換為文字並用 webhook 發送
                    content = extract_text_from_messages(single["messages"])
                    if content:
                        await send_discord_webhook(content)
                        await asyncio.sleep(0.5 + random.randint(1, 3))
        except Exception as e:
            logger.exception(f"[推送] {qid} 私聊推送失败!错误信息", e)
        await asyncio.sleep(0.5 + random.randint(1, 3))
    logger.info(f"[推送] {board_cast_type} 私聊推送完成!")

    # 执行群聊推送 - 使用 webhook 發送
    for gid in group_msg_list:
        try:
            for bot_id in gss.active_bot:
                if isinstance(group_msg_list[gid], list):
                    for group in group_msg_list[gid]:
                        # 原本的邏輯：獲取 bot_self_id（保持邏輯不變）
                        bot_self_id = get_bot_self_id("", group["bot_id"], "group", gid)  # type: ignore
                        # 改為：將訊息轉換為文字並用 webhook 發送
                        content = extract_text_from_messages(group["messages"])  # type: ignore
                        if content:
                            await send_discord_webhook(content)
                            await asyncio.sleep(0.5 + random.randint(1, 3))
                else:
                    # 原本的邏輯：獲取 bot_self_id（保持邏輯不變）
                    bot_self_id = get_bot_self_id(
                        "", group_msg_list[gid]["bot_id"], "group", gid
                    )
                    # 改為：將訊息轉換為文字並用 webhook 發送
                    content = extract_text_from_messages(
                        group_msg_list[gid]["messages"]
                    )
                    if content:
                        await send_discord_webhook(content)
                        await asyncio.sleep(0.5 + random.randint(1, 3))
        except Exception as e:
            logger.exception(f"[推送] 群 {gid} 推送失败!错误信息", e)
        await asyncio.sleep(0.5 + random.randint(1, 3))
    logger.info(f"[推送] {board_cast_type} 群聊推送完成!")
    logger.info(f"[推送] {board_cast_type} 任务结束!")
