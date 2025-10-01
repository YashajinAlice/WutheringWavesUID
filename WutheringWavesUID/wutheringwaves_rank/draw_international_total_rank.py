"""
國際服總排行繪製模組
基於bot排行邏輯，專門為國際服數據設計
"""

import copy
import time
import asyncio
from pathlib import Path
from typing import List, Union, Optional

from gsuid_core.bot import Bot
from pydantic import BaseModel
from PIL import Image, ImageDraw
from gsuid_core.models import Event
from gsuid_core.logger import logger
from gsuid_core.sv import get_plugin_available_prefix
from gsuid_core.utils.image.convert import convert_img
from gsuid_core.utils.image.image_tools import crop_center_img

from ..utils.calc import WuWaCalc
from ..utils.util import hide_uid
from ..utils.cache import TimedCache
from ..utils.waves_card_cache import get_card
from ..utils.damage.abstract import DamageRankRegister
from ..utils.api.model import WeaponData, RoleDetailData
from ..utils.database.models import WavesBind, WavesUser

PREFIX = get_plugin_available_prefix("WutheringWavesUID")


# 延遲導入以避免循環依賴
def get_config():
    from ..wutheringwaves_config import WutheringWavesConfig

    return WutheringWavesConfig


# TEXT_PATH 在本地定義
TEXT_PATH = Path(__file__).parent / "texture2d"
TITLE_I = Image.open(TEXT_PATH / "title.png")
TITLE_II = Image.open(TEXT_PATH / "title2.png")
avatar_mask = Image.open(TEXT_PATH / "avatar_mask.png")
weapon_icon_bg_3 = Image.open(TEXT_PATH / "weapon_icon_bg_3.png")
weapon_icon_bg_4 = Image.open(TEXT_PATH / "weapon_icon_bg_4.png")
weapon_icon_bg_5 = Image.open(TEXT_PATH / "weapon_icon_bg_5.png")
pic_cache = TimedCache(600, 200)


def get_weapon_icon_bg(star: int = 3) -> Image.Image:
    """獲取武器圖標背景"""
    if star < 3:
        star = 3
    bg_path = TEXT_PATH / f"weapon_icon_bg_{star}.png"
    bg_img = Image.open(bg_path)
    return bg_img


from ..utils.resource.constant import SPECIAL_CHAR, SPECIAL_CHAR_NAME
from ..utils.name_convert import alias_to_char_name, char_name_to_char_id
from ..utils.calculate import (
    get_calc_map,
    calc_phantom_score,
    get_total_score_bg,
)
from ..utils.image import (
    GREY,
    SPECIAL_GOLD,
    WEAPON_RESONLEVEL_COLOR,
    get_square_weapon,
)
from ..wutheringwaves_analyzecard.user_info_utils import (
    get_region_for_rank,
    get_user_detail_info,
)
from ..utils.fonts.waves_fonts import (
    waves_font_14,
    waves_font_16,
    waves_font_18,
    waves_font_20,
    waves_font_24,
    waves_font_28,
    waves_font_30,
    waves_font_34,
    waves_font_44,
)


# 國際服總排行數據模型
class InternationalRankInfo(BaseModel):
    roleDetail: RoleDetailData  # 角色明细
    qid: str  # qq id
    uid: str  # uid
    kuro_name: str  # 库洛名称
    server: str  # 服务器
    server_color: str  # 服务器颜色
    level: int  # 等级
    chain: int  # 共鸣链
    chainName: str  # 命座
    score: float  # 角色评分
    score_bg: str  # 评分背景
    expected_damage: str  # 期望伤害
    expected_damage_int: int  # 期望伤害
    sonata_name: str  # 合鸣效果
    bot_name: str  # 機器人名稱
    server_region: str  # 服務器區域


