from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.aps import scheduler
from gsuid_core.logger import logger

from ..utils.waves_api import waves_api
from .notice_stamina import get_notice_list
from ..utils.waves_send_msg import send_board_cast_msg
from ..utils.database.models import WavesBind, WavesUser
from ..wutheringwaves_config import WutheringWavesConfig
from ..utils.error_reply import ERROR_CODE, WAVES_CODE_098, WAVES_CODE_103
from .draw_waves_stamina import (
    draw_stamina_img,
    draw_international_stamina_img,
)

waves_daily_info = SV("waves查询体力")


stamina_push_interval = WutheringWavesConfig.get_config("StaminaPushInterval").data

logger.info(f"[鸣潮] 体力推送间隔设置: {stamina_push_interval} 分钟")


@waves_daily_info.on_fullmatch(
    (
        "每日",
        "mr",
        "实时便笺",
        "便笺",
        "便签",
        "体力",
    )
)
async def send_daily_info_pic(bot: Bot, ev: Event):
    await bot.logger.info(f"[鸣潮]开始执行[每日信息]: {ev.user_id}")

    # 檢查查詢冷卻
    try:
        from ..utils.enhanced_cooldown_manager import query_cooldown_manager

        can_use, remaining_time = query_cooldown_manager.can_use(ev.user_id)
        if not can_use:
            remaining_seconds = int(remaining_time) if remaining_time else 0
            return await bot.send(
                f"⏰ 查詢功能冷卻中，請等待 {remaining_seconds} 秒後再試\n"
                f"💎 升級Premium會員可無冷卻限制！",
                at_sender=True if ev.group_id else False,
            )
    except ImportError:
        # 如果冷卻管理器未安裝，跳過冷卻檢查
        pass
    except Exception as e:
        await bot.logger.error(f"[鸣潮] 冷卻檢查失敗: {e}")

    # 首先嘗試獲取用戶選擇的特定伺服器 UID
    selected_uid = None
    selected_user = None

    # 檢查是否有用戶選擇的特定伺服器記錄
    # 優先使用 platform 包含具體伺服器信息的用戶記錄
    all_users = await WavesUser.select_data_list(user_id=ev.user_id, bot_id=ev.bot_id)
    if all_users:
        # 尋找有具體伺服器信息的用戶（platform 包含 international_ 前綴）
        for user in all_users:
            if user.platform and user.platform.startswith("international_"):
                selected_uid = user.uid
                selected_user = user
                await bot.logger.info(
                    f"[鸣潮][每日信息] 找到用戶選擇的伺服器: {user.platform}, UID: {user.uid}"
                )
                break

    # 如果沒有找到特定伺服器選擇，使用默認綁定的 UID
    if not selected_uid:
        selected_uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
        if not selected_uid:
            return await bot.send(ERROR_CODE[WAVES_CODE_103])

        # 獲取對應的用戶信息
        selected_user = await WavesUser.get_user_by_attr(
            ev.user_id, ev.bot_id, "uid", selected_uid
        )
        await bot.logger.info(f"[鸣潮][每日信息] 使用默認綁定 UID: {selected_uid}")

    # 調試信息
    await bot.logger.info(f"[鸣潮][每日信息]最終使用 UID: {selected_uid}")
    await bot.logger.info(f"[鸣潮][每日信息]用戶信息: {selected_user}")
    if selected_user:
        await bot.logger.info(f"[鸣潮][每日信息]平台: {selected_user.platform}")

    # 檢查是否為國際服用戶（多種方式）
    is_international = False
    if (
        selected_user
        and selected_user.platform
        and selected_user.platform.startswith("international_")
    ):
        is_international = True
        await bot.logger.info(
            f"[鸣潮][每日信息] 检测到国际服用户（platform: {selected_user.platform}）"
        )
    elif (
        selected_user
        and selected_user.platform
        and selected_user.platform == "international"
    ):
        is_international = True
        await bot.logger.info(
            f"[鸣潮][每日信息] 检测到国际服用户（platform: {selected_user.platform}）"
        )
    elif (
        selected_user
        and selected_user.uid
        and selected_user.uid.isdigit()
        and int(selected_user.uid) >= 200000000
    ):
        is_international = True
        await bot.logger.info(
            f"[鸣潮][每日信息] 检测到国际服用户（UID: {selected_user.uid}）"
        )
    elif selected_user and selected_user.cookie and len(selected_user.cookie) > 20:
        is_international = True
        await bot.logger.info(
            f"[鸣潮][每日信息] 检测到可能的国际服用户（有有效cookie）"
        )

    if is_international:
        # 國際服體力查詢
        await bot.logger.info(
            f"[鸣潮][每日信息]使用國際服體力查詢，平台: {selected_user.platform}"
        )
        result = await draw_international_stamina_img(bot, ev, selected_user)

        # 檢查查詢結果是否成功
        if result and not str(result).startswith("❌"):
            # 查詢成功，標記冷卻
            try:
                from ..utils.enhanced_cooldown_manager import (
                    query_cooldown_manager,
                )

                query_cooldown_manager.mark_success(ev.user_id)
            except ImportError:
                pass
        else:
            # 查詢失敗，不計入冷卻
            try:
                from ..utils.enhanced_cooldown_manager import (
                    query_cooldown_manager,
                )

                query_cooldown_manager.mark_failure(ev.user_id)
            except ImportError:
                pass

        return await bot.send(result)
    else:
        # 國服體力查詢
        if waves_api.is_net(selected_uid):
            await bot.logger.info(
                f"[鸣潮][每日信息]檢測到國際服UID但平台標記錯誤，使用國際服查詢"
            )
            # 如果檢測到是國際服UID但平台標記錯誤，嘗試使用國際服查詢
            if selected_user:
                # 更新平台標記
                await WavesUser.update_data_by_data(
                    select_data={
                        "user_id": ev.user_id,
                        "bot_id": ev.bot_id,
                        "uid": selected_uid,
                    },
                    update_data={"platform": "international"},
                )
                result = await draw_international_stamina_img(bot, ev, selected_user)

                # 檢查查詢結果是否成功
                if result and not str(result).startswith("❌"):
                    # 查詢成功，標記冷卻
                    try:
                        from ..utils.enhanced_cooldown_manager import (
                            query_cooldown_manager,
                        )

                        query_cooldown_manager.mark_success(ev.user_id)
                    except ImportError:
                        pass
                else:
                    # 查詢失敗，不計入冷卻
                    try:
                        from ..utils.enhanced_cooldown_manager import (
                            query_cooldown_manager,
                        )

                        query_cooldown_manager.mark_failure(ev.user_id)
                    except ImportError:
                        pass

                return await bot.send(result)
            else:
                return await bot.send(ERROR_CODE[WAVES_CODE_098])
        result = await draw_stamina_img(bot, ev)

        # 檢查查詢結果是否成功
        if result and not str(result).startswith("❌"):
            # 查詢成功，標記冷卻
            try:
                from ..utils.enhanced_cooldown_manager import (
                    query_cooldown_manager,
                )

                query_cooldown_manager.mark_success(ev.user_id)
            except ImportError:
                pass
        else:
            # 查詢失敗，不計入冷卻
            try:
                from ..utils.enhanced_cooldown_manager import (
                    query_cooldown_manager,
                )

                query_cooldown_manager.mark_failure(ev.user_id)
            except ImportError:
                pass

        return await bot.send(result)


