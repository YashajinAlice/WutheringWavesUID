import json
from typing import Any, Dict, Union, Generator

import aiofiles
from gsuid_core.logger import logger

from ..utils.api.model import RoleDetailData
from .resource.RESOURCE_PATH import PLAYER_PATH


def migrate_phantom_data(role_data: dict) -> dict:
    """遷移舊格式的聲骸數據，添加缺失的phantomId字段"""
    if "phantomData" in role_data and role_data["phantomData"]:
        phantom_data = role_data["phantomData"]
        if "equipPhantomList" in phantom_data and phantom_data["equipPhantomList"]:
            equip_list = phantom_data["equipPhantomList"]

            # 處理兩種可能的數據結構
            phantom_list = None
            if isinstance(equip_list, dict) and "list" in equip_list:
                # 新格式: {"list": [...]}
                phantom_list = equip_list["list"]
            elif isinstance(equip_list, list):
                # 舊格式: [...] (直接是列表)
                phantom_list = equip_list

            if phantom_list:
                for phantom in phantom_list:
                    if phantom and isinstance(phantom, dict):
                        if "phantomProp" in phantom and phantom["phantomProp"]:
                            phantom_prop = phantom["phantomProp"]
                            # 如果缺少phantomId，使用phantomPropId作為默認值
                            if (
                                "phantomId" not in phantom_prop
                                and "phantomPropId" in phantom_prop
                            ):
                                phantom_prop["phantomId"] = phantom_prop[
                                    "phantomPropId"
                                ]
                                logger.info(
                                    f"遷移聲骸數據: 添加phantomId={phantom_prop['phantomId']}"
                                )
    return role_data


async def get_all_role_detail_info_list(
    uid: str,
) -> Union[Generator[RoleDetailData, Any, None], None]:
    path = PLAYER_PATH / uid / "rawData.json"
    if not path.exists():
        return None
    try:
        async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
            player_data = json.loads(await f.read())
    except Exception as e:
        logger.exception(f"get role detail info failed {path}:", e)
        path.unlink(missing_ok=True)
        return None

    # 遷移舊格式數據
    migrated_data = []
    for role_data in player_data:
        migrated_role_data = migrate_phantom_data(role_data)
        migrated_data.append(migrated_role_data)

    try:
        return iter(RoleDetailData(**r) for r in migrated_data)
    except Exception as e:
        logger.exception(f"數據模型驗證失敗 {path}: {e}")
        # 如果還是失敗，嘗試刪除損壞的數據文件
        logger.warning(f"刪除損壞的數據文件: {path}")
        path.unlink(missing_ok=True)
        return None


async def get_all_role_detail_info(uid: str) -> Union[Dict[str, RoleDetailData], None]:
    _all = await get_all_role_detail_info_list(uid)
    if not _all:
        return None
    return {r.role.roleName: r for r in _all}


async def get_all_roleid_detail_info(
    uid: str,
) -> Union[Dict[str, RoleDetailData], None]:
    _all = await get_all_role_detail_info_list(uid)
    if not _all:
        return None
    return {str(r.role.roleId): r for r in _all}


async def get_all_roleid_detail_info_int(
    uid: str,
) -> Union[Dict[int, RoleDetailData], None]:
    _all = await get_all_role_detail_info_list(uid)
    if not _all:
        return None
    return {r.role.roleId: r for r in _all}
