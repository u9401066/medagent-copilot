#!/usr/bin/env python3
"""
MedAgentBench Batch Runner

批次執行 MedAgentBench 任務，使用 MCP Server 的 FHIR 工具
透過 LLM (OpenAI/Claude) 來扮演 Agent 角色

使用方式:
    python batch_runner.py --model gpt-4 --version v1
    python batch_runner.py --model claude-3-opus --version v2
"""

import os
import sys
import json
import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

# 加入 src 路徑
sys.path.insert(0, str(Path(__file__).parent))

from mcp_server import (
    search_patient,
    get_patient_by_mrn,
    get_observations,
    create_vital_sign,
    create_medication_order,
    create_service_request,
    get_conditions,
    get_medication_requests,
)

# 嘗試載入 OpenAI
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# 嘗試載入 Anthropic
try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# FHIR 工具定義 (給 LLM 看的)
FHIR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_patient",
            "description": "Search for patients by name, birthdate, or MRN",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Patient name"},
                    "family": {"type": "string", "description": "Family (last) name"},
                    "given": {"type": "string", "description": "Given (first) name"},
                    "birthdate": {"type": "string", "description": "DOB (YYYY-MM-DD)"},
                    "identifier": {"type": "string", "description": "Patient MRN"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_by_mrn",
            "description": "Get patient details by MRN",
            "parameters": {
                "type": "object",
                "properties": {
                    "mrn": {"type": "string", "description": "Patient MRN"},
                },
                "required": ["mrn"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_observations",
            "description": "Get lab results or vitals. Codes: MG=Magnesium, K=Potassium, GLU=Glucose, A1C=HbA1C",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "Patient FHIR ID"},
                    "code": {"type": "string", "description": "Observation code"},
                    "date": {"type": "string", "description": "Date filter (e.g., ge2023-11-12)"},
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_vital_sign",
            "description": "Record a vital sign (e.g., BP)",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "Patient FHIR ID"},
                    "code": {"type": "string", "description": "Vital sign code"},
                    "value": {"type": "string", "description": "Value"},
                    "datetime": {"type": "string", "description": "ISO datetime"},
                },
                "required": ["patient_id", "code", "value", "datetime"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_medication_order",
            "description": "Order a medication. NDC codes: 0338-1715-40=IV Mag, 40032-917-01=Oral K",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "Patient FHIR ID"},
                    "medication_code": {"type": "string", "description": "NDC code"},
                    "medication_name": {"type": "string", "description": "Medication name"},
                    "dose_value": {"type": "number", "description": "Dose amount"},
                    "dose_unit": {"type": "string", "description": "Dose unit"},
                    "datetime": {"type": "string", "description": "ISO datetime"},
                    "route": {"type": "string", "description": "Route (IV, oral)"},
                    "rate_value": {"type": "number", "description": "Rate for IV"},
                    "rate_unit": {"type": "string", "description": "Rate unit (h)"},
                },
                "required": ["patient_id", "medication_code", "medication_name", "dose_value", "dose_unit", "datetime"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_service_request",
            "description": "Create a referral or lab order. SNOMED 306181000000106=Ortho referral",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "Patient FHIR ID"},
                    "code_system": {"type": "string", "description": "Code system URL"},
                    "code": {"type": "string", "description": "Service code"},
                    "display": {"type": "string", "description": "Display name"},
                    "datetime": {"type": "string", "description": "ISO datetime"},
                    "note": {"type": "string", "description": "Free text note"},
                    "occurrence_datetime": {"type": "string", "description": "When to perform"},
                },
                "required": ["patient_id", "code_system", "code", "display", "datetime"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_conditions",
            "description": "Get patient's problem list",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "Patient FHIR ID"},
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_medication_requests",
            "description": "Get medication orders for a patient",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "Patient FHIR ID"},
                    "category": {"type": "string", "description": "Category filter"},
                },
                "required": ["patient_id"],
            },
        },
    },
]

# 工具名稱對應函數
TOOL_FUNCTIONS = {
    "search_patient": search_patient,
    "get_patient_by_mrn": get_patient_by_mrn,
    "get_observations": get_observations,
    "create_vital_sign": create_vital_sign,
    "create_medication_order": create_medication_order,
    "create_service_request": create_service_request,
    "get_conditions": get_conditions,
    "get_medication_requests": get_medication_requests,
}


