"""
增強PCAP系統與刷新面板的整合模組
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from gsuid_core.logger import logger

from .enhanced_pcap_processor import get_enhanced_data
from .data_merger import merge_enhanced_data_to_rawdata


async def check_and_use_enhanced_data(uid: str) -> Dict[str, Any]:
    """
    檢查是否有增強PCAP數據，如果有則使用它來更新原始數據

    Args:
        uid: 用戶ID

    Returns:
        處理結果
    """
    try:
        # 1. 檢查是否有增強PCAP數據
        enhanced_data = await get_enhanced_data(uid)

        if not enhanced_data:
            return {"has_enhanced_data": False, "message": "沒有找到增強PCAP數據"}

        logger.info(f"🔍 發現增強PCAP數據: {uid} - {len(enhanced_data)}個角色")

        # 2. 合併增強數據到原始數據
        merge_result = await merge_enhanced_data_to_rawdata(uid, enhanced_data)

        if merge_result.get("success"):
            return {
                "has_enhanced_data": True,
                "enhanced_update_applied": True,
                "merge_result": merge_result,
                "message": "✅ 增強PCAP數據已成功更新到面板數據",
            }
        else:
            return {
                "has_enhanced_data": True,
                "enhanced_update_applied": False,
                "error": merge_result.get("error"),
                "message": f"❌ 增強數據更新失敗: {merge_result.get('error')}",
            }

    except Exception as e:
        logger.exception(f"增強數據整合失敗: {uid} - {e}")
        return {
            "has_enhanced_data": False,
            "enhanced_update_applied": False,
            "error": str(e),
            "message": f"❌ 增強數據處理失敗: {str(e)}",
        }


async def get_enhanced_update_summary(uid: str) -> Optional[str]:
    """
    獲取增強數據更新摘要信息

    Args:
        uid: 用戶ID

    Returns:
        摘要信息字符串
    """
    try:
        result = await check_and_use_enhanced_data(uid)

        if not result.get("has_enhanced_data"):
            return None

        if not result.get("enhanced_update_applied"):
            return f"⚠️ {result.get('message', '增強數據處理失敗')}"

        merge_result = result.get("merge_result", {})

        summary_parts = [
            "🚀 增強PCAP數據更新摘要:",
            f"• 總角色數: {merge_result.get('total_roles', 0)}",
            f"• 新增角色: {merge_result.get('new_roles', 0)}",
            f"• 更新角色: {merge_result.get('updated_roles', 0)}",
            f"• 等級變化: {merge_result.get('level_changes', 0)}",
            f"• 武器變化: {merge_result.get('weapon_changes', 0)}",
            f"• 聲骸變化: {merge_result.get('phantom_changes', 0)}",
            f"• 技能變化: {merge_result.get('skill_changes', 0)}",
        ]

        return "\n".join(summary_parts)

    except Exception as e:
        logger.exception(f"獲取增強更新摘要失敗: {uid} - {e}")
        return f"❌ 增強數據摘要獲取失敗: {str(e)}"


async def format_enhanced_changes_detail(uid: str) -> Optional[str]:
    """
    格式化增強數據變化詳情

    Args:
        uid: 用戶ID

    Returns:
        詳細變化信息
    """
    try:
        result = await check_and_use_enhanced_data(uid)

        if not result.get("enhanced_update_applied"):
            return None

        merge_result = result.get("merge_result", {})
        details = merge_result.get("details", {})

        detail_parts = []

        # 等級變化詳情
        if details.get("level_changes"):
            detail_parts.append("📈 等級變化:")
            for change in details["level_changes"][:5]:  # 最多顯示5個
                detail_parts.append(
                    f"  • {change['roleName']}: {change['old_level']} → {change['new_level']}"
                )
            if len(details["level_changes"]) > 5:
                detail_parts.append(
                    f"  ... 還有 {len(details['level_changes']) - 5} 個角色"
                )

        # 武器變化詳情
        if details.get("weapon_changes"):
            detail_parts.append("🗡️ 武器變化:")
            for change in details["weapon_changes"][:3]:  # 最多顯示3個
                detail_parts.append(
                    f"  • {change['roleName']}: {change['old_weapon']} → {change['new_weapon']}"
                )
            if len(details["weapon_changes"]) > 3:
                detail_parts.append(
                    f"  ... 還有 {len(details['weapon_changes']) - 3} 個角色"
                )

        # 聲骸變化詳情
        if details.get("phantom_changes"):
            detail_parts.append("👻 聲骸變化:")
            for change in details["phantom_changes"][:3]:  # 最多顯示3個
                phantom_diff = change.get("phantom_diff", {})
                phantom_change_count = len(phantom_diff.get("phantom_changes", []))
                detail_parts.append(
                    f"  • {change['roleName']}: {phantom_change_count}個聲骸位變化"
                )
            if len(details["phantom_changes"]) > 3:
                detail_parts.append(
                    f"  ... 還有 {len(details['phantom_changes']) - 3} 個角色"
                )

        # 新角色
        if details.get("new_roles"):
            detail_parts.append(f"🆕 新增 {len(details['new_roles'])} 個角色")

        return "\n".join(detail_parts) if detail_parts else None

    except Exception as e:
        logger.exception(f"格式化增強變化詳情失敗: {uid} - {e}")
        return f"❌ 詳情獲取失敗: {str(e)}"
