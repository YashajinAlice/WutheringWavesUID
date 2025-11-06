from typing import Any, Dict, List

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.gss import gss
from gsuid_core.models import Event
from gsuid_core.aps import scheduler
from gsuid_core.logger import logger
from gsuid_core.config import core_config

from ..utils.button import WavesButton
from .deal import add_cookie, get_cookie, delete_cookie
from ..wutheringwaves_user.login_succ import login_success_msg
from ..wutheringwaves_config import PREFIX, WutheringWavesConfig
from ..utils.database.models import WavesBind, WavesUser, WavesUserAvatar

waves_bind_uid = SV("鸣潮绑定特征码", priority=10)
waves_add_ck = SV("鸣潮添加token", priority=5)
waves_del_ck = SV("鸣潮删除token", priority=5)
waves_get_ck = SV("waves获取ck", area="DIRECT")
waves_del_all_invalid_ck = SV("鸣潮删除无效token", priority=1, pm=1)
waves_admin_query_uid = SV("鸣潮管理員查詢UID", priority=1, pm=1)
waves_change_nickname = SV("鸣潮改暱稱", priority=5)


def get_ck_and_devcode(text: str, split_str: str = ",") -> tuple[str, str]:
    ck, devcode = "", ""
    try:
        ck, devcode = text.split(split_str)
        devcode = devcode.strip()
        ck = ck.strip()
    except ValueError:
        pass
    return ck, devcode


msg_notify = [
    "[鸣潮] 该命令末尾需要跟正确的token和did!",
    f"例如【{PREFIX}添加token token,did】",
    "",
    "先找名字为did，没有再找devcode（不是distinct_id）",
    "",
    "当前did位数不正确（32位、36位、40位），请检查后重新添加",
]


@waves_add_ck.on_prefix(
    ("添加CK", "添加ck", "添加Token", "添加token", "添加TOKEN"), block=True
)
async def send_waves_add_ck_msg(bot: Bot, ev: Event):
    at_sender = True if ev.group_id else False
    text = ev.text.strip()

    ck, did = "", ""
    for i in ["，", ","]:
        ck, did = get_ck_and_devcode(text, split_str=i)
        if ck and did:
            break

    if len(did) == 32 or len(did) == 36 or len(did) == 40:
        pass
    else:
        did = ""

    if not ck or not did:
        return await bot.send(
            "\n".join(msg_notify),
            at_sender,
        )

    msg = await add_cookie(ev, ck, did)
    if "成功" in msg:
        user = await WavesUser.get_user_by_attr(ev.user_id, ev.bot_id, "cookie", ck)
        if user:
            return await login_success_msg(bot, ev, user)

    await bot.send(msg, at_sender)


@waves_del_ck.on_command(
    ("删除ck", "删除CK", "删除Token", "删除token", "删除TOKEN"), block=True
)
async def send_waves_del_ck_msg(bot: Bot, ev: Event):
    at_sender = True if ev.group_id else False
    uid = ev.text.strip()
    if not uid or len(uid) != 9:
        return await bot.send(
            f"[鸣潮] 该命令末尾需要跟正确的特征码! \n例如【{PREFIX}删除token123456】\n",
            at_sender,
        )
    await bot.send(await delete_cookie(ev, uid), at_sender)


@waves_get_ck.on_fullmatch(
    ("获取ck", "获取CK", "获取Token", "获取token", "获取TOKEN"), block=True
)
async def send_waves_get_ck_msg(bot: Bot, ev: Event):
    await bot.send(await get_cookie(bot, ev))


@waves_del_all_invalid_ck.on_fullmatch(("删除无效token"), block=True)
async def delete_all_invalid_cookie(bot: Bot, ev: Event):
    at_sender = True if ev.group_id else False
    del_len = await WavesUser.delete_all_invalid_cookie()
    await bot.send(f"[鸣潮] 已删除无效token【{del_len}】个\n", at_sender)


