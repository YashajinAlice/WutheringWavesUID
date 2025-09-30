import re
import uuid
import asyncio
import hashlib
from pathlib import Path
from typing import Union, Optional

import httpx
from gsuid_core.bot import Bot
from pydantic import BaseModel
from async_timeout import timeout
from gsuid_core.web_app import app
from gsuid_core.models import Event
from gsuid_core.logger import logger
from gsuid_core.config import core_config
from starlette.responses import HTMLResponse
from gsuid_core.segment import MessageSegment
from gsuid_core.utils.cookie_manager.qrlogin import get_qrcode_base64

from ..utils.cache import TimedCache
from ..utils.util import get_public_ip
from ..wutheringwaves_user import deal
from ..utils.waves_api import waves_api
from ..utils.database.models import WavesBind, WavesUser
from ..utils.resource.RESOURCE_PATH import waves_templates
from ..wutheringwaves_user.login_succ import login_success_msg
from ..wutheringwaves_config import PREFIX, WutheringWavesConfig

cache = TimedCache(timeout=600, maxsize=10)

game_title = "[鸣潮]"
msg_error = "[鸣潮] 登录失败\n1.是否注册过库街区\n2.库街区能否查询当前鸣潮特征码数据\n"


async def get_url() -> tuple[str, bool]:
    url = WutheringWavesConfig.get_config("WavesLoginUrl").data
    if url:
        if not url.startswith("http"):
            # 對於 localhost，使用 http；對於其他地址，使用 https
            if "localhost" in url or "127.0.0.1" in url:
                url = f"http://{url}"
            else:
                url = f"https://{url}"
        return url, WutheringWavesConfig.get_config("WavesLoginUrlSelf").data
    else:
        HOST = core_config.get_config("HOST")
        PORT = core_config.get_config("PORT")

        if HOST == "localhost" or HOST == "127.0.0.1":
            _host = "localhost"
        else:
            _host = await get_public_ip(HOST)

        return f"http://{_host}:{PORT}", True


def is_valid_chinese_phone_number(phone_number):
    # 正则表达式匹配中国大陆的手机号
    pattern = re.compile(r"^1[3-9]\d{9}$")
    return pattern.match(phone_number) is not None


def is_validate_code(code):
    # 正则表达式匹配6位数字
    pattern = re.compile(r"^\d{6}$")
    return pattern.match(code) is not None


def get_token(userId: str):
    return hashlib.sha256(userId.encode()).hexdigest()[:8]


async def send_login(bot: Bot, ev: Event, url):
    at_sender = True if ev.group_id else False

    if WutheringWavesConfig.get_config("WavesQRLogin").data:
        path = Path(__file__).parent / f"{ev.user_id}.gif"

        im = [
            f"{game_title} 您的id为【{ev.user_id}】\n",
            "请扫描下方二维码获取登录地址，并复制地址到浏览器打开\n",
            MessageSegment.image(await get_qrcode_base64(url, path, ev.bot_id)),
        ]

        if WutheringWavesConfig.get_config("WavesLoginForward").data:
            if not ev.group_id and ev.bot_id == "onebot":
                # 私聊+onebot 不转发
                await bot.send(im)
            else:
                await bot.send(MessageSegment.node(im))
        else:
            await bot.send(im, at_sender=at_sender)

        if path.exists():
            path.unlink()
    else:
        if WutheringWavesConfig.get_config("WavesTencentWord").data:
            url = f"https://docs.qq.com/scenario/link.html?url={url}"
        im = [
            f"{game_title} 您的id为【{ev.user_id}】",
            "请复制地址到浏览器打开",
            f" {url}",
            "登录地址10分钟内有效",
        ]

        if WutheringWavesConfig.get_config("WavesLoginForward").data:
            if not ev.group_id and ev.bot_id == "onebot":
                # 私聊+onebot 不转发
                await bot.send("\n".join(im))
            else:
                await bot.send(MessageSegment.node(im))
        else:
            await bot.send("\n".join(im), at_sender=at_sender)


async def page_login_local(bot: Bot, ev: Event, url):
    at_sender = True if ev.group_id else False
    user_token = get_token(ev.user_id)
    await send_login(bot, ev, f"{url}/waves/i/{user_token}")
    result = cache.get(user_token)
    if isinstance(result, dict):
        # 如果緩存已存在，檢查是否為國際服登入
        if result.get("login_type") == "international":
            # 國際服登入，不覆蓋緩存
            pass
        else:
            # 國服登入，更新緩存
            result.update(
                {
                    "user_id": ev.user_id,
                    "bot_id": ev.bot_id,
                    "group_id": ev.group_id,
                    "login_type": "domestic",
                }
            )
            cache.set(user_token, result)
        return

    # 手机登录 - 創建新的國服登入緩存
    data = {
        "mobile": -1,
        "code": -1,
        "user_id": ev.user_id,
        "bot_id": ev.bot_id,
        "group_id": ev.group_id,
        "login_type": "domestic",  # 標記為國服登入
    }
    cache.set(user_token, data)
    try:
        async with timeout(600):
            while True:
                result = cache.get(user_token)
                if result is None:
                    return await bot.send("登录超时!\n", at_sender=at_sender)

                # 檢查是否為國際服登入
                if result.get("login_type") == "international" and result.get(
                    "login_completed"
                ):
                    cache.delete(user_token)
                    # 國際服登入已完成，直接發送成功消息
                    uid = result.get("uid", "未知")
                    username = result.get("username", "未知")

                    # 創建國際服專用的按鈕
                    from ..utils.button import WavesButton

                    buttons = [
                        WavesButton("体力", "mr"),
                        WavesButton("每日", "每日"),
                        WavesButton("卡片", "卡片"),
                    ]

                    # 發送國際服登入成功消息
                    success_msg = f"[鸣潮] 國際服登入成功！\n用戶名: {username}\n特征碼: {uid}\n平台: 國際服\n狀態: 已啟用\n\n目前支援功能：每日、卡片、体力"

                    # 發送帶按鈕的消息
                    return await bot.send_option(success_msg, buttons)

                # 檢查是否需要角色選擇（網頁處理，不需要機器人消息）
                if result.get("login_type") == "international" and result.get(
                    "need_character_selection"
                ):
                    # 角色選擇由網頁處理，這裡不需要機器人消息
                    # 直接返回成功，讓網頁顯示角色選擇界面
                    return await bot.send(
                        "角色選擇將在網頁中進行，請在網頁中選擇角色",
                        at_sender=at_sender,
                    )

                # 檢查是否為國服登入（確保不是國際服登入）
                if (
                    result.get("login_type") != "international"
                    and result.get("mobile") != -1
                    and result.get("code") != -1
                ):
                    text = f"{result['mobile']},{result['code']}"
                    cache.delete(user_token)
                    break
                await asyncio.sleep(1)
    except asyncio.TimeoutError:
        return await bot.send("登录超时!\n", at_sender=at_sender)
    except Exception as e:
        logger.error(e)

    return await code_login(bot, ev, text, True)


