from __future__ import annotations

import math
from typing import Any


def calculate_growth_rate(
    current_value: float,
    previous_value: float,
) -> dict[str, Any]:
    """計算目前期間相較於前一期間的成長率。

    適合用於計算：
    - 營收成長率
    - 訂單數成長率
    - 銷售件數成長率
    - 顧客數成長率

    計算公式：
        (current_value - previous_value) / previous_value

    Args:
        current_value:
            目前期間的指標數值。

        previous_value:
            前一期間的指標數值。

    Returns:
        包含原始數值、成長率小數及成長率百分比的結果。
        若前期數值為零或輸入不是有效數字，回傳錯誤資訊。
    """

    if not math.isfinite(current_value):
        return {
            "status": "error",
            "growth_rate": None,
            "growth_rate_percent": None,
            "reason": "current_value 必須是有限數值。",
        }

    if not math.isfinite(previous_value):
        return {
            "status": "error",
            "growth_rate": None,
            "growth_rate_percent": None,
            "reason": "previous_value 必須是有限數值。",
        }

    if previous_value == 0:
        return {
            "status": "error",
            "current_value": current_value,
            "previous_value": previous_value,
            "growth_rate": None,
            "growth_rate_percent": None,
            "reason": "前期數值為零，無法計算成長率。",
        }

    growth_rate = (
        current_value - previous_value
    ) / previous_value

    return {
        "status": "success",
        "current_value": current_value,
        "previous_value": previous_value,
        "difference": current_value - previous_value,
        "growth_rate": round(growth_rate, 6),
        "growth_rate_percent": round(
            growth_rate * 100,
            2,
        ),
    }