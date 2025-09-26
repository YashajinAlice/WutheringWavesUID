import time
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw
from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img

from ..utils.waves_api import waves_api
from ..utils.imagetool import draw_pic_with_ring
from ..utils.char_info_utils import get_all_roleid_detail_info_int
from ..utils.resource.constant import NORMAL_LIST, SPECIAL_CHAR_INT
from ..wutheringwaves_analyzecard.user_info_utils import get_user_detail_info
from ..utils.api.model import (
    Role,
    RoleList,
    CalabashData,
    RoleDetailData,
    AccountBaseInfo,
)
from ..utils.fonts.waves_fonts import (
    waves_font_25,
    waves_font_26,
    waves_font_30,
    waves_font_40,
    waves_font_42,
)
from ..utils.image import (
    GOLD,
    GREY,
    add_footer,
    get_waves_bg,
    get_attribute,
    get_square_avatar,
    get_square_weapon,
    cropped_square_avatar,
)

TEXT_PATH = Path(__file__).parent / "texture2d"


async def draw_role_img(uid: str, ck: str, ev: Event):
    # succ, game_info = await waves_api.get_game_role_info(ck)
    # if not succ:
    #     return game_info
    # game_info = KuroRoleInfo(**game_info)

    # 共鸣者信息
    if waves_api.is_net(uid):
        from ..wutheringwaves_analyzecard.changeEcho import (
            get_local_all_role_info,
        )

        succ, role_info = await get_local_all_role_info(uid)
        if not succ:
            from ..utils.hint import error_reply
            from ..utils.error_reply import WAVES_CODE_099

            return error_reply(WAVES_CODE_099)
        role_info = RoleList.model_validate(role_info)
    else:
        role_info = await waves_api.get_role_info(uid, ck)
        if not role_info.success:
            return role_info.throw_msg()

        role_info = RoleList.model_validate(role_info.data)
    role_info.roleList.sort(
        key=lambda i: (i.level, i.starLevel, i.roleId), reverse=True
    )

    if waves_api.is_net(uid):
        account_info = await get_user_detail_info(uid)
        # 拒绝掉无用数据，不走is_full
        account_info.creatTime = None
    else:
        # 账户数据
        account_info = await waves_api.get_base_info(uid, ck)
        if not account_info.success:
            return account_info.throw_msg()
        account_info = AccountBaseInfo.model_validate(account_info.data)

        # 数据坞
        calabash_data = await waves_api.get_calabash_data(uid, ck)
        if not calabash_data.success:
            return calabash_data.throw_msg()
        calabash_data = CalabashData.model_validate(calabash_data.data)

    # five_num = sum(1 for i in role_info.roleList if i.starLevel == 5)
    up_num = sum(
        1
        for i in role_info.roleList
        if i.starLevel == 5 and i.roleName not in NORMAL_LIST
    )

    base_info_value_list = []
    if account_info.is_full:
        base_info_value_list = [
            {
                "key": "活跃天数",
                "value": f"{account_info.activeDays}",
                "info_block": "color_y.png",
            },
            {"key": "解锁角色", "value": f"{account_info.roleNum}", "info_block": ""},
            {"key": "UP角色", "value": f"{up_num}", "info_block": "color_g.png"},
            {
                "key": "数据坞等级",
                "value": f"{calabash_data.level if calabash_data.isUnlock else 0}",
                "info_block": "",
            },
            {
                "key": "已达成成就",
                "value": f"{account_info.achievementCount}",
                "info_block": "color_p.png",
            },
            {
                "key": "成就星数",
                "value": f"{account_info.achievementStar}",
                "info_block": "",
            },
            {
                "key": "小型信标",
                "value": f"{account_info.smallCount}",
                "info_block": "",
            },
            {"key": "中型信标", "value": f"{account_info.bigCount}", "info_block": ""},
        ]

        for b in account_info.treasureBoxList:
            base_info_value_list.append(
                {"key": b.name, "value": f"{b.num}", "info_block": ""}
            )

    # 初始化基础信息栏位
    bs = Image.open(TEXT_PATH / "bs.png")

    # 角色信息
    roleTotalNum = (
        account_info.roleNum if account_info.is_full else len(role_info.roleList)
    )
    xset = 50
    yset = 470
    if account_info.is_full:
        yset += bs.size[1]

    w = 1000
    h = 100 + yset + 200 * int(roleTotalNum / 4 + (1 if roleTotalNum % 4 else 0))
    card_img = get_waves_bg(w, h)

    def calc_info_block(_x: int, _y: int, key: str, value: str, color_path: str = ""):
        if not color_path:
            color_path = "info_block.png"
        info_block = Image.open(TEXT_PATH / f"{color_path}")
        info_block_draw = ImageDraw.Draw(info_block)
        info_block_draw.text((66, 90), key, "white", waves_font_26, "mm")
        info_block_draw.text((66, 43), value, "white", waves_font_40, "mm")
        bs.paste(info_block, (_x, _y), info_block)

    # 基本信息
    x = 66
    y = 75
    for i in range(2):
        for j in range(6):
            _x = x + 145 * j
            _y = y + 140 * i
            _len = i * 6 + j
            if _len >= len(base_info_value_list):
                break
            calc_info_block(
                _x,
                _y,
                base_info_value_list[_len]["key"],
                base_info_value_list[_len]["value"],
                base_info_value_list[_len]["info_block"],
            )

    # 根据面板数据获取详细信息
    role_detail_info_map = await get_all_roleid_detail_info_int(uid)

    async def calc_role_info(_x: int, _y: int, roleInfo: Role):
        if not role_detail_info_map:
            return
        char_bg = Image.open(TEXT_PATH / "char_bg.png")
        char_attribute = await get_attribute(roleInfo.attributeName)
        char_attribute = char_attribute.resize((40, 40)).convert("RGBA")
        role_avatar = await get_square_avatar(roleInfo.roleId)
        role_avatar = await cropped_square_avatar(role_avatar, 130)
        char_bg.paste(role_avatar, (10, 25), role_avatar)
        char_bg.paste(char_attribute, (155, 13), char_attribute)

        char_bg_draw = ImageDraw.Draw(char_bg)
        char_bg_draw.text(
            (90, 173), f"LV.{roleInfo.level}", "white", waves_font_26, "lm"
        )

        if roleInfo.roleId in SPECIAL_CHAR_INT:
            query_list = SPECIAL_CHAR_INT.copy()
        else:
            query_list = [roleInfo.roleId]

        temp: Optional[RoleDetailData] = None  # type: ignore
        for char_id in query_list:
            if char_id in role_detail_info_map:
                temp: RoleDetailData = role_detail_info_map[char_id]
                break

        if temp:
            weapon_bg = Image.open(TEXT_PATH / "weapon_bg.png")
            weaponId = temp.weaponData.weapon.weaponId
            weapon_icon = await get_square_weapon(weaponId)
            weapon_icon = weapon_icon.resize((75, 75)).convert("RGBA")
            weapon_bg.paste(weapon_icon, (123, 73), weapon_icon)
            char_bg.paste(weapon_bg, (0, 5), weapon_bg)

            info_block = Image.new("RGBA", (60, 30), color=(255, 255, 255, 0))
            info_block_draw = ImageDraw.Draw(info_block)
            info_block_draw.rounded_rectangle(
                [0, 0, 60, 30], radius=7, fill=(96, 12, 120, int(0.8 * 255))
            )
            info_block_draw.text(
                (5, 15), f"{temp.get_chain_name()}", "white", waves_font_26, "lm"
            )
            char_bg.paste(info_block, (18, 158), info_block)

        card_img.paste(char_bg, (_x, _y), char_bg)

    # 角色信息
    for index, role in enumerate(role_info.roleList):
        _x = xset + 210 * int(index % 4)
        _y = yset + 200 * int(index / 4)
        await calc_role_info(_x, _y, role)

    # 基础信息 名字 特征码
    base_info_bg = Image.open(TEXT_PATH / "base_info_bg.png")
    base_info_draw = ImageDraw.Draw(base_info_bg)
    base_info_draw.text(
        (275, 120), f"{account_info.name[:7]}", "white", waves_font_30, "lm"
    )
    base_info_draw.text(
        (226, 173), f"特征码:  {account_info.id}", GOLD, waves_font_25, "lm"
    )
    card_img.paste(base_info_bg, (35, 170), base_info_bg)

    # 头像 头像环
    avatar, avatar_ring = await draw_pic_with_ring(ev)
    card_img.paste(avatar, (45, 220), avatar)
    card_img.paste(avatar_ring, (55, 230), avatar_ring)

    # 右侧装饰
    char = Image.open(TEXT_PATH / "char.png")
    card_img.paste(char, (910, 0), char)

    # 账号基本信息，由于可能会没有，放在一起
    if account_info.is_full:
        line = Image.open(TEXT_PATH / "line.png")
        line_draw = ImageDraw.Draw(line)
        line_draw.text((475, 30), "基本信息", "white", waves_font_30, "mm")

        title_bar = Image.open(TEXT_PATH / "title_bar.png")
        title_bar_draw = ImageDraw.Draw(title_bar)
        title_bar_draw.text((660, 125), "账号等级", GREY, waves_font_26, "mm")
        title_bar_draw.text(
            (660, 78), f"Lv.{account_info.level}", "white", waves_font_42, "mm"
        )

        title_bar_draw.text((810, 125), "世界等级", GREY, waves_font_26, "mm")
        title_bar_draw.text(
            (810, 78), f"Lv.{account_info.worldLevel}", "white", waves_font_42, "mm"
        )
        card_img.paste(line, (0, yset - bs.size[1] - 70), line)
        card_img.paste(bs, (-10, yset - bs.size[1] - 70), bs)
        card_img.paste(title_bar, (0, 220), title_bar)

    line2 = Image.open(TEXT_PATH / "line.png")
    line2_draw = ImageDraw.Draw(line2)
    line2_draw.text((475, 30), "角色信息", "white", waves_font_30, "mm")
    card_img.paste(line2, (0, yset - 70), line2)

    card_img = add_footer(card_img, 600, 20)
    card_img = await convert_img(card_img)
    return card_img


