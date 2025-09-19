"""
增強PCAP數據合併器 - 智能比較和更新原始數據
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

import aiofiles
from gsuid_core.logger import logger

from ..utils.resource.RESOURCE_PATH import PLAYER_PATH


class EnhancedDataMerger:
    """增強數據合併器"""

    def __init__(self):
        self.player_path = PLAYER_PATH

    async def compare_and_merge_data(
        self, uid: str, enhanced_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        比較增強PCAP數據和原始數據，智能合併更新

        Args:
            uid: 用戶ID
            enhanced_data: 增強PCAP數據

        Returns:
            合併結果統計
        """
        try:
            # 1. 讀取現有原始數據
            existing_data = await self._load_existing_rawdata(uid)

            # 2. 比較數據差異
            comparison_result = await self._compare_data_changes(
                existing_data, enhanced_data
            )

            # 3. 智能合併數據
            merged_data = await self._merge_data_intelligently(
                existing_data, enhanced_data, comparison_result
            )

            # 4. 保存合併後的數據
            await self._save_merged_data(uid, merged_data)

            # 5. 生成合併報告
            merge_report = await self._generate_merge_report(
                uid, comparison_result, merged_data
            )

            logger.info(f"✅ 增強數據合併完成: {uid}")
            return merge_report

        except Exception as e:
            logger.exception(f"增強數據合併失敗: {uid} - {e}")
            return {"error": f"合併失敗: {str(e)}"}

    async def _load_existing_rawdata(self, uid: str) -> List[Dict[str, Any]]:
        """讀取現有的原始數據"""
        rawdata_path = self.player_path / uid / "rawData.json"

        if not rawdata_path.exists():
            logger.info(f"沒有找到現有數據，將創建新數據: {uid}")
            return []

        try:
            async with aiofiles.open(rawdata_path, "r", encoding="utf-8") as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.warning(f"讀取現有數據失敗: {uid} - {e}")
            return []

    async def _compare_data_changes(
        self, existing_data: List[Dict[str, Any]], enhanced_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """比較數據變化"""
        comparison = {
            "new_roles": [],
            "updated_roles": [],
            "unchanged_roles": [],
            "level_changes": [],
            "weapon_changes": [],
            "phantom_changes": [],
            "skill_changes": [],
        }

        # 創建現有數據的索引
        existing_roles = {role["role"]["roleId"]: role for role in existing_data}

        for enhanced_role in enhanced_data:
            role_id = enhanced_role["role"]["roleId"]

            if role_id not in existing_roles:
                # 新角色
                comparison["new_roles"].append(role_id)
                continue

            existing_role = existing_roles[role_id]
            changes = await self._compare_single_role(existing_role, enhanced_role)

            if changes["has_changes"]:
                comparison["updated_roles"].append(
                    {
                        "roleId": role_id,
                        "roleName": enhanced_role["role"]["roleName"],
                        "changes": changes,
                    }
                )

                # 記錄具體變化
                if changes["level_changed"]:
                    comparison["level_changes"].append(
                        {
                            "roleId": role_id,
                            "roleName": enhanced_role["role"]["roleName"],
                            "old_level": existing_role["role"]["level"],
                            "new_level": enhanced_role["role"]["level"],
                        }
                    )

                if changes["weapon_changed"]:
                    comparison["weapon_changes"].append(
                        {
                            "roleId": role_id,
                            "roleName": enhanced_role["role"]["roleName"],
                            "old_weapon": existing_role["weaponData"]["weapon"][
                                "weaponName"
                            ],
                            "new_weapon": enhanced_role["weaponData"]["weapon"][
                                "weaponName"
                            ],
                        }
                    )

                if changes["phantom_changed"]:
                    comparison["phantom_changes"].append(
                        {
                            "roleId": role_id,
                            "roleName": enhanced_role["role"]["roleName"],
                            "phantom_diff": changes["phantom_diff"],
                        }
                    )

                if changes["skill_changed"]:
                    comparison["skill_changes"].append(
                        {
                            "roleId": role_id,
                            "roleName": enhanced_role["role"]["roleName"],
                            "skill_diff": changes["skill_diff"],
                        }
                    )
            else:
                comparison["unchanged_roles"].append(role_id)

        return comparison

    async def _compare_single_role(
        self, existing_role: Dict[str, Any], enhanced_role: Dict[str, Any]
    ) -> Dict[str, Any]:
        """比較單個角色的變化"""
        changes = {
            "has_changes": False,
            "level_changed": False,
            "weapon_changed": False,
            "phantom_changed": False,
            "skill_changed": False,
            "chain_changed": False,
            "phantom_diff": {},
            "skill_diff": {},
            "chain_diff": {},
        }

        # 比較等級
        if existing_role["role"]["level"] != enhanced_role["role"]["level"]:
            changes["level_changed"] = True
            changes["has_changes"] = True

        # 比較突破等級
        if existing_role["role"]["breach"] != enhanced_role["role"]["breach"]:
            changes["level_changed"] = True
            changes["has_changes"] = True

        # 比較武器
        existing_weapon = existing_role["weaponData"]["weapon"]["weaponId"]
        enhanced_weapon = enhanced_role["weaponData"]["weapon"]["weaponId"]
        if existing_weapon != enhanced_weapon:
            changes["weapon_changed"] = True
            changes["has_changes"] = True

        # 比較武器等級和共鳴
        if (
            existing_role["weaponData"]["level"] != enhanced_role["weaponData"]["level"]
            or existing_role["weaponData"]["resonLevel"]
            != enhanced_role["weaponData"]["resonLevel"]
        ):
            changes["weapon_changed"] = True
            changes["has_changes"] = True

        # 比較聲骸
        phantom_diff = await self._compare_phantoms(
            existing_role.get("phantomData", {}), enhanced_role.get("phantomData", {})
        )
        if phantom_diff["has_changes"]:
            changes["phantom_changed"] = True
            changes["phantom_diff"] = phantom_diff
            changes["has_changes"] = True

        # 比較技能等級
        existing_skills = existing_role.get("skillList", [])
        enhanced_skills = enhanced_role.get("skillList", [])

        # 確保列表不為 None
        if existing_skills is None:
            existing_skills = []
        if enhanced_skills is None:
            enhanced_skills = []

        skill_diff = await self._compare_skills(existing_skills, enhanced_skills)
        if skill_diff["has_changes"]:
            changes["skill_changed"] = True
            changes["skill_diff"] = skill_diff
            changes["has_changes"] = True

        # 比較命座
        existing_chains = existing_role.get("chainList", [])
        enhanced_chains = enhanced_role.get("chainList", [])

        # 確保列表不為 None
        if existing_chains is None:
            existing_chains = []
        if enhanced_chains is None:
            enhanced_chains = []

        chain_diff = await self._compare_chains(existing_chains, enhanced_chains)
        if chain_diff["has_changes"]:
            changes["chain_changed"] = True
            changes["chain_diff"] = chain_diff
            changes["has_changes"] = True

        return changes

    async def _compare_phantoms(
        self, existing_phantoms: Dict[str, Any], enhanced_phantoms: Dict[str, Any]
    ) -> Dict[str, Any]:
        """比較聲骸變化"""
        phantom_diff = {
            "has_changes": False,
            "cost_changed": False,
            "phantom_changes": [],
        }

        existing_cost = existing_phantoms.get("cost", 0)
        enhanced_cost = enhanced_phantoms.get("cost", 0)

        if existing_cost != enhanced_cost:
            phantom_diff["cost_changed"] = True
            phantom_diff["has_changes"] = True

        # 比較具體聲骸
        existing_list = existing_phantoms.get("equipPhantomList", [])
        enhanced_list = enhanced_phantoms.get("equipPhantomList", [])

        # 確保列表不為 None
        if existing_list is None:
            existing_list = []
        if enhanced_list is None:
            enhanced_list = []

        # 創建位置索引
        existing_by_pos = {p.get("position", i): p for i, p in enumerate(existing_list)}
        enhanced_by_pos = {p.get("position", i): p for i, p in enumerate(enhanced_list)}

        all_positions = set(existing_by_pos.keys()) | set(enhanced_by_pos.keys())

        for pos in all_positions:
            existing_phantom = existing_by_pos.get(pos)
            enhanced_phantom = enhanced_by_pos.get(pos)

            if not existing_phantom and enhanced_phantom:
                # 新增聲骸
                phantom_diff["phantom_changes"].append(
                    {
                        "position": pos,
                        "type": "added",
                        "phantom": enhanced_phantom["phantomProp"]["name"],
                    }
                )
                phantom_diff["has_changes"] = True
            elif existing_phantom and not enhanced_phantom:
                # 移除聲骸
                phantom_diff["phantom_changes"].append(
                    {
                        "position": pos,
                        "type": "removed",
                        "phantom": existing_phantom["phantomProp"]["name"],
                    }
                )
                phantom_diff["has_changes"] = True
            elif existing_phantom and enhanced_phantom:
                # 比較聲骸變化
                existing_phantom_id = existing_phantom["phantomProp"].get(
                    "phantomId", existing_phantom["phantomProp"].get("phantomPropId", 0)
                )
                enhanced_phantom_id = enhanced_phantom["phantomProp"].get(
                    "phantomId", enhanced_phantom["phantomProp"].get("phantomPropId", 0)
                )
                if existing_phantom_id != enhanced_phantom_id:
                    phantom_diff["phantom_changes"].append(
                        {
                            "position": pos,
                            "type": "changed",
                            "old_phantom": existing_phantom["phantomProp"]["name"],
                            "new_phantom": enhanced_phantom["phantomProp"]["name"],
                        }
                    )
                    phantom_diff["has_changes"] = True
                elif existing_phantom["level"] != enhanced_phantom["level"]:
                    phantom_diff["phantom_changes"].append(
                        {
                            "position": pos,
                            "type": "level_changed",
                            "phantom": enhanced_phantom["phantomProp"]["name"],
                            "old_level": existing_phantom["level"],
                            "new_level": enhanced_phantom["level"],
                        }
                    )
                    phantom_diff["has_changes"] = True

        return phantom_diff

    async def _compare_skills(
        self,
        existing_skills: List[Dict[str, Any]],
        enhanced_skills: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """比較技能變化"""
        skill_diff = {"has_changes": False, "skill_changes": []}

        # 創建技能ID索引
        existing_by_id = {s["skill"]["id"]: s for s in existing_skills}
        enhanced_by_id = {s["skill"]["id"]: s for s in enhanced_skills}

        for skill_id, enhanced_skill in enhanced_by_id.items():
            existing_skill = existing_by_id.get(skill_id)

            if not existing_skill:
                # 新技能
                skill_diff["skill_changes"].append(
                    {
                        "skill_id": skill_id,
                        "skill_name": enhanced_skill["skill"]["name"],
                        "type": "added",
                        "level": enhanced_skill["level"],
                    }
                )
                skill_diff["has_changes"] = True
            elif existing_skill["level"] != enhanced_skill["level"]:
                # 技能等級變化
                skill_diff["skill_changes"].append(
                    {
                        "skill_id": skill_id,
                        "skill_name": enhanced_skill["skill"]["name"],
                        "type": "level_changed",
                        "old_level": existing_skill["level"],
                        "new_level": enhanced_skill["level"],
                    }
                )
                skill_diff["has_changes"] = True

        return skill_diff

    async def _compare_chains(
        self,
        existing_chains: List[Dict[str, Any]],
        enhanced_chains: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """比較命座變化"""
        chain_diff = {"has_changes": False, "chain_changes": []}

        # 創建命座順序索引
        existing_by_order = {c["order"]: c for c in existing_chains}
        enhanced_by_order = {c["order"]: c for c in enhanced_chains}

        for order, enhanced_chain in enhanced_by_order.items():
            existing_chain = existing_by_order.get(order)

            if not existing_chain:
                continue

            # 檢查解鎖狀態變化
            if existing_chain["unlocked"] != enhanced_chain["unlocked"]:
                chain_diff["chain_changes"].append(
                    {
                        "order": order,
                        "name": enhanced_chain["name"],
                        "type": "unlock_changed",
                        "old_unlocked": existing_chain["unlocked"],
                        "new_unlocked": enhanced_chain["unlocked"],
                    }
                )
                chain_diff["has_changes"] = True

        return chain_diff

    async def _merge_data_intelligently(
        self,
        existing_data: List[Dict[str, Any]],
        enhanced_data: List[Dict[str, Any]],
        comparison_result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """智能合併數據"""
        # 創建現有數據索引
        existing_roles = {role["role"]["roleId"]: role for role in existing_data}

        merged_data = []

        for enhanced_role in enhanced_data:
            role_id = enhanced_role["role"]["roleId"]

            if role_id in existing_roles:
                # 合併現有角色數據
                existing_role = existing_roles[role_id]
                merged_role = await self._merge_single_role(
                    existing_role, enhanced_role
                )
                merged_data.append(merged_role)
            else:
                # 新角色直接添加
                merged_data.append(enhanced_role)

        # 添加增強數據中沒有但原始數據中存在的角色
        enhanced_role_ids = {role["role"]["roleId"] for role in enhanced_data}
        for existing_role in existing_data:
            role_id = existing_role["role"]["roleId"]
            if role_id not in enhanced_role_ids:
                merged_data.append(existing_role)

        return merged_data

    async def _merge_single_role(
        self, existing_role: Dict[str, Any], enhanced_role: Dict[str, Any]
    ) -> Dict[str, Any]:
        """合併單個角色數據"""
        # 使用增強數據作為基礎
        merged_role = enhanced_role.copy()

        # 保留一些原始數據中的特殊字段（如果需要）
        # 這裡可以根據需要添加特殊邏輯

        return merged_role

    async def _save_merged_data(self, uid: str, merged_data: List[Dict[str, Any]]):
        """保存合併後的數據"""
        data_dir = self.player_path / uid
        data_dir.mkdir(parents=True, exist_ok=True)

        rawdata_path = data_dir / "rawData.json"

        try:
            async with aiofiles.open(rawdata_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(merged_data, ensure_ascii=False, indent=2))

            logger.info(f"✅ 合併數據已保存: {rawdata_path}")

            # 不再覆蓋userData.json，保持原始數據

        except Exception as e:
            logger.exception(f"保存合併數據失敗: {uid} - {e}")
            raise

    async def _generate_merge_report(
        self,
        uid: str,
        comparison_result: Dict[str, Any],
        merged_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """生成合併報告"""
        report = {
            "success": True,
            "uid": uid,
            "merge_time": datetime.now().isoformat(),
            "total_roles": len(merged_data),
            "new_roles": len(comparison_result["new_roles"]),
            "updated_roles": len(comparison_result["updated_roles"]),
            "unchanged_roles": len(comparison_result["unchanged_roles"]),
            "level_changes": len(comparison_result["level_changes"]),
            "weapon_changes": len(comparison_result["weapon_changes"]),
            "phantom_changes": len(comparison_result["phantom_changes"]),
            "skill_changes": len(comparison_result["skill_changes"]),
            "details": comparison_result,
        }

        return report

    async def sync_player_info_to_userdata(self, uid: str):
        """將playerInfo.json的信息直接複製到userData.json"""
        try:
            # 檢查playerInfo.json是否存在
            player_info_file = Path("data/enhanced_players") / uid / "playerInfo.json"
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


# 便利函數
async def merge_enhanced_data_to_rawdata(
    uid: str, enhanced_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """合併增強PCAP數據到原始數據的便利函數"""
    merger = EnhancedDataMerger()
    return await merger.compare_and_merge_data(uid, enhanced_data)