@scheduler.scheduled_job("cron", hour=23, minute=30)
async def auto_delete_all_invalid_cookie():
    DelInvalidCookie = WutheringWavesConfig.get_config("DelInvalidCookie").data
    if not DelInvalidCookie:
        return
    del_len = await WavesUser.delete_all_invalid_cookie()
    if del_len == 0:
        return
    msg = f"[鸣潮] 删除无效token【{del_len}】个"
    config_masters = core_config.get_config("masters")

    if not config_masters:
        return
    for bot_id in gss.active_bot:
        await gss.active_bot[bot_id].target_send(
            msg,
            "direct",
            config_masters[0],
            "onebot",
            "",
            "",
        )
        break
    logger.info(f"[鸣潮]推送主人删除无效token结果: {msg}")


@waves_admin_query_uid.on_command(("查特征码", "查UID"), block=True)
async def admin_query_uid_binding(bot: Bot, ev: Event):
    """管理員查詢UID綁定信息"""
    at_sender = True if ev.group_id else False
    uid = ev.text.strip().replace("uid", "").replace("UID", "")

    if not uid:
        return await bot.send(
            f"❌ 請提供要查詢的UID！\n格式：查特征码 123456789\n", at_sender
        )

    if len(uid) != 9 or not uid.isdigit():
        return await bot.send(
            f"❌ UID格式不正確！請提供9位數字的UID\n例如 綁定710596960\n", at_sender
        )

    try:
        # 查詢UID綁定信息
        bind_info = await WavesBind.get_uid_bind_info(uid)

        if not bind_info:
            return await bot.send(
                f"🔍 **UID查詢結果**\n\n"
                f"UID: `{uid}`\n"
                f"狀態: ❌ 未綁定\n"
                f"說明: 此UID尚未被任何用戶綁定",
                at_sender,
            )

        # 格式化綁定時間
        bind_time = bind_info.get("bind_time", 0)
        if bind_time:
            import time

            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(bind_time))
        else:
            time_str = "未知"

        # 獲取用戶的其他綁定UID
        all_uids = bind_info.get("all_uids", [])
        other_uids = [u for u in all_uids if u != uid]

        # 構建回應訊息
        message = f"🔍 **UID查詢結果**\n\n"
        message += f"UID: `{uid}`\n"
        message += f"狀態: ✅ 已綁定\n"
        message += f"綁定用戶ID: `{bind_info['user_id']}`\n"
        message += f"平台: `{bind_info['bot_id']}`\n"
        message += f"綁定時間: {time_str}\n"

        if bind_info.get("group_id"):
            message += f"群組ID: `{bind_info['group_id']}`\n"

        if other_uids:
            message += f"該用戶其他綁定UID: `{', '.join(other_uids)}`\n"

        return await bot.send(message, at_sender)

    except Exception as e:
        logger.error(f"[鸣潮] 管理員查詢UID失敗: {e}")
        return await bot.send(
            f"❌ 查詢失敗！請檢查UID格式或聯繫技術支援\n錯誤: {str(e)}", at_sender
        )


