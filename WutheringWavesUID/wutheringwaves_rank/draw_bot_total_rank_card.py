import time
import asyncio
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Union, Optional

from gsuid_core.bot import Bot
from PIL import Image, ImageDraw
from gsuid_core.models import Event
from gsuid_core.logger import logger
from gsuid_core.utils.image.convert import convert_img

from ..utils.calc import WuWaCalc
from ..utils.util import hide_uid
from ..utils.cache import TimedCache
from ..utils.api.model import RoleDetailData
from ..utils.waves_card_cache import get_card
from ..utils.resource.constant import SPECIAL_CHAR_NAME
from ..utils.database.models import WavesBind, WavesUser
from ..wutheringwaves_config import PREFIX, WutheringWavesConfig
from ..utils.calculate import (
    get_calc_map,
    calc_phantom_score,
    get_total_score_bg,
)
from ..wutheringwaves_analyzecard.user_info_utils import (
    get_region_for_rank,
    get_user_detail_info,
)
from ..utils.fonts.waves_fonts import (
    waves_font_12,
    waves_font_16,
    waves_font_18,
    waves_font_20,
    waves_font_24,
    waves_font_28,
    waves_font_30,
    waves_font_34,
    waves_font_44,
)
from ..utils.image import (
    RED,
    GREY,
    AMBER,
    WAVES_VOID,
    SPECIAL_GOLD,
    WAVES_MOLTEN,
    WAVES_SIERRA,
    WAVES_MOONLIT,
    WAVES_FREEZING,
    WAVES_LINGERING,
    add_footer,
    get_waves_bg,
    get_square_avatar,
)

TEXT_PATH = Path(__file__).parent / "texture2d"
pic_cache = TimedCache(600, 200)
rank_cache = TimedCache(86400, 50)  # 24小時緩存排行數據

BOT_COLOR = [
    WAVES_MOLTEN,
    AMBER,
    WAVES_VOID,
    WAVES_SIERRA,
    WAVES_FREEZING,
    WAVES_LINGERING,
    WAVES_MOONLIT,
]


class BotUserRankInfo:
    def __init__(
        self, user_id: str, uid: str, kuro_name: str, server: str, server_color: tuple
    ):
        self.user_id = user_id
        self.uid = uid
        self.kuro_name = kuro_name
        self.server = server
        self.server_color = server_color
        self.total_score = 0.0
        self.char_count = 0
        self.char_details = []  # List of (char_id, char_name, score)
        self.highest_score = 0.0


async def calculate_user_total_score(
    uid: str, user_id: str
) -> Optional[BotUserRankInfo]:
    """計算單個用戶的總練度分數"""
    try:
        # 獲取用戶角色數據
        role_details = await get_card(uid)
        if not role_details:
            return None

        # 獲取用戶信息
        account_info = await get_user_detail_info(uid)
        region_text, region_color = get_region_for_rank(uid)

        rank_info = BotUserRankInfo(
            user_id=user_id,
            uid=uid,
            kuro_name=account_info.name[:6],
            server=region_text,
            server_color=region_color,
        )

        total_score = 0.0
        char_details = []

        # 計算每個角色的分數（簡化計算以提高性能）
        for role_detail in role_details:
            if (
                not role_detail.phantomData
                or not role_detail.phantomData.equipPhantomList
            ):
                continue

            try:
                # 使用正確的聲骸分數計算
                calc = WuWaCalc(role_detail)
                calc.phantom_pre = calc.prepare_phantom()
                calc.phantom_card = calc.enhance_summation_phantom_value(
                    calc.phantom_pre
                )
                calc.calc_temp = get_calc_map(
                    calc.phantom_card,
                    role_detail.role.roleName,
                    role_detail.role.roleId,
                )

                phantom_score = 0.0
                for phantom in role_detail.phantomData.equipPhantomList:
                    if phantom and phantom.phantomProp:
                        props = phantom.get_props()
                        score, _ = calc_phantom_score(
                            role_detail.role.roleName,
                            props,
                            phantom.cost,
                            calc.calc_temp,
                        )
                        phantom_score += score

                # 只有當分數大於等於175時才計算
                if phantom_score >= 175:
                    char_details.append(
                        (
                            role_detail.role.roleId,
                            role_detail.role.roleName,
                            phantom_score,
                        )
                    )
                    total_score += phantom_score

            except Exception as e:
                logger.warning(f"計算角色 {role_detail.role.roleId} 分數失敗: {e}")
                continue

        # 按分數排序
        char_details.sort(key=lambda x: x[2], reverse=True)

        rank_info.total_score = total_score
        rank_info.char_count = len(char_details)
        rank_info.char_details = char_details
        rank_info.highest_score = char_details[0][2] if char_details else 0.0

        return rank_info

    except Exception as e:
        logger.warning(f"計算用戶 {uid} 練度失敗: {e}")
        return None


