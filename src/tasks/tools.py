"""
Task Tools - 任務管理工具

提供給 MCP Server 註冊的任務管理工具函數
"""

import json
from datetime import datetime
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from .state import task_state
from ..config import MEDAGENTBENCH_PATH, MED_MEMORY_PATH, RESULTS_PATH
from ..helpers import with_reminder, with_constitution
from ..helpers.patient import patient_memory
from ..fhir.client import fhir_get


def register_task_tools(mcp: FastMCP):
    """向 MCP Server 註冊所有任務管理工具
    
    Args:
        mcp: FastMCP 實例
    """
    
    # ============ Memory Tools ============
    
    @mcp.tool()
    async def get_constitution() -> str:
        """Get the MedAgent Constitution - rules for memory usage and privacy protection.
        
        Call this at the start of a session to understand the rules.
        The constitution is also reminded in every tool response.
        
        Returns:
            Full constitution text with memory architecture and privacy rules.
        """
        constitution_file = MED_MEMORY_PATH / "CONSTITUTION.md"
        if constitution_file.exists():
            with open(constitution_file) as f:
                return f.read()
        return "Constitution file not found. Check .med_memory/CONSTITUTION.md"
    
    
    @mcp.tool()
    async def load_patient_context(mrn: str, task_id: str = None) -> str:
        """Load patient context and memory for the current task.
        
        This loads any existing notes/memory for this patient.
        Use add_patient_note() to save important observations.
        
        Args:
            mrn: Patient MRN to load (e.g., S6534835)
            task_id: Optional task ID for tracking
        
        Returns:
            Patient info and any existing notes.
        """
        # 先查詢病人資訊
        data = await fhir_get("Patient", {"identifier": mrn})
        
        fhir_id = None
        if data and data.get("entry"):
            fhir_id = data["entry"][0]["resource"]["id"]
        
        # 載入病人記憶（會自動讀取歷史筆記）
        memory = patient_memory.load(mrn, fhir_id)
        
        return with_reminder({
            "status": "loaded",
            "mrn": mrn,
            "fhir_id": fhir_id,
            "task_id": task_id,
            "notes_count": memory.get("notes_count", 0),
            "notes": memory.get("notes", []),
            "hint": "Use add_patient_note() to save important observations for future reference."
        })
    
    
    @mcp.tool()
    async def add_patient_note(note: str, category: str = "general") -> str:
        """Add a note to the current patient's memory.
        
        ⚠️ Only save IMPORTANT observations, not everything from FHIR.
        Good examples: "Patient allergic to penicillin", "Chronic kidney disease stage 3"
        Bad examples: Full lab results, entire medication list
        
        Args:
            note: The note content (keep it concise)
            category: Note category (general, clinical, alert, medication, etc.)
        
        Returns:
            Confirmation with updated notes.
        """
        if not patient_memory.current_mrn:
            return with_reminder({
                "error": "No patient loaded",
                "hint": "Call load_patient_context(mrn) first, or search_patient/get_patient_by_mrn"
            })
        
        result = patient_memory.add_note(note, category)
        
        return with_reminder({
            "status": "note_added",
            "mrn": patient_memory.current_mrn,
            "note": note,
            "category": category,
            "total_notes": result.get("notes_count", 0)
        })
    
    
    @mcp.tool()
    async def get_current_patient_context() -> str:
        """Get the currently loaded patient context and notes.
        
        Returns:
            Current patient MRN, FHIR ID, and saved notes.
        """
        memory = patient_memory.get_memory()
        
        if memory.get("status") == "no_patient":
            return with_reminder({
                "status": "no_patient_loaded",
                "message": "No patient context loaded. Use search_patient or get_patient_by_mrn."
            })
        
        return with_reminder({
            "status": "active",
            **memory
        })
    
    
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
        # 重置狀態
        task_state.reset()
        task_state.version = version
        
        # 尋找任務檔案
        task_file = MEDAGENTBENCH_PATH / "data" / "medagentbench" / f"test_data_{version}.json"
        
        if not task_file.exists():
            return json.dumps({"error": f"Cannot find {task_file}"})
        
        task_state.task_file = task_file
        
        with open(task_file) as f:
            tasks = json.load(f)
        
        # 過濾任務類型
        if task_type:
            tasks = [t for t in tasks if t["id"].startswith(f"task{task_type}_")]
        
        task_state.tasks = tasks
        
        # 統計任務類型
        task_types = {}
        for t in tasks:
            prefix = t["id"].split("_")[0]
            task_types[prefix] = task_types.get(prefix, 0) + 1
        
        # 強制返回憲法 - 這是任務開始的唯一入口
        return with_constitution({
            "status": "success",
            "version": version,
            "total_tasks": len(tasks),
            "task_types": task_types,
            "message": f"Loaded {len(tasks)} tasks. Call get_next_task() to start.",
            "workflow": "get_next_task → load_patient_context → [FHIR tools] → submit_answer → clear_patient_context → repeat",
            "⚠️ IMPORTANT": "Read the _constitution field above before proceeding!"
        })
    
    
    @mcp.tool()
    async def get_next_task() -> str:
        """Get the next task to process.
        
        ⚠️ IMPORTANT: You must call submit_answer() before getting the next task!
        
        Returns the task instruction and context. After completing the task,
        use submit_answer to record your answer, then call get_next_task again.
        
        Returns:
            Next task details or completion message if all tasks are done.
        """
        if not task_state.has_tasks:
            return json.dumps({"error": "No tasks loaded. Call load_tasks first."})
        
        # 檢查是否已提交上一題答案
        if task_state.awaiting_submit:
            current = task_state.current_task
            return json.dumps({
                "error": "Must submit answer before getting next task!",
                "current_task_id": current["id"] if current else None,
                "hint": "Call submit_answer(task_id, answer) first."
            })
        
        if task_state.is_complete:
            return json.dumps({
                "status": "all_completed",
                "message": "All tasks completed!",
                "total_processed": len(task_state.results),
                "next_action": "Call save_results() to save, then evaluate_results() to grade."
            })
        
        task = task_state.current_task
        task_id = task["id"]
        
        # 標記任務開始，等待 submit
        task_state.mark_task_started()
        
        return with_reminder({
            "task_number": task_state.current_index + 1,
            "total_tasks": len(task_state.tasks),
            "task_id": task_id,
            "instruction": task["instruction"],
            "context": task.get("context", ""),
            "eval_MRN": task.get("eval_MRN", ""),
            "⚠️_WORKFLOW": "1. Use FHIR tools → 2. submit_answer(task_id, answer) → 3. get_next_task()"
        })
    
    
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
        if not task_state.has_tasks:
            return json.dumps({"error": "No tasks loaded. Call load_tasks first."})
        
        if task_state.is_complete:
            return json.dumps({"error": "No more tasks to submit."})
        
        current_task = task_state.current_task
        
        if current_task["id"] != task_id:
            return json.dumps({
                "error": f"Task ID mismatch. Expected {current_task['id']}, got {task_id}. Please check."
            })
        
        # 記錄答案
        task_state.add_result(task_id, answer, current_task)
        
        remaining = task_state.remaining
        
        return with_reminder({
            "status": "recorded",
            "task_id": task_id,
            "answer": answer,
            "progress": f"{task_state.current_index}/{len(task_state.tasks)}",
            "remaining": remaining,
            "next_action": "clear_patient_context() → get_next_task()" if remaining > 0 else "clear_patient_context() → save_results() → evaluate_results()"
        })
    
    
    @mcp.tool()
    async def save_results(filename: str = None) -> str:
        """Save all submitted answers to a JSON file.
        
        Call this after completing all tasks to save your answers.
        
        Args:
            filename: Optional custom filename. Default: results_{version}_{timestamp}.json
        
        Returns:
            Path to the saved file.
        """
        if not task_state.results:
            return json.dumps({"error": "No results to save. Complete some tasks first."})
        
        # 建立輸出目錄
        RESULTS_PATH.mkdir(exist_ok=True)
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            version = task_state.version or "unknown"
            filename = f"results_{version}_{timestamp}.json"
        
        output_file = RESULTS_PATH / filename
        
        # 整理結果格式
        output_data = {
            "version": task_state.version,
            "timestamp": datetime.now().isoformat(),
            "total_tasks": len(task_state.results),
            "results": task_state.results
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        return json.dumps({
            "status": "success",
            "file": str(output_file),
            "total_saved": len(task_state.results),
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
        if results_file:
            result_path = Path(results_file)
        else:
            # 找最新的結果檔案
            result_files = list(RESULTS_PATH.glob("results_*.json"))
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
        eval_file = RESULTS_PATH / f"eval_{result_path.stem}.json"
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
            "version": task_state.version,
            "tasks_loaded": len(task_state.tasks),
            "current_index": task_state.current_index,
            "completed": len(task_state.results),
            "remaining": task_state.remaining
        }, indent=2)
    
    
    @mcp.tool()
    async def reset_tasks() -> str:
        """Reset task state to start over.
        
        Use this if you want to restart the task processing from the beginning.
        
        Returns:
            Confirmation message.
        """
        task_state.reset()
        return json.dumps({
            "status": "reset",
            "message": "Task state cleared. Call load_tasks() to reload."
        })
