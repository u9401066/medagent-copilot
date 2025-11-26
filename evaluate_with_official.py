#!/usr/bin/env python3
"""
使用官方 MedAgentBench 評估器

這個腳本：
1. 讀取我們的結果檔案
2. 將其轉換為官方 TaskOutput 格式
3. 直接調用官方 eval.py 進行評估
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Literal

# 添加 MedAgentBench 到路徑
MEDAGENTBENCH_PATH = Path("/home/eric/workspace251126/MedAgentBench")
sys.path.insert(0, str(MEDAGENTBENCH_PATH))
sys.path.insert(0, str(MEDAGENTBENCH_PATH / "src"))

FHIR_BASE = "http://localhost:8080/fhir/"
RESULTS_PATH = Path("/home/eric/workspace251126/medagent-copilot/results")


# ============ 模擬官方類型 ============

@dataclass
class ChatHistoryItem:
    """官方 ChatHistoryItem 格式"""
    role: str  # "user" 或 "agent"
    content: str


@dataclass
class TaskOutput:
    """官方 TaskOutput 格式"""
    result: str = None  # FINISH 中的內容
    history: List[ChatHistoryItem] = field(default_factory=list)
    status: str = "COMPLETED"
    index: int = None


def build_official_result(result_entry: dict) -> TaskOutput:
    """將我們的結果轉換為官方格式"""
    answer = result_entry["answer"]
    post_history = result_entry.get("post_history", [])
    
    # 建立 history
    history = []
    for entry in post_history:
        history.append(ChatHistoryItem(
            role=entry["role"],
            content=entry["content"]
        ))
    
    return TaskOutput(
        result=answer,
        history=history
    )


def main():
    # 導入官方評估器
    from src.server.tasks.medagentbench.eval import eval as official_eval
    
    # 載入結果檔案
    results_files = list(RESULTS_PATH.glob("results_v1_*.json"))
    if not results_files:
        print("No results file found")
        return
    
    results_file = max(results_files, key=lambda p: p.stat().st_mtime)
    print(f"📁 Evaluating: {results_file}")
    
    with open(results_file) as f:
        data = json.load(f)
    
    results_list = data["results"]
    
    # 載入任務資料
    task_file = MEDAGENTBENCH_PATH / "data" / "medagentbench" / "test_data_v1.json"
    with open(task_file) as f:
        all_tasks = json.load(f)
    task_dict = {t["id"]: t for t in all_tasks}
    
    # 評估
    stats = {}
    details = []
    
    print("\n" + "=" * 70)
    print("📊 OFFICIAL EVALUATION (using MedAgentBench eval.py)")
    print("=" * 70)
    
    for r in results_list:
        task_id = r["task_id"]
        task_type = task_id.split("_")[0]
        
        if task_type not in stats:
            stats[task_type] = {"correct": 0, "total": 0}
        stats[task_type]["total"] += 1
        
        # 建立官方格式
        case_data = task_dict.get(task_id, {}).copy()
        case_data["eval_MRN"] = r.get("eval_MRN")
        case_data["id"] = task_id
        
        official_result = build_official_result(r)
        
        # 調用官方評估
        try:
            is_correct = official_eval(case_data, official_result, FHIR_BASE)
            if is_correct is None:
                is_correct = False
        except Exception as e:
            print(f"  Error in {task_id}: {e}")
            is_correct = False
        
        if is_correct:
            stats[task_type]["correct"] += 1
        
        details.append({
            "task_id": task_id,
            "correct": is_correct,
            "answer": r["answer"],
            "post_count": r.get("post_count", 0)
        })
    
    # 輸出結果
    print()
    total_correct = 0
    total_count = 0
    
    for task_type in sorted(stats.keys()):
        s = stats[task_type]
        pct = s["correct"] / s["total"] * 100 if s["total"] > 0 else 0
        total_correct += s["correct"]
        total_count += s["total"]
        status = "✅" if pct == 100 else "⚠️" if pct >= 50 else "❌"
        print(f"{status} {task_type}: {s['correct']}/{s['total']} ({pct:.0f}%)")
    
    print("-" * 70)
    print(f"🎯 TOTAL: {total_correct}/{total_count} ({total_correct/total_count*100:.1f}%)")
    print("=" * 70)
    
    # 顯示錯誤
    incorrect = [d for d in details if not d["correct"]]
    if incorrect:
        print(f"\n🔍 INCORRECT ({len(incorrect)} items):")
        for d in incorrect[:20]:  # 只顯示前 20 個
            print(f"  {d['task_id']}: posts={d['post_count']}, answer={str(d['answer'])[:50]}")
        if len(incorrect) > 20:
            print(f"  ... and {len(incorrect) - 20} more")
    
    # 保存
    eval_output = RESULTS_PATH / f"official_eval_{results_file.stem}.json"
    with open(eval_output, "w") as f:
        json.dump({
            "evaluated_at": datetime.now().isoformat(),
            "source_file": str(results_file),
            "stats": stats,
            "total_correct": total_correct,
            "total_count": total_count,
            "accuracy": f"{total_correct/total_count*100:.1f}%",
            "details": details
        }, f, indent=2)
    print(f"\n📁 Saved to: {eval_output}")


if __name__ == "__main__":
    main()