async def get_bot_total_rank_data(ev: Event) -> List[BotUserRankInfo]:
    """獲取所有 bot 用戶的練度數據"""
    # 獲取所有綁定的用戶
    users = await WavesBind.get_all_data()
    if not users:
        return []

    # 檢查是否需要登錄驗證
    token_limit_flag, waves_token_users_map = await get_waves_token_condition(ev)

    rank_data = []
    semaphore = asyncio.Semaphore(10)  # 減少並發數以提高穩定性

    async def process_user(user):
        async with semaphore:
            if not user.uid:
                return

            # 處理多個 UID 的情況，但只取第一個 UID 以提高性能
            uid = user.uid.split("_")[0]  # 只處理第一個 UID

            # 檢查是否需要登錄驗證
            if token_limit_flag and (user.user_id, uid) not in waves_token_users_map:
                return

            rank_info = await calculate_user_total_score(uid, user.user_id)
            if rank_info:
                rank_data.append(rank_info)

    # 並發處理所有用戶
    tasks = [process_user(user) for user in users]
    await asyncio.gather(*tasks)

    # 按總分排序
    rank_data.sort(key=lambda x: x.total_score, reverse=True)

    return rank_data


async def get_waves_token_condition(ev):
    """獲取登錄驗證條件"""
    waves_token_users_map = {}
    flag = False

    # 群組自定義的
    waves_rank_use_token_group = WutheringWavesConfig.get_config(
        "WavesRankUseTokenGroup"
    ).data
    # 全局主人定義的
    rank_use_token = WutheringWavesConfig.get_config("RankUseToken").data

    if (
        waves_rank_use_token_group and ev.group_id in waves_rank_use_token_group
    ) or rank_use_token:
        waves_token_users = await WavesUser.get_waves_all_user(None)
        waves_token_users_map = {
            (w.user_id, w.uid): w.cookie for w in waves_token_users
        }
        flag = True

    return flag, waves_token_users_map


