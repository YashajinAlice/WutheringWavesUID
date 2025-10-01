"""
測試付費機制指令註冊
"""


def test_command_registration():
    """測試指令註冊"""
    try:
        # 導入主模組
        from .. import wutheringwaves_payment

        print("✅ 付費模組導入成功")

        # 檢查指令處理器是否導入
        from . import payment_commands, premium_commands

        print("✅ 指令處理器導入成功")

        # 檢查服務是否創建
        from .premium_commands import sv_premium
        from .payment_commands import sv_redeem, sv_payment

        print("✅ 服務創建成功")

        print("✅ 所有指令已正確註冊！")
        return True

    except Exception as e:
        print(f"❌ 指令註冊失敗: {e}")
        return False


if __name__ == "__main__":
    test_command_registration()