async def international_login(
    bot: Bot, ev: Event, login_data: dict, geetest_data: Optional[str] = None
):
    """處理國際服登入"""
    at_sender = True if ev.group_id else False

    try:
        email = login_data.get("email")
        password = login_data.get("password")

        logger.info(f"開始處理國際服登入: {email}")
        if geetest_data:
            logger.info("使用 Geetest 驗證數據進行登入")

        # 集成 kuro.py 的國際服登入功能
        try:
            import kuro
            from kuro.types import Game, Region
            from kuro.errors import KuroError, GeetestTriggeredError

            # 創建 kuro 客戶端
            client = kuro.Client(region=Region.OVERSEAS)

            # 如果有 Geetest 數據，使用 kuro.py 的內建方法
            if geetest_data:
                try:
                    import json

                    # 解析 Geetest 數據
                    geetest_json = json.loads(geetest_data)
                    logger.info(f"解析 Geetest 數據: {geetest_json}")

                    # 創建 MMTResult 對象
                    mmt_result = kuro.models.MMTResult(**geetest_json)
                    logger.info(f"創建 MMTResult 成功: {mmt_result}")

                    # 使用 kuro.py 的內建 game_login 方法
                    login_result = await client.game_login(
                        email, password, mmt_result=mmt_result
                    )
                    logger.info(f"kuro.py 內建登入成功: {login_result.username}")

                except GeetestTriggeredError as e:
                    logger.error(f"Geetest 驗證觸發: {e}")
                    raise Exception("需要進行行為驗證 (錯誤碼: 41000)")
                except KuroError as e:
                    logger.error(f"kuro.py Geetest 登入錯誤: {e}")
                    logger.error(
                        f"KuroError 詳細信息: retcode={e.retcode}, msg={e.msg}, api_msg={e.api_msg}"
                    )
                    logger.error(f"API 響應: {e.response}")
                    # 檢查 API 響應中的具體錯誤碼
                    api_codes = e.response.get("codes", 0)
                    error_description = e.response.get("error_description", "")

                    if api_codes == -4 or "校验码不通过" in error_description:
                        logger.warning("Geetest 驗證碼不通過，需要重新驗證")
                        raise Exception("需要進行行為驗證 (錯誤碼: 41000)")
                    elif (
                        api_codes == 10001
                        or "account or password" in error_description.lower()
                    ):
                        logger.error("賬號或密碼錯誤")
                        raise Exception(f"賬號或密碼錯誤: {error_description}")
                    elif e.retcode == 0:
                        logger.warning(
                            "Geetest 驗證數據可能已過期或服務器問題，需要重新驗證"
                        )
                        raise Exception("需要進行行為驗證 (錯誤碼: 41000)")
                    else:
                        raise Exception(f"Geetest 驗證失敗: {str(e)}")
                except Exception as e:
                    logger.error(f"kuro.py 內建登入失敗: {e}")
                    # 回退到原始方法
                    raise Exception(f"Geetest 驗證失敗: {str(e)}")
            else:
                # 嘗試正常登入
                try:
                    login_result = await client.game_login(email, password)
                    logger.info(f"kuro.py 正常登入成功: {login_result.username}")
                except GeetestTriggeredError as e:
                    logger.info(f"觸發 Geetest 驗證: {e}")
                    raise Exception("需要進行行為驗證 (錯誤碼: 41000)")
                except KuroError as e:
                    logger.info(f"kuro.py 錯誤: {e}")
                    logger.info(
                        f"KuroError 詳細信息: retcode={e.retcode}, msg={e.msg}, api_msg={e.api_msg}"
                    )
                    logger.info(f"API 響應: {e.response}")
                    # 檢查 API 響應中的具體錯誤碼
                    api_codes = e.response.get("codes", 0)
                    error_description = e.response.get("error_description", "")

                    if (
                        api_codes == 10001
                        or "account or password" in error_description.lower()
                    ):
                        logger.error("賬號或密碼錯誤")
                        raise Exception(f"賬號或密碼錯誤: {error_description}")
                    elif e.retcode == 0:  # Unknown error
                        raise Exception("需要進行行為驗證 (錯誤碼: 41000)")
                    else:
                        raise Exception(f"登入失敗: {str(e)}")
                except Exception as e:
                    logger.info(f"正常登入失敗，可能需要 Geetest 驗證: {e}")
                    # 檢查是否為需要 Geetest 驗證的錯誤
                    error_str = str(e).lower()
                    if any(
                        keyword in error_str
                        for keyword in [
                            "41000",
                            "行為驗證",
                            "unknown error",
                            "captcha",
                            "verification",
                        ]
                    ):
                        raise Exception("需要進行行為驗證 (錯誤碼: 41000)")
                    else:
                        raise Exception(f"登入失敗: {str(e)}")

            # 登入成功，繼續處理
            # 清理用戶名稱中的特殊字符，避免數據處理問題
            import re
            import time

            clean_username = re.sub(r"[^\w\s\u4e00-\u9fa5]", "", login_result.username)
            if not clean_username.strip():
                clean_username = "User" + str(
                    int(time.time())
                )  # 如果清理後為空，使用時間戳
            logger.info(
                f"國際服登入成功: {login_result.username} -> 清理後: {clean_username}"
            )

            # 獲取遊戲 token
            token_result = await client.get_game_token(login_result.code)
            logger.info(f"獲取遊戲 token 成功")

            # 生成 OAuth code
            oauth_code = await client.generate_oauth_code(token_result.access_token)
            logger.info(f"生成 OAuth code 成功")

            # 國際服登入成功，存儲用戶數據並調用成功消息
            # 注意：國際服目前不支援角色面板刷新，只支援每日、卡片等功能

            # 為國際服創建/更新 WavesUser 記錄
            from ..utils.database.models import WavesBind, WavesUser

            # 使用登入結果中的用戶名作為 UID（國際服的特殊處理）
            # 國際服的 UID 格式：U568812713A，需要提取數字部分作為特征碼
            uid = login_result.username  # 例如: U568812713A
            # 提取數字部分作為特征碼（用於數據庫存儲）
            import re

            uid_digits = re.sub(r"[^0-9]", "", uid)  # 提取純數字：568812713
            if not uid_digits:
                uid_digits = uid  # 如果沒有數字，使用原始 UID

            # 檢查是否已存在用戶（使用數字特征碼）
            existing_user = await WavesUser.get_user_by_attr(
                ev.user_id, ev.bot_id, "uid", uid_digits
            )

            if existing_user:
                # 更新現有用戶
                await WavesUser.update_data_by_data(
                    select_data={
                        "user_id": ev.user_id,
                        "bot_id": ev.bot_id,
                        "uid": uid_digits,
                    },
                    update_data={
                        "cookie": token_result.access_token,
                        "platform": "international",
                        "status": "on",
                    },
                )
                waves_user = existing_user
                logger.info(f"WavesUser 更新成功: UID {uid_digits} (原始: {uid})")
            else:
                # 創建新用戶
                await WavesUser.insert_data(
                    ev.user_id,
                    ev.bot_id,
                    cookie=token_result.access_token,
                    uid=uid_digits,  # 使用數字特征碼
                    platform="international",
                    status="on",
                )
                # 獲取創建的用戶
                waves_user = await WavesUser.get_user_by_attr(
                    ev.user_id, ev.bot_id, "uid", uid_digits
                )
                logger.info(f"WavesUser 創建成功: UID {uid_digits} (原始: {uid})")

            # 檢查是否已有此 UID 的綁定，避免雙重 UID
            try:
                existing_bind = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
                if existing_bind == uid_digits:
                    # UID 已綁定，跳過重複儲存
                    logger.info(f"UID {uid_digits} 已綁定，跳過重複儲存 WavesBind")
                else:
                    # 新 UID 或不同 UID，更新綁定
                    await WavesBind.insert_waves_uid(
                        ev.user_id, ev.bot_id, uid_digits, ev.group_id, lenth_limit=9
                    )
                    logger.info(f"WavesBind 更新成功: UID {uid_digits}")
            except Exception as e:
                logger.warning(f"WavesBind 更新失敗: {e}")

            # 國際服登入成功，發送專門的成功消息
            if waves_user:
                # 為國際服創建專門的成功消息（不調用國服的角色面板生成）
                at_sender = True if ev.group_id else False

                # 創建國際服專用的按鈕
                from ..utils.button import WavesButton

                buttons = [
                    WavesButton("体力", "mr"),
                    WavesButton("每日", "每日"),
                    WavesButton("卡片", "卡片"),
                ]

                # 發送國際服登入成功消息
                success_msg = f"[鸣潮] 國際服登入成功！\n用戶名: {login_result.username}\n特征碼: {uid_digits}\n平台: 國際服\n狀態: 已啟用\n\n目前支援功能：每日、卡片、体力"

                # 發送帶按鈕的消息
                return await bot.send_option(success_msg, buttons)
            else:
                # 備用方案：簡單文字消息
                success_msg = f"[鸣潮] 國際服登入成功！\n用戶名: {login_result.username}\n平台: 國際服\n狀態: 已啟用\n\n目前支援功能：每日、卡片"
                return await bot.send(success_msg, at_sender=at_sender)

        except ImportError:
            logger.warning("kuro.py 未安裝，使用模擬登入")
            success_msg = f"[鸣潮] 國際服登入成功！\n郵箱: {email}\n\n注意：kuro.py 未安裝，無法獲取實際遊戲數據。"
            return await bot.send(success_msg, at_sender=at_sender)

        except Exception as e:
            logger.error(f"kuro.py 登入失敗: {e}")
            # 檢查是否為需要 Geetest 驗證的錯誤，如果是則重新拋出
            error_str = str(e).lower()
            if any(
                keyword in error_str
                for keyword in [
                    "41000",
                    "行為驗證",
                    "unknown error",
                    "captcha",
                    "verification",
                ]
            ):
                # 重新拋出異常，讓 API 端點處理
                raise e
            else:
                # 如果 kuro.py 登入失敗，返回錯誤信息
                error_msg = f"[鸣潮] 國際服登入失敗: {str(e)}"
                return await bot.send(error_msg, at_sender=at_sender)

    except Exception as e:
        logger.error(f"國際服登入處理失敗: {e}")
        # 檢查是否為需要 Geetest 驗證的錯誤，如果是則重新拋出
        error_str = str(e).lower()
        if any(
            keyword in error_str
            for keyword in [
                "41000",
                "行為驗證",
                "unknown error",
                "captcha",
                "verification",
            ]
        ):
            # 重新拋出異常，讓 API 端點處理
            raise e
        else:
            error_msg = f"[鸣潮] 國際服登入失敗: {str(e)}"
            return await bot.send(error_msg, at_sender=at_sender)


