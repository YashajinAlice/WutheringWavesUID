from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger

from ..utils.at_help import ruser_id
from ..utils.hint import error_reply
from ..utils.waves_api import waves_api
from ..utils.database.models import WavesBind
from ..utils.error_reply import WAVES_CODE_102, WAVES_CODE_103
from .draw_role_info import draw_role_img, draw_international_role_img

waves_role_info = SV("waves查询信息")


@waves_role_info.on_fullmatch(("查询", "卡片"), block=True)
async def send_role_info(bot: Bot, ev: Event):
    logger.info("[鸣潮]开始执行[查询信息]")
    user_id = ruser_id(ev)

    # 檢查查詢冷卻
    try:
        from ..utils.enhanced_cooldown_manager import query_cooldown_manager

        can_use, remaining_time = query_cooldown_manager.can_use(user_id)
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
        logger.error(f"[鸣潮] 冷卻檢查失敗: {e}")

    uid = await WavesBind.get_uid_by_game(user_id, ev.bot_id)
    logger.info(f"[鸣潮][查询信息] user_id: {user_id} UID: {uid}")
    if not uid:
        await bot.send(error_reply(WAVES_CODE_103))
        return

    # 檢查是否為國際服用戶
    from ..utils.database.models import WavesUser

    user = await WavesUser.get_user_by_attr(user_id, ev.bot_id, "uid", uid)

    # 添加調試信息
    logger.info(f"[鸣潮][卡片] 用户信息: user={user}")
    if user:
        logger.info(f"[鸣潮][卡片] 用户平台: {user.platform}")
        logger.info(f"[鸣潮][卡片] 用户UID: {user.uid}")

    # 檢查是否為國際服用戶（多種方式）
    is_international = False
    if user and user.platform and user.platform.startswith("international_"):
        is_international = True
        logger.info(f"[鸣潮][卡片] 检测到国际服用户（platform: {user.platform}）")
    elif user and user.platform and user.platform == "international":
        is_international = True
        logger.info(f"[鸣潮][卡片] 检测到国际服用户（platform: {user.platform}）")
    elif user and user.uid and user.uid.isdigit() and int(user.uid) >= 200000000:
        is_international = True
        logger.info(f"[鸣潮][卡片] 检测到国际服用户（UID: {user.uid}）")
    elif user and user.cookie and len(user.cookie) > 20:
        is_international = True
        logger.info(f"[鸣潮][卡片] 检测到可能的国际服用户（有有效cookie）")

    if is_international:
        # 國際服用戶使用 kuro.py API
        logger.info(f"[鸣潮][卡片] 使用国际服API查询")
        im = await draw_international_role_img(uid, user, ev)

        # 檢查查詢結果是否成功
        if im and not str(im).startswith("❌"):
            # 查詢成功，標記冷卻
            try:
                from ..utils.enhanced_cooldown_manager import (
                    query_cooldown_manager,
                )

                query_cooldown_manager.mark_success(user_id)
            except ImportError:
                pass
        else:
            # 查詢失敗，不計入冷卻
            try:
                from ..utils.enhanced_cooldown_manager import (
                    query_cooldown_manager,
                )

                query_cooldown_manager.mark_failure(user_id)
            except ImportError:
                pass
    else:
        # 國服用戶使用原有邏輯
        logger.info(f"[鸣潮][卡片] 使用国服API查询")
        _, ck = await waves_api.get_ck_result(uid, user_id, ev.bot_id)
        if not ck and not waves_api.is_net(uid):
            await bot.send(error_reply(WAVES_CODE_102))
            return
        im = await draw_role_img(uid, ck, ev)

        # 檢查查詢結果是否成功
        if im and not str(im).startswith("❌"):
            # 查詢成功，標記冷卻
            try:
                from ..utils.enhanced_cooldown_manager import (
                    query_cooldown_manager,
                )

                query_cooldown_manager.mark_success(user_id)
            except ImportError:
                pass
        else:
            # 查詢失敗，不計入冷卻
            try:
                from ..utils.enhanced_cooldown_manager import (
                    query_cooldown_manager,
                )

                query_cooldown_manager.mark_failure(user_id)
            except ImportError:
                pass

    await bot.send(im)  # type: ignore
