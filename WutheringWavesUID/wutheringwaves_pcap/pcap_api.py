import aiohttp
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from gsuid_core.logger import logger


class PcapApi:
    """PCAP API 客戶端"""

    def __init__(self):
        self.base_url = "https://pcap.wuthery.com/v1"
        self.timeout = 30

    async def parse_pcap_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        上傳並解析 pcap 文件

        Args:
            file_path: pcap 文件路徑

        Returns:
            解析結果字典，如果失敗返回 None
        """
        try:
            file_path = Path(file_path)
            logger.debug(f"pcap path: {file_path}")
            if not file_path.exists():
                logger.error(f"PCAP 文件不存在: {file_path}")
                return None
            #  文件会冲突吗
            # 準備文件數據
            with open(file_path, "rb") as f:
                file_data = f.read()

            # 檢查文件大小
            file_size = len(file_data)
            logger.debug(f"pcap 文件大小: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
            
            if file_size == 0:
                logger.error(f"PCAP 文件為空: {file_path}")
                return None

            # 簡單驗證文件格式（檢查 pcap 文件頭）
            # pcap 文件通常以特定的魔數開頭
            # 標準 pcap: 0xa1b2c3d4 或 0xd4c3b2a1 (little/big endian)
            # pcapng: 0x0a0d0d0a
            if file_size >= 4:
                magic = int.from_bytes(file_data[:4], byteorder='little')
                magic_be = int.from_bytes(file_data[:4], byteorder='big')
                is_pcap = magic in [0xa1b2c3d4, 0xd4c3b2a1] or magic_be in [0xa1b2c3d4, 0xd4c3b2a1]
                is_pcapng = magic == 0x0a0d0d0a or magic_be == 0x0a0d0d0a
                
                if not (is_pcap or is_pcapng):
                    logger.warning(
                        f"文件可能不是有效的 pcap 格式 (魔數: {hex(magic)}/{hex(magic_be)})"
                    )
                    # 不直接返回，讓 API 來判斷

            # 準備表單數據
            # 嘗試不指定 content_type，讓服務器自動判斷
            data = aiohttp.FormData()
            data.add_field(
                "file",
                file_data,
                filename=file_path.name,
                # 不指定 content_type，讓 aiohttp 自動判斷或讓服務器判斷
            )

            # 發送請求
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:
                async with session.post(
                    f"{self.base_url}/parse", data=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"PCAP 解析成功: {file_path.name}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"PCAP 解析失敗: {response.status} - {error_text}")
                        # 如果是 400 錯誤，可能是文件格式問題
                        if response.status == 400:
                            logger.warning(
                                "API 返回 400 錯誤，可能的原因：\n"
                                "1. 文件格式不正確或損壞\n"
                                "2. 文件不是有效的 .pcap 或 .pcapng 格式\n"
                                "3. 文件不包含有效的鳴潮遊戲數據\n"
                                "4. 文件可能被加密或壓縮"
                            )
                        return None

        except asyncio.TimeoutError:
            logger.error(f"PCAP 解析超時: {file_path}")
            return None
        except Exception as e:
            logger.exception(f"PCAP 解析異常: {file_path}", e)
            return None


# 創建全局實例
pcap_api = PcapApi()