@scheduler.scheduled_job("interval", minutes=stamina_push_interval)
async def waves_daily_info_notice_job():
    logger.info(f"[鸣潮] 体力推送任务开始执行 (间隔: {stamina_push_interval} 分钟)")

    if stamina_push_interval == 0:
        logger.info("[鸣潮] 体力推送间隔设置为0，跳过推送")
        return

    result = await get_notice_list()
    if not result:
        logger.info("[鸣潮] 没有需要推送的用户")
        return

    logger.info(f"[鸣潮] 开始推送: {result}")
    await send_board_cast_msg(result, "resin")
    logger.info("[鸣潮] 体力推送任务完成")


# 添加測試推送命令
test_push = SV("测试体力推送")


@test_push.on_fullmatch("测试推送", "test_push")
async def test_stamina_push(bot: Bot, ev: Event):
    """測試體力推送功能"""
    await bot.logger.info(f"[鸣潮] 开始执行测试推送: {ev.user_id}")

    try:
        result = await get_notice_list()
        if not result:
            return await bot.send("[鸣潮] 没有需要推送的用户")

        await bot.send(f"[鸣潮] 测试推送结果: {result}")
        await send_board_cast_msg(result, "resin")
        await bot.send("[鸣潮] 测试推送完成")

    except Exception as e:
        await bot.send(f"[鸣潮] 测试推送失败: {e}")
        logger.error(f"[鸣潮] 测试推送错误: {e}")
