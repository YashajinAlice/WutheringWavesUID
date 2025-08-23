import re
import json
import random
from typing import Any
from pathlib import Path

from gsuid_core.logger import logger

from .detail_json import (
    DETAIL,
    SONATA_COST_1_ID,
    SONATA_COST_3_ID,
    SONATA_COST_4_ID,
)

PLUGIN_PATH = Path(__file__).parent.parent
FETTERDETAIL_PATH = PLUGIN_PATH / "utils/map/detail_json/sonata"


async def get_fetterDetail_from_char(char_id) -> list[dict[Any, Any]]:

    sonata = DETAIL[char_id]["fetterDetail"]

    if isinstance(sonata, dict):
        sonata_list = []
        for key, num in sonata.items():
            sonata_list.extend([await get_fetterDetail_from_sonata(key)] * num)
        return sonata_list

    return [await get_fetterDetail_from_sonata(sonata)] * 5


async def get_fetterDetail_from_sonata(sonata) -> dict:

    path = FETTERDETAIL_PATH / f"{sonata}.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    echo = {
        "cost": 1,
        "level": 25,
        "quality": 5,
        "fetterDetail": {
            "firstDescription": (data["set"].get("2", {}).get("desc") or ""),
            "groupId": 0,
            "iconUrl": "",
            "name": data["name"],
            "num": 5,
            "secondDescription": (data["set"].get("5", {}).get("desc") or ""),
            "tripleDescription": (data["set"].get("3", {}).get("desc") or ""),
        },
        "phantomProp": {
            "cost": 1,
            "iconUrl": "",
            "name": data["name"],
            "phantomId": 391070105,
            "phantomPropId": 0,
            "quality": 5,
            "skillDescription": "龟",
        },
    }
    return echo


async def get_first_echo_id_list(sonata_info):

    cost_4_list = []
    cost_3_list = []
    cost_1_list = []

    # 用于跟踪已添加的ID（避免重复）
    seen_ids = set()

    def add_unique(target, items):
        """将未出现过的ID添加到目标列表"""
        for item in items:
            if item not in seen_ids:
                seen_ids.add(item)
                target.append(item)

    if isinstance(sonata_info, dict):  # 处理多套装的情况
        for sonata_name in sonata_info.keys():
            add_unique(cost_4_list, SONATA_COST_4_ID.get(sonata_name, []))
            add_unique(cost_3_list, SONATA_COST_3_ID.get(sonata_name, []))
            add_unique(cost_1_list, SONATA_COST_1_ID.get(sonata_name, []))
    else:
        add_unique(cost_4_list, SONATA_COST_4_ID.get(sonata_info, []))
        add_unique(cost_3_list, SONATA_COST_3_ID.get(sonata_info, []))
        add_unique(cost_1_list, SONATA_COST_1_ID.get(sonata_info, []))

    phantom_id_list = [
        {"cost": 4, "list": cost_4_list},
        {"cost": 3, "list": cost_3_list},
        {"cost": 1, "list": cost_1_list},
    ]

    # 添加详细的调试日志
    logger.debug(f"[鸣潮]获取到套装：{sonata_info}的声骸id列表：{phantom_id_list}")
    logger.debug(
        f"[鸣潮]4cost数量: {len(cost_4_list)}, 3cost数量: {len(cost_3_list)}, 1cost数量: {len(cost_1_list)}"
    )

    # 如果某个cost没有选项，记录警告
    if not cost_3_list:
        logger.warning(f"[鸣潮]套装{sonata_info}没有3cost声骸选项")
    if not cost_1_list:
        logger.warning(f"[鸣潮]套装{sonata_info}没有1cost声骸选项")

    return phantom_id_list


# 全局变量用于追踪已使用的声骸ID
_used_echo_ids = set()


