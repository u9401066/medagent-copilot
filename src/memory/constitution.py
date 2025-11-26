"""
Constitution - 憲法提醒系統

每個工具回傳都會附帶憲法提醒，確保 Copilot 遵守隱私保護規則
"""

import json

CONSTITUTION_REMINDER = """
📜 [CONSTITUTION REMINDER]
• 記憶系統: knowledge/ (通用醫學) + patient_context/ (個人化，僅限當前病人)
• 隱私規則: 一次只能處理一位病人，任務結束後清除 patient_context
• 時間點: 2023-11-13T10:15:00+00:00
• 答案格式: JSON 陣列字串，如 '["S6534835"]', '[90]', '[-1]', '[]'
"""


def with_constitution(result: dict | str) -> str:
    """為工具回傳結果附加憲法提醒
    
    Args:
        result: 原始回傳結果 (dict 或 str)
        
    Returns:
        附加憲法提醒的 JSON 字串
    """
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except:
            return result + "\n" + CONSTITUTION_REMINDER
    
    if isinstance(result, dict):
        result["_constitution_reminder"] = CONSTITUTION_REMINDER.strip()
    
    return json.dumps(result, indent=2, ensure_ascii=False)
