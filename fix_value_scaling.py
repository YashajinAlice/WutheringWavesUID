#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修復數值縮放問題的腳本
參考上游PCAP解析器的處理方式
"""

import re
import json
from typing import Any, Dict, List, Tuple


def is_property_percent(attribute_name: str) -> bool:
    """
    判斷屬性是否為百分比類型
    參考上游PCAP解析器的邏輯
    """
    percent_attributes = [
        "攻擊",
        "生命",
        "防禦",  # 這些可能是百分比也可能是固定值，需要根據數值判斷
        "暴擊",
        "暴擊傷害",
        "共鳴效率",
        "普攻傷害加成",
        "重擊傷害加成",
        "共鳴技能傷害加成",
        "共鳴解放傷害加成",
        "氣動傷害加成",
        "導電傷害加成",
        "熱熔傷害加成",
        "凝聚傷害加成",
        "衍射傷害加成",
        "治療效果加成",
    ]

    # 明確的百分比屬性
    explicit_percent = [
        "暴擊",
        "暴擊傷害",
        "共鳴效率",
        "普攻傷害加成",
        "重擊傷害加成",
        "共鳴技能傷害加成",
        "共鳴解放傷害加成",
        "氣動傷害加成",
        "導電傷害加成",
        "熱熔傷害加成",
        "凝聚傷害加成",
        "衍射傷害加成",
        "治療效果加成",
    ]

    if attribute_name in explicit_percent:
        return True

    # 對於攻擊、生命、防禦，需要根據數值大小判斷
    if attribute_name in ["攻擊", "生命", "防禦"]:
        return None  # 需要根據數值判斷

    return False


def format_property_value(attribute_name: str, value: str) -> str:
    """
    格式化屬性數值
    參考上游PCAP解析器的 _format_property_value 函數
    """
    # 如果已經是百分比格式，直接返回
    if isinstance(value, str) and "%" in value:
        return value

    # 嘗試轉換為數值
    try:
        if isinstance(value, str):
            # 移除百分號並轉換為浮點數
            numeric_value = float(value.replace("%", ""))
        else:
            numeric_value = float(value)
    except (ValueError, TypeError):
        # 如果轉換失敗，返回原始值
        return str(value)

    # 判斷是否為百分比屬性
    is_percent = is_property_percent(attribute_name)

    if is_percent is True:
        # 明確的百分比屬性
        return format_percentage_value(numeric_value)
    elif is_percent is None:
        # 需要根據數值判斷的屬性（攻擊、生命、防禦）
        return format_ambiguous_value(attribute_name, numeric_value)
    else:
        # 固定值屬性
        return str(int(numeric_value))


def format_percentage_value(numeric_value: float) -> str:
    """
    格式化百分比數值
    參考上游PCAP解析器的邏輯
    """
    # 關鍵邏輯：檢測數值是否被錯誤放大
    if numeric_value > 100:
        # 如果數值大於100，說明被錯誤放大了100倍
        # 需要除以100來修正
        percentage_value = numeric_value / 100.0
        return f"{percentage_value:.2f}%"
    else:
        # 如果數值小於等於100，直接使用
        return f"{numeric_value:.2f}%"


def format_ambiguous_value(attribute_name: str, numeric_value: float) -> str:
    """
    格式化需要判斷的屬性數值（攻擊、生命、防禦）
    根據數值大小判斷是百分比還是固定值
    """
    # 根據遊戲數值範圍判斷
    if attribute_name == "攻擊":
        if numeric_value > 1000:  # 固定攻擊值通常很大
            return str(int(numeric_value))
        elif numeric_value > 100:  # 可能是被放大的百分比值
            return format_percentage_value(numeric_value)
        else:  # 百分比攻擊值通常小於100
            return format_percentage_value(numeric_value)
    elif attribute_name == "生命":
        if numeric_value > 10000:  # 固定生命值通常很大
            return str(int(numeric_value))
        elif numeric_value > 100:  # 可能是被放大的百分比值
            return format_percentage_value(numeric_value)
        else:  # 百分比生命值通常小於100
            return format_percentage_value(numeric_value)
    elif attribute_name == "防禦":
        if numeric_value > 1000:  # 固定防禦值通常很大
            return str(int(numeric_value))
        elif numeric_value > 100:  # 可能是被放大的百分比值
            return format_percentage_value(numeric_value)
        else:  # 百分比防禦值通常小於100
            return format_percentage_value(numeric_value)
    else:
        return str(int(numeric_value))


def fix_phantom_values(phantom_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    修復聲骸數值
    """
    fixed_phantom = phantom_data.copy()

    # 修復主詞條
    if "mainProps" in fixed_phantom:
        for main_prop in fixed_phantom["mainProps"]:
            if "attributeName" in main_prop and "attributeValue" in main_prop:
                original_value = main_prop["attributeValue"]
                fixed_value = format_property_value(
                    main_prop["attributeName"], original_value
                )
                main_prop["attributeValue"] = fixed_value
                print(
                    f"主詞條修復: {main_prop['attributeName']} {original_value} -> {fixed_value}"
                )

    # 修復副詞條
    if "subProps" in fixed_phantom:
        for sub_prop in fixed_phantom["subProps"]:
            if "attributeName" in sub_prop and "attributeValue" in sub_prop:
                original_value = sub_prop["attributeValue"]
                fixed_value = format_property_value(
                    sub_prop["attributeName"], original_value
                )
                sub_prop["attributeValue"] = fixed_value
                print(
                    f"副詞條修復: {sub_prop['attributeName']} {original_value} -> {fixed_value}"
                )

    return fixed_phantom


