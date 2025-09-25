import time
import asyncio
from typing import Dict
from pathlib import Path
from datetime import datetime, timedelta

import kuro
from kuro.types import Region
from gsuid_core.bot import Bot
from PIL import Image, ImageDraw
from gsuid_core.models import Event
from gsuid_core.logger import logger
from gsuid_core.utils.image.convert import convert_img
from gsuid_core.utils.image.image_tools import crop_center_img

from ..utils.waves_api import waves_api
from ..utils.api.request_util import KuroApiResp
from ..utils.resource.constant import SPECIAL_CHAR
from ..utils.name_convert import char_name_to_char_id
from ..utils.api.model import DailyData, AccountBaseInfo
from ..utils.database.models import WavesBind, WavesUser
from ..wutheringwaves_config.set_config import set_push_time
from ..utils.error_reply import ERROR_CODE, WAVES_CODE_102, WAVES_CODE_103
from ..utils.image import (
    RED,
    GOLD,
    GREY,
    GREEN,
    YELLOW,
    add_footer,
    get_event_avatar,
    get_random_waves_role_pile,
)
from ..utils.fonts.waves_fonts import (
    waves_font_24,
    waves_font_25,
    waves_font_26,
    waves_font_30,
    waves_font_32,
    waves_font_42,
)

TEXT_PATH = Path(__file__).parent / "texture2d"
YES = Image.open(TEXT_PATH / "yes.png")
YES = YES.resize((40, 40))
NO = Image.open(TEXT_PATH / "no.png")
NO = NO.resize((40, 40))
bar_down = Image.open(TEXT_PATH / "bar_down.png")

based_w = 1150
based_h = 850


