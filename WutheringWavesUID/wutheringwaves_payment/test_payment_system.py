"""
付費機制測試腳本
"""

import time
import asyncio

from .payment_manager import payment_manager
from .premium_features import premium_features
from .user_tier_manager import user_tier_manager
from .redeem_code_manager import redeem_code_manager


async def test_payment_system():
    """測試付費機制功能"""
    print("🧪 開始測試付費機制系統...")

    # 測試用戶ID
    test_user_id = "123456789"

    print("\n1. 測試用戶等級管理")
    # 測試一般用戶
    tier = payment_manager.get_user_tier(test_user_id)
    print(f"   用戶等級: {tier}")
    assert tier == "free", "初始用戶應該是免費用戶"

    # 測試添加Premium用戶
    success = user_tier_manager.add_premium_user(test_user_id, 1)  # 1個月
    print(f"   添加Premium用戶: {success}")
    assert success, "添加Premium用戶應該成功"

    # 測試Premium狀態
    is_premium = payment_manager.is_premium_user(test_user_id)
    print(f"   是否為Premium用戶: {is_premium}")
    assert is_premium, "用戶應該是Premium用戶"

    print("\n2. 測試冷卻時間管理")
    # 測試冷卻時間
    analyze_cooldown = payment_manager.get_cooldown_time(test_user_id, "analyze")
    print(f"   分析冷卻時間: {analyze_cooldown} 秒")
    assert analyze_cooldown == 0, "Premium用戶應該無冷卻限制"

    # 測試綁定限制
    max_bind = payment_manager.get_max_bind_num(test_user_id)
    print(f"   最大綁定數量: {max_bind}")
    assert max_bind == 999, "Premium用戶應該無綁定限制"

    print("\n3. 測試兌換碼系統")
    # 創建兌換碼
    code = redeem_code_manager.create_redeem_code(1, None)  # 1個月，通用
    print(f"   創建兌換碼: {code}")
    assert code, "兌換碼創建應該成功"

    # 測試兌換碼信息
    code_info = redeem_code_manager.get_redeem_code_info(code)
    print(f"   兌換碼信息: {code_info}")
    assert code_info, "應該能獲取兌換碼信息"

    print("\n4. 測試Premium功能")
    # 測試功能權限檢查
    can_use, error_msg = premium_features.check_premium_access(
        test_user_id, "custom_panel"
    )
    print(f"   自定義面板權限: {can_use}")
    assert can_use, "Premium用戶應該有自定義面板權限"

    # 測試功能狀態
    feature_status = premium_features.get_premium_feature_status(test_user_id)
    print(f"   功能狀態: {feature_status}")
    assert feature_status["custom_panel"], "Premium用戶應該有自定義面板功能"

    print("\n5. 測試用戶限制信息")
    # 獲取用戶限制信息
    limits_info = payment_manager.get_user_limits_info(test_user_id)
    print(f"   限制信息: {limits_info}")
    assert limits_info["is_premium"], "用戶應該是Premium用戶"
    assert limits_info["features"]["custom_panel"], "用戶應該有自定義面板功能"

    print("\n6. 測試清理功能")
    # 測試清理過期數據
    clean_result = payment_manager.clean_expired_data()
    print(f"   清理結果: {clean_result}")

    print("\n7. 測試移除Premium用戶")
    # 移除Premium用戶
    success = user_tier_manager.remove_premium_user(test_user_id)
    print(f"   移除Premium用戶: {success}")
    assert success, "移除Premium用戶應該成功"

    # 驗證移除結果
    is_premium = payment_manager.is_premium_user(test_user_id)
    print(f"   移除後是否為Premium用戶: {is_premium}")
    assert not is_premium, "移除後用戶不應該是Premium用戶"

    print("\n✅ 所有測試通過！付費機制系統運行正常。")


async def test_redeem_code_usage():
    """測試兌換碼使用"""
    print("\n🧪 測試兌換碼使用...")

    test_user_id = "987654321"
    test_code = "TEST123456789"

    # 創建測試兌換碼
    code = redeem_code_manager.create_redeem_code(1, test_user_id)
    print(f"   創建專用兌換碼: {code}")

    # 測試使用兌換碼
    success, message = payment_manager.use_redeem_code(code, test_user_id)
    print(f"   使用兌換碼: {success}, 消息: {message}")
    assert success, "兌換碼使用應該成功"

    # 驗證用戶升級
    is_premium = payment_manager.is_premium_user(test_user_id)
    print(f"   兌換後是否為Premium用戶: {is_premium}")
    assert is_premium, "兌換後用戶應該是Premium用戶"

    print("✅ 兌換碼使用測試通過！")


if __name__ == "__main__":
    # 運行測試
    asyncio.run(test_payment_system())
    asyncio.run(test_redeem_code_usage())
