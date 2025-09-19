#!/usr/bin/env python3
"""
鳴潮助手網站啟動腳本
獨立運行，不影響機器人服務
"""

import os
import sys
from pathlib import Path

# 添加項目路徑
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 使用模組方式導入
import wutheringwaves_website
from wutheringwaves_website.app import run_server

if __name__ == "__main__":
    print("🚀 啟動鳴潮助手網站...")
    print("📝 注意：此服務完全獨立於機器人服務")
    print("🔒 不會影響現有的機器人功能")
    print("=" * 50)

    try:
        run_server()
    except KeyboardInterrupt:
        print("\n👋 服務已停止")
    except Exception as e:
        print(f"❌ 啟動失敗: {e}")
        sys.exit(1)
