"""
國際服排行數據上傳模組
在用戶分析時同步計算期望傷害並上傳到國際服排行API
"""

import asyncio
from typing import Dict, Optional

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger

from .calc import WuWaCalc
from .calculate import get_calc_map
from .damage.damage import DamageAttribute
from .damage.abstract import DamageRankRegister
from ..wutheringwaves_config import WutheringWavesConfig
from .name_convert import char_id_to_char_name, weapon_name_to_weapon_id


class InternationalRankUploader:
    """國際服排行上傳器"""

    def __init__(self):
        self.upload_enabled = True
        self.batch_size = 5
        self.upload_queue = []

    def _get_api_version(self) -> str:
        """獲取API版本號"""
        try:
            from .api_version import get_api_version

            return get_api_version()
        except ImportError:
            return "1.1.0"  # 默認版本

    async def upload_analysis_result(
        self, bot: Bot, ev: Event, result_dict: Dict, waves_data: list
    ) -> bool:
        """
        上傳分析結果到國際服排行

        Args:
            bot: Bot實例
            ev: Event實例
            result_dict: OCR分析結果
            waves_data: 處理後的鳴潮數據

        Returns:
            bool: 是否上傳成功
        """
        try:
            # 1. 檢查是否啟用國際服上傳
            if not self._is_upload_enabled():
                logger.info("[國際服排行] 上傳功能未啟用")
                return False

            # 2. 提取必要數據
            rank_data = await self._extract_rank_data(result_dict, waves_data, ev)
            if not rank_data:
                logger.warning("[國際服排行] 無法提取排行數據")
                return False

            # 調試信息：檢查提取的數據
            logger.info(f"[國際服排行] 提取的數據: {list(rank_data.keys())}")

            # 3. 檢查武器精煉度是否符合上傳條件
            if not await self._check_weapon_resonance_level(rank_data, waves_data):
                logger.info(
                    f"[國際服排行] 武器精煉度不符合上傳條件，跳過上傳: {rank_data.get('char_name', '未知角色')}"
                )
                return False

            # 4. 計算期望傷害和期望傷害名稱
            expected_damage, expected_damage_name = (
                await self._calculate_expected_damage_with_name(rank_data, waves_data)
            )

            # 如果期望傷害計算失敗（為0），跳過上傳
            if expected_damage == 0:
                logger.warning(
                    f"[國際服排行] 期望傷害計算失敗，跳過上傳: {rank_data.get('char_name', '未知角色')}"
                )
                return False

            rank_data["expected_damage"] = expected_damage
            rank_data["expected_damage_name"] = expected_damage_name

            # 4. 計算聲骸評分
            phantom_score = await self._calculate_phantom_score(rank_data, waves_data)
            rank_data["phantom_score"] = phantom_score

            # 5. 計算套裝屬性
            sonata_name = await self._calculate_sonata_name(rank_data, waves_data)
            rank_data["sonata_name"] = sonata_name

            # 6. 上傳到API
            success = await self._upload_to_api(rank_data)

            if success:
                logger.info(f"[國際服排行] 成功上傳 {rank_data['char_name']} 的數據")
            else:
                logger.error("[國際服排行] 上傳失敗")

            return success

        except Exception as e:
            logger.exception(f"[國際服排行] 上傳過程出錯: {e}")
            return False

    def _is_upload_enabled(self) -> bool:
        """檢查是否啟用國際服上傳"""
        try:
            # 簡化檢查：直接嘗試連接，如果失敗則禁用上傳
            import socket

            def check_port_open(host, port, timeout=3):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    result = sock.connect_ex((host, port))
                    sock.close()
                    return result == 0
                except:
                    return False

            # 檢查端口 3456 是否開放
            if check_port_open("localhost", 3456):
                return True
            else:
                logger.info("[國際服排行] API服務器未運行，跳過上傳")
                return False

        except Exception as e:
            logger.warning(f"[國際服排行] 無法檢查API服務器狀態: {e}")
            return False  # 如果無法檢查，則禁用上傳

    async def _extract_rank_data(
        self, result_dict: Dict, waves_data: list, ev: Event
    ) -> Optional[Dict]:
        """從分析結果中提取排行所需數據"""
        try:
            # 提取用戶信息
            user_info = result_dict.get("用户信息", {})
            char_info = result_dict.get("角色信息", {})
            weapon_info = result_dict.get("武器信息", {})

            # 提取聲骸套裝信息
            sonata_name = self._extract_sonata_name(result_dict.get("装备数据", []))

            # 獲取Discord用戶ID
            discord_user_id = ""
            if ev.bot_id == "discord":
                discord_user_id = str(ev.user_id)

            # 獲取玩家名稱，如果分析數據中沒有，則從已保存的用戶信息中獲取
            username = user_info.get("玩家名称", "")
            logger.info(f"[國際服排行] 分析數據中的玩家名稱: '{username}'")

            if not username:
                try:
                    from ..wutheringwaves_analyzecard.user_info_utils import (
                        get_user_detail_info,
                    )

                    uid = user_info.get("UID", "")
                    logger.info(f"[國際服排行] 嘗試從用戶數據獲取名稱，UID: {uid}")
                    if uid:
                        user_detail = await get_user_detail_info(uid)
                        username = user_detail.name if user_detail else ""
                        logger.info(f"[國際服排行] 從用戶數據獲取的名稱: '{username}'")
                except Exception as e:
                    logger.warning(f"[國際服排行] 獲取用戶名稱失敗: {e}")
                    username = ""

            logger.info(f"[國際服排行] 最終玩家名稱: '{username}'")

            rank_data = {
                "waves_id": user_info.get("UID", ""),
                "username": username,
                "discord_user_id": discord_user_id,  # 從Event獲取Discord用戶ID
                "char_id": int(char_info.get("角色ID", 0)),
                "char_name": char_id_to_char_name(char_info.get("角色ID", 0)),
                "level": int(char_info.get("等级", 0)),
                "chain": int(char_info.get("共鸣链", 0)),
                "weapon_id": weapon_name_to_weapon_id(weapon_info.get("武器名", "")),
                "weapon_level": int(weapon_info.get("等级", 0)),
                "weapon_resonance_level": self._extract_weapon_resonance_level(
                    weapon_info, waves_data, char_info
                ),
                "sonata_name": sonata_name,
                "server_region": "international",
                "version": self._get_api_version(),  # 可以從配置獲取
            }

            return rank_data

        except Exception as e:
            logger.error(f"[國際服排行] 提取數據失敗: {e}")
            return None

    def _extract_weapon_resonance_level(
        self, weapon_info: dict, waves_data: list, char_info: dict = None
    ) -> int:
        """從武器信息和本地數據中提取武器精煉度 - 只使用舊數據"""
        try:
            # 只從本地數據中獲取武器精煉度（忽略新分析的精煉度）
            char_id = (
                char_info.get("角色ID", 0)
                if char_info
                else weapon_info.get("角色ID", 0)
            )
            logger.info(
                f"[國際服排行] 尋找角色ID: {char_id}, 本地數據數量: {len(waves_data) if waves_data else 0}"
            )

            if char_id and waves_data:
                for i, char_data in enumerate(waves_data):
                    # 從role字段中獲取角色ID
                    role_data = char_data.get("role", {})
                    char_data_id = role_data.get("roleId") if role_data else None
                    logger.info(
                        f"[國際服排行] 本地數據[{i}] 角色ID (roleId): {char_data_id}"
                    )

                    logger.info(
                        f"[國際服排行] 比較角色ID: {char_data_id} == {char_id} ? {char_data_id == char_id}"
                    )
                    # 確保類型一致進行比較
                    if str(char_data_id) == str(char_id):
                        weapon_data = char_data.get("weaponData", {})
                        local_resonance_level = weapon_data.get("resonLevel", 1)
                        logger.info(
                            f"[國際服排行] 從本地數據獲取武器精煉度: {local_resonance_level}"
                        )
                        return local_resonance_level
                    else:
                        logger.info(f"[國際服排行] 角色ID不匹配，繼續查找下一個")

            # 如果找不到本地數據，默認返回1
            logger.info("[國際服排行] 未找到本地數據，使用默認武器精煉度: 1")
            return 1

        except Exception as e:
            logger.warning(f"[國際服排行] 提取武器精煉度失敗: {e}")
            return 1

    async def _check_weapon_resonance_level(
        self, rank_data: dict, waves_data: list
    ) -> bool:
        """檢查武器精煉度是否符合上傳條件"""
        try:
            current_resonance_level = rank_data.get("weapon_resonance_level", 1)
            char_id = rank_data.get("char_id")

            logger.info(f"[國際服排行] 當前武器精煉度: {current_resonance_level}")

            # 如果當前精煉度大於1，直接上傳
            if current_resonance_level > 1:
                logger.info(
                    f"[國際服排行] 武器精煉度大於1，符合上傳條件: {current_resonance_level}"
                )
                return True

            # 如果當前精煉度等於1，檢查本地數據中的舊精煉度
            if current_resonance_level == 1 and waves_data:
                for char_data in waves_data:
                    if char_data.get("charId") == char_id:
                        weapon_data = char_data.get("weaponData", {})
                        old_resonance_level = weapon_data.get("resonLevel", 1)

                        # 如果舊數據的精煉度大於1，則上傳
                        if old_resonance_level > 1:
                            logger.info(
                                f"[國際服排行] 舊數據武器精煉度大於1，符合上傳條件: {old_resonance_level}"
                            )
                            # 更新rank_data中的精煉度為舊數據的值
                            rank_data["weapon_resonance_level"] = old_resonance_level
                            return True
                        else:
                            logger.info(
                                f"[國際服排行] 舊數據武器精煉度等於1，跳過上傳: {old_resonance_level}"
                            )
                            return False

            # 默認情況：精煉度等於1，跳過上傳
            logger.info("[國際服排行] 武器精煉度等於1，跳過上傳")
            return False

        except Exception as e:
            logger.error(f"[國際服排行] 檢查武器精煉度失敗: {e}")
            return False

    def _extract_sonata_name(self, equipment_data: list) -> str:
        """從裝備數據中提取聲骸套裝名稱"""
        try:
            if not equipment_data or not isinstance(equipment_data, list):
                return "未知套裝"

            # 統計套裝數量
            sonata_count = {}
            for equip in equipment_data:
                if isinstance(equip, dict):
                    sonata_name = equip.get("sonataName", "未知")
                    sonata_count[sonata_name] = sonata_count.get(sonata_name, 0) + 1

            # 找出最多的套裝
            if sonata_count:
                main_sonata = max(sonata_count.items(), key=lambda x: x[1])
                return f"{main_sonata[0]} ({main_sonata[1]}件)"

            return "散件"

        except Exception as e:
            logger.error(f"[國際服排行] 提取聲骸套裝失敗: {e}")
            return "未知套裝"

    async def _calculate_expected_damage_with_name(
        self, rank_data: Dict, waves_data: list
    ) -> tuple[float, str]:
        """計算期望傷害和期望傷害名稱"""
        try:
            # 使用用戶實際的數據計算期望傷害
            if not waves_data or len(waves_data) == 0:
                logger.warning("[國際服排行] 沒有用戶數據，無法計算期望傷害")
                return 0.0, "期望伤害"

            # 從用戶數據中獲取角色詳情
            user_data = waves_data[0]  # 取第一個（最新的）數據
            if not user_data or not user_data.get("role"):
                logger.warning("[國際服排行] 用戶數據結構不完整")
                return 0.0, "期望伤害"

            # 使用用戶實際的角色詳情數據
            from .calc import WuWaCalc
            from .calculate import get_calc_map
            from .api.model import RoleDetailData

            # 將用戶數據轉換為 RoleDetailData 對象
            role_detail = RoleDetailData(**user_data)

            # 創建 WuWaCalc 實例並處理數據（使用用戶實際數據）
            calc = WuWaCalc(role_detail)
            calc.phantom_pre = calc.prepare_phantom()
            calc.phantom_card = calc.enhance_summation_phantom_value(calc.phantom_pre)
            calc.calc_temp = get_calc_map(
                calc.phantom_card,
                role_detail.role.roleName,
                role_detail.role.roleId,
            )
            calc.role_card = calc.enhance_summation_card_value(calc.phantom_card)
            calc.damageAttribute = calc.card_sort_map_to_attribute(calc.role_card)

            # 使用 DamageRankRegister 查找傷害計算函數
            try:
                from .damage.abstract import DamageRankRegister

                char_id = rank_data["char_id"]
                rank_detail = DamageRankRegister.find_class(str(char_id))
            except ImportError as e:
                logger.error(f"[國際服排行] 導入傷害計算模組失敗: {e}")
                return 0.0, "期望伤害"

            if rank_detail and "func" in rank_detail:
                # 深拷貝 damageAttribute 避免修改原始數據
                import copy

                damageAttributeTemp = copy.deepcopy(calc.damageAttribute)
                crit_damage, expected_damage = rank_detail["func"](
                    damageAttributeTemp, role_detail
                )
                # 處理期望傷害的格式（移除逗號）
                if isinstance(expected_damage, str):
                    expected_damage = expected_damage.replace(",", "")

                # 獲取期望傷害名稱
                expected_damage_name = rank_detail.get("title", "期望伤害")

                return (
                    float(expected_damage) if expected_damage else 0.0
                ), expected_damage_name

            return 0.0, "期望伤害"

        except Exception as e:
            logger.error(f"[國際服排行] 計算期望傷害失敗: {e}")
            return 0.0, "期望伤害"

    async def _calculate_expected_damage(
        self, rank_data: Dict, waves_data: list
    ) -> float:
        """計算期望傷害"""
        try:
            # 使用用戶實際的數據計算期望傷害，而不是重新生成
            if not waves_data or len(waves_data) == 0:
                logger.warning("[國際服排行] 沒有用戶數據，無法計算期望傷害")
                return 0.0

            # 從用戶數據中獲取角色詳情
            user_data = waves_data[0]  # 取第一個（最新的）數據
            if not user_data or not user_data.get("role"):
                logger.warning("[國際服排行] 用戶數據結構不完整")
                return 0.0

            # 使用用戶實際的角色詳情數據
            from .calc import WuWaCalc
            from .calculate import get_calc_map
            from .api.model import RoleDetailData

            # 將用戶數據轉換為 RoleDetailData 對象
            role_detail = RoleDetailData(**user_data)

            # 創建 WuWaCalc 實例並處理數據（使用用戶實際數據）
            calc = WuWaCalc(role_detail)
            calc.phantom_pre = calc.prepare_phantom()
            calc.phantom_card = calc.enhance_summation_phantom_value(calc.phantom_pre)
            calc.calc_temp = get_calc_map(
                calc.phantom_card,
                role_detail.role.roleName,
                role_detail.role.roleId,
            )
            calc.role_card = calc.enhance_summation_card_value(calc.phantom_card)
            calc.damageAttribute = calc.card_sort_map_to_attribute(calc.role_card)

            # 使用 DamageRankRegister 查找傷害計算函數
            try:
                from .damage.abstract import DamageRankRegister

                char_id = rank_data["char_id"]
                rank_detail = DamageRankRegister.find_class(str(char_id))
            except ImportError as e:
                logger.error(f"[國際服排行] 導入傷害計算模組失敗: {e}")
                return 0.0

            if rank_detail and "func" in rank_detail:
                # 深拷貝 damageAttribute 避免修改原始數據
                import copy

                damageAttributeTemp = copy.deepcopy(calc.damageAttribute)
                crit_damage, expected_damage = rank_detail["func"](
                    damageAttributeTemp, role_detail
                )
                # 處理期望傷害的格式（移除逗號）
                if isinstance(expected_damage, str):
                    expected_damage = expected_damage.replace(",", "")
                return float(expected_damage) if expected_damage else 0.0

            return 0.0

        except Exception as e:
            logger.error(f"[國際服排行] 計算期望傷害失敗: {e}")
            return 0.0

    async def _calculate_phantom_score(
        self, rank_data: Dict, waves_data: list
    ) -> float:
        """計算聲骸評分"""
        try:
            # 使用用戶實際的數據計算聲骸評分
            if not waves_data or len(waves_data) == 0:
                logger.warning("[國際服排行] 沒有用戶數據，無法計算聲骸評分")
                return 0.0

            # 從用戶數據中獲取角色詳情
            user_data = waves_data[0]  # 取第一個（最新的）數據
            if not user_data or not user_data.get("role"):
                logger.warning("[國際服排行] 用戶數據結構不完整")
                return 0.0

            # 使用用戶實際的角色詳情數據
            from .calc import WuWaCalc
            from .api.model import RoleDetailData
            from .calculate import get_calc_map, calc_phantom_score

            # 將用戶數據轉換為 RoleDetailData 對象
            role_detail = RoleDetailData(**user_data)

            # 創建 WuWaCalc 實例並處理數據（使用用戶實際數據）
            calc = WuWaCalc(role_detail)
            calc.phantom_pre = calc.prepare_phantom()
            calc.phantom_card = calc.enhance_summation_phantom_value(calc.phantom_pre)
            calc.calc_temp = get_calc_map(
                calc.phantom_card, role_detail.role.roleName, role_detail.role.roleId
            )

            # 獲取裝備的聲骸列表
            equip_phantom_list = (
                role_detail.phantomData.equipPhantomList
                if role_detail.phantomData
                and hasattr(role_detail.phantomData, "equipPhantomList")
                else []
            )

            # 計算總評分
            phantom_score = 0.0
            if equip_phantom_list:  # 確保列表不為空
                for phantom in equip_phantom_list:
                    if (
                        phantom
                        and hasattr(phantom, "phantomProp")
                        and phantom.phantomProp
                    ):
                        try:
                            props = phantom.get_props()
                            score, _ = calc_phantom_score(
                                role_detail.role.roleName,
                                props,
                                phantom.cost,
                                calc.calc_temp,
                            )
                            phantom_score += score
                        except Exception as e:
                            logger.warning(f"[國際服排行] 聲骸評分計算跳過: {e}")
                            continue

            return phantom_score

        except Exception as e:
            logger.error(f"[國際服排行] 計算聲骸評分失敗: {e}")
            return 0.0

    async def _calculate_sonata_name(self, rank_data: Dict, waves_data: list) -> str:
        """計算套裝屬性名稱"""
        try:
            # 使用用戶實際的數據計算套裝屬性
            if not waves_data or len(waves_data) == 0:
                logger.warning("[國際服排行] 沒有用戶數據，無法計算套裝屬性")
                return "未知套裝"

            # 從用戶數據中獲取角色詳情
            user_data = waves_data[0]  # 取第一個（最新的）數據
            if not user_data or not user_data.get("role"):
                logger.warning("[國際服排行] 用戶數據結構不完整")
                return "未知套裝"

            # 使用用戶實際的角色詳情數據
            from .calc import WuWaCalc
            from .calculate import get_calc_map
            from .api.model import RoleDetailData

            # 將用戶數據轉換為 RoleDetailData 對象
            role_detail = RoleDetailData(**user_data)

            # 創建 WuWaCalc 實例並處理數據（使用用戶實際數據）
            calc = WuWaCalc(role_detail)
            calc.phantom_pre = calc.prepare_phantom()
            calc.phantom_card = calc.enhance_summation_phantom_value(calc.phantom_pre)
            calc.calc_temp = get_calc_map(
                calc.phantom_card, role_detail.role.roleName, role_detail.role.roleId
            )

            # 從計算後的phantom_card中獲取套裝信息（與bot排行邏輯一致）
            sonata_name = ""
            ph_detail = calc.phantom_card.get("ph_detail", [])
            if isinstance(ph_detail, list):
                for ph in ph_detail:
                    if ph.get("ph_num") == 5:  # 5件套裝
                        sonata_name = ph.get("ph_name", "")
                        break
                    if ph.get("isFull"):  # 完整套裝
                        sonata_name = ph.get("ph_name", "")
                        break

            logger.info(f"[國際服排行] 套裝屬性: {sonata_name}")
            return sonata_name if sonata_name else "散件"

        except Exception as e:
            logger.error(f"[國際服排行] 計算套裝屬性失敗: {e}")
            return "未知套裝"

    async def _upload_to_api(self, rank_data: Dict) -> bool:
        """上傳數據到排行API（自動判斷國服/國際服）"""
        try:
            from .rank_upload_manager import rank_upload_manager

            # 使用統一的上傳管理器，自動判斷服務器類型
            return await rank_upload_manager.upload_character_ranking(rank_data)

        except Exception as e:
            logger.exception(f"[排行上傳] API上傳失敗: {e}")
            return False


# 全局上傳器實例
international_uploader = InternationalRankUploader()
