"""
增強PCAP分析結果繪製
基於原始系統的繪製邏輯，但使用增強數據
"""

import time
from pathlib import Path
from typing import List, Union

from gsuid_core.bot import Bot
from PIL import Image, ImageDraw
from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img

from ..utils.button import WavesButton
from ..utils.database.models import WavesBind
from ..utils.imagetool import draw_pic_with_ring
from ..utils.api.model import RoleDetailData, AccountBaseInfo
from ..utils.expression_ctx import WavesCharRank, get_waves_char_rank
from .enhanced_pcap_processor import get_enhanced_data, get_enhanced_summary
from ..utils.fonts.waves_fonts import (
    waves_font_25,
    waves_font_30,
    waves_font_40,
    waves_font_60,
)
from ..utils.image import (
    RED,
    GOLD,
    GREY,
    add_footer,
    get_star_bg,
    get_square_avatar,
    draw_text_with_shadow,
    get_random_share_bg_path,
)

TEXT_PATH = Path(__file__).parent / "texture2d"


async def draw_enhanced_pcap_analysis_img(
    bot: Bot,
    ev: Event,
    user_id: str,
    uid: str,
    buttons: List[WavesButton],
) -> Union[str, bytes]:
    """繪製增強PCAP分析結果"""

    # 檢查是否有增強數據
    enhanced_data = await get_enhanced_data(uid)
    if not enhanced_data:
        return (
            "❌ 尚無增強PCAP分析數據\n\n"
            "📋 請先上傳PCAP文件進行增強分析：\n"
            "1. 發送包含 .pcap 或 .pcapng 文件的消息\n"
            "2. 系統會自動使用增強分析器處理\n"
            "3. 完成後使用 '增強面板' 查看結果"
        )

    # 獲取摘要信息
    summary = await get_enhanced_summary(uid)

    try:
        # 轉換為標準格式以便繪製
        role_detail_list = []
        for role_data in enhanced_data:
            role_detail_list.append(RoleDetailData(**role_data))

        # 獲取用戶基本信息（如果可用）
        account_info = None
        try:
            from ..utils.waves_api import waves_api

            account_result = await waves_api.get_base_info(uid, None)
            if account_result.success:
                account_info = AccountBaseInfo.model_validate(account_result.data)
        except:
            # 創建默認賬戶信息
            account_info = AccountBaseInfo(
                id=uid, name="增強分析用戶", level=1, is_full=False
            )

        # 計算圖片尺寸
        role_len = len(role_detail_list)
        role_high = role_len // 6 + (0 if role_len % 6 == 0 else 1)
        height = 470 + 50 + role_high * 330
        width = 2000

        # 創建圖片
        img = Image.new("RGBA", (width, height))

        # 背景
        bg_img = await get_random_share_bg_path()
        if bg_img:
            bg = Image.open(bg_img).convert("RGBA")
            bg = bg.resize((width, height))
            img.alpha_composite(bg, (0, 0))

        # 標題區域
        title_color = GOLD
        shadow_title = "增強PCAP分析!"

        # 繪製標題
        draw = ImageDraw.Draw(img)
        draw_text_with_shadow(
            draw, (width // 2, 50), shadow_title, waves_font_60, title_color, "mm"
        )

        # 統計信息
        if summary and "stats" in summary:
            stats = summary["stats"]
            stats_text = (
                f"共分析 {stats['role_count']} 個角色 | "
                f"聲骸成功率: {stats['phantom_success_rate']:.1f}% | "
                f"屬性成功率: {stats['property_success_rate']:.1f}%"
            )
            draw_text_with_shadow(
                draw, (width // 2, 120), stats_text, waves_font_30, GOLD, "mm"
            )

        # 繪製角色卡片
        rIndex = 0
        for role_detail in role_detail_list:
            # 轉換為排名格式
            char_rank = await get_waves_char_rank(role_detail)

            # 繪製角色卡片
            pic = await draw_enhanced_char_pic(char_rank, True)
            img.alpha_composite(
                pic, (80 + 300 * (rIndex % 6), 470 + (rIndex // 6) * 330)
            )

            # 添加按鈕
            if rIndex < 5:
                role_name = role_detail.role.roleName
                button = WavesButton(role_name, f"增強{role_name}面板")
                buttons.append(button)

            rIndex += 1

        # 用戶信息區域
        if account_info:
            # 基礎信息背景
            info_bg = Image.new("RGBA", (400, 150), (0, 0, 0, 128))
            info_draw = ImageDraw.Draw(info_bg)

            info_draw.text(
                (20, 30), f"{account_info.name[:10]}", "white", waves_font_30, "lm"
            )
            info_draw.text(
                (20, 70), f"特征码: {account_info.id}", GOLD, waves_font_25, "lm"
            )
            info_draw.text((20, 100), "增強PCAP分析", GOLD, waves_font_25, "lm")

            img.paste(info_bg, (15, 20), info_bg)

        # 添加通用按鈕
        buttons.append(WavesButton("重新分析", "增強PCAP分析"))
        buttons.append(WavesButton("幫助", "增強PCAP分析"))

        # 添加頁腳
        img = add_footer(img)

        return await convert_img(img)

    except Exception as e:
        from gsuid_core.logger import logger

        logger.exception(f"繪製增強PCAP分析圖片失敗: {uid}")
        return f"❌ 繪製分析結果失敗: {str(e)}"


async def draw_enhanced_char_pic(
    char_rank: WavesCharRank, is_updated: bool = True
) -> Image.Image:
    """繪製增強角色卡片"""
    try:
        # 基礎卡片尺寸
        width, height = 280, 320

        # 創建卡片
        card = Image.new("RGBA", (width, height))

        # 背景
        star_bg = get_star_bg(char_rank.starLevel)
        if star_bg:
            star_bg = star_bg.resize((width, height))
            card.alpha_composite(star_bg, (0, 0))

        # 角色頭像
        try:
            avatar = await get_square_avatar(char_rank.roleId)
            if avatar:
                avatar = avatar.resize((120, 120))
                card.paste(avatar, (80, 20), avatar)
        except:
            pass

        # 角色信息
        draw = ImageDraw.Draw(card)

        # 角色名稱
        draw_text_with_shadow(
            draw, (width // 2, 160), char_rank.roleName, waves_font_30, "white", "mm"
        )

        # 等級
        draw_text_with_shadow(
            draw, (width // 2, 190), f"Lv.{char_rank.level}", waves_font_25, GOLD, "mm"
        )

        # 共鳴鍊
        chain_text = f"共鳴鍊 {char_rank.chainUnlockNum}"
        draw_text_with_shadow(
            draw,
            (width // 2, 220),
            chain_text,
            waves_font_25,
            GOLD if char_rank.chainUnlockNum > 0 else GREY,
            "mm",
        )

        # 更新標識
        if is_updated:
            # 添加更新標記
            update_bg = Image.new("RGBA", (60, 30), (0, 255, 0, 180))
            update_draw = ImageDraw.Draw(update_bg)
            update_draw.text((30, 15), "增強", waves_font_25, "white", "mm")
            card.paste(update_bg, (width - 70, 10), update_bg)

        return card

    except Exception as e:
        from gsuid_core.logger import logger

        logger.exception(f"繪製增強角色卡片失敗: {char_rank.roleId}")

        # 返回錯誤卡片
        error_card = Image.new("RGBA", (280, 320), (128, 128, 128, 255))
        error_draw = ImageDraw.Draw(error_card)
        error_draw.text((140, 160), "載入失敗", waves_font_30, "white", "mm")
        return error_card


async def draw_enhanced_refresh_panel(bot, ev, user_id: str, uid: str, buttons):
    """繪製增強PCAP刷新面板（不需要token）"""
    try:
        from PIL import Image, ImageDraw
        from gsuid_core.logger import logger
        from gsuid_core.utils.image.convert import convert_img

        from ..utils.char_info_utils import get_all_role_detail_info_list
        from ..utils.fonts.waves_fonts import waves_font_25, waves_font_30
        from ..utils.image import GOLD, add_footer, get_random_share_bg_path

        logger.info(f"開始繪製增強刷新面板: {uid}")

        # 獲取本地角色數據
        all_waves_datas = await get_all_role_detail_info_list(uid)

        # 將生成器轉換為列表
        if all_waves_datas:
            all_waves_datas_list = list(all_waves_datas)
        else:
            all_waves_datas_list = []

        if not all_waves_datas_list:
            return "暂无面板数据，请先使用「解析」指令上传PCAP文件"

        logger.info(f"找到 {len(all_waves_datas_list)} 個角色數據")

        # 創建一個簡單的面板圖片
        bg_path_or_image = await get_random_share_bg_path()

        if isinstance(bg_path_or_image, Image.Image):
            # 如果返回的是圖片對象，直接使用
            bg = bg_path_or_image
        else:
            # 如果返回的是路徑，打開圖片
            bg = Image.open(bg_path_or_image).convert("RGBA")

        # 調整背景大小
        bg = bg.resize((1200, 800))

        # 創建繪圖對象
        draw = ImageDraw.Draw(bg)

        # 添加標題
        draw.text((600, 50), "增強PCAP面板刷新成功", GOLD, waves_font_30, anchor="mm")
        draw.text(
            (600, 100),
            f"已更新 {len(all_waves_datas_list)} 個角色的面板數據",
            "white",
            waves_font_25,
            anchor="mm",
        )

        # 添加角色信息
        y_offset = 150
        for i, char_data in enumerate(all_waves_datas_list[:10]):  # 最多顯示10個角色
            char_name = char_data.role.roleName
            char_level = char_data.role.level

            draw.text(
                (100, y_offset), f"• {char_name}", "white", waves_font_25, anchor="lm"
            )
            draw.text(
                (300, y_offset), f"等級 {char_level}", GOLD, waves_font_25, anchor="lm"
            )

            y_offset += 40

        # 添加使用說明
        draw.text(
            (600, y_offset + 50),
            "現在可以正常使用角色面板功能了",
            "white",
            waves_font_25,
            anchor="mm",
        )
        draw.text(
            (600, y_offset + 90),
            "數據已同步到本地，無需再次解析",
            "white",
            waves_font_25,
            anchor="mm",
        )

        # 添加頁腳
        bg = add_footer(bg)

        return await convert_img(bg)

    except Exception as e:
        from gsuid_core.logger import logger

        logger.exception(f"繪製增強刷新面板失敗: {uid} - {e}")
        return f"❌ 繪製面板失敗: {str(e)}"
