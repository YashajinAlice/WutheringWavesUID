"""
排行上傳管理器
處理國服和國際服的不同上傳邏輯
"""

from typing import Dict, Optional

from gsuid_core.logger import logger

from ..wutheringwaves_config import WutheringWavesConfig


class RankUploadManager:
    """排行上傳管理器"""

    def __init__(self):
        self.bot_name = "雅蘭娜"  # 機器人名稱，其他機器人可以修改這裡
        self.server_configs = {
            "cn": {  # 國服
                "needs_token": True,
                "upload_url": "https://top.camellya.xyz/top/waves/upload",
                "api_type": "cn_rank",
            },
            "international": {  # 國際服
                "needs_token": False,
                "upload_url": "https://wwuidapi.fulin-net.top/api/international/character/ranking/upload",
                "api_type": "international_rank",
            },
        }

    def get_server_type(self, uid: str) -> str:
        """根據UID判斷服務器類型"""
        # 簡單的UID判斷邏輯，可以根據實際情況調整
        if uid.startswith("1") or uid.startswith("2"):
            return "cn"  # 國服UID
        else:
            return "international"  # 國際服UID

    async def upload_character_ranking(self, rank_data: Dict) -> bool:
        """上傳角色排行數據"""
        try:
            server_type = self.get_server_type(rank_data.get("waves_id", ""))
            config = self.server_configs.get(server_type)

            if not config:
                logger.error(f"[排行上傳] 未知服務器類型: {server_type}")
                return False

            if config["needs_token"]:
                return await self._upload_to_cn_server(rank_data, config)
            else:
                return await self._upload_to_international_server(rank_data, config)

        except Exception as e:
            logger.exception(f"[排行上傳] 上傳失敗: {e}")
            return False

    async def _upload_to_cn_server(self, rank_data: Dict, config: Dict) -> bool:
        """上傳到國服服務器（需要token）"""
        try:
            import httpx

            # 獲取國服認證token
            waves_token = WutheringWavesConfig.get_config("WavesToken").data
            if not waves_token:
                logger.error("[國服排行] 未配置 WavesToken")
                return False

            # 構建國服上傳數據格式
            upload_data = {
                "waves_id": rank_data["waves_id"],
                "username": rank_data["username"],
                "char_id": rank_data["char_id"],
                "level": rank_data["level"],
                "chain": rank_data["chain"],
                "weapon_id": rank_data["weapon_id"],
                "weapon_level": rank_data["weapon_level"],
                "weapon_resonance_level": rank_data["weapon_resonance_level"],
                "sonata_name": rank_data["sonata_name"],
                "phantom_score": rank_data["phantom_score"],
                "expected_damage": rank_data["expected_damage"],
                "bot_name": self.bot_name,
                "version": rank_data.get("version", "1.0.0"),
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config["upload_url"],
                    json=upload_data,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {waves_token}",
                    },
                    timeout=httpx.Timeout(10),
                )

                if response.status_code == 200:
                    logger.info(f"[國服排行] 上傳成功: {rank_data['char_name']}")
                    return True
                else:
                    logger.error(
                        f"[國服排行] 上傳失敗: {response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            logger.exception(f"[國服排行] API上傳失敗: {e}")
            return False

    async def _upload_to_international_server(
        self, rank_data: Dict, config: Dict
    ) -> bool:
        """上傳到國際服服務器（直連）"""
        try:
            import httpx

            # 構建國際服上傳數據格式
            upload_data = {
                "uid": rank_data["waves_id"],
                "version": "1.0.0",  # 客戶端版本
                "characters": [
                    {
                        "character_id": rank_data["char_id"],
                        "character_name": rank_data["char_name"],
                        "level": rank_data["level"],
                        "resonance_chain": rank_data["chain"],
                        "weapon_id": rank_data["weapon_id"],
                        "weapon_level": rank_data["weapon_level"],
                        "weapon_resonance_level": rank_data["weapon_resonance_level"],
                        "sonata_name": rank_data["sonata_name"],
                        "phantom_resonance_score": rank_data.get("phantom_score", 0.0),
                        "expected_damage": rank_data.get("expected_damage", 0.0),
                        "expected_damage_name": rank_data.get(
                            "expected_damage_name", "期望伤害"
                        ),
                        "discord_user_id": rank_data.get(
                            "discord_user_id", ""
                        ),  # 新增Discord用戶ID
                        "username": rank_data.get("username", ""),  # 新增玩家名稱
                        "bot_name": self.bot_name,
                        "server_region": rank_data.get(
                            "server_region", "international"
                        ),
                    }
                ],
            }

            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        config["upload_url"],
                        json=upload_data,
                        headers={
                            "Content-Type": "application/json",
                        },
                        timeout=httpx.Timeout(10),
                    )

                    if response.status_code == 200:
                        logger.info(
                            f"[國際服排行] 上傳成功: {rank_data['char_name']} - 期望傷害: {rank_data.get('expected_damage', 0):,.0f}"
                        )
                        return True
                    else:
                        logger.error(
                            f"[國際服排行] 上傳失敗: {response.status_code} - {response.text}"
                        )
                        return False
                except httpx.ConnectError:
                    logger.warning(
                        f"[國際服排行] API服務器未運行，跳過上傳: {config['upload_url']}"
                    )
                    return False
                except Exception as e:
                    logger.error(f"[國際服排行] 上傳異常: {e}")
                    return False

        except Exception as e:
            logger.exception(f"[國際服排行] API上傳失敗: {e}")
            return False


# 全局上傳管理器實例
rank_upload_manager = RankUploadManager()
