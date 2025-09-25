# kuro.py 安裝指南

## 概述

WutheringWavesUID 現在使用最新的 kuro.py 庫來處理國際服登入和 Geetest 驗證。kuro.py 是一個外部依賴，需要單獨安裝。

## 安裝方法

### 方法 1: 使用 pip 安裝（推薦）

```bash
pip install kuro.py>=0.6.0
```

### 方法 2: 從源碼安裝

```bash
git clone https://github.com/Wuthery/kuro.py.git
cd kuro.py
pip install -e .
```

### 方法 3: 使用 uv 安裝

```bash
uv add kuro.py>=0.6.0
```

## 驗證安裝

安裝完成後，可以通過以下方式驗證：

```python
import kuro
print(f"kuro.py 版本: {kuro.__version__}")

# 測試主要功能
from kuro.types import Region
from kuro.models.auth.web import MMTResult
from kuro.client.components.auth.subclients.game import GameAuthClient

print("✅ kuro.py 安裝成功！")
```

## 主要功能

### 1. Geetest 驗證支持

kuro.py 0.6.0+ 版本包含完整的 Geetest 驗證支持：

- `MMTResult` 模型用於處理 Geetest 數據
- `get_game_dict()` 方法將 Geetest 數據轉換為遊戲 API 格式
- 自動處理時間戳驗證和錯誤處理

### 2. 國際服登入

```python
import kuro
from kuro.types import Region

# 創建客戶端
client = kuro.Client(region=Region.OVERSEAS)

# 正常登入
login_result = await client.game_login(email, password)

# 帶 Geetest 驗證的登入
mmt_result = kuro.models.MMTResult(**geetest_data)
login_result = await client.game_login(email, password, mmt_result=mmt_result)
```

### 3. 錯誤處理

kuro.py 提供了專門的錯誤類：

```python
from kuro import errors

try:
    # 登入操作
    pass
except errors.GeetestTriggeredError:
    # 處理 41000 錯誤（需要 Geetest 驗證）
    pass
except errors.KuroError as e:
    # 處理其他錯誤
    pass
```

## 依賴關係

kuro.py 的主要依賴：

- `httpx` - HTTP 客戶端
- `pydantic` - 數據驗證
- `aiohttp` - 異步 HTTP 服務器（用於 Geetest 服務器）

## 故障排除

### 1. 導入錯誤

如果遇到 `ModuleNotFoundError: No module named 'kuro'`：

```bash
# 檢查是否已安裝
pip list | grep kuro

# 重新安裝
pip uninstall kuro.py
pip install kuro.py>=0.6.0
```

### 2. 版本不匹配

確保使用 kuro.py 0.6.0 或更高版本：

```python
import kuro
print(kuro.__version__)  # 應該 >= 0.6.0
```

### 3. Geetest 功能不可用

如果 Geetest 相關功能不可用，請檢查：

```python
# 檢查 MMTResult 是否可用
from kuro.models.auth.web import MMTResult

# 檢查 get_game_dict 方法
mmt = MMTResult(
    captcha_id="test",
    lot_number="test",
    pass_token="test",
    gen_time="test",
    captcha_output="test"
)
print(mmt.get_game_dict())
```

## 更新日誌

### v0.6.0 主要更新

- ✅ 添加 `MMTResult.get_game_dict()` 方法
- ✅ 改進 `game_login` 方法支持 `mmt_result` 參數
- ✅ 更新設備參數和 API 端點
- ✅ 改進 Geetest 錯誤處理
- ✅ 支持最新的 Geetest 驗證流程

## 相關鏈接

- [kuro.py GitHub](https://github.com/Wuthery/kuro.py)
- [kuro.py PyPI](https://pypi.org/project/kuro.py/)
- [WutheringWavesUID GitHub](https://github.com/tyql688/WutheringWavesUID)

## 注意事項

1. **版本要求**: 必須使用 kuro.py 0.6.0 或更高版本
2. **Python 版本**: 需要 Python 3.10 或更高版本
3. **依賴管理**: 建議使用虛擬環境管理依賴
4. **網絡要求**: 需要能夠訪問 Kuro Games 的 API 服務器

---

如有問題，請檢查上述故障排除部分或提交 Issue。
