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

waves_bind_uid = SV("鳴潮特徴コード連携", priority=10)
waves_add_ck = SV("鳴潮token追加", priority=5)
waves_del_ck = SV("鳴潮token削除", priority=5)
waves_get_ck = SV("waves ck取得", area="DIRECT")
waves_del_all_invalid_ck = SV("鳴潮無効token削除", priority=1, pm=1)
waves_admin_query_uid = SV("鳴潮管理者UID照会", priority=1, pm=1)
waves_change_nickname = SV("鳴潮ニックネーム変更", priority=5)


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
    "[鳴潮] このコマンドの末尾に正しいtokenとdidが必要です！",
    f"例：【{PREFIX}token追加 token,did】",
    "",
    "まずdidという名前を探し、なければdevcodeを探します（distinct_idではありません）",
    "",
    "現在のdidの桁数が正しくありません（32桁、36桁、40桁）。確認後に再度追加してください",
]


@waves_add_ck.on_prefix(
    ("token追加", "TOKEN追加", "Token追加", "ck追加", "CK追加"), block=True
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
    if "成功" in msg or "ログイン成功" in msg:
        user = await WavesUser.get_user_by_attr(ev.user_id, ev.bot_id, "cookie", ck)
        if user:
            return await login_success_msg(bot, ev, user)

    await bot.send(msg, at_sender)


@waves_del_ck.on_command(
    ("token削除", "TOKEN削除", "Token削除", "ck削除", "CK削除"), block=True
)
async def send_waves_del_ck_msg(bot: Bot, ev: Event):
    at_sender = True if ev.group_id else False
    uid = ev.text.strip()
    if not uid or len(uid) != 9:
        return await bot.send(
            f"[鳴潮] このコマンドの末尾に正しい特徴コードが必要です！ \n例：【{PREFIX}token削除123456789】\n",
            at_sender,
        )
    await bot.send(await delete_cookie(ev, uid), at_sender)


@waves_get_ck.on_fullmatch(
    ("token取得", "TOKEN取得", "Token取得", "ck取得", "CK取得"), block=True
)
async def send_waves_get_ck_msg(bot: Bot, ev: Event):
    await bot.send(await get_cookie(bot, ev))


@waves_del_all_invalid_ck.on_fullmatch(("無効token削除"), block=True)
async def delete_all_invalid_cookie(bot: Bot, ev: Event):
    at_sender = True if ev.group_id else False
    del_len = await WavesUser.delete_all_invalid_cookie()
    await bot.send(f"[鳴潮] 無効tokenを【{del_len}】個削除しました\n", at_sender)


@scheduler.scheduled_job("cron", hour=23, minute=30)
async def auto_delete_all_invalid_cookie():
    DelInvalidCookie = WutheringWavesConfig.get_config("DelInvalidCookie").data
    if not DelInvalidCookie:
        return
    del_len = await WavesUser.delete_all_invalid_cookie()
    if del_len == 0:
        return
    msg = f"[鳴潮] 無効tokenを【{del_len}】個削除しました"
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
    logger.info(f"[鳴潮]管理者への無効token削除結果の送信: {msg}")


@waves_admin_query_uid.on_command(("特徴コード照会", "UID照会"), block=True)
async def admin_query_uid_binding(bot: Bot, ev: Event):
    """管理者UID連携情報照会"""
    at_sender = True if ev.group_id else False
    uid = ev.text.strip().replace("uid", "").replace("UID", "")

    if not uid:
        return await bot.send(
            f"❌ 照会するUIDを入力してください！\n形式：特徴コード照会 123456789\n",
            at_sender,
        )

    if len(uid) != 9 or not uid.isdigit():
        return await bot.send(
            f"❌ UIDの形式が正しくありません！9桁の数字のUIDを入力してください\n例：連携710596960\n",
            at_sender,
        )

    try:
        # UID連携情報を照会
        bind_info = await WavesBind.get_uid_bind_info(uid)

        if not bind_info:
            return await bot.send(
                f"🔍 **UID照会結果**\n\n"
                f"UID: `{uid}`\n"
                f"状態: ❌ 未連携\n"
                f"説明: このUIDはまだどのユーザーにも連携されていません",
                at_sender,
            )

        # 連携時間をフォーマット
        bind_time = bind_info.get("bind_time", 0)
        if bind_time:
            import time

            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(bind_time))
        else:
            time_str = "不明"

        # ユーザーの他の連携UIDを取得
        all_uids = bind_info.get("all_uids", [])
        other_uids = [u for u in all_uids if u != uid]

        # 応答メッセージを構築
        message = f"🔍 **UID照会結果**\n\n"
        message += f"UID: `{uid}`\n"
        message += f"状態: ✅ 連携済み\n"
        message += f"連携ユーザーID: `{bind_info['user_id']}`\n"
        message += f"プラットフォーム: `{bind_info['bot_id']}`\n"
        message += f"連携時間: {time_str}\n"

        if bind_info.get("group_id"):
            message += f"グループID: `{bind_info['group_id']}`\n"

        if other_uids:
            message += f"このユーザーの他の連携UID: `{', '.join(other_uids)}`\n"

        return await bot.send(message, at_sender)

    except Exception as e:
        logger.error(f"[鳴潮] 管理者UID照会失敗: {e}")
        return await bot.send(
            f"❌ 照会失敗！UIDの形式を確認するか、技術サポートに連絡してください\nエラー: {str(e)}",
            at_sender,
        )