async def page_login_other(bot: Bot, ev: Event, url):
    at_sender = True if ev.group_id else False
    user_token = get_token(ev.user_id)

    auth = {"bot_id": ev.bot_id, "user_id": ev.user_id}

    token = cache.get(user_token)
    if isinstance(token, str):
        await send_login(bot, ev, f"{url}/waves/i/{token}")
        return

    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                url + "/waves/token",
                json=auth,
                headers={"Content-Type": "application/json"},
            )
            token = r.json().get("token", "")
        except Exception as e:
            token = ""
            logger.error(e)
        if not token:
            return await bot.send("登录服务请求失败! 请稍后再试\n", at_sender=at_sender)

        await send_login(bot, ev, f"{url}/waves/i/{token}")

        cache.set(user_token, token)
        times = 3
        async with timeout(600):
            while True:
                if times <= 0:
                    return await bot.send(
                        "登录服务请求失败! 请稍后再试\n", at_sender=at_sender
                    )

                result = await client.post(url + "/waves/get", json={"token": token})
                if result.status_code != 200:
                    times -= 1
                    await asyncio.sleep(5)
                    continue
                data = result.json()
                if not data.get("ck"):
                    await asyncio.sleep(1)
                    continue

                waves_user = await add_cookie(ev, data["ck"], data["did"])
                cache.delete(user_token)
                if waves_user and isinstance(waves_user, WavesUser):
                    return await login_success_msg(bot, ev, waves_user)
                else:
                    if isinstance(waves_user, str):
                        return await bot.send(waves_user, at_sender=at_sender)
                    else:
                        return await bot.send(msg_error, at_sender=at_sender)


