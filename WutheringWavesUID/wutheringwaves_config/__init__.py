import re

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger
from gsuid_core.sv import SV, get_plugin_available_prefix

from ..utils.database.models import WavesBind
from ..utils.name_convert import alias_to_char_name
from .wutheringwaves_config import WutheringWavesConfig
from .set_config import set_push_value, set_config_func, set_waves_user_value

sv_self_config = SV("鸣潮配置")

# 延遲導入以避免循環依賴
PREFIX = get_plugin_available_prefix("WutheringWavesUID")


@sv_self_config.on_prefix(("开启", "关闭"))
async def open_switch_func(bot: Bot, ev: Event):
    at_sender = True if ev.group_id else False
    uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    if uid is None:
        return await bot.send(
            f"您还未绑定鸣潮特征码, 请使用【{PREFIX}绑定uid】完成绑定！", at_sender
        )

    # 检查是否为国际服用户
    from ..utils.database.models import WavesUser

    user = await WavesUser.get_user_by_attr(ev.user_id, ev.bot_id, "uid", uid)

    # 添加调试信息
    logger.info(f"[{ev.user_id}] 用户信息: user={user}")
    if user:
        logger.info(f"[{ev.user_id}] 用户平台: {user.platform}")
        logger.info(f"[{ev.user_id}] 用户UID: {user.uid}")
        logger.info(
            f"[{ev.user_id}] 用户Cookie长度: {len(user.cookie) if user.cookie else 0}"
        )

    # 检查是否为国际服用户（UID >= 200000000 或者 platform 以 international_ 开头）
    is_international = False
    if user and user.platform and user.platform.startswith("international_"):
        is_international = True
        logger.info(f"[{ev.user_id}] 检测到国际服用户（platform: {user.platform}）")
    elif user and user.uid and user.uid.isdigit() and int(user.uid) >= 200000000:
        is_international = True
        logger.info(f"[{ev.user_id}] 检测到国际服用户（UID: {user.uid}）")
    elif user and user.cookie and len(user.cookie) > 20:
        # 如果有有效的 cookie，可能是国际服用户
        is_international = True
        logger.info(f"[{ev.user_id}] 检测到可能的国际服用户（有有效cookie）")

    if is_international:
        # 国际服用户，直接允许设置推送
        logger.info(f"[{ev.user_id}]国际服用户尝试[{ev.command[2:]}]了[{ev.text}]功能")
        im = await set_config_func(ev, uid)
        await bot.send(im, at_sender)
    else:
        # 国服用户，检查 token 有效性
        from ..utils.waves_api import waves_api

        ck = await waves_api.get_self_waves_ck(uid, ev.user_id, ev.bot_id)
        if not ck:
            from ..utils.error_reply import ERROR_CODE, WAVES_CODE_102

            return await bot.send(f"当前特征码：{uid}\n{ERROR_CODE[WAVES_CODE_102]}")

        logger.info(f"[{ev.user_id}]国服用户尝试[{ev.command[2:]}]了[{ev.text}]功能")

        im = await set_config_func(ev, uid)
        await bot.send(im, at_sender)


