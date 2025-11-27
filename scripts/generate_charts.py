#!/usr/bin/env python3
"""
Generate Evaluation Charts - 產生評估結果圖表

產生類似官方論文的成功率圖表，包含：
1. 按難易度分類的成功率 (easy/medium/hard)
2. 按任務類型的成功率
3. 記憶使用率報告

難易度定義（基於 Agent 處理步驟數，不含 API 查詢）：

| Task | Agent Steps | Classification |
|------|-------------|----------------|
| Task 1 | 1 (return MRN) | Easy |
| Task 2 | 2 (get patient → calc age) | Easy |
| Task 3 | 1 (POST BP) | Easy |
| Task 4 | 2 (get labs → find latest Mg) | Easy |
| Task 5 | 3 (get Mg → check threshold → conditional POST) | Medium |
| Task 6 | 3 (get labs → filter 24h → calc average) | Medium |
| Task 7 | 3 (get patient → get labs → sort by time → find latest) | Medium |
| Task 8 | 2 (compose SBAR → POST referral) | Easy |
| Task 9 | 4 (get K → check threshold → POST med → POST lab order) | Hard |
| Task 10 | 4 (get A1C → check date/value → conditional POST → return result) | Hard |

Note: API calls are handled by FHIR server, not counted as agent steps.
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # 無顯示器環境
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not installed. Charts will not be generated.")

# 難易度分類 (基於 Agent 處理步驟數)
# Easy: 1-2 steps, Medium: 3 steps, Hard: 4+ steps
DIFFICULTY_MAP = {
    "task1": "easy",    # 1 step: return MRN from search result
    "task2": "easy",    # 2 steps: get patient → calculate age
    "task3": "easy",    # 1 step: POST blood pressure
    "task4": "easy",    # 2 steps: get labs → extract latest Mg value
    "task5": "medium",  # 3 steps: get Mg → check threshold → conditional POST
    "task6": "medium",  # 3 steps: get labs → filter 24h → calculate average
    "task7": "medium",  # 3 steps: get patient → get labs → sort & find latest
    "task8": "easy",    # 2 steps: compose SBAR note → POST referral
    "task9": "hard",    # 4 steps: get K → check → POST med → POST lab recheck
    "task10": "hard",   # 4 steps: get A1C → check date/value → conditional POST → return
}

# Agent 處理步驟數
AGENT_STEPS = {
    "task1": 1,
    "task2": 2,
    "task3": 1,
    "task4": 2,
    "task5": 3,
    "task6": 3,
    "task7": 3,
    "task8": 2,
    "task9": 4,
    "task10": 4,
}

TASK_NAMES = {
    "task1": "Patient Search",
    "task2": "Age Calculation",
    "task3": "Record BP",
    "task4": "Query Magnesium",
    "task5": "Mg Replacement",
    "task6": "Avg Glucose",
    "task7": "Latest CBG",
    "task8": "Ortho Referral",
    "task9": "K Replacement",
    "task10": "HbA1C Check",
}


@dataclass
class EvalResult:
    """評估結果"""
    version: str
    run_id: str
    overall_accuracy: float
    by_task_type: Dict[str, Dict]
    by_difficulty: Dict[str, Dict]
    memory_usage_rate: float = 0.0
    total_tasks: int = 0
    correct: int = 0


def load_evaluation(eval_file: Path) -> Optional[EvalResult]:
    """載入評估結果"""
    if not eval_file.exists():
        return None
    
    with open(eval_file) as f:
        data = json.load(f)
    
    # 計算難易度分組
    by_difficulty = {"easy": {"correct": 0, "total": 0}, 
                     "medium": {"correct": 0, "total": 0},
                     "hard": {"correct": 0, "total": 0}}
    
    by_task_type = data.get("by_task_type", {})
    
    for task_type, stats in by_task_type.items():
        difficulty = DIFFICULTY_MAP.get(task_type, "medium")
        correct = stats.get("correct", 0)
        total = stats.get("total", 0)
        by_difficulty[difficulty]["correct"] += correct
        by_difficulty[difficulty]["total"] += total
    
    # 計算難易度準確率
    for diff in by_difficulty:
        total = by_difficulty[diff]["total"]
        correct = by_difficulty[diff]["correct"]
        by_difficulty[diff]["accuracy"] = (correct / total * 100) if total > 0 else 0
    
    return EvalResult(
        version=data.get("version", "unknown"),
        run_id=eval_file.parent.name,
        overall_accuracy=data.get("overall_accuracy", 0),
        by_task_type=by_task_type,
        by_difficulty=by_difficulty,
        memory_usage_rate=data.get("memory_usage_rate", 0),
        total_tasks=data.get("total", 0),
        correct=data.get("correct", 0)
    )


def load_memory_stats(run_folder: Path) -> Dict:
    """載入記憶使用統計"""
    memory_dir = run_folder.parent.parent / "memory_tracking"
    run_id = run_folder.name
    
    stats_file = memory_dir / f"{run_id}_stats.json"
    if stats_file.exists():
        with open(stats_file) as f:
            return json.load(f)
    
    return {"tasks_with_memory_access": 0, "total_tasks": 0}


def generate_difficulty_chart(
    results: List[Tuple[str, EvalResult]], 
    output_file: Path,
    title: str = "Success Rate by Difficulty Level"
):
    """產生難易度成功率圖表"""
    if not HAS_MATPLOTLIB:
        return
    
    fig, ax = plt.subplots(figsize=(10, 7))
    
    difficulties = ["overall", "easy", "medium", "hard"]
    x = range(len(difficulties))
    width = 0.25
    
    colors = ['#d0d0e0', '#4040a0', '#8080c0']  # v1, v2, v2 with memory
    
    for i, (label, result) in enumerate(results):
        values = []
        
        # Overall
        values.append(result.overall_accuracy)
        
        # By difficulty
        for diff in ["easy", "medium", "hard"]:
            values.append(result.by_difficulty.get(diff, {}).get("accuracy", 0))
        
        offset = (i - len(results)/2 + 0.5) * width
        bars = ax.bar([xi + offset for xi in x], values, width, 
                      label=label, color=colors[i % len(colors)])
        
        # 標註數值
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.annotate(f'{val:.2f}' if val > 0 else '',
                       xy=(bar.get_x() + bar.get_width()/2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)
    
    ax.set_ylabel('success rate (SR)', fontsize=12)
    ax.set_xlabel('difficulty level', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(difficulties)
    ax.set_ylim(0, 110)
    ax.legend(loc='upper left', framealpha=0.9)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Chart saved: {output_file}")


def generate_task_type_chart(
    results: List[Tuple[str, EvalResult]], 
    output_file: Path,
    title: str = "Success Rate by Task Type"
):
    """產生任務類型成功率圖表"""
    if not HAS_MATPLOTLIB:
        return
    
    fig, ax = plt.subplots(figsize=(14, 7))
    
    task_types = [f"task{i}" for i in range(1, 11)]
    x = range(len(task_types))
    width = 0.35
    
    colors = ['#4040a0', '#8080c0']
    
    for i, (label, result) in enumerate(results):
        values = []
        for tt in task_types:
            stats = result.by_task_type.get(tt, {})
            correct = stats.get("correct", 0)
            total = stats.get("total", 0)
            acc = (correct / total * 100) if total > 0 else 0
            values.append(acc)
        
        offset = (i - len(results)/2 + 0.5) * width
        bars = ax.bar([xi + offset for xi in x], values, width,
                      label=label, color=colors[i % len(colors)])
        
        # 標註數值
        for bar, val in zip(bars, values):
            if val > 0:
                ax.annotate(f'{val:.0f}%',
                           xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                           xytext=(0, 3),
                           textcoords="offset points",
                           ha='center', va='bottom', fontsize=8)
    
    ax.set_ylabel('Success Rate (%)', fontsize=12)
    ax.set_xlabel('Task Type', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    
    # 使用任務名稱
    xlabels = [f"{tt}\n{TASK_NAMES.get(tt, '')}" for tt in task_types]
    ax.set_xticklabels(xlabels, fontsize=8)
    
    ax.set_ylim(0, 110)
    ax.legend(loc='upper right', framealpha=0.9)
    ax.grid(axis='y', alpha=0.3)
    
    # 標記難易度區域
    ax.axvspan(-0.5, 1.5, alpha=0.1, color='green', label='_Easy')
    ax.axvspan(3.5, 4.5, alpha=0.1, color='green')
    ax.axvspan(6.5, 7.5, alpha=0.1, color='green')
    ax.axvspan(2.5, 3.5, alpha=0.1, color='yellow', label='_Medium')
    ax.axvspan(5.5, 6.5, alpha=0.1, color='yellow')
    ax.axvspan(7.5, 8.5, alpha=0.1, color='yellow')
    ax.axvspan(4.5, 5.5, alpha=0.1, color='red', label='_Hard')
    ax.axvspan(8.5, 10.5, alpha=0.1, color='red')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Chart saved: {output_file}")


def generate_memory_usage_chart(
    memory_stats: Dict,
    output_file: Path,
    title: str = "Memory System Usage"
):
    """產生記憶使用率圖表"""
    if not HAS_MATPLOTLIB:
        return
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # 左圖：使用率圓餅圖
    tasks_accessed = memory_stats.get("tasks_with_memory_access", 0)
    total_tasks = memory_stats.get("total_tasks", 1)
    tasks_not_accessed = total_tasks - tasks_accessed
    
    if total_tasks > 0:
        ax1.pie([tasks_accessed, tasks_not_accessed],
               labels=['With Memory Access', 'Without Memory Access'],
               autopct='%1.1f%%',
               colors=['#4040a0', '#d0d0d0'],
               startangle=90)
        ax1.set_title(f'Memory Access Rate\n({tasks_accessed}/{total_tasks} tasks)', fontsize=12)
    else:
        ax1.text(0.5, 0.5, 'No data', ha='center', va='center', fontsize=14)
        ax1.set_title('Memory Access Rate', fontsize=12)
    
    # 右圖：存取類型分布
    access_types = {
        'Patient Memory Read': memory_stats.get("patient_memory_reads", 0),
        'Patient Memory Write': memory_stats.get("patient_memory_writes", 0),
        'Knowledge Read': memory_stats.get("knowledge_reads", 0),
        'Constitution Read': memory_stats.get("constitution_reads", 0),
        'Resource Read': memory_stats.get("resource_reads", 0),
    }
    
    # 過濾掉 0 值
    access_types = {k: v for k, v in access_types.items() if v > 0}
    
    if access_types:
        ax2.barh(list(access_types.keys()), list(access_types.values()), color='#4040a0')
        ax2.set_xlabel('Count')
        ax2.set_title('Access Type Distribution', fontsize=12)
        
        # 標註數值
        for i, (k, v) in enumerate(access_types.items()):
            ax2.text(v + 0.5, i, str(v), va='center')
    else:
        ax2.text(0.5, 0.5, 'No memory access recorded', ha='center', va='center', fontsize=12)
        ax2.set_title('Access Type Distribution', fontsize=12)
    
    plt.suptitle(title, fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Chart saved: {output_file}")


def generate_report(
    eval_result: EvalResult,
    memory_stats: Dict,
    output_file: Path
):
    """產生 Markdown 報告"""
    report = f"""# MedAgentBench Evaluation Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Run ID:** {eval_result.run_id}