async def get_international_rank_info(user_id, uid, role_detail, rankDetail):
    """獲取國際服排行信息"""
    equipPhantomList = role_detail.phantomData.equipPhantomList

    calc: WuWaCalc = WuWaCalc(role_detail)
    calc.phantom_pre = calc.prepare_phantom()
    calc.phantom_card = calc.enhance_summation_phantom_value(calc.phantom_pre)
    calc.calc_temp = get_calc_map(
        calc.phantom_card,
        role_detail.role.roleName,
        role_detail.role.roleId,
    )

    # 评分
    phantom_score = 0
    for i, _phantom in enumerate(equipPhantomList):
        if _phantom and _phantom.phantomProp:
            props = _phantom.get_props()
            _score, _bg = calc_phantom_score(
                role_detail.role.roleName, props, _phantom.cost, calc.calc_temp
            )
            phantom_score += _score

    if phantom_score == 0:
        return

    phantom_bg = get_total_score_bg(
        role_detail.role.roleName, phantom_score, calc.calc_temp
    )

    calc.role_card = calc.enhance_summation_card_value(calc.phantom_card)
    calc.damageAttribute = calc.card_sort_map_to_attribute(calc.role_card)

    if rankDetail:
        crit_damage, expected_damage = rankDetail["func"](
            calc.damageAttribute, role_detail
        )
    else:
        expected_damage = "0"

    sonata_name = ""
    ph_detail = calc.phantom_card.get("ph_detail", [])
    if isinstance(ph_detail, list):
        for ph in ph_detail:
            if ph.get("ph_num") == 5:
                sonata_name = ph.get("ph_name", "")
                break

            if ph.get("isFull"):
                sonata_name = ph.get("ph_name", "")
                break

    # 区服
    region_text, region_color = get_region_for_rank(uid)

    # 用户名称
    account_info = await get_user_detail_info(uid)

    rankInfo = InternationalRankInfo(
        **{
            "roleDetail": role_detail,
            "qid": user_id,
            "uid": uid,
            "kuro_name": account_info.name[:6],
            "server": region_text,
            "server_color": region_color,
            "level": role_detail.role.level,
            "chain": role_detail.get_chain_num(),
            "chainName": role_detail.get_chain_name(),
            "score": round(phantom_score, 2),
            "score_bg": phantom_bg,
            "expected_damage": expected_damage,
            "expected_damage_int": int(expected_damage.replace(",", "")),
            "sonata_name": sonata_name,
            "bot_name": "雅蘭娜",  # 默認機器人名稱
            "server_region": "international",  # 國際服標識
        }
    )

    return rankInfo


async def find_international_role_detail(
    uid: str, char_id: Union[int, str, List[str], List[int]]
) -> Optional[RoleDetailData]:
    """查找國際服角色詳情"""
    role_details = await get_card(uid)
    if role_details is None:
        return None

    if isinstance(char_id, (list, tuple)):
        query_list = [str(c) for c in char_id]
    else:
        query_list = [str(char_id)]

    for role_detail in role_details:
        if str(role_detail.role.roleId) in query_list:
            # 檢查是否為國際服數據
            if (
                hasattr(role_detail, "server_region")
                and role_detail.server_region == "international"
            ):
                return role_detail
            # 如果沒有server_region字段，假設為國際服（向後兼容）
            elif not hasattr(role_detail, "server_region"):
                return role_detail

    return None


def _get_api_version() -> str:
    """獲取API版本號"""
    try:
        from ..utils.api_version import get_api_version

        return get_api_version()
    except ImportError:
        return "1.1.0"  # 默認版本


async def draw_international_total_rank_img(
    bot: Bot, ev: Event, char: str, rank_type: str, pages: int
):
    """繪製國際服總排行圖片"""
    try:
        # 從國際服API獲取數據
        logger.info(
            f"[國際服總排行] 開始獲取國際服數據 - 角色: {char}, 類型: {rank_type}, 頁數: {pages}"
        )

        # 調用國際服API獲取指定角色的數據
        import httpx

        from ..utils.name_convert import char_name_to_char_id

        # 獲取角色ID
        char_id = char_name_to_char_id(char)
        if not char_id:
            return f"[鳴潮] 角色名【{char}】無法找到，請檢查輸入是否正確！"

        async with httpx.AsyncClient() as client:
            # 初始化API版本
            api_version = _get_api_version()

            try:
                # 首先檢查API版本
                version_response = await client.get(
                    "https://wwuidapi.fulin-net.top/api/international/version",
                    timeout=httpx.Timeout(5),
                )
                if version_response.status_code == 200:
                    version_info = version_response.json()
                    api_version = version_info.get("version", _get_api_version())
                    client_version = _get_api_version()

                    if api_version != client_version:
                        return f"[鳴潮] 版本不匹配：客戶端版本 {client_version}，服務端版本 {api_version}。請聯絡API端進行協助更新。"
                else:
                    logger.warning("[國際服總排行] 無法獲取API版本信息，繼續執行...")

                # 調用國際服API獲取指定角色的排行數據
                response = await client.get(
                    f"https://wwuidapi.fulin-net.top/api/international/character/ranking/{char_id}?limit=20&page={pages}&client_version={_get_api_version()}",
                    timeout=httpx.Timeout(10),
                )
                if response.status_code == 200:
                    api_data = response.json()
                    rankings = api_data.get("rankings", [])
                    logger.info(f"[國際服總排行] 獲取到 {len(rankings)} 個{char}的數據")
                    logger.info(f"[國際服總排行] API完整響應: {api_data}")

                    # 繪製排行圖片
                    img = await create_international_rank_image(
                        api_data, char, rank_type, pages, api_version
                    )
                    return img
                else:
                    logger.error(f"[國際服總排行] API請求失敗: {response.status_code}")
                    return "[鳴潮] 國際服API請求失敗"
            except Exception as e:
                logger.error(f"[國際服總排行] API請求異常: {e}")
                return "[鳴潮] 國際服API服務不可用"

    except Exception as e:
        logger.error(f"[國際服總排行] 繪製失敗: {e}")
        return f"[鳴潮] 國際服總排行生成失敗: {str(e)}"


