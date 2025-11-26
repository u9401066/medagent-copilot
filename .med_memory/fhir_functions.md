# FHIR API Functions

## API Base
```
http://localhost:8080/fhir/
```

## 1. Patient.Search
搜尋病患資訊

**GET /Patient**

參數:
- `name`: 病患姓名 (任意部分)
- `family`: 姓氏
- `given`: 名字
- `birthdate`: 出生日期 (YYYY-MM-DD)
- `identifier`: 病患識別碼 (MRN)
- `gender`: 性別
- `telecom`: 電話或 email

範例:
```
GET http://localhost:8080/fhir/Patient?name=Peter%20Stafford&birthdate=1932-12-29&_format=json
```

## 2. Observation.Search (Labs)
查詢檢驗結果

**GET /Observation**

參數:
- `patient`: 病患 FHIR ID (必填)
- `code`: 檢驗代碼 (MG, K, GLU, A1C 等)
- `date`: 日期篩選 (ge=大於等於, le=小於等於)

範例:
```
GET http://localhost:8080/fhir/Observation?patient=12345&code=MG&date=ge2023-11-12&_format=json
```

## 3. Observation.Search (Vitals)
查詢生命徵象

**GET /Observation**

參數:
- `patient`: 病患 FHIR ID (必填)
- `category`: vital-signs
- `date`: 日期篩選

## 4. Observation.Create (Vitals)
記錄生命徵象

**POST /Observation**

Payload:
```json
{
  "resourceType": "Observation",
  "status": "final",
  "category": [{
    "coding": [{
      "system": "http://hl7.org/fhir/observation-category",
      "code": "vital-signs",
      "display": "Vital Signs"
    }]
  }],
  "code": {
    "text": "BP"
  },
  "subject": {
    "reference": "Patient/{patient_id}"
  },
  "effectiveDateTime": "2023-11-13T10:15:00+00:00",
  "valueString": "118/77 mmHg"
}
```

## 5. MedicationRequest.Search
查詢藥物醫囑

**GET /MedicationRequest**

參數:
- `patient`: 病患 FHIR ID (必填)
- `category`: Inpatient, Outpatient, Community, Discharge

## 6. MedicationRequest.Create
開立藥物醫囑

**POST /MedicationRequest**

Payload:
```json
{
  "resourceType": "MedicationRequest",
  "status": "active",
  "intent": "order",
  "medicationCodeableConcept": {
    "coding": [{
      "system": "http://hl7.org/fhir/sid/ndc",
      "code": "0338-1715-40",
      "display": "Magnesium Sulfate"
    }],
    "text": "Magnesium Sulfate"
  },
  "subject": {
    "reference": "Patient/{patient_id}"
  },
  "authoredOn": "2023-11-13T10:15:00+00:00",
  "dosageInstruction": [{
    "route": {"text": "IV"},
    "doseAndRate": [{
      "doseQuantity": {"value": 2, "unit": "g"},
      "rateQuantity": {"value": 2, "unit": "h"}
    }]
  }]
}
```

## 7. ServiceRequest.Create
開立服務請求 (轉診/檢驗)

**POST /ServiceRequest**

Payload:
```json
{
  "resourceType": "ServiceRequest",
  "status": "active",
  "intent": "order",
  "priority": "stat",
  "code": {
    "coding": [{
      "system": "http://snomed.info/sct",
      "code": "306181000000106",
      "display": "Referral to orthopedic surgery service"
    }]
  },
  "subject": {
    "reference": "Patient/{patient_id}"
  },
  "authoredOn": "2023-11-13T10:15:00+00:00",
  "note": [{"text": "SBAR note here"}],
  "occurrenceDateTime": "2023-11-14T08:00:00+00:00"
}
```

## 8. Condition.Search
查詢問題清單

**GET /Condition**

參數:
- `patient`: 病患 FHIR ID (必填)
- `category`: problem-list-item

## 常用代碼

### 檢驗代碼 (Observation codes)
- `MG`: 鎂離子 (Magnesium)
- `K`: 鉀離子 (Potassium)
- `GLU`: 血糖 (Glucose/CBG)
- `A1C`: 糖化血色素 (HbA1C)
- `BP`: 血壓 (Blood Pressure)

### NDC 藥物代碼
- `0338-1715-40`: IV Magnesium Sulfate
- `40032-917-01`: Oral Potassium

### LOINC 檢驗代碼
- `2823-3`: Serum Potassium
- `4548-4`: HbA1C

### SNOMED 代碼
- `306181000000106`: Orthopedic surgery referral
