"""
測試OCR系統 - 驗證用戶等級區分和冷卻機制
"""

import os
import sys
import asyncio

# 添加項目路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wutheringwaves_payment.ocr_manager import ocr_manager
from wutheringwaves_payment.payment_manager import payment_manager


async def test_ocr_system():
    """測試OCR系統功能"""
    print("🧪 開始測試OCR系統...")

    # 測試用戶ID
    test_user_id = "123456789"

    print(f"\n📋 測試用戶: {test_user_id}")

    # 1. 測試一般用戶OCR配置
    print("\n🔍 測試一般用戶OCR配置...")
    api_key, engine_num = ocr_manager.get_user_ocr_config(test_user_id)
    engine_info = ocr_manager.get_engine_info(test_user_id)

    print(f"   API Key: {api_key}")
    print(f"   Engine: {engine_num}")
    print(f"   線路: {engine_info}")

    # 2. 測試Premium用戶OCR配置
    print("\n💎 設置為Premium用戶...")
    payment_manager.set_premium_user(test_user_id, 30)  # 30天Premium

    api_key_premium, engine_num_premium = ocr_manager.get_user_ocr_config(test_user_id)
    engine_info_premium = ocr_manager.get_engine_info(test_user_id)

    print(f"   API Key: {api_key_premium}")
    print(f"   Engine: {engine_num_premium}")
    print(f"   線路: {engine_info_premium}")

    # 3. 測試可用keys
    print("\n🔑 測試可用keys...")
    free_keys = ocr_manager.get_available_keys("free_user")
    premium_keys = ocr_manager.get_available_keys(test_user_id)

    print(f"   一般用戶可用keys: {free_keys}")
    print(f"   Premium用戶可用keys: {premium_keys}")

    # 4. 測試冷卻管理器
    print("\n⏰ 測試冷卻管理器...")
    try:
        from utils.enhanced_cooldown_manager import ocr_cooldown_manager

        # 測試冷卻檢查
        can_use, remaining = ocr_cooldown_manager.can_use(test_user_id)
        print(f"   可以使用: {can_use}")
        print(f"   剩餘時間: {remaining}")

        # 標記成功
        ocr_cooldown_manager.mark_success(test_user_id)
        print("   ✅ 冷卻標記成功")

        # 再次檢查
        can_use_after, remaining_after = ocr_cooldown_manager.can_use(test_user_id)
        print(f"   標記後可使用: {can_use_after}")
        print(f"   標記後剩餘時間: {remaining_after}")

    except ImportError as e:
        print(f"   ⚠️ 冷卻管理器未安裝: {e}")
    except Exception as e:
        print(f"   ❌ 冷卻管理器測試失敗: {e}")

    print("\n✅ OCR系統測試完成！")


if __name__ == "__main__":
    asyncio.run(test_ocr_system())
