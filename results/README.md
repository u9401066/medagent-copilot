# MedAgentBench Results

## 目錄結構

每次測試會自動建立以版本和時間戳命名的資料夾：

```
results/
├── v1_20251126_233000/           # V1 測試 (100 tasks)
│   ├── agent_results.json        # Agent 提交的原始答案
│   └── evaluation.json           # 官方評估結果
├── v2_20251126_234500/           # V2 測試 (300 tasks)
│   ├── agent_results.json
│   └── evaluation.json
└── README.md
```

## 檔案說明

### agent_results.json
Agent 透過 MCP `submit_answer` 提交的所有答案：
```json
{
  "version": "v1",
  "run_timestamp": "20251126_233000",
  "saved_at": "2025-11-26T23:45:00.000000",
  "total_tasks": 100,
  "results": [
    {
      "task_id": "task1_1",
      "answer": "[\"S6534835\"]",
      "expected_sol": ["S6534835"],
      "eval_MRN": "S6534835",
      "timestamp": "...",
      "post_history": [...],
      "post_count": 0
    }
  ]
}
```

### evaluation.json
使用官方 `refsol.py` 的評估結果：
```json
{
  "version": "v1",
  "run_timestamp": "20251126_233000",
  "evaluated_at": "2025-11-26T23:50:00.000000",
  "evaluator": "official_refsol.py",
  "overall_accuracy": "95.0%",
  "correct": 95,
  "total": 100,
  "by_task_type": {
    "task1": {"correct": 10, "total": 10, "accuracy": "100.0%"},
    ...
  },
  "details": [...]
}
```

## Agent 測試流程

1. `load_tasks(version="v1")` - 載入任務並建立執行資料夾
2. `get_next_task()` - 取得任務
3. 使用 FHIR 工具執行任務
4. `submit_answer(task_id, answer)` - 提交答案 (自動即時儲存)
5. 重複 2-4 直到完成
6. `evaluate_results()` - 執行官方評估
