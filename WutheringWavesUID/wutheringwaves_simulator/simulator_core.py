"""模擬抽卡核心邏輯"""

import json
import random
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from gsuid_core.logger import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.database.models import WavesSimulator
from ..utils.resource.RESOURCE_PATH import MAIN_PATH

# 配置文件路徑
SIMULATOR_CONFIG_PATH = Path(__file__).parent / "config"


class SimulatorCore:
    """模擬抽卡核心類"""

    def __init__(self):
        self.role_config = self._load_config("role.json")
        self.weapon_config = self._load_config("weapon.json")

    def _load_config(self, filename: str) -> Dict:
        """載入配置文件"""
        config_file = SIMULATOR_CONFIG_PATH / filename
        if not config_file.exists():
            logger.warning(f"配置文件不存在: {config_file}")
            return {}

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception as e:
            logger.error(f"載入配置文件失敗: {e}")
            return {}

    async def get_user_state(self, user_id: str, bot_id: str, gacha_type: str) -> Dict:
        """獲取用戶抽卡狀態"""
        state = await WavesSimulator.get_user_state(user_id, bot_id, gacha_type)
        if not state:
            # 默認狀態
            return {
                "five_star_time": 0,
                "five_star_other": True,  # True = 上次沒歪, False = 上次歪了
                "four_star_time": 0,
                "four_star_other": True,
            }
        return state

    async def save_user_state(
        self, user_id: str, bot_id: str, gacha_type: str, state: Dict
    ):
        """保存用戶抽卡狀態"""
        await WavesSimulator.save_user_state(user_id, bot_id, gacha_type, state)

    def simulate_one(
        self, config: Dict, user_state: Dict, recent_four_stars: List[str] = None
    ) -> Tuple[Dict, Dict]:
        """
        模擬一次抽卡

        Returns:
            (抽卡結果, 新狀態)
            抽卡結果格式: {"name": "角色名", "star": 5}
        """
        five_star_time = user_state["five_star_time"]
        five_star_other = user_state["five_star_other"]
        four_star_time = user_state["four_star_time"]
        four_star_other = user_state["four_star_other"]

        five_star_config = config["five_star"]
        four_star_config = config["four_star"]
        three_star_config = config["three_star"]

        # ========== 五星抽卡邏輯 ==========
        # 階段 A: 前70抽（基礎概率）
        if five_star_time < 70:
            if random.random() < five_star_config["basic"]:
                # 出五星了
                result, new_five_star_other = self._get_five_star(
                    five_star_config, five_star_other
                )
                new_state = {
                    "five_star_time": 0,
                    "five_star_other": new_five_star_other,
                    "four_star_time": four_star_time + 1,
                    "four_star_other": four_star_other,
                }
                return result, new_state

        # 階段 B: 70抽後（概率遞增）
        if five_star_time >= 70:
            # 計算遞增概率
            increase_prob = (five_star_time - 69) * five_star_config[
                "increase"
            ] + five_star_config["basic"]

            if random.random() < increase_prob:
                # 出五星了
                result, new_five_star_other = self._get_five_star(
                    five_star_config, five_star_other
                )
                new_state = {
                    "five_star_time": 0,
                    "five_star_other": new_five_star_other,
                    "four_star_time": four_star_time + 1,
                    "four_star_other": four_star_other,
                }
                return result, new_state

        # 沒出五星，繼續判斷四星
        five_star_time += 1

        # ========== 四星抽卡邏輯 ==========
        # 階段 A: 前9抽（基礎概率）
        if four_star_time < 9:
            if random.random() < four_star_config["basic"]:
                # 出四星了
                result, new_four_star_other = self._get_four_star(
                    four_star_config, four_star_other, recent_four_stars or []
                )
                new_state = {
                    "five_star_time": five_star_time,
                    "five_star_other": five_star_other,
                    "four_star_time": 0,
                    "four_star_other": new_four_star_other,
                }
                return result, new_state

        # 階段 B: 第10抽（保底必出）
        if four_star_time >= 9:
            result, new_four_star_other = self._get_four_star(
                four_star_config, four_star_other, recent_four_stars or []
            )
            new_state = {
                "five_star_time": five_star_time,
                "five_star_other": five_star_other,
                "four_star_time": 0,
                "four_star_other": new_four_star_other,
            }
            return result, new_state

        # 沒出四星，出三星
        four_star_time += 1

        # ========== 三星抽卡 ==========
        three_star_pool = three_star_config["other_pool"]
        result = {
            "name": random.choice(three_star_pool)["name"],
            "star": 3,
        }

        new_state = {
            "five_star_time": five_star_time,
            "five_star_other": five_star_other,
            "four_star_time": four_star_time,
            "four_star_other": four_star_other,
        }
        return result, new_state

    def _get_five_star(
        self, five_star_config: Dict, five_star_other: bool
    ) -> Tuple[Dict, bool]:
        """獲取五星結果"""
        up_pool = five_star_config["up_pool"]
        other_pool = five_star_config["other_pool"]
        other_rate = five_star_config.get("other", 0.5)

        if five_star_other:
            # 上次沒歪，這次可能歪
            if random.random() < other_rate:
                # 歪了
                result = {
                    "name": random.choice(other_pool)["name"],
                    "star": 5,
                }
                return result, False  # 標記為歪了
            else:
                # 沒歪
                result = {
                    "name": random.choice(up_pool)["name"],
                    "star": 5,
                }
                return result, True  # 標記為沒歪
        else:
            # 上次歪了，這次必出UP（小保底）
            result = {
                "name": random.choice(up_pool)["name"],
                "star": 5,
            }
            return result, True  # 標記為沒歪

    def _get_four_star(
        self,
        four_star_config: Dict,
        four_star_other: bool,
        recent_four_stars: List[str] = None,
    ) -> Tuple[Dict, bool]:
        """獲取四星結果 - 完全隨機選擇，沒有保底機制"""
        up_pool = four_star_config["up_pool"]
        other_pool = four_star_config["other_pool"]
        recent_four_stars = recent_four_stars or []

        # 合併所有四星池（包含UP和常駐）
        all_four_star = up_pool + other_pool

        # 過濾掉最近出現過的四星（避免連續重複）
        available_four_star = [
            item for item in all_four_star if item["name"] not in recent_four_stars
        ]
        if not available_four_star:
            # 如果所有四星都出現過了，則重置列表，從全部中選
            available_four_star = all_four_star

        # 四星完全隨機，沒有大小保底機制
        result = {
            "name": random.choice(available_four_star)["name"],
            "star": 4,
        }
        # 檢查選中的是否為UP角色（僅用於狀態記錄，不影響下次抽卡）
        selected_is_up = any(item["name"] == result["name"] for item in up_pool)
        return result, selected_is_up


