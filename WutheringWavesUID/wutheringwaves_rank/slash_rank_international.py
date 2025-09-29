import re
import copy
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from gsuid_core.bot import Bot
from PIL import Image, ImageDraw
from gsuid_core.models import Event
from gsuid_core.logger import logger
from gsuid_core.utils.image.convert import convert_img
from gsuid_core.utils.image.image_tools import crop_center_img

from ..utils.cache import TimedCache
from ..utils.util import get_version
from ..utils.database.models import WavesBind
from ..utils.ascension.char import get_char_model
from ..utils.resource.RESOURCE_PATH import SLASH_PATH
from ..wutheringwaves_config import WutheringWavesConfig
from ..wutheringwaves_abyss.draw_slash_card import COLOR_QUALITY
from ..utils.fonts.waves_fonts import (
    waves_font_12,
    waves_font_18,
    waves_font_20,
    waves_font_34,
    waves_font_44,
    waves_font_58,
)
from ..utils.image import (
    RED,
    AMBER,
    WAVES_VOID,
    WAVES_MOLTEN,
    WAVES_SIERRA,
    WAVES_MOONLIT,
    AVATAR_GETTERS,
    WAVES_FREEZING,
    WAVES_LINGERING,
    get_ICON,
    add_footer,
    get_waves_bg,
    get_qq_avatar,
    get_square_avatar,
    pic_download_from_url,
)

TEXT_PATH = Path(__file__).parent / "texture2d"
avatar_mask = Image.open(TEXT_PATH / "avatar_mask.png")
default_avatar_char_id = "1505"
pic_cache = TimedCache(600, 200)

BOT_COLOR = [
    WAVES_MOLTEN,
    AMBER,
    WAVES_VOID,
    WAVES_SIERRA,
    WAVES_FREEZING,
    WAVES_LINGERING,
    WAVES_MOONLIT,
]

from ..utils.api.international_api import (
    get_international_slash_rank,
    get_international_slash_record,
)


def get_score_color(score: int):
    """根據分數獲取顏色"""
    if score >= 30000:
        return (255, 0, 0)
    elif score >= 25000:
        return (234, 183, 4)
    elif score >= 20000:
        return (185, 106, 217)
    elif score >= 15000:
        return (22, 145, 121)
    elif score >= 10000:
        return (53, 152, 219)
    else:
        return (255, 255, 255)