async def get_avatar(
    qid: Optional[str],
    char_id: Union[int, str],
) -> Image.Image:
    """獲取玩家頭像"""
    # 检查qid 为纯数字
    if qid and qid.isdigit():
        if get_config().get_config("QQPicCache").data:
            pic = pic_cache.get(qid)
            if not pic:
                from ..utils.image import get_qq_avatar

                pic = await get_qq_avatar(qid, size=100)
                pic_cache.set(qid, pic)
        else:
            from ..utils.image import get_qq_avatar

            pic = await get_qq_avatar(qid, size=100)
            pic_cache.set(qid, pic)
        from ..utils.image import crop_center_img

        pic_temp = crop_center_img(pic, 120, 120)

        img = Image.new("RGBA", (180, 180))
        avatar_mask_temp = avatar_mask.copy()
        mask_pic_temp = avatar_mask_temp.resize((120, 120), Image.Resampling.LANCZOS)
        img.paste(pic_temp, (0, -5), mask_pic_temp)
    else:
        from ..utils.image import get_square_avatar

        pic = await get_square_avatar(char_id)

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


async def get_discord_avatar_for_rank(
    user_id: str, char_id: Union[int, str]
) -> Image.Image:
    """為國際服排行獲取Discord用戶頭像"""
    try:
        from ..wutheringwaves_config import WutheringWavesConfig
        from ..utils.image import (
            crop_center_img,
            get_square_avatar,
            get_discord_avatar,
        )

        # 使用Discord頭像獲取邏輯
        if WutheringWavesConfig.get_config("QQPicCache").data:
            pic = pic_cache.get(user_id)
            if not pic:
                pic = await get_discord_avatar(user_id, size=100)
                pic_cache.set(user_id, pic)
        else:
            pic = await get_discord_avatar(user_id, size=100)
            pic_cache.set(user_id, pic)

        # 統一處理 crop 和遮罩
        pic_temp = crop_center_img(pic, 120, 120)
        img = Image.new("RGBA", (180, 180))
        avatar_mask_temp = avatar_mask.copy()
        mask_pic_temp = avatar_mask_temp.resize((120, 120), Image.Resampling.LANCZOS)
        img.paste(pic_temp, (0, -5), mask_pic_temp)

        return img

    except Exception as e:
        logger.warning(f"Discord頭像獲取失敗，使用默認頭像: {e}")
        # 降級處理：使用角色頭像
        from ..utils.image import get_square_avatar

        pic = await get_square_avatar(char_id)

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


