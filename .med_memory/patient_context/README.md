# Patient Context (病人情境記憶)

> ⚠️ **此目錄用於存放當前任務的病人工作記憶**
> 
> ⛔ **一次只能有一位病人的資料**

## 使用規則

1. 任務開始時，MCP 會自動在此建立 `current_patient.json`
2. 任務結束時，必須呼叫 `clear_patient_context()` 清除
3. 永遠不要手動編輯此目錄的檔案

## 檔案格式

```json
{
  "mrn": "S6534835",
  "loaded_at": "2025-11-26T10:15:00",
  "task_id": "task1_1",
  "fhir_id": "abc123",
  "cache": {
    "observations": [...],
    "medications": [...]
  }
}
```

## 隱私保護

- 此目錄的內容在 Git 中被忽略
- 每次任務結束後自動清除
- 禁止跨病人存取
