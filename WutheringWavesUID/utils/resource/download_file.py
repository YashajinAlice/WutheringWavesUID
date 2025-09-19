from pathlib import Path
from typing import Union

from PIL import Image
from gsuid_core.utils.download_resource.download_file import download

from .RESOURCE_PATH import (
    FETTER_PATH,
    PHANTOM_PATH,
    MATERIAL_PATH,
    ROLE_DETAIL_SKILL_PATH,
    ROLE_DETAIL_CHAINS_PATH,
)


async def get_skill_img(
    char_id: Union[str, int], skill_name: str, pic_url: str
) -> Image.Image:
    _dir = ROLE_DETAIL_SKILL_PATH / str(char_id)
    _dir.mkdir(parents=True, exist_ok=True)

    skill_name = skill_name.strip()
    name = f"skill_{skill_name}.png"
    _path = _dir / name
    if not _path.exists():
        await download(pic_url, _dir, name, tag="[鸣潮]")

    return Image.open(_path).convert("RGBA")


async def get_chain_img(
    char_id: Union[str, int], order_id: int, pic_url: str
) -> Image.Image:
    _dir = ROLE_DETAIL_CHAINS_PATH / str(char_id)
    _dir.mkdir(parents=True, exist_ok=True)

    name = f"chain_{order_id}.png"
    _path = _dir / name
    if not _path.exists():
        await download(pic_url, _dir, name, tag="[鸣潮]")

    return Image.open(_path).convert("RGBA")


async def get_phantom_img(phantom_id: int, pic_url: str) -> Image.Image:
    # 首先嘗試使用phantom_id構建文件名
    name = f"phantom_{phantom_id}.png"
    _path = PHANTOM_PATH / name

    # 如果文件不存在，嘗試從聲骸數據中獲取monsterId
    if not _path.exists():
        try:
            # 嘗試從聲骸數據中獲取monsterId
            phantom_data_path = (
                Path(__file__).parent.parent
                / "zh-Hant"
                / "Phantom"
                / f"{phantom_id}.json"
            )
            if phantom_data_path.exists():
                import json

                with open(phantom_data_path, "r", encoding="utf-8") as f:
                    phantom_data = json.load(f)
                    monster_id = phantom_data.get("monsterId")
                    if monster_id:
                        # 使用monsterId構建文件名
                        name = f"phantom_{monster_id}.png"
                        _path = PHANTOM_PATH / name
        except Exception:
            pass

    # 如果文件仍然不存在，嘗試下載或使用默認圖片
    if not _path.exists():
        if pic_url:
            await download(pic_url, PHANTOM_PATH, name, tag="[鸣潮]")
        else:
            _path = PHANTOM_PATH / "phantom_390070051.png"

    return Image.open(_path).convert("RGBA")


async def get_fetter_img(name: str, pic_url: str) -> Image.Image:
    name = f"fetter_{name}.png"
    _path = FETTER_PATH / name
    if not _path.exists():
        await download(pic_url, FETTER_PATH, name, tag="[鸣潮]")

    return Image.open(_path).convert("RGBA")


async def get_material_img(material_id: Union[str, int]) -> Image.Image:
    name = f"material_{material_id}.png"
    _path = MATERIAL_PATH / name
    return Image.open(_path).convert("RGBA")