@waves_bind_uid.on_command(
    (
        "連携",
        "切り替え",
        "全特徴コード削除",
        "全UID削除",
        "削除",
        "確認",
    ),
    block=True,
)
async def send_waves_bind_uid_msg(bot: Bot, ev: Event):
    uid = ev.text.strip().replace("uid", "").replace("UID", "")
    qid = ev.user_id
    if ev.bot_id == "discord" or ev.bot_id == "qqgroup":
        await sync_non_onebot_user_avatar(ev)

    at_sender = True if ev.group_id else False

    if "連携" in ev.command:
        if not uid:
            return await bot.send(
                f"このコマンドには正しいuidが必要です！\n{PREFIX}連携uid\n", at_sender
            )

        # UIDがブラックリストにないか確認
        from ..utils.util import is_uid_banned

        if is_uid_banned(uid):
            return await bot.send(
                f"[鳴潮] このUID[{uid}]は連携が禁止されており、すべての機能が使用できません！\n",
                at_sender,
            )

        uid_list = await WavesBind.get_uid_list_by_game(qid, ev.bot_id)

        # 連携制限を確認
        max_bind_num: int = WutheringWavesConfig.get_config("MaxBindNum").data

        # 連携上限に達しているか確認
        if uid_list and len(uid_list) >= max_bind_num:
            return await bot.send(
                f"[鳴潮] 特徴コード連携が上限に達しました（{max_bind_num}個）\n",
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
                0: f"[鳴潮] [{uid}]連携成功！\n\n現在国際服ユーザーが使用できる機能は限られています\n国服ユーザーは【{PREFIX}ログイン】を使用し、【{PREFIX}パネル更新】でキャラクターパネルを更新してください\n国際服ユーザーは【{PREFIX}分析】でパネルをアップロードしてください\n【{PREFIX}確認】で現在連携中のUIDを確認できます\nキャラクターパネル更新後、【{PREFIX}暗主ランキング】で暗主ランキングを照会できます\nプレイヤーのニックネームが特殊な言語の場合は、ニックネーム変更で名前を変更できます\n",
                -1: f"[鳴潮] 特徴コード[{uid}]の桁数が正しくありません！\n 連携710596960\n",
                -2: f"[鳴潮] 特徴コード[{uid}]は既に連携済みです！\n",
                -3: "[鳴潮] 入力形式が間違っています！\n",
                -4: f"[鳴潮] この[{uid}]は既に他のユーザーが使用しており、重複連携は禁止されています！\n",
            },
            at_sender=at_sender,
        )
    elif "切り替え" in ev.command:
        retcode = await WavesBind.switch_uid_by_game(qid, ev.bot_id, uid)
        if retcode == 0:
            uid_list = await WavesBind.get_uid_list_by_game(qid, ev.bot_id)
            if uid_list:
                _buttons: List[Any] = []
                for uid in uid_list:
                    _buttons.append(WavesButton(f"{uid}", f"切り替え{uid}"))
                return await bot.send_option(
                    f"[鳴潮] [{uid_list[0]}]に切り替えました！\n", _buttons
                )
            else:
                return await bot.send("[鳴潮] 現在UIDを連携していません\n", at_sender)
        else:
            return await bot.send(
                f"[鳴潮] 現在UID[{uid}]を連携していません\n", at_sender
            )
    elif "確認" in ev.command:
        uid_list = await WavesBind.get_uid_list_by_game(qid, ev.bot_id)
        if uid_list:
            uids = "\n".join(uid_list)
            buttons: List[Any] = []
            for uid in uid_list:
                buttons.append(WavesButton(f"{uid}", f"切り替え{uid}"))
            return await bot.send_option(
                f"[鳴潮] 現在連携中のUIDリスト：\n{uids}\n", buttons
            )
        else:
            return await bot.send("[鳴潮] 現在UIDを連携していません\n", at_sender)
    elif (
        "全削除" in ev.command
        or "全特徴コード削除" in ev.command
        or "全UID削除" in ev.command
    ):
        retcode = await WavesBind.update_data(
            user_id=qid,
            bot_id=ev.bot_id,
            **{WavesBind.get_gameid_name(None): None},
        )
        if retcode == 0:
            return await bot.send("[鳴潮] 全特徴コード削除成功！\n", at_sender)
        else:
            return await bot.send("[鳴潮] 現在UIDを連携していません\n", at_sender)
    else:
        if not uid:
            return await bot.send(
                f"[鳴潮] このコマンドの末尾に正しい特徴コードが必要です！\n例：【{PREFIX}削除123456789】\n",
                at_sender,
            )
        data = await WavesBind.delete_uid(qid, ev.bot_id, uid)
        return await send_diff_msg(
            bot,
            data,
            {
                0: f"[鳴潮] 特徴コード[{uid}]削除成功！\n",
                -1: f"[鳴潮] この特徴コード[{uid}]は連携リストにありません！\n",
            },
            at_sender=at_sender,
        )


