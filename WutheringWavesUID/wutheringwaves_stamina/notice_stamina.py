import time
from datetime import datetime
from typing import Dict, List, Union

from gsuid_core.logger import logger
from gsuid_core.segment import MessageSegment

from ..utils.api.model import DailyData
from ..utils.waves_api import waves_api
from ..utils.database.models import WavesPush, WavesUser
from ..wutheringwaves_config import PREFIX, WutheringWavesConfig


async def get_notice_list() -> Dict[str, Dict[str, Dict]]:
    """获取推送列表"""
    # 檢查全局配置
    global_push_enabled = WutheringWavesConfig.get_config("StaminaPush").data
    logger.info(f"[鸣潮] 全局体力推送状态: {global_push_enabled}")

    msg_dict = {"private_msg_dict": {}, "group_msg_dict": {}}

    user_list: List[WavesUser] = await WavesUser.get_all_push_user_list()
    logger.info(f"[鸣潮] 推送用户列表: {len(user_list)} 个用户")

    # 檢查是否有國際服用戶
    has_international_users = False
    international_count = 0
    for user in user_list:
        if user.uid and user.uid.isdigit() and int(user.uid) >= 200000000:
            has_international_users = True
            international_count += 1
        elif user.platform and user.platform.startswith("international_"):
            has_international_users = True
            international_count += 1
        elif user.cookie and len(user.cookie) > 20:
            has_international_users = True
            international_count += 1

    logger.info(f"[鸣潮] 国际服用户数量: {international_count}")

    # 如果有國際服用戶，允許推送（跳過全局配置檢查）
    if has_international_users:
        logger.info("[鸣潮] 检测到国际服用户，允许推送")
    elif not global_push_enabled:
        logger.info("[鸣潮] 全局体力推送已禁用且无国际服用户")
        return {}

    for user in user_list:
        if not user.uid or not user.cookie or user.status or not user.bot_id:
            logger.debug(f"[鸣潮] 跳过用户 {user.uid}: 缺少必要信息")
            continue

        push_data = await WavesPush.select_data_by_uid(user.uid)
        if push_data is None:
            logger.debug(f"[鸣潮] 跳过用户 {user.uid}: 无推送数据")
            continue

        logger.info(f"[鸣潮] 检查用户 {user.uid} 的体力推送")
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

    # 檢查是否為國際服用戶
    is_international = False
    if user.platform and user.platform.startswith("international_"):
        is_international = True
    elif user.uid and user.uid.isdigit() and int(user.uid) >= 200000000:
        is_international = True
    elif user.cookie and len(user.cookie) > 20:
        is_international = True

    if is_international:
        # 国际服体力查询
        logger.info(f"[鸣潮][推送] 国际服用户 {user.uid} 开始体力检查")
        await check_international_stamina(push_data, msg_dict, user)
    else:
        # 国服体力查询
        logger.info(f"[鸣潮][推送] 国服用户 {user.uid} 开始体力检查")
        await check_domestic_stamina(push_data, msg_dict, user)


async def check_international_stamina(
    push_data: Dict, msg_dict: Dict[str, Dict[str, Dict]], user: WavesUser
):
    """检查国际服体力"""
    mode = "resin"
    status = "push_time"

    logger.info(f"[鸣潮][国际服推送] 开始检查用户 {user.uid} 的体力")
    logger.info(f"[鸣潮][国际服推送] 推送数据: {push_data}")

    try:
        # 使用 kuro.py 获取国际服体力信息
        import kuro
        from kuro.types import Region

        client = kuro.Client(region=Region.OVERSEAS)

        # 生成 OAuth code
        logger.info(f"[鸣潮][国际服推送] 生成 OAuth code...")
        oauth_code = await client.generate_oauth_code(user.cookie)
        logger.info(f"[鸣潮][国际服推送] OAuth code 生成成功")

        # 从 platform 字段中提取服务器区域
        server_region = "Asia"  # 默认值
        if user.platform and user.platform.startswith("international_"):
            server_region = user.platform.replace("international_", "")
            logger.info(f"[鸣潮][国际服推送] 使用服务器区域: {server_region}")

        # 获取角色信息
        logger.info(f"[鸣潮][国际服推送] 获取角色信息...")
        role_info = await client.get_player_role(
            oauth_code, int(user.uid), server_region
        )
        basic_info = role_info.basic
        logger.info(f"[鸣潮][国际服推送] 角色信息获取成功")

        # 检查体力是否达到阈值
        current_stamina = basic_info.waveplates
        max_stamina = basic_info.max_waveplates
        threshold = push_data[f"{mode}_value"]

        logger.info(
            f"[鸣潮][国际服推送] UID: {user.uid}, 当前体力: {current_stamina}/{max_stamina}, 阈值: {threshold}"
        )

        if current_stamina >= threshold:
            logger.info(f"[鸣潮][国际服推送] 体力达到阈值，准备推送")
            # 体力达到阈值，准备推送
            await send_push_notification(
                push_data, msg_dict, user, current_stamina, max_stamina
            )
        else:
            logger.info(f"[鸣潮][国际服推送] 体力未达到阈值，跳过推送")

    except Exception as e:
        logger.error(f"[鸣潮][国际服推送] 获取体力信息失败: {e}")
        import traceback

        logger.error(f"[鸣潮][国际服推送] 错误详情: {traceback.format_exc()}")


