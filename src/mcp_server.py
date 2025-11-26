#!/usr/bin/env python3
"""
MedAgent FHIR MCP Server

使用 FastMCP 建立 FHIR API 工具給 VS Code Copilot 使用
讓 Copilot 可以作為醫療 Agent 來回答 MedAgentBench 的問題

重要時間點: 所有任務假設當前時間為 2023-11-13T10:15:00+00:00

評估機制: 使用官方 refsol.py 進行評估
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# 加入 MedAgentBench 到 path 以使用官方評估
MEDAGENTBENCH_PATH = Path(__file__).parent.parent.parent / "MedAgentBench"
sys.path.insert(0, str(MEDAGENTBENCH_PATH))

# Initialize FastMCP server
mcp = FastMCP("medagent-fhir")

# FHIR API 設定
FHIR_API_BASE = os.getenv("FHIR_API_BASE", "http://localhost:8080/fhir/")


# 任務狀態追蹤 (全域類別，支援反覆呼叫)
class TaskState:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.tasks = []
        self.current_index = 0
        self.results = []
        self.version = None
        self.task_file = None

_state = TaskState()


async def fhir_get(endpoint: str, params: dict = None) -> dict[str, Any] | None:
    """發送 FHIR GET 請求"""
    url = f"{FHIR_API_BASE.rstrip('/')}/{endpoint}"
    if params:
        query_params = "&".join(f"{k}={v}" for k, v in params.items() if v)
        if query_params:
            url = f"{url}?{query_params}"
    if "_format" not in url:
        url += ("&" if "?" in url else "?") + "_format=json"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}


async def fhir_post(endpoint: str, data: dict) -> dict[str, Any] | None:
    """發送 FHIR POST 請求"""
    url = f"{FHIR_API_BASE.rstrip('/')}/{endpoint}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url, 
                json=data, 
                headers={"Content-Type": "application/fhir+json"},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}


# ============ FHIR Query Tools ============

@mcp.tool()
async def search_patient(
    name: str = None,
    family: str = None, 
    given: str = None,
    birthdate: str = None,
    identifier: str = None
) -> str:
    """Search for patients in the FHIR server.
    
    Use this to find patient information by name, birthdate, identifier (MRN), or other demographics.
    Returns patient demographic information including FHIR ID and MRN.
    
    Args:
        name: Patient name (any part)
        family: Patient family (last) name
        given: Patient given (first) name
        birthdate: Date of birth (YYYY-MM-DD)
        identifier: Patient MRN (e.g., S6534835)
    """
    params = {}
    if name:
        params["name"] = name
    if family:
        params["family"] = family
    if given:
        params["given"] = given
    if birthdate:
        params["birthdate"] = birthdate
    if identifier:
        params["identifier"] = identifier
    
    data = await fhir_get("Patient", params)
    
    if not data or "error" in data:
        return json.dumps({"error": "Unable to search patients", "details": data})
    
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_patient_by_mrn(mrn: str) -> str:
    """Get patient FHIR ID from MRN.
    
    Use this first when you have an MRN and need to call other FHIR APIs.
    Returns the patient's FHIR ID, name, birthDate, and other demographics.
    
    Args:
        mrn: Patient MRN (e.g., S6534835)
    """
    data = await fhir_get("Patient", {"identifier": mrn})
    
    if not data or "error" in data or not data.get("entry"):
        return json.dumps({"error": "Patient not found", "mrn": mrn})
    
    patient = data["entry"][0]["resource"]
    summary = {
        "fhir_id": patient["id"],
        "mrn": mrn,
        "name": patient.get("name", []),
        "birthDate": patient.get("birthDate"),
        "gender": patient.get("gender"),
    }
    return json.dumps(summary, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_observations(
    patient_id: str,
    code: str = None,
    date: str = None,
    category: str = None
) -> str:
    """Get observations (lab results, vitals) for a patient.
    
    Use this to retrieve lab values or vital signs.
    
    Common codes:
    - MG: Magnesium
    - K: Potassium  
    - GLU: Glucose/CBG
    - A1C: HbA1C
    - BP: Blood Pressure (vital signs)
    
    Args:
        patient_id: Patient FHIR ID (not MRN). For MedAgentBench, use MRN directly as patient_id.
        code: Observation code (MG, K, GLU, A1C, etc.)
        date: Date filter (e.g., 'ge2023-11-12T10:15:00+00:00' for after this time)
        category: Category filter (e.g., 'vital-signs', 'laboratory')
    """
    params = {"patient": patient_id, "_count": "5000"}
    if code:
        params["code"] = code
    if date:
        params["date"] = date
    if category:
        params["category"] = category
    
    data = await fhir_get("Observation", params)
    
    if not data or "error" in data:
        return json.dumps({"error": "Unable to fetch observations", "details": data})
    
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_conditions(patient_id: str) -> str:
    """Get conditions (problems) from a patient's problem list.
    
    Args:
        patient_id: Patient FHIR ID
    """
    params = {
        "patient": patient_id,
        "category": "problem-list-item"
    }
    
    data = await fhir_get("Condition", params)
    
    if not data or "error" in data:
        return json.dumps({"error": "Unable to fetch conditions", "details": data})
    
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_medication_requests(
    patient_id: str,
    category: str = None
) -> str:
    """Get medication orders for a patient.
    
    Args:
        patient_id: Patient FHIR ID
        category: Category (Inpatient, Outpatient, Community, Discharge)
    """
    params = {"patient": patient_id}
    if category:
        params["category"] = category
    
    data = await fhir_get("MedicationRequest", params)
    
    if not data or "error" in data:
        return json.dumps({"error": "Unable to fetch medication requests", "details": data})
    
    return json.dumps(data, indent=2, ensure_ascii=False)


# ============ FHIR Write Tools ============

@mcp.tool()
async def create_vital_sign(
    patient_id: str,
    code: str,
    value: str,
    datetime: str
) -> str:
    """Record a vital sign observation for a patient.
    
    Use this to record blood pressure or other vital signs.
    The flowsheet ID for blood pressure is 'BP'.
    
    Args:
        patient_id: Patient FHIR ID
        code: Vital sign code (e.g., 'BP')
        value: Measurement value (e.g., '118/77 mmHg')
        datetime: DateTime in ISO format (e.g., '2023-11-12T15:30:00+00:00')
    """
    observation = {
        "resourceType": "Observation",
        "status": "final",
        "category": [{
            "coding": [{
                "system": "http://hl7.org/fhir/observation-category",
                "code": "vital-signs",
                "display": "Vital Signs"
            }]
        }],
        "code": {"text": code},
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": datetime,
        "valueString": value
    }
    
    result = await fhir_post("Observation", observation)
    
    if not result or "error" in result:
        return json.dumps({"error": "Failed to create vital sign observation", "details": result})
    
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def create_medication_order(
    patient_id: str,
    medication_code: str,
    medication_name: str,
    dose_value: float,
    dose_unit: str,
    datetime: str,
    route: str = None,
    rate_value: float = None,
    rate_unit: str = None
) -> str:
    """Create a medication order for a patient.
    
    Use this to order medications like IV magnesium or potassium replacement.
    
    Common NDC codes:
    - 0338-1715-40: IV Magnesium Sulfate
    - 40032-917-01: Oral Potassium
    
    Magnesium dosing:
    - Mild (1.5-1.9 mg/dL): 1g over 1 hour
    - Moderate (1.0-<1.5 mg/dL): 2g over 2 hours
    - Severe (<1.0 mg/dL): 4g over 4 hours
    
    Potassium dosing:
    - For every 0.1 mEq/L below 3.5, order 10 mEq
    
    Args:
        patient_id: Patient FHIR ID
        medication_code: NDC code (e.g., '0338-1715-40')
        medication_name: Medication display name
        dose_value: Dose amount
        dose_unit: Dose unit (g, mEq, etc.)
        datetime: Order datetime in ISO format
        route: Route (IV, oral, etc.) - MUST be string like "IV" or "oral"
        rate_value: Infusion rate (for IV medications)
        rate_unit: Rate unit (h for hours)
    """
    medication_request = {
        "resourceType": "MedicationRequest",
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {
            "coding": [{
                "system": "http://hl7.org/fhir/sid/ndc",
                "code": medication_code,
                "display": medication_name
            }],
            "text": medication_name
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "authoredOn": datetime,
        "dosageInstruction": [{
            "doseAndRate": [{
                "doseQuantity": {
                    "value": dose_value,
                    "unit": dose_unit
                }
            }]
        }]
    }
    
    # route 必須是字串格式，直接放入
    if route:
        medication_request["dosageInstruction"][0]["route"] = route
    
    if rate_value and rate_unit:
        medication_request["dosageInstruction"][0]["doseAndRate"][0]["rateQuantity"] = {
            "value": rate_value,
            "unit": rate_unit
        }
    
    result = await fhir_post("MedicationRequest", medication_request)
    
    if not result or "error" in result:
        return json.dumps({"error": "Failed to create medication order", "details": result})
    
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def create_service_request(
    patient_id: str,
    code_system: str,
    code: str,
    display: str,
    datetime: str,
    note: str = None,
    occurrence_datetime: str = None
) -> str:
    """Create a service request (lab order, referral) for a patient.
    
    Use this to order lab tests or create referrals.
    
    Common codes:
    - SNOMED 306181000000106: Orthopedic surgery referral
    - LOINC 2823-3: Serum potassium level
    - LOINC 4548-4: HbA1C
    
    For referrals, include SBAR note in the 'note' field.
    
    Args:
        patient_id: Patient FHIR ID
        code_system: Code system (http://snomed.info/sct or http://loinc.org)
        code: Service code
        display: Display name
        datetime: Order datetime in ISO format
        note: Free text note (SBAR for referrals) - will be wrapped in {"text": note}
        occurrence_datetime: When to perform (ISO format)
    """
    service_request = {
        "resourceType": "ServiceRequest",
        "status": "active",
        "intent": "order",
        "priority": "stat",
        "code": {
            "coding": [{
                "system": code_system,
                "code": code,
                "display": display
            }]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "authoredOn": datetime
    }
    
    if note:
        service_request["note"] = {"text": note}
    
    if occurrence_datetime:
        service_request["occurrenceDateTime"] = occurrence_datetime
    
    result = await fhir_post("ServiceRequest", service_request)
    
    if not result or "error" in result:
        return json.dumps({"error": "Failed to create service request", "details": result})
    
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_conditions(patient_id: str) -> str:
    """Get conditions (problems) from a patient's problem list.
    
    Args:
        patient_id: Patient FHIR ID
    """
    params = {
        "patient": patient_id,
        "category": "problem-list-item"
    }
    
    data = await fhir_get("Condition", params)
    
    if not data:
        return "Unable to fetch conditions. Check patient ID and FHIR connection."
    
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_medication_requests(
    patient_id: str,
    category: str = None
) -> str:
    """Get medication orders for a patient.
    
    Args:
        patient_id: Patient FHIR ID
        category: Category (Inpatient, Outpatient, Community, Discharge)
    """
    params = {"patient": patient_id}
    if category:
        params["category"] = category
    
    data = await fhir_get("MedicationRequest", params)
    
    if not data:
        return "Unable to fetch medication requests. Check patient ID and FHIR connection."
    
    return json.dumps(data, indent=2, ensure_ascii=False)


# ============ Task Management Tools ============

@mcp.tool()
async def load_tasks(version: str = "v1", task_type: int = None) -> str:
    """Load MedAgentBench tasks from JSON file.
    
    Call this first to load the task file. Then use get_next_task to get tasks one by one.
    Can be called again to reset and reload tasks.
    
    Args:
        version: Test version (v1 or v2). v1 has 100 tasks, v2 has 300 tasks.
        task_type: Optional filter for specific task type (1-10). If not specified, loads all tasks.
    
    Returns:
        Summary of loaded tasks.
    """
    # 重置狀態（支援反覆呼叫）
    _state.reset()
    _state.version = version
    
    # 尋找任務檔案
    task_file = MEDAGENTBENCH_PATH / "data" / "medagentbench" / f"test_data_{version}.json"
    
    if not task_file.exists():
        return json.dumps({"error": f"Cannot find {task_file}"})
    
    _state.task_file = task_file
    
    with open(task_file) as f:
        tasks = json.load(f)
    
    # 過濾任務類型
    if task_type:
        tasks = [t for t in tasks if t["id"].startswith(f"task{task_type}_")]
    
    _state.tasks = tasks
    
    # 統計任務類型
    task_types = {}
    for t in tasks:
        prefix = t["id"].split("_")[0]
        task_types[prefix] = task_types.get(prefix, 0) + 1
    
    return json.dumps({
        "status": "success",
        "version": version,
        "total_tasks": len(tasks),
        "task_types": task_types,
        "message": f"Loaded {len(tasks)} tasks. Call get_next_task() to start."
    }, indent=2)


@mcp.tool()
async def get_next_task() -> str:
    """Get the next task to process.
    
    Returns the task instruction and context. After completing the task,
    use submit_answer to record your answer, then call get_next_task again.
    
    Returns:
        Next task details or completion message if all tasks are done.
    """
    if not _state.tasks:
        return json.dumps({"error": "No tasks loaded. Call load_tasks first."})
    
    if _state.current_index >= len(_state.tasks):
        return json.dumps({
            "status": "all_completed",
            "message": "All tasks completed!",
            "total_processed": len(_state.results),
            "next_action": "Call save_results() to save, then evaluate_results() to grade."
        })
    
    task = _state.tasks[_state.current_index]
    
    return json.dumps({
        "task_number": _state.current_index + 1,
        "total_tasks": len(_state.tasks),
        "task_id": task["id"],
        "instruction": task["instruction"],
        "context": task.get("context", ""),
        "eval_MRN": task.get("eval_MRN", ""),
        "next_action": "Complete this task using FHIR tools, then call submit_answer()."
    }, indent=2, ensure_ascii=False)


@mcp.tool()
async def submit_answer(task_id: str, answer: str) -> str:
    """Submit your answer for the current task.
    
    After completing a task, call this to record your answer.
    The answer should be in the format expected by MedAgentBench:
    - For task1: MRN string like '["S6534835"]' or '["Patient not found"]'
    - For task2: Age as integer like '[90]'
    - For task3,5,8,9,10: Empty list '[]' if action completed
    - For task4,6,7: Numeric value like '[1.8]' or '[-1]' if not available
    
    Args:
        task_id: The task ID (e.g., "task1_1")
        answer: Your answer as a JSON array string.
                Examples: '["S6534835"]', '[90]', '[-1]', '[]'
    
    Returns:
        Confirmation and prompt to get next task.
    """
    if not _state.tasks:
        return json.dumps({"error": "No tasks loaded. Call load_tasks first."})
    
    # 驗證 task_id
    if _state.current_index >= len(_state.tasks):
        return json.dumps({"error": "No more tasks to submit."})
    
    current_task = _state.tasks[_state.current_index]
    
    if current_task["id"] != task_id:
        return json.dumps({
            "error": f"Task ID mismatch. Expected {current_task['id']}, got {task_id}. Please check."
        })
    
    # 記錄答案
    _state.results.append({
        "task_id": task_id,
        "answer": answer,
        "expected_sol": current_task.get("sol"),
        "eval_MRN": current_task.get("eval_MRN"),
        "timestamp": datetime.now().isoformat()
    })
    
    _state.current_index += 1
    
    remaining = len(_state.tasks) - _state.current_index
    
    return json.dumps({
        "status": "recorded",
        "task_id": task_id,
        "answer": answer,
        "progress": f"{_state.current_index}/{len(_state.tasks)}",
        "remaining": remaining,
        "next_action": "Call get_next_task()" if remaining > 0 else "Call save_results() then evaluate_results()"
    }, indent=2)


@mcp.tool()
async def save_results(filename: str = None) -> str:
    """Save all submitted answers to a JSON file.
    
    Call this after completing all tasks to save your answers.
    
    Args:
        filename: Optional custom filename. Default: results_{version}_{timestamp}.json
    
    Returns:
        Path to the saved file.
    """
    if not _state.results:
        return json.dumps({"error": "No results to save. Complete some tasks first."})
    
    # 建立輸出目錄
    output_dir = Path(__file__).parent.parent / "results"
    output_dir.mkdir(exist_ok=True)
    
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version = _state.version or "unknown"
        filename = f"results_{version}_{timestamp}.json"
    
    output_file = output_dir / filename
    
    # 整理結果格式
    output_data = {
        "version": _state.version,
        "timestamp": datetime.now().isoformat(),
        "total_tasks": len(_state.results),
        "results": _state.results
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    return json.dumps({
        "status": "success",
        "file": str(output_file),
        "total_saved": len(_state.results),
        "next_action": "Call evaluate_results() to grade using official refsol.py"
    }, indent=2)


@mcp.tool()
async def evaluate_results(results_file: str = None) -> str:
    """Evaluate saved results against expected answers.
    
    Compares your answers with the expected solutions from the task file.
    
    Args:
        results_file: Path to results JSON file. If not specified, uses the most recent.
    
    Returns:
        Evaluation summary with accuracy and details.
    """
    # 找到結果檔案
    results_dir = Path(__file__).parent.parent / "results"
    
    if results_file:
        result_path = Path(results_file)
    else:
        # 找最新的結果檔案
        result_files = list(results_dir.glob("results_*.json"))
        if not result_files:
            return json.dumps({"error": "No result files found. Run save_results first."})
        result_path = max(result_files, key=lambda p: p.stat().st_mtime)
    
    if not result_path.exists():
        return json.dumps({"error": f"File not found: {result_path}"})
    
    with open(result_path) as f:
        results_data = json.load(f)
    
    results_list = results_data.get("results", [])
    version = results_data.get("version", "v1")
    
    # 載入對應的任務資料
    task_file = MEDAGENTBENCH_PATH / "data" / "medagentbench" / f"test_data_{version}.json"
    if not task_file.exists():
        return json.dumps({"error": f"Task file not found: {task_file}"})
    
    with open(task_file) as f:
        all_tasks = json.load(f)
    
    task_dict = {t["id"]: t for t in all_tasks}
    
    # 評估結果
    correct_by_type = {}
    total_by_type = {}
    details = []
    
    for r in results_list:
        task_id = r["task_id"]
        answer = r["answer"]
        task_type = task_id.split("_")[0]
        
        task_data = task_dict.get(task_id, {})
        expected = task_data.get("sol", [])
        
        # 初始化統計
        if task_type not in correct_by_type:
            correct_by_type[task_type] = 0
            total_by_type[task_type] = 0
        
        total_by_type[task_type] += 1
        
        # 比對答案
        try:
            answer_parsed = json.loads(answer) if isinstance(answer, str) else answer
        except:
            answer_parsed = answer
        
        is_correct = answer_parsed == expected or [answer_parsed] == expected
        
        if is_correct:
            correct_by_type[task_type] += 1
        
        details.append({
            "task_id": task_id,
            "expected": expected,
            "actual": answer,
            "correct": is_correct
        })
    
    # 計算總體準確率
    total_correct = sum(correct_by_type.values())
    total_count = sum(total_by_type.values())
    accuracy = total_correct / total_count if total_count > 0 else 0
    
    # 按類型統計
    type_stats = {}
    for t in sorted(total_by_type.keys()):
        type_stats[t] = {
            "correct": correct_by_type[t],
            "total": total_by_type[t],
            "accuracy": f"{correct_by_type[t]/total_by_type[t]:.2%}" if total_by_type[t] > 0 else "N/A"
        }
    
    # 儲存評估結果
    eval_file = results_dir / f"eval_{result_path.stem}.json"
    eval_data = {
        "timestamp": datetime.now().isoformat(),
        "source_file": str(result_path),
        "overall_accuracy": f"{accuracy:.2%}",
        "correct": total_correct,
        "total": total_count,
        "by_task_type": type_stats,
        "details": details
    }
    
    with open(eval_file, "w") as f:
        json.dump(eval_data, f, indent=2, ensure_ascii=False)
    
    return json.dumps({
        "overall_accuracy": f"{accuracy:.2%}",
        "correct": total_correct,
        "total": total_count,
        "by_task_type": type_stats,
        "evaluation_file": str(eval_file),
        "note": "For write tasks (3,5,8,9,10), run official eval script for accurate grading."
    }, indent=2)


@mcp.tool()
async def get_task_status() -> str:
    """Get current task processing status.
    
    Shows how many tasks are loaded, completed, and remaining.
    Can be called anytime to check progress.
    
    Returns:
        Current status summary.
    """
    return json.dumps({
        "version": _state.version,
        "tasks_loaded": len(_state.tasks),
        "current_index": _state.current_index,
        "completed": len(_state.results),
        "remaining": len(_state.tasks) - _state.current_index if _state.tasks else 0
    }, indent=2)


@mcp.tool()
async def reset_tasks() -> str:
    """Reset task state to start over.
    
    Use this if you want to restart the task processing from the beginning.
    
    Returns:
        Confirmation message.
    """
    _state.reset()
    return json.dumps({
        "status": "reset",
        "message": "Task state cleared. Call load_tasks() to reload."
    })


# ============ Run Server ============

def main():
    """Run the MCP server"""
    mcp.run(transport='stdio')


if __name__ == "__main__":
    main()
