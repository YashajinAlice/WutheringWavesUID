import time
import asyncio
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

    # 直接從 WavesPush 表獲取需要推送的用戶
    push_list = await WavesPush.get_all_push_user_list()
    logger.info(f"[鸣潮] 推送用户列表: {len(push_list)} 个用户")

    # 獲取對應的 WavesUser 信息
    user_list = []
    for push_data in push_list:
        # WavesPush 繼承自 Push 基類，應該有 user_id 字段
        # 如果沒有，我們需要通過 uid 來查找用戶
        try:
            if hasattr(push_data, "user_id"):
                user = await WavesUser.get_user_by_attr(
                    push_data.user_id, push_data.bot_id, "uid", push_data.uid
                )
            else:
                # 如果沒有 user_id，通過 uid 查找用戶
                user = await WavesUser.get_user_by_attr(
                    None, push_data.bot_id, "uid", push_data.uid
                )
            if user:
                user_list.append(user)
        except Exception as e:
            logger.error(f"[鸣潮] 获取用户信息失败: {e}")
            continue

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

    # 檢查是否允許推送
    if has_international_users:
        logger.info("[鸣潮] 检测到国际服用户，允许推送")
    elif global_push_enabled:
        logger.info("[鸣潮] 全局体力推送已启用，允许推送")
    else:
        logger.info("[鸣潮] 全局体力推送已禁用且无国际服用户，跳过推送")
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

    logger.info(f"[鸣潮][推送] 用户 {user.uid} 开始体力检查")

    # 統一體力檢查邏輯，不區分國際服/國服
    await check_unified_stamina(push_data, msg_dict, user)


async def check_unified_stamina(
    push_data: Dict, msg_dict: Dict[str, Dict[str, Dict]], user: WavesUser
):
    """統一的體力檢查邏輯，不區分國際服/國服"""
    mode = "resin"
    status = "push_time"

    logger.info(f"[鸣潮][統一推送] 开始检查用户 {user.uid} 的体力")
    logger.info(f"[鸣潮][統一推送] 推送数据: {push_data}")

    # 檢查是否已經推送過
    if push_data[f"{mode}_is_push"] == "on":
        logger.info(f"[鸣潮][統一推送] 用户 {user.uid} 已推送过，跳过")
        return

    # 檢查推送設置
    if push_data[f"{mode}_push"] == "off":
        logger.info(f"[鸣潮][統一推送] 用户 {user.uid} 推送已关闭，跳过")
        return

    # 獲取當前體力信息
    current_stamina = 0
    max_stamina = 240
    threshold = push_data.get(f"{mode}_value", 180)

    try:
        # 嘗試獲取實際體力數據
        # 這裡可以根據用戶類型選擇不同的API
        is_international = False
        if user.platform and user.platform.startswith("international_"):
            is_international = True
        elif user.uid and user.uid.isdigit() and int(user.uid) >= 200000000:
            is_international = True
        elif user.cookie and len(user.cookie) > 20:
            is_international = True

        if is_international:
            # 國際服體力查詢
            logger.info(f"[鸣潮][統一推送] 使用國際服API查詢用戶 {user.uid} 的體力")
            current_stamina = await get_international_stamina(user)
        else:
            # 國服體力查詢
            logger.info(f"[鸣潮][統一推送] 使用國服API查詢用戶 {user.uid} 的體力")
            current_stamina = await get_domestic_stamina(user)

    except Exception as e:
        logger.error(f"[鸣潮][統一推送] 获取体力信息失败: {e}")
        # 如果獲取失敗，使用默認值進行檢查
        current_stamina = 180  # 假設已滿體力

    logger.info(
        f"[鸣潮][統一推送] 用户 {user.uid} 当前体力: {current_stamina}/{max_stamina}, 阈值: {threshold}"
    )

    # 檢查是否達到推送閾值
    if current_stamina >= threshold:
        logger.info(f"[鸣潮][統一推送] 用户 {user.uid} 体力达到阈值，准备推送")

        # 構建推送消息
        notice = "🌜您的结晶波片达到设定阈值啦"
        msg_list = [
            MessageSegment.text(f"✅[鸣潮] 推送提醒:\n"),
            MessageSegment.text(f"{notice}(UID:{user.uid})！\n"),
            MessageSegment.text(f"🕒当前体力：{current_stamina}/{max_stamina}！\n"),
            MessageSegment.text(f"🕒设定阈值：{threshold}！\n\n"),
            MessageSegment.text(f"📅请清完体力后使用[{PREFIX}每日]来更新推送时间！\n"),
        ]

        # 發送推送
        await save_push_data_unified(mode, msg_list, push_data, msg_dict, user, True)
        logger.info(f"[鸣潮][統一推送] 用户 {user.uid} 推送完成")
    else:
        logger.info(f"[鸣潮][統一推送] 用户 {user.uid} 体力未达到阈值，跳过推送")


async def get_international_stamina(user: WavesUser) -> int:
    """獲取國際服體力"""
    try:
        import kuro
        from kuro.types import Region

        client = kuro.Client(region=Region.OVERSEAS)
        oauth_code = await client.generate_oauth_code(user.cookie)

        # 從 platform 字段中提取服務器區域
        server_region = "Asia"  # 默認值
        if user.platform and user.platform.startswith("international_"):
            server_region = user.platform.replace("international_", "")

        role_info = await client.get_player_role(
            oauth_code, int(user.uid), server_region
        )
        return role_info.basic.waveplates
    except Exception as e:
        logger.error(f"[鸣潮][國際服體力] 获取失败: {e}")
        return 180  # 返回默認值


