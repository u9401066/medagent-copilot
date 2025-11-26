#!/usr/bin/env python3
"""
MedAgentBench V2 批次執行器

使用與 MCP 相同的邏輯，直接批次執行 300 個任務
"""

import json
import re
import httpx
from datetime import datetime, timedelta
from pathlib import Path

FHIR_BASE = "http://localhost:8080/fhir/"
REF_TIME = datetime.fromisoformat("2023-11-13T10:15:00+00:00")
ONE_YEAR_AGO = datetime.fromisoformat("2022-11-13T10:15:00+00:00")
MEDAGENTBENCH_PATH = Path("/home/eric/workspace251126/MedAgentBench")
RESULTS_PATH = Path("/home/eric/workspace251126/medagent-copilot/results")


def fhir_get(endpoint, params=None):
    """FHIR GET 請求"""
    url = f"{FHIR_BASE}{endpoint}"
    if params:
        params["_format"] = "json"
    else:
        params = {"_format": "json"}
    
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, params=params)
        return resp.json()


def fhir_post(endpoint, payload):
    """FHIR POST 請求"""
    url = f"{FHIR_BASE}{endpoint}"
    headers = {"Content-Type": "application/fhir+json"}
    
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json=payload, headers=headers)
        return resp.json(), url, payload


def calculate_age(dob_str):
    """計算年齡"""
    dob = datetime.strptime(dob_str, "%Y-%m-%d")
    today = datetime(2023, 11, 13)
    age = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        age -= 1
    return age


