# 自定義背景功能使用指南

## 概述

Premium會員現在可以設置自定義背景圖片，讓您的角色面板更加個性化！支持圖片上傳和URL設置兩種方式。

## 功能特點

- 🖼️ **自定義背景圖片** - 上傳您喜歡的圖片作為面板背景
- 🔗 **URL背景設置** - 直接使用網絡圖片URL
- 📁 **自動文件管理** - 系統自動管理背景文件
- 🔄 **智能回退** - 如果自定義背景不可用，自動使用默認背景
- 💾 **文件驗證** - 自動驗證圖片格式和大小

## 使用方法

### 1. 設置背景圖片

#### 方法一：直接上傳圖片
```
設置背景圖片 [圖片]
```
直接發送圖片文件，系統會自動保存為您的專屬背景。

#### 方法二：使用圖片URL
```
設置背景URL https://example.com/your-image.png
```
使用網絡圖片的URL地址。

### 2. 查看背景信息
```
查看背景信息
```
查看您當前的背景設置狀態。

### 3. 重置背景
```
重置背景
```
刪除自定義背景，恢復使用默認背景。

## 支持的圖片格式

- PNG
- JPG/JPEG
- GIF
- BMP

## 文件大小限制

- 最大文件大小：10MB
- 建議尺寸：800x600 或更高分辨率

## 文件存儲位置

用戶自定義背景文件存儲在：
```
WutheringWavesUID/utils/texture2d/user_backgrounds/
```

文件命名格式：`{用戶ID}_bg.png`

## 技術實現

### 背景管理器

```python
from WutheringWavesUID.wutheringwaves_payment import background_manager

# 獲取用戶背景路徑
bg_path = background_manager.get_background_path(user_id)

# 檢查是否有自定義背景
has_custom = background_manager.has_custom_background(user_id)

# 獲取背景信息
bg_info = background_manager.get_background_info(user_id)
```

### 在面板生成中使用

```python
from WutheringWavesUID.wutheringwaves_payment import background_manager

def create_panel_with_background(user_id: str):
    # 獲取背景圖片路徑
    bg_path = background_manager.get_background_path(user_id)
    
    # 加載背景圖片
    background = Image.open(bg_path)
    
    # 創建面板
    panel = Image.new('RGBA', background.size, (0, 0, 0, 0))
    panel.paste(background, (0, 0))
    
    # 添加其他面板元素...
    
    return panel
```

## 權限檢查

只有Premium會員才能使用自定義背景功能：

```python
from WutheringWavesUID.wutheringwaves_payment import payment_manager

if payment_manager.is_premium_user(user_id):
    # 用戶有權限使用自定義背景
    pass
else:
    # 用戶沒有權限，使用默認背景
    pass
```

## 錯誤處理

系統會自動處理以下情況：

1. **文件不存在** - 自動回退到默認背景
2. **文件格式不支持** - 提示用戶使用支持的格式
3. **文件過大** - 提示用戶壓縮圖片
4. **URL無效** - 提示用戶檢查URL格式
5. **網絡錯誤** - 提示用戶稍後重試

## 安全考慮

- 所有上傳的圖片都會進行格式驗證
- 文件大小限制防止濫用
- URL驗證確保安全性
- 用戶只能管理自己的背景文件

## 常見問題

### Q: 為什麼我的背景沒有生效？
A: 請檢查：
1. 您是否為Premium會員
2. 圖片格式是否支持
3. 文件大小是否超過限制
4. 使用 `查看背景信息` 檢查設置狀態

### Q: 可以設置動態背景嗎？
A: 目前支持靜態圖片，動態背景（GIF）會顯示為靜態幀。

### Q: 背景圖片會影響性能嗎？
A: 系統會自動優化圖片，但建議使用適當大小的圖片以獲得最佳性能。

### Q: 如何恢復默認背景？
A: 使用 `重置背景` 指令即可恢復默認背景。

## 更新日誌

- **v1.0.0** - 初始版本，支持圖片上傳和URL設置
- 支持PNG、JPG、GIF、BMP格式
- 文件大小限制10MB
- 自動文件管理和驗證

## 技術支持

如果您在使用過程中遇到問題，請：
1. 檢查您的Premium會員狀態
2. 確認圖片格式和大小
3. 查看系統日誌獲取詳細錯誤信息
4. 聯繫管理員獲取幫助
