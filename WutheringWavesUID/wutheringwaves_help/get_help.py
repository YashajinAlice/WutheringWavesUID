import json
from typing import Dict
from pathlib import Path

from PIL import Image
from gsuid_core.help.model import PluginHelp
from gsuid_core.help.draw_new_plugin_help import get_new_help

from ..utils.image import get_footer
from ..wutheringwaves_config import PREFIX
from ..version import WutheringWavesUID_version

ICON = Path(__file__).parent.parent.parent / "ICON.png"
HELP_DATA = Path(__file__).parent / "help.json"
HELP_DATA_JA = Path(__file__).parent / "help_ja.json"
ICON_PATH = Path(__file__).parent / "icon_path"
TEXT_PATH = Path(__file__).parent / "texture2d"


def get_help_data(lang: str = "zh") -> Dict[str, PluginHelp]:
    # 读取文件内容
    if lang == "ja":
        help_file = HELP_DATA_JA
    else:
        help_file = HELP_DATA
    with open(help_file, "r", encoding="utf-8") as file:
        return json.load(file)


async def get_help(pm: int, lang: str = "zh"):
    plugin_help = get_help_data(lang)
    banner_sub_text = "漂泊者，欢迎在这个时代醒来。" if lang == "zh" else "漂泊者よ、この時代に目覚めることを歓迎する。"
    return await get_new_help(
        plugin_name="WutheringWavesUID",
        plugin_info={f"v{WutheringWavesUID_version}": ""},
        plugin_icon=Image.open(ICON),
        plugin_help=plugin_help,
        plugin_prefix=PREFIX,
        help_mode="dark",
        banner_bg=Image.open(TEXT_PATH / "banner_bg.jpg"),
        banner_sub_text=banner_sub_text,
        help_bg=Image.open(TEXT_PATH / "bg.jpg"),
        cag_bg=Image.open(TEXT_PATH / "cag_bg.png"),
        item_bg=Image.open(TEXT_PATH / "item.png"),
        icon_path=ICON_PATH,
        footer=get_footer(),
        enable_cache=False,
        column=5,
        pm=pm,
    )