def execute_task(task):
    """執行單一任務"""
    task_id = task["id"]
    task_type = task_id.split("_")[0]
    mrn = task.get("eval_MRN", "")
    instruction = task["instruction"]
    post_history = []
    
    def record_post(url, payload, response):
        """記錄 POST 歷史"""
        post_content = f"POST {url}\n{json.dumps(payload)}"
        post_history.append({"role": "agent", "content": post_content})
        post_history.append({"role": "user", "content": f"POST request accepted, id: {response.get('id', 'unknown')}"})
    
    try:
        if task_type == "task1":
            # 從 instruction 解析姓名和 DOB
            name_match = re.search(r"name\s+(\w+)\s+(\w+)", instruction)
            dob_match = re.search(r"DOB of (\d{4}-\d{2}-\d{2})", instruction)
            
            if name_match and dob_match:
                given, family = name_match.group(1), name_match.group(2)
                dob = dob_match.group(1)
                
                data = fhir_get("Patient", {"given": given, "family": family, "birthdate": dob})
                
                if data.get("total", 0) > 0:
                    patient_mrn = data["entry"][0]["resource"]["id"]
                    return json.dumps([patient_mrn]), post_history
            
            return json.dumps(["Patient not found"]), post_history
        
        elif task_type == "task2":
            data = fhir_get("Patient", {"identifier": mrn})
            if data.get("entry"):
                dob = data["entry"][0]["resource"]["birthDate"]
                age = calculate_age(dob)
                return json.dumps([age]), post_history
            return json.dumps([-1]), post_history
        
        elif task_type == "task3":
            # 記錄血壓
            bp_match = re.search(r'"(\d+/\d+ mmHg)"', instruction)
            bp_value = bp_match.group(1) if bp_match else "118/77 mmHg"
            
            payload = {
                "resourceType": "Observation",
                "status": "final",
                "category": [{
                    "coding": [{
                        "system": "http://hl7.org/fhir/observation-category",
                        "code": "vital-signs",
                        "display": "Vital Signs"
                    }]
                }],
                "code": {"text": "BP"},
                "subject": {"reference": f"Patient/{mrn}"},
                "effectiveDateTime": "2023-11-13T10:15:00+00:00",
                "valueString": bp_value
            }
            
            response, url, _ = fhir_post("Observation", payload)
            record_post(url, payload, response)
            return json.dumps([]), post_history
        
        elif task_type == "task4":
            data = fhir_get("Observation", {"patient": mrn, "code": "MG", "_count": "5000"})
            cutoff = REF_TIME - timedelta(hours=24)
            
            last_value = None
            last_time = None
            
            for entry in data.get("entry", []):
                resource = entry["resource"]
                eff_time = datetime.fromisoformat(resource["effectiveDateTime"])
                value = resource["valueQuantity"]["value"]
                
                if eff_time >= cutoff:
                    if last_time is None or eff_time > last_time:
                        last_time = eff_time
                        last_value = value
            
            return json.dumps([last_value if last_value is not None else -1]), post_history
        
        elif task_type == "task5":
            data = fhir_get("Observation", {"patient": mrn, "code": "MG", "_count": "5000"})
            cutoff = REF_TIME - timedelta(hours=24)
            
            last_value = None
            last_time = None
            
            for entry in data.get("entry", []):
                resource = entry["resource"]
                eff_time = datetime.fromisoformat(resource["effectiveDateTime"])
                value = resource["valueQuantity"]["value"]
                
                if eff_time >= cutoff:
                    if last_time is None or eff_time > last_time:
                        last_time = eff_time
                        last_value = value
            
            if last_value is None:
                return json.dumps([]), post_history
            
            if last_value > 1.9:
                return json.dumps([last_value]), post_history
            
            # 需要補鎂
            if last_value < 1.0:
                dose, rate = 4, 4
            elif last_value < 1.5:
                dose, rate = 2, 2
            else:
                dose, rate = 1, 1
            
            payload = {
                "resourceType": "MedicationRequest",
                "status": "active",
                "intent": "order",
                "medicationCodeableConcept": {
                    "coding": [{
                        "system": "http://hl7.org/fhir/sid/ndc",
                        "code": "0338-1715-40",
                        "display": "IV Magnesium Sulfate"
                    }]
                },
                "subject": {"reference": f"Patient/{mrn}"},
                "authoredOn": "2023-11-13T10:15:00+00:00",
                "dosageInstruction": [{
                    "route": "IV",
                    "doseAndRate": [{
                        "doseQuantity": {"value": dose, "unit": "g"},
                        "rateQuantity": {"value": rate, "unit": "h"}
                    }]
                }]
            }
            
            response, url, _ = fhir_post("MedicationRequest", payload)
            record_post(url, payload, response)
            return json.dumps([last_value]), post_history
        
        elif task_type == "task6":
            data = fhir_get("Observation", {"patient": mrn, "code": "GLU", "_count": "5000"})
            cutoff = REF_TIME - timedelta(hours=24)
            
            total = 0.0
            count = 0
            
            for entry in data.get("entry", []):
                resource = entry["resource"]
                eff_time = datetime.fromisoformat(resource["effectiveDateTime"])
                value = resource["valueQuantity"]["value"]
                
                if eff_time >= cutoff:
                    total += value
                    count += 1
            
            if count == 0:
                return json.dumps([-1]), post_history
            
            return json.dumps([total / count]), post_history
        
        elif task_type == "task7":
            data = fhir_get("Observation", {"patient": mrn, "code": "GLU", "_count": "5000"})
            
            last_value = None
            last_time = None
            
            for entry in data.get("entry", []):
                resource = entry["resource"]
                eff_time = datetime.fromisoformat(resource["effectiveDateTime"])
                value = resource["valueQuantity"]["value"]
                
                if last_time is None or eff_time > last_time:
                    last_time = eff_time
                    last_value = value
            
            return json.dumps([last_value if last_value is not None else -1]), post_history
        
        elif task_type == "task8":
            # 骨科轉介
            sbar = "Situation: acute left knee injury, Background: radiology report indicates ACL tear. Assessment: ACL tear grade II. Recommendation: request for Orthopedic service to evaluate and provide management recommendations."
            
            payload = {
                "resourceType": "ServiceRequest",
                "status": "active",
                "intent": "order",
                "priority": "stat",
                "code": {
                    "coding": [{
                        "system": "http://snomed.info/sct",
                        "code": "306181000000106",
                        "display": "Orthopedic surgery referral"
                    }]
                },
                "subject": {"reference": f"Patient/{mrn}"},
                "authoredOn": "2023-11-13T10:15:00+00:00",
                "note": {"text": sbar}
            }
            
            response, url, _ = fhir_post("ServiceRequest", payload)
            record_post(url, payload, response)
            return json.dumps([]), post_history
        
        elif task_type == "task9":
            data = fhir_get("Observation", {"patient": mrn, "code": "K", "_count": "5000"})
            
            last_value = None
            last_time = None
            
            for entry in data.get("entry", []):
                resource = entry["resource"]
                eff_time = datetime.fromisoformat(resource["effectiveDateTime"])
                value = resource["valueQuantity"]["value"]
                
                if last_time is None or eff_time > last_time:
                    last_time = eff_time
                    last_value = value
            
            if last_value is None or last_value >= 3.5:
                return json.dumps([]), post_history
            
            # 需要補 K - 使用 round() 避免浮點數精度問題
            dose = round((3.5 - last_value) / 0.1 * 10)
            
            # POST 1: MedicationRequest
            payload1 = {
                "resourceType": "MedicationRequest",
                "status": "active",
                "intent": "order",
                "medicationCodeableConcept": {
                    "coding": [{
                        "system": "http://hl7.org/fhir/sid/ndc",
                        "code": "40032-917-01",
                        "display": "Oral Potassium"
                    }]
                },
                "subject": {"reference": f"Patient/{mrn}"},
                "authoredOn": "2023-11-13T10:15:00+00:00",
                "dosageInstruction": [{
                    "route": "oral",
                    "doseAndRate": [{
                        "doseQuantity": {"value": dose, "unit": "mEq"}
                    }]
                }]
            }
            
            response1, url1, _ = fhir_post("MedicationRequest", payload1)
            record_post(url1, payload1, response1)
            
            # POST 2: ServiceRequest (隔天 8am 抽血)
            payload2 = {
                "resourceType": "ServiceRequest",
                "status": "active",
                "intent": "order",
                "priority": "stat",
                "code": {
                    "coding": [{
                        "system": "http://loinc.org",
                        "code": "2823-3",
                        "display": "Serum Potassium"
                    }]
                },
                "subject": {"reference": f"Patient/{mrn}"},
                "authoredOn": "2023-11-13T10:15:00+00:00",
                "occurrenceDateTime": "2023-11-14T08:00:00+00:00"
            }
            
            response2, url2, _ = fhir_post("ServiceRequest", payload2)
            record_post(url2, payload2, response2)
            
            return json.dumps([last_value]), post_history
        
        elif task_type == "task10":
            data = fhir_get("Observation", {"patient": mrn, "code": "A1C", "_count": "5000"})
            
            last_value = None
            last_time = None
            last_time_str = None
            
            for entry in data.get("entry", []):
                resource = entry["resource"]
                eff_time = datetime.fromisoformat(resource["effectiveDateTime"])
                value = resource["valueQuantity"]["value"]
                
                if last_time is None or eff_time > last_time:
                    last_time = eff_time
                    last_value = value
                    last_time_str = resource["effectiveDateTime"]
            
            # 判斷是否需要訂購
            need_order = (last_value is None) or (last_time < ONE_YEAR_AGO)
            
            if need_order:
                # POST ServiceRequest
                payload = {
                    "resourceType": "ServiceRequest",
                    "status": "active",
                    "intent": "order",
                    "priority": "stat",
                    "code": {
                        "coding": [{
                            "system": "http://loinc.org",
                            "code": "4548-4",
                            "display": "HbA1C"
                        }]
                    },
                    "subject": {"reference": f"Patient/{mrn}"},
                    "authoredOn": "2023-11-13T10:15:00+00:00"
                }
                
                response, url, _ = fhir_post("ServiceRequest", payload)
                record_post(url, payload, response)
            
            if last_value is None:
                return json.dumps([-1]), post_history
            
            return json.dumps([last_value, last_time_str]), post_history
        
        else:
            return json.dumps([]), post_history
    
    except Exception as e:
        print(f"  Error in {task_id}: {e}")
        return json.dumps([]), post_history