async def draw_bot_total_rank(bot: Bot, ev: Event, pages: int = 1) -> Union[str, bytes]:
    """繪製 bot 練度總排行"""
    start_time = time.time()
    logger.info(f"[bot_total_rank] 開始獲取數據: {start_time}")

    # 檢查緩存（每天更新一次）
    cache_key = f"bot_total_rank_{ev.group_id or 'private'}"
    cache_date_key = f"bot_total_rank_date_{ev.group_id or 'private'}"

    # 獲取今天的日期
    today = time.strftime("%Y-%m-%d")
    cached_date = rank_cache.get(cache_date_key)
    cached_data = rank_cache.get(cache_key)

    # 如果緩存存在且是今天的數據，則使用緩存
    if cached_data and cached_date == today:
        logger.info(f"[bot_total_rank] 使用今日緩存數據")
        rank_data = cached_data
    else:
        # 獲取新的排行數據
        logger.info(f"[bot_total_rank] 重新計算排行數據")
        rank_data = await get_bot_total_rank_data(ev)
        # 緩存數據和日期
        rank_cache.set(cache_key, rank_data)
        rank_cache.set(cache_date_key, today)

    if not rank_data:
        msg = []
        msg.append("[鳴潮] bot內暫無練度數據")
        msg.append(f"請使用【{PREFIX}刷新面板】後再使用此功能！")
        return "\n".join(msg)

    # 分頁處理
    page_size = 20
    start_idx = (pages - 1) * page_size
    end_idx = start_idx + page_size
    page_data = rank_data[start_idx:end_idx]

    if not page_data:
        return f"[鳴潮] 第 {pages} 頁暫無數據"

    # 獲取當前用戶的 UID
    self_uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    if not self_uid:
        self_uid = ""

    # 設置圖像尺寸
    width = 1300
    text_bar_height = 130
    item_spacing = 120
    header_height = 510
    footer_height = 50
    char_list_len = len(page_data)

    # 計算所需的總高度
    total_height = (
        header_height + text_bar_height + item_spacing * char_list_len + footer_height
    )

    # 創建帶背景的畫布
    card_img = get_waves_bg(width, total_height, "bg9")

    # 繪製說明欄
    text_bar_img = Image.new("RGBA", (width, 130), color=(0, 0, 0, 0))
    text_bar_draw = ImageDraw.Draw(text_bar_img)

    # 繪製深灰色背景
    bar_bg_color = (36, 36, 41, 230)
    text_bar_draw.rounded_rectangle(
        [20, 20, width - 40, 110], radius=8, fill=bar_bg_color
    )

    # 繪製頂部的金色高亮線
    accent_color = (203, 161, 95)
    text_bar_draw.rectangle([20, 20, width - 40, 26], fill=accent_color)

    # 左側標題
    text_bar_draw.text((40, 60), "排行說明", GREY, waves_font_28, "lm")
    text_bar_draw.text(
        (185, 50),
        "練度總排行：計算所有角色的聲骸分數總和，展示 bot 內用戶的整體練度水平",
        "white",
        waves_font_18,
        "lm",
    )
    text_bar_draw.text(
        (185, 75),
        "排序標準：總分 > 最高分 > 角色數",
        SPECIAL_GOLD,
        waves_font_16,
        "lm",
    )

    # 右側統計信息
    total_users = len(rank_data)
    avg_score = (
        sum(user.total_score for user in rank_data) / total_users
        if total_users > 0
        else 0
    )
    text_bar_draw.text(
        (1000, 50), f"總用戶數: {total_users}", "white", waves_font_18, "lm"
    )
    text_bar_draw.text(
        (1000, 75), f"平均分數: {avg_score:.1f}", SPECIAL_GOLD, waves_font_18, "lm"
    )

    # 貼上說明欄
    card_img.paste(text_bar_img, (0, header_height), text_bar_img)

    # 繪製排行條目
    bot_color_map = {}
    bot_color = BOT_COLOR.copy()

    for index, user_rank in enumerate(page_data):
        # 創建排行條目背景
        bar_bg = Image.new("RGBA", (width, item_spacing), color=(0, 0, 0, 0))
        bar_draw = ImageDraw.Draw(bar_bg)

        # 繪製條目背景
        item_bg_color = (36, 36, 41, 200)
        bar_draw.rounded_rectangle(
            [20, 10, width - 40, item_spacing - 10], radius=8, fill=item_bg_color
        )

        # 排名
        rank_id = start_idx + index + 1
        rank_color = (54, 54, 54)
        if rank_id == 1:
            rank_color = (255, 0, 0)  # 紅色
        elif rank_id == 2:
            rank_color = (255, 180, 0)  # 金色
        elif rank_id == 3:
            rank_color = (185, 106, 217)  # 紫色

        # 繪製排名標籤
        info_rank = Image.new("RGBA", (50, 50), color=(255, 255, 255, 0))
        rank_draw = ImageDraw.Draw(info_rank)
        rank_draw.rounded_rectangle(
            [0, 0, 50, 50], radius=8, fill=rank_color + (int(0.9 * 255),)
        )
        rank_draw.text((25, 25), f"{rank_id}", "white", waves_font_34, "mm")
        bar_bg.alpha_composite(info_rank, (40, 35))

        # 繪製玩家名字
        bar_draw.text((210, 75), f"{user_rank.kuro_name}", "white", waves_font_20, "lm")

        # 繪製角色數量
        bar_draw.text((210, 45), "角色數:", (255, 255, 255), waves_font_18, "lm")
        bar_draw.text((280, 45), f"{user_rank.char_count}", RED, waves_font_20, "lm")

        # 繪製角色頭像
        if user_rank.char_details:
            logger.info(
                f"用戶 {user_rank.kuro_name} 有 {len(user_rank.char_details)} 個角色"
            )
            # 按分數排序，取前6名
            sorted_chars = sorted(
                user_rank.char_details, key=lambda x: x[2], reverse=True
            )[:6]

            # 在條目底部繪製前6名角色的頭像
            char_size = 40
            char_spacing = 45
            char_start_x = 570
            char_start_y = 35

            for i, (char_id, char_name, char_score) in enumerate(sorted_chars):
                char_x = char_start_x + i * char_spacing
                logger.info(f"繪製角色 {char_id} ({char_name}) 分數: {char_score}")

                # 使用與國服練度總排行相同的頭像處理方式
                try:
                    # 獲取角色頭像
                    char_avatar = await get_square_avatar(char_id)
                    char_avatar = char_avatar.resize((char_size, char_size))

                    # 應用圓形遮罩（與國服練度總排行相同）
                    char_mask_img = Image.open(TEXT_PATH / "char_mask.png")
                    char_mask_resized = char_mask_img.resize((char_size, char_size))
                    char_avatar_masked = Image.new("RGBA", (char_size, char_size))
                    char_avatar_masked.paste(char_avatar, (0, 0), char_mask_resized)

                    # 粘貼頭像
                    bar_bg.paste(
                        char_avatar_masked, (char_x, char_start_y), char_avatar_masked
                    )
                    logger.info(f"成功繪製角色 {char_id} 頭像")
                except Exception as e:
                    logger.warning(f"獲取角色 {char_id} 頭像失敗: {e}")
                    # 使用預設頭像
                    try:
                        default_avatar = await get_square_avatar("1505")  # 預設頭像
                        default_avatar = default_avatar.resize((char_size, char_size))

                        # 應用圓形遮罩
                        char_mask_img = Image.open(TEXT_PATH / "char_mask.png")
                        char_mask_resized = char_mask_img.resize((char_size, char_size))
                        char_avatar_masked = Image.new("RGBA", (char_size, char_size))
                        char_avatar_masked.paste(
                            default_avatar, (0, 0), char_mask_resized
                        )

                        # 粘貼預設頭像
                        bar_bg.paste(
                            char_avatar_masked,
                            (char_x, char_start_y),
                            char_avatar_masked,
                        )
                        logger.info(f"使用預設頭像替代角色 {char_id}")
                    except Exception as e2:
                        logger.warning(f"獲取預設頭像失敗: {e2}")

                # 繪製分數（只在頭像下方顯示）
                score_text = f"{int(char_score)}"
                bar_draw.text(
                    (char_x + char_size // 2, char_start_y + char_size + 2),
                    score_text,
                    SPECIAL_GOLD,
                    waves_font_12,
                    "mm",
                )

            # 顯示最高分（只顯示一次，避免重疊）
            if sorted_chars:
                best_score = f"{int(sorted_chars[0][2])} "
                bar_draw.text((1080, 45), best_score, "lightgreen", waves_font_30, "mm")
                bar_draw.text((1080, 75), "最高分", "white", waves_font_16, "mm")
        else:
            logger.warning(f"用戶 {user_rank.kuro_name} 沒有角色數據")

        # UID
        uid_color = "white"
        if user_rank.uid == self_uid:
            uid_color = RED
        bar_draw.text(
            (350, 40),
            f"特征碼: {hide_uid(user_rank.uid)}",
            uid_color,
            waves_font_20,
            "lm",
        )

        # 區服標籤
        region_block = Image.new("RGBA", (200, 30), color=(255, 255, 255, 0))
        region_draw = ImageDraw.Draw(region_block)
        region_draw.rounded_rectangle(
            [0, 0, 200, 30], radius=6, fill=user_rank.server_color + (int(0.6 * 255),)
        )
        region_draw.text(
            (100, 15), f"Server: {user_rank.server}", "white", waves_font_18, "mm"
        )
        bar_bg.alpha_composite(region_block, (350, 66))

        # 總分數
        bar_draw.text(
            (1180, 45),
            f"{user_rank.total_score:.1f}",
            (255, 255, 255),
            waves_font_34,
            "mm",
        )
        bar_draw.text((1180, 75), "總分", "white", waves_font_16, "mm")

        # 繪製角色信息（前10名）
        if user_rank.char_details:
            char_size = 40
            char_spacing = 45
            char_start_x = 570
            char_start_y = 35

            for i, (char_id, char_name, score) in enumerate(
                user_rank.char_details[:10]
            ):
                char_x = char_start_x + i * char_spacing

                # 獲取角色頭像
                char_avatar = await get_square_avatar(char_id)
                char_avatar = char_avatar.resize((char_size, char_size))

                # 應用圓形遮罩
                char_mask_img = Image.open(TEXT_PATH / "char_mask.png")
                char_mask_resized = char_mask_img.resize((char_size, char_size))
                char_avatar_masked = Image.new("RGBA", (char_size, char_size))
                char_avatar_masked.paste(char_avatar, (0, 0), char_mask_resized)

                # 粘貼頭像
                bar_bg.paste(
                    char_avatar_masked, (char_x, char_start_y), char_avatar_masked
                )

                # 繪製分數
                score_text = f"{int(score)}"
                bar_draw.text(
                    (char_x + char_size // 2, char_start_y + char_size + 2),
                    score_text,
                    SPECIAL_GOLD,
                    waves_font_12,
                    "mm",
                )

            # 顯示最高分
            best_score = f"{int(user_rank.highest_score)}"
            bar_draw.text((1080, 45), best_score, "lightgreen", waves_font_30, "mm")
            bar_draw.text((1080, 75), "最高分", "white", waves_font_16, "mm")

        # 貼到背景
        card_img.paste(
            bar_bg, (0, header_height + text_bar_height + index * item_spacing), bar_bg
        )

    # 繪製標題（使用與國服練度總排行相同的樣式）
    title_bg = Image.open(TEXT_PATH / "totalrank.jpg")
    title_bg = title_bg.crop((0, 0, width, 500))

    # icon
    from ..utils.image import get_ICON

    icon = get_ICON()
    icon = icon.resize((128, 128))
    title_bg.paste(icon, (60, 240), icon)

    # title
    title_text = "#Bot练度总排行"
    title_bg_draw = ImageDraw.Draw(title_bg)
    title_bg_draw.text((220, 290), title_text, "white", waves_font_44, "lm")

    # 副標題
    title_bg_draw.text((220, 340), f"第 {pages} 頁", SPECIAL_GOLD, waves_font_28, "lm")

    # 統計信息
    if rank_data:
        total_score = sum(user.total_score for user in rank_data)
        avg_score = total_score / len(rank_data)
        title_bg_draw.text(
            (220, 380), f"總用戶數: {len(rank_data)}", "white", waves_font_20, "lm"
        )
        title_bg_draw.text(
            (220, 410), f"平均練度: {avg_score:.1f}", SPECIAL_GOLD, waves_font_20, "lm"
        )

    # 遮罩
    char_mask_img = Image.open(TEXT_PATH / "char_mask.png").convert("RGBA")
    # 根据width扩图
    char_mask_img = char_mask_img.resize(
        (width, char_mask_img.height * width // char_mask_img.width)
    )
    char_mask_img = char_mask_img.crop(
        (0, char_mask_img.height - 500, width, char_mask_img.height)
    )
    char_mask_temp = Image.new("RGBA", char_mask_img.size, (0, 0, 0, 0))
    char_mask_temp.paste(title_bg, (0, 0), char_mask_img)

    card_img.paste(char_mask_temp, (0, 0), char_mask_temp)

    # 添加頁腳
    card_img = add_footer(card_img)
    card_img = await convert_img(card_img)

    logger.info(f"[bot_total_rank] 完成: {time.time() - start_time}")
    return card_img
