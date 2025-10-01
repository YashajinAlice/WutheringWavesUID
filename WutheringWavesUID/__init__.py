"""init"""

from gsuid_core.sv import Plugins

# 導入付費機制模組以註冊指令
from . import wutheringwaves_payment

Plugins(name="WutheringWavesUID", force_prefix=["ww"], allow_empty_prefix=False)
