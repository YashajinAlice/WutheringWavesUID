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
        uid_list = await WavesBind.get_uid_list_by_game(qid, ev.bot_id)

        # 使用付費機制檢查綁定限制
        try:
            from ..wutheringwaves_payment.payment_manager import (
                payment_manager,
            )

            max_bind_num = payment_manager.get_max_bind_num(qid)
        except ImportError:
            # 如果付費模組未安裝，使用舊的配置
            max_bind_num: int = WutheringWavesConfig.get_config("MaxBindNum").data

        # 檢查是否已達到綁定上限
        if uid_list and len(uid_list) >= max_bind_num:
            if max_bind_num == 999:  # Premium用戶理論上無限制
                return await bot.send("[鸣潮] 系統錯誤，請聯繫管理員\n", at_sender)
            else:
                return await bot.send(
                    f"[鸣潮] 绑定特征码达到上限（{max_bind_num}個）\n"
                    "💎 升級Premium會員可無限制綁定UID！\n"
                    f"💰 價格：{payment_manager.get_premium_price() if 'payment_manager' in locals() else 100} 台幣/月",
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
                0: f"[鸣潮] 特征码[{uid}]绑定成功！\n\n当前仅支持查询部分信息，完整功能请\n国服用户使用【{PREFIX}登录】，使用【{PREFIX}刷新面板】更新角色面板\n国际服用户请使用【{PREFIX}分析】上传角色面板\n使用【{PREFIX}查看】查看已绑定的特征码\n更新角色面板后可以使用【{PREFIX}暗主排行】查询暗主排行\n",
                -1: f"[鸣潮] 特征码[{uid}]的位数不正确！\n",
                -2: f"[鸣潮] 特征码[{uid}]已经绑定过了！\n",
                -3: "[鸣潮] 你输入了错误的格式!\n",
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
                    f"[鸣潮] 切换特征码[{uid_list[0]}]成功！\n", _buttons
                )
            else:
                return await bot.send("[鸣潮] 尚未绑定任何特征码\n", at_sender)
        else:
            return await bot.send(f"[鸣潮] 尚未绑定该特征码[{uid}]\n", at_sender)
    elif "查看" in ev.command:
        uid_list = await WavesBind.get_uid_list_by_game(qid, ev.bot_id)
        if uid_list:
            uids = "\n".join(uid_list)
            buttons: List[Any] = []
            for uid in uid_list:
                buttons.append(WavesButton(f"{uid}", f"切换{uid}"))
            return await bot.send_option(
                f"[鸣潮] 绑定的特征码列表为：\n{uids}\n", buttons
            )
        else:
            return await bot.send("[鸣潮] 尚未绑定任何特征码\n", at_sender)
    elif "删除全部" in ev.command:
        retcode = await WavesBind.update_data(
            user_id=qid,
            bot_id=ev.bot_id,
            **{WavesBind.get_gameid_name(None): None},
        )
        if retcode == 0:
            return await bot.send("[鸣潮] 删除全部特征码成功！\n", at_sender)
        else:
            return await bot.send("[鸣潮] 尚未绑定任何特征码\n", at_sender)
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
