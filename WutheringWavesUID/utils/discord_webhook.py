import json
import asyncio
from typing import Dict, List, Optional

import aiohttp
from gsuid_core.logger import logger


class DiscordWebhook:
    """Discord Webhook 推送類"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.session = None

    async def _get_session(self):
        """獲取或創建 aiohttp 會話"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """關閉會話"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def send_message(
        self,
        content: str = None,
        username: str = None,
        avatar_url: str = None,
        embeds: List[Dict] = None,
        files: List[Dict] = None,
    ) -> bool:
        """
        發送 Discord webhook 消息

        Args:
            content: 消息內容
            username: 發送者用戶名
            avatar_url: 發送者頭像 URL
            embeds: Discord embeds 列表
            files: 文件列表

        Returns:
            bool: 發送是否成功
        """
        try:
            session = await self._get_session()

            # 構建 payload
            payload = {}
            if content:
                payload["content"] = content
            if username:
                payload["username"] = username
            if avatar_url:
                payload["avatar_url"] = avatar_url
            if embeds:
                payload["embeds"] = embeds

            # 準備請求數據
            data = json.dumps(payload)
            headers = {"Content-Type": "application/json"}

            # 發送請求
            async with session.post(
                self.webhook_url,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 204:  # Discord webhook 成功響應
                    logger.info(f"[Discord Webhook] 消息發送成功")
                    return True
                else:
                    logger.error(
                        f"[Discord Webhook] 發送失敗: {response.status} - {await response.text()}"
                    )
                    return False

        except asyncio.TimeoutError:
            logger.error("[Discord Webhook] 發送超時")
            return False
        except Exception as e:
            logger.error(f"[Discord Webhook] 發送異常: {e}")
            return False

    async def send_stamina_notification(
        self,
        user_id: str,
        current_stamina: int,
        max_stamina: int,
        threshold: int,
        server_region: str = "未知",
    ) -> bool:
        """
        發送體力推送通知

        Args:
            user_id: 用戶 ID
            current_stamina: 當前體力
            max_stamina: 最大體力
            threshold: 體力閾值
            server_region: 伺服器區域

        Returns:
            bool: 發送是否成功
        """
        try:
            # 構建 Discord embed
            embed = {
                "title": "🌜 鳴潮體力推送提醒",
                "description": f"<@{user_id}> 你的結晶波片達到設定閾值啦！",
                "color": 0x00FF00,  # 綠色
                "fields": [
                    {
                        "name": "🕒 當前體力",
                        "value": f"{current_stamina}/{max_stamina}",
                        "inline": True,
                    },
                    {"name": "📊 體力閾值", "value": str(threshold), "inline": True},
                    {"name": "🌍 伺服器", "value": server_region, "inline": True},
                ],
                "footer": {"text": "請清完體力後使用 [每日] 來更新推送時間！"},
                "timestamp": None,  # Discord 會自動設置當前時間
            }

            # 設置時間戳
            import datetime

            embed["timestamp"] = datetime.datetime.utcnow().isoformat()

            return await self.send_message(
                embeds=[embed],
                username="鳴潮體力助手",
                avatar_url="https://cdn.discordapp.com/emojis/1234567890123456789.png",  # 可以設置一個默認頭像
            )

        except Exception as e:
            logger.error(f"[Discord Webhook] 體力推送通知發送失敗: {e}")
            return False


# 全局 webhook 實例
_webhook_instance = None


async def get_webhook_instance() -> Optional[DiscordWebhook]:
    """獲取 Discord webhook 實例"""
    global _webhook_instance

    if _webhook_instance is None:
        # 從配置中獲取 webhook URL
        from ..wutheringwaves_config import WutheringWavesConfig

        webhook_url = WutheringWavesConfig.get_config("DiscordWebhookUrl").data
        if not webhook_url:
            logger.warning("[Discord Webhook] 未配置 Discord Webhook URL")
            return None

        _webhook_instance = DiscordWebhook(webhook_url)
        logger.info("[Discord Webhook] Discord Webhook 實例已創建")

    return _webhook_instance


async def send_stamina_webhook(
    user_id: str,
    current_stamina: int,
    max_stamina: int,
    threshold: int,
    server_region: str = "未知",
) -> bool:
    """
    發送體力 webhook 推送

    Args:
        user_id: 用戶 ID
        current_stamina: 當前體力
        max_stamina: 最大體力
        threshold: 體力閾值
        server_region: 伺服器區域

    Returns:
        bool: 發送是否成功
    """
    webhook = await get_webhook_instance()
    if not webhook:
        logger.warning("[Discord Webhook] Webhook 實例不可用")
        return False

    return await webhook.send_stamina_notification(
        user_id=user_id,
        current_stamina=current_stamina,
        max_stamina=max_stamina,
        threshold=threshold,
        server_region=server_region,
    )


async def cleanup_webhook():
    """清理 webhook 資源"""
    global _webhook_instance
    if _webhook_instance:
        await _webhook_instance.close()
        _webhook_instance = None
        logger.info("[Discord Webhook] Webhook 資源已清理")
