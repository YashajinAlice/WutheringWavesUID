#!/usr/bin/env python3
"""
檢測free線路的所有key可用性和餘額狀態
"""

import asyncio
import aiohttp
import base64
import json
from io import BytesIO
from PIL import Image
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Free線路API keys列表
FREE_KEYS = [
    "K87115869688957",  # 原始免費key
    "K81457457688957",
    "K82846373288957",
    "K82808869488957",
    "K82766743188957",
    "K88154355588957",
    "K85254905088957",
]

# OCR.space API URLs
FREE_URL = "https://api.ocr.space/parse/image"
PRO_URL = "https://apipro2.ocr.space/parse/image"

class OCRKeyChecker:
    def __init__(self):
        self.session = None
        self.results = {}
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def create_test_image(self):
        """創建一個簡單的測試圖片"""
        # 創建一個簡單的測試圖片
        img = Image.new('RGB', (200, 100), color='white')
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        
        # 添加一些文字
        try:
            # 嘗試使用默認字體
            font = ImageFont.load_default()
        except:
            font = None
        
        draw.text((10, 40), "Test OCR", fill='black', font=font)
        
        # 轉換為base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return img_base64
    
    async def test_key(self, api_key: str) -> dict:
        """測試單個API key"""
        result = {
            'key': api_key,
            'status': 'unknown',
            'error': None,
            'response_time': None,
            'quota_info': None,
            'engine_available': False
        }
        
        try:
            # 創建測試圖片
            test_image = self.create_test_image()
            
            # 構建請求參數
            payload = {
                "apikey": api_key,
                "language": "cht",
                "isOverlayRequired": False,
                "base64Image": f"data:image/png;base64,{test_image}",
                "OCREngine": 2,  # 使用引擎2
                "isTable": True,
                "detectOrientation": False,
                "scale": False,
            }
            
            # 發送請求，增加重試機制
            start_time = asyncio.get_event_loop().time()
            
            # 添加請求頭
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with self.session.post(
                FREE_URL, 
                data=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)  # 減少超時時間
            ) as response:
                end_time = asyncio.get_event_loop().time()
                result['response_time'] = round(end_time - start_time, 2)
                
                # 檢查HTTP狀態碼
                if response.status == 200:
                    data = await response.json()
                    
                    # 檢查響應內容
                    if data.get("ParsedResults"):
                        result['status'] = 'available'
                        result['engine_available'] = True
                        logger.info(f"✅ Key {api_key[:10]}... 可用")
                    else:
                        result['status'] = 'no_results'
                        result['error'] = "No parsed results"
                        logger.warning(f"⚠️ Key {api_key[:10]}... 無識別結果")
                
                elif response.status == 403:
                    result['status'] = 'forbidden'
                    result['error'] = "403 Forbidden - 可能餘額用盡或key無效"
                    logger.error(f"❌ Key {api_key[:10]}... 403錯誤 - 可能餘額用盡")
                
                elif response.status == 401:
                    result['status'] = 'unauthorized'
                    result['error'] = "401 Unauthorized - API key無效"
                    logger.error(f"❌ Key {api_key[:10]}... 401錯誤 - API key無效")
                
                elif response.status == 429:
                    result['status'] = 'rate_limited'
                    result['error'] = "429 Too Many Requests - 請求過於頻繁"
                    logger.warning(f"⚠️ Key {api_key[:10]}... 429錯誤 - 請求過於頻繁")
                
                else:
                    result['status'] = 'error'
                    result['error'] = f"HTTP {response.status}"
                    logger.error(f"❌ Key {api_key[:10]}... HTTP {response.status}錯誤")
                
                # 嘗試獲取配額信息
                try:
                    quota_data = await self.get_quota_info(api_key)
                    result['quota_info'] = quota_data
                except Exception as e:
                    logger.debug(f"無法獲取key {api_key[:10]}... 的配額信息: {e}")
        
        except asyncio.TimeoutError:
            result['status'] = 'timeout'
            result['error'] = "請求超時"
            logger.error(f"⏰ Key {api_key[:10]}... 請求超時")
        
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            logger.error(f"❌ Key {api_key[:10]}... 測試失敗: {e}")
        
        return result
    
    async def get_quota_info(self, api_key: str) -> dict:
        """獲取API配額信息"""
        try:
            # 嘗試獲取配額信息（如果API支持）
            quota_url = "https://api.ocr.space/parse/usage"
            async with self.session.get(
                quota_url,
                params={"apikey": api_key},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    return {"error": f"HTTP {response.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def check_all_keys(self):
        """檢測所有free線路keys"""
        logger.info("開始檢測free線路的所有API keys...")
        
        # 並發測試所有keys，但限制並發數
        semaphore = asyncio.Semaphore(2)  # 限制同時測試2個key
        
        async def test_with_semaphore(key):
            async with semaphore:
                return await self.test_key(key)
        
        # 執行所有測試
        tasks = [test_with_semaphore(key) for key in FREE_KEYS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 處理結果
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.results[FREE_KEYS[i]] = {
                    'key': FREE_KEYS[i],
                    'status': 'error',
                    'error': str(result),
                    'response_time': None,
                    'quota_info': None,
                    'engine_available': False
                }
            else:
                self.results[result['key']] = result
        
        return self.results
    
    def generate_report(self):
        """生成檢測報告"""
        print("\n" + "="*80)
        print("🔍 FREE線路API Keys檢測報告")
        print("="*80)
        
        available_count = 0
        unavailable_count = 0
        
        for key, result in self.results.items():
            status_emoji = {
                'available': '✅',
                'forbidden': '❌',
                'unauthorized': '❌',
                'rate_limited': '⚠️',
                'timeout': '⏰',
                'error': '❌',
                'no_results': '⚠️'
            }.get(result['status'], '❓')
            
            print(f"\n{status_emoji} Key: {key[:10]}...")
            print(f"   狀態: {result['status']}")
            if result['error']:
                print(f"   錯誤: {result['error']}")
            if result['response_time']:
                print(f"   響應時間: {result['response_time']}秒")
            if result['quota_info']:
                print(f"   配額信息: {result['quota_info']}")
            
            if result['status'] == 'available':
                available_count += 1
            else:
                unavailable_count += 1
        
        print("\n" + "-"*80)
        print(f"📊 統計結果:")
        print(f"   可用keys: {available_count}/{len(FREE_KEYS)}")
        print(f"   不可用keys: {unavailable_count}/{len(FREE_KEYS)}")
        
        # 列出可用的keys
        available_keys = [key for key, result in self.results.items() if result['status'] == 'available']
        if available_keys:
            print(f"\n✅ 可用的keys:")
            for key in available_keys:
                print(f"   - {key}")
        
        # 列出不可用的keys
        unavailable_keys = [key for key, result in self.results.items() if result['status'] != 'available']
        if unavailable_keys:
            print(f"\n❌ 不可用的keys:")
            for key in unavailable_keys:
                result = self.results[key]
                print(f"   - {key} ({result['status']})")
        
        print("\n" + "="*80)

async def main():
    """主函數"""
    async with OCRKeyChecker() as checker:
        await checker.check_all_keys()
        checker.generate_report()

if __name__ == "__main__":
    asyncio.run(main())