async def draw_international_slash_rank_card(bot: Bot, ev: Event, limit: int = 20):
    """绘制国际服无尽排行卡片"""
    try:
        # 获取排行数据
        rank_data = await get_international_slash_rank(limit)

        if not rank_data:
            return "获取国际服无尽排行数据失败，请检查API服务是否正常运行"

        # API返回的数据结构是 {"rank_list": [...], "total_count": ...}
        rank_list = rank_data.get("rank_list", [])

        # 添加調試信息
        logger.info(f"獲取到排行數據: 總數={len(rank_list)}, 限制={limit}")
        for i, record in enumerate(rank_list):
            logger.info(
                f"  第{i+1}名: UID={record.get('uid')}, 分數={record.get('total_score')}"
            )

        if not rank_list:
            # 添加調試信息
            return f"暂无国际服无尽排行数据 (数据结构: {type(rank_data)}, 键: {list(rank_data.keys()) if isinstance(rank_data, dict) else 'N/A'})"
    except Exception as e:
        logger.exception(f"获取排行数据时发生错误: {e}")
        return f"获取排行数据时发生错误: {str(e)}"

    # 设置图像尺寸
    width = 1300
    item_spacing = 120
    header_height = 510
    footer_height = 50
    char_list_len = len(rank_list)

    # 计算所需的总高度
    total_height = header_height + item_spacing * char_list_len + footer_height

    # 创建带背景的画布
    card_img = get_waves_bg(width, total_height, "bg9")

    # 标题背景
    title_bg = Image.open(TEXT_PATH / "slash.jpg")
    title_bg = title_bg.crop((0, 0, width, 500))

    # 图标
    icon = get_ICON()
    icon = icon.resize((128, 128), Image.Resampling.LANCZOS)
    title_bg.paste(icon, (60, 240), icon)

    # 标题文字
    title_text = "#国际服无尽总排行"
    title_bg_draw = ImageDraw.Draw(title_bg)
    title_bg_draw.text((220, 290), title_text, "white", waves_font_58, "lm")

    # 遮罩处理
    char_mask = Image.open(TEXT_PATH / "char_mask.png").convert("RGBA")
    char_mask = char_mask.resize((width, char_mask.height * width // char_mask.width), Image.Resampling.LANCZOS)
    char_mask = char_mask.crop((0, char_mask.height - 500, width, char_mask.height))
    char_mask_temp = Image.new("RGBA", char_mask.size, (0, 0, 0, 0))
    char_mask_temp.paste(title_bg, (0, 0), char_mask)

    card_img.paste(char_mask_temp, (0, 0), char_mask_temp)

    # 获取用户头像
    tasks = [
        get_avatar(rank.get("discord_user_id") or rank.get("uid"), ev)
        for rank in rank_list
    ]
    results = await asyncio.gather(*tasks)

    # 获取角色信息
    bot_color_map = {}
    bot_color = copy.deepcopy(BOT_COLOR)

    for rank_index, (rank_data, role_avatar) in enumerate(zip(rank_list, results)):
        logger.info(f"正在繪製第 {rank_index + 1} 個項目: UID={rank_data.get('uid')}")
        role_bg = Image.open(TEXT_PATH / "bar1.png")
        role_bg.paste(role_avatar, (100, 0), role_avatar)
        role_bg_draw = ImageDraw.Draw(role_bg)

        # 添加排名显示
        rank_id = rank_data.get("rank", rank_index + 1)
        rank_color = (54, 54, 54)
        if rank_id == 1:
            rank_color = (255, 0, 0)
        elif rank_id == 2:
            rank_color = (255, 180, 0)
        elif rank_id == 3:
            rank_color = (185, 106, 217)

        def draw_rank_id(rank_id, size=(50, 50), draw=(24, 24), dest=(40, 30)):
            info_rank = Image.new("RGBA", size, color=(255, 255, 255, 0))
            rank_draw = ImageDraw.Draw(info_rank)
            rank_draw.rounded_rectangle(
                [0, 0, size[0], size[1]], radius=8, fill=rank_color + (int(0.9 * 255),)
            )
            rank_draw.text(draw, f"{rank_id}", "white", waves_font_34, "mm")
            role_bg.alpha_composite(info_rank, dest)

        if rank_id > 999:
            draw_rank_id("999+", size=(100, 50), draw=(50, 24), dest=(10, 30))
        elif rank_id > 99:
            draw_rank_id(rank_id, size=(75, 50), draw=(37, 24), dest=(25, 30))
        else:
            draw_rank_id(rank_id, size=(50, 50), draw=(24, 24), dest=(40, 30))

        # 名字
        kuro_name = rank_data.get("kuro_name", "未知")
        role_bg_draw.text((210, 75), f"{kuro_name}", "white", waves_font_20, "lm")

        # UID
        uid = rank_data.get("uid", "")
        uid_color = "white"
        role_bg_draw.text((350, 40), f"UID: {uid}", uid_color, waves_font_20, "lm")

        # Bot主人名稱
        alias_name = rank_data.get("alias_name", "")
        if alias_name:
            # 清理特殊字符，只保留基本ASCII和中文字符
            def clean_text(text):
                if not text:
                    return ""
                # 只保留字母、數字、中文、空格和基本標點
                import re

                # 更嚴格的過濾，移除所有特殊Unicode字符
                cleaned = re.sub(r"[^\w\s\u4e00-\u9fff\-_\.]", "", text)
                # 進一步清理，移除所有非ASCII字母（保留中文）
                cleaned = re.sub(r"[^\u4e00-\u9fff\s\-_\.]", "", cleaned)
                # 移除多餘的空格
                cleaned = " ".join(cleaned.split())
                return cleaned.strip()

            clean_alias = clean_text(alias_name)
            if clean_alias:  # 只有清理後還有內容才顯示
                color = (54, 54, 54)
                if alias_name in bot_color_map:
                    color = bot_color_map[alias_name]
                elif bot_color:
                    color = bot_color.pop(0)
                    bot_color_map[alias_name] = color

                info_block = Image.new("RGBA", (200, 30), color=(255, 255, 255, 0))
                info_block_draw = ImageDraw.Draw(info_block)
                info_block_draw.rounded_rectangle(
                    [0, 0, 200, 30], radius=6, fill=color + (int(0.6 * 255),)
                )
                info_block_draw.text(
                    (100, 15), f"Bot: {clean_alias}", "white", waves_font_18, "mm"
                )
                role_bg.alpha_composite(info_block, (350, 66))

        # 平台信息 - 已移除顯示

        # 总分数
        total_score = rank_data.get("total_score", 0)
        role_bg_draw.text(
            (1140, 55),
            f"{total_score}",
            get_score_color(total_score),
            waves_font_44,
            "mm",
        )

        # 处理无尽排行数据
        slash_data = rank_data.get("slash_data", {})
        half_list = slash_data.get("half_list", [])

        for half_index, slash_half in enumerate(half_list):
            char_ids = slash_half.get("char_ids", [])
            score = slash_half.get("score", 0)

            # 显示角色
            for role_index, char_id in enumerate(char_ids):
                char_model = get_char_model(char_id)
                if char_model is None:
                    continue
                char_avatar = await get_square_avatar(char_id)
                char_avatar = char_avatar.resize((45, 45), Image.Resampling.LANCZOS)

                role_bg.alpha_composite(
                    char_avatar, (570 + half_index * 250 + role_index * 50, 20)
                )

            # Buff显示
            buff_icon = slash_half.get("buff_icon", "")
            buff_name = slash_half.get("buff_name", "")
            buff_quality = slash_half.get("buff_quality", 5)

            if buff_icon:
                buff_bg = Image.new("RGBA", (50, 50), (255, 255, 255, 0))
                buff_bg_draw = ImageDraw.Draw(buff_bg)
                buff_bg_draw.rounded_rectangle(
                    [0, 0, 50, 50],
                    radius=5,
                    fill=(0, 0, 0, int(0.8 * 255)),
                )
                buff_color = COLOR_QUALITY.get(buff_quality, (255, 255, 255))
                buff_bg_draw.rectangle(
                    [0, 45, 50, 50],
                    fill=buff_color,
                )
                try:
                    buff_pic = await pic_download_from_url(SLASH_PATH, buff_icon)
                    buff_pic = buff_pic.resize((50, 50), Image.Resampling.LANCZOS)
                    buff_bg.paste(buff_pic, (0, 0), buff_pic)
                except:
                    # 如果图标下载失败，显示文字
                    buff_bg_draw.text(
                        (25, 25), buff_name[:2], "white", waves_font_12, "mm"
                    )

                role_bg.alpha_composite(buff_bg, (720 + half_index * 250, 15))

            # 分数
            role_bg_draw.text(
                (670 + half_index * 250, 80),
                f"{score}",
                get_score_color(score),
                waves_font_20,
                "mm",
            )

        card_img.paste(role_bg, (0, 510 + rank_index * item_spacing), role_bg)

    card_img = add_footer(card_img)
    card_img = await convert_img(card_img)
    return card_img


async def get_avatar(qid: Optional[str], ev: Event = None) -> Image.Image:
    """获取用户头像"""
    try:
        # 如果有Event对象，尝试使用对应的bot头像获取函数
        if ev and ev.bot_id:
            get_bot_avatar = AVATAR_GETTERS.get(ev.bot_id)
            if get_bot_avatar:
                if WutheringWavesConfig.get_config("QQPicCache").data:
                    pic = pic_cache.get(qid)
                    if not pic:
                        pic = await get_bot_avatar(qid, size=100)
                        pic_cache.set(qid, pic)
                else:
                    pic = await get_bot_avatar(qid, size=100)
                    pic_cache.set(qid, pic)

                pic_temp = crop_center_img(pic, 120, 120)
                img = Image.new("RGBA", (180, 180))
                avatar_mask_temp = avatar_mask.copy()
                mask_pic_temp = avatar_mask_temp.resize((120, 120), Image.Resampling.LANCZOS)
                img.paste(pic_temp, (0, -5), mask_pic_temp)
                return img

        # 回退到原来的逻辑
        if qid and qid.isdigit():
            if WutheringWavesConfig.get_config("QQPicCache").data:
                pic = pic_cache.get(qid)
                if not pic:
                    pic = await get_qq_avatar(qid, size=100)
                    pic_cache.set(qid, pic)
            else:
                pic = await get_qq_avatar(qid, size=100)
                pic_cache.set(qid, pic)
            pic_temp = crop_center_img(pic, 120, 120)

            img = Image.new("RGBA", (180, 180))
            avatar_mask_temp = avatar_mask.copy()
            mask_pic_temp = avatar_mask_temp.resize((120, 120), Image.Resampling.LANCZOS)
            img.paste(pic_temp, (0, -5), mask_pic_temp)
        else:
            pic = await get_square_avatar(default_avatar_char_id)

            pic_temp = Image.new("RGBA", pic.size)
            pic_temp.paste(pic.resize((160, 160), Image.Resampling.LANCZOS), (10, 10))
            pic_temp = pic_temp.resize((160, 160), Image.Resampling.LANCZOS)

            avatar_mask_temp = avatar_mask.copy()
            mask_pic_temp = Image.new("RGBA", avatar_mask_temp.size)
            mask_pic_temp.paste(avatar_mask_temp, (-20, -45), avatar_mask_temp)
            mask_pic_temp = mask_pic_temp.resize((160, 160), Image.Resampling.LANCZOS)

            img = Image.new("RGBA", (180, 180))
            img.paste(pic_temp, (0, 0), mask_pic_temp)

        return img
    except Exception as e:
        logger.warning(f"头像获取失败: {e}，使用默认头像")
        # 使用默认角色头像
        pic = await get_square_avatar(default_avatar_char_id)
        pic_temp = Image.new("RGBA", pic.size)
        pic_temp.paste(pic.resize((160, 160), Image.Resampling.LANCZOS), (10, 10))
        pic_temp = pic_temp.resize((160, 160), Image.Resampling.LANCZOS)

        avatar_mask_temp = avatar_mask.copy()
        mask_pic_temp = Image.new("RGBA", avatar_mask_temp.size)
        mask_pic_temp.paste(avatar_mask_temp, (-20, -45), avatar_mask_temp)
        mask_pic_temp = mask_pic_temp.resize((160, 160), Image.Resampling.LANCZOS)

        img = Image.new("RGBA", (180, 180))
        img.paste(pic_temp, (0, 0), mask_pic_temp)
        return img
