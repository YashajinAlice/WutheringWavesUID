from typing import Dict, List, Union

from gsuid_core.logger import logger
from gsuid_core.segment import MessageSegment

from ..utils.waves_api import waves_api
from ..utils.api.model import DailyData
from ..utils.database.models import WavesPush, WavesUser
from ..wutheringwaves_config import PREFIX, WutheringWavesConfig

import time
from datetime import datetime

async def get_notice_list() -> Dict[str, Dict[str, Dict]]:
    """获取推送列表"""
    if not WutheringWavesConfig.get_config("StaminaPush").data:
        return {}

    msg_dict = {"private_msg_dict": {}, "group_msg_dict": {}}

    user_list: List[WavesUser] = await WavesUser.get_all_push_user_list()
    logger.debug(f"[鸣潮] 推送列表: {user_list}")
    for user in user_list:
        if not user.uid or not user.cookie or user.status or not user.bot_id:
            continue

        push_data = await WavesPush.select_data_by_uid(user.uid)
        if push_data is None:
            continue

        await all_check(push_data.__dict__, msg_dict, user)

    return msg_dict


async def all_check(
    push_data: Dict, msg_dict: Dict[str, Dict[str, Dict]], user: WavesUser
):
    # 检查条件
    mode = "resin"
    status = "push_time"

    bot_id = user.bot_id
    uid = user.uid
    token = user.cookie


    # 当前时间
    time_now = int(time.time())
    dt = datetime.strptime(push_data[f"{status}_value"], "%Y-%m-%d %H:%M:%S")
    timestamp = int(dt.timestamp())

    _check = await check(
        time_now,
        timestamp,
    )

    if push_data[f"{mode}_is_push"] == "on":
        if WutheringWavesConfig.get_config("CrazyNotice").data:
            await WavesPush.update_data_by_uid(
                uid=uid, bot_id=bot_id, **{f"{mode}_is_push": "off"}
            )
            if _check:
                time_refresh = timestamp
                daily_info_res = await waves_api.get_daily_info(uid, token)
                if daily_info_res.success:
                    daily_info = DailyData.model_validate(daily_info_res.data)
                    refreshTimeStamp = daily_info.energyData.refreshTimeStamp
                    time_refresh = int(
                        refreshTimeStamp - (240 - push_data[f"{mode}_value"]) * 6 * 60
                    )

                extended_time = WutheringWavesConfig.get_config("StaminaRemindInterval").data # 分钟
                time_repush = timestamp + int(extended_time) * 60

                time_out = time_refresh if await check(time_refresh, time_repush) else time_repush
                time_push = datetime.fromtimestamp(time_out)
                await WavesPush.update_data_by_uid(
                    uid=uid, bot_id=bot_id, **{f"{status}_value": str(time_push)}
                )
                logger.info(f"催命模式设置成功!\n当前用户{uid} 体力提醒下一次推送时间:{time_push}\n")
            return

    # 准备推送
    if _check:
        if push_data[f"{mode}_push"] == "off":
            pass
        else:
            notice = "🌜你的结晶波片达到设定阈值啦！"
            msg_list = [
                MessageSegment.text("✅[鸣潮] 推送提醒:\n"),
                MessageSegment.text(notice),
                MessageSegment.text(
                    f"\n🕒当前体力阈值：{push_data[f'{mode}_value']}！\n"
                ),
                MessageSegment.text(
                    f"\n📅请清完体力后使用[{PREFIX}每日]来更新推送时间！\n"
                ),
            ]

            await save_push_data(mode, msg_list, push_data, msg_dict, user, True)


async def check(
    time: int,
    limit: int,
) -> Union[bool, int]:
    logger.info(f"{time} >?= {limit}")
    if time >= limit:
        return True
    else:
        return False


async def save_push_data(
    mode: str,
    msg_list: List,
    push_data: Dict,
    msg_dict: Dict[str, Dict[str, Dict]],
    user: WavesUser,
    is_need_save: bool = False,
):
    # 获取数据
    bot_id = user.bot_id
    qid = user.user_id
    uid = user.uid

    private_msgs: Dict = msg_dict["private_msg_dict"]
    group_data: Dict = msg_dict["group_msg_dict"]

    # on 推送到私聊
    if push_data[f"{mode}_push"] == "on":
        # 添加私聊信息
        if qid not in private_msgs:
            private_msgs[qid] = []

        private_msgs[qid].append({"bot_id": bot_id, "messages": msg_list})
    # 群号推送到群聊
    else:
        # 初始化
        gid = push_data[f"{mode}_push"]
        if gid not in group_data:
            group_data[gid] = []
        msg_list.append(MessageSegment.at(qid))
        group_data[gid].append({"bot_id": bot_id, "messages": msg_list})

    if is_need_save:
        await WavesPush.update_data_by_uid(
            uid=uid, bot_id=bot_id, **{f"{mode}_is_push": "on"}
        )
