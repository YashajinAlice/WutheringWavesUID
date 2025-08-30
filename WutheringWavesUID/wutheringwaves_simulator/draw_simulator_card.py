import asyncio
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont
from gsuid_core.utils.image.convert import convert_img

from ..utils.name_convert import alias_to_char_name
from ..utils.fonts.waves_fonts import (
    waves_font_20,
    waves_font_24,
    waves_font_30,
    waves_font_36,
)
from ..utils.image import (
    TEXT_PATH,
    get_waves_bg,
    get_square_avatar,
    get_square_weapon,
    cropped_square_avatar,
)


class SimulatorCardDrawer:
    def __init__(self):
        # 載入抽卡記錄使用的背景圖片
        try:
            self.item_fg = Image.open(TEXT_PATH / "char_bg.png")
            self.up_icon = Image.open(TEXT_PATH / "up_tag.png")
            self.up_icon = self.up_icon.resize((68, 52))
        except:
            # 如果文件不存在，創建簡單的背景
            self.item_fg = Image.new("RGBA", (167, 170), (255, 255, 255, 0))
            self.up_icon = Image.new("RGBA", (68, 52), (255, 0, 0, 255))

    async def draw_simulator_card(
        self,
        gacha_results: List[Dict],
        pool_name: str,
        user_name: str,
        five_star_time: int,
    ) -> bytes:
        """繪製十連抽卡結果卡片"""

        # 計算卡片高度
        item_height = 170
        items_per_row = 5
        rows = (len(gacha_results) + items_per_row - 1) // items_per_row
        card_height = 200 + rows * item_height + 50

        # 創建背景
        card_width = 1000
        card_img = get_waves_bg(card_width, card_height)
        card_draw = ImageDraw.Draw(card_img)

        # 繪製標題
        card_draw.text((500, 50), f"{pool_name}模拟抽卡", "white", waves_font_36, "mm")
        card_draw.text((500, 100), f"用户: {user_name}", "white", waves_font_24, "mm")
        card_draw.text(
            (500, 140),
            f"距离五星保底: {five_star_time}/90",
            "white",
            waves_font_20,
            "mm",
        )

        # 繪製抽卡結果
        start_x = 50
        start_y = 200
        item_width = 167

        for i, result in enumerate(gacha_results):
            row = i // items_per_row
            col = i % items_per_row

            x = start_x + col * item_width
            y = start_y + row * item_height

            item_img = await self._create_gacha_item(result)
            card_img.paste(item_img, (x, y), item_img)

        # 轉換為bytes
        return await convert_img(card_img)

    async def draw_single_simulator_card(
        self, gacha_result: Dict, pool_name: str, user_name: str, five_star_time: int
    ) -> bytes:
        """繪製單抽結果卡片"""

        # 創建背景
        card_width = 800
        card_height = 600
        card_img = get_waves_bg(card_width, card_height)
        card_draw = ImageDraw.Draw(card_img)

        # 繪製標題
        card_draw.text((400, 50), f"{pool_name}单抽模拟", "white", waves_font_36, "mm")
        card_draw.text((400, 100), f"用户: {user_name}", "white", waves_font_24, "mm")
        card_draw.text(
            (400, 140),
            f"距离五星保底: {five_star_time}/90",
            "white",
            waves_font_20,
            "mm",
        )

        # 繪製單個抽卡結果
        item_img = await self._create_gacha_item(gacha_result, is_single=True)
        card_img.paste(item_img, (316, 200), item_img)

        # 轉換為bytes
        return await convert_img(card_img)

    async def _create_gacha_item(
        self, result: Dict, is_single: bool = False
    ) -> Image.Image:
        """創建單個抽卡項目"""
        star = result["star"]
        name = result["name"]
        item_id = result["id"]
        is_up = result.get("is_up", False)

        # 創建背景
        item_bg = Image.new("RGBA", (167, 170))
        item_fg_cp = self.item_fg.copy()
        item_bg.paste(item_fg_cp, (0, 0), item_fg_cp)

        # 創建內容區域
        item_temp = Image.new("RGBA", (167, 170))

        # 獲取頭像/武器圖片
        try:
            # 根據星級和ID判斷是角色還是武器
            if star == 5 and item_id < 2000:  # 五星角色
                item_icon = await get_square_avatar(str(item_id))
                item_icon = await cropped_square_avatar(item_icon, 130)
            elif star == 4 and item_id < 2000:  # 四星角色
                item_icon = await get_square_avatar(str(item_id))
                item_icon = await cropped_square_avatar(item_icon, 130)
            else:  # 武器或三星角色
                if item_id >= 2000:  # 武器ID
                    item_icon = await get_square_weapon(str(item_id))
                    item_icon = item_icon.resize((130, 130)).convert("RGBA")
                else:  # 三星角色
                    item_icon = await get_square_avatar(str(item_id))
                    item_icon = await cropped_square_avatar(item_icon, 130)

            item_temp.paste(item_icon, (22, 0), item_icon)
        except:
            # 如果獲取失敗，創建默認圖片
            if star == 5:
                bg_color = (255, 215, 0)  # 金色
            elif star == 4:
                bg_color = (138, 43, 226)  # 紫色
            else:
                bg_color = (100, 149, 237)  # 藍色

            default_icon = Image.new("RGBA", (130, 130), bg_color)
            item_temp.paste(default_icon, (22, 0), default_icon)

        # 合成圖片
        item_bg.paste(item_temp, (-2, -2), item_temp)

        # 添加UP標記
        if is_up:
            item_bg.paste(self.up_icon, (70, 5), self.up_icon)

        # 添加星級標記
        star_color = "white"
        if star == 5:
            star_color = (255, 215, 0)  # 金色
        elif star == 4:
            star_color = (138, 43, 226)  # 紫色
        else:
            star_color = (100, 149, 237)  # 藍色

        # 在右下角添加星級
        star_draw = ImageDraw.Draw(item_bg)
        star_draw.text((140, 140), f"{star}★", star_color, waves_font_20, "mm")

        # 添加名稱
        name_bg = Image.new("RGBA", (167, 30), (0, 0, 0, 180))
        name_draw = ImageDraw.Draw(name_bg)
        name_draw.text((83, 15), name[:6], "white", waves_font_20, "mm")
        item_bg.paste(name_bg, (0, 140), name_bg)

        return item_bg
