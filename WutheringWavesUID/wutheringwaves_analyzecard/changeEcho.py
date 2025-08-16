from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger

from ..utils.error_reply import WAVES_CODE_103
from ..utils.hint import error_reply
from ..utils.resource.RESOURCE_PATH import PLAYER_PATH
from ..wutheringwaves_config import PREFIX
from ..utils.refresh_char_detail import save_card_info
from ..utils.database.models import WavesBind
from ..utils.waves_api import waves_api
from ..utils.name_convert import (
    alias_to_char_name, 
    alias_to_sonata_name,
    phantom_id_to_phantom_name
)

from .char_fetterDetail import get_fetterDetail_from_sonata, get_first_echo_id_list

import aiofiles
import json
import copy
import re

async def change_echo(bot: Bot, ev: Event):
    at_sender = True if ev.group_id else False
    user_id = ev.at if ev.at else ev.user_id

    uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    if not uid:
        return await bot.send(error_reply(WAVES_CODE_103))

    # 更新groupid
    await WavesBind.insert_waves_uid(
        user_id, ev.bot_id, uid, ev.group_id, lenth_limit=9
    )

    if not waves_api.is_net(uid):
        return await bot.send("[鸣潮] 国服用户不支持修改角色数据\n", at_sender)

    char = ev.regex_dict.get("char")
    sonata = ev.regex_dict.get("sonata")
    phantom = bool(ev.regex_dict.get("echo"))  # 改为布尔值判断
    if not sonata and not phantom:
        return await bot.send(f"[鸣潮] 请正确使用命令：\n {PREFIX}改{char}套装合鸣效果 (可使用 [...合鸣一3合鸣二2] 改为3+2合鸣,按顺序修改) --合鸣效果可用前两字缩写 \n {PREFIX}改{char}声骸 --修改当前套装下的首位声骸\n", at_sender)

    char_name = alias_to_char_name(char)
    if char == "漂泊者":
        char_name = char # 匹配本地用，不接受alias的结果
    char_name_print = re.sub(r'[^\u4e00-\u9fa5A-Za-z0-9\s]', '', char_name) # 删除"漂泊者·衍射"的符号

    bool_get, old_data = await get_local_all_role_detail(uid)
    if not bool_get:
        return await bot.send(f"[鸣潮] 用户{uid}数据不存在，请先使用【{PREFIX}分析】上传{char_name_print}角色数据\n", at_sender)

    char_id, roleName = await get_char_name_from_local(char_name, old_data)
    if not char_id:
        return await bot.send(f"[鸣潮] 角色{char_name_print}不存在，请先使用【{PREFIX}分析】上传角色数据\n", at_sender)
    char_name_print = re.sub(r'[^\u4e00-\u9fa5A-Za-z0-9\s]', '', roleName) # 删除"漂泊者·衍射"的符号

    bool_change, waves_data = await change_sonata_and_first_echo(bot, char_id, sonata, phantom, old_data)
    if not bool_change or isinstance(waves_data, str):
        return await bot.send(f"[鸣潮] 修改角色{char_name_print}数据失败，{waves_data}\n", at_sender)

    # 覆盖更新
    await save_card_info(uid, waves_data)
    return await bot.send(f"[鸣潮] 修改角色{char_name_print}数据成功，使用【{PREFIX}{char_name_print}面板】查看您的角色面板\n", at_sender)

async def get_local_all_role_detail(uid: str) -> tuple[bool, dict]:
    _dir = PLAYER_PATH / uid
    _dir.mkdir(parents=True, exist_ok=True)
    path = _dir / "rawData.json"

    role_data = {}
    if path.exists():
        try:
            async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
                data = json.loads(await f.read())
                role_data = {d["role"]["roleId"]: d for d in data}
        except Exception as e:
            logger.error(f"[鸣潮] 基础数据get failed {path}:", e)
            path.unlink(missing_ok=True)
    else:
        return False, role_data

    return True, role_data

async def get_char_name_from_local(char_name: str, role_data: dict):
    for char_id, role_info in role_data.items():
        roleName = role_info.get("role").get("roleName")
        if char_name in roleName:
            logger.info(f"[鸣潮] 角色{char_name}与{roleName}匹配")
            return int(char_id), roleName
    # 未找到匹配角色
    return None, None