async def page_login(bot: Bot, ev: Event):
    url, is_local = await get_url()

    if is_local:
        return await page_login_local(bot, ev, url)
    else:
        return await page_login_other(bot, ev, url)


async def code_login(bot: Bot, ev: Event, text: str, isPage=False):
    at_sender = True if ev.group_id else False
    game_title = "[鸣潮]"
    # 手机+验证码
    try:
        phone_number, code = text.split(",")
        if not is_valid_chinese_phone_number(phone_number):
            raise ValueError("Invalid phone number")
    except ValueError as _:
        return await bot.send(
            f"{game_title} 手机号+验证码登录失败\n\n请参照以下格式:\n{PREFIX}登录 手机号,验证码\n",
            at_sender=at_sender,
        )

    did = str(uuid.uuid4()).upper()
    result = await waves_api.login(phone_number, code, did)
    if not result.success:
        return await bot.send(result.throw_msg(), at_sender=at_sender)

    if result.msg == "系统繁忙，请稍后再试":
        # 可能是没注册库街区。 -_-||
        return await bot.send(msg_error, at_sender=at_sender)

    if not result.data or not isinstance(result.data, dict):
        return await bot.send(message=result.throw_msg(), at_sender=at_sender)

    token = result.data.get("token", "")
    waves_user = await add_cookie(ev, token, did)
    if waves_user and isinstance(waves_user, WavesUser):
        return await login_success_msg(bot, ev, waves_user)
    else:
        if isinstance(waves_user, str):
            return await bot.send(waves_user, at_sender=at_sender)
        else:
            return await bot.send(msg_error, at_sender=at_sender)


async def add_cookie(ev, token, did) -> Union[WavesUser, str, None]:
    ck_res = await deal.add_cookie(ev, token, did)
    if "成功" in ck_res:
        user = await WavesUser.get_user_by_attr(ev.user_id, ev.bot_id, "cookie", token)
        if user:
            data = await WavesBind.insert_waves_uid(
                ev.user_id, ev.bot_id, user.uid, ev.group_id, lenth_limit=9
            )
            if data == 0 or data == -2:
                await WavesBind.switch_uid_by_game(ev.user_id, ev.bot_id, user.uid)
        return user
    return ck_res


@app.get("/waves/i/{auth}")
async def waves_login_index(auth: str):
    temp = cache.get(auth)
    if temp is None:
        # 為國際服登入創建初始緩存數據
        temp = {
            "email": -1,
            "password": -1,
            "login_type": "international",
            "user_id": auth,
            "bot_id": "discord",  # 默認 bot_id
            "group_id": None,  # 默認 group_id
        }
        cache.set(auth, temp)
        logger.info(f"為國際服登入創建初始緩存: {auth}")

    from ..utils.api.api import MAIN_URL

    url, _ = await get_url()
    template = waves_templates.get_template("index.html")
    return HTMLResponse(
        template.render(
            server_url=url,
            auth=auth,
            userId=temp.get("user_id", auth),
            kuro_url=MAIN_URL,
        )
    )