@sv_self_config.on_prefix("设置")
async def send_config_ev(bot: Bot, ev: Event):
    at_sender = True if ev.group_id else False

    uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    if uid is None:
        return await bot.send(
            f"您还未绑定鸣潮特征码, 请使用【{PREFIX}绑定uid】 完成绑定！\n", at_sender
        )

    # 检查是否为国际服用户
    from ..utils.database.models import WavesUser

    user = await WavesUser.get_user_by_attr(ev.user_id, ev.bot_id, "uid", uid)

    # 添加调试信息
    logger.info(f"[{ev.user_id}] 设置功能 - 用户信息: user={user}")
    if user:
        logger.info(f"[{ev.user_id}] 设置功能 - 用户平台: {user.platform}")
        logger.info(f"[{ev.user_id}] 设置功能 - 用户UID: {user.uid}")

    # 检查是否为国际服用户（UID >= 200000000 或者 platform 以 international_ 开头）
    is_international = False
    if user and user.platform and user.platform.startswith("international_"):
        is_international = True
        logger.info(
            f"[{ev.user_id}] 设置功能 - 检测到国际服用户（platform: {user.platform}）"
        )
    elif user and user.uid and user.uid.isdigit() and int(user.uid) >= 200000000:
        is_international = True
        logger.info(f"[{ev.user_id}] 设置功能 - 检测到国际服用户（UID: {user.uid}）")
    elif user and user.cookie and len(user.cookie) > 20:
        # 如果有有效的 cookie，可能是国际服用户
        is_international = True
        logger.info(f"[{ev.user_id}] 设置功能 - 检测到可能的国际服用户（有有效cookie）")

    if not is_international:
        # 国服用户，检查 token 有效性
        from ..utils.waves_api import waves_api

        ck = await waves_api.get_self_waves_ck(uid, ev.user_id, ev.bot_id)
        if not ck:
            from ..utils.error_reply import ERROR_CODE, WAVES_CODE_102

            return await bot.send(f"当前特征码：{uid}\n{ERROR_CODE[WAVES_CODE_102]}")

    if "阈值" in ev.text:
        func = "".join(re.findall("[\u4e00-\u9fa5]", ev.text.replace("阈值", "")))
        value = re.findall(r"\d+", ev.text)
        value = value[0] if value else None

        if value is None:
            return await bot.send("请输入正确的阈值数字...\n", at_sender)
        im = await set_push_value(ev, func, uid, int(value))
    elif "体力背景" in ev.text:
        # 对于体力背景设置，国际服和国服都需要检查 token
        from ..utils.waves_api import waves_api
        from ..utils.database.models import WavesUser

        # 先檢查用戶是否存在且有 cookie
        waves_user = await WavesUser.select_waves_user(uid, ev.user_id, ev.bot_id)
        if not waves_user or not waves_user.cookie:
            from ..utils.error_reply import ERROR_CODE, WAVES_CODE_102

            return await bot.send(
                f"当前特征码：{uid}\n{ERROR_CODE[WAVES_CODE_102]}", at_sender
            )

        # 對於國際服，直接使用 cookie，不檢查狀態
        if waves_user.platform and waves_user.platform.startswith("international"):
            ck = waves_user.cookie
        else:
            # 國服需要檢查 token 有效性
            ck = await waves_api.get_self_waves_ck(uid, ev.user_id, ev.bot_id)
            if not ck:
                from ..utils.error_reply import ERROR_CODE, WAVES_CODE_102

                return await bot.send(
                    f"当前特征码：{uid}\n{ERROR_CODE[WAVES_CODE_102]}", at_sender
                )
        func = "体力背景"
        value = "".join(re.findall("[\u4e00-\u9fa5]", ev.text.replace(func, "")))
        if not value:
            return await bot.send("[鸣潮] 请输入正确的角色名...\n", at_sender)
        char_name = alias_to_char_name(value)
        if not char_name:
            return await bot.send(
                f"[鸣潮] 角色名【{value}】无法找到, 可能暂未适配, 请先检查输入是否正确！\n",
                at_sender,
            )
        im = await set_waves_user_value(ev, func, uid, char_name)
    elif "群排行" in ev.text:
        if ev.user_pm > 3:
            return await bot.send("[鸣潮] 群排行设置需要群管理才可设置\n", at_sender)
        if not ev.group_id:
            return await bot.send("[鸣潮] 请使用群聊进行设置\n", at_sender)

        WavesRankUseTokenGroup = set(
            WutheringWavesConfig.get_config("WavesRankUseTokenGroup").data
        )
        WavesRankNoLimitGroup = set(
            WutheringWavesConfig.get_config("WavesRankNoLimitGroup").data
        )

        if "1" in ev.text:
            # 设置为 无限制
            WavesRankNoLimitGroup.add(ev.group_id)
            # 删除token限制
            WavesRankUseTokenGroup.discard(ev.group_id)
            msg = f"[鸣潮] 【{ev.group_id}】群排行已设置为[无限制上榜]\n"
        elif "2" in ev.text:
            # 设置为 token限制
            WavesRankUseTokenGroup.add(ev.group_id)
            # 删除无限制
            WavesRankNoLimitGroup.discard(ev.group_id)
            msg = f"[鸣潮] 群【{ev.group_id}】群排行已设置为[登录后上榜]\n"
        else:
            return await bot.send(
                "[鸣潮] 群排行设置参数失效\n1.无限制上榜\2.登录后上榜\n", at_sender
            )

        WutheringWavesConfig.set_config(
            "WavesRankUseTokenGroup", list(WavesRankUseTokenGroup)
        )
        WutheringWavesConfig.set_config(
            "WavesRankNoLimitGroup", list(WavesRankNoLimitGroup)
        )
        return await bot.send(msg, at_sender)
    else:
        return await bot.send("请输入正确的设置信息...\n", at_sender)

    await bot.send(im, at_sender)
