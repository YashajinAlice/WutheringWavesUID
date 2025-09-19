#!/usr/bin/env python3
"""
鳴潮助手網站啟動腳本
獨立運行，不影響機器人服務
"""

import os
import sys
from pathlib import Path

# 添加當前目錄到 Python 路徑
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 直接導入模組
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# 配置
app_name = "鳴潮助手"
app_version = "1.0.0"
debug = False
host = "0.0.0.0"
port = 8000

# 創建 FastAPI 應用
app = FastAPI(
    title=app_name,
    version=app_version,
    description="鳴潮助手網站 - 獨立於機器人服務",
    docs_url="/api/docs" if debug else None,
    redoc_url="/api/redoc" if debug else None,
)

# 添加中間件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# 掛載靜態文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 設置模板
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index():
    """首頁"""
    return templates.TemplateResponse("index.html", {"request": None})

@app.get("/health")
async def health_check():
    """健康檢查"""
    return {"status": "healthy", "service": "waves_website"}

@app.get("/api/test")
async def test_api():
    """測試 API"""
    return {"message": "鳴潮助手網站 API 正常運行", "version": app_version}

if __name__ == "__main__":
    print("🚀 啟動鳴潮助手網站...")
    print("📝 注意：此服務完全獨立於機器人服務")
    print("🔒 不會影響現有的機器人功能")
    print("=" * 50)
    
    try:
        uvicorn.run(
            "start_server:app",
            host=host,
            port=port,
            reload=debug,
            log_level="info" if not debug else "debug"
        )
    except KeyboardInterrupt:
        print("\n👋 服務已停止")
    except Exception as e:
        print(f"❌ 啟動失敗: {e}")
        sys.exit(1)
