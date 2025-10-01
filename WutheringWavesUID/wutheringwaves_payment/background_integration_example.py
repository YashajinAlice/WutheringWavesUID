"""
背景集成示例 - 展示如何在現有代碼中使用自定義背景
"""

from pathlib import Path

from PIL import Image
from gsuid_core.logger import logger

from .payment_manager import payment_manager
from .background_manager import background_manager


def get_background_for_user(user_id: str) -> Path:
    """
    為用戶獲取背景圖片路徑

    Args:
        user_id: 用戶ID

    Returns:
        背景圖片路徑
    """
    return background_manager.get_background_path(user_id)


def create_panel_with_custom_background(user_id: str, panel_data: dict) -> Image.Image:
    """
    使用自定義背景創建面板（示例函數）

    Args:
        user_id: 用戶ID
        panel_data: 面板數據

    Returns:
        生成的面板圖片
    """
    try:
        # 獲取背景圖片路徑
        bg_path = get_background_for_user(user_id)

        # 檢查背景文件是否存在
        if not bg_path.exists():
            logger.warning(f"[背景集成] 背景文件不存在: {bg_path}")
            # 使用默認背景
            bg_path = background_manager.default_bg_path

        # 加載背景圖片
        background = Image.open(bg_path)

        # 創建面板（這裡是示例，實際實現會根據具體需求）
        panel = Image.new("RGBA", background.size, (0, 0, 0, 0))

        # 將背景作為底層
        panel.paste(background, (0, 0))

        # 在這裡添加其他面板元素（角色信息、數據等）
        # 例如：
        # - 添加角色頭像
        # - 添加角色信息文字
        # - 添加數據圖表
        # - 添加裝飾元素

        logger.info(f"[背景集成] 為用戶 {user_id} 創建面板，使用背景: {bg_path.name}")

        return panel

    except Exception as e:
        logger.error(f"[背景集成] 創建面板失敗: {e}")
        # 返回默認面板
        return create_default_panel()


def create_default_panel() -> Image.Image:
    """
    創建默認面板（示例函數）

    Returns:
        默認面板圖片
    """
    try:
        bg_path = background_manager.default_bg_path
        if bg_path.exists():
            return Image.open(bg_path)
        else:
            # 如果連默認背景都沒有，創建一個純色背景
            return Image.new("RGB", (800, 600), (50, 50, 50))
    except Exception as e:
        logger.error(f"[背景集成] 創建默認面板失敗: {e}")
        return Image.new("RGB", (800, 600), (50, 50, 50))


def check_user_background_permission(user_id: str) -> bool:
    """
    檢查用戶是否有權限使用自定義背景

    Args:
        user_id: 用戶ID

    Returns:
            是否有權限
    """
    return payment_manager.is_premium_user(user_id)


def get_background_info_for_user(user_id: str) -> dict:
    """
    獲取用戶背景信息

    Args:
        user_id: 用戶ID

    Returns:
        背景信息字典
    """
    return background_manager.get_background_info(user_id)


# 使用示例
def example_usage():
    """
    使用示例
    """
    user_id = "123456789"

    # 檢查用戶權限
    if check_user_background_permission(user_id):
        print(f"用戶 {user_id} 有權限使用自定義背景")

        # 獲取背景信息
        bg_info = get_background_info_for_user(user_id)
        print(f"背景信息: {bg_info}")

        # 創建面板
        panel = create_panel_with_custom_background(user_id, {})
        print(f"面板創建成功，尺寸: {panel.size}")

    else:
        print(f"用戶 {user_id} 沒有權限使用自定義背景，使用默認背景")

        # 創建默認面板
        panel = create_default_panel()
        print(f"默認面板創建成功，尺寸: {panel.size}")


if __name__ == "__main__":
    example_usage()