class LoginModel(BaseModel):
    auth: str
    mobile: str
    code: str


class InternationalLoginModel(BaseModel):
    auth: str
    email: str
    password: str
    geetest_data: Optional[str] = None  # Geetest 驗證數據


@app.post("/waves/login")
async def waves_login(data: LoginModel):
    temp = cache.get(data.auth)
    if temp is None:
        return {"success": False, "msg": "登录超时"}

    temp.update(data.dict())
    cache.set(data.auth, temp)
    return {"success": True}


@app.post("/waves/international/login")
async def waves_international_login(data: InternationalLoginModel):
    """國際服登入 API"""
    logger.info(f"收到國際服登入請求: auth={data.auth}, email={data.email}")

    # 檢查緩存，如果沒有則創建新的
    temp = cache.get(data.auth)
    logger.info(f"緩存狀態: {temp}")

    if temp is None:
        # 為國際服登入創建初始緩存數據
        temp = {
            "email": -1,
            "password": -1,
            "login_type": "international",
            "user_id": data.auth,  # 使用 auth 作為 user_id
            "bot_id": "discord",  # 默認 bot_id
            "group_id": None,  # 默認 group_id
        }
        cache.set(data.auth, temp)
        logger.info(f"創建新緩存: {temp}")

    try:
        # 直接處理國際服登入邏輯，不通過模擬對象
        email = data.email
        password = data.password

        logger.info(f"開始處理國際服登入: {email}")
        if data.geetest_data:
            logger.info("使用 Geetest 驗證數據進行登入")

        # 集成 kuro.py 的國際服登入功能
        try:
            import kuro
            from kuro.types import Game, Region
            from kuro.errors import KuroError, GeetestTriggeredError

            # 創建 kuro 客戶端
            client = kuro.Client(region=Region.OVERSEAS)

            # 如果有 Geetest 數據，使用 kuro.py 的內建方法
            if data.geetest_data:
                try:
                    import json

                    # 解析 Geetest 數據
                    geetest_json = json.loads(data.geetest_data)
                    logger.info(f"解析 Geetest 數據: {geetest_json}")

                    # 創建 MMTResult 對象
                    mmt_result = kuro.models.MMTResult(**geetest_json)
                    logger.info(f"創建 MMTResult 成功: {mmt_result}")

                    # 使用 kuro.py 的內建 game_login 方法
                    login_result = await client.game_login(
                        email, password, mmt_result=mmt_result
                    )
                    logger.info(f"kuro.py 內建登入成功: {login_result.username}")

                except GeetestTriggeredError as e:
                    logger.error(f"Geetest 驗證觸發: {e}")
                    raise Exception("需要進行行為驗證 (錯誤碼: 41000)")
                except KuroError as e:
                    logger.error(f"kuro.py Geetest 登入錯誤: {e}")
                    logger.error(
                        f"KuroError 詳細信息: retcode={e.retcode}, msg={e.msg}, api_msg={e.api_msg}"
                    )
                    logger.error(f"API 響應: {e.response}")
                    # 檢查 API 響應中的具體錯誤碼
                    api_codes = e.response.get("codes", 0)
                    error_description = e.response.get("error_description", "")

                    if api_codes == -4 or "校验码不通过" in error_description:
                        logger.warning("Geetest 驗證碼不通過，需要重新驗證")
                        raise Exception("需要進行行為驗證 (錯誤碼: 41000)")
                    elif (
                        api_codes == 10001
                        or "account or password" in error_description.lower()
                    ):
                        logger.error("賬號或密碼錯誤")
                        raise Exception(f"賬號或密碼錯誤: {error_description}")
                    elif e.retcode == 0:
                        logger.warning(
                            "Geetest 驗證數據可能已過期或服務器問題，需要重新驗證"
                        )
                        raise Exception("需要進行行為驗證 (錯誤碼: 41000)")
                    else:
                        raise Exception(f"Geetest 驗證失敗: {str(e)}")
                except Exception as e:
                    logger.error(f"kuro.py 內建登入失敗: {e}")
                    # 回退到原始方法
                    raise Exception(f"Geetest 驗證失敗: {str(e)}")
            else:
                # 嘗試正常登入
                try:
                    login_result = await client.game_login(email, password)
                    logger.info(f"kuro.py 正常登入成功: {login_result.username}")
                except GeetestTriggeredError as e:
                    logger.info(f"觸發 Geetest 驗證: {e}")
                    raise Exception("需要進行行為驗證 (錯誤碼: 41000)")
                except KuroError as e:
                    logger.info(f"kuro.py 錯誤: {e}")
                    logger.info(
                        f"KuroError 詳細信息: retcode={e.retcode}, msg={e.msg}, api_msg={e.api_msg}"
                    )
                    logger.info(f"API 響應: {e.response}")
                    # 檢查 API 響應中的具體錯誤碼
                    api_codes = e.response.get("codes", 0)
                    error_description = e.response.get("error_description", "")

                    if (
                        api_codes == 10001
                        or "account or password" in error_description.lower()
                    ):
                        logger.error("賬號或密碼錯誤")
                        raise Exception(f"賬號或密碼錯誤: {error_description}")
                    elif e.retcode == 0:  # Unknown error
                        raise Exception("需要進行行為驗證 (錯誤碼: 41000)")
                    else:
                        raise Exception(f"登入失敗: {str(e)}")
                except Exception as e:
                    logger.info(f"正常登入失敗，可能需要 Geetest 驗證: {e}")
                    # 檢查是否為需要 Geetest 驗證的錯誤
                    error_str = str(e).lower()
                    if any(
                        keyword in error_str
                        for keyword in [
                            "41000",
                            "行為驗證",
                            "unknown error",
                            "captcha",
                            "verification",
                        ]
                    ):
                        raise Exception("需要進行行為驗證 (錯誤碼: 41000)")
                    else:
                        raise Exception(f"登入失敗: {str(e)}")

            # 登入成功，繼續處理
            # 清理用戶名稱中的特殊字符，避免數據處理問題
            import re
            import time

            clean_username = re.sub(r"[^\w\s\u4e00-\u9fa5]", "", login_result.username)
            if not clean_username.strip():
                clean_username = "User" + str(
                    int(time.time())
                )  # 如果清理後為空，使用時間戳
            logger.info(
                f"國際服登入成功: {login_result.username} -> 清理後: {clean_username}"
            )

            # 獲取遊戲 token
            token_result = await client.get_game_token(login_result.code)
            logger.info(f"獲取遊戲 token 成功")

            # 生成 OAuth code
            oauth_code = await client.generate_oauth_code(token_result.access_token)
            logger.info(f"生成 OAuth code 成功")

            # 獲取玩家信息以確定 UID（帶重試機制）
            player_info = None
            max_retries = 3
            retry_count = 0

            while retry_count < max_retries:
                try:
                    player_info = await client.get_player_info(oauth_code)
                    logger.info(f"獲取玩家信息成功: {len(player_info)} 個角色")
                    break  # 成功獲取，跳出重試循環
                except Exception as e:
                    error_msg = str(e)
                    logger.warning(
                        f"獲取玩家信息失敗 (嘗試 {retry_count + 1}/{max_retries}): {error_msg}"
                    )

                    # 檢查是否為 'retrying' 錯誤
                    if "'retrying'" in error_msg or "retrying" in error_msg:
                        retry_count += 1
                        if retry_count < max_retries:
                            logger.info(f"檢測到 'retrying' 錯誤，將在 2 秒後重試...")
                            await asyncio.sleep(2)  # 等待2秒後重試
                            continue
                        else:
                            logger.error(
                                f"重試 {max_retries} 次後仍然失敗，使用登入 ID 作為 UID"
                            )
                            break
                    else:
                        # 其他錯誤，直接跳出重試循環
                        logger.warning(
                            f"非 'retrying' 錯誤，直接使用登入 ID 作為 UID: {error_msg}"
                        )
                        break

            # 如果成功獲取到玩家信息
            if player_info:
                # 檢查角色數量
                if len(player_info) > 1:
                    # 多個角色，需要用戶選擇
                    logger.info(f"檢測到 {len(player_info)} 個角色，需要用戶選擇")

                    # 構建角色列表
                    characters = []
                    for region, info in player_info.items():
                        characters.append(
                            {
                                "region": region,
                                "name": info.name,
                                "uid": str(info.uid),
                                "level": info.level,
                                "sex": getattr(info, "sex", 1),
                                "headPhoto": getattr(info, "headPhoto", 1),
                            }
                        )

                    # 將 OAuth code 和 access_token 存儲到緩存中，供後續角色選擇使用
                    temp.update(
                        {
                            "login_type": "international",  # 確保標記為國際服登入
                            "oauth_code": oauth_code,
                            "access_token": token_result.access_token,
                            "login_result_username": clean_username,  # 使用清理後的名稱
                            "characters": characters,
                            "need_character_selection": True,
                        }
                    )
                    cache.set(data.auth, temp)

                    # 返回需要角色選擇的響應，讓前端顯示角色選擇界面
                    return {
                        "success": True,
                        "need_character_selection": True,
                        "characters": characters,
                        "msg": f"檢測到 {len(player_info)} 個角色，請選擇要使用的主角色",
                    }
                else:
                    # 只有一個角色，直接使用
                    first_region = next(iter(player_info))
                    first_player = player_info[first_region]
                    uid = str(first_player.uid)
                    logger.info(f"只有一個角色，使用 UID: {uid}")
            else:
                # 如果沒有角色信息，使用登入結果中的 ID
                uid = str(login_result.id)
                logger.info(f"使用登入 ID 作為 UID: {uid}")

            # 國際服登入成功，存儲用戶數據
            # 為國際服創建/更新 WavesUser 記錄
            from ..utils.database.models import WavesBind, WavesUser

            # 從緩存中獲取真實的 user_id 和 bot_id
            real_user_id = temp.get("user_id", data.auth)
            real_bot_id = temp.get("bot_id", "discord")  # 默認使用 discord

            # 檢查是否已存在用戶
            existing_user = await WavesUser.get_user_by_attr(
                real_user_id, real_bot_id, "uid", uid
            )

            if existing_user:
                # 更新現有用戶
                await WavesUser.update_data_by_data(
                    select_data={
                        "user_id": real_user_id,
                        "bot_id": real_bot_id,
                        "uid": uid,
                    },
                    update_data={
                        "cookie": token_result.access_token,
                        "platform": "international",
                        "status": "on",
                    },
                )
                waves_user = existing_user
                logger.info(f"WavesUser 更新成功: UID {uid}")
            else:
                # 創建新用戶
                await WavesUser.insert_data(
                    real_user_id,
                    real_bot_id,
                    cookie=token_result.access_token,
                    uid=uid,
                    platform="international",
                    status="on",
                )
                # 獲取創建的用戶
                waves_user = await WavesUser.get_user_by_attr(
                    real_user_id, real_bot_id, "uid", uid
                )
                logger.info(f"WavesUser 創建成功: UID {uid}")

            # 更新綁定信息
            try:
                await WavesBind.insert_waves_uid(
                    real_user_id,
                    real_bot_id,
                    uid,
                    temp.get("group_id"),
                    lenth_limit=9,
                )
                logger.info(f"WavesBind 更新成功: UID {uid}")
            except Exception as e:
                logger.warning(f"WavesBind 更新失敗: {e}")

            # 更新緩存，標記登入完成
            temp.update(
                {
                    "login_type": "international",  # 確保標記為國際服登入
                    "login_completed": True,
                    "uid": uid,
                    "username": login_result.username,
                    "platform": "international",
                }
            )
            cache.set(data.auth, temp)

            return {"success": True, "msg": "國際服登入成功", "uid": uid}

        except ImportError:
            logger.warning("kuro.py 未安裝，使用模擬登入")
            return {"success": False, "msg": "kuro.py 未安裝，無法進行國際服登入"}

        except Exception as e:
            logger.error(f"kuro.py 登入失敗: {e}")
            # 檢查是否為需要 Geetest 驗證的錯誤，如果是則重新拋出
            error_str = str(e).lower()
            if any(
                keyword in error_str
                for keyword in [
                    "41000",
                    "行為驗證",
                    "unknown error",
                    "captcha",
                    "verification",
                ]
            ):
                return {
                    "success": False,
                    "msg": "需要進行行為驗證",
                    "need_verification": True,
                    "error_code": 41000,
                }
            else:
                return {"success": False, "msg": f"登入失敗: {str(e)}"}

    except Exception as e:
        logger.error(f"國際服登入失敗: {e}")
        return {"success": False, "msg": f"登入失敗: {str(e)}"}