class BatchRunner:
    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.results = []
        
        if "gpt" in model.lower() or "o1" in model.lower():
            if not HAS_OPENAI:
                raise ImportError("OpenAI package not installed. Run: pip install openai")
            self.client = OpenAI()
            self.provider = "openai"
        elif "claude" in model.lower():
            if not HAS_ANTHROPIC:
                raise ImportError("Anthropic package not installed. Run: pip install anthropic")
            self.client = Anthropic()
            self.provider = "anthropic"
        else:
            raise ValueError(f"Unknown model: {model}")

    async def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """執行 FHIR 工具"""
        if tool_name not in TOOL_FUNCTIONS:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        
        func = TOOL_FUNCTIONS[tool_name]
        try:
            result = await func(**arguments)
            return result
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def run_task_openai(self, task: dict) -> dict:
        """使用 OpenAI 執行單一任務"""
        instruction = task["instruction"]
        context = task.get("context", "")
        
        system_prompt = """You are a medical agent that can interact with FHIR EHR systems.
Use the provided tools to complete the task.
When you have the final answer, respond with: FINISH(["answer"])
For example: FINISH(["S6534835"]) or FINISH(["Patient not found"])"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {instruction}\n\nContext: {context}"},
        ]

        max_iterations = 10
        for _ in range(max_iterations):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=FHIR_TOOLS,
                tool_choice="auto",
            )
            
            message = response.choices[0].message
            
            # 檢查是否有 tool calls
            if message.tool_calls:
                messages.append(message)
                
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    
                    tool_result = await self.execute_tool(tool_name, arguments)
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    })
            else:
                # 沒有 tool calls，檢查是否有最終答案
                content = message.content or ""
                if "FINISH" in content:
                    return {
                        "task_id": task["id"],
                        "response": content,
                        "success": True,
                    }
                else:
                    messages.append(message)
                    messages.append({
                        "role": "user",
                        "content": "Please provide your final answer in the format: FINISH([\"answer\"])"
                    })
        
        return {
            "task_id": task["id"],
            "response": "Max iterations reached",
            "success": False,
        }

    async def run_task(self, task: dict) -> dict:
        """執行單一任務"""
        if self.provider == "openai":
            return await self.run_task_openai(task)
        else:
            # TODO: 實作 Anthropic 版本
            return {"task_id": task["id"], "response": "Anthropic not implemented", "success": False}

    async def run_batch(self, tasks: list, output_file: str = None) -> list:
        """批次執行任務"""
        results = []
        total = len(tasks)
        
        for i, task in enumerate(tasks):
            print(f"[{i+1}/{total}] Running task: {task['id']}")
            
            try:
                result = await self.run_task(task)
                results.append(result)
                print(f"  Result: {result['response'][:100]}...")
            except Exception as e:
                print(f"  Error: {e}")
                results.append({
                    "task_id": task["id"],
                    "response": str(e),
                    "success": False,
                })
        
        # 儲存結果
        if output_file:
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\nResults saved to: {output_file}")
        
        return results


def evaluate_results(results: list, tasks: list) -> dict:
    """評估結果"""
    correct = 0
    total = len(results)
    
    task_dict = {t["id"]: t for t in tasks}
    
    details = []
    for result in results:
        task_id = result["task_id"]
        task = task_dict.get(task_id, {})
        expected = task.get("sol", [])
        
        response = result.get("response", "")
        
        # 提取 FINISH 答案
        import re
        match = re.search(r'FINISH\(\[(.*?)\]\)', response)
        if match:
            # 解析答案
            answer_str = match.group(1)
            # 簡單解析
            actual = [s.strip().strip('"\'') for s in answer_str.split(",")]
        else:
            actual = []
        
        is_correct = actual == expected
        if is_correct:
            correct += 1
        
        details.append({
            "task_id": task_id,
            "expected": expected,
            "actual": actual,
            "correct": is_correct,
        })
    
    return {
        "accuracy": correct / total if total > 0 else 0,
        "correct": correct,
        "total": total,
        "details": details,
    }


async def main():
    parser = argparse.ArgumentParser(description="MedAgentBench Batch Runner")
    parser.add_argument("--model", default="gpt-4o", help="LLM model to use")
    parser.add_argument("--version", default="v1", choices=["v1", "v2"], help="Test version")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tasks")
    parser.add_argument("--task-type", type=int, default=None, help="Only run specific task type (1-10)")
    args = parser.parse_args()
    
    # 載入測試資料
    data_path = Path(__file__).parent.parent.parent / "MedAgentBench" / "data" / "medagentbench" / f"test_data_{args.version}.json"
    
    if not data_path.exists():
        print(f"Error: Test data not found at {data_path}")
        sys.exit(1)
    
    with open(data_path) as f:
        tasks = json.load(f)
    
    # 過濾任務
    if args.task_type:
        tasks = [t for t in tasks if t["id"].startswith(f"task{args.task_type}_")]
    
    if args.limit:
        tasks = tasks[:args.limit]
    
    print(f"Loaded {len(tasks)} tasks from {args.version}")
    print(f"Using model: {args.model}")
    
    # 建立輸出目錄
    output_dir = Path(__file__).parent.parent / "results"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"results_{args.version}_{args.model}_{timestamp}.json"
    
    # 執行批次
    runner = BatchRunner(model=args.model)
    results = await runner.run_batch(tasks, str(output_file))
    
    # 評估結果
    evaluation = evaluate_results(results, tasks)
    
    print("\n" + "=" * 50)
    print("EVALUATION RESULTS")
    print("=" * 50)
    print(f"Accuracy: {evaluation['accuracy']:.2%}")
    print(f"Correct: {evaluation['correct']}/{evaluation['total']}")
    
    # 儲存評估結果
    eval_file = output_dir / f"eval_{args.version}_{args.model}_{timestamp}.json"
    with open(eval_file, "w") as f:
        json.dump(evaluation, f, indent=2, ensure_ascii=False)
    print(f"\nEvaluation saved to: {eval_file}")


if __name__ == "__main__":
    asyncio.run(main())
