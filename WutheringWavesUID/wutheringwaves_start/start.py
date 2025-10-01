from gsuid_core.logger import logger
from gsuid_core.server import on_core_start


# 延遲導入以避免循環依賴
def get_startup():
    from ..wutheringwaves_resource import startup

    return startup


@on_core_start
async def all_start():
    logger.info("[鸣潮] 启动中...")
    try:
        from ..utils.queues import init_queues
        from ..utils.damage.register_char import register_char
        from ..utils.damage.register_echo import register_echo
        from ..utils.limit_user_card import load_limit_user_card
        from ..utils.damage.register_weapon import register_weapon
        from ..utils.map.damage.register import register_rank, register_damage

        # 注册
        register_weapon()
        register_echo()
        register_damage()
        register_rank()
        register_char()

        # 初始化任务队列
        init_queues()

        # 加载角色极限面板
        card_list = await load_limit_user_card()
        logger.info(f"[鸣潮][加载角色极限面板] 数量: {len(card_list)}")

        startup = get_startup()
        await startup()
    except Exception as e:
        logger.exception(e)

    logger.success("[鸣潮] 启动完成✅")
