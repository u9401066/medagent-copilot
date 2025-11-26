# MedAgentBench Task Instructions

## 任務概述

你是一個醫療 AI 助手，需要透過 FHIR API 與電子健康記錄 (EHR) 系統互動來完成各種醫療任務。

## ⚠️ 答案格式 (極重要)

**所有答案必須是 JSON 字串格式**，使用 `json.dumps()` 產生：

```python
import json
answer = json.dumps([value])                    # 單一值
answer = json.dumps([value, datetime_str])      # 多值 (task10)
```

### 各任務答案格式

| Task | 答案格式 | 正確範例 | 錯誤範例 |
|------|----------|----------|----------|
| task1 | `'["MRN"]'` 或 `'["Patient not found"]'` | `'["S6534835"]'` | `"S6534835"` |
| task2 | `'[age]'` (整數) | `'[60]'` | `'["60"]'` |
| task3 | `'[]'` (POST history matters) | `'[]'` | 任何其他值 |
| task4 | `'[mg_value]'` 或 `'[-1]'` | `'[2.7]'` | `'["2.7"]'` |
| task5 | `'[]'` 或 `'[mg_value]'` | `'[1.8]'` | `'["ordered"]'` |
| task6 | `'[avg]'` **保留小數!** | `'[89.88888889]'` | `'[90]'` |
| task7 | `'[cbg_value]'` | `'[123.0]'` | `'["123"]'` |
| task8 | `'[]'` (POST history matters) | `'[]'` | 任何其他值 |
| task9 | `'[]'` 或 `'[k_value]'` | `'[]'` | `'[3.4]'` 當 K≥3.5 |
| task10 | `'[value, "datetime"]'` 或 `'[-1]'` | `'[5.9, "2023-11-09T03:05:00+00:00"]'` | `'[5.9]'` |

### 關鍵規則

1. **Task 2**: 年齡是整數，不是字串 → `[60]` 不是 `["60"]`
2. **Task 6**: 保留所有小數位 → `[89.88888889]` 不是 `[90]`
3. **Task 9**: K ≥ 3.5 時答案是 `[]`，只有 K < 3.5 才回報值並下 order
4. **Task 10**: 必須包含日期時間 → `[5.9, "datetime"]`

## 任務類型

### Task 1: 病患搜尋 (Patient Search)
- 目標: 根據姓名和生日查詢病患 MRN
- API: `GET /Patient?name={name}&birthdate={date}`
- 答案: `'["MRN"]'` 或 `'["Patient not found"]'`
- POST: ❌ 不需要

### Task 2: 年齡計算 (Age Calculation)
- 目標: 根據 MRN 計算病患年齡 (參考時間: 2023-11-13)
- API: `GET /Patient?identifier={MRN}`
- 答案: `'[age]'` 整數
- POST: ❌ 不需要

### Task 3: 記錄血壓 (Record Blood Pressure)
- 目標: 為病患記錄血壓測量值
- API: `POST /Observation` with vital signs data
- Flowsheet ID: BP
- 答案: `'[]'` (POST history 會被檢查)
- POST: ✅ 必須 1 個

### Task 4: 查詢鎂離子 (Magnesium Level)
- 目標: 查詢 24 小時內的鎂離子值
- API: `GET /Observation?patient={id}&code=MG&date=ge2023-11-12T10:15:00+00:00`
- 答案: `'[mg_value]'` 或 `'[-1]'` (無資料時)
- POST: ❌ 不需要

### Task 5: 鎂離子補充 (Magnesium Replacement)
- 目標: 檢查鎂離子值，如果 < 2.0 則開立補充醫囑
- NDC: 0338-1715-40 (IV Magnesium)
- 劑量規則:
  - 輕度 (1.5-1.9 mg/dL): 1g IV over 1 hour
  - 中度 (1.0-<1.5 mg/dL): 2g IV over 2 hours
  - 重度 (<1.0 mg/dL): 4g IV over 4 hours
- 答案: `'[]'` (Mg ≥ 2.0) 或 `'[mg_value]'` (Mg < 2.0 且已 POST)
- POST: ✅ 只有當 Mg < 2.0 才需要

### Task 6: 平均血糖 (Average CBG)
- 目標: 計算 24 小時內的平均血糖
- API: `GET /Observation?patient={id}&code=GLU&date=ge2023-11-12T10:15:00+00:00`
- 答案: `'[avg]'` **保留所有小數位!** 或 `'[-1]'` (無資料時)
- POST: ❌ 不需要

### Task 7: 最新血糖 (Latest CBG)
- 目標: 查詢最新的血糖值
- API: `GET /Observation?patient={id}&code=GLU`
- 答案: `'[cbg_value]'`
- POST: ❌ 不需要

### Task 8: 骨科轉診 (Orthopedic Referral)
- 目標: 開立骨科手術轉診單 (含 SBAR note)
- API: `POST /ServiceRequest`
- SNOMED Code: 306181000000106
- 答案: `'[]'` (POST history 會被檢查)
- POST: ✅ 必須 1 個

### Task 9: 鉀離子補充 (Potassium Replacement)
- 目標: 檢查鉀離子值，如果 < 3.5 則:
  1. POST 補充醫囑 (每低 0.1 補 10 mEq)
  2. POST 隔天早上抽血 (2023-11-14T06:00:00+00:00)
- NDC: 40032-917-01 (Potassium)
- LOINC: 2823-3 (Serum Potassium)
- 劑量: `round((3.5 - k_value) / 0.1) * 10` mEq
- 答案: `'[]'` (K ≥ 3.5) 或 `'[k_value]'` (K < 3.5 且已 POST 2 個)
- POST: ✅ 只有當 K < 3.5 才需要 **2 個** POST

### Task 10: HbA1C 檢查 (HbA1C Check)
- 目標: 查詢 HbA1C，如果無資料或超過一年則開新檢驗
- API: `GET /Observation?patient={id}&code=A1C`
- LOINC: 4548-4 (HbA1C order)
- 一年前截止: 2022-11-13T10:15:00+00:00
- 答案: `'[value, "datetime"]'` (有效資料) 或 `'[-1]'` (需要開新檢驗)
- POST: ✅ 只有當資料缺失或超過一年才需要

## 常用 FHIR 路徑

- 病患: `/Patient`
- 觀察值 (檢驗/生命徵象): `/Observation`
- 藥物醫囑: `/MedicationRequest`
- 服務請求 (轉診/檢驗): `/ServiceRequest`
- 問題清單: `/Condition`

## 重要時間參數

| 參數 | 值 |
|------|-----|
| 參考時間 | `2023-11-13T10:15:00+00:00` |
| 24h 過濾 | `ge2023-11-12T10:15:00+00:00` |
| 1 年前截止 | `2022-11-13T10:15:00+00:00` |
| 隔天早上 (Task 9) | `2023-11-14T06:00:00+00:00` |

## POST 歷史格式

MCP 會自動記錄 POST 歷史，格式如下：

```json
{
  "role": "agent",
  "content": "POST http://localhost:8080/fhir/Observation\n{\"resourceType\":...}"
}
```

官方評估器會解析此格式驗證 POST 請求是否正確。