@waves_bind_uid.on_command(
    (
        "绑定",
        "切换",
        "删除全部特征码",
        "删除全部UID",
        "删除",
        "查看",
    ),
    block=True,
)
async def send_waves_bind_uid_msg(bot: Bot, ev: Event):
    uid = ev.text.strip().replace("uid", "").replace("UID", "")
    qid = ev.user_id
    if ev.bot_id == "discord" or ev.bot_id == "qqgroup":
        await sync_non_onebot_user_avatar(ev)

    at_sender = True if ev.group_id else False

    if "绑定" in ev.command:
        if not uid:
            return await bot.send(
                f"该命令需要带上正确的uid!\n{PREFIX}绑定uid\n", at_sender
            )

        # 檢查UID是否在黑名單中
        from ..utils.util import is_uid_banned

        if is_uid_banned(uid):
            return await bot.send(
                f"[鸣潮] 此UID[{uid}]已被禁止綁定，無法使用所有功能！\n",
                at_sender,
            )

        uid_list = await WavesBind.get_uid_list_by_game(qid, ev.bot_id)

        # 檢查綁定限制
        max_bind_num: int = WutheringWavesConfig.get_config("MaxBindNum").data

        # 檢查是否已達到綁定上限
        if uid_list and len(uid_list) >= max_bind_num:
            return await bot.send(
                f"[鸣潮] 绑定特征码达到上限（{max_bind_num}個）\n",
                at_sender,
            )

        code = await WavesBind.insert_waves_uid(
            qid, ev.bot_id, uid, ev.group_id, lenth_limit=9
        )
        if code == 0 or code == -2:
            retcode = await WavesBind.switch_uid_by_game(qid, ev.bot_id, uid)
        return await send_diff_msg(
            bot,
            code,
            {
                0: f"[鸣潮] [{uid}]已綁定成功！\n\n目前國際服用戶可使用功能較少\n国服用户使用【{PREFIX}登录】，使用【{PREFIX}刷新面板】更新角色面板\n國際服用戶請使用【{PREFIX}分析】上傳面板\n使用【{PREFIX}查看】查看目前已綁定的UID\n更新角色面板后可以使用【{PREFIX}暗主排行】查询暗主排行\n玩家暱稱若因為是特殊語言可使用 修改暱稱 來修改名字\n日本のユーザーは次々バージョンでのコマンドサポートを期待している\n",
                -1: f"[鸣潮] 特徵碼[{uid}]的位數並不正確！\n 綁定710596960\n",
                -2: f"[鸣潮] 特徵碼[{uid}]您已綁定了！\n",
                -3: "[鸣潮] 您輸入了錯誤的格式！\n",
                -4: f"[鸣潮] 此[{uid}]已經被其他用戶佔據，禁止重複綁定！\n",
            },
            at_sender=at_sender,
        )
    elif "切换" in ev.command:
        retcode = await WavesBind.switch_uid_by_game(qid, ev.bot_id, uid)
        if retcode == 0:
            uid_list = await WavesBind.get_uid_list_by_game(qid, ev.bot_id)
            if uid_list:
                _buttons: List[Any] = []
                for uid in uid_list:
                    _buttons.append(WavesButton(f"{uid}", f"切换{uid}"))
                return await bot.send_option(
                    f"[鸣潮] 已切換至[{uid_list[0]}]！\n", _buttons
                )
            else:
                return await bot.send("[鸣潮] 您目前尚未綁定UID\n", at_sender)
        else:
            return await bot.send(f"[鸣潮] 您目前尚未綁定UID[{uid}]\n", at_sender)
    elif "查看" in ev.command:
        uid_list = await WavesBind.get_uid_list_by_game(qid, ev.bot_id)
        if uid_list:
            uids = "\n".join(uid_list)
            buttons: List[Any] = []
            for uid in uid_list:
                buttons.append(WavesButton(f"{uid}", f"切换{uid}"))
            return await bot.send_option(
                f"[鸣潮] 您目前綁定的UID列表為：\n{uids}\n", buttons
            )
        else:
            return await bot.send("[鸣潮] 您目前尚未綁定UID\n", at_sender)
    elif "删除全部" in ev.command:
        retcode = await WavesBind.update_data(
            user_id=qid,
            bot_id=ev.bot_id,
            **{WavesBind.get_gameid_name(None): None},
        )
        if retcode == 0:
            return await bot.send("[鸣潮] 删除全部特征码成功！\n", at_sender)
        else:
            return await bot.send("[鸣潮] 您目前尚未綁定UID\n", at_sender)
    else:
        if not uid:
            return await bot.send(
                f"[鸣潮] 该命令末尾需要跟正确的特征码!\n例如【{PREFIX}删除123456】\n",
                at_sender,
            )
        data = await WavesBind.delete_uid(qid, ev.bot_id, uid)
        return await send_diff_msg(
            bot,
            data,
            {
                0: f"[鸣潮] 删除特征码[{uid}]成功！\n",
                -1: f"[鸣潮] 该特征码[{uid}]不在已绑定列表中！\n",
            },
            at_sender=at_sender,
        )