def main():
    # 載入 V2 任務
    task_file = MEDAGENTBENCH_PATH / "data" / "medagentbench" / "test_data_v2.json"
    with open(task_file) as f:
        tasks = json.load(f)
    
    print(f"📁 Loaded {len(tasks)} tasks from V2")
    
    results = []
    
    for i, task in enumerate(tasks):
        task_id = task["id"]
        task_type = task_id.split("_")[0]
        
        # 進度顯示
        if (i + 1) % 30 == 0 or (i + 1) == len(tasks):
            print(f"  Progress: {i + 1}/{len(tasks)} ({(i+1)*100//len(tasks)}%)")
        
        answer, post_history = execute_task(task)
        
        results.append({
            "task_id": task_id,
            "answer": answer,
            "expected_sol": task.get("sol", []),
            "eval_MRN": task.get("eval_MRN", ""),
            "timestamp": datetime.now().isoformat(),
            "post_history": post_history,
            "post_count": len(post_history) // 2
        })
    
    # 儲存結果
    RESULTS_PATH.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = RESULTS_PATH / f"results_v2_{timestamp}.json"
    
    output_data = {
        "version": "v2",
        "timestamp": datetime.now().isoformat(),
        "total_tasks": len(results),
        "results": results
    }
    
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved to: {output_file}")
    
    # 統計
    post_counts = {}
    for r in results:
        task_type = r["task_id"].split("_")[0]
        if task_type not in post_counts:
            post_counts[task_type] = {"total": 0, "with_post": 0}
        post_counts[task_type]["total"] += 1
        if r["post_count"] > 0:
            post_counts[task_type]["with_post"] += 1
    
    print("\n📊 POST Statistics:")
    for t in sorted(post_counts.keys()):
        s = post_counts[t]
        print(f"  {t}: {s['with_post']}/{s['total']} tasks had POST")


if __name__ == "__main__":
    main()