def test_fix_with_yuno_data():
    """
    使用尤諾數據測試修復效果
    """
    print("=== 尤諾聲骸數值修復測試 ===")

    # 模擬尤諾的聲骸數據（基於之前的分析）
    test_phantoms = [
        {
            "cost": 4,
            "mainProps": [{"attributeName": "暴擊傷害", "attributeValue": "44"}],
            "subProps": [
                {"attributeName": "攻擊", "attributeValue": "150"},
                {"attributeName": "生命", "attributeValue": "7.9"},
                {"attributeName": "攻擊", "attributeValue": "10.9"},
                {"attributeName": "暴擊傷害", "attributeValue": "18.6"},
                {"attributeName": "共鳴解放傷害加成", "attributeValue": "7.9"},
                {"attributeName": "防禦", "attributeValue": "60"},
            ],
        },
        {
            "cost": 3,
            "mainProps": [{"attributeName": "氣動傷害加成", "attributeValue": "30"}],
            "subProps": [
                {"attributeName": "攻擊", "attributeValue": "100"},
                {"attributeName": "暴擊", "attributeValue": "9.3"},
                {"attributeName": "共鳴效率", "attributeValue": "9.2"},
                {"attributeName": "暴擊傷害", "attributeValue": "13.8"},
                {"attributeName": "攻擊", "attributeValue": "50"},
                {"attributeName": "共鳴技能傷害加成", "attributeValue": "10.1"},
            ],
        },
        {
            "cost": 1,
            "mainProps": [{"attributeName": "攻擊", "attributeValue": "18"}],
            "subProps": [
                {"attributeName": "生命", "attributeValue": "2280"},
                {"attributeName": "暴擊", "attributeValue": "9.3"},
                {"attributeName": "暴擊傷害", "attributeValue": "15"},
                {"attributeName": "攻擊", "attributeValue": "40"},
                {"attributeName": "攻擊", "attributeValue": "8.6"},
                {"attributeName": "普攻傷害加成", "attributeValue": "8.6"},
            ],
        },
    ]

    print("\n修復前後對比:")
    for i, phantom in enumerate(test_phantoms, 1):
        print(f"\n--- 聲骸 {i} (Cost: {phantom['cost']}) ---")
        fixed_phantom = fix_phantom_values(phantom)

        print("修復後的主詞條:")
        for main_prop in fixed_phantom["mainProps"]:
            print(f"  {main_prop['attributeName']}: {main_prop['attributeValue']}")

        print("修復後的副詞條:")
        for sub_prop in fixed_phantom["subProps"]:
            print(f"  {sub_prop['attributeName']}: {sub_prop['attributeValue']}")


if __name__ == "__main__":
    test_fix_with_yuno_data()
