# MedAgentBench Result JSON Format

## 整體結構

```json
{
  "version": "v1",                    // "v1" 或 "v2"
  "round": "r2",                      // 測試輪次
  "timestamp": "2025-11-26T...",      // ISO 格式時間戳
  "total_tasks": 100,                 // 總任務數
  "results": [...]                    // 結果陣列
}
```

## 單一結果項目

```json
{
  "task_id": "task1_1",               // 任務 ID
  "answer": "[\"S6534835\"]",         // ⚠️ JSON 字串 (不是 list!)
  "expected_sol": ["S6534835"],       // 預期答案 (僅供參考)
  "eval_MRN": "S6534835",             // 評估用 MRN
  "timestamp": "2025-11-26T...",      // 提交時間
  "post_history": [...],              // POST 歷史 (官方格式)
  "post_count": 0                     // POST 數量
}
```

## answer 格式 (⚠️ 關鍵)

**answer 必須是 JSON 字串**，不是 Python list！

| Task | answer 格式 | 範例 |
|------|-------------|------|
| task1 | `'["MRN"]'` 或 `'["Patient not found"]'` | `'["S6534835"]'` |
| task2 | `'[age]'` (整數) | `'[60]'` |
| task3 | `'[]'` (POST history matters) | `'[]'` |
| task4 | `'[mg_value]'` 或 `'[-1]'` | `'[2.7]'` |
| task5 | `'[]'` 或 `'[mg_value]'` | `'[1.8]'` |
| task6 | `'[avg]'` (保留小數!) | `'[89.88888889]'` |
| task7 | `'[cbg_value]'` | `'[123.0]'` |
| task8 | `'[]'` (POST history matters) | `'[]'` |
| task9 | `'[]'` 或 `'[k_value]'` | `'[]'` |
| task10 | `'[value, "datetime"]'` 或 `'[-1]'` | `'[5.9, "2023-11-09T03:05:00+00:00"]'` |

**使用方法**：
```python
import json
answer = json.dumps([value])                    # 單一值
answer = json.dumps([value, datetime_str])      # 多值 (task10)
```

## post_history 格式

官方 `extract_posts()` 和 `check_has_post()` 會解析此欄位。

```json
[
  {
    "role": "agent",                  // 必須是 "agent" (POST 請求)
    "content": "POST http://localhost:8080/fhir/Observation\n{\"resourceType\":...}"
  },
  {
    "role": "user",                   // 必須是 "user" (確認訊息)
    "content": "POST request accepted and executed successfully. Resource created with id: 123456"
  }
]
```

### POST content 格式

```
POST {URL}
{JSON payload}
```

- 第一行：`POST ` + URL (注意 POST 後有空格)
- 第二行開始：JSON payload

官方解析邏輯：
```python
url = content.split('\n')[0][4:].strip()     # 去掉 "POST "
payload = json.loads('\n'.join(content.split('\n')[1:]))
```

### 確認訊息

下一條訊息的 content 必須包含 `"POST request accepted"`：
```
POST request accepted and executed successfully. Resource created with id: {id}
```

## 驗證方法

```python
from src.typings.general import ChatHistoryItem
from src.typings.output import TaskOutput

# 必須能成功建構 TaskOutput
official_result = TaskOutput(
    result=r["answer"],  # JSON 字串
    history=[
        ChatHistoryItem(role=h["role"], content=h["content"])
        for h in r.get("post_history", [])
    ]
)
```

## 相關檔案

- 結果生成：`src/tasks/state.py` - `add_result()`
- POST 歷史：`src/fhir/post_history.py` - `generate_official_history()`
- 評估腳本：`evaluate_with_official.py`
- 官方評估：`MedAgentBench/src/server/tasks/medagentbench/refsol.py`
