from gsuid_core.models import Event


def ruser_id(ev: Event) -> str:
    # 延遲導入以避免循環依賴
    try:
        from ..wutheringwaves_config.wutheringwaves_config import (
            WutheringWavesConfig,
        )

        AtCheck = WutheringWavesConfig.get_config("AtCheck").data
        if AtCheck:
            return ev.at if ev.at else ev.user_id
        else:
            return ev.user_id
    except ImportError:
        # 如果配置模組無法導入，使用默認行為
        return ev.user_id


def is_valid_at(ev: Event) -> bool:
    return ev.user_id != ruser_id(ev)
