from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger

from ..utils.at_help import ruser_id
from ..utils.database.models import WavesBind
from ..utils.error_reply import ERROR_CODE, WAVES_CODE_103

# 增強PCAP解析系統服務
sv_enhanced_pcap = SV("增强pcap解析", priority=5)


# 解析指令 - 支持附件文件處理
@sv_enhanced_pcap.on_fullmatch(
    (
        "解析",
        "增强解析",
        "增强pcap解析",
        "jc",
    )
)
async def enhanced_pcap_parse(bot: Bot, ev: Event):
    """增強PCAP解析指令"""
    await bot.logger.info(f"[增强PCAP]开始执行[解析]: {ev.user_id}")

    uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    if not uid:
        return await bot.send(ERROR_CODE[WAVES_CODE_103])

    # 檢查是否有附件文件
    attachment_file = None
    for msg in ev.content:
        if msg.type == "attachment":
            attachment_file = msg.data
            break

    if attachment_file:
        # 如果有附件，處理文件
        file_name = attachment_file.get("filename", "")
        file_url = attachment_file.get("url", "")
        file_size = attachment_file.get("size", 0)

        # 檢查文件格式
        if not file_name.lower().endswith((".pcap", ".pcapng")):
            return await bot.send("[鸣潮] 請上傳 .pcap 或 .pcapng 格式的文件")

        # 檢查文件大小 (50MB限制)
        if file_size > 50 * 1024 * 1024:
            return await bot.send("[鸣潮] 文件過大，請上傳小於 50MB 的文件")

        await bot.send("[鸣潮] 正在解析中，请稍候...")

        try:
            import aiohttp

            from .enhanced_pcap_processor import process_enhanced_pcap_file

            # 下載文件內容
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    if response.status == 200:
                        file_content = await response.read()
                    else:
                        return await bot.send(
                            f"❌ 文件下載失敗，HTTP狀態碼: {response.status}"
                        )

            result = await process_enhanced_pcap_file(file_content, uid, ev.user_id)

            if result.get("error"):
                await bot.send(result["error"])
            elif result.get("success"):
                success_msg = f"""[鸣潮] 数据解析成功！

解析数据提取成功！
• 提取角色数量: {result['role_count']}
《 新系统尚在测试中，若有异常请告知开发者检查》
🎯 在使用面板前务必使用 刷新面板！"""

                await bot.send(success_msg)
            else:
                await bot.send("[鸣潮] 处理失败，未知错误")

        except Exception as e:
            logger.exception(f"[鸣潮] PCAP文件处理失败: {e}")
            await bot.send(f"[鸣潮] 处理过程中发生错误: {str(e)}")

    else:
        # 如果沒有附件，顯示狀態
        from .enhanced_pcap_processor import get_enhanced_data

        enhanced_data = await get_enhanced_data(uid)

        if enhanced_data:
            role_count = len(enhanced_data)
            status_msg = f"""[鸣潮] 已找到PCAP数据

📊 数据统计:
• 角色数量: {role_count}
《 若成功率非100%，请告知开发者检查是否存在有尚未支援的声骸或属性》
💡 现在可以使用「刷新面板」查看详细数据"""

            await bot.send(status_msg)
        else:
            await bot.send("[鸣潮] 未找到PCAP数据，请先上传并解析pcap文件")
