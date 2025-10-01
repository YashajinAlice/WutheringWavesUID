from typing import Optional

from gsuid_core.sv import get_plugin_available_prefix

from .error_reply import ERROR_CODE

PREFIX = get_plugin_available_prefix("WutheringWavesUID")

BIND_UID_HINT = f"你还没有添加ck哦, 请使用 {PREFIX}添加CK 完成绑定！"

WAVES_ERROR_CODE = {}
WAVES_ERROR_CODE.update(ERROR_CODE)


def error_reply(code: Optional[int] = None, msg: str = "") -> str:
    msg_list = []
    if isinstance(code, int):
        msg_list.append(f"❌错误代码为: {code}")
    if msg:
        msg_list.append(f"📝错误信息: {msg}")
    elif code in WAVES_ERROR_CODE:
        msg_list.append(f"📝错误信息: {WAVES_ERROR_CODE[code]}")
    return "\n".join(msg_list)
