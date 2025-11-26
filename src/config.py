"""
MedAgent Configuration

共用設定與路徑定義
"""

import os
import sys
from pathlib import Path

# 專案路徑
PROJECT_ROOT = Path(__file__).parent.parent
MEDAGENTBENCH_PATH = PROJECT_ROOT.parent / "MedAgentBench"

# 記憶體路徑
MED_MEMORY_PATH = PROJECT_ROOT / ".med_memory"
PATIENT_CONTEXT_PATH = MED_MEMORY_PATH / "patient_context"
KNOWLEDGE_PATH = MED_MEMORY_PATH / "knowledge"

# 結果輸出
RESULTS_PATH = PROJECT_ROOT / "results"

# FHIR API 設定
FHIR_API_BASE = os.getenv("FHIR_API_BASE", "http://localhost:8080/fhir/")

# 任務時間點 (MedAgentBench 固定時間)
TASK_DATETIME = "2023-11-13T10:15:00+00:00"

# 加入 MedAgentBench 到 path
sys.path.insert(0, str(MEDAGENTBENCH_PATH))