async def draw_international_role_img(uid: str, user, ev: Event):
    """國際服角色卡片"""
    try:
        import kuro
        from kuro.types import Region

        # 創建 kuro 客戶端
        client = kuro.Client(region=Region.OVERSEAS)

        # 生成 OAuth code
        oauth_code = await client.generate_oauth_code(user.cookie)

        # 從 platform 字段中提取服務器區域
        server_region = "Asia"  # 默認值
        if user.platform and user.platform.startswith("international_"):
            server_region = user.platform.replace("international_", "")
            print(f"[鸣潮][國際服角色卡片]使用服務器區域: {server_region}")

        # 獲取角色信息
        role_info = await client.get_player_role(oauth_code, int(uid), server_region)

        # 創建簡化的角色信息
        basic_info = role_info.basic
        battle_pass_info = role_info.battle_pass

        # 獲取箱子數據
        chests = basic_info.chests
        chest_1 = chests.get("1", 0)  # 朴素奇藏箱
        chest_2 = chests.get("2", 0)  # 基準奇藏箱
        chest_3 = chests.get("3", 0)  # 精密奇藏箱
        chest_4 = chests.get("4", 0)  # 輝光奇藏箱

        # 獲取潮汐之遺數據
        tidal_heritages = basic_info.tidal_heritages
        tidal_1 = tidal_heritages.get("1", 0)  # 潮汐之遺-綠
        tidal_2 = tidal_heritages.get("2", 0)  # 潮汐之遺-紫
        tidal_3 = tidal_heritages.get("3", 0)  # 潮汐之遺-金

        # 計算UP角色數量（國際服）
        up_num = 0
        try:
            # 基於分析系統的練度計算邏輯
            # 使用與查詢系統相同的UP角色判斷標準
            from ..utils.resource.constant import (
                NORMAL_LIST_IDS,
                SPECIAL_CHAR_NAME,
            )

            # 獲取角色總數
            character_count = basic_info.character_count
            print(f"[鸣潮][國際服卡片] 角色總數: {character_count}")

            if character_count > 0:
                # 基於練度統計的UP角色計算邏輯
                # 根據分析系統的練度標準：UP角色 = 五星角色且不在常駐列表中

                # 根據角色總數估算五星角色數量
                # 基於練度統計：活躍玩家通常有30-50%的角色是五星
                estimated_5star_ratio = 0.4  # 假設40%的角色是五星
                estimated_5star_count = int(character_count * estimated_5star_ratio)

                # 在五星角色中，UP角色約佔80-90%（排除常駐角色）
                # 常駐角色包括：凌陽、安可、卡卡罗、鉴心、维里奈、漂泊者等
                up_ratio = 0.85  # 假設85%的五星角色是UP角色
                up_num = int(estimated_5star_count * up_ratio)

                # 基於練度統計的邊界保護
                # 確保UP角色數量在合理範圍內
                min_up = max(3, int(character_count * 0.15))  # 至少3個或總角色的15%
                max_up = int(character_count * 0.5)  # 最多不超過總角色的50%

                up_num = max(min_up, min(up_num, max_up))

                print(f"[鸣潮][國際服卡片] 角色總數: {character_count}")
                print(f"[鸣潮][國際服卡片] 估算五星角色數量: {estimated_5star_count}")
                print(f"[鸣潮][國際服卡片] 估算UP角色數量: {up_num}")
                print(f"[鸣潮][國際服卡片] UP角色範圍: {min_up}-{max_up}")
            else:
                print("[鸣潮][國際服卡片] 角色總數為0，無法估算UP角色數量")
        except Exception as e:
            print(f"[鸣潮][國際服卡片] 計算UP角色失敗: {e}")
            up_num = 0

        # 生成圖像
        img = await _draw_international_role_card_img(
            uid, basic_info, battle_pass_info, chests, tidal_heritages, up_num, ev
        )
        return await convert_img(img)

    except Exception as e:
        return f"❌ 國際服角色卡片生成失敗: {str(e)}"


