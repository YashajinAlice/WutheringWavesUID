import json
import asyncio
from typing import Dict, List, Union, Optional

import aiofiles
from gsuid_core.models import Event
from gsuid_core.logger import logger

from ..utils.hint import error_reply
from ..utils.waves_api import waves_api
from ..utils.queues.queues import put_item
from ..utils.queues.const import QUEUE_SCORE_RANK
from ..utils.resource.RESOURCE_PATH import PLAYER_PATH
from ..utils.util import get_version, send_master_info
from ..utils.api.model import RoleList, AccountBaseInfo
from ..utils.error_reply import WAVES_CODE_101, WAVES_CODE_102
from ..utils.expression_ctx import WavesCharRank, get_waves_char_rank


# 延遲導入以避免循環依賴
def get_config():
    from ..wutheringwaves_config import WutheringWavesConfig

    return WutheringWavesConfig


from .resource.constant import SPECIAL_CHAR_INT_ALL


def is_use_global_semaphore() -> bool:
    config = get_config()
    return config.get_config("UseGlobalSemaphore").data or False


def get_refresh_card_concurrency() -> int:
    config = get_config()
    return config.get_config("RefreshCardConcurrency").data or 2


class SemaphoreManager:
    def __init__(self):
        self._last_config: int = get_refresh_card_concurrency()
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(value=self._last_config)
        self._semaphore_lock = asyncio.Lock()

    async def get_semaphore(self) -> asyncio.Semaphore:
        current_config = get_refresh_card_concurrency()

        if is_use_global_semaphore():
            return await self._get_semaphore(current_config)  # 全局模式
        else:
            return asyncio.Semaphore(value=current_config)  # 独立模式

    async def _get_semaphore(self, current_config: int) -> asyncio.Semaphore:
        if self._last_config != current_config:
            async with self._semaphore_lock:
                if self._last_config != current_config:
                    self._semaphore = asyncio.Semaphore(value=current_config)
                    self._last_config = current_config

        return self._semaphore


semaphore_manager = SemaphoreManager()


async def send_card(
    uid: str,
    user_id: str,
    save_data: List,
    is_self_ck: bool = False,
    token: Optional[str] = "",
    role_info: Optional[RoleList] = None,
    waves_data: Optional[List] = None,
):
    waves_char_rank: Optional[List[WavesCharRank]] = None

    WutheringWavesConfig = get_config()
    WavesToken = WutheringWavesConfig.get_config("WavesToken").data

    if WavesToken:
        waves_char_rank = await get_waves_char_rank(uid, save_data, True)

    if (
        is_self_ck
        and token
        and waves_char_rank
        and WavesToken
        and role_info
        and waves_data
        and user_id
    ):
        # 单角色上传排行
        if len(waves_data) != 1 and len(role_info.roleList) != len(save_data):
            logger.warning(
                f"角色数量不一致，role_info.roleNum:{len(role_info.roleList)} != waves_char_rank:{len(save_data)}"
            )
            return
        account_info = await waves_api.get_base_info(uid, token=token)
        if not account_info.success:
            return account_info.throw_msg()
        account_info = AccountBaseInfo.model_validate(account_info.data)
        if len(waves_data) != 1 and account_info.roleNum != len(save_data):
            logger.warning(
                f"角色数量不一致，role_info.roleNum:{account_info.roleNum} != waves_char_rank:{len(save_data)}"
            )
            return
        metadata = {
            "user_id": user_id,
            "waves_id": f"{account_info.id}",
            "kuro_name": account_info.name,
            "version": get_version(),
            "char_info": [r.to_rank_dict() for r in waves_char_rank],
            "role_num": account_info.roleNum,
        }
        await put_item(QUEUE_SCORE_RANK, metadata)