async def change_sonata_and_first_echo(bot: Bot, char_id: int, sonata_a: str, phantom_a: bool, role_data: dict):
    # 检查角色是否存在
    if char_id not in role_data:
        return False, "角色不存在！"
    char_data = copy.deepcopy(role_data[char_id])

    # 初始化
    waves_data = []

    if sonata_a:
        phantom_a = True # 启用首位声骸替换
        sonata_parts = re.findall(r'([^\d]+)(\d*)', sonata_a)
        ECHO = []
        
        for sonata_part, num in sonata_parts:
            # 如果没有数字，默认重复1次
            num = int(num) if num else 5
            sonata = alias_to_sonata_name(sonata_part)
            if sonata:
                ECHO.extend([await get_fetterDetail_from_sonata(sonata)] * num)

        if not ECHO:
            return False, "请输入正确的套装名(可用前两字缩写)"
        if len(ECHO) != len(char_data["phantomData"]["equipPhantomList"]):
            return False, f"套装数 {len(ECHO)}与角色声骸数 {len(char_data['phantomData']['equipPhantomList'])}不一致"
        logger.info(f"[鸣潮] 修改套装为:{sonata_parts}")


        echo_num = len(char_data["phantomData"]["equipPhantomList"])
        for i, echo in enumerate(char_data["phantomData"]["equipPhantomList"]):
            echo["fetterDetail"] = ECHO[i]["fetterDetail"]
            echo["phantomProp"]["name"] = ECHO[i]["phantomProp"]["name"]
            echo["fetterDetail"]["num"] = echo_num
        
    if phantom_a:
        sonata = None
        # 构建可选项（标注cost层级 与 对应套装名称）
        phantom_id_list_groups = []
        options = []
        flat_choices = []  # 用于存储扁平化的选项信息（cost + id）

        for echo in char_data["phantomData"]["equipPhantomList"]:
            if not sonata or echo["fetterDetail"]["name"] != sonata:
                sonata = echo["fetterDetail"]["name"]
                phantom_id_list = await get_first_echo_id_list(sonata)
        
                phantom_id_list_groups.extend(phantom_id_list)
                for group in phantom_id_list:
                    cost = group["cost"]
                    for phantom_id in group["list"]:
                        options.append(
                            f"{len(options)+1}: [套装:{sonata[:2]} {cost}c] {phantom_id_to_phantom_name(phantom_id)}"
                        )
                        flat_choices.append({"cost": cost, "id": phantom_id})

        TEXT_GET_RESP = (
            "[鸣潮] 请于30秒内选择首位声骸替换为(仅提供有首位buff加成的)：\n"
            + "\n".join(options)
            + "\n请输入序号（1-{}）选择".format(len(options))
        )

        resp = await bot.receive_resp(TEXT_GET_RESP)
        if resp is not None and resp.content[0].data is not None and resp.content[0].type == "text" and resp.content[0].data.isdigit():
            choice = int(resp.content[0].data) - 1
            if 0 <= choice < len(flat_choices):
                selected = flat_choices[choice]
                target_cost = selected["cost"]
                selected_id = selected["id"]
                
                # 获取该 cost 层级的全部可选 ID
                same_cost_ids = [echo_id for g in phantom_id_list_groups if g["cost"] == target_cost for echo_id in g["list"]]
                
                other_phantoms = [p for p in same_cost_ids if p != selected_id]

                first_change_bool = True # 只修改第一顺位声骸
                for echo in char_data["phantomData"]["equipPhantomList"]:
                    if int(echo["cost"]) == target_cost:
                        if first_change_bool:
                            echo["phantomProp"]["phantomId"] = selected_id
                            echo["phantomProp"]["name"] = phantom_id_to_phantom_name(selected_id)
                            first_change_bool = False
                        else:
                            if other_phantoms:
                                echo["phantomProp"]["phantomId"] = other_phantoms[0]  # 取第一个不同的元素
                                echo["phantomProp"]["name"] = phantom_id_to_phantom_name(other_phantoms[0])
                            else:
                                pass


                logger.info(f"[鸣潮] 修改cost声骸id为:{selected_id}")
            else:
                return False, "请检查命令的正确性"
        else:
            return False, "请检查命令的正确性"
    
    # 更新数据
    role_data[char_id] = char_data
    waves_data = list(role_data.values())
    
    return True, waves_data


async def get_local_all_role_info(uid: str) -> tuple[bool, dict]:
    _dir = PLAYER_PATH / uid
    _dir.mkdir(parents=True, exist_ok=True)
    path = _dir / "rawData.json"

    # 初始化标准数据结构
    role_data = {
        'roleList': [],
        'showRoleIdList': [],
        'showToGuest': False
    }
    
    if not path.exists():
        return False, role_data
        
    try:
        async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
            raw_data = json.loads(await f.read())
            
            # 正确解析角色列表
            if isinstance(raw_data, list):
                for item in raw_data:
                    if "role" in item:
                        role_data["roleList"].append(item["role"])
            
        return True, role_data
    except Exception as e:
        logger.error(f"[鸣潮] 数据解析失败 {path}:", e)
        path.unlink(missing_ok=True)
        return False, role_data



async def change_weapon_resonLevel(waves_id: str, char: str, reson_level: int):
    logger.info(f"[鸣潮] 准备修改{waves_id}{char}角色武器精炼为：{reson_level}")
    if not waves_api.is_net(waves_id):
        return "[鸣潮] 不支持修改国服用户角色武器数据!"
    
    bool_get, old_data = await get_local_all_role_detail(waves_id)
    if not bool_get:
        return f"[鸣潮] 用户{waves_id}数据不存在，请先使用【{PREFIX}分析】上传角色数据"

    # 初始化
    waves_data = []

    if "所有" in char:
        for char_id in old_data:
            # 修改
            old_data[char_id]["weaponData"]["resonLevel"] = reson_level
    else:
        char_name = alias_to_char_name(char)
        if char == "漂泊者":
            char_name = char # 匹配本地用，不接受alias的结果
        char_id, roleName = await get_char_name_from_local(char_name, old_data)
        if not char_id:
            return f"[鸣潮] 角色{char_name}不存在，请先使用【{PREFIX}分析】上传角色数据"

        # 检查角色是否存在
        if char_id not in old_data:
            return f"[鸣潮] {char_name}角色不存在！请检查命令是否正确！"

        # 修改
        old_data[char_id]["weaponData"]["resonLevel"] = reson_level

    
    waves_data = list(old_data.values())

    # 覆盖更新
    await save_card_info(waves_id, waves_data)
    return f"[鸣潮] 修改用户{waves_id}{char}角色武器精炼为{reson_level}成功！"

    