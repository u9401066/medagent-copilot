"""
Reminder - MCP 工具回傳提醒系統

每個 MCP 工具回傳都會附帶簡短提醒，強化正確行為
注意：這不是「憲法」本身，憲法原則在 .med_memory/CONSTITUTION.md
      任務特定知識在 .med_memory/knowledge/
"""

import json
from pathlib import Path

# 核心提醒 - 精簡版，每次都顯示
CORE_REMINDER = """📜 REMEMBER:
- One patient at a time
- Check med://knowledge/clinical for thresholds & dosing
- Answer format: JSON array like '["value"]' or '[90]' or '[-1]' or '[]'"""


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
