#!/usr/bin/env python3
"""
簡單的OCR key檢測腳本
"""

import requests
import base64
import json
from io import BytesIO
from PIL import Image
import time

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

# OCR.space API URL
FREE_URL = "https://api.ocr.space/parse/image"

def create_test_image():
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

def test_key(api_key):
    """測試單個API key"""
    print(f"🔍 測試key: {api_key[:10]}...")
    
    try:
        # 創建測試圖片
        test_image = create_test_image()
        
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
        
        # 添加請求頭
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # 發送請求
        start_time = time.time()
        response = requests.post(
            FREE_URL, 
            data=payload,
            headers=headers,
            timeout=10
        )
        end_time = time.time()
        response_time = round(end_time - start_time, 2)
        
        print(f"   響應時間: {response_time}秒")
        print(f"   HTTP狀態: {response.status_code}")
        
        # 檢查HTTP狀態碼
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("ParsedResults"):
                    print("   ✅ 狀態: 可用")
                    print("   ✅ 引擎: 可用")
                    return True
                else:
                    print("   ⚠️ 狀態: 無識別結果")
                    return False
            except json.JSONDecodeError:
                print("   ❌ 狀態: JSON解析失敗")
                print(f"   響應內容: {response.text[:200]}...")
                return False
        
        elif response.status_code == 403:
            print("   ❌ 狀態: 403 Forbidden - 可能餘額用盡或key無效")
            return False
        
        elif response.status_code == 401:
            print("   ❌ 狀態: 401 Unauthorized - API key無效")
            return False
        
        elif response.status_code == 429:
            print("   ⚠️ 狀態: 429 Too Many Requests - 請求過於頻繁")
            return False
        
        else:
            print(f"   ❌ 狀態: HTTP {response.status_code}錯誤")
            print(f"   響應內容: {response.text[:200]}...")
            return False
    
    except requests.exceptions.Timeout:
        print("   ⏰ 狀態: 請求超時")
        return False
    
    except requests.exceptions.ConnectionError:
        print("   🔌 狀態: 連接錯誤")
        return False
    
    except Exception as e:
        print(f"   ❌ 狀態: 錯誤 - {e}")
        return False

def main():
    """主函數"""
    print("🔍 開始檢測free線路的所有API keys...")
    print("="*80)
    
    available_keys = []
    unavailable_keys = []
    
    for i, key in enumerate(FREE_KEYS, 1):
        print(f"\n[{i}/{len(FREE_KEYS)}] 測試key: {key}")
        try:
            if test_key(key):
                available_keys.append(key)
            else:
                unavailable_keys.append(key)
        except Exception as e:
            print(f"   ❌ 測試失敗: {e}")
            unavailable_keys.append(key)
        
        # 添加延遲避免請求過於頻繁
        if i < len(FREE_KEYS):
            print("   等待2秒...")
            time.sleep(2)
    
    # 生成報告
    print("\n" + "="*80)
    print("📊 檢測報告")
    print("="*80)
    print(f"總共測試: {len(FREE_KEYS)} 個keys")
    print(f"可用keys: {len(available_keys)} 個")
    print(f"不可用keys: {len(unavailable_keys)} 個")
    
    if available_keys:
        print(f"\n✅ 可用的keys:")
        for key in available_keys:
            print(f"   - {key}")
    
    if unavailable_keys:
        print(f"\n❌ 不可用的keys:")
        for key in unavailable_keys:
            print(f"   - {key}")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