# 全局實例
simulator_core = SimulatorCore()


async def simulate_gacha(
    user_id: str, bot_id: str, gacha_type: str = "role"
) -> Optional[Dict]:
    """
    執行十連抽卡

    Args:
        user_id: 用戶ID
        bot_id: 機器人ID
        gacha_type: 抽卡類型 ("role" 或 "weapon")

    Returns:
        抽卡結果字典，包含 gacha_list, pool_name, times
    """
    try:
        # 獲取配置
        config = (
            simulator_core.role_config
            if gacha_type == "role"
            else simulator_core.weapon_config
        )

        if not config:
            logger.error(f"無法載入 {gacha_type} 配置")
            return None

        # 獲取用戶狀態
        user_state = await simulator_core.get_user_state(user_id, bot_id, gacha_type)

        # 執行十連
        gacha_list = []
        current_state = user_state.copy()
        # 記錄本輪已抽到的四星，避免重複（只在同一輪十連中）
        recent_four_stars = []

        for _ in range(10):
            result, current_state = simulator_core.simulate_one(
                config, current_state, recent_four_stars
            )
            gacha_list.append(result)

            # 如果是四星，記錄到本輪列表中
            if result["star"] == 4:
                recent_four_stars.append(result["name"])
                # 只保留最近3個四星（避免列表過長）
                if len(recent_four_stars) > 3:
                    recent_four_stars.pop(0)

            # 每抽一次都保存狀態（保持狀態同步）
            await simulator_core.save_user_state(
                user_id, bot_id, gacha_type, current_state
            )

        # 獲取池子名稱
        pool_name = config.get("pool_name", "未知池子")

        # 獲取當前五星計數
        times = current_state["five_star_time"]

        return {
            "gacha_list": gacha_list,
            "pool_name": pool_name,
            "times": times,
            "type": gacha_type,
        }

    except Exception as e:
        logger.error(f"模擬抽卡失敗: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return None