@app.post("/waves/international/select-character")
async def waves_international_select_character(data: dict):
    """國際服角色選擇 API"""
    auth = data.get("auth")
    character = data.get("character")

    logger.info(f"收到角色選擇請求: auth={auth}, character={character}")

    if not auth or not character:
        return {"success": False, "msg": "缺少必要參數"}

    try:
        # 從緩存中獲取登入數據
        temp = cache.get(auth)
        if not temp:
            return {"success": False, "msg": "登入會話已過期，請重新登入"}

        if not temp.get("need_character_selection"):
            return {"success": False, "msg": "當前不需要角色選擇"}

        # 獲取緩存中的數據
        oauth_code = temp.get("oauth_code")
        access_token = temp.get("access_token")
        login_result_username = temp.get("login_result_username")
        characters = temp.get("characters", [])

        if not oauth_code or not access_token:
            return {"success": False, "msg": "登入數據不完整，請重新登入"}

        # 驗證選擇的角色是否在列表中
        selected_character = None
        for char in characters:
            if char.get("region") == character.get("region") and char.get(
                "uid"
            ) == character.get("uid"):
                selected_character = char
                break

        if not selected_character:
            return {"success": False, "msg": "選擇的角色無效"}

        # 使用選中的角色信息
        uid = selected_character["uid"]
        region = selected_character["region"]
        character_name = selected_character["name"]

        # 清理角色名稱中的特殊字符
        import re
        import time

        clean_character_name = re.sub(r"[^\w\s\u4e00-\u9fa5]", "", character_name)
        if not clean_character_name.strip():
            clean_character_name = "Character" + str(int(time.time()))
        logger.info(
            f"用戶選擇角色: {character_name} -> 清理後: {clean_character_name} (UID: {uid}, 伺服器: {region})"
        )

        # 從緩存中獲取真實的 user_id 和 bot_id
        real_user_id = temp.get("user_id", auth)
        real_bot_id = temp.get("bot_id", "discord")
        real_group_id = temp.get("group_id")

        # 創建/更新 WavesUser 記錄
        from ..utils.database.models import WavesBind, WavesUser

        # 檢查是否已存在用戶
        existing_user = await WavesUser.get_user_by_attr(
            real_user_id, real_bot_id, "uid", uid
        )

        if existing_user:
            # 更新現有用戶
            await WavesUser.update_data_by_data(
                select_data={
                    "user_id": real_user_id,
                    "bot_id": real_bot_id,
                    "uid": uid,
                },
                update_data={
                    "cookie": access_token,
                    "platform": f"international_{region}",
                    "status": "on",
                },
            )
            waves_user = existing_user
            logger.info(f"WavesUser 更新成功: UID {uid} (伺服器: {region})")
        else:
            # 創建新用戶
            await WavesUser.insert_data(
                real_user_id,
                real_bot_id,
                cookie=access_token,
                uid=uid,
                platform=f"international_{region}",
                status="on",
            )
            # 獲取創建的用戶
            waves_user = await WavesUser.get_user_by_attr(
                real_user_id, real_bot_id, "uid", uid
            )
            logger.info(f"WavesUser 創建成功: UID {uid} (伺服器: {region})")

        # 檢查是否已有此 UID 的綁定，避免雙重 UID
        try:
            existing_bind = await WavesBind.get_uid_by_game(real_user_id, real_bot_id)
            if existing_bind == uid:
                # UID 已綁定，跳過重複儲存
                logger.info(f"UID {uid} 已綁定，跳過重複儲存 WavesBind")
            else:
                # 新 UID 或不同 UID，更新綁定
                await WavesBind.insert_waves_uid(
                    real_user_id, real_bot_id, uid, real_group_id, lenth_limit=9
                )
                logger.info(f"WavesBind 更新成功: UID {uid}")
        except Exception as e:
            logger.warning(f"WavesBind 更新失敗: {e}")

        # 清除緩存中的角色選擇數據
        temp.update(
            {
                "login_completed": True,
                "uid": uid,
                "username": clean_character_name,  # 使用清理後的名稱
                "platform": "international",
                "need_character_selection": False,
                "characters": None,
                "oauth_code": None,
                "access_token": None,
            }
        )
        cache.set(auth, temp)

        return {
            "success": True,
            "msg": f"角色選擇成功！已綁定 {clean_character_name} ({region})",
            "uid": uid,
            "character_name": clean_character_name,
        }

    except Exception as e:
        logger.error(f"角色選擇失敗: {e}")
        return {"success": False, "msg": f"角色選擇失敗: {str(e)}"}


