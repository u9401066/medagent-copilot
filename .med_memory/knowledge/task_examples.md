# Task Examples

## Task 1: 病患搜尋範例

**問題**: What's the MRN of the patient with name Peter Stafford and DOB of 1932-12-29?

**步驟 1**: 搜尋病患
```
GET http://localhost:8080/fhir/Patient?name=Peter%20Stafford&birthdate=1932-12-29&_format=json
```

**回應處理**: 從回應中提取 identifier，找到 MRN

**最終答案**:
```
FINISH(["S6534835"])
```

---

## Task 2: 年齡計算範例

**問題**: What's the age of the patient with MRN of S2874099?
**Context**: It's 2023-11-13T10:15:00+00:00 now

**步驟 1**: 查詢病患資料
```
GET http://localhost:8080/fhir/Patient?identifier=S2874099&_format=json
```

**計算**: 從 birthDate 計算到 2023-11-13 的年齡，無條件捨去

**最終答案**:
```
FINISH([60])
```

---

## Task 3: 記錄血壓範例

**問題**: I just measured the blood pressure for patient with MRN of S2380121, and it is "118/77 mmHg". Help me record it.
**Context**: It's 2023-11-13T10:15:00+00:00 now. The flowsheet ID for blood pressure is BP.

**步驟 1**: 先查詢病患 FHIR ID
```
GET http://localhost:8080/fhir/Patient?identifier=S2380121&_format=json
```

**步驟 2**: 記錄血壓 (假設 FHIR ID 是 12345)
```
POST http://localhost:8080/fhir/Observation
{
  "resourceType": "Observation",
  "status": "final",
  "category": [{"coding": [{"system": "http://hl7.org/fhir/observation-category", "code": "vital-signs", "display": "Vital Signs"}]}],
  "code": {"text": "BP"},
  "subject": {"reference": "Patient/12345"},
  "effectiveDateTime": "2023-11-13T10:15:00+00:00",
  "valueString": "118/77 mmHg"
}
```

**最終答案**:
```
FINISH(["Blood pressure recorded successfully"])
```

---

## Task 4: 查詢鎂離子範例

**問題**: What's the most recent magnesium level of the patient S3032536 within last 24 hours?
**Context**: It's 2023-11-13T10:15:00+00:00 now. The code for magnesium is "MG".

**步驟 1**: 查詢病患 FHIR ID
```
GET http://localhost:8080/fhir/Patient?identifier=S3032536&_format=json
```

**步驟 2**: 查詢鎂離子值 (假設 FHIR ID 是 12345)
```
GET http://localhost:8080/fhir/Observation?patient=12345&code=MG&date=ge2023-11-12T10:15:00&_format=json
```

**處理**: 找到最新的數值，轉換為 mg/dL

**最終答案**:
```
FINISH([1.8])
```

或如果沒有資料:
```
FINISH([-1])
```

---

## Task 5: 鎂離子補充範例

**問題**: Check patient S6315806's last serum magnesium level within last 24 hours. If low, then order replacement IV magnesium according to dosing instructions.

**劑量規則**:
- 輕度 (1.5-1.9 mg/dL): 1g over 1 hour
- 中度 (1.0-<1.5 mg/dL): 2g over 2 hours  
- 重度 (<1.0 mg/dL): 4g over 4 hours

**步驟 1**: 查詢病患和鎂離子值

**步驟 2**: 如果低於 2.0 mg/dL，開立藥物
```
POST http://localhost:8080/fhir/MedicationRequest
{
  "resourceType": "MedicationRequest",
  "status": "active",
  "intent": "order",
  "medicationCodeableConcept": {
    "coding": [{"system": "http://hl7.org/fhir/sid/ndc", "code": "0338-1715-40", "display": "Magnesium Sulfate IV"}],
    "text": "Magnesium Sulfate IV"
  },
  "subject": {"reference": "Patient/12345"},
  "authoredOn": "2023-11-13T10:15:00+00:00",
  "dosageInstruction": [{
    "route": {"text": "IV"},
    "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "g"}, "rateQuantity": {"value": 2, "unit": "h"}}]
  }]
}
```

---

## Task 8: 骨科轉診範例

**問題**: Order orthopedic surgery referral for patient S2016972. Specify within the free text of the referral, "Situation: acute left knee injury..."

```
POST http://localhost:8080/fhir/ServiceRequest
{
  "resourceType": "ServiceRequest",
  "status": "active",
  "intent": "order",
  "priority": "stat",
  "code": {
    "coding": [{"system": "http://snomed.info/sct", "code": "306181000000106", "display": "Referral to orthopedic surgery service"}]
  },
  "subject": {"reference": "Patient/12345"},
  "authoredOn": "2023-11-13T10:15:00+00:00",
  "note": [{"text": "Situation: acute left knee injury, Background: radiology report indicates ACL tear. Assessment: ACL tear grade II. Recommendation: request for Orthopedic service to evaluate and provide management recommendations."}]
}
```

---

## 重要提醒

1. 先用 MRN 查詢病患 FHIR ID
2. 所有後續 API 使用 FHIR ID (不是 MRN)
3. 日期格式: ISO 8601 (例: 2023-11-13T10:15:00+00:00)
4. 永遠加上 `&_format=json` 到 GET 請求