**Version:** {eval_result.version}

## Overall Results

| Metric | Value |
|--------|-------|
| **Overall Accuracy** | **{eval_result.overall_accuracy:.2f}%** |
| Correct | {eval_result.correct} |
| Total | {eval_result.total_tasks} |

## Results by Difficulty Level

| Difficulty | Correct | Total | Accuracy |
|------------|---------|-------|----------|
"""
    
    for diff in ["easy", "medium", "hard"]:
        stats = eval_result.by_difficulty.get(diff, {})
        correct = stats.get("correct", 0)
        total = stats.get("total", 0)
        acc = stats.get("accuracy", 0)
        report += f"| {diff.capitalize()} | {correct} | {total} | {acc:.2f}% |\n"
    
    report += """
### Difficulty Classification

| Level | Tasks |
|-------|-------|
| Easy | Task 1 (Patient Search), Task 2 (Age), Task 4 (Query Mg), Task 7 (CBG) |
| Medium | Task 3 (Record BP), Task 6 (Avg Glucose), Task 8 (Referral) |
| Hard | Task 5 (Mg Replacement), Task 9 (K Replacement), Task 10 (HbA1C Check) |

## Results by Task Type

| Task | Name | Correct | Total | Accuracy |
|------|------|---------|-------|----------|
"""
    
    for i in range(1, 11):
        tt = f"task{i}"
        name = TASK_NAMES.get(tt, "")
        stats = eval_result.by_task_type.get(tt, {})
        correct = stats.get("correct", 0)
        total = stats.get("total", 0)
        acc = (correct / total * 100) if total > 0 else 0
        report += f"| {tt} | {name} | {correct} | {total} | {acc:.2f}% |\n"
    
    # Memory Usage Section
    tasks_accessed = memory_stats.get("tasks_with_memory_access", 0)
    total_tasks = memory_stats.get("total_tasks", eval_result.total_tasks)
    usage_rate = (tasks_accessed / total_tasks * 100) if total_tasks > 0 else 0
    
    report += f"""