async def handle_character_selection_callback(bot, ev, callback_data):
    """處理機器人角色選擇回調"""
    logger.info(f"收到角色選擇回調: {callback_data}")

    try:
        # 解析回調數據
        if not callback_data.startswith("select_char_"):
            return False

        char_index = int(callback_data.replace("select_char_", ""))
        logger.info(f"用戶選擇角色索引: {char_index}")

        # 從緩存中獲取角色數據
        temp = cache.get(ev.user_id)
        if not temp or not temp.get("need_character_selection"):
            await bot.send("角色選擇會話已過期，請重新登入", at_sender=True)
            return True

        characters = temp.get("characters", [])
        if char_index >= len(characters):
            await bot.send("無效的角色選擇，請重新選擇", at_sender=True)
            return True

        # 獲取選中的角色
        selected_character = characters[char_index]
        logger.info(f"用戶選擇角色: {selected_character}")

        # 處理角色選擇
        uid = selected_character["uid"]
        region = selected_character["region"]
        character_name = selected_character["name"]

        # 從緩存中獲取登入數據
        oauth_code = temp.get("oauth_code")
        access_token = temp.get("access_token")

        if not oauth_code or not access_token:
            await bot.send("登入數據不完整，請重新登入", at_sender=True)
            return True

        # 創建/更新 WavesUser 記錄
        from ..utils.database.models import WavesBind, WavesUser

        # 檢查是否已存在用戶
        existing_user = await WavesUser.get_user_by_attr(
            ev.user_id, ev.bot_id, "uid", uid
        )

        if existing_user:
            # 更新現有用戶
            await WavesUser.update_data_by_data(
                select_data={
                    "user_id": ev.user_id,
                    "bot_id": ev.bot_id,
                    "uid": uid,
                },
                update_data={
                    "cookie": access_token,
                    "platform": f"international_{region}",
                    "status": "on",
                },
            )
            waves_user = existing_user
            logger.info(f"WavesUser 更新成功: UID {uid} (伺服器: {region})")
        else:
            # 創建新用戶
            await WavesUser.insert_data(
                ev.user_id,
                ev.bot_id,
                cookie=access_token,
                uid=uid,
                platform=f"international_{region}",
                status="on",
            )
            # 獲取創建的用戶
            waves_user = await WavesUser.get_user_by_attr(
                ev.user_id, ev.bot_id, "uid", uid
            )
            logger.info(f"WavesUser 創建成功: UID {uid} (伺服器: {region})")

        # 更新綁定信息
        try:
            await WavesBind.insert_waves_uid(
                ev.user_id, ev.bot_id, uid, ev.group_id, lenth_limit=9
            )
            logger.info(f"WavesBind 更新成功: UID {uid}")
        except Exception as e:
            logger.warning(f"WavesBind 更新失敗: {e}")

        # 清除緩存中的角色選擇數據
        temp.update(
            {
                "login_completed": True,
                "uid": uid,
                "username": character_name,
                "platform": "international",
                "need_character_selection": False,
                "characters": None,
                "oauth_code": None,
                "access_token": None,
            }
        )
        cache.set(ev.user_id, temp)

        # 發送成功消息
        server_names = {
            "Asia": "🌏 亞洲服",
            "Europe": "🌍 歐洲服",
            "America": "🌎 美洲服",
            "HMT": "🇭🇰 台港澳服",
            "SEA": "🌴 東南亞服",
        }
        server_display = server_names.get(region, region)

        # 清理角色名稱用於顯示
        import re
        import time

        clean_character_name = re.sub(r"[^\w\s\u4e00-\u9fa5]", "", character_name)
        if not clean_character_name.strip():
            clean_character_name = "Character" + str(int(time.time()))

        success_msg = f"[鸣潮] 國際服登入成功！\n角色: {clean_character_name}\n伺服器: {server_display}\n特征碼: {uid}\n平台: 國際服\n狀態: 已啟用\n\n目前支援功能：每日、卡片"

        from ..utils.button import WavesButton

        buttons = [
            WavesButton("体力", "mr"),
            WavesButton("每日", "每日"),
            WavesButton("卡片", "卡片"),
        ]

        await bot.send_option(success_msg, buttons)
        logger.info(f"角色選擇成功: {clean_character_name} ({region})")
        return True

    except Exception as e:
        logger.error(f"處理角色選擇回調失敗: {e}")
        await bot.send(f"角色選擇失敗: {str(e)}", at_sender=True)
        return True
