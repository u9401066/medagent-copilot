"""
Reminder - MCP 工具回傳提醒系統

每個 MCP 工具回傳都會附帶簡短提醒，強化正確行為
注意：這不是「憲法」本身，憲法原則在 .med_memory/CONSTITUTION.md
      任務特定知識在 .med_memory/knowledge/
"""

import json

# 核心提醒 - 精簡版，每次都顯示
CORE_REMINDER = "📜 One patient at a time | Answer: JSON array like '[\"value\"]' or '[90]' or '[-1]' or '[]'"


def with_reminder(result: dict | str) -> str:
    """為工具回傳結果附加提醒
    
    Args:
        result: 原始回傳結果 (dict 或 str)
        
    Returns:
        附加提醒的 JSON 字串
    """
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except:
            return result + "\n" + CORE_REMINDER
    
    if isinstance(result, dict):
        result["_reminder"] = CORE_REMINDER
    
    return json.dumps(result, indent=2, ensure_ascii=False)
