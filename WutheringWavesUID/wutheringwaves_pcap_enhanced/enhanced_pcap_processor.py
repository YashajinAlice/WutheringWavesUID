"""
增強PCAP處理器 - 完整版本恢復高成功率
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiofiles
from gsuid_core.logger import logger


class EnhancedPcapProcessor:
    """增強PCAP處理器 - 完整功能版本"""

    def __init__(self):
        self.enhanced_data_path = Path("data/enhanced_players")

    async def process_pcap_file(
        self, file_data: bytes, uid: str, user_id: str
    ) -> Dict[str, Any]:
        """處理PCAP文件"""
        try:
            # 導入必要模組
            try:
                from .api.pcap_api import PcapApi
                from .standalone_pcap_analyzer import StandalonePcapAnalyzer
            except ImportError as e:
                logger.error(f"導入PCAP模組失敗: {e}")
                return {"error": "❌ PCAP分析模組未安裝"}

            # 初始化
            pcap_api = PcapApi()
            analyzer = StandalonePcapAnalyzer()

            # 1. 保存臨時文件
            temp_file = Path(f"temp_enhanced_{uid}.pcap")

            try:
                with open(temp_file, "wb") as f:
                    f.write(file_data)

                # 2. 使用PCAP API解析
                logger.info(f"🔧 開始解析PCAP文件 (增強系統): {uid}")
                pcap_data = await pcap_api.parse_pcap_file(str(temp_file))

                if not pcap_data:
                    return {"error": "❌ PCAP文件解析失敗"}

                # 3. 使用增強分析器處理
                logger.info(f"🎯 開始增強數據分析: {uid}")
                enhanced_data = await analyzer.convert_to_standard_format(
                    pcap_data, uid
                )

                if not enhanced_data:
                    return {"error": "❌ 數據轉換失敗"}

                # 4. 保存增強數據（獨立路徑）
                await self.save_enhanced_data(uid, enhanced_data)

                # 5. 生成統計信息
                stats = await self.generate_comprehensive_stats(enhanced_data)

                logger.info(f"✅ 增強PCAP處理完成: {uid}")
                return {
                    "success": True,
                    "role_count": stats["role_count"],
                    "phantom_success_rate": stats["phantom_success_rate"],
                    "property_success_rate": stats["property_success_rate"],
                    "weapon_success_rate": stats["weapon_success_rate"],
                    "skill_success_rate": stats["skill_success_rate"],
                    "chain_success_rate": stats["chain_success_rate"],
                }

            finally:
                # 清理臨時文件
                if temp_file.exists():
                    temp_file.unlink()

        except Exception as e:
            logger.exception(f"增強PCAP處理失敗: {uid} - {e}")
            return {"error": f"❌ 處理失敗: {str(e)}"}

    async def save_enhanced_data(self, uid: str, enhanced_data: List[Dict[str, Any]]):
        """保存增強數據"""
        data_dir = self.enhanced_data_path / uid
        data_dir.mkdir(parents=True, exist_ok=True)

        # 保存增強數據
        enhanced_file = data_dir / "enhancedData.json"
        async with aiofiles.open(enhanced_file, "w", encoding="utf-8") as f:
            await f.write(json.dumps(enhanced_data, ensure_ascii=False, indent=2))

        # 不再同步playerInfo.json到userData.json，保持原始數據

        # 保存分析摘要
        summary = {
            "uid": uid,
            "total_roles": len(enhanced_data),
            "analysis_time": datetime.now().isoformat(),
            "system": "enhanced_v2.0",
            "roles": [
                {
                    "roleId": role["role"]["roleId"],
                    "roleName": role["role"]["roleName"],
                    "level": role["role"]["level"],
                    "phantom_count": len(
                        role.get("phantomData", {}).get("equipPhantomList", [])
                    ),
                }
                for role in enhanced_data
            ],
        }

        summary_file = data_dir / "enhancedSummary.json"
        async with aiofiles.open(summary_file, "w", encoding="utf-8") as f:
            await f.write(json.dumps(summary, ensure_ascii=False, indent=2))

        logger.info(f"✅ 增強數據已保存: {enhanced_file}")

    async def sync_player_info_to_userdata(self, uid: str):
        """將playerInfo.json的信息直接複製到userData.json"""
        try:
            # 檢查playerInfo.json是否存在
            player_info_file = self.enhanced_data_path / uid / "playerInfo.json"
            if not player_info_file.exists():
                logger.info(f"[鸣潮] 未找到playerInfo.json，跳過同步: {uid}")
                return

            # 讀取playerInfo.json
            async with aiofiles.open(player_info_file, "r", encoding="utf-8") as f:
                player_info_content = await f.read()
                player_info = json.loads(player_info_content)

            # 直接複製數據到userData.json格式（因為結構已經一致）
            from ..wutheringwaves_analyzecard.user_info_utils import (
                save_user_info,
            )

            await save_user_info(
                uid,
                player_info.get("name", f"PCAP用戶_{uid[-4:]}"),
                player_info.get("level", 1),
                player_info.get("worldLevel", 1),
            )

            logger.info(
                f"✅ 玩家信息已覆蓋到userData.json: 名字={player_info.get('name')}, 等級={player_info.get('level')}, 世界等級={player_info.get('worldLevel')}"
            )

        except Exception as e:
            logger.exception(f"❌ 覆蓋玩家信息失敗: {uid} - {e}")

    async def generate_comprehensive_stats(
        self, enhanced_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成全面的統計信息"""
        role_count = len(enhanced_data)

        if role_count == 0:
            return {
                "role_count": 0,
                "phantom_success_rate": 0.0,
                "property_success_rate": 0.0,
                "weapon_success_rate": 0.0,
                "skill_success_rate": 0.0,
                "chain_success_rate": 0.0,
            }

        # 聲骸統計
        phantom_equipped = 0
        phantom_full_equipped = 0
        phantom_properties_complete = 0

        # 武器統計
        weapon_equipped = 0
        weapon_leveled = 0

        # 技能統計
        skill_leveled = 0

        # 命座統計
        chain_unlocked = 0

        for role in enhanced_data:
            # 聲骸統計
            phantom_data = role.get("phantomData", {})
            phantom_list = phantom_data.get("equipPhantomList", [])

            if phantom_data.get("cost", 0) > 0:
                phantom_equipped += 1

                if len(phantom_list) >= 5:
                    phantom_full_equipped += 1

                # 檢查屬性完整性
                properties_complete = True
                for phantom in phantom_list:
                    main_props = phantom.get("mainProps", [])
                    sub_props = phantom.get("subProps", [])

                    if not main_props or not sub_props:
                        properties_complete = False
                        break

                if properties_complete:
                    phantom_properties_complete += 1

            # 武器統計
            weapon_data = role.get("weaponData", {})
            if weapon_data.get("weapon", {}).get("weaponId"):
                weapon_equipped += 1

                if weapon_data.get("level", 1) > 1:
                    weapon_leveled += 1

            # 技能統計
            skill_list = role.get("skillList", [])
            if any(skill.get("level", 1) > 1 for skill in skill_list):
                skill_leveled += 1

            # 命座統計
            chain_list = role.get("chainList", [])
            if any(chain.get("unlocked", False) for chain in chain_list):
                chain_unlocked += 1

        return {
            "role_count": role_count,
            "phantom_success_rate": (phantom_equipped / role_count * 100),
            "property_success_rate": (phantom_properties_complete / role_count * 100),
            "weapon_success_rate": (weapon_equipped / role_count * 100),
            "skill_success_rate": (skill_leveled / role_count * 100),
            "chain_success_rate": (chain_unlocked / role_count * 100),
        }


async def get_enhanced_data(uid: str) -> Optional[List[Dict[str, Any]]]:
    """獲取增強數據"""
    enhanced_file = Path("data/enhanced_players") / uid / "enhancedData.json"

    if not enhanced_file.exists():
        return None

    try:
        async with aiofiles.open(enhanced_file, "r", encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content)
    except Exception as e:
        logger.exception(f"讀取增強數據失敗: {uid}")
        return None


async def get_enhanced_summary(uid: str) -> Optional[Dict[str, Any]]:
    """獲取增強數據摘要"""
    summary_file = Path("data/enhanced_players") / uid / "enhancedSummary.json"

    if not summary_file.exists():
        return None

    try:
        async with aiofiles.open(summary_file, "r", encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content)
    except Exception as e:
        logger.exception(f"讀取增強摘要失敗: {uid}")
        return None


async def process_enhanced_pcap_file(
    file_data: bytes, uid: str, user_id: str
) -> Dict[str, Any]:
    """處理增強PCAP文件的便利函數"""
    processor = EnhancedPcapProcessor()
    return await processor.process_pcap_file(file_data, uid, user_id)