async def check_domestic_stamina(
    push_data: Dict, msg_dict: Dict[str, Dict[str, Dict]], user: WavesUser
):
    """检查国服体力"""
    mode = "resin"
    status = "push_time"

    # 当前时间
    time_now = int(time.time())
    dt = datetime.strptime(push_data[f"{status}_value"], "%Y-%m-%d %H:%M:%S")
    timestamp = int(dt.timestamp())

    _check = await check(time_now, timestamp)

    if push_data[f"{mode}_is_push"] == "on":
        # 催命模式已推送，直接返回避免重複推送
        return

    # 准备推送
    if _check:
        if push_data[f"{mode}_push"] == "off":
            pass
        else:
            # 統一推送到指定 Discord 頻道
            notice = "🌜你的结晶波片达到设定阈值啦！"
            msg_list = [
                MessageSegment.text("✅[鸣潮] 体力推送提醒\n"),
                MessageSegment.text(notice),
                MessageSegment.text(
                    f"\n🕒当前体力阈值：{push_data[f'{mode}_value']}！\n"
                ),
                MessageSegment.text(
                    f"\n📅请清完体力后使用[{PREFIX}每日]来更新推送时间！\n"
                ),
            ]

            await save_push_data_unified(
                mode, msg_list, push_data, msg_dict, user, True
            )


async def send_push_notification(
    push_data: Dict,
    msg_dict: Dict[str, Dict[str, Dict]],
    user: WavesUser,
    current_stamina: int,
    max_stamina: int,
):
    """发送推送通知"""
    mode = "resin"

    logger.info(f"[鸣潮][推送通知] 开始发送推送通知给用户 {user.uid}")

    # 检查是否已经推送过
    if push_data[f"{mode}_is_push"] == "on":
        logger.info(f"[鸣潮][推送通知] UID: {user.uid} 已推送过，跳过")
        return

    # 統一推送到指定 Discord 頻道
    notice = "🌜你的结晶波片达到设定阈值啦！"
    msg_list = [
        MessageSegment.text("✅[鸣潮] 体力推送提醒\n"),
        MessageSegment.text(notice),
        MessageSegment.text(f"\n🕒当前体力：{current_stamina}/{max_stamina}！\n"),
        MessageSegment.text(f"\n📅请清完体力后使用[{PREFIX}每日]来更新推送时间！\n"),
    ]

    logger.info(f"[鸣潮][推送通知] 准备发送消息: {msg_list}")
    await save_push_data_unified(mode, msg_list, push_data, msg_dict, user, True)
    logger.info(f"[鸣潮][推送通知] 推送通知发送完成")


async def check(
    time: int,
    limit: int,
) -> Union[bool, int]:
    logger.info(f"{time} >?= {limit}")
    if time >= limit:
        return True
    else:
        return False


async def save_push_data_unified(
    mode: str,
    msg_list: List,
    push_data: Dict,
    msg_dict: Dict[str, Dict[str, Dict]],
    user: WavesUser,
    is_need_save: bool = False,
):
    """統一推送到指定 Discord 頻道"""
    # 获取数据
    bot_id = user.bot_id
    qid = user.user_id
    uid = user.uid

    logger.info(
        f"[鸣潮][推送保存] 开始保存推送数据: UID={uid}, BotID={bot_id}, UserID={qid}"
    )

    # 統一推送到指定頻道
    UNIFIED_CHANNEL_ID = "1421047419348451422"

    # 添加 @用戶 到消息
    msg_list_with_at = [MessageSegment.at(qid), *msg_list]  # 艾特用戶

    # 添加到統一頻道
    group_data: Dict = msg_dict["group_msg_dict"]
    if UNIFIED_CHANNEL_ID not in group_data:
        group_data[UNIFIED_CHANNEL_ID] = []

    group_data[UNIFIED_CHANNEL_ID].append(
        {"bot_id": bot_id, "messages": msg_list_with_at}
    )

    logger.info(f"[鸣潮][推送保存] 消息已添加到推送队列: {UNIFIED_CHANNEL_ID}")

    if is_need_save:
        logger.info(f"[鸣潮][推送保存] 更新推送状态: {mode}_is_push=on")
        await WavesPush.update_data_by_uid(
            uid=uid, bot_id=bot_id, **{f"{mode}_is_push": "on"}
        )
        logger.info(f"[鸣潮][推送保存] 推送状态更新完成")


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
