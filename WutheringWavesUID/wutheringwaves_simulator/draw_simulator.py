"""模擬抽卡繪圖"""

import os
from pathlib import Path
from typing import Dict, List, Optional

from gsuid_core.logger import logger
from PIL import Image, ImageDraw, ImageFont
from gsuid_core.utils.image.convert import convert_img

from ..utils.ascension.char import get_char_id
from ..utils.ascension.weapon import get_weapon_id
from ..utils.resource.RESOURCE_PATH import WEAPON_PATH, ROLE_PILE_PATH
from ..utils.image import GOLD, get_waves_bg, get_role_pile, get_square_weapon
from ..utils.fonts.waves_fonts import (
    waves_font_18,
    waves_font_20,
    waves_font_24,
)
from ..utils.name_convert import (
    alias_to_char_name,
    alias_to_weapon_name,
    char_name_to_char_id,
)

TEXT_PATH = Path(__file__).parent / "texture2d"


async def get_item_image(
    name: str, star: int, gacha_type: str = "role"
) -> Optional[Image.Image]:
    """
    獲取角色立繪或武器圖片

    Args:
        name: 名稱
        star: 星級
        gacha_type: 抽卡類型 (role/weapon)

    Returns:
        圖片對象
    """
    try:
        # 如果是三星，通常是武器
        if star == 3:
            gacha_type = "weapon"

        # 先嘗試作為角色處理（如果 gacha_type 是 role）
        if gacha_type == "role":
            char_name = alias_to_char_name(name)
            char_id = char_name_to_char_id(char_name) or get_char_id(char_name)

            if char_id:
                try:
                    # 嘗試獲取角色立繪
                    _, pile = await get_role_pile(char_id)
                    # 檢查文件是否真的存在
                    pile_file = ROLE_PILE_PATH / f"role_pile_{char_id}.png"
                    if pile_file.exists():
                        return pile
                    else:
                        logger.debug(
                            f"角色立繪文件不存在: {pile_file}，嘗試作為武器處理"
                        )
                except Exception as e:
                    logger.debug(f"獲取角色立繪失敗 {name}: {e}，嘗試作為武器處理")

            # 如果角色處理失敗，嘗試作為武器
            logger.debug(f"{name} 未找到角色ID或立繪，嘗試作為武器處理")
            weapon_name = alias_to_weapon_name(name)
            weapon_id = get_weapon_id(weapon_name)
            if weapon_id:
                return await get_square_weapon(weapon_id)

        # 武器處理
        weapon_name = alias_to_weapon_name(name)
        weapon_id = get_weapon_id(weapon_name)
        if weapon_id:
            return await get_square_weapon(weapon_id)

        # 都找不到，返回 None
        logger.warning(f"未找到 {name} 的角色或武器ID")
        return None

    except Exception as e:
        logger.error(f"獲取圖片失敗 {name}: {e}")
        return None


def load_card_bg(star: int) -> Optional[Image.Image]:
    """載入卡片背景"""
    bg_file = TEXT_PATH / f"bg-card-{star}.png"
    if bg_file.exists():
        return Image.open(bg_file).convert("RGBA")
    return None


def load_card_cover(star: int) -> Optional[Image.Image]:
    """載入卡片覆蓋層"""
    cover_file = TEXT_PATH / f"tb-card-{star}.png"
    if cover_file.exists():
        return Image.open(cover_file).convert("RGBA")
    return None


async def draw_simulator_card(
    gacha_result: Dict, user_name: str = "未知用戶"
) -> Optional[bytes]:
    """
    繪製模擬抽卡結果卡片

    Args:
        gacha_result: 抽卡結果字典，包含 gacha_list, pool_name, times, type
        user_name: 用戶名稱

    Returns:
        圖片 bytes
    """
    try:
        gacha_list = gacha_result.get("gacha_list", [])
        pool_name = gacha_result.get("pool_name", "未知池子")
        times = gacha_result.get("times", 0)
        gacha_type = gacha_result.get("type", "role")

        if not gacha_list:
            return "抽卡結果為空"

        # 創建背景
        background_file = TEXT_PATH / "background.png"
        if background_file.exists():
            bg = Image.open(background_file).convert("RGB")
            bg = bg.resize((1920, 1080), Image.Resampling.LANCZOS)
        else:
            try:
                bg = await get_waves_bg(1920, 1080, "simulator")
            except Exception:
                bg = None

        if bg is None:
            bg = Image.new("RGB", (1920, 1080), (20, 20, 30))

        # 繪製標題信息
        draw = ImageDraw.Draw(bg)

        # 用戶名稱和池子名稱
        info_text = f"{user_name}\n{pool_name}\n距離五星: {times}抽"
        try:
            font = waves_font_24
            # 計算文字位置（右上角）
            bbox = draw.textbbox((0, 0), info_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = 1920 - text_width - 40
            y = 40

            # 繪製半透明背景
            padding = 20
            info_bg = Image.new(
                "RGBA",
                (text_width + padding * 2, text_height + padding * 2),
                (0, 0, 0, 180),
            )
            bg.paste(info_bg, (x - padding, y - padding), info_bg)

            # 繪製文字
            draw.text((x, y), info_text, font=font, fill=(255, 255, 255, 255))
        except Exception as e:
            logger.warning(f"繪製標題失敗: {e}")

        # 繪製十連結果（5x2 網格）
        card_width = 265
        card_height = 400
        card_spacing = 15
        start_x = 265
        start_y = 135

        for idx, gacha_item in enumerate(gacha_list):
            row = idx // 5
            col = idx % 5

            x = start_x + col * (card_width + card_spacing)
            y = start_y + row * (card_height + card_spacing)

            # 載入卡片背景
            card_bg_img = load_card_bg(gacha_item["star"])
            if card_bg_img:
                card_bg = card_bg_img.resize(
                    (card_width, card_height), Image.Resampling.LANCZOS
                ).convert("RGBA")
            else:
                # 如果沒有背景圖，創建純色背景
                card_bg = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 200))

            # 獲取角色立繪或武器圖片
            item_image = await get_item_image(
                gacha_item["name"], gacha_item["star"], gacha_type
            )
            if item_image:
                # 縮放圖片適應卡片
                item_image = item_image.convert("RGBA")
                # 保持寬高比，縮放到卡片寬度
                img_ratio = item_image.size[0] / item_image.size[1]
                target_height = int(card_width / img_ratio)
                if target_height > card_height * 0.9:
                    target_height = int(card_height * 0.9)
                    target_width = int(target_height * img_ratio)
                else:
                    target_width = card_width

                item_image = item_image.resize(
                    (target_width, target_height), Image.Resampling.LANCZOS
                )

                # 貼到卡片底部
                paste_x = (card_width - target_width) // 2
                paste_y = card_height - target_height - 50  # 底部留空間給文字
                card_bg.paste(item_image, (paste_x, paste_y), item_image)

            # 載入覆蓋層
            cover_img = load_card_cover(gacha_item["star"])
            if cover_img:
                cover_img = cover_img.resize(
                    (card_width, card_height), Image.Resampling.LANCZOS
                )
                card_bg.paste(cover_img, (0, 0), cover_img)

            # 繪製名稱和星級（可選，因為卡片覆蓋層可能已經有星級標示）
            # 如果需要顯示名稱，可以在這裡添加

            # 將卡片貼到背景上
            bg.paste(card_bg, (x, y), card_bg)

        # 轉換為 bytes
        return await convert_img(bg)

    except Exception as e:
        logger.error(f"繪製模擬抽卡卡片失敗: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return f"繪製失敗: {e}"