async def seconds2hours(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return "%02d小时%02d分" % (h, m)


async def process_uid(uid, ev):
    ck = await waves_api.get_self_waves_ck(uid, ev.user_id, ev.bot_id)
    if not ck:
        return None

    # 并行请求所有相关 API
    results = await asyncio.gather(
        waves_api.get_daily_info(uid, ck),
        waves_api.get_base_info(uid, ck),
        return_exceptions=True,
    )

    (daily_info_res, account_info_res) = results
    if not isinstance(daily_info_res, KuroApiResp) or not daily_info_res.success:
        return None

    if not isinstance(account_info_res, KuroApiResp) or not account_info_res.success:
        return None

    daily_info = DailyData.model_validate(daily_info_res.data)
    account_info = AccountBaseInfo.model_validate(account_info_res.data)

    return {
        "daily_info": daily_info,
        "account_info": account_info,
    }


async def draw_stamina_img(bot: Bot, ev: Event):
    try:
        uid_list = await WavesBind.get_uid_list_by_game(ev.user_id, ev.bot_id)
        logger.info(f"[鸣潮][每日信息]UID: {uid_list}")
        if uid_list is None:
            return ERROR_CODE[WAVES_CODE_103]
        # 进行校验UID是否绑定CK
        tasks = [process_uid(uid, ev) for uid in uid_list]
        results = await asyncio.gather(*tasks)

        # 过滤掉 None 值
        valid_daily_list = [res for res in results if res is not None]

        if len(valid_daily_list) == 0:
            return ERROR_CODE[WAVES_CODE_102]

        # 开始绘图任务
        task = []
        img = Image.new(
            "RGBA", (based_w, based_h * len(valid_daily_list)), (0, 0, 0, 0)
        )
        for uid_index, valid in enumerate(valid_daily_list):
            task.append(_draw_all_stamina_img(ev, img, valid, uid_index))
        await asyncio.gather(*task)
        res = await convert_img(img)
        logger.info("[鸣潮][每日信息]绘图已完成,等待发送!")
    except TypeError:
        logger.exception("[鸣潮][每日信息]绘图失败!")
        res = "你绑定过的UID中可能存在过期CK~请重新绑定一下噢~"

    return res


async def _draw_all_stamina_img(ev: Event, img: Image.Image, valid: Dict, index: int):
    stamina_img = await _draw_stamina_img(ev, valid)
    stamina_img = stamina_img.convert("RGBA")
    img.paste(stamina_img, (0, based_h * index), stamina_img)


async def _draw_stamina_img(ev: Event, valid: Dict) -> Image.Image:
    daily_info: DailyData = valid["daily_info"]
    account_info: AccountBaseInfo = valid["account_info"]
    if daily_info.hasSignIn:
        sign_in_icon = YES
        sing_in_text = "签到已完成！"
    else:
        sign_in_icon = NO
        sing_in_text = "今日未签到！"

    if (
        daily_info.livenessData.total != 0
        and daily_info.livenessData.cur == daily_info.livenessData.total
    ):
        active_icon = YES
        active_text = "活跃度已满！"
    else:
        active_icon = NO
        active_text = "活跃度未满！"

    img = Image.open(TEXT_PATH / "bg.jpg").convert("RGBA")
    info = Image.open(TEXT_PATH / "main_bar.png").convert("RGBA")
    base_info_bg = Image.open(TEXT_PATH / "base_info_bg.png")
    avatar_ring = Image.open(TEXT_PATH / "avatar_ring.png")

    # 头像
    avatar = await draw_pic_with_ring(ev)

    # 随机获得pile
    user = await WavesUser.get_user_by_attr(
        ev.user_id, ev.bot_id, "uid", daily_info.roleId
    )
    pile_id = None
    if user and user.stamina_bg_value:
        char_id = char_name_to_char_id(user.stamina_bg_value)
        if char_id in SPECIAL_CHAR:
            ck = await waves_api.get_self_waves_ck(
                daily_info.roleId, ev.user_id, ev.bot_id
            )
            if ck:
                for char_id in SPECIAL_CHAR[char_id]:
                    role_detail_info = await waves_api.get_role_detail_info(
                        char_id, daily_info.roleId, ck
                    )
                    if not role_detail_info.success:
                        continue
                    role_detail_info = role_detail_info.data
                    if (
                        not isinstance(role_detail_info, Dict)
                        or "role" not in role_detail_info
                        or role_detail_info["role"] is None
                        or "level" not in role_detail_info
                        or role_detail_info["level"] is None
                    ):
                        continue
                    pile_id = char_id
                    break
        else:
            pile_id = char_id
    pile = await get_random_waves_role_pile(pile_id)
    # pile = pile.crop((0, 0, pile.size[0], pile.size[1] - 155))

    base_info_draw = ImageDraw.Draw(base_info_bg)
    base_info_draw.text(
        (275, 120), f"{daily_info.roleName[:7]}", GREY, waves_font_30, "lm"
    )
    base_info_draw.text(
        (226, 173), f"特征码:  {daily_info.roleId}", GOLD, waves_font_25, "lm"
    )
    # 账号基本信息，由于可能会没有，放在一起

    title_bar = Image.open(TEXT_PATH / "title_bar.png")
    title_bar_draw = ImageDraw.Draw(title_bar)
    title_bar_draw.text((480, 125), "战歌重奏", GREY, waves_font_26, "mm")
    color = RED if account_info.weeklyInstCount != 0 else GREEN
    if (
        account_info.weeklyInstCountLimit is not None
        and account_info.weeklyInstCount is not None
    ):
        title_bar_draw.text(
            (480, 78),
            f"{account_info.weeklyInstCountLimit - account_info.weeklyInstCount} / {account_info.weeklyInstCountLimit}",
            color,
            waves_font_42,
            "mm",
        )

    title_bar_draw.text((630, 125), "先约电台", GREY, waves_font_26, "mm")
    title_bar_draw.text(
        (630, 78),
        f"Lv.{daily_info.battlePassData[0].cur}",
        "white",
        waves_font_42,
        "mm",
    )

    # logo_img = get_small_logo(2)
    # title_bar.alpha_composite(logo_img, dest=(760, 60))

    color = RED if account_info.rougeScore != account_info.rougeScoreLimit else GREEN
    title_bar_draw.text((810, 125), "千道门扉的异想", GREY, waves_font_26, "mm")
    title_bar_draw.text(
        (810, 78),
        f"{account_info.rougeScore}/{account_info.rougeScoreLimit}",
        color,
        waves_font_32,
        "mm",
    )

    # 体力剩余恢复时间
    active_draw = ImageDraw.Draw(info)
    curr_time = int(time.time())
    refreshTimeStamp = (
        daily_info.energyData.refreshTimeStamp
        if daily_info.energyData.refreshTimeStamp
        else curr_time
    )
    # remain_time = await seconds2hours(refreshTimeStamp - curr_time)
    # 设置体力推送时间
    push_bool = await set_push_time(ev.bot_id, daily_info.roleId, refreshTimeStamp)
    if push_bool:
        push_icon = YES
        push_text = "体力推送开启"
    else:
        push_icon = NO
        push_text = "体力推送关闭"

    time_img = Image.new("RGBA", (190, 33), (255, 255, 255, 0))
    time_img_draw = ImageDraw.Draw(time_img)
    time_img_draw.rounded_rectangle(
        [0, 0, 190, 33], radius=15, fill=(186, 55, 42, int(0.7 * 255))
    )
    if refreshTimeStamp != curr_time:
        date_from_timestamp = datetime.fromtimestamp(refreshTimeStamp)
        now = datetime.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)

        remain_time = datetime.fromtimestamp(refreshTimeStamp).strftime(
            "%m.%d %H:%M:%S"
        )
        if date_from_timestamp.date() == today:
            remain_time = "今天 " + datetime.fromtimestamp(refreshTimeStamp).strftime(
                "%H:%M:%S"
            )
        elif date_from_timestamp.date() == tomorrow:
            remain_time = "明天 " + datetime.fromtimestamp(refreshTimeStamp).strftime(
                "%H:%M:%S"
            )

        time_img_draw.text((10, 15), f"{remain_time}", "white", waves_font_24, "lm")
    else:
        time_img_draw.text((10, 15), "漂泊者该上潮了", "white", waves_font_24, "lm")

    info.alpha_composite(time_img, (280, 50))

    max_len = 345
    # 体力
    active_draw.text(
        (350, 115), f"/{daily_info.energyData.total}", GREY, waves_font_30, "lm"
    )
    active_draw.text(
        (348, 115), f"{daily_info.energyData.cur}", GREY, waves_font_30, "rm"
    )
    radio = daily_info.energyData.cur / daily_info.energyData.total
    color = RED if radio > 0.8 else YELLOW
    active_draw.rectangle((173, 142, int(173 + radio * max_len), 150), color)

    # 结晶单质
    active_draw.text(
        (350, 230), f"/{account_info.storeEnergyLimit}", GREY, waves_font_30, "lm"
    )
    active_draw.text(
        (348, 230), f"{account_info.storeEnergy}", GREY, waves_font_30, "rm"
    )
    radio = (
        account_info.storeEnergy / account_info.storeEnergyLimit
        if account_info.storeEnergyLimit is not None
        and account_info.storeEnergy is not None
        and account_info.storeEnergyLimit != 0
        else 0
    )
    color = RED if radio > 0.8 else YELLOW
    active_draw.rectangle((173, 254, int(173 + radio * max_len), 262), color)

    # 活跃度
    active_draw.text(
        (350, 350), f"/{daily_info.livenessData.total}", GREY, waves_font_30, "lm"
    )
    active_draw.text(
        (348, 350), f"{daily_info.livenessData.cur}", GREY, waves_font_30, "rm"
    )
    radio = (
        daily_info.livenessData.cur / daily_info.livenessData.total
        if daily_info.livenessData.total != 0
        else 0
    )
    active_draw.rectangle((173, 374, int(173 + radio * max_len), 382), YELLOW)

    # 签到状态
    status_img = Image.new("RGBA", (230, 40), (255, 255, 255, 0))
    status_img_draw = ImageDraw.Draw(status_img)
    status_img_draw.rounded_rectangle([0, 0, 230, 40], fill=(0, 0, 0, int(0.3 * 255)))
    status_img.alpha_composite(sign_in_icon, (0, 0))
    status_img_draw.text((50, 20), f"{sing_in_text}", "white", waves_font_30, "lm")
    img.alpha_composite(status_img, (70, 80))

    # 活跃状态
    status_img2 = Image.new("RGBA", (230, 40), (255, 255, 255, 0))
    status_img2_draw = ImageDraw.Draw(status_img2)
    status_img2_draw.rounded_rectangle([0, 0, 230, 40], fill=(0, 0, 0, int(0.3 * 255)))
    status_img2.alpha_composite(active_icon, (0, 0))
    status_img2_draw.text((50, 20), f"{active_text}", "white", waves_font_30, "lm")
    img.alpha_composite(status_img2, (70, 120))

    # 体力推送状态
    status_img3 = Image.new("RGBA", (230, 40), (255, 255, 255, 0))
    status_img3_draw = ImageDraw.Draw(status_img3)
    status_img3_draw.rounded_rectangle([0, 0, 230, 40], fill=(0, 0, 0, int(0.3 * 255)))
    status_img3.alpha_composite(push_icon, (0, 0))
    status_img3_draw.text((50, 20), f"{push_text}", "white", waves_font_30, "lm")
    img.alpha_composite(status_img3, (70, 160))

    # bbs状态
    # status_img3 = Image.new("RGBA", (300, 40), (255, 255, 255, 0))
    # status_img3_draw = ImageDraw.Draw(status_img3)
    # status_img3_draw.rounded_rectangle([0, 0, 300, 40], fill=(0, 0, 0, int(0.3 * 255)))
    # status_img3.alpha_composite(bbs_icon, (0, 0))
    # status_img3_draw.text((50, 20), f"{bbs_text}", "white", waves_font_30, "lm")
    # img.alpha_composite(status_img3, (70, 80))

    # pile 放在背景上
    img.paste(pile, (550, -150), pile)
    # 贴个bar_down
    img.alpha_composite(bar_down, (0, 0))
    # info 放在背景上
    img.paste(info, (0, 190), info)
    # base_info 放在背景上
    img.paste(base_info_bg, (40, 570), base_info_bg)
    # avatar_ring 放在背景上
    img.paste(avatar_ring, (40, 620), avatar_ring)
    img.paste(avatar, (40, 620), avatar)
    # account_info 放背景上
    img.paste(title_bar, (190, 620), title_bar)
    img = add_footer(img, 600, 25)
    return img