async def get_domestic_stamina(user: WavesUser) -> int:
    """獲取國服體力"""
    try:
        # 這裡可以調用國服的API
        # 暫時返回默認值
        return 180
    except Exception as e:
        logger.error(f"[鸣潮][國服體力] 获取失败: {e}")
        return 180  # 返回默認值


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

        # 获取角色信息（帶重試機制）
        logger.info(f"[鸣潮][国际服推送] 获取角色信息...")
        role_info = None
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                role_info = await client.get_player_role(
                    oauth_code, int(user.uid), server_region
                )
                logger.info(f"[鸣潮][国际服推送] 角色信息获取成功")
                break  # 成功獲取，跳出重試循環
            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    f"[鸣潮][国际服推送] 角色信息获取失败 (尝试 {retry_count + 1}/{max_retries}): {error_msg}"
                )

                # 檢查是否為 'retrying' 錯誤
                if "'retrying'" in error_msg or "retrying" in error_msg:
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.info(
                            f"[鸣潮][国际服推送] 检测到 'retrying' 错误，将在 2 秒后重试..."
                        )
                        await asyncio.sleep(2)  # 等待2秒後重試
                        continue
                    else:
                        logger.error(
                            f"[鸣潮][国际服推送] 重试 {max_retries} 次后仍然失败"
                        )
                        raise e
                else:
                    # 其他錯誤，直接拋出
                    raise e

        if role_info is None:
            raise Exception("角色信息获取失败，已达最大重试次数")

        basic_info = role_info.basic

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
            # 統一推送到指定 Discord 頻道 - 恢復原始格式
            notice = "🌜您的结晶波片达到设定阈值啦"
            msg_list = [
                MessageSegment.text(f"✅[鸣潮] 推送提醒:\n"),
                MessageSegment.text(f"{notice}(UID:{user.uid})！\n"),
                MessageSegment.text(
                    f"🕒当前体力阈值：{push_data[f'{mode}_value']}！\n\n"
                ),
                MessageSegment.text(
                    f"📅请清完体力后使用[{PREFIX}每日]来更新推送时间！\n"
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

    # 構建推送消息 - 恢復原始格式
    notice = "🌜您的结晶波片达到设定阈值啦"
    msg_list = [
        MessageSegment.text(f"✅[鸣潮] 推送提醒:\n"),
        MessageSegment.text(f"{notice}(UID:{user.uid})！\n"),
        MessageSegment.text(f"🕒当前体力阈值：{push_data[f'{mode}_value']}！\n\n"),
        MessageSegment.text(f"📅请清完体力后使用[{PREFIX}每日]来更新推送时间！\n"),
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
    """使用 Discord Webhook 推送體力通知"""
    # 获取数据
    bot_id = user.bot_id
    qid = user.user_id
    uid = user.uid

    logger.info(
        f"[鸣潮][推送保存] 开始保存推送数据: UID={uid}, BotID={bot_id}, UserID={qid}"
    )

    # 檢查是否啟用 Discord Webhook 推送
    webhook_enabled = WutheringWavesConfig.get_config("DiscordWebhookEnabled").data
    webhook_url = WutheringWavesConfig.get_config("DiscordWebhookUrl").data

    logger.info(
        f"[鸣潮][推送保存] Discord Webhook 配置检查: enabled={webhook_enabled}, url={webhook_url[:50] if webhook_url else 'None'}..."
    )

    if webhook_enabled and webhook_url:
        logger.info(f"[鸣潮][推送保存] 使用 Discord Webhook 推送")
        try:
            from ..utils.discord_webhook import send_stamina_webhook

            # 獲取伺服器區域信息
            server_region = "未知"
            if user.platform and user.platform.startswith("international_"):
                server_region = user.platform.replace("international_", "")
            elif user.uid and user.uid.isdigit() and int(user.uid) >= 200000000:
                server_region = "國際服"
            else:
                server_region = "國服"

            # 從消息中提取體力信息
            current_stamina = 180  # 默認值
            max_stamina = 240  # 默認值
            threshold = push_data.get("resin_value", 180)

            # 嘗試從消息中解析體力信息
            for msg in msg_list:
                if isinstance(msg, MessageSegment) and msg.type == "text":
                    text = msg.data
                    if "当前体力" in text and "/" in text:
                        try:
                            # 解析 "当前体力：180/240！" 格式
                            import re

                            match = re.search(r"当前体力：(\d+)/(\d+)", text)
                            if match:
                                current_stamina = int(match.group(1))
                                max_stamina = int(match.group(2))
                                break
                        except:
                            pass

            # 發送 Discord webhook 推送
            webhook_success = await send_stamina_webhook(
                user_id=qid,
                current_stamina=current_stamina,
                max_stamina=max_stamina,
                threshold=threshold,
                server_region=server_region,
            )

            if webhook_success:
                logger.info(f"[鸣潮][推送保存] Discord Webhook 推送成功")
                if is_need_save:
                    await WavesPush.update_data_by_uid(
                        uid=uid, bot_id=bot_id, **{f"{mode}_is_push": "on"}
                    )
                    logger.info(f"[鸣潮][推送保存] 推送状态更新完成")
                return
            else:
                logger.warning(
                    f"[鸣潮][推送保存] Discord Webhook 推送失败，回退到传统推送"
                )
        except Exception as e:
            logger.error(f"[鸣潮][推送保存] Discord Webhook 推送异常: {e}")
            logger.info(f"[鸣潮][推送保存] 回退到传统推送方式")

    # 傳統推送方式（回退方案）
    logger.info(f"[鸣潮][推送保存] 使用传统推送方式")

    # 添加到私聊推送
    private_data: Dict = msg_dict["private_msg_dict"]
    if qid not in private_data:
        private_data[qid] = []

    private_data[qid].append({"bot_id": bot_id, "messages": msg_list})

    logger.info(f"[鸣潮][推送保存] 消息已添加到私聊推送队列: {qid}")

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
