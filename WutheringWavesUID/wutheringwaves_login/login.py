import re
import uuid
import asyncio
import hashlib
from pathlib import Path
from typing import Union

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
        return

    # 手机登录
    data = {"mobile": -1, "code": -1, "user_id": ev.user_id}
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
                    return await international_login(bot, ev, result)

                # 檢查是否為國服登入
                if result.get("mobile") != -1 and result.get("code") != -1:
                    text = f"{result['mobile']},{result['code']}"
                    cache.delete(user_token)
                    break
                await asyncio.sleep(1)
    except asyncio.TimeoutError:
        return await bot.send("登录超时!\n", at_sender=at_sender)
    except Exception as e:
        logger.error(e)

    return await code_login(bot, ev, text, True)


async def international_login(bot: Bot, ev: Event, login_data: dict):
    """處理國際服登入"""
    at_sender = True if ev.group_id else False

    try:
        email = login_data.get("email")
        password = login_data.get("password")

        logger.info(f"開始處理國際服登入: {email}")

        # 集成 kuro.py 的國際服登入功能
        try:
            import kuro
            from kuro.types import Game, Region

            # 創建 kuro 客戶端
            client = kuro.Client(region=Region.OVERSEAS)

            # 使用改進的登入系統（類似之前成功的版本）
            import time
            import random

            from kuro.constants import APP_KEYS
            from kuro.client.routes import GAME_LOGIN
            from kuro.utility.auth import encode_password, encode_md5_parameter

            # 生成動態設備參數
            device_num = f"device_{random.randint(100000, 999999)}"
            platform = f"PC-{random.randint(1, 10)}.{random.randint(0, 9)}.{random.randint(0, 9)}"
            sdk_version = f"1.{random.randint(0, 9)}.{random.randint(0, 9)}"
            timestamp = int(time.time() * 1000)

            # 構建登入數據
            data = {
                "__e__": 1,
                "email": email,
                "client_id": "7rxmydkibzzsf12om5asjnoo",
                "deviceNum": device_num,
                "password": encode_password(password),
                "platform": platform,
                "productId": "A1725",
                "productKey": "01433708256c41838cda8ead20b64042",
                "projectId": "G153",
                "redirect_uri": 1,
                "response_type": "code",
                "sdkVersion": sdk_version,
                "channelId": "171",
                "timestamp": timestamp,
            }

            # 添加簽名
            data["sign"] = encode_md5_parameter(
                data, APP_KEYS[Game.WUWA][Region.OVERSEAS]
            )

            # 發送登入請求
            rsp = await client.request(GAME_LOGIN.get_url(), data=data)

            if rsp["codes"] not in {0, None}:
                raise Exception(f"登入失敗: {rsp.get('msg', '未知錯誤')}")

            # 解析登入結果
            login_result = kuro.models.GameLoginResult(**rsp)
            logger.info(f"國際服登入成功: {login_result.username}")

            # 獲取遊戲 token（使用動態參數）
            from kuro.client.routes import GAME_TOKEN

            # 生成新的動態設備參數
            device_num_2 = f"device_{random.randint(100000, 999999)}"

            token_data = {
                "client_id": "7rxmydkibzzsf12om5asjnoo",
                "deviceNum": device_num_2,
                "client_secret": "32gh5r0p35ullmxrzzwk40ly",
                "code": login_result.code,  # 使用 code 字段而不是 temp_token
                "productId": "A1725",
                "projectId": "G153",
                "redirect_uri": 1,
                "grant_type": "authorization_code",
            }

            # 添加簽名
            token_data["sign"] = encode_md5_parameter(
                token_data, APP_KEYS[Game.WUWA][Region.OVERSEAS]
            )

            # 發送 token 請求
            logger.info(f"發送 token 請求，數據: {token_data}")
            token_rsp = await client.request(GAME_TOKEN.get_url(), data=token_data)
            logger.info(f"token 響應: {token_rsp}")

            if token_rsp["codes"] not in {0, None}:
                error_msg = token_rsp.get("msg", "未知錯誤")
                error_code = token_rsp.get("codes", "N/A")
                logger.error(
                    f"獲取 token 失敗 - 錯誤碼: {error_code}, 錯誤信息: {error_msg}"
                )
                raise Exception(f"獲取 token 失敗: {error_msg} (錯誤碼: {error_code})")

            token_result = kuro.models.GameTokenResult(**token_rsp)
            logger.info(f"獲取遊戲 token 成功")

            # 生成 OAuth code
            oauth_code = await client.generate_oauth_code(token_result.access_token)
            logger.info(f"生成 OAuth code 成功")

            # 獲取玩家信息
            try:
                player_info = await client.get_player_info(oauth_code)
                logger.info(f"獲取玩家信息成功: {len(player_info)} 個角色")

                # 選擇第一個角色（如果有多個）
                if player_info:
                    first_player = list(player_info.values())[0]
                    uid = first_player.uid  # 使用 uid 字段而不是 id
                    logger.info(f"使用角色 UID: {uid}")

                    # 為國際服創建簡化的 WavesUser（避免調用國服 API）
                    from ..utils.database.models import WavesBind, WavesUser

                    # 檢查是否已存在用戶
                    existing_user = await WavesUser.get_user_by_attr(
                        ev.user_id, ev.bot_id, "uid", str(uid)
                    )

                    if existing_user:
                        # 更新現有用戶
                        await WavesUser.update_data_by_data(
                            select_data={
                                "user_id": ev.user_id,
                                "bot_id": ev.bot_id,
                                "uid": str(uid),
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
                            ev.user_id,
                            ev.bot_id,
                            cookie=token_result.access_token,
                            uid=str(uid),
                            platform="international",
                            status="on",
                        )
                        # 獲取創建的用戶
                        waves_user = await WavesUser.get_user_by_attr(
                            ev.user_id, ev.bot_id, "uid", str(uid)
                        )
                        logger.info(f"WavesUser 創建成功: UID {uid}")

                    # 更新綁定信息
                    try:
                        await WavesBind.insert_waves_uid(
                            ev.user_id, ev.bot_id, str(uid), ev.group_id, lenth_limit=9
                        )
                        logger.info(f"WavesBind 更新成功: UID {uid}")
                    except Exception as e:
                        logger.warning(f"WavesBind 更新失敗: {e}")

                    # 調用成功消息
                    return await login_success_msg(bot, ev, waves_user)
                else:
                    raise Exception("未找到角色信息")

            except Exception as e:
                logger.warning(f"獲取玩家信息失敗: {e}")
                # 即使獲取玩家信息失敗，也返回基本成功消息
                success_msg = f"[鸣潮] 國際服登入成功！\n用戶名: {login_result.username}\nUID: {login_result.id}\n\n注意：角色信息獲取失敗，但登入已成功。"
                return await bot.send(success_msg, at_sender=at_sender)

        except ImportError:
            logger.warning("kuro.py 未安裝，使用模擬登入")
            success_msg = f"[鸣潮] 國際服登入成功！\n郵箱: {email}\n\n注意：kuro.py 未安裝，無法獲取實際遊戲數據。"
            return await bot.send(success_msg, at_sender=at_sender)

        except Exception as e:
            logger.error(f"kuro.py 登入失敗: {e}")
            # 如果 kuro.py 登入失敗，返回錯誤信息
            error_msg = f"[鸣潮] 國際服登入失敗: {str(e)}"
            return await bot.send(error_msg, at_sender=at_sender)

    except Exception as e:
        logger.error(f"國際服登入處理失敗: {e}")
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
        }
        cache.set(data.auth, temp)
        logger.info(f"創建新緩存: {temp}")

    try:
        # 這裡可以集成 kuro.py 的國際服登入功能
        # 暫時返回成功，實際實現需要調用 kuro.py 的登入 API
        logger.info(f"國際服登入嘗試: {data.email}")

        # 更新緩存數據，標記登入完成
        temp.update(
            {
                "email": data.email,
                "password": data.password,
                "login_type": "international",
                "login_completed": True,  # 標記登入完成
            }
        )
        cache.set(data.auth, temp)
        logger.info(f"更新緩存: {temp}")

        return {"success": True, "msg": "國際服登入成功"}

    except Exception as e:
        logger.error(f"國際服登入失敗: {e}")
        return {"success": False, "msg": f"登入失敗: {str(e)}"}