async def draw_pic_with_ring(ev: Event):
    pic = await get_event_avatar(ev, is_valid_at_param=False)

    mask_pic = Image.open(TEXT_PATH / "avatar_mask.png")
    img = Image.new("RGBA", (200, 200))
    mask = mask_pic.resize((160, 160))
    resize_pic = crop_center_img(pic, 160, 160)
    img.paste(resize_pic, (20, 20), mask)

    return img


async def draw_international_stamina_img(bot: Bot, ev: Event, user: WavesUser):
    """國際服體力查詢"""
    try:
        logger.info(f"[鸣潮][國際服體力查詢]UID: {user.uid}")
        logger.info(
            f"[鸣潮][國際服體力查詢]Token 長度: {len(user.cookie) if user.cookie else 0}"
        )

        # 檢查 token 是否有效
        if not user.cookie or len(user.cookie) < 10:
            return "❌ 登入 token 無效，請重新登入國際服"

        # 創建 kuro 客戶端
        client = kuro.Client(region=Region.OVERSEAS)

        # 生成 OAuth code
        logger.info(f"[鸣潮][國際服體力查詢]生成 OAuth code...")
        try:
            oauth_code = await client.generate_oauth_code(user.cookie)
            logger.info(f"[鸣潮][國際服體力查詢]OAuth code 生成成功")
        except kuro.errors.KuroError as e:
            logger.error(f"[鸣潮][國際服體力查詢]OAuth 生成失敗: {e}")
            if "Unknown error occurred" in str(e):
                return "❌ 登入 token 已過期，請重新登入國際服"
            else:
                return f"❌ OAuth 生成失敗: {str(e)}"
        except Exception as e:
            logger.error(f"[鸣潮][國際服體力查詢]OAuth 生成異常: {e}")
            return f"❌ OAuth 生成異常: {str(e)}"

        # 獲取角色信息
        logger.info(f"[鸣潮][國際服體力查詢]獲取角色信息...")
        
        # 從 platform 字段中提取服務器區域
        server_region = "Asia"  # 默認值
        if user.platform and user.platform.startswith("international_"):
            server_region = user.platform.replace("international_", "")
            logger.info(f"[鸣潮][國際服體力查詢]使用服務器區域: {server_region}")
        
        try:
            role_info = await client.get_player_role(oauth_code, int(user.uid), server_region)
            logger.info(f"[鸣潮][國際服體力查詢]角色信息獲取成功")
        except kuro.errors.KuroError as e:
            logger.error(f"[鸣潮][國際服體力查詢]角色信息獲取失敗: {e}")
            return f"❌ 角色信息獲取失敗: {str(e)}"
        except Exception as e:
            logger.error(f"[鸣潮][國際服體力查詢]角色信息獲取異常: {e}")
            return f"❌ 角色信息獲取異常: {str(e)}"

        # 提取體力信息
        basic_info = role_info.basic
        current_stamina = basic_info.waveplates
        max_stamina = basic_info.max_waveplates
        refined_stamina = basic_info.refined_waveplates

        # 生成圖像
        logger.info(f"[鸣潮][國際服體力查詢]開始生成圖像...")
        img = await _draw_international_stamina_img(ev, role_info, user)
        logger.info(f"[鸣潮][國際服體力查詢]圖像生成完成")

        # 轉換為可發送的格式
        res = await convert_img(img)
        return res

    except Exception as e:
        logger.error(f"[鸣潮][國際服體力查詢]失敗: {e}")
        logger.error(f"[鸣潮][國際服體力查詢]錯誤類型: {type(e).__name__}")
        logger.error(f"[鸣潮][國際服體力查詢]錯誤詳情: {str(e)}")

        # 返回更詳細的錯誤信息
        error_msg = f"❌ 國際服體力查詢失敗\n\n錯誤類型: {type(e).__name__}\n錯誤詳情: {str(e)}\n\n請檢查:\n1. 登入是否有效\n2. 網絡連接是否正常\n3. 遊戲服務器是否可用"
        return error_msg