async def sync_non_onebot_user_avatar(ev: Event):
    """从事件中提取头像 avatar_hash 并自动更新数据库中的 hash 映射"""
    avatar_hash = "error"
    if ev.bot_id == "discord":
        avatar_url = ev.sender.get("avatar")
        if not avatar_url:
            logger.error("Discord 事件中缺少 avatar 字段")
            return
        parts = avatar_url.split("/")
        index = parts.index(str(ev.user_id))
        avatar_hash = parts[index + 1]
    elif ev.bot_id == "qqgroup":
        avatar_hash = ev.bot_self_id

    data = await WavesUserAvatar.select_data(ev.user_id, ev.bot_id)
    old_avatar_hash = data.avatar_hash if data else ""

    if avatar_hash != old_avatar_hash:
        await WavesUserAvatar.insert_data(
            user_id=ev.user_id, bot_id=ev.bot_id, avatar_hash=avatar_hash
        )


async def send_diff_msg(bot: Bot, code: Any, data: Dict, at_sender=False):
    for retcode in data:
        if code == retcode:
            return await bot.send(data[retcode], at_sender)


@waves_change_nickname.on_command(
    ("修改昵称", "修改暱稱", "改昵称", "改暱稱", "改名字", "修改名字"), block=True
)
async def change_nickname(bot: Bot, ev: Event):
    """修改玩家暱稱指令"""
    at_sender = True if ev.group_id else False
    new_nickname = ev.text.strip()

    if not new_nickname:
        return await bot.send(
            f"❌ 請提供新的暱稱！\n"
            f"格式：改暱稱 新暱稱\n"
            f"例如：@艾特机器人 改暱稱 我的新暱稱",
            at_sender,
        )

    # 檢查暱稱長度
    if len(new_nickname) > 20:
        return await bot.send("❌ 暱稱長度不能超過20個字符！", at_sender)

    if len(new_nickname) < 1:
        return await bot.send("❌ 暱稱不能為空！", at_sender)

    try:
        # 獲取用戶綁定的UID
        uid_list = await WavesBind.get_uid_list_by_game(ev.user_id, ev.bot_id)

        if not uid_list:
            return await bot.send(
                "❌ 您尚未綁定任何UID！\n" f"請先使用 @艾特机器人 綁定 您的UID",
                at_sender,
            )

        # 使用第一個綁定的UID
        uid = uid_list[0]

        # 導入必要的模組
        from ..wutheringwaves_analyzecard.user_info_utils import (
            save_user_info,
            get_user_detail_info,
        )

        # 獲取當前用戶信息
        current_user_info = await get_user_detail_info(uid)

        # 更新暱稱
        await save_user_info(
            uid=uid,
            name=new_nickname,
            level=(
                current_user_info.level
                if current_user_info and current_user_info.level is not None
                else 0
            ),
            worldLevel=(
                current_user_info.worldLevel
                if current_user_info and current_user_info.worldLevel is not None
                else 0
            ),
            achievementCount=(
                current_user_info.achievementCount
                if current_user_info and current_user_info.achievementCount is not None
                else 0
            ),
            achievementStar=(
                current_user_info.achievementStar
                if current_user_info and current_user_info.achievementStar is not None
                else 0
            ),
        )

        # 發送成功消息
        await bot.send(
            f"✅ 暱稱修改成功！\n"
            f"UID: {uid}\n"
            f"新暱稱: {new_nickname}\n\n"
            f"💡 提示：暱稱已更新，下次使用相關功能時會顯示新暱稱",
            at_sender,
        )

        logger.info(
            f"[鸣潮] 用戶 {ev.user_id} 成功修改暱稱為: {new_nickname} (UID: {uid})"
        )

    except Exception as e:
        logger.error(f"[鸣潮] 修改暱稱失敗: {e}")
        await bot.send(
            f"❌ 修改暱稱失敗！\n" f"錯誤: {str(e)}\n" f"請檢查UID是否正確或聯繫管理員",
            at_sender,
        )
