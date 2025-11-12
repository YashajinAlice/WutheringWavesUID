from typing import List, Union, Optional

from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ..utils.api.api import GAME_ID
from ..utils.waves_api import waves_api
from ..utils.api.model import KuroWavesUserInfo
from ..utils.api.request_util import PLATFORM_SOURCE
from ..utils.database.models import WavesBind, WavesUser
from ..utils.error_reply import ERROR_CODE, WAVES_CODE_103


async def add_cookie(ev: Event, ck: str, did: str) -> str:
    platform = PLATFORM_SOURCE
    kuroWavesUserInfos = await waves_api.get_kuro_role_list(ck, did)
    if (
        not kuroWavesUserInfos.success
        or not kuroWavesUserInfos.data
        or not isinstance(kuroWavesUserInfos.data, list)
    ):
        return kuroWavesUserInfos.throw_msg()

    kuroWavesUserInfos = kuroWavesUserInfos.data

    # 連携制限を確認
    from ..wutheringwaves_config import WutheringWavesConfig

    max_bind_num: int = WutheringWavesConfig.get_config("MaxBindNum").data

    # 現在連携中のUIDリストを取得
    current_uid_list = await WavesBind.get_uid_list_by_game(ev.user_id, ev.bot_id)
    current_bind_count = len(current_uid_list) if current_uid_list else 0

    role_list = []
    new_bind_count = 0  # 新規連携カウント

    for kuroWavesUserInfo in kuroWavesUserInfos:
        data = KuroWavesUserInfo.model_validate(kuroWavesUserInfo)
        if data.gameId != GAME_ID:
            continue

        # UIDがブラックリストにないか確認
        from ..utils.util import is_uid_banned
        
        if is_uid_banned(data.roleId):
            # ブラックリストのUIDをスキップし、連携しない
            continue

        # このUIDが既に連携されているか確認
        user = await WavesUser.get_user_by_attr(
            ev.user_id, ev.bot_id, "uid", data.roleId
        )

        # 新しいUIDで連携上限に達している場合はスキップ
        if not user and current_bind_count + new_bind_count >= max_bind_num:
            continue

        succ, bat = await waves_api.get_request_token(
            data.roleId,
            ck,
            did,
            data.serverId,
        )
        if not succ or not bat:
            return bat

        if user:
            await WavesUser.update_data_by_data(
                select_data={
                    "user_id": ev.user_id,
                    "bot_id": ev.bot_id,
                    "uid": data.roleId,
                },
                update_data={
                    "cookie": ck,
                    "status": "",
                    "platform": platform,
                },
            )
        else:
            await WavesUser.insert_data(
                ev.user_id,
                ev.bot_id,
                cookie=ck,
                uid=data.roleId,
                platform=platform,
            )

        # 更新bat
        await WavesUser.update_data_by_data(
            select_data={
                "user_id": ev.user_id,
                "bot_id": ev.bot_id,
                "uid": data.roleId,
            },
            update_data={"bat": bat, "did": did},
        )

        res = await WavesBind.insert_waves_uid(
            ev.user_id, ev.bot_id, data.roleId, ev.group_id, lenth_limit=9
        )
        if res == 0 or res == -2:
            await WavesBind.switch_uid_by_game(ev.user_id, ev.bot_id, data.roleId)
            # 新規連携の場合はカウンターを増やす
            if not user:
                new_bind_count += 1
        elif res == -4:
            # UIDが既に他のユーザーに連携されているため、このUIDをスキップ
            continue

        role_list.append(
            {
                "名前": data.roleName,
                "特徴コード": data.roleId,
            }
        )

    if len(role_list) == 0:
        # 連携制限による失敗か確認
        if current_bind_count >= max_bind_num:
            return f"[鳴潮] ログイン失敗！\n❌ 特徴コード連携が上限に達しました（{max_bind_num}個）"
        return "ログイン失敗\n"

    msg = []
    for role in role_list:
        msg.append(f"[鳴潮]【{role['名前']}】特徴コード【{role['特徴コード']}】ログイン成功！")

    # 連携制限のヒントを追加
    final_bind_count = current_bind_count + new_bind_count
    if final_bind_count >= max_bind_num * 0.8:  # 80%に達したらヒント
        msg.append(f"\n💡 現在 {final_bind_count}/{max_bind_num} 個のUIDを連携しています")

    return "\n".join(msg)


async def delete_cookie(ev: Event, uid: str) -> str:
    count = await WavesUser.delete_cookie(uid, ev.user_id, ev.bot_id)
    if count == 0:
        return f"[鳴潮] 特徴コード[{uid}]のtoken削除失敗！\n❌この特徴コードのtokenが存在しません！\n"
    return f"[鳴潮] 特徴コード[{uid}]のtoken削除成功！\n"


async def get_cookie(bot: Bot, ev: Event) -> Union[List[str], str]:
    uid_list = await WavesBind.get_uid_list_by_game(ev.user_id, ev.bot_id)
    if uid_list is None:
        return ERROR_CODE[WAVES_CODE_103]

    msg = []
    for uid in uid_list:
        waves_user: Optional[WavesUser] = await WavesUser.select_waves_user(
            uid, ev.user_id, ev.bot_id
        )
        if not waves_user:
            continue

        ck = await waves_api.get_self_waves_ck(uid, ev.user_id, ev.bot_id)
        if not ck:
            continue
        msg.append(f"鳴潮uid: {uid}")
        msg.append(f"token, did: {waves_user.cookie}, {waves_user.did}")
        msg.append("--------------------------------")

    if not msg:
        return "現在tokenを連携していないか、tokenがすべて無効になっています\n"

    return msg
