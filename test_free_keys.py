#!/usr/bin/env python3
"""
測試免費線路OCR keys的可用性和餘額狀態
"""

import requests
import base64
import json
import time
from io import BytesIO
from PIL import Image

# 免費線路API keys列表
FREE_KEYS = [
    "K87115869688957",  # 原始免費key
    "K81457457688957",
    "K82846373288957",
    "K82808869488957",
    "K82766743188957",
    "K88154355588957",
    "K85254905088957",
]

# 免費線路API URL
FREE_URL = "https://api.ocr.space/parse/image"

def create_test_image():
    """創建測試圖片"""
    # 創建一個簡單的測試圖片
    img = Image.new('RGB', (100, 50), color='white')
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    
    # 添加文字
    try:
        font = ImageFont.load_default()
    except:
        font = None
    
    draw.text((10, 20), "Test", fill='black', font=font)
    
    # 轉換為base64
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_base64

def test_free_key(api_key):
    """測試免費線路key"""
    print(f"🔍 測試免費key: {api_key[:10]}...")
    
    try:
        # 創建測試圖片
        test_image = create_test_image()
        
        # 構建免費線路請求參數
        payload = {
            "apikey": api_key,
            "language": "eng",  # 使用英文，更簡單
            "isOverlayRequired": False,
            "base64Image": f"data:image/png;base64,{test_image}",
            "OCREngine": 2,  # 免費線路使用引擎2
            "isTable": False,
            "detectOrientation": False,
            "scale": False,
        }
        
        # 添加請求頭
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        print("   發送請求到免費線路...")
        start_time = time.time()
        
        # 發送請求到免費線路
        response = requests.post(
            FREE_URL,
            data=payload,
            headers=headers,
            timeout=15
        )
        
        end_time = time.time()
        response_time = round(end_time - start_time, 2)
        
        print(f"   響應時間: {response_time}秒")
        print(f"   HTTP狀態: {response.status_code}")
        
        # 檢查響應
        if response.status_code == 200:
            try:
                data = response.json()
                print("   ✅ 請求成功")
                
                # 檢查是否有識別結果
                if data.get("ParsedResults"):
                    parsed_results = data["ParsedResults"]
                    if parsed_results and len(parsed_results) > 0:
                        first_result = parsed_results[0]
                        if first_result.get("ParsedText"):
                            print("   ✅ 識別成功")
                            print(f"   識別結果: {first_result['ParsedText'][:50]}...")
                            return True
                        else:
                            print("   ⚠️ 無識別文字")
                            return False
                    else:
                        print("   ⚠️ 無解析結果")
                        return False
                else:
                    print("   ⚠️ 無ParsedResults")
                    print(f"   響應內容: {json.dumps(data, indent=2)[:200]}...")
                    return False
                    
            except json.JSONDecodeError as e:
                print(f"   ❌ JSON解析失敗: {e}")
                print(f"   原始響應: {response.text[:200]}...")
                return False
        
        elif response.status_code == 403:
            print("   ❌ 403 Forbidden - 可能餘額用盡或key無效")
            try:
                error_data = response.json()
                if "error" in error_data:
                    print(f"   錯誤信息: {error_data['error']}")
            except:
                pass
            return False
        
        elif response.status_code == 401:
            print("   ❌ 401 Unauthorized - API key無效")
            return False
        
        elif response.status_code == 429:
            print("   ⚠️ 429 Too Many Requests - 請求過於頻繁")
            return False
        
        elif response.status_code == 400:
            print("   ❌ 400 Bad Request - 請求參數錯誤")
            try:
                error_data = response.json()
                if "error" in error_data:
                    print(f"   錯誤信息: {error_data['error']}")
            except:
                pass
            return False
        
        else:
            print(f"   ❌ HTTP {response.status_code}錯誤")
            print(f"   響應內容: {response.text[:200]}...")
            return False
    
    except requests.exceptions.Timeout:
        print("   ⏰ 請求超時")
        return False
    
    except requests.exceptions.ConnectionError:
        print("   🔌 連接錯誤")
        return False
    
    except Exception as e:
        print(f"   ❌ 請求失敗: {e}")
        return False

def test_quota_info(api_key):
    """測試配額信息"""
    print(f"   🔍 檢查配額信息...")
    
    try:
        # 嘗試獲取配額信息
        quota_url = "https://api.ocr.space/parse/usage"
        response = requests.get(
            quota_url,
            params={"apikey": api_key},
            timeout=10
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   ✅ 配額信息: {json.dumps(data, indent=2)}")
                return data
            except json.JSONDecodeError:
                print(f"   ⚠️ 配額信息JSON解析失敗")
                return None
        else:
            print(f"   ⚠️ 配額信息請求失敗: HTTP {response.status_code}")
            return None
            
    except Exception as e:
        print(f"   ⚠️ 配額信息檢查失敗: {e}")
        return None

def main():
    """主函數"""
    print("🔍 免費線路OCR Keys檢測")
    print("="*80)
    
    available_keys = []
    unavailable_keys = []
    quota_info = {}
    
    for i, key in enumerate(FREE_KEYS, 1):
        print(f"\n[{i}/{len(FREE_KEYS)}] 測試免費key: {key}")
        print("-" * 50)
        
        # 測試key可用性
        if test_free_key(key):
            available_keys.append(key)
            print("   ✅ 狀態: 可用")
        else:
            unavailable_keys.append(key)
            print("   ❌ 狀態: 不可用")
        
        # 檢查配額信息
        quota = test_quota_info(key)
        if quota:
            quota_info[key] = quota
        
        # 添加延遲避免請求過於頻繁
        if i < len(FREE_KEYS):
            print("   等待3秒...")
            time.sleep(3)
    
    # 生成報告
    print("\n" + "="*80)
    print("📊 免費線路檢測報告")
    print("="*80)
    print(f"總共測試: {len(FREE_KEYS)} 個免費keys")
    print(f"可用keys: {len(available_keys)} 個")
    print(f"不可用keys: {len(unavailable_keys)} 個")
    
    if available_keys:
        print(f"\n✅ 可用的免費keys:")
        for key in available_keys:
            print(f"   - {key}")
            if key in quota_info:
                print(f"     配額: {quota_info[key]}")
    
    if unavailable_keys:
        print(f"\n❌ 不可用的免費keys:")
        for key in unavailable_keys:
            print(f"   - {key}")
            if key in quota_info:
                print(f"     配額: {quota_info[key]}")
    
    # 總結
    print(f"\n📈 總結:")
    if available_keys:
        print(f"   ✅ 有 {len(available_keys)} 個免費key可用")
        print(f"   建議優先使用: {available_keys[0]}")
    else:
        print(f"   ❌ 所有免費key都不可用")
        print(f"   ⚠️ 可能需要檢查網絡連接或API狀態")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