async def _draw_international_stamina_img(
    ev: Event, role_info, user: WavesUser
) -> Image.Image:
    """生成國際服體力查詢圖像"""
    basic_info = role_info.basic

    # 載入背景圖片
    img = Image.open(TEXT_PATH / "bg.jpg").convert("RGBA")
    info = Image.open(TEXT_PATH / "main_bar.png").convert("RGBA")
    base_info_bg = Image.open(TEXT_PATH / "base_info_bg.png")
    avatar_ring = Image.open(TEXT_PATH / "avatar_ring.png")

    # 用戶頭像
    avatar = await draw_pic_with_ring(ev)

    # 隨機角色立繪
    pile = await get_random_waves_role_pile(None)

    # 基本信息背景
    base_info_draw = ImageDraw.Draw(base_info_bg)
    base_info_draw.text((275, 120), f"{basic_info.name[:7]}", GREY, waves_font_30, "lm")
    base_info_draw.text((226, 173), f"特征码:  {user.uid}", GOLD, waves_font_25, "lm")

    # 標題欄
    title_bar = Image.open(TEXT_PATH / "title_bar.png")
    title_bar_draw = ImageDraw.Draw(title_bar)

    # 戰歌重奏 (weekly_challenge)
    title_bar_draw.text((480, 125), "戰歌重奏", GREY, waves_font_26, "mm")
    weekly_challenge = basic_info.weekly_challenge
    color_weekly = RED if weekly_challenge != 0 else GREEN
    title_bar_draw.text(
        (480, 78), f"{weekly_challenge}/3", color_weekly, waves_font_42, "mm"
    )

    # 先約電台 (battle_pass.level)
    title_bar_draw.text((630, 125), "先約電台", GREY, waves_font_26, "mm")
    battle_pass_level = role_info.battle_pass.level
    title_bar_draw.text(
        (630, 78), f"Lv.{battle_pass_level}", "white", waves_font_42, "mm"
    )

    # 千道門扉的異想 (國際服不支援，顯示0)
    title_bar_draw.text((810, 125), "千道門扉的異想", GREY, waves_font_26, "mm")
    title_bar_draw.text((810, 78), "0/6000", RED, waves_font_32, "mm")

    # 體力信息
    active_draw = ImageDraw.Draw(info)
    current_stamina = basic_info.waveplates
    max_stamina = basic_info.max_waveplates
    refined_stamina = basic_info.refined_waveplates

    # 體力條
    active_draw.text((350, 115), f"/{max_stamina}", GREY, waves_font_30, "lm")
    active_draw.text((348, 115), f"{current_stamina}", GREY, waves_font_30, "rm")
    radio = current_stamina / max_stamina if max_stamina > 0 else 0
    color = RED if radio > 0.8 else YELLOW
    max_len = 345
    active_draw.rectangle((173, 142, int(173 + radio * max_len), 150), color)

    # 精煉體力條 (結晶單質，最大值為 480)
    max_refined_stamina = 480
    active_draw.text((350, 230), f"/{max_refined_stamina}", GREY, waves_font_30, "lm")
    active_draw.text((348, 230), f"{refined_stamina}", GREY, waves_font_30, "rm")
    radio_refined = (
        refined_stamina / max_refined_stamina if max_refined_stamina > 0 else 0
    )
    color_refined = RED if radio_refined > 0.8 else YELLOW
    active_draw.rectangle(
        (173, 254, int(173 + radio_refined * max_len), 262), color_refined
    )

    # 活躍度 (使用國際服的 activity_points)
    activity_points = basic_info.activity_points
    max_activity_points = basic_info.max_activity_points
    active_draw.text((350, 350), f"/{max_activity_points}", GREY, waves_font_30, "lm")
    active_draw.text((348, 350), f"{activity_points}", GREY, waves_font_30, "rm")
    radio_active = (
        activity_points / max_activity_points if max_activity_points > 0 else 0
    )
    active_draw.rectangle((173, 374, int(173 + radio_active * max_len), 382), YELLOW)

    # 體力恢復時間
    time_img = Image.new("RGBA", (190, 33), (255, 255, 255, 0))
    time_img_draw = ImageDraw.Draw(time_img)
    time_img_draw.rounded_rectangle(
        [0, 0, 190, 33], radius=15, fill=(186, 55, 42, int(0.7 * 255))
    )

    # 處理體力恢復時間
    # 檢查體力是否已滿
    if current_stamina >= max_stamina:
        time_img_draw.text((10, 15), "體力已滿", "white", waves_font_24, "lm")
    else:
        # 體力未滿，顯示恢復時間
        replenish_time = basic_info.waveplates_replenish_time
        if replenish_time and replenish_time != 0:
            try:
                # 假設 replenish_time 是時間戳
                date_from_timestamp = datetime.fromtimestamp(replenish_time)
                now = datetime.now()
                today = now.date()
                tomorrow = today + timedelta(days=1)

                remain_time = datetime.fromtimestamp(replenish_time).strftime(
                    "%m.%d %H:%M:%S"
                )
                if date_from_timestamp.date() == today:
                    remain_time = "今天 " + datetime.fromtimestamp(
                        replenish_time
                    ).strftime("%H:%M:%S")
                elif date_from_timestamp.date() == tomorrow:
                    remain_time = "明天 " + datetime.fromtimestamp(
                        replenish_time
                    ).strftime("%H:%M:%S")

                time_img_draw.text(
                    (10, 15), f"{remain_time}", "white", waves_font_24, "lm"
                )
            except:
                # 如果時間解析失敗，顯示體力未滿的提示
                time_img_draw.text((10, 15), "體力恢復中", "white", waves_font_24, "lm")
        else:
            # 如果沒有恢復時間信息，顯示體力未滿的提示
            time_img_draw.text((10, 15), "體力恢復中", "white", waves_font_24, "lm")

    info.alpha_composite(time_img, (280, 50))

    # 狀態圖標
    # 簽到狀態 (國際服可能沒有簽到功能，顯示為已完成)
    sign_in_icon = YES
    sing_in_text = "國際服模式"

    # 活躍狀態
    character_count = basic_info.character_count
    active_icon = YES if character_count > 0 else NO
    active_text = "角色已解鎖" if character_count > 0 else "無角色數據"

    # 推送狀態
    push_icon = YES
    push_text = "體力推送開啟"

    # 簽到狀態
    status_img = Image.new("RGBA", (230, 40), (255, 255, 255, 0))
    status_img_draw = ImageDraw.Draw(status_img)
    status_img_draw.rounded_rectangle([0, 0, 230, 40], fill=(0, 0, 0, int(0.3 * 255)))
    status_img.alpha_composite(sign_in_icon, (0, 0))
    status_img_draw.text((50, 20), f"{sing_in_text}", "white", waves_font_30, "lm")
    img.alpha_composite(status_img, (70, 80))

    # 活躍狀態
    status_img2 = Image.new("RGBA", (230, 40), (255, 255, 255, 0))
    status_img2_draw = ImageDraw.Draw(status_img2)
    status_img2_draw.rounded_rectangle([0, 0, 230, 40], fill=(0, 0, 0, int(0.3 * 255)))
    status_img2.alpha_composite(active_icon, (0, 0))
    status_img2_draw.text((50, 20), f"{active_text}", "white", waves_font_30, "lm")
    img.alpha_composite(status_img2, (70, 120))

    # 推送狀態
    status_img3 = Image.new("RGBA", (230, 40), (255, 255, 255, 0))
    status_img3_draw = ImageDraw.Draw(status_img3)
    status_img3_draw.rounded_rectangle([0, 0, 230, 40], fill=(0, 0, 0, int(0.3 * 255)))
    status_img3.alpha_composite(push_icon, (0, 0))
    status_img3_draw.text((50, 20), f"{push_text}", "white", waves_font_30, "lm")
    img.alpha_composite(status_img3, (70, 160))

    # 組合所有元素
    img.paste(pile, (550, -150), pile)
    img.alpha_composite(bar_down, (0, 0))
    img.paste(info, (0, 190), info)
    img.paste(base_info_bg, (40, 570), base_info_bg)
    img.paste(avatar_ring, (40, 620), avatar_ring)
    img.paste(avatar, (40, 620), avatar)
    img.paste(title_bar, (190, 620), title_bar)
    img = add_footer(img, 600, 25)

    return img
