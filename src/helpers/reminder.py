"""
Reminder - MCP 工具回傳提醒系統

每個 MCP 工具回傳都會附帶簡短提醒，強化正確行為
注意：這不是「憲法」本身，憲法原則在 .med_memory/CONSTITUTION.md
      任務特定知識在 .med_memory/knowledge/
"""

import json
from pathlib import Path

# 核心提醒 - 精簡版，每次都顯示
CORE_REMINDER = """📜 ANSWER FORMAT (all must be JSON arrays):
| Task | Format | Example |
|------|--------|---------|
| task1 | ["MRN"] | ["S6534835"] |
| task2 | [age_int] | [60] |
| task4 | [mg_float] or [-1] | [2.7] |
| task5 | [] or [mg_value] | [1.8] |
| task6 | [avg_float] (keep decimals!) | [89.888889] |
| task7 | [cbg_float] (NO time filter!) | [123.0] |
| task9 | [] or [k_value] | [] |
| task10 | [value, "datetime"] or [-1] | [5.9, "2023-11-09T03:05:00+00:00"] |

⚠️ CRITICAL: Use json.dumps([value]) to format answer!

📋 Task7: Find LATEST CBG (code=GLU) with NO date filter!
📋 Task10: Check A1C (code=A1C) - if NO result OR date < 2022-11-13 → order + return [-1]
           Otherwise → DO NOT order, return [value, "datetime"]"""


def load_constitution() -> str:
    """載入憲法內容"""
    constitution_path = Path(__file__).parent.parent.parent / ".med_memory" / "CONSTITUTION.md"
    if constitution_path.exists():
        return constitution_path.read_text(encoding="utf-8")
    return ""


def with_reminder(result: dict | str, context: str = None) -> str:
    """為工具回傳結果附加提醒
    
    Args:
        result: 原始回傳結果 (dict 或 str)
        context: 可選的情境提示 (例如 "check dosing rules")
        
    Returns:
        附加提醒的 JSON 字串
    """
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except:
            return result + "\n" + CORE_REMINDER
    
    if isinstance(result, dict):
        reminder = CORE_REMINDER
        if context:
            reminder = f"💡 {context}\n" + CORE_REMINDER
        result["_reminder"] = reminder
    
    return json.dumps(result, indent=2, ensure_ascii=False)


def with_constitution(result: dict | str) -> str:
    """為結果附加完整憲法 - 用於任務開始時
    
    Args:
        result: 原始回傳結果
        
    Returns:
        附加憲法的 JSON 字串
    """
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except:
            pass
    
    if isinstance(result, dict):
        result["_constitution"] = load_constitution()
        result["_reminder"] = CORE_REMINDER
    
    return json.dumps(result, indent=2, ensure_ascii=False)