async def create_international_rank_image(
    api_data: dict, char: str, rank_type: str, pages: int, api_version: str = None
):
    """創建國際服總排行圖片 - 基於國服總排行結構"""
    try:
        # 獲取指定角色的數據
        char_data = api_data.get("rankings", [])
        if not char_data:
            return "[鳴潮] 暫無國際服數據"

        # 使用與國服總排行完全相同的結構
        totalNum = len(char_data)
        title_h = 500
        bar_star_h = 110
        text_bar_h = 130
        h = title_h + totalNum * bar_star_h + text_bar_h + 80

        # 創建背景圖片
        from ..utils.image import get_waves_bg

        card_img = get_waves_bg(1300, h, "bg3")

        # 繪製上榜條件（與國服總排行相同結構）
        text_bar_img = Image.new("RGBA", (1300, text_bar_h), color=(0, 0, 0, 0))
        text_bar_draw = ImageDraw.Draw(text_bar_img)

        # 繪製深灰色背景
        bar_bg_color = (36, 36, 41, 230)
        text_bar_draw.rounded_rectangle(
            [20, 20, 1280, text_bar_h - 15], radius=8, fill=bar_bg_color
        )

        # 繪製頂部的金色高亮線
        accent_color = (203, 161, 95)
        text_bar_draw.rectangle([20, 20, 1280, 26], fill=accent_color)

        # 左側標題
        text_bar_draw.text((40, 60), "上榜條件", GREY, waves_font_28, "lm")
        text_bar_draw.text(
            (185, 50), "1. 僅顯示國際服用戶", SPECIAL_GOLD, waves_font_20, "lm"
        )
        text_bar_draw.text(
            (185, 85), "2. 基於分析後上傳的數據", SPECIAL_GOLD, waves_font_20, "lm"
        )

        # 備註
        temp_notes = "排行標準：以期望傷害為排序的排名，僅顯示國際服用戶數據"
        text_bar_draw.text((1260, 100), temp_notes, SPECIAL_GOLD, waves_font_16, "rm")

        card_img.alpha_composite(text_bar_img, (0, title_h))

        # 繪製排行列表（與國服總排行相同結構）
        bar = Image.open(TEXT_PATH / "bar1.png")
        total_score = 0
        total_damage = 0

        # 獲取角色頭像
        from ..utils.image import get_square_avatar
        from ..utils.ascension.char import get_char_model
        from ..utils.name_convert import char_name_to_char_id

        char_id = char_name_to_char_id(char)
        if char_id:
            pic = await get_square_avatar(char_id)
            pic_temp = Image.new("RGBA", pic.size)
            pic_temp.paste(pic.resize((160, 160), Image.Resampling.LANCZOS), (10, 10))
            pic_temp = pic_temp.resize((160, 160), Image.Resampling.LANCZOS)
        else:
            pic_temp = Image.new("RGBA", (160, 160), color=(0, 0, 0, 0))

        # 獲取角色屬性
        from ..utils.ascension.char import get_char_model

        char_model = get_char_model(char_id)
        if char_model:
            from ..utils.resource.constant import ATTRIBUTE_ID_MAP

            attribute_name = ATTRIBUTE_ID_MAP[char_model.attributeId]
            from ..utils.image import get_attribute

            role_attribute = await get_attribute(attribute_name, is_simple=True)
            role_attribute = role_attribute.resize(
                (40, 40), Image.Resampling.LANCZOS
            ).convert("RGBA")
        else:
            role_attribute = None

        # 獲取武器和聲骸相關函數
        from ..utils.ascension.weapon import get_weapon_model

        # Bot顏色管理系統
        from ..utils.image import (
            AMBER,
            WAVES_VOID,
            WAVES_MOLTEN,
            WAVES_SIERRA,
            WAVES_MOONLIT,
            WAVES_FREEZING,
            WAVES_LINGERING,
            WEAPON_RESONLEVEL_COLOR,
            crop_center_img,
            get_square_weapon,
            get_attribute_effect,
        )

        BOT_COLOR = [
            WAVES_MOLTEN,
            AMBER,
            WAVES_VOID,
            WAVES_SIERRA,
            WAVES_FREEZING,
            WAVES_LINGERING,
            WAVES_MOONLIT,
        ]

        bot_color = copy.deepcopy(BOT_COLOR)
        bot_color_map = {}

        for index, rank_data in enumerate(char_data):
            # 調試：打印API返回的完整數據
            logger.info(f"[國際服排行] 玩家 {index+1} 數據: {rank_data}")

            bar_bg = bar.copy()
            bar_star_draw = ImageDraw.Draw(bar_bg)

            # 玩家頭像 (100, 0)
            # 使用Discord頭像處理邏輯
            discord_user_id = rank_data.get("discord_user_id", "")
            if discord_user_id:
                avatar_img = await get_discord_avatar_for_rank(discord_user_id, char_id)
            else:
                # 降級處理：使用UID
                user_id = rank_data.get("uid", "")
                avatar_img = await get_discord_avatar_for_rank(user_id, char_id)
            bar_bg.paste(avatar_img, (100, 0), avatar_img)

            # 角色屬性圖標 (300, 20)
            if role_attribute:
                bar_bg.alpha_composite(role_attribute, (300, 20))

            # 命座等級 (190, 30)
            resonance_chain = rank_data.get("resonance_chain", 0)
            from ..utils.image import CHAIN_COLOR

            info_block = Image.new("RGBA", (46, 20), color=(255, 255, 255, 0))
            info_block_draw = ImageDraw.Draw(info_block)
            fill = CHAIN_COLOR[resonance_chain] + (int(0.9 * 255),)
            info_block_draw.rounded_rectangle([0, 0, 46, 20], radius=6, fill=fill)

            def get_chain_name(n: int) -> str:
                return f"{n}链"

            info_block_draw.text(
                (5, 10),
                f"{get_chain_name(resonance_chain)}",
                "white",
                waves_font_18,
                "lm",
            )
            bar_bg.alpha_composite(info_block, (190, 30))

            # 角色等級 (240, 30)
            level = rank_data.get("level", 0)
            info_block = Image.new("RGBA", (60, 20), color=(255, 255, 255, 0))
            info_block_draw = ImageDraw.Draw(info_block)
            info_block_draw.rounded_rectangle(
                [0, 0, 60, 20], radius=6, fill=(54, 54, 54, int(0.9 * 255))
            )
            info_block_draw.text((5, 10), f"Lv.{level}", "white", waves_font_18, "lm")
            bar_bg.alpha_composite(info_block, (240, 30))

            # 聲骸分數 (545, 2) 和 (707, 45)
            phantom_score = rank_data.get("phantom_resonance_score", 0)
            if phantom_score > 0.0:
                # 聲骸分數背景
                score_bg = Image.open(TEXT_PATH / f"score_S.png")  # 默認使用S級
                bar_bg.alpha_composite(score_bg, (545, 2))
                bar_star_draw.text(
                    (707, 45),
                    f"{phantom_score:.2f}",
                    "white",
                    waves_font_34,
                    "mm",
                )
                bar_star_draw.text(
                    (707, 75), "声骸分数", SPECIAL_GOLD, waves_font_16, "mm"
                )

            # 合鳴效果 (790, 15) 和 (815, 75)
            sonata_name = rank_data.get("sonata_name", "")
            if sonata_name and sonata_name.strip() and sonata_name != "散件":
                try:
                    effect_image = await get_attribute_effect(sonata_name)
                    effect_image = effect_image.resize(
                        (50, 50), Image.Resampling.LANCZOS
                    )
                    bar_bg.alpha_composite(effect_image, (790, 15))
                except Exception as e:
                    # 嘗試使用別名轉換
                    from ..utils.name_convert import (
                        load_alias_data,
                        alias_to_sonata_name,
                    )

                    load_alias_data()
                    standard_sonata_name = alias_to_sonata_name(sonata_name)
                    if standard_sonata_name:
                        try:
                            effect_image = await get_attribute_effect(
                                standard_sonata_name
                            )
                            effect_image = effect_image.resize(
                                (50, 50), Image.Resampling.LANCZOS
                            )
                            bar_bg.alpha_composite(effect_image, (790, 15))
                            sonata_name = standard_sonata_name
                        except Exception as e2:
                            sonata_name = "合鸣效果"
                    else:
                        sonata_name = "合鸣效果"
            else:
                sonata_name = "合鸣效果"

            sonata_font = waves_font_16
            if len(sonata_name) > 4:
                sonata_font = waves_font_14
            bar_star_draw.text((815, 75), f"{sonata_name}", "white", sonata_font, "mm")

            # 武器信息 (850, 25)
            weapon_id = rank_data.get("weapon_id", 0)
            weapon_model = get_weapon_model(weapon_id)
            if weapon_model:
                weapon_bg_temp = Image.new("RGBA", (600, 300))
                weapon_icon = await get_square_weapon(weapon_id)
                weapon_icon = crop_center_img(weapon_icon, 110, 110)

                def get_weapon_icon_bg(star: int = 3) -> Image.Image:
                    if star == 5:
                        return Image.open(TEXT_PATH / "weapon_icon_bg_5.png")
                    elif star == 4:
                        return Image.open(TEXT_PATH / "weapon_icon_bg_4.png")
                    else:
                        return Image.open(TEXT_PATH / "weapon_icon_bg_3.png")

                weapon_icon_bg = get_weapon_icon_bg(weapon_model.starLevel)
                weapon_icon_bg.paste(weapon_icon, (10, 20), weapon_icon)

                weapon_bg_temp_draw = ImageDraw.Draw(weapon_bg_temp)
                weapon_bg_temp_draw.text(
                    (200, 30),
                    f"{weapon_model.name}",
                    SPECIAL_GOLD,
                    waves_font_34,
                    "lm",
                )
                weapon_bg_temp_draw.text(
                    (203, 75),
                    f"Lv.{rank_data.get('weapon_level', 0)}/90",
                    "white",
                    waves_font_30,
                    "lm",
                )

                # 武器精煉等級
                weapon_reson_level = rank_data.get("weapon_resonance_level", 1)
                _x = 220
                _y = 120
                wrc_fill = WEAPON_RESONLEVEL_COLOR[weapon_reson_level] + (
                    int(0.8 * 255),
                )
                weapon_bg_temp_draw.rounded_rectangle(
                    [_x - 15, _y - 15, _x + 50, _y + 15], radius=7, fill=wrc_fill
                )
                weapon_bg_temp_draw.text(
                    (_x, _y), f"精{weapon_reson_level}", "white", waves_font_24, "lm"
                )

                weapon_bg_temp.alpha_composite(weapon_icon_bg, dest=(45, 0))
                bar_bg.alpha_composite(
                    weapon_bg_temp.resize((260, 130), Image.Resampling.LANCZOS),
                    dest=(850, 25),
                )

            # 期望傷害 (1140, 45) 和 (1140, 75)
            expected_damage = rank_data.get("expected_damage", 0)
            expected_damage_name = rank_data.get("expected_damage_name", "期望伤害")
            bar_star_draw.text(
                (1140, 45),
                f"{expected_damage:,.0f}",
                SPECIAL_GOLD,
                waves_font_34,
                "mm",
            )
            bar_star_draw.text(
                (1140, 75), expected_damage_name, "white", waves_font_16, "mm"
            )

            # 排名 (40, 30)
            rank_id = index + 1
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
                    [0, 0, size[0], size[1]],
                    radius=8,
                    fill=rank_color + (int(0.9 * 255),),
                )
                rank_draw.text(draw, f"{rank_id}", "white", waves_font_34, "mm")
                bar_bg.alpha_composite(info_rank, dest)

            if rank_id > 999:
                draw_rank_id("999+", size=(100, 50), draw=(50, 24), dest=(10, 30))
            elif rank_id > 99:
                draw_rank_id(rank_id, size=(75, 50), draw=(37, 24), dest=(25, 30))
            else:
                draw_rank_id(rank_id, size=(50, 50), draw=(24, 24), dest=(40, 30))

            # 玩家名稱 (210, 75)
            player_name = rank_data.get(
                "username", rank_data.get("player_name", "未知玩家")
            )
            bar_star_draw.text(
                (210, 75), f"{player_name}", "white", waves_font_20, "lm"
            )

            # 特徵碼 (350, 40)
            uid = rank_data.get("uid", "")
            bar_star_draw.text(
                (350, 40), f"特征码: {uid}", "white", waves_font_20, "lm"
            )

            # bot主人名字 (350, 65)
            bot_name = rank_data.get("bot_name", "雅蘭娜")
            if bot_name:
                color = (54, 54, 54)
                if bot_name in bot_color_map:
                    color = bot_color_map[bot_name]
                elif bot_color:
                    color = bot_color.pop(0)
                    bot_color_map[bot_name] = color

                info_block = Image.new("RGBA", (200, 30), color=(255, 255, 255, 0))
                info_block_draw = ImageDraw.Draw(info_block)
                info_block_draw.rounded_rectangle(
                    [0, 0, 200, 30], radius=6, fill=color + (int(0.6 * 255),)
                )
                info_block_draw.text(
                    (100, 15), f"bot: {bot_name}", "white", waves_font_18, "mm"
                )
                bar_bg.alpha_composite(info_block, (350, 65))

            # 武器圖標和名稱 (850, 25)
            weapon_id = rank_data.get("weapon_id", 0)
            weapon_level = rank_data.get("weapon_level", 90)
            weapon_resonance_level = rank_data.get("weapon_resonance_level", 1)

            # 調試：打印武器相關數據
            logger.info(
                f"[國際服排行] 武器數據 - ID: {weapon_id}, Level: {weapon_level}, Resonance: {weapon_resonance_level}"
            )

            if weapon_id:
                try:
                    # 獲取武器模型
                    from ..utils.ascension.weapon import get_weapon_model

                    weapon_model = get_weapon_model(weapon_id)

                    if weapon_model:
                        # 武器背景
                        weapon_bg_temp = Image.new("RGBA", (600, 300))

                        # 武器圖標
                        weapon_icon = await get_square_weapon(weapon_id)
                        weapon_icon = crop_center_img(weapon_icon, 110, 110)
                        weapon_icon_bg = get_weapon_icon_bg(weapon_model.starLevel)
                        weapon_icon_bg.paste(weapon_icon, (10, 20), weapon_icon)

                        # 武器信息
                        weapon_bg_temp_draw = ImageDraw.Draw(weapon_bg_temp)
                        weapon_bg_temp_draw.text(
                            (200, 30),
                            f"{weapon_model.name}",
                            SPECIAL_GOLD,
                            waves_font_34,
                            "lm",
                        )
                        weapon_bg_temp_draw.text(
                            (203, 75),
                            f"Lv.{weapon_level}/90",
                            "white",
                            waves_font_30,
                            "lm",
                        )

                        # 武器精煉等級
                        _x = 220
                        _y = 120
                        wrc_fill = WEAPON_RESONLEVEL_COLOR[weapon_resonance_level] + (
                            int(0.8 * 255),
                        )
                        weapon_bg_temp_draw.rounded_rectangle(
                            [_x - 15, _y - 15, _x + 50, _y + 15],
                            radius=7,
                            fill=wrc_fill,
                        )
                        weapon_bg_temp_draw.text(
                            (_x, _y),
                            f"精{weapon_resonance_level}",
                            "white",
                            waves_font_24,
                            "lm",
                        )

                        # 組合武器圖標和背景
                        weapon_bg_temp.alpha_composite(weapon_icon_bg, dest=(45, 0))

                        # 貼到主背景
                        bar_bg.alpha_composite(
                            weapon_bg_temp.resize((260, 130), Image.Resampling.LANCZOS),
                            dest=(850, 25),
                        )
                    else:
                        logger.warning(f"武器ID {weapon_id} 無法找到對應的武器模型")
                except Exception as e:
                    logger.warning(f"武器圖標繪製失敗: {e}")

            # 貼到背景
            card_img.paste(
                bar_bg, (0, title_h + text_bar_h + index * bar_star_h), bar_bg
            )

            # 統計數據
            total_score += phantom_score
            total_damage += expected_damage

        # 繪製標題（與國服總排行相同結構）
        title = TITLE_II.copy()
        title_draw = ImageDraw.Draw(title)

        # 計算平均數據
        avg_score = f"{total_score / totalNum:.1f}" if totalNum != 0 else "0"
        avg_damage = f"{total_damage / totalNum:,.0f}" if totalNum != 0 else "0"

        title_draw.text((600, 335), f"{avg_score}", "white", waves_font_44, "mm")
        title_draw.text((600, 375), "平均聲骸分數", SPECIAL_GOLD, waves_font_20, "mm")

        title_draw.text((790, 335), f"{avg_damage}", "white", waves_font_44, "mm")
        title_draw.text((790, 375), "平均傷害", SPECIAL_GOLD, waves_font_20, "mm")

        title_name = f"{char}{rank_type}总排行"
        title_draw.text((540, 265), f"{title_name}", "black", waves_font_30, "lm")

        # 時間
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        title_draw.text((470, 205), f"{time_str}", GREY, waves_font_20, "lm")

        # 版本
        # 使用API版本號
        version = api_version

        info_block = Image.new("RGBA", (100, 30), color=(255, 255, 255, 0))
        info_block_draw = ImageDraw.Draw(info_block)
        info_block_draw.rounded_rectangle(
            [0, 0, 100, 30], radius=6, fill=(0, 79, 152, int(0.9 * 255))
        )
        info_block_draw.text((50, 15), f"v{version}", "white", waves_font_24, "mm")
        _x = 540 + 31 * len(title_name)
        title.alpha_composite(info_block, (_x, 255))

        # 添加標題到圖片（與國服總排行相同的處理方式）
        from ..utils.image import get_role_pile_old
        from ..utils.resource.constant import SPECIAL_CHAR_NAME

        # 獲取角色名稱
        char_name = char
        if char_id in SPECIAL_CHAR_NAME:
            char_name = SPECIAL_CHAR_NAME[char_id]

        # 添加logo
        logo_img = Image.open(TEXT_PATH / "logo_small_2.png")
        title.alpha_composite(logo_img.copy(), dest=(350, 65))

        # 處理角色立繪（與國服總排行相同）
        char_mask2 = Image.open(TEXT_PATH / "char_mask.png")
        char_mask2 = char_mask2.resize(
            (1300, char_mask2.size[1]), Image.Resampling.LANCZOS
        )

        img_temp = Image.new("RGBA", char_mask2.size)
        img_temp.alpha_composite(title, (-300, 0))

        # 人物立繪
        pile = await get_role_pile_old(char_id, custom=True)
        img_temp.alpha_composite(pile, (600, -120))

        img_temp2 = Image.new("RGBA", char_mask2.size)
        img_temp2.paste(img_temp, (0, 0), char_mask2.copy())

        card_img.alpha_composite(img_temp2, (0, 0))

        # 添加頁腳
        from ..utils.image import add_footer

        card_img = add_footer(card_img)

        return await convert_img(card_img)

    except Exception as e:
        logger.error(f"[國際服總排行] 圖片創建失敗: {e}")
        return f"[鳴潮] 國際服總排行圖片生成失敗: {str(e)}"


