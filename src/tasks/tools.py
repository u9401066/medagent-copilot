"""
Task Tools - 任務管理工具

提供給 MCP Server 註冊的任務管理工具函數
"""

import json
from datetime import datetime
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from tasks.state import task_state
from config import MEDAGENTBENCH_PATH, MED_MEMORY_PATH, RESULTS_PATH
from helpers import with_reminder, with_constitution
from helpers.patient import patient_memory
from helpers.memory_tracker import get_tracker, memory_tracker
from fhir.client import fhir_get


def _save_results_to_file():
    """即時儲存結果到執行資料夾
    
    結構：
    results/
      {version}_{timestamp}/
        agent_results.json     # Agent 提交的原始結果
    """
    if not task_state.results:
        return
    
    # 確保資料夾存在
    if task_state.run_folder is None:
        task_state.init_run_folder(RESULTS_PATH)
    
    # 寫入 agent_results.json
    output_file = task_state.run_folder / "agent_results.json"
    
    output_data = {
        "version": task_state.version,
        "run_timestamp": task_state.run_timestamp,
        "saved_at": datetime.now().isoformat(),
        "total_tasks": len(task_state.results),
        "results": task_state.results
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


def _run_evaluation():
    """執行評估並儲存到執行資料夾"""
    import sys
    from dataclasses import dataclass, field
    from typing import List
    
    if not task_state.run_folder or not task_state.results:
        return None
    
    # 添加 MedAgentBench 到路徑
    sys.path.insert(0, str(MEDAGENTBENCH_PATH))
    sys.path.insert(0, str(MEDAGENTBENCH_PATH / "src"))
    
    FHIR_BASE = "http://localhost:8080/fhir/"
    
    # 使用官方類型
    from src.typings.general import ChatHistoryItem
    from src.typings.output import TaskOutput
    
    def build_official_result(result_entry: dict) -> TaskOutput:
        return TaskOutput(
            result=result_entry["answer"],
            history=[
                ChatHistoryItem(role=h["role"], content=h["content"])
                for h in result_entry.get("post_history", [])
            ]
        )
    
    # 導入官方評估器
    from src.server.tasks.medagentbench.eval import eval as official_eval
    
    # 載入任務資料
    version = task_state.version or "v1"
    task_file = MEDAGENTBENCH_PATH / "data" / "medagentbench" / f"test_data_{version}.json"
    with open(task_file) as f:
        all_tasks = json.load(f)
    task_dict = {t["id"]: t for t in all_tasks}
    
    # 評估
    stats = {}
    details = []
    
    for r in task_state.results:
        task_id = r["task_id"]
        task_type = task_id.split("_")[0]
        
        if task_type not in stats:
            stats[task_type] = {"correct": 0, "total": 0}
        stats[task_type]["total"] += 1
        
        case_data = task_dict.get(task_id, {}).copy()
        case_data["eval_MRN"] = r.get("eval_MRN")
        case_data["id"] = task_id
        
        official_result = build_official_result(r)
        
        try:
            is_correct = official_eval(case_data, official_result, FHIR_BASE)
            if is_correct is None:
                is_correct = False
        except Exception as e:
            is_correct = False
        
        if is_correct:
            stats[task_type]["correct"] += 1
        
        details.append({
            "task_id": task_id,
            "correct": is_correct,
            "answer": r["answer"],
            "post_count": r.get("post_count", 0)
        })
    
    # 計算總體
    total_correct = sum(s["correct"] for s in stats.values())
    total_count = sum(s["total"] for s in stats.values())
    
    type_stats = {}
    for t in sorted(stats.keys()):
        s = stats[t]
        pct = s["correct"] / s["total"] * 100 if s["total"] > 0 else 0
        type_stats[t] = {
            "correct": s["correct"],
            "total": s["total"],
            "accuracy": f"{pct:.1f}%"
        }
    
    # 儲存評估結果
    eval_data = {
        "version": version,
        "run_timestamp": task_state.run_timestamp,
        "evaluated_at": datetime.now().isoformat(),
        "evaluator": "official_refsol.py",
        "overall_accuracy": f"{total_correct/total_count*100:.1f}%",
        "correct": total_correct,
        "total": total_count,
        "by_task_type": type_stats,
        "details": details
    }
    
    eval_file = task_state.run_folder / "evaluation.json"
    with open(eval_file, "w", encoding="utf-8") as f:
        json.dump(eval_data, f, indent=2, ensure_ascii=False)
    
    return eval_data


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
    async def load_tasks(
        version: str = "v1", 
        task_type: int = None,
        task_ids: list = None,
        start_index: int = None,
        end_index: int = None
    ) -> str:
        """Load MedAgentBench tasks from JSON file.
        
        Call this first to load the task file. Then use get_next_task to get tasks one by one.
        Can be called again to reset and reload tasks.
        
        Filtering options (applied in order: task_ids > task_type > range):
        - task_ids: Load specific task IDs (e.g., ["task7_10", "task7_11", "task10_5"])
        - task_type: Load all tasks of a type (1-10)
        - start_index/end_index: Load a range of tasks (0-based)
        
        Args:
            version: Test version (v1 or v2). v1 has 100 tasks, v2 has 300 tasks.
            task_type: Optional filter for specific task type (1-10).
            task_ids: Optional list of specific task IDs to load (for re-testing failed tasks).
            start_index: Optional start index (0-based, inclusive).
            end_index: Optional end index (0-based, exclusive).
        
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
            all_tasks = json.load(f)
        
        # 過濾邏輯（優先順序：task_ids > task_type > range）
        filter_suffix = None  # 用於資料夾命名
        
        if task_ids:
            # 選擇特定的 task IDs（用於重跑錯誤題目）
            task_id_set = set(task_ids)
            tasks = [t for t in all_tasks if t["id"] in task_id_set]
            # 保持原始順序
            task_order = {tid: i for i, tid in enumerate(task_ids)}
            tasks.sort(key=lambda t: task_order.get(t["id"], 999))
            filter_mode = f"specific IDs ({len(task_ids)})"
            filter_suffix = f"retest{len(task_ids)}"
        elif task_type:
            # 過濾任務類型
            tasks = [t for t in all_tasks if t["id"].startswith(f"task{task_type}_")]
            filter_mode = f"task{task_type}"
            filter_suffix = f"task{task_type}"
        elif start_index is not None or end_index is not None:
            # 範圍過濾
            start = start_index or 0
            end = end_index or len(all_tasks)
            tasks = all_tasks[start:end]
            filter_mode = f"range [{start}:{end}]"
            filter_suffix = f"r{start}-{end}"
        else:
            tasks = all_tasks
            filter_mode = "all"
        
        task_state.tasks = tasks
        
        # 初始化執行資料夾（在知道過濾模式後）
        task_state.init_run_folder(RESULTS_PATH, filter_suffix)
        
        # 初始化 memory tracker，使用 run_folder 名稱作為 run_id
        run_id = task_state.run_folder.name if task_state.run_folder else None
        get_tracker(run_id)
        
        # 統計任務類型
        task_types = {}
        for t in tasks:
            prefix = t["id"].split("_")[0]
            task_types[prefix] = task_types.get(prefix, 0) + 1
        
        # 強制返回憲法 - 這是任務開始的唯一入口
        return with_constitution({
            "status": "success",
            "version": version,
            "filter": filter_mode,
            "total_tasks": len(tasks),
            "task_types": task_types,
            "run_folder": str(task_state.run_folder),
            "memory_tracking": "enabled",
            "message": f"Loaded {len(tasks)} tasks ({version.upper()}, {filter_mode}). Call get_next_task() to start.",
            "workflow": "get_next_task → [FHIR tools] → submit_answer → repeat",
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
        
        # 設定 memory tracker 的當前任務
        memory_tracker.set_current_task(task_id)
        
        # 標記任務開始，清空 POST 歷史等待新記錄
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
        The answer will be immediately saved to the results file.
        
        ⚠️ CRITICAL FORMAT - ALL ANSWERS MUST BE JSON ARRAYS:
        
        | Task | Format | Example |
        |------|--------|---------|
        | task1 | '["MRN"]' or '["Patient not found"]' | '["S6534835"]' |
        | task2 | '[age]' as integer | '[60]' NOT '["60"]' |
        | task3 | Any (POST history matters) | '' |
        | task4 | '[mg_value]' or '[-1]' | '[2.7]' |
        | task5 | '[]' or '[mg_value]' | '[1.8]' |
        | task6 | '[avg]' KEEP DECIMALS! | '[89.88888889]' NOT '[90]' |
        | task7 | '[cbg_value]' | '[123.0]' |
        | task8 | Any (POST history matters) | '' |
        | task9 | '[]' or '[k_value]' | '[]' |
        | task10 | '[value, "datetime"]' or '[-1]' | '[5.9, "2023-11-09T03:05:00+00:00"]' |
        
        USE: import json; answer = json.dumps([value]) or json.dumps([value, datetime_str])
        
        Args:
            task_id: The task ID (e.g., "task1_1")
            answer: Your answer as JSON array string. Use json.dumps([...])
        
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
        
        # ⚠️ 自動修正答案格式
        original_answer = answer
        corrected = False
        
        # 嘗試解析答案，檢查是否為有效的 JSON 陣列
        try:
            parsed = json.loads(answer)
            if not isinstance(parsed, list):
                # 不是陣列，包成陣列
                answer = json.dumps([parsed])
                corrected = True
        except json.JSONDecodeError:
            # 解析失敗，可能是純數字或字串
            answer_stripped = answer.strip()
            
            # 嘗試解析為數字
            try:
                num = float(answer_stripped)
                # 如果是整數（task2），轉為 int
                if num == int(num) and task_id.startswith("task2"):
                    answer = json.dumps([int(num)])
                else:
                    answer = json.dumps([num])
                corrected = True
            except ValueError:
                # 不是數字，當作字串處理
                if not answer_stripped.startswith("["):
                    answer = json.dumps([answer_stripped])
                    corrected = True
        
        # 記錄答案
        task_state.add_result(task_id, answer, current_task)
        
        # 即時寫入檔案
        _save_results_to_file()
        
        remaining = task_state.remaining
        
        result = {
            "status": "recorded",
            "task_id": task_id,
            "answer": answer,
            "progress": f"{task_state.current_index}/{len(task_state.tasks)}",
            "remaining": remaining,
            "next_action": "get_next_task()" if remaining > 0 else "evaluate_results()"
        }
        
        # 如果有修正，加入提示
        if corrected:
            result["⚠️_auto_corrected"] = True
            result["original_answer"] = original_answer
            result["corrected_to"] = answer
        
        return with_reminder(result)
    
    
    @mcp.tool()
    async def save_results(filename: str = None) -> str:
        """Save all submitted answers to a JSON file.
        
        Call this after completing all tasks to save your answers.
        Results are auto-saved to the run folder, this is for explicit save.
        
        Args:
            filename: Optional custom filename (ignored, uses run folder structure)
        
        Returns:
            Path to the saved file.
        """
        if not task_state.results:
            return json.dumps({"error": "No results to save. Complete some tasks first."})
        
        # 儲存到執行資料夾
        _save_results_to_file()
        
        return json.dumps({
            "status": "success",
            "run_folder": str(task_state.run_folder),
            "agent_results": str(task_state.run_folder / "agent_results.json"),
            "total_saved": len(task_state.results),
            "next_action": "Call evaluate_results() to grade using official refsol.py"
        }, indent=2)
    
    
    @mcp.tool()
    async def evaluate_results(results_file: str = None) -> str:
        """Evaluate saved results using OFFICIAL MedAgentBench evaluator.
        
        This calls the official refsol.py evaluation functions.
        Results are saved to evaluation.json in the run folder.
        Also generates memory usage report.
        
        Args:
            results_file: Ignored, uses current run folder
        
        Returns:
            Evaluation summary with accuracy and details.
        """
        if not task_state.results:
            return json.dumps({"error": "No results to evaluate. Complete some tasks first."})
        
        # 執行評估
        eval_data = _run_evaluation()
        
        if eval_data is None:
            return json.dumps({"error": "Evaluation failed."})
        
        # 產生記憶使用報告
        total_tasks = len(task_state.tasks)
        memory_report = memory_tracker.save_full_report(total_tasks)
        memory_usage_rate = memory_report.get("usage_rate", 0) * 100
        
        # 找出錯誤
        incorrect = [d for d in eval_data["details"] if not d["correct"]]
        
        return json.dumps({
            "evaluator": "OFFICIAL MedAgentBench refsol.py",
            "version": eval_data["version"],
            "overall_accuracy": eval_data["overall_accuracy"],
            "correct": eval_data["correct"],
            "total": eval_data["total"],
            "by_task_type": eval_data["by_task_type"],
            "incorrect_count": len(incorrect),
            "incorrect_samples": incorrect[:10],
            "memory_usage": {
                "usage_rate": f"{memory_usage_rate:.1f}%",
                "tasks_with_access": len(memory_tracker.tasks_accessed),
                "total_events": len(memory_tracker.events),
                "report_file": memory_report.get("report_file")
            },
            "run_folder": str(task_state.run_folder),
            "files": {
                "agent_results": "agent_results.json",
                "evaluation": "evaluation.json",
                "memory_report": memory_report.get("report_file")
            }
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
            "run_folder": str(task_state.run_folder) if task_state.run_folder else None,
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