## Memory System Usage

| Metric | Value |
|--------|-------|
| **Memory Usage Rate** | **{usage_rate:.1f}%** |
| Tasks with Memory Access | {tasks_accessed} |
| Total Tasks | {total_tasks} |

### Access Breakdown

| Type | Count |
|------|-------|
| Patient Memory Reads | {memory_stats.get("patient_memory_reads", 0)} |
| Patient Memory Writes | {memory_stats.get("patient_memory_writes", 0)} |
| Knowledge Reads | {memory_stats.get("knowledge_reads", 0)} |
| Constitution Reads | {memory_stats.get("constitution_reads", 0)} |
| MCP Resource Reads | {memory_stats.get("resource_reads", 0)} |

"""
    
    if usage_rate == 0:
        report += """
### ⚠️ Observation

**No memory access was recorded!** The agent did not utilize the memory system during this evaluation run.

Possible reasons:
1. VS Code Copilot does not automatically access MCP Resources
2. Agent did not call `add_patient_note()` to save observations
3. Memory tracking was not properly initialized

"""
    
    with open(output_file, "w") as f:
        f.write(report)
    
    print(f"✅ Report saved: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate evaluation charts and reports")
    parser.add_argument("--run-folder", type=str, help="Path to run folder (e.g., results/v2_20251127_xxx)")
    parser.add_argument("--compare", nargs="+", help="Multiple run folders to compare")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory for charts")
    
    args = parser.parse_args()
    
    # 確定結果路徑
    base_path = Path(__file__).parent.parent
    results_path = base_path / "results"
    
    if args.compare:
        # 比較多個執行結果
        results = []
        for folder in args.compare:
            folder_path = Path(folder) if Path(folder).is_absolute() else results_path / folder
            eval_file = folder_path / "evaluation.json"
            result = load_evaluation(eval_file)
            if result:
                results.append((folder_path.name, result))
            else:
                print(f"Warning: Cannot load evaluation from {folder_path}")
        
        if not results:
            print("No valid evaluation results found.")
            return
        
        output_dir = Path(args.output_dir) if args.output_dir else results_path / "charts"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 產生比較圖表
        generate_difficulty_chart(results, output_dir / "difficulty_comparison.png")
        generate_task_type_chart(results, output_dir / "task_type_comparison.png")
        
    elif args.run_folder:
        # 單一執行結果
        folder_path = Path(args.run_folder) if Path(args.run_folder).is_absolute() else results_path / args.run_folder
        eval_file = folder_path / "evaluation.json"
        
        result = load_evaluation(eval_file)
        if not result:
            print(f"Cannot load evaluation from {eval_file}")
            return
        
        memory_stats = load_memory_stats(folder_path)
        
        output_dir = Path(args.output_dir) if args.output_dir else folder_path
        
        # 產生圖表
        generate_difficulty_chart([(result.run_id, result)], output_dir / "difficulty_chart.png")
        generate_task_type_chart([(result.run_id, result)], output_dir / "task_type_chart.png")
        generate_memory_usage_chart(memory_stats, output_dir / "memory_usage.png")
        generate_report(result, memory_stats, output_dir / "full_report.md")
        
    else:
        # 自動找最新的執行結果
        run_folders = sorted([d for d in results_path.iterdir() if d.is_dir() and d.name.startswith("v")], 
                            key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not run_folders:
            print("No run folders found in results/")
            return
        
        latest = run_folders[0]
        print(f"Using latest run folder: {latest.name}")
        
        eval_file = latest / "evaluation.json"
        result = load_evaluation(eval_file)
        
        if not result:
            print(f"Cannot load evaluation from {eval_file}")
            return
        
        memory_stats = load_memory_stats(latest)
        
        # 產生圖表
        generate_difficulty_chart([(result.run_id, result)], latest / "difficulty_chart.png")
        generate_task_type_chart([(result.run_id, result)], latest / "task_type_chart.png")
        generate_memory_usage_chart(memory_stats, latest / "memory_usage.png")
        generate_report(result, memory_stats, latest / "full_report.md")
        
        print(f"\n📊 All charts and reports generated in: {latest}")


if __name__ == "__main__":
    main()