def draw_international_title():
    """繪製國際服總排行標題"""
    title_img = Image.new("RGBA", (1300, 500), color=(0, 0, 0, 0))
    title_draw = ImageDraw.Draw(title_img)

    # 繪製標題背景
    title_bg = TITLE_I.copy()
    title_img.alpha_composite(title_bg, (0, 0))

    # 繪製標題文字
    title_draw.text((650, 200), "國際服總排行", "white", waves_font_44, "mm")
    title_draw.text(
        (650, 250), "International Server Total Ranking", "white", waves_font_24, "mm"
    )

    return title_img


def draw_rank_conditions():
    """繪製上榜條件"""
    text_bar_h = 130
    text_bar_img = Image.new("RGBA", (1300, text_bar_h), color=(0, 0, 0, 0))
    text_bar_draw = ImageDraw.Draw(text_bar_img)

    # 繪製深灰色背景
    bar_bg_color = (36, 36, 41, 230)
    text_bar_draw.rounded_rectangle(
        [20, 20, 1280, text_bar_h - 15], radius=8, fill=bar_bg_color
    )

    # 繪製頂部的金色高亮線
    accent_color = (203, 161, 95)
    text_bar_draw.rectangle([20, 20, 1280, 26], fill=accent_color)

    # 左側標題
    text_bar_draw.text((40, 60), "上榜條件", GREY, waves_font_28, "lm")
    text_bar_draw.text(
        (185, 50), "1. 僅顯示國際服用戶", SPECIAL_GOLD, waves_font_20, "lm"
    )
    text_bar_draw.text(
        (185, 85), "2. 基於分析後上傳的數據", SPECIAL_GOLD, waves_font_20, "lm"
    )

    # 備註
    temp_notes = "排行標準：以期望傷害為排序的排名，僅顯示國際服用戶數據"
    text_bar_draw.text((1260, 100), temp_notes, SPECIAL_GOLD, waves_font_16, "rm")

    return text_bar_img


def draw_rank_item(draw, rank_data: dict, rank: int):
    """繪製單個排行項目"""
    # 排行位置
    draw.text((50, 50), f"#{rank}", "white", waves_font_30, "mm")

    # 角色名稱
    char_name = rank_data.get("character_name", "未知角色")
    draw.text((200, 30), char_name, "white", waves_font_24, "lm")

    # 玩家數量
    player_count = rank_data.get("player_count", 0)
    draw.text((200, 60), f"玩家數量: {player_count}", GREY, waves_font_16, "lm")

    # 最高傷害
    max_damage = rank_data.get("max_damage", 0)
    draw.text(
        (600, 30), f"最高傷害: {max_damage:,.0f}", SPECIAL_GOLD, waves_font_20, "lm"
    )

    # 平均傷害
    avg_damage = rank_data.get("avg_damage", 0)
    draw.text((600, 60), f"平均傷害: {avg_damage:,.0f}", GREY, waves_font_16, "lm")

    # 角色ID
    char_id = rank_data.get("character_id", 0)
    draw.text((1000, 50), f"ID: {char_id}", GREY, waves_font_16, "mm")
