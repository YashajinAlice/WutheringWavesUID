"""
國際服API配置和工具函數
"""

from typing import Any, Dict, List, Optional

import httpx
from gsuid_core.logger import logger

# 國際服API配置
INTERNATIONAL_API_CONFIG = {
    "base_url": "https://wwuidapi.fulin-net.top",
    "endpoints": {
        "slash_rank": "/api/international/slash/rank",
        "slash_record": "/api/international/slash/record",
        "abyss_rank": "/api/international/abyss/rank",
        "abyss_record": "/api/international/abyss/record",
        "character_record": "/api/international/character",
        "stats": "/api/international/stats",
    },
    "timeout": 10,
    "max_retries": 3,
}


class InternationalAPIClient:
    """國際服API客戶端"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or INTERNATIONAL_API_CONFIG["base_url"]
        self.timeout = INTERNATIONAL_API_CONFIG["timeout"]
        self.max_retries = INTERNATIONAL_API_CONFIG["max_retries"]

    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """發送HTTP請求"""
        url = f"{self.base_url}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        timeout=httpx.Timeout(self.timeout),
                        **kwargs,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        logger.info(f"API請求成功: {url}, 數據類型: {type(result)}")
                        return result
                    else:
                        logger.warning(
                            f"API請求失敗: {response.status_code} - {response.text}"
                        )
                        if attempt == self.max_retries - 1:
                            return None

            except Exception as e:
                logger.warning(
                    f"API請求異常 (嘗試 {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt == self.max_retries - 1:
                    logger.exception(f"API請求最終失敗: {e}")
                    return None

        return None

    async def get_slash_rank(self, limit: int = 20) -> Optional[Dict[str, Any]]:
        """獲取無盡排行數據"""
        return await self._make_request(
            "GET",
            INTERNATIONAL_API_CONFIG["endpoints"]["slash_rank"],
            params={"limit": limit},
        )

    async def get_slash_record(self, uid: str) -> Optional[Dict[str, Any]]:
        """獲取指定UID的無盡排行記錄"""
        endpoint = f"{INTERNATIONAL_API_CONFIG['endpoints']['slash_record']}/{uid}"
        return await self._make_request("GET", endpoint)

    async def get_abyss_rank(self, limit: int = 20) -> Optional[Dict[str, Any]]:
        """獲取深淵排行數據"""
        return await self._make_request(
            "GET",
            INTERNATIONAL_API_CONFIG["endpoints"]["abyss_rank"],
            params={"limit": limit},
        )

    async def get_abyss_record(self, uid: str) -> Optional[Dict[str, Any]]:
        """獲取指定UID的深淵記錄"""
        endpoint = f"{INTERNATIONAL_API_CONFIG['endpoints']['abyss_record']}/{uid}"
        return await self._make_request("GET", endpoint)

    async def get_character_record(self, uid: str) -> Optional[Dict[str, Any]]:
        """獲取指定UID的角色記錄"""
        endpoint = f"{INTERNATIONAL_API_CONFIG['endpoints']['character_record']}/{uid}"
        return await self._make_request("GET", endpoint)

    async def get_stats(self) -> Optional[Dict[str, Any]]:
        """獲取統計數據"""
        return await self._make_request(
            "GET", INTERNATIONAL_API_CONFIG["endpoints"]["stats"]
        )

    async def upload_slash_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """上傳無盡排行數據"""
        return await self._make_request(
            "POST", "/api/international/slash/upload", json=data
        )

    async def upload_abyss_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """上傳深淵數據"""
        return await self._make_request(
            "POST", "/api/international/abyss/upload", json=data
        )

    async def upload_character_data(
        self, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """上傳角色數據"""
        return await self._make_request(
            "POST", "/api/international/character/upload", json=data
        )


# 全局API客戶端實例
international_api = InternationalAPIClient()


async def get_international_slash_rank(limit: int = 20) -> Optional[Dict[str, Any]]:
    """獲取國際服無盡排行數據"""
    return await international_api.get_slash_rank(limit)


async def get_international_slash_record(uid: str) -> Optional[Dict[str, Any]]:
    """獲取指定UID的國際服無盡排行記錄"""
    return await international_api.get_slash_record(uid)


async def get_international_abyss_rank(limit: int = 20) -> Optional[Dict[str, Any]]:
    """獲取國際服深淵排行數據"""
    return await international_api.get_abyss_rank(limit)


async def get_international_abyss_record(uid: str) -> Optional[Dict[str, Any]]:
    """獲取指定UID的國際服深淵記錄"""
    return await international_api.get_abyss_record(uid)


async def get_international_character_record(uid: str) -> Optional[Dict[str, Any]]:
    """獲取指定UID的國際服角色記錄"""
    return await international_api.get_character_record(uid)


async def get_international_stats() -> Optional[Dict[str, Any]]:
    """獲取國際服統計數據"""
    return await international_api.get_stats()


def update_api_config(
    base_url: str = None, timeout: int = None, max_retries: int = None
):
    """更新API配置"""
    if base_url:
        international_api.base_url = base_url
    if timeout:
        international_api.timeout = timeout
    if max_retries:
        international_api.max_retries = max_retries