async def sync_non_onebot_user_avatar(ev: Event):
    """イベントからアバター avatar_hash を抽出し、データベースの hash マッピングを自動更新"""
    avatar_hash = "error"
    if ev.bot_id == "discord":
        avatar_url = ev.sender.get("avatar")
        if not avatar_url:
            logger.error("Discord イベントに avatar フィールドがありません")
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
    ("ニックネーム変更", "名前変更", "ニックネーム修正", "名前修正"), block=True
)
async def change_nickname(bot: Bot, ev: Event):
    """プレイヤーニックネーム変更コマンド"""
    at_sender = True if ev.group_id else False
    new_nickname = ev.text.strip()

    if not new_nickname:
        return await bot.send(
            f"❌ 新しいニックネームを入力してください！\n"
            f"形式：ニックネーム変更 新しいニックネーム\n"
            f"例：@ボット ニックネーム変更 私の新しいニックネーム",
            at_sender,
        )

    # ニックネームの長さを確認
    if len(new_nickname) > 20:
        return await bot.send(
            "❌ ニックネームは20文字以内で入力してください！", at_sender
        )

    if len(new_nickname) < 1:
        return await bot.send("❌ ニックネームは空にできません！", at_sender)

    try:
        # ユーザーが連携しているUIDを取得
        uid_list = await WavesBind.get_uid_list_by_game(ev.user_id, ev.bot_id)

        if not uid_list:
            return await bot.send(
                "❌ UIDを連携していません！\n"
                f"まず @ボット 連携 あなたのUID を使用して連携してください",
                at_sender,
            )

        # 最初に連携されたUIDを使用
        uid = uid_list[0]

        # 必要なモジュールをインポート
        from ..wutheringwaves_analyzecard.user_info_utils import (
            save_user_info,
            get_user_detail_info,
        )

        # 現在のユーザー情報を取得
        current_user_info = await get_user_detail_info(uid)

        # ニックネームを更新
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

        # 成功メッセージを送信
        await bot.send(
            f"✅ ニックネーム変更成功！\n"
            f"UID: {uid}\n"
            f"新しいニックネーム: {new_nickname}\n\n"
            f"💡 ヒント：ニックネームが更新されました。次回関連機能を使用する際に新しいニックネームが表示されます",
            at_sender,
        )

        logger.info(
            f"[鳴潮] ユーザー {ev.user_id} がニックネームを変更しました: {new_nickname} (UID: {uid})"
        )

    except Exception as e:
        logger.error(f"[鳴潮] ニックネーム変更失敗: {e}")
        await bot.send(
            f"❌ ニックネーム変更失敗！\n"
            f"エラー: {str(e)}\n"
            f"UIDが正しいか確認するか、管理者に連絡してください",
            at_sender,
        )
