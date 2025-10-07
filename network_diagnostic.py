#!/usr/bin/env python3
"""
網絡診斷和OCR key檢測腳本
"""

import requests
import base64
import json
import socket
import time
from io import BytesIO
from PIL import Image

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

def test_network_connectivity():
    """測試網絡連接"""
    print("🔍 測試網絡連接...")
    
    # 測試DNS解析
    try:
        ip = socket.gethostbyname("api.ocr.space")
        print(f"   ✅ DNS解析成功: api.ocr.space -> {ip}")
    except socket.gaierror as e:
        print(f"   ❌ DNS解析失敗: {e}")
        return False
    
    # 測試TCP連接
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((ip, 443))
        sock.close()
        
        if result == 0:
            print(f"   ✅ TCP連接成功: {ip}:443")
        else:
            print(f"   ❌ TCP連接失敗: {ip}:443")
            return False
    except Exception as e:
        print(f"   ❌ TCP連接錯誤: {e}")
        return False
    
    return True

def test_http_connectivity():
    """測試HTTP連接"""
    print("\n🔍 測試HTTP連接...")
    
    try:
        # 測試簡單的HTTP請求
        response = requests.get("https://api.ocr.space/", timeout=10)
        print(f"   ✅ HTTP連接成功: {response.status_code}")
        return True
    except requests.exceptions.Timeout:
        print("   ⏰ HTTP連接超時")
        return False
    except requests.exceptions.ConnectionError:
        print("   🔌 HTTP連接錯誤")
        return False
    except Exception as e:
        print(f"   ❌ HTTP連接失敗: {e}")
        return False

def create_minimal_test_image():
    """創建最小的測試圖片"""
    # 創建一個1x1像素的圖片
    img = Image.new('RGB', (1, 1), color='white')
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_base64

def test_simple_ocr_request():
    """測試簡單的OCR請求"""
    print("\n🔍 測試簡單OCR請求...")
    
    try:
        # 使用最小的測試圖片
        test_image = create_minimal_test_image()
        
        payload = {
            "apikey": FREE_KEYS[0],  # 使用第一個key
            "language": "eng",  # 使用英文，更簡單
            "isOverlayRequired": False,
            "base64Image": f"data:image/png;base64,{test_image}",
            "OCREngine": 1,  # 使用引擎1，更簡單
            "isTable": False,
            "detectOrientation": False,
            "scale": False,
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print(f"   使用key: {FREE_KEYS[0][:10]}...")
        print("   發送請求...")
        
        start_time = time.time()
        response = requests.post(
            "https://api.ocr.space/parse/image",
            data=payload,
            headers=headers,
            timeout=15
        )
        end_time = time.time()
        
        print(f"   響應時間: {round(end_time - start_time, 2)}秒")
        print(f"   HTTP狀態: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print("   ✅ OCR請求成功")
                print(f"   響應內容: {json.dumps(data, indent=2)[:200]}...")
                return True
            except json.JSONDecodeError:
                print("   ❌ JSON解析失敗")
                print(f"   原始響應: {response.text[:200]}...")
                return False
        else:
            print(f"   ❌ HTTP錯誤: {response.status_code}")
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

def test_all_keys_quick():
    """快速測試所有keys"""
    print("\n🔍 快速測試所有keys...")
    
    available_keys = []
    unavailable_keys = []
    
    for i, key in enumerate(FREE_KEYS, 1):
        print(f"\n[{i}/{len(FREE_KEYS)}] 測試key: {key[:10]}...")
        
        try:
            # 使用最小的測試圖片
            test_image = create_minimal_test_image()
            
            payload = {
                "apikey": key,
                "language": "eng",
                "isOverlayRequired": False,
                "base64Image": f"data:image/png;base64,{test_image}",
                "OCREngine": 1,
                "isTable": False,
                "detectOrientation": False,
                "scale": False,
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            start_time = time.time()
            response = requests.post(
                "https://api.ocr.space/parse/image",
                data=payload,
                headers=headers,
                timeout=10
            )
            end_time = time.time()
            
            response_time = round(end_time - start_time, 2)
            print(f"   響應時間: {response_time}秒")
            print(f"   HTTP狀態: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("ParsedResults"):
                        print("   ✅ 可用")
                        available_keys.append(key)
                    else:
                        print("   ⚠️ 無結果")
                        unavailable_keys.append(key)
                except json.JSONDecodeError:
                    print("   ❌ JSON解析失敗")
                    unavailable_keys.append(key)
            elif response.status_code == 403:
                print("   ❌ 403 - 可能餘額用盡")
                unavailable_keys.append(key)
            elif response.status_code == 401:
                print("   ❌ 401 - API key無效")
                unavailable_keys.append(key)
            else:
                print(f"   ❌ HTTP {response.status_code}")
                unavailable_keys.append(key)
                
        except requests.exceptions.Timeout:
            print("   ⏰ 超時")
            unavailable_keys.append(key)
        except Exception as e:
            print(f"   ❌ 錯誤: {e}")
            unavailable_keys.append(key)
        
        # 添加延遲
        if i < len(FREE_KEYS):
            time.sleep(1)
    
    return available_keys, unavailable_keys

def main():
    """主函數"""
    print("🔍 OCR Key網絡診斷和檢測")
    print("="*80)
    
    # 1. 測試網絡連接
    if not test_network_connectivity():
        print("\n❌ 網絡連接失敗，無法繼續檢測")
        return
    
    # 2. 測試HTTP連接
    if not test_http_connectivity():
        print("\n❌ HTTP連接失敗，無法繼續檢測")
        return
    
    # 3. 測試簡單OCR請求
    if not test_simple_ocr_request():
        print("\n❌ 簡單OCR請求失敗，可能API有問題")
        return
    
    # 4. 測試所有keys
    print("\n" + "="*80)
    available_keys, unavailable_keys = test_all_keys_quick()
    
    # 5. 生成報告
    print("\n" + "="*80)
    print("📊 最終檢測報告")
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
