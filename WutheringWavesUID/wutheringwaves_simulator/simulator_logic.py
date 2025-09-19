import json
import random
from pathlib import Path
from typing import Dict, List, Optional

from gsuid_core.logger import logger


class GachaSimulator:
    def __init__(self):
        self.config_path = Path(__file__).parent / "config"
        self.load_config()
        # 使用內存存儲用戶數據
        self.user_data_cache = {}

    def load_config(self):
        """加載抽卡配置"""
        try:
            with open(self.config_path / "role.json", "r", encoding="utf-8") as f:
                self.role_config = json.load(f)
            with open(self.config_path / "weapon.json", "r", encoding="utf-8") as f:
                self.weapon_config = json.load(f)
        except Exception as e:
            logger.error(f"加載抽卡配置失敗: {e}")
            self.role_config = self.get_default_role_config()
            self.weapon_config = self.get_default_weapon_config()

    def get_default_role_config(self) -> Dict:
        """默認角色抽卡配置"""
        return {
            "pool_name": "角色精准调谐",
            "five_star": {
                "basic": 0.006,  # 0.6%
                "increase": 0.06,  # 6%
                "other": 0.5,  # 50%歪
                "up_pool": [{"name": "尤諾", "id": 1410}, {"name": "今汐", "id": 1409}],
                "other_pool": [
                    {"name": "渊武", "id": 1608},
                    {"name": "弗洛洛", "id": 1607},
                    {"name": "卡卡罗", "id": 1606},
                ],
            },
            "four_star": {
                "basic": 0.051,  # 5.1%
                "other": 0.5,  # 50%歪
                "up_pool": [{"name": "白芷", "id": 1305}, {"name": "炽霞", "id": 1203}],
                "other_pool": [
                    {"name": "安可", "id": 1105},
                    {"name": "吟霖", "id": 1104},
                ],
            },
            "three_star": {
                "other_pool": [
                    {"name": "三星武器1", "id": 21010011},
                    {"name": "三星武器2", "id": 21010012},
                ]
            },
        }

    def get_default_weapon_config(self) -> Dict:
        """默認武器抽卡配置"""
        return {
            "pool_name": "武器精准调谐",
            "five_star": {
                "basic": 0.008,  # 0.8%
                "increase": 0.08,  # 8%
                "other": 0.25,  # 25%歪
                "up_pool": [
                    {"name": "长离专武", "id": 21020011},
                    {"name": "今汐专武", "id": 21020012},
                ],
                "other_pool": [
                    {"name": "通用五星武器1", "id": 21020013},
                    {"name": "通用五星武器2", "id": 21020014},
                ],
            },
            "four_star": {
                "basic": 0.066,  # 6.6%
                "other": 0.75,  # 75%歪
                "up_pool": [
                    {"name": "四星武器1", "id": 21010011},
                    {"name": "四星武器2", "id": 21010012},
                ],
                "other_pool": [
                    {"name": "通用四星武器1", "id": 21010013},
                    {"name": "通用四星武器2", "id": 21010014},
                ],
            },
            "three_star": {
                "other_pool": [
                    {"name": "三星武器1", "id": 21010021},
                    {"name": "三星武器2", "id": 21010022},
                ]
            },
        }

    def get_user_data(self, user_id: str, gacha_type: str) -> Dict:
        """獲取用戶抽卡數據"""
        key = f"{gacha_type}:{user_id}"

        if key in self.user_data_cache:
            return self.user_data_cache[key]
        else:
            default_data = {
                "five_star_time": 0,
                "five_star_other": True,
                "four_star_time": 0,
                "four_star_other": True,
            }
            self.user_data_cache[key] = default_data
            return default_data

    def save_user_data(self, user_id: str, gacha_type: str, data: Dict):
        """保存用戶抽卡數據"""
        key = f"{gacha_type}:{user_id}"
        self.user_data_cache[key] = data

    async def simulate_gacha(
        self, user_id: str, gacha_type: str = "role"
    ) -> List[Dict]:
        """模擬十連抽卡"""
        config = self.role_config if gacha_type == "role" else self.weapon_config
        user_data = self.get_user_data(user_id, gacha_type)

        gacha_results = []

        for i in range(10):  # 十連抽
            result = await self._single_gacha(config, user_data)
            gacha_results.append(result)
            self.save_user_data(user_id, gacha_type, user_data)

        return gacha_results

    async def simulate_single_gacha(
        self, user_id: str, gacha_type: str = "role"
    ) -> List[Dict]:
        """模擬單抽"""
        config = self.role_config if gacha_type == "role" else self.weapon_config
        user_data = self.get_user_data(user_id, gacha_type)

        result = await self._single_gacha(config, user_data)
        self.save_user_data(user_id, gacha_type, user_data)

        return [result]

    async def _single_gacha(self, config: Dict, user_data: Dict) -> Dict:
        """單次抽卡"""
        five_star_time = user_data["five_star_time"]
        five_star_other = user_data["five_star_other"]
        four_star_time = user_data["four_star_time"]
        four_star_other = user_data["four_star_other"]

        # 五星抽卡邏輯
        if five_star_time < 70 and random.random() < config["five_star"]["basic"]:
            return await self._get_five_star(config, user_data, five_star_other)

        if five_star_time >= 70:
            prob = (five_star_time - 69) * config["five_star"]["increase"] + config[
                "five_star"
            ]["basic"]
            if random.random() < prob:
                return await self._get_five_star(config, user_data, five_star_other)

        user_data["five_star_time"] += 1

        # 四星抽卡邏輯
        if four_star_time < 9 and random.random() < config["four_star"]["basic"]:
            return await self._get_four_star(config, user_data, four_star_other)

        if four_star_time >= 9:
            return await self._get_four_star(config, user_data, four_star_other)

        user_data["four_star_time"] += 1

        # 三星保底
        return await self._get_three_star(config)

    async def _get_five_star(
        self, config: Dict, user_data: Dict, five_star_other: bool
    ) -> Dict:
        """獲取五星"""
        if five_star_other:
            if random.random() < config["five_star"]["other"]:
                # 歪了
                item = random.choice(config["five_star"]["other_pool"])
                user_data["five_star_other"] = False
                user_data["five_star_time"] = 0
                return {
                    "name": item["name"],
                    "id": item["id"],
                    "star": 5,
                    "is_up": False,
                }
            else:
                # 沒歪
                item = random.choice(config["five_star"]["up_pool"])
                user_data["five_star_other"] = True
                user_data["five_star_time"] = 0
                return {
                    "name": item["name"],
                    "id": item["id"],
                    "star": 5,
                    "is_up": True,
                }
        else:
            # 大保底
            item = random.choice(config["five_star"]["up_pool"])
            user_data["five_star_other"] = True
            user_data["five_star_time"] = 0
            return {"name": item["name"], "id": item["id"], "star": 5, "is_up": True}

    async def _get_four_star(
        self, config: Dict, user_data: Dict, four_star_other: bool
    ) -> Dict:
        """獲取四星"""
        if four_star_other:
            if random.random() < config["four_star"]["other"]:
                # 歪了
                item = random.choice(config["four_star"]["other_pool"])
                user_data["four_star_other"] = False
                user_data["four_star_time"] = 0
                return {
                    "name": item["name"],
                    "id": item["id"],
                    "star": 4,
                    "is_up": False,
                }
            else:
                # 沒歪
                item = random.choice(config["four_star"]["up_pool"])
                user_data["four_star_other"] = True
                user_data["four_star_time"] = 0
                return {
                    "name": item["name"],
                    "id": item["id"],
                    "star": 4,
                    "is_up": True,
                }
        else:
            # 小保底
            item = random.choice(config["four_star"]["up_pool"])
            user_data["four_star_other"] = True
            user_data["four_star_time"] = 0
            return {"name": item["name"], "id": item["id"], "star": 4, "is_up": True}

    async def _get_three_star(self, config: Dict) -> Dict:
        """獲取三星"""
        item = random.choice(config["three_star"]["other_pool"])
        return {"name": item["name"], "id": item["id"], "star": 3, "is_up": False}
