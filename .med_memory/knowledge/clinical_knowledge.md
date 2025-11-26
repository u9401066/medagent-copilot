# Clinical Knowledge Reference

## 電解質正常值

### 鎂離子 (Magnesium)
- 正常範圍: 1.7-2.2 mg/dL
- 低鎂血症 (Hypomagnesemia): < 1.7 mg/dL
  - 輕度: 1.5-1.7 mg/dL
  - 中度: 1.0-1.5 mg/dL
  - 重度: < 1.0 mg/dL

### 鉀離子 (Potassium)
- 正常範圍: 3.5-5.0 mEq/L
- 低鉀血症 (Hypokalemia): < 3.5 mEq/L
- 補充規則: 每低於目標 0.1 mEq/L，補充 10 mEq

### 血糖 (Glucose/CBG)
- 空腹正常: 70-100 mg/dL
- 飯後正常: < 140 mg/dL
- 糖尿病診斷: 空腹 ≥ 126 mg/dL

### 糖化血色素 (HbA1C)
- 正常: < 5.7%
- 糖尿病前期: 5.7-6.4%
- 糖尿病: ≥ 6.5%
- 建議每年檢查一次

## 血壓分類

- 正常: < 120/80 mmHg
- 偏高: 120-129/< 80 mmHg
- 高血壓 Stage 1: 130-139/80-89 mmHg
- 高血壓 Stage 2: ≥ 140/90 mmHg

## 藥物補充劑量

### IV Magnesium Sulfate (NDC: 0338-1715-40)
| 缺乏程度 | 血清鎂值 | 劑量 | 輸注時間 |
|---------|---------|------|---------|
| 輕度 | 1.5-1.9 mg/dL | 1 g | 1 hour |
| 中度 | 1.0-<1.5 mg/dL | 2 g | 2 hours |
| 重度 | <1.0 mg/dL | 4 g | 4 hours |

### Oral Potassium (NDC: 40032-917-01)
- 目標: 3.5 mEq/L
- 補充: 每低於目標 0.1 mEq/L，給予 10 mEq
- 範例: 血鉀 3.2 mEq/L → (3.5-3.2)/0.1 × 10 = 30 mEq

## 年齡計算

計算病患年齡時:
1. 取得出生日期 (birthDate)
2. 計算到當前日期的年數
3. **無條件捨去** (向下取整)

範例:
- 出生日期: 1963-01-29
- 當前日期: 2023-11-13
- 年齡: 60 歲 (不是 61)

## 時間相關計算

### 24 小時內
- 當前時間: 2023-11-13T10:15:00
- 24 小時前: 2023-11-12T10:15:00
- FHIR 日期篩選: `date=ge2023-11-12T10:15:00`

### 一年前
- 當前時間: 2023-11-13
- 一年前: 2022-11-13
- 用於判斷 HbA1C 是否過期

## SBAR 格式 (醫療溝通)

用於轉診或會診的結構化溝通:

- **S**ituation (情況): 目前發生什麼事
- **B**ackground (背景): 相關病史和檢查
- **A**ssessment (評估): 目前的臨床判斷
- **R**ecommendation (建議): 希望對方做什麼

範例:
```
Situation: acute left knee injury
Background: radiology report indicates ACL tear
Assessment: ACL tear grade II
Recommendation: request for Orthopedic service to evaluate and provide management recommendations
```

---

## 多步驟臨床決策流程

### 流程 1: 電解質補充決策

```
Step 1: 查詢檢驗值
    └─ get_observations(patient_id, code="MG"/"K", date="ge...")
    
Step 2: 判斷是否需要補充
    └─ 比對上方閾值表
    
Step 3: 如需補充，決定劑量
    └─ 參考「藥物補充劑量」表格
    
Step 4: 開立醫囑
    └─ create_medication_order(...)
    
Step 5: 如需追蹤 (K補充)
    └─ create_service_request(...) 開隔日抽血
```

### 流程 2: A1C 檢查決策

```
Step 1: 查詢 A1C 歷史
    └─ get_observations(patient_id, code="A1C")
    
Step 2: 找最新一筆，檢查日期
    └─ 比對 effectiveDateTime 與一年前 (2022-11-13)
    
Step 3: 判斷
    ├─ 如果 < 一年前 → 需要開新檢驗
    │   └─ create_service_request(code="4548-4")
    └─ 如果 >= 一年內 → 回報該值，不用開單
```

### 流程 3: 計算平均值

```
Step 1: 查詢時間範圍內所有值
    └─ get_observations(patient_id, code="GLU", date="ge...")
    
Step 2: 從回傳的 entry[] 提取所有 valueQuantity.value
    
Step 3: 計算平均
    └─ sum(values) / len(values)
    
Step 4: 四捨五入到整數
```

---

## 常見錯誤與解決

| 錯誤 | 原因 | 解決 |
|------|------|------|
| 答案格式錯誤 | 忘記用 JSON array | 確保是 `[value]` 不是 `value` |
| 24h 查詢無結果 | date 參數格式錯誤 | 用 `ge2023-11-12T10:15:00` |
| 補充劑量錯 | 沒查閾值表 | 回來查本文件 |
| K 補充後忘記開抽血 | 只完成一半 | Task 9 需要兩個 POST |
| A1C 不該開卻開了 | 沒算對一年期限 | 2022-11-13 之後的不用開 |

---

## NDC/LOINC/SNOMED 代碼速查

| 用途 | 系統 | 代碼 |
|------|------|------|
| IV Magnesium | NDC | 0338-1715-40 |
| Oral Potassium | NDC | 40032-917-01 |
| Serum K level | LOINC | 2823-3 |
| HbA1C | LOINC | 4548-4 |
| Orthopedic referral | SNOMED | 306181000000106 |