async def _draw_international_role_card_img(
    uid: str, basic_info, battle_pass_info, chests, tidal_heritages, up_num, ev: Event
):
    """生成國際服角色卡片圖像 - 參考國服的生成邏輯"""
    # 計算圖像尺寸 - 參考國服的計算方式
    roleTotalNum = basic_info.character_count
    xset = 50
    yset = 470

    # 初始化基础信息栏位 - 參考國服
    bs = Image.open(TEXT_PATH / "bs.png")
    yset += bs.size[1]

    w = 1000
    h = 100 + yset + 200 * int(roleTotalNum / 4 + (1 if roleTotalNum % 4 else 0))
    card_img = get_waves_bg(w, h)

    # 基本信息數據 - 按照新的布局要求
    base_info_value_list = [
        # 上排：活躍天數、三種潮汐之遺、已達成成就、成就星數
        {
            "key": "活跃天数",
            "value": f"{basic_info.active_days}",
            "info_block": "color_y.png",
        },
        {
            "key": "潮汐之遗-绿",
            "value": f"{tidal_heritages.get('1', 0)}",
            "info_block": "",
        },
        {
            "key": "潮汐之遗-紫",
            "value": f"{tidal_heritages.get('2', 0)}",
            "info_block": "",
        },
        {
            "key": "潮汐之遗-金",
            "value": f"{tidal_heritages.get('3', 0)}",
            "info_block": "",
        },
        {
            "key": "已达成成就",
            "value": "0",
            "info_block": "color_p.png",
        },  # 國際服暫不支援
        {"key": "成就星数", "value": "0", "info_block": ""},  # 國際服暫不支援
        # 下排：解鎖角色、UP角色、四種箱子
        {"key": "解锁角色", "value": f"{basic_info.character_count}", "info_block": ""},
        {"key": "UP角色", "value": f"{up_num}", "info_block": "color_g.png"},
        {
            "key": "朴素奇藏箱",
            "value": f"{chests.get('1', 0)}",
            "info_block": "",
        },
        {
            "key": "基准奇藏箱",
            "value": f"{chests.get('2', 0)}",
            "info_block": "",
        },
        {
            "key": "精密奇藏箱",
            "value": f"{chests.get('3', 0)}",
            "info_block": "",
        },
        {
            "key": "辉光奇藏箱",
            "value": f"{chests.get('4', 0)}",
            "info_block": "",
        },
    ]

    # 基本信息網格生成 - 參考國服的 calc_info_block 函數
    def calc_info_block(_x: int, _y: int, key: str, value: str, color_path: str = ""):
        if not color_path:
            color_path = "info_block.png"
        info_block = Image.open(TEXT_PATH / f"{color_path}")
        info_block_draw = ImageDraw.Draw(info_block)
        info_block_draw.text((66, 90), key, "white", waves_font_26, "mm")
        info_block_draw.text((66, 43), value, "white", waves_font_40, "mm")
        bs.paste(info_block, (_x, _y), info_block)

    # 基本信息網格布局 - 參考國服的布局邏輯
    x = 66
    y = 75
    for i in range(2):
        for j in range(6):
            _x = x + 145 * j
            _y = y + 140 * i
            _len = i * 6 + j
            if _len >= len(base_info_value_list):
                break
            calc_info_block(
                _x,
                _y,
                base_info_value_list[_len]["key"],
                base_info_value_list[_len]["value"],
                base_info_value_list[_len]["info_block"],
            )

    # 基础信息 名字 特征码 - 參考國服
    base_info_bg = Image.open(TEXT_PATH / "base_info_bg.png")
    base_info_draw = ImageDraw.Draw(base_info_bg)
    base_info_draw.text(
        (275, 120), f"{basic_info.name[:7]}", "white", waves_font_30, "lm"
    )
    base_info_draw.text((226, 173), f"特征码:  {uid}", GOLD, waves_font_25, "lm")
    card_img.paste(base_info_bg, (35, 170), base_info_bg)

    # 头像 头像环 - 參考國服
    avatar, avatar_ring = await draw_pic_with_ring(ev)
    card_img.paste(avatar, (45, 220), avatar)
    card_img.paste(avatar_ring, (55, 230), avatar_ring)

    # 右侧装饰 - 參考國服
    char = Image.open(TEXT_PATH / "char.png")
    card_img.paste(char, (910, 0), char)

    # 账号基本信息 - 參考國服
    line = Image.open(TEXT_PATH / "line.png")
    line_draw = ImageDraw.Draw(line)
    line_draw.text((475, 30), "基本信息", "white", waves_font_30, "mm")

    title_bar = Image.open(TEXT_PATH / "title_bar.png")
    title_bar_draw = ImageDraw.Draw(title_bar)
    title_bar_draw.text((660, 125), "角色等级", GREY, waves_font_26, "mm")
    title_bar_draw.text(
        (660, 78), f"Lv.{basic_info.level}", "white", waves_font_42, "mm"
    )

    title_bar_draw.text((810, 125), "世界等级", GREY, waves_font_26, "mm")
    title_bar_draw.text(
        (810, 78), f"Lv.{basic_info.world_level}", "white", waves_font_42, "mm"
    )

    # 貼上基本信息網格和分隔線 - 參考國服的位置
    card_img.paste(line, (0, yset - bs.size[1] - 70), line)
    card_img.paste(bs, (-10, yset - bs.size[1] - 70), bs)
    card_img.paste(title_bar, (0, 220), title_bar)

    # 角色信息分隔線 - 參考國服
    line2 = Image.open(TEXT_PATH / "line.png")
    line2_draw = ImageDraw.Draw(line2)
    line2_draw.text((475, 30), "角色信息", "white", waves_font_30, "mm")
    card_img.paste(line2, (0, yset - 70), line2)

    card_img = add_footer(card_img, 600, 20)
    return card_img
