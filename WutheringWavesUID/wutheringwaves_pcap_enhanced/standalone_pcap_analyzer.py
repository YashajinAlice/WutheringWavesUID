#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增強 PCAP 分析器 - 適配 gsuid_core 架構
支援完整的鳴潮資源映射和數據轉換
"""

import copy
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from gsuid_core.logger import logger

# 繁簡轉換
try:
    import opencc

    converter = opencc.OpenCC("t2s")  # 繁體轉簡體
    HAS_OPENCC = True
except ImportError:
    HAS_OPENCC = False
    logger.warning("OpenCC 未安裝，將跳過繁簡轉換功能")


class StandalonePcapAnalyzer:
    """增強 PCAP 分析器 - 適配 gsuid_core"""

    def __init__(self):
        self.base_url = "https://pcap.wuthery.com/v1"
        self.timeout = 30

        # 設定資源路徑（適配 gsuid_core 結構）
        self.setup_resource_paths()

        # 載入映射數據
        self.load_mappings()

    def setup_resource_paths(self):
        """設定資源路徑以適配 gsuid_core 結構"""
        # 基礎路徑
        self.base_path = Path(__file__).parent

        # 映射資源路徑 - 全部使用 utils 中的資源
        self.char_mapping_path = (
            self.base_path.parent / "utils" / "map" / "CharId2Data.json"
        )
        self.char_detail_path = (
            self.base_path.parent / "utils" / "map" / "detail_json" / "char"
        )
        self.phantom_detail_path = (
            self.base_path.parent / "utils" / "map" / "detail_json" / "echo"
        )
        self.sonata_detail_path = (
            self.base_path.parent / "utils" / "map" / "detail_json" / "sonata"
        )
        self.weapon_detail_path = (
            self.base_path.parent / "utils" / "map" / "detail_json" / "weapon"
        )

        # 繁體資源路徑 - 使用 utils 中的資源
        self.local_zh_hant_path = self.base_path.parent / "utils" / "zh-Hant"

        logger.info(f"資源路徑設定完成: {self.base_path}")
        logger.info(f"繁體資源路徑: {self.local_zh_hant_path}")

    def convert_to_simplified(self, text: str) -> str:
        """繁體轉簡體"""
        if HAS_OPENCC and text:
            try:
                return converter.convert(text)
            except Exception:
                return text
        return text

    def convert_rarity_to_star_level(self, rarity_id: int) -> int:
        """將品質ID轉換為星級

        Args:
            rarity_id: 品質ID (R=1, SR=2/4, SSR=3/5)

        Returns:
            星級 (3, 4, 5)
        """
        rarity_mapping = {
            1: 3,  # R -> 三星
            2: 4,  # SR -> 四星
            3: 5,  # SSR -> 五星
            4: 4,  # SR -> 四星
            5: 5,  # SSR -> 五星
        }
        return rarity_mapping.get(rarity_id, 5)  # 默認五星

    def load_mappings(self):
        """載入所有資源映射數據"""
        try:
            # 1. 載入角色映射
            self.char_mapping = {}
            self.char_details = {}

            # 從 CharId2Data.json 載入基本映射
            if self.char_mapping_path.exists():
                with open(self.char_mapping_path, "r", encoding="utf-8") as f:
                    self.char_mapping = json.load(f)
                logger.info(f"載入角色基本映射: {len(self.char_mapping)} 個")

            # 從本地繁體資源載入詳細資料
            if self.char_detail_path.exists():
                for char_file in self.char_detail_path.glob("*.json"):
                    try:
                        with open(char_file, "r", encoding="utf-8") as f:
                            char_data = json.load(f)
                            # 使用文件名作為角色ID（去掉.json擴展名）
                            char_id = char_file.stem
                            if char_id.isdigit():
                                # 保存原始繁體資料
                                self.char_details[char_id] = char_data
                                # 同時更新基本映射，優先使用繁體資源
                                if char_id not in self.char_mapping:
                                    self.char_mapping[char_id] = {
                                        "name": char_data.get("name", f"角色_{char_id}")
                                    }
                    except Exception as e:
                        logger.warning(f"載入角色資料失敗: {char_file.name}: {e}")
                        continue

            logger.info(
                f"✅ 載入角色資料: {len(self.char_mapping)} 個基本映射, {len(self.char_details)} 個詳細資料"
            )

            # 2. 載入聲骸映射
            self.phantom_mapping = {}
            self.phantom_details = {}

            # 優先從繁體資源載入（新格式，直接使用PCAP ID）
            phantom_dir = self.local_zh_hant_path / "Phantom"
            if phantom_dir.exists():
                for phantom_file in phantom_dir.glob("*.json"):
                    try:
                        with open(phantom_file, "r", encoding="utf-8") as f:
                            phantom_data = json.load(f)
                            # 使用文件名作為聲骸ID（新格式直接對應PCAP ID）
                            phantom_id = int(phantom_file.stem)  # 去掉 .json 後綴
                            phantom_name = phantom_data.get(
                                "name", f"聲骸_{phantom_id}"
                            )
                            self.phantom_mapping[phantom_id] = phantom_name
                            self.phantom_details[phantom_id] = phantom_data
                    except Exception as e:
                        continue

            # 從舊資源載入（轉換後的ID格式）
            if self.phantom_detail_path.exists():
                for echo_file in self.phantom_detail_path.glob("*.json"):
                    try:
                        with open(echo_file, "r", encoding="utf-8") as f:
                            echo_data = json.load(f)
                            # 使用文件名作為聲骸ID
                            echo_id = int(echo_file.stem)  # 去掉 .json 後綴
                            echo_name = echo_data.get("name", f"聲骸_{echo_id}")
                            # 如果新資源中沒有，才使用舊資源
                            if echo_id not in self.phantom_mapping:
                                self.phantom_mapping[echo_id] = echo_name
                                self.phantom_details[echo_id] = echo_data
                    except Exception as e:
                        continue

            logger.info(f"✅ 載入聲骸資料: {len(self.phantom_mapping)} 個聲骸")

            # 3. 載入套裝映射
            self.sonata_mapping = {}
            self.sonata_details = {}

            # 從繁體資源載入套裝ID映射（優先使用）
            phantom_fetter_groups_file = (
                self.local_zh_hant_path
                / "LocalizationIndex"
                / "PhantomFetterGroups.json"
            )
            if phantom_fetter_groups_file.exists():
                try:
                    with open(phantom_fetter_groups_file, "r", encoding="utf-8") as f:
                        fetter_groups = json.load(f)
                        for group in fetter_groups:
                            group_id = group.get("id")
                            group_name = group.get(
                                "fetterGroupName", f"套裝_{group_id}"
                            )
                            if group_id:
                                self.sonata_mapping[group_id] = group_name
                                self.sonata_details[group_id] = group
                except Exception as e:
                    logger.warning(f"❌ 載入繁體套裝資源失敗: {e}")

            # 從舊資源載入（作為補充）
            if self.sonata_detail_path.exists():
                for sonata_file in self.sonata_detail_path.glob("*.json"):
                    try:
                        with open(sonata_file, "r", encoding="utf-8") as f:
                            sonata_data = json.load(f)
                            sonata_name = sonata_data.get("name")
                            if sonata_name:
                                # 使用名稱作為key（舊格式）
                                if sonata_name not in [
                                    v for v in self.sonata_mapping.values()
                                ]:
                                    self.sonata_details[sonata_name] = sonata_data
                    except Exception as e:
                        continue

            logger.info(f"✅ 載入套裝資料: {len(self.sonata_mapping)} 個ID映射套裝")

            # 4. 載入武器映射
            self.weapon_mapping = {}
            self.weapon_details = {}

            # 優先從繁體資源載入（新格式，包含完整品質信息）
            weapon_zh_hant_dir = self.local_zh_hant_path / "Weapon"
            if weapon_zh_hant_dir.exists():
                for weapon_file in weapon_zh_hant_dir.glob("*.json"):
                    try:
                        with open(weapon_file, "r", encoding="utf-8") as f:
                            weapon_data = json.load(f)
                            weapon_id = int(weapon_file.stem)  # 去掉 .json 後綴
                            weapon_name = weapon_data.get("name", f"武器_{weapon_id}")
                            self.weapon_mapping[weapon_id] = weapon_name
                            self.weapon_details[weapon_id] = weapon_data
                    except Exception as e:
                        logger.warning(f"載入武器資料失敗: {weapon_file.name}: {e}")
                        continue

            # 如果繁體資源不夠，再從舊路徑補充
            if self.weapon_detail_path.exists():
                for weapon_file in self.weapon_detail_path.glob("*.json"):
                    try:
                        weapon_id = int(weapon_file.stem)
                        # 只有當繁體資源中沒有時才載入
                        if weapon_id not in self.weapon_details:
                            with open(weapon_file, "r", encoding="utf-8") as f:
                                weapon_data = json.load(f)
                                weapon_name = weapon_data.get(
                                    "name", f"武器_{weapon_id}"
                                )
                                self.weapon_mapping[weapon_id] = weapon_name
                                self.weapon_details[weapon_id] = weapon_data
                    except Exception as e:
                        continue

            logger.info(f"✅ 載入武器資料: {len(self.weapon_mapping)} 個武器")

        except Exception as e:
            logger.error(f"❌ 載入映射數據失敗: {e}")
            self.char_mapping = {}
            self.char_details = {}
            self.phantom_mapping = {}
            self.phantom_details = {}
            self.sonata_mapping = {}
            self.sonata_details = {}
            self.weapon_mapping = {}
            self.weapon_details = {}

    async def parse_pcap_file(self, file_path: str) -> Dict[str, Any]:
        """解析 pcap 檔案"""
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"❌ PCAP 文件不存在: {file_path}")
                return {}

            with open(file_path, "rb") as f:
                file_data = f.read()

            logger.info(
                f"📁 讀取 PCAP 檔案: {file_path_obj.name}, 大小: {len(file_data)} bytes"
            )

            data = aiohttp.FormData()
            data.add_field(
                "file",
                file_data,
                filename=file_path_obj.name,
                content_type="application/vnd.tcpdump.pcap",
            )

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:
                logger.info(f"🌐 正在上傳到 {self.base_url}/parse...")
                async with session.post(
                    f"{self.base_url}/parse", data=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info("✅ PCAP 解析成功")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"❌ PCAP 解析失敗: {response.status} - {error_text}"
                        )
                        return {}

        except Exception as e:
            logger.error(f"❌ PCAP 解析異常: {e}")
            return {}

    def extract_uid_from_data(self, pcap_data: Dict[str, Any]) -> str:
        """從數據中提取 UID"""
        try:
            if "data" in pcap_data and "BasicInfoNotify" in pcap_data["data"]:
                basic_info = pcap_data["data"]["BasicInfoNotify"]
                uid = basic_info.get("id", "")
                return str(uid) if uid else ""
        except Exception as e:
            logger.error(f"❌ 提取 UID 失敗: {e}")
        return ""

    def get_breach_level(self, level: int) -> int:
        """根據等級計算突破等級"""
        if level <= 20:
            return 0
        elif level <= 40:
            return 1
        elif level <= 50:
            return 2
        elif level <= 60:
            return 3
        elif level <= 70:
            return 4
        elif level <= 80:
            return 5
        elif level <= 90:
            return 6
        else:
            return 0

    def get_char_name(self, char_id: int) -> str:
        """根據角色ID獲取角色名稱"""
        char_id_str = str(char_id)

        # 優先從詳細資料獲取（繁體轉簡體）
        if char_id_str in self.char_details:
            name = self.char_details[char_id_str].get("name", f"角色_{char_id}")
            return self.convert_to_simplified(name)

        # 其次從基本映射獲取
        if char_id_str in self.char_mapping:
            char_data = self.char_mapping[char_id_str]
            if isinstance(char_data, dict):
                name = char_data.get("name", f"角色_{char_id}")
                return self.convert_to_simplified(name)
            else:
                return self.convert_to_simplified(str(char_data))

        return f"角色_{char_id}"

    def get_phantom_name(self, phantom_id: int) -> str:
        """根據聲骸ID獲取聲骸名稱"""
        # 先嘗試直接使用原始ID（新資源格式）
        if phantom_id in self.phantom_details:
            phantom_name = self.phantom_details[phantom_id].get(
                "name", f"聲骸_{phantom_id}"
            )
            return self.convert_to_simplified(phantom_name)

        # PCAP中的聲骸ID需要轉換：去掉最後一位數字
        # 例如：60000525 -> 6000052
        converted_id = phantom_id // 10

        # 優先從詳細資料獲取（使用轉換後的ID）
        if converted_id in self.phantom_details:
            phantom_name = self.phantom_details[converted_id].get(
                "name", f"聲骸_{phantom_id}"
            )
            # 轉換為簡體
            return self.convert_to_simplified(phantom_name)

        # 其次從基本映射獲取（使用轉換後的ID）
        if converted_id in self.phantom_mapping:
            phantom_name = self.phantom_mapping[converted_id]
            # 轉換為簡體
            return self.convert_to_simplified(phantom_name)

        return f"聲骸_{phantom_id}"

    def get_char_attribute(self, char_id: int) -> Dict[str, Any]:
        """獲取角色屬性信息（元素、武器類型等）"""
        char_id_str = str(char_id)
        if char_id_str in self.char_details:
            char_data = self.char_details[char_id_str]

            # 從角色數據文件獲取屬性ID和武器類型ID
            attribute_id = char_data.get("attributeId", 0)
            weapon_type_id = char_data.get("weaponTypeId", 0)
            star_level = char_data.get("starLevel", 5)

            # 映射屬性ID到屬性名稱
            attribute_name_map = {
                1: "冷凝",  # 冰屬性
                2: "热熔",  # 火屬性
                3: "导电",  # 雷屬性
                4: "气动",  # 風屬性
                5: "衍射",  # 光屬性
                6: "湮灭",  # 暗屬性
            }

            # 映射武器類型ID到武器類型名稱（與圖片文件名匹配）
            weapon_type_name_map = {
                1: "迅刀",  # 刀
                2: "长刃",  # 劍
                3: "佩枪",  # 槍
                4: "长刃",  # 重劍（暫時使用長刃圖片）
                5: "佩枪",  # 手槍
            }

            attribute_name = attribute_name_map.get(attribute_id, "")
            weapon_type_name = weapon_type_name_map.get(weapon_type_id, "")

            return {
                "attributeId": attribute_id,
                "attributeName": attribute_name,
                "weaponTypeId": weapon_type_id,
                "weaponTypeName": weapon_type_name,
                "starLevel": star_level,
                "acronym": char_data.get("name", "")[
                    :2
                ],  # 使用角色名稱前兩個字作為簡稱
                "roleIconUrl": "",  # 可以從資源路徑構建
                "rolePicUrl": "",  # 可以從資源路徑構建
            }
        return {
            "attributeId": 0,
            "attributeName": "",
            "weaponTypeId": 0,
            "weaponTypeName": "",
            "starLevel": 5,
            "acronym": "",
            "roleIconUrl": "",
            "rolePicUrl": "",
        }

    def get_weapon_name(self, weapon_id: int) -> str:
        """獲取武器名稱"""
        if weapon_id in self.weapon_details:
            return self.weapon_details[weapon_id].get("name", f"武器_{weapon_id}")
        return self.weapon_mapping.get(weapon_id, f"武器_{weapon_id}")

    def get_sonata_name_by_fetter_id(self, fetter_group_id: int) -> str:
        """根據羈絆組ID獲取套裝名稱"""
        # 優先從繁體資源映射獲取
        if fetter_group_id in self.sonata_mapping:
            sonata_name = self.sonata_mapping[fetter_group_id]
            # 轉換為簡體
            return self.convert_to_simplified(sonata_name)

        # 後備的硬編碼映射（以防萬一）
        fetter_mapping = {
            1: "凝夜白霜",
            2: "熔山裂谷",
            3: "彻空冥雷",
            4: "不绝余音",
            5: "沉日劫明",
            6: "轻云出月",
            7: "隐世回光",
            8: "愿戴荣光之旅",
            9: "无惧浪涛之勇",
            10: "啸谷长风",
            11: "凌冽决断之心",
        }
        return fetter_mapping.get(fetter_group_id, f"套装_{fetter_group_id}")

    def format_property_value(self, prop_id: int, value: Any) -> str:
        """格式化屬性值"""
        # 百分比屬性ID列表
        percent_props = {
            # 基礎百分比屬性
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            # 特殊生命百分比
            2018,
            # 4000系列百分比
            4003,
            # 5000系列百分比屬性
            5001,
            5002,
            5003,
            5004,
            5005,
            5006,
            5007,
            5008,
            5009,
            5010,
            5011,
            5012,
            5013,
            5014,
            5015,
            5016,
            5017,
            5018,
            5019,
        }

        try:
            numeric_value = float(value)
            if prop_id in percent_props:
                if numeric_value > 100:
                    # 原始值大于100，除以100
                    result_value = numeric_value / 100.0
                    # 如果是整数，不显示小数；否则显示一位小数
                    if result_value == int(result_value):
                        return f"{int(result_value)}%"
                    else:
                        return f"{result_value:.1f}%"
                else:
                    # 原始值小于等于100，直接使用
                    if numeric_value == int(numeric_value):
                        return f"{int(numeric_value)}%"
                    else:
                        return f"{numeric_value:.1f}%"
            else:
                return str(int(numeric_value))
        except (ValueError, TypeError):
            return str(value)

    def get_property_name(self, prop_id: int) -> str:
        """獲取屬性名稱"""
        prop_mapping = {
            # 基礎屬性 (1-13)
            1: "生命",  # 生命 (固定值)
            2: "攻击",  # 攻击 (固定值)
            3: "防御",  # 防御 (固定值)
            4: "生命",  # 生命 (百分比)
            5: "攻击",  # 攻击 (百分比)
            6: "防御",  # 防御 (百分比)
            7: "共鸣技能伤害加成",  # 共鸣技能伤害加成 (百分比)
            8: "普攻伤害加成",  # 普攻伤害加成 (百分比)
            9: "重击伤害加成",  # 重击伤害加成 (百分比)
            10: "共鸣解放伤害加成",  # 共鸣解放伤害加成 (百分比)
            11: "暴击",  # 暴击 (百分比)
            12: "暴击伤害",  # 暴击伤害 (百分比)
            13: "共鸣效率",  # 共鸣效率 (百分比)
            # 特殊生命屬性
            2018: "生命",  # 生命 (百分比)
            20002: "生命",  # 生命 (固定值)
            # 4000系列
            4003: "攻击",  # 攻击 (百分比)
            40001: "攻击",  # 攻击 (固定值)
            # 5000系列 - 主要屬性
            5001: "暴击",  # 暴击 (百分比)
            5002: "暴击伤害",  # 暴击伤害 (百分比)
            5003: "攻击",  # 攻击 (百分比)
            5004: "生命",  # 生命 (百分比)
            5005: "防御",  # 防御 (百分比)
            5006: "治疗效果加成",  # 治疗效果加成 (百分比)
            5007: "冷凝伤害加成",  # 冷凝伤害加成 (百分比)
            5008: "热熔伤害加成",  # 热熔伤害加成 (百分比)
            5009: "导电伤害加成",  # 导电伤害加成 (百分比)
            5010: "气动伤害加成",  # 气动伤害加成 (百分比)
            5011: "衍射伤害加成",  # 衍射伤害加成 (百分比)
            5012: "湮灭伤害加成",  # 湮灭伤害加成 (百分比)
            5013: "攻击",  # 攻击 (百分比)
            5014: "生命",  # 生命 (百分比)
            5015: "防御",  # 防御 (百分比)
            5016: "共鸣效率",  # 共鸣效率 (百分比)
            5017: "攻击",  # 攻击 (百分比)
            5018: "生命",  # 生命 (百分比)
            5019: "防御",  # 防御 (百分比)
            # 50000系列 - 固定值屬性
            50001: "攻击",  # 攻击 (固定值)
            50002: "生命",  # 生命 (固定值)
            50003: "攻击",  # 攻击 (固定值)
        }
        return prop_mapping.get(prop_id, f"属性_{prop_id}")

    async def convert_to_standard_format(
        self, pcap_data: Dict[str, Any], uid: str
    ) -> List[Dict[str, Any]]:
        """轉換為標準格式"""
        try:
            logger.info("🔧 開始轉換為標準格式...")

            data = pcap_data.get("data", {})

            # 提取角色數據
            role_list = data.get("PbGetRoleListNotify", {}).get("role_list", [])
            weapon_list = data.get("WeaponItemResponse", {}).get("weapon_item_list", [])
            phantom_data = data.get("PhantomItemResponse", {})
            phantom_list = phantom_data.get("phantom_item_list", [])
            equip_info = phantom_data.get("equip_info", [])

            logger.info(f"📊 原始數據統計:")
            logger.info(f"  • 角色: {len(role_list)} 個")
            logger.info(f"  • 武器: {len(weapon_list)} 個")
            logger.info(f"  • 聲骸: {len(phantom_list)} 個")

            # 建立武器映射 (role_id -> weapon_data)
            weapon_mapping = {}
            for weapon in weapon_list:
                role_id = weapon.get("role_id", 0)
                if role_id > 0:
                    weapon_mapping[role_id] = weapon

            # 建立聲骸映射 (role_id -> [phantom_data])
            phantom_mapping = {}
            for equip in equip_info:
                role_id = equip.get("role_id", 0)
                phantom_incr_ids = equip.get("phantom_item_incr_id", [])

                if role_id > 0 and phantom_incr_ids:
                    role_phantoms = []
                    for incr_id in phantom_incr_ids[:5]:  # 最多5個聲骸
                        if incr_id > 0:
                            for phantom in phantom_list:
                                if phantom.get("incr_id") == incr_id:
                                    role_phantoms.append(phantom)
                                    break
                    phantom_mapping[role_id] = role_phantoms

            # 轉換角色數據
            role_detail_list = []
            for role in role_list:
                role_id = role.get("role_id", 0)
                if role_id == 0:
                    continue

                level = role.get("level", 1)
                breach = role.get("breakthrough", 0)
                resonant_chain = role.get("resonant_chain_group_index", 0)

                # 構建角色基本信息
                role_name = self.get_char_name(role_id)
                char_attributes = self.get_char_attribute(role_id)

                role_detail = {
                    "level": level,
                    "role": {
                        "roleId": role_id,
                        "roleName": role_name,
                        "level": level,
                        "breach": breach,
                        "chainUnlockNum": resonant_chain,
                        "isMainRole": False,
                        "attributeId": char_attributes["attributeId"],
                        "attributeName": char_attributes["attributeName"],
                        "weaponTypeId": char_attributes["weaponTypeId"],
                        "weaponTypeName": char_attributes["weaponTypeName"],
                        "starLevel": char_attributes["starLevel"],
                        "acronym": char_attributes["acronym"],
                        "roleIconUrl": char_attributes["roleIconUrl"],
                        "rolePicUrl": char_attributes["rolePicUrl"],
                    },
                    "chainList": self.build_chain_list(resonant_chain, role_id),
                    "skillList": self.build_skill_list(role),
                    "skillTreeList": self.build_skill_tree_list(role),
                    "weaponData": self.build_weapon_data(role_id, weapon_mapping),
                    "phantomData": self.build_phantom_data(role_id, phantom_mapping),
                }

                role_detail_list.append(role_detail)
                logger.info(f"✅ 處理角色: {role_name} (ID: {role_id})")

            logger.info(f"🎉 轉換完成，共 {len(role_detail_list)} 個角色")
            return role_detail_list

        except Exception as e:
            logger.error(f"❌ 轉換為標準格式失敗: {e}")
            import traceback

            traceback.print_exc()
            return []

    def build_chain_list(
        self, chain_count: int, role_id: int = 0
    ) -> List[Dict[str, Any]]:
        """構建共鳴鏈列表，動態根據角色ID獲取繁體資源"""
        chain_list = []
        char_id_str = str(role_id)

        # 從繁體中文資源獲取共鳴鏈信息
        if char_id_str in self.char_details:
            char_data = self.char_details[char_id_str]
            chains_data = char_data.get("chains", {})  # 繁體資源中的共鳴鏈數據

            if chains_data:
                # 獲取所有共鳴鏈ID並排序（可能不是1-6，比如炽霞是7-12）
                chain_ids = sorted([int(k) for k in chains_data.keys() if k.isdigit()])

                # 取前6個共鳴鏈（按順序）
                for i, chain_id in enumerate(chain_ids[:6], 1):
                    chain_key = str(chain_id)
                    chain_info = chains_data[chain_key]

                    # 從繁體資源獲取名稱和描述
                    chain_name = chain_info.get("name", f"共鳴鏈{i}")
                    chain_desc = chain_info.get("desc", f"共鳴鏈{i}的描述")

                    # 轉換為簡體
                    chain_name = self.convert_to_simplified(chain_name)
                    chain_desc = self.convert_to_simplified(chain_desc)

                    # 構建共鳴鏈圖片的URL
                    chain_icon_url = f"/d/GameData/UIResources/Common/Image/ChainIcon/T_ChainIcon_{role_id}_{i:02d}.png"

                    chain_list.append(
                        {
                            "name": chain_name,
                            "order": i,  # 使用順序編號（1-6），不是原始ID
                            "description": chain_desc,
                            "iconUrl": chain_icon_url,
                            "unlocked": i <= chain_count,
                        }
                    )

                # 如果找到的共鳴鏈少於6個，補充默認的
                while len(chain_list) < 6:
                    i = len(chain_list) + 1
                    chain_icon_url = f"/d/GameData/UIResources/Common/Image/ChainIcon/T_ChainIcon_{role_id}_{i:02d}.png"
                    chain_list.append(
                        {
                            "name": f"共鸣链{i}",
                            "order": i,
                            "description": f"共鸣链{i}的描述",
                            "iconUrl": chain_icon_url,
                            "unlocked": i <= chain_count,
                        }
                    )
            else:
                # 沒有共鳴鏈數據，使用默認
                for i in range(1, 7):
                    chain_icon_url = f"/d/GameData/UIResources/Common/Image/ChainIcon/T_ChainIcon_{role_id}_{i:02d}.png"
                    chain_list.append(
                        {
                            "name": f"共鸣链{i}",
                            "order": i,
                            "description": f"共鸣链{i}的描述",
                            "iconUrl": chain_icon_url,
                            "unlocked": i <= chain_count,
                        }
                    )
        else:
            # 默認共鳴鏈結構
            for i in range(1, 7):  # 6個共鳴鏈
                chain_icon_url = f"/d/GameData/UIResources/Common/Image/ChainIcon/T_ChainIcon_{role_id}_{i:02d}.png"
                chain_list.append(
                    {
                        "name": f"共鸣链{i}",
                        "order": i,
                        "description": f"共鸣链{i}的描述",
                        "iconUrl": chain_icon_url,
                        "unlocked": i <= chain_count,
                    }
                )

        return chain_list

    def build_skill_list(self, role_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """構建技能列表，動態根據PCAP中的技能ID獲取繁體資源"""
        role_id = role_data.get("role_id", 0)
        char_id_str = str(role_id)
        pcap_skills = role_data.get(
            "skills", []
        )  # PCAP中的技能數據: [{'key': 1000101, 'value': 1}, ...]
        skill_list = []

        # 從繁體中文資源獲取技能信息
        if char_id_str in self.char_details:
            char_data = self.char_details[char_id_str]
            skill_data = char_data.get(
                "skillTree", {}
            )  # 繁體資源中的技能數據在skillTree字段

            # 主要技能類型映射（12367規律）
            main_skill_types = {
                1: "常态攻击",  # xxxx01
                2: "共鸣技能",  # xxxx02
                3: "共鸣解放",  # xxxx03
                6: "变奏技能",  # xxxx06
                7: "共鸣回路",  # xxxx07
            }

            # 主要技能的後綴（12367規律）
            main_skill_suffixes = {1, 2, 3, 6, 7}

            # 根據PCAP中實際存在的技能ID來處理（只處理主要技能，排除固有技能）
            main_skill_count = 0
            for pcap_skill in pcap_skills:
                if main_skill_count >= 5:  # 原始系統只處理前5個主要技能
                    break

                skill_key = str(pcap_skill.get("key", ""))
                skill_level = pcap_skill.get("value", 1)

                # 檢查是否為主要技能（12367規律）
                skill_suffix = int(skill_key[-2:]) if skill_key[-2:].isdigit() else 1
                if skill_suffix not in main_skill_suffixes:
                    continue  # 跳過非主要技能（固有技能等）

                # 在繁體資源中查找對應的技能
                # 使用技能後綴（如"1", "2", "3"）來查找，因為技能數據結構中使用的是字符串格式的數字
                skill_suffix_str = str(skill_suffix)
                if skill_suffix_str in skill_data:
                    skill_info = skill_data[skill_suffix_str]
                    skill_params = skill_info.get("skill", {})

                    # 從繁體資源獲取技能名稱和描述
                    skill_name = skill_params.get("name", "")
                    skill_desc = skill_params.get(
                        "desc", ""
                    )  # detail_json中使用desc字段

                    # 轉換為簡體
                    skill_name = self.convert_to_simplified(skill_name)
                    skill_desc = self.convert_to_simplified(skill_desc)

                    # 根據技能ID末尾確定技能類型
                    skill_type = main_skill_types.get(skill_suffix, "技能")
                    skill_type = self.convert_to_simplified(skill_type)

                    # 構建技能圖片的URL
                    icon_url = f"/d/GameData/UIResources/Common/Image/SkillIcon/T_SkillIcon_{role_id}_{skill_suffix:02d}.png"

                    skill_list.append(
                        {
                            "level": skill_level,
                            "skill": {
                                "id": skill_suffix,  # 保留ID用於排序，但這是內部使用
                                "name": skill_name,
                                "type": skill_type,
                                "description": skill_desc,
                                "iconUrl": icon_url,
                            },
                        }
                    )
                    main_skill_count += 1
                else:
                    # 如果在繁體資源中找不到，使用默認名稱
                    skill_type = main_skill_types.get(skill_suffix, "技能")

                    # 構建技能圖片的URL
                    icon_url = f"/d/GameData/UIResources/Common/Image/SkillIcon/T_SkillIcon_{role_id}_{skill_suffix:02d}.png"

                    skill_list.append(
                        {
                            "level": skill_level,
                            "skill": {
                                "id": skill_suffix,
                                "name": skill_type,
                                "type": skill_type,
                                "description": f"{skill_type}的描述",
                                "iconUrl": icon_url,
                            },
                        }
                    )
                    main_skill_count += 1

            # 按技能ID排序
            skill_list.sort(key=lambda x: x["skill"]["id"])

            if skill_list:
                return skill_list

        # 默認技能結構（如果沒有找到繁體資源，使用12367規律）
        default_skill_types = {
            1: "常态攻击",
            2: "共鸣技能",
            3: "共鸣解放",
            6: "变奏技能",
            7: "共鸣回路",
        }
        main_skill_suffixes = {1, 2, 3, 6, 7}

        main_skill_count = 0
        for pcap_skill in pcap_skills:
            if main_skill_count >= 5:  # 原始系統只處理前5個主要技能
                break

            skill_key = pcap_skill.get("key", 0)
            skill_level = pcap_skill.get("value", 1)

            if skill_key > 0:
                skill_suffix = skill_key % 100

                # 只處理主要技能（12367規律）
                if skill_suffix not in main_skill_suffixes:
                    continue

                skill_type = default_skill_types.get(skill_suffix, "技能")

                # 構建技能圖片的URL
                icon_url = f"/d/GameData/UIResources/Common/Image/SkillIcon/T_SkillIcon_{role_id}_{skill_suffix:02d}.png"

                skill_list.append(
                    {
                        "level": skill_level,
                        "skill": {
                            "id": skill_suffix,
                            "name": skill_type,
                            "type": skill_type,
                            "description": f"{skill_type}的描述",
                            "iconUrl": icon_url,
                        },
                    }
                )
                main_skill_count += 1

        return skill_list

    def build_skill_tree_list(self, role_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """構建技能樹列表，從PCAP中的skill_tree數據獲取"""
        role_id = role_data.get("role_id", 0)
        char_id_str = str(role_id)
        pcap_skill_tree = role_data.get("skill_tree", [])  # PCAP中的技能樹數據
        skill_tree_list = []

        # 從繁體中文資源獲取技能樹信息
        if char_id_str in self.char_details:
            char_data = self.char_details[char_id_str]
            skill_tree_data = char_data.get("skillTree", {})  # 繁體資源中的技能樹數據

            # 處理PCAP中的技能樹數據
            for pcap_node in pcap_skill_tree:
                node_id = pcap_node.get("key", 0)
                node_level = pcap_node.get("value", 0)
                node_id_str = str(node_id)

                # 在繁體資源中查找對應的技能樹節點
                if node_id_str in skill_tree_data:
                    node_info = skill_tree_data[node_id_str]
                    node_params = node_info.get("skill", {})

                    # 從繁體資源獲取技能樹節點名稱和描述
                    node_name = node_params.get("name", f"技能樹節點{node_id}")
                    node_desc = node_params.get("desc", f"技能樹節點{node_id}的描述")

                    # 轉換為簡體
                    node_name = self.convert_to_simplified(node_name)
                    node_desc = self.convert_to_simplified(node_desc)

                    # 構建技能樹節點圖片的URL
                    icon_url = f"/d/GameData/UIResources/Common/Image/SkillTreeIcon/T_SkillTreeIcon_{role_id}_{node_id:02d}.png"

                    skill_tree_list.append(
                        {
                            "id": node_id,
                            "level": node_level,
                            "name": node_name,
                            "description": node_desc,
                            "iconUrl": icon_url,
                            "unlocked": node_level > 0,
                        }
                    )
                else:
                    # 如果在繁體資源中找不到，使用默認名稱
                    icon_url = f"/d/GameData/UIResources/Common/Image/SkillTreeIcon/T_SkillTreeIcon_{role_id}_{node_id:02d}.png"

                    skill_tree_list.append(
                        {
                            "id": node_id,
                            "level": node_level,
                            "name": f"技能樹節點{node_id}",
                            "description": f"技能樹節點{node_id}的描述",
                            "iconUrl": icon_url,
                            "unlocked": node_level > 0,
                        }
                    )

            # 按節點ID排序
            skill_tree_list.sort(key=lambda x: x["id"])

        return skill_tree_list

    def build_weapon_data(
        self, role_id: int, weapon_mapping: Dict[int, Dict]
    ) -> Dict[str, Any]:
        """構建武器數據"""
        weapon = weapon_mapping.get(role_id, {})

        weapon_id = weapon.get("id", 0)
        weapon_level = weapon.get("weapon_level", 1)
        weapon_breach = weapon.get("weapon_breach", 0)
        weapon_reson = weapon.get("weapon_reson_level", 1)

        # 獲取武器詳細信息
        weapon_name = self.get_weapon_name(weapon_id) if weapon_id > 0 else "無武器"
        weapon_star_level = 5
        weapon_type = 0
        weapon_effect_name = ""

        if weapon_id > 0 and weapon_id in self.weapon_details:
            weapon_detail = self.weapon_details[weapon_id]
            rarity_id = weapon_detail.get("rarity", {}).get("id", 5)
            weapon_star_level = self.convert_rarity_to_star_level(rarity_id)
            weapon_type = weapon_detail.get("weaponType", {}).get("id", 0)
            weapon_effect_name = weapon_detail.get("passiveSkill", {}).get("name", "")

        return {
            "breach": weapon_breach,
            "level": weapon_level,
            "resonLevel": weapon_reson,
            "weapon": {
                "weaponId": weapon_id,
                "weaponName": weapon_name,
                "weaponType": weapon_type,
                "weaponStarLevel": weapon_star_level,
                "weaponIcon": "",
                "weaponEffectName": weapon_effect_name,
            },
        }

    def build_phantom_data(
        self, role_id: int, phantom_mapping: Dict[int, List]
    ) -> Dict[str, Any]:
        """構建聲骸數據"""
        phantoms = phantom_mapping.get(role_id, [])

        if not phantoms:
            return {"cost": 0, "equipPhantomList": []}

        equip_phantom_list = []
        total_cost = 0

        for phantom in phantoms:
            original_phantom_id = phantom.get("id", 0)  # PCAP中的原始ID
            phantom_level = phantom.get("phantom_level", 1)
            fetter_group_id = phantom.get("fetter_group_id", 0)

            # 從聲骸資源獲取詳細信息（使用原始ID）
            rarity = 5  # 默認品質
            cost = 4  # 默認cost
            monster_id = original_phantom_id  # 默認使用原始ID作為monsterId
            phantom_name = f"聲骸_{original_phantom_id}"
            phantom_icon_url = ""

            if original_phantom_id in self.phantom_details:
                phantom_detail = self.phantom_details[original_phantom_id]
                rarity_id = phantom_detail.get("rarity", {}).get("id", 5)
                rarity = self.convert_rarity_to_star_level(rarity_id)
                cost = phantom_detail.get("cost", {}).get("cost", 4)
                monster_id = phantom_detail.get("monsterId", original_phantom_id)
                phantom_name = phantom_detail.get("name", phantom_name)

                # 獲取圖標URL
                icon_info = phantom_detail.get("icon", {})
                if isinstance(icon_info, dict):
                    phantom_icon_url = icon_info.get(
                        "iconSmall",
                        icon_info.get("iconMiddle", icon_info.get("icon", "")),
                    )

                logger.info(
                    f"聲骸詳情: ID={original_phantom_id}, monsterId={monster_id}, name={phantom_name}, icon={phantom_icon_url}"
                )
            else:
                # 如果沒有詳細資源，使用簡化邏輯
                rarity_id = original_phantom_id % 10
                rarity = self.convert_rarity_to_star_level(
                    rarity_id if rarity_id in [1, 2, 3, 4, 5] else 5
                )
                cost = 4 if rarity >= 5 else (3 if rarity >= 4 else 1)
                monster_id = original_phantom_id  # 設置monster_id為原始ID
                logger.warning(f"未找到聲骸資源: {original_phantom_id}")
            total_cost += cost

            # 處理主屬性
            main_props = []
            for prop in phantom.get("phantom_main_prop", []):
                prop_id = prop.get("phantom_prop_id", 0)
                value = prop.get("value", 0)
                main_props.append(
                    {
                        "id": prop_id,
                        "attributeName": self.get_property_name(prop_id),
                        "attributeValue": self.format_property_value(prop_id, value),
                        "iconUrl": None,
                    }
                )

            # 處理副屬性
            sub_props = []
            for prop in phantom.get("phantom_sub_prop", []):
                prop_id = prop.get("phantom_prop_id", 0)
                value = prop.get("value", 0)
                sub_props.append(
                    {
                        "id": prop_id,
                        "attributeName": self.get_property_name(prop_id),
                        "attributeValue": self.format_property_value(prop_id, value),
                        "iconUrl": None,
                    }
                )

            # phantom_name已經在上面獲取，使用轉換為簡體的版本
            phantom_name = self.convert_to_simplified(phantom_name)

            equip_phantom_list.append(
                {
                    "cost": cost,
                    "level": phantom_level,
                    "quality": rarity,
                    "fetterDetail": {
                        "groupId": fetter_group_id,
                        "name": self.get_sonata_name_by_fetter_id(fetter_group_id),
                        "num": len(phantoms),
                        "firstDescription": "",
                        "secondDescription": "",
                        "tripleDescription": "",
                        "iconUrl": "",
                    },
                    "mainProps": main_props,
                    "subProps": sub_props,
                    "phantomProp": {
                        "phantomId": monster_id,  # 使用monsterId作為phantomId
                        "phantomPropId": monster_id,
                        "name": phantom_name,
                        "cost": cost,
                        "quality": rarity,
                        "iconUrl": phantom_icon_url,  # 使用獲取的圖標URL
                        "skillDescription": "",
                    },
                }
            )

        return {"cost": total_cost, "equipPhantomList": equip_phantom_list}

    async def save_in_standard_format(
        self, uid: str, role_detail_list: List[Dict[str, Any]]
    ):
        """以標準格式保存數據"""
        try:
            # 創建數據目錄
            data_dir = Path("data/players") / uid
            data_dir.mkdir(parents=True, exist_ok=True)

            # 保存為 rawData.json（標準格式）
            rawdata_file = data_dir / "rawData.json"
            with open(rawdata_file, "w", encoding="utf-8") as f:
                json.dump(role_detail_list, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ 數據已保存為標準格式: {rawdata_file}")

            # 保存分析摘要
            summary = {
                "uid": uid,
                "total_roles": len(role_detail_list),
                "analysis_time": datetime.now().isoformat(),
                "roles": [
                    {
                        "roleId": role["role"]["roleId"],
                        "roleName": role["role"]["roleName"],
                        "level": role["level"],
                        "phantom_count": len(
                            role.get("phantomData", {}).get("equipPhantomList", [])
                        ),
                    }
                    for role in role_detail_list
                ],
            }

            summary_file = data_dir / "analysis_summary.json"
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ 分析摘要已保存: {summary_file}")
            return True

        except Exception as e:
            logger.error(f"❌ 保存數據失敗: {e}")
            return False

    async def verify_standard_format(self, role_detail_list: List[Dict[str, Any]]):
        """驗證標準格式"""
        try:
            if not role_detail_list:
                logger.error("❌ 角色數據為空")
                return False

            logger.info("🔍 驗證標準格式...")

            # 檢查必要字段
            first_role = role_detail_list[0]
            required_fields = [
                "role",
                "level",
                "chainList",
                "skillList",
                "weaponData",
                "phantomData",
            ]

            missing_fields = [
                field for field in required_fields if field not in first_role
            ]
            if missing_fields:
                logger.error(f"❌ 缺少必要字段: {missing_fields}")
                return False

            logger.info("✅ 頂層字段檢查通過")

            # 檢查 role 字段
            role = first_role["role"]
            role_fields = ["roleId", "roleName", "level", "breach", "chainUnlockNum"]
            role_missing = [field for field in role_fields if field not in role]
            if role_missing:
                logger.error(f"❌ role 字段缺少: {role_missing}")
                return False

            logger.info("✅ role 字段檢查通過")

            # 統計信息
            total_roles = len(role_detail_list)
            total_phantoms = sum(
                len(role.get("phantomData", {}).get("equipPhantomList", []))
                for role in role_detail_list
            )

            logger.info(f"📊 數據統計:")
            logger.info(f"  • 角色數量: {total_roles}")
            logger.info(f"  • 聲骸數量: {total_phantoms}")
            logger.info(
                f"  • 示例角色: {first_role['role']['roleName']} (ID: {first_role['role']['roleId']})"
            )

            logger.info("✅ 標準格式驗證完全通過")
            return True

        except Exception as e:
            logger.error(f"❌ 格式驗證失敗: {e}")
            return False