async def echo_data_to_cost(
    char_id, mainProps_first, cost4_counter=0
) -> tuple[int, int]:
    """
    根据主词条判断声骸cost并返回适配ID

    参数：
        char_name: str - 角色名称
        mainProps_first: dict - 主词条数据，需包含attributeName和attributeValue

    返回：
        tuple (echo_id, cost)
    """
    global _used_echo_ids

    # ---------- 常量定义 ----------
    # 主词条阈值配置 . change from utils.map.calc_score_script.py
    phantom_main_value = [
        {"name": "攻击", "values": ["18%", "30%", "33%"]},
        {"name": "生命", "values": ["22.8%", "30%", "33%"]},
        {"name": "防御", "values": ["18%", "38%", "41.8%"]},
    ]
    phantom_main_value_map = {i["name"]: i["values"] for i in phantom_main_value}

    # 属性类型定义
    FOUR_COST_ATTRS = {"暴击", "暴击伤害", "治疗效果加成"}
    THREE_COST_PATTERNS = [r"共鸣效率", r".*伤害加成"]
    BASE_COST_ATTRS = {"攻击", "生命", "防御"}

    # 默认ID配置
    ECHO_ID_COST_ONE = 6000054
    ECHO_ID_COST_THREE = 6000050

    # ---------- 初始化 ----------
    key = mainProps_first[0]["attributeName"]
    value = float(mainProps_first[0]["attributeValue"].strip("%"))
    key_little = mainProps_first[1]["attributeName"]  # 小词条

    # ---------- 获取角色配置 ----------
    try:
        # 获取完整的层级结构
        full_id_list = await get_first_echo_id_list(DETAIL[char_id]["fetterDetail"])
        # 提取各cost的列表
        echo_id_4_list = [
            echo_id
            for item in full_id_list
            if item["cost"] == 4
            for echo_id in item["list"]
        ]
        echo_id_3_list = [
            echo_id
            for item in full_id_list
            if item["cost"] == 3
            for echo_id in item["list"]
        ]
        echo_id_1_list = [
            echo_id
            for item in full_id_list
            if item["cost"] == 1
            for echo_id in item["list"]
        ]
    except KeyError as e:
        logger.error(f"[鸣潮]角色配置数据缺失: {e}")
        return ECHO_ID_COST_ONE, 1  # 降级处理
    except FileNotFoundError:
        logger.error(f"[鸣潮]角色{DETAIL[char_id]['name']}配置文件不存在")
        return ECHO_ID_COST_ONE, 1

    # ---------- 4cost分配id逻辑 ----------
    def select_cost4_id():
        """选择cost4的ID（实现44111逻辑）"""
        if len(echo_id_4_list) >= 2:
            used_idx = cost4_counter % 2  # 在0和1之间循环
            return echo_id_4_list[used_idx]
        elif len(echo_id_4_list) == 1:
            return echo_id_4_list[0]
        else:
            return ECHO_ID_COST_ONE  # 降级处理

    # ---------- 3cost分配id逻辑 ----------
    def select_cost3_id():
        """选择cost3的ID（避免重复）"""
        if echo_id_3_list:
            # 过滤掉已使用的ID
            available_ids = [id for id in echo_id_3_list if id not in _used_echo_ids]
            if available_ids:
                selected_id = random.choice(available_ids)
                _used_echo_ids.add(selected_id)
                logger.debug(
                    f"[鸣潮] 3cost声骸选择: {selected_id} (从{len(available_ids)}个可用ID中选择)"
                )
                return selected_id
            else:
                # 如果所有ID都用过了，重置并重新选择
                logger.warning(f"[鸣潮] 所有3cost声骸ID都已使用，重置选择池")
                _used_echo_ids.clear()
                selected_id = random.choice(echo_id_3_list)
                _used_echo_ids.add(selected_id)
                return selected_id
        else:
            return ECHO_ID_COST_THREE  # 使用默认ID

    # ---------- 1cost分配id逻辑 ----------
    def select_cost1_id():
        """选择cost1的ID（避免重复）"""
        if echo_id_1_list:
            # 过滤掉已使用的ID
            available_ids = [id for id in echo_id_1_list if id not in _used_echo_ids]
            if available_ids:
                selected_id = random.choice(available_ids)
                _used_echo_ids.add(selected_id)
                logger.debug(
                    f"[鸣潮] 1cost声骸选择: {selected_id} (从{len(available_ids)}个可用ID中选择)"
                )
                return selected_id
            else:
                # 如果所有ID都用过了，重置并重新选择
                logger.warning(f"[鸣潮] 所有1cost声骸ID都已使用，重置选择池")
                _used_echo_ids.clear()
                selected_id = random.choice(echo_id_1_list)
                _used_echo_ids.add(selected_id)
                return selected_id
        else:
            return ECHO_ID_COST_ONE  # 使用默认ID

    # 处理4cost属性
    if key in FOUR_COST_ATTRS:
        selected_id = select_cost4_id()
        _used_echo_ids.add(selected_id)  # 4cost也需要追踪
        return selected_id, 4

    # 处理3cost属性（正则匹配）
    if any(re.fullmatch(p, key) for p in THREE_COST_PATTERNS):
        return select_cost3_id(), 3

    # 处理基础属性
    if key in BASE_COST_ATTRS:
        try:
            thresholds = phantom_main_value_map[key]
            t1 = float(thresholds[0].strip("%"))
            t2 = float(thresholds[1].strip("%"))

            if value > t2:
                selected_id = select_cost4_id()
                _used_echo_ids.add(selected_id)
                return selected_id, 4
            elif value > t1:
                return select_cost3_id(), 3
            elif key_little == "生命":  # 声骸没拉满时
                return select_cost1_id(), 1
            else:
                return select_cost3_id(), 3
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"[鸣潮]阈值处理异常: {e}")
            return select_cost1_id(), 1  # 降级处理

    # 未知属性处理
    logger.warning(f"[鸣潮]未知主词条类型: {key}")
    return select_cost1_id(), 1  # 安全降级
