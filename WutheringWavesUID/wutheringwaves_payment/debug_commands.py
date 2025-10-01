"""
調試指令註冊問題
"""


def debug_command_registration():
    """調試指令註冊"""
    print("🔍 開始調試指令註冊...")

    try:
        # 1. 檢查模組導入
        print("1. 檢查模組導入...")
        from . import payment_commands, premium_commands

        print("   ✅ 指令處理器模組導入成功")

        # 2. 檢查服務創建
        print("2. 檢查服務創建...")
        from .premium_commands import sv_premium
        from .payment_commands import sv_redeem, sv_payment

        print("   ✅ 服務創建成功")

        # 3. 檢查指令註冊
        print("3. 檢查指令註冊...")
        print(f"   sv_payment: {sv_payment}")
        print(f"   sv_redeem: {sv_redeem}")
        print(f"   sv_premium: {sv_premium}")

        # 4. 檢查指令列表
        print("4. 檢查可用指令...")
        print("   付費機制指令:")
        for handler in sv_payment._handlers:
            if hasattr(handler, "cmds"):
                print(f"     - {handler.cmds}")

        print("   兌換碼指令:")
        for handler in sv_redeem._handlers:
            if hasattr(handler, "cmds"):
                print(f"     - {handler.cmds}")

        print("   Premium功能指令:")
        for handler in sv_premium._handlers:
            if hasattr(handler, "cmds"):
                print(f"     - {handler.cmds}")

        print("✅ 指令註冊調試完成")
        return True

    except Exception as e:
        print(f"❌ 指令註冊調試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    debug_command_registration()