async def save_card_info(
    uid: str,
    waves_data: List,
    waves_map: Optional[Dict] = None,
    user_id: str = "",
    is_self_ck: bool = False,
    token: str = "",
    role_info: Optional[RoleList] = None,
):
    if len(waves_data) == 0:
        return
    _dir = PLAYER_PATH / uid
    _dir.mkdir(parents=True, exist_ok=True)
    path = _dir / "rawData.json"

    old_data = {}
    if path.exists():
        try:
            async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
                old = json.loads(await f.read())
                old_data = {d["role"]["roleId"]: d for d in old}
        except Exception as e:
            logger.exception(f"save_card_info get failed {path}:", e)
            path.unlink(missing_ok=True)

    #
    refresh_update = {}
    refresh_unchanged = {}
    for item in waves_data:
        role_id = item["role"]["roleId"]

        if role_id in SPECIAL_CHAR_INT_ALL:
            # 漂泊者预处理
            for piaobo_id in SPECIAL_CHAR_INT_ALL:
                old = old_data.get(piaobo_id)
                if not old:
                    continue
                if piaobo_id != role_id:
                    del old_data[piaobo_id]

        old = old_data.get(role_id)
        if old != item:
            refresh_update[role_id] = item
        else:
            refresh_unchanged[role_id] = item

        old_data[role_id] = item

    save_data = list(old_data.values())

    if not waves_api.is_net(uid):
        await send_card(
            uid, user_id, save_data, is_self_ck, token, role_info, waves_data
        )

    try:
        async with aiofiles.open(path, "w", encoding="utf-8") as file:
            await file.write(json.dumps(save_data, ensure_ascii=False))
    except Exception as e:
        logger.exception(f"save_card_info save failed {path}:", e)

    if waves_map:
        waves_map["refresh_update"] = refresh_update
        waves_map["refresh_unchanged"] = refresh_unchanged


async def refresh_char(
    ev: Event,
    uid: str,
    user_id: str,
    ck: Optional[str] = None,  # type: ignore
    waves_map: Optional[Dict] = None,
    is_self_ck: bool = False,
    refresh_type: Union[str, List[str]] = "all",
) -> Union[str, List]:
    waves_datas = []
    if not ck:
        is_self_ck, ck = await waves_api.get_ck_result(uid, user_id, ev.bot_id)
    if not ck:
        return error_reply(WAVES_CODE_102)
    # 共鸣者信息
    role_info = await waves_api.get_role_info(uid, ck)
    if not role_info.success:
        return role_info.throw_msg()

    try:
        role_info = RoleList.model_validate(role_info.data)
    except Exception as e:
        logger.exception(f"{uid} 角色信息解析失败", e)
        msg = f"鸣潮特征码[{uid}]获取数据失败\n1.是否注册过库街区\n2.库街区能否查询当前鸣潮特征码数据"
        return msg

    semaphore = await semaphore_manager.get_semaphore()

    async def limited_get_role_detail_info(role_id, uid, ck):
        async with semaphore:
            return await waves_api.get_role_detail_info(role_id, uid, ck)

    if is_self_ck:
        tasks = [
            limited_get_role_detail_info(f"{r.roleId}", uid, ck)
            for r in role_info.roleList
            if refresh_type == "all"
            or (isinstance(refresh_type, list) and f"{r.roleId}" in refresh_type)
        ]
    else:
        if role_info.showRoleIdList:
            tasks = [
                limited_get_role_detail_info(f"{r}", uid, ck)
                for r in role_info.showRoleIdList
                if refresh_type == "all"
                or (isinstance(refresh_type, list) and f"{r}" in refresh_type)
            ]
        else:
            tasks = [
                limited_get_role_detail_info(f"{r.roleId}", uid, ck)
                for r in role_info.roleList
                if refresh_type == "all"
                or (isinstance(refresh_type, list) and f"{r.roleId}" in refresh_type)
            ]
    results = await asyncio.gather(*tasks)

    charId2chainNum: Dict[int, int] = {
        r.roleId: r.chainUnlockNum
        for r in role_info.roleList
        if isinstance(r.chainUnlockNum, int)
    }
    # 处理返回的数据
    for role_detail_info in results:
        if not role_detail_info.success:
            continue

        role_detail_info = role_detail_info.data
        if (
            not isinstance(role_detail_info, dict)
            or "role" not in role_detail_info
            or role_detail_info["role"] is None
            or "level" not in role_detail_info
            or role_detail_info["level"] is None
        ):
            continue
        if role_detail_info["phantomData"]["cost"] == 0:
            role_detail_info["phantomData"]["equipPhantomList"] = None
        try:
            # 扰我道心 难道谐振几阶还算不明白吗
            del role_detail_info["weaponData"]["weapon"]["effectDescription"]
        except Exception as _:
            pass

        # 修正共鸣链
        try:
            role_id = role_detail_info["role"]["roleId"]
            for i in role_detail_info["chainList"]:
                if i["order"] <= charId2chainNum[role_id]:
                    i["unlocked"] = True
                else:
                    i["unlocked"] = False
        except Exception as e:
            logger.exception(f"{uid} 共鸣链修正失败", e)

        # 修正合鸣效果
        try:
            if (
                role_detail_info["phantomData"]
                and role_detail_info["phantomData"]["equipPhantomList"]
            ):
                for i in role_detail_info["phantomData"]["equipPhantomList"]:
                    if not isinstance(i, dict):
                        continue
                    sonata_name = i.get("fetterDetail", {}).get("name", "")
                    if sonata_name == "雷曜日冕之冠":
                        i["fetterDetail"]["name"] = "荣斗铸锋之冠"  # type: ignore
        except Exception as e:
            logger.exception(f"{uid} 合鸣效果修正失败", e)

        waves_datas.append(role_detail_info)

    await save_card_info(
        uid,
        waves_datas,
        waves_map,
        user_id,
        is_self_ck=is_self_ck,
        token=ck,
        role_info=role_info,
    )

    if not waves_datas:
        if refresh_type == "all":
            return error_reply(WAVES_CODE_101)
        else:
            return error_reply(code=-110, msg="库街区暂未查询到角色数据")

    return waves_datas


async def refresh_char_from_pcap(
    ev: Event,
    uid: str,
    user_id: str,
    pcap_data: Dict,
    waves_map: Optional[Dict] = None,
    refresh_type: Union[str, List[str]] = "all",
) -> Union[str, List]:
    """基於 pcap 數據刷新角色面板"""
    try:
        from ..wutheringwaves_pcap.pcap_parser import PcapDataParser

        parser = PcapDataParser()
        role_detail_list = await parser.parse_pcap_data(pcap_data)

        if not role_detail_list:
            logger.warning(f"PCAP 數據解析結果為空: {user_id}")
            return []

        # 初始化 waves_map
        if waves_map is None:
            waves_map = {"refresh_update": {}, "refresh_unchanged": {}}

        waves_data = []

        # for role_detail in role_detail_list:
        #     role_id = role_detail["role"]["roleId"]
        #     # 標記為已更新
        #     waves_map["refresh_update"][str(role_id)] = role_detail

        async def limited_check_role_detail_info(r):
            role_name = r["role"]["roleName"]

            PhantomList = r["phantomData"]["equipPhantomList"]
            if PhantomList:
                for Phantom in PhantomList:
                    prop_list = []
                    if Phantom.get("mainProps"):
                        prop_list.extend(Phantom.get("mainProps"))
                    if Phantom.get("subProps"):
                        prop_list.extend(Phantom.get("subProps"))
                    for prop in prop_list:
                        if (
                            prop.get("attributeName")
                            and "缺失" in prop["attributeName"]
                        ):
                            await send_master_info(
                                f"[鸣潮] 刷新用户{user_id} id{uid} 角色{role_name} 的词条数据, 遇到[{prop['attributeName']}]"
                            )
                            logger.warning(
                                f"[鸣潮] 刷新用户{user_id} id{uid} 角色{role_name} 的词条数据, 遇到[{prop['attributeName']}]"
                            )
                            return

            waves_data.append(r)

        # 确定需要处理的角色
        if refresh_type == "all":
            roles_to_process = role_detail_list
        elif isinstance(refresh_type, list):
            # 将 refresh_type 转换为字符串列表以确保类型一致
            refresh_type_str = [str(x) for x in refresh_type]
            roles_to_process = [
                r
                for r in role_detail_list
                if str(r["role"]["roleId"]) in refresh_type_str
            ]
        else:
            logger.warning(f"无效的 refresh_type: {refresh_type}")
            roles_to_process = []

        # 并行处理所有角色
        if roles_to_process:
            tasks = [limited_check_role_detail_info(r) for r in roles_to_process]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 检查并记录任何异常
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    role_id = roles_to_process[i]["role"]["roleId"]
                    logger.error(f"处理角色 {role_id} 时发生异常: {result}")

        # 儲存數據到數據庫
        await save_card_info(
            uid,
            waves_data,
            waves_map,
            user_id,
            is_self_ck=True,  # PCAP 模式視為自登錄
        )
        return waves_data

    except Exception as e:
        logger.exception(f"PCAP 數據刷新失敗: {user_id}", e)
        return []
