# MedAgent Copilot

[English](#english) | [繁體中文](#繁體中文)

---

## English

### Overview

**MedAgent Copilot** transforms GitHub Copilot into a medical AI agent using the Model Context Protocol (MCP). This project enables Copilot to interact with FHIR (Fast Healthcare Interoperability Resources) electronic health record systems and complete clinical tasks autonomously.

This implementation is designed to work with the **[MedAgentBench](https://github.com/stanfordmlgroup/MedAgentBench)** benchmark from Stanford ML Group, which evaluates language model agents on realistic clinical tasks.

### What is MedAgentBench?

MedAgentBench is a benchmark for evaluating LLM agents on 10 types of clinical tasks:

| Task | Description | Requires POST |
|------|-------------|---------------|
| Task 1 | Patient Search by Name + DOB | ❌ |
| Task 2 | Age Calculation from MRN | ❌ |
| Task 3 | Record Blood Pressure | ✅ |
| Task 4 | Query Magnesium Level (24h) | ❌ |
| Task 5 | Magnesium Replacement Order | ✅ (if low) |
| Task 6 | Average Blood Glucose (24h) | ❌ |
| Task 7 | Latest Blood Glucose | ❌ |
| Task 8 | Orthopedic Surgery Referral | ✅ |
| Task 9 | Potassium Replacement + Recheck | ✅ (if low) |
| Task 10 | HbA1C Check + Order if needed | ✅ (if missing/old) |

- **V1**: 100 tasks (10 per type)
- **V2**: 300 tasks (30 per type)

### How It Works

```
┌─────────────────┐     MCP Protocol      ┌─────────────────┐
│  GitHub Copilot │ ◄──────────────────► │  MedAgent MCP   │
│    (VS Code)    │                       │     Server      │
└─────────────────┘                       └────────┬────────┘
                                                   │
                                                   │ FHIR R4 API
                                                   ▼
                                          ┌─────────────────┐
                                          │  FHIR Server    │
                                          │ (Docker:8080)   │
                                          └─────────────────┘
```

### Prerequisites

- Python 3.10+
- VS Code with GitHub Copilot extension
- Docker (for FHIR server)
- Git

### Quick Start

#### 1. Clone this repository

```bash
git clone https://github.com/u9401066/medagent-copilot.git
cd medagent-copilot
```

#### 2. Install dependencies

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 3. Clone MedAgentBench (required for task data)

```bash
cd ..
git clone https://github.com/stanfordmlgroup/MedAgentBench.git
```

Final directory structure:
```
workspace/
├── medagent-copilot/    # This project
└── MedAgentBench/       # Stanford's benchmark (task data)
```

#### 4. Start FHIR Server

```bash
docker run -p 8080:8080 jyxsu6/medagentbench:latest
```

Verify: `curl http://localhost:8080/fhir/Patient?_count=1`

#### 5. Configure VS Code MCP

Create `.vscode/mcp.json` in your workspace root:

```json
{
  "servers": {
    "medagent-fhir": {
      "type": "stdio",
      "command": "python",
      "args": ["${workspaceFolder}/medagent-copilot/src/mcp_server.py"],
      "env": {
        "FHIR_API_BASE": "http://localhost:8080/fhir/"
      }
    }
  }
}
```

#### 6. Start MCP Server

1. Open VS Code
2. Press `Cmd/Ctrl + Shift + P` → Type `MCP: List Servers`
3. Confirm `medagent-fhir` shows as **Running**
4. If not running, use `MCP: Start Server` → Select `medagent-fhir`

#### 7. Run Tasks

In GitHub Copilot Chat:

```
@workspace Please load MedAgentBench V1 tasks and start executing
```

### MCP Tools Reference

#### Task Management
| Tool | Description |
|------|-------------|
| `load_tasks(version)` | Load tasks (v1: 100, v2: 300) |
| `get_next_task()` | Get next task |
| `submit_answer(task_id, answer)` | Submit answer (auto-saves) |
| `get_task_status()` | Check progress |
| `evaluate_results()` | Run official evaluation |

#### FHIR Operations
| Tool | Description |
|------|-------------|
| `search_patient` | Search patient by name/DOB |
| `get_patient_by_mrn` | Get patient by MRN |
| `get_lab_observations` | Query labs (MG, K, GLU, A1C) |
| `get_vital_signs` | Query vital signs |
| `create_vital_sign` | Record BP |
| `create_medication_order` | Order medication |
| `create_service_request` | Create referral/lab order |

### Answer Format (Critical!)

All answers must be **JSON array strings**:

| Task | Format | Example |
|------|--------|---------|
| task1 | `'["MRN"]'` | `'["S6534835"]'` |
| task2 | `'[age]'` (integer) | `'[60]'` |
| task3 | `'[]'` | `'[]'` |
| task4 | `'[mg]'` or `'[-1]'` | `'[2.7]'` |
| task5 | `'[]'` or `'[mg]'` | `'[1.8]'` |
| task6 | `'[avg]'` (keep decimals!) | `'[89.888889]'` |
| task7 | `'[cbg]'` | `'[123.0]'` |
| task8 | `'[]'` | `'[]'` |
| task9 | `'[]'` or `'[k]'` | `'[]'` |
| task10 | `'[val, "datetime"]'` or `'[-1]'` | `'[5.9, "2023-11-09T03:05:00+00:00"]'` |

### Results Structure

```
results/
├── v1_20251126_120000/
│   ├── agent_results.json    # Agent's submitted answers
│   └── evaluation.json       # Official evaluation results
└── v2_20251126_130000/
    └── ...
```

### Key Parameters

| Parameter | Value |
|-----------|-------|
| FHIR Base | `http://localhost:8080/fhir/` |
| Reference Time | `2023-11-13T10:15:00+00:00` |
| 24h Filter | `ge2023-11-12T10:15:00+00:00` |
| 1 Year Ago | `2022-11-13T10:15:00+00:00` |

### Related Projects

- **MedAgentBench**: https://github.com/stanfordmlgroup/MedAgentBench
- **MCP Specification**: https://modelcontextprotocol.io/

### License

MIT License - See [LICENSE](LICENSE)

---

## 繁體中文

### 概述

**MedAgent Copilot** 使用模型上下文協議 (MCP) 將 GitHub Copilot 轉變為醫療 AI 代理。本專案讓 Copilot 能夠與 FHIR（快速醫療互操作性資源）電子健康記錄系統互動，並自主完成臨床任務。

本實作專為 Stanford ML Group 的 **[MedAgentBench](https://github.com/stanfordmlgroup/MedAgentBench)** 基準測試而設計，該基準測試評估語言模型代理在真實臨床任務上的表現。

### 什麼是 MedAgentBench？

MedAgentBench 是用於評估 LLM 代理在 10 種臨床任務上表現的基準測試：

| 任務 | 說明 | 需要 POST |
|------|------|-----------|
| Task 1 | 依姓名+生日搜尋病患 | ❌ |
| Task 2 | 依 MRN 計算年齡 | ❌ |
| Task 3 | 記錄血壓 | ✅ |
| Task 4 | 查詢鎂離子值（24小時內） | ❌ |
| Task 5 | 鎂離子補充醫囑 | ✅（若偏低） |
| Task 6 | 平均血糖（24小時內） | ❌ |
| Task 7 | 最新血糖值 | ❌ |
| Task 8 | 骨科轉診 | ✅ |
| Task 9 | 鉀離子補充 + 追蹤抽血 | ✅（若偏低） |
| Task 10 | HbA1C 檢查 + 需要時開單 | ✅（若缺失/過期） |

- **V1**：100 個任務（每類型 10 個）
- **V2**：300 個任務（每類型 30 個）

### 運作原理

```
┌─────────────────┐     MCP 協議          ┌─────────────────┐
│  GitHub Copilot │ ◄──────────────────► │  MedAgent MCP   │
│    (VS Code)    │                       │     Server      │
└─────────────────┘                       └────────┬────────┘
                                                   │
                                                   │ FHIR R4 API
                                                   ▼
                                          ┌─────────────────┐
                                          │   FHIR 伺服器   │
                                          │ (Docker:8080)   │
                                          └─────────────────┘
```

### 前置需求

- Python 3.10+
- VS Code 搭配 GitHub Copilot 擴充功能
- Docker（用於 FHIR 伺服器）
- Git

### 快速開始

#### 1. Clone 本專案

```bash
git clone https://github.com/u9401066/medagent-copilot.git
cd medagent-copilot
```

#### 2. 安裝依賴

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 3. Clone MedAgentBench（任務資料來源）

```bash
cd ..
git clone https://github.com/stanfordmlgroup/MedAgentBench.git
```

最終目錄結構：
```
workspace/
├── medagent-copilot/    # 本專案
└── MedAgentBench/       # Stanford 基準測試（任務資料）
```

#### 4. 啟動 FHIR 伺服器

```bash
docker run -p 8080:8080 jyxsu6/medagentbench:latest
```

驗證：`curl http://localhost:8080/fhir/Patient?_count=1`

#### 5. 設定 VS Code MCP

在工作區根目錄建立 `.vscode/mcp.json`：

```json
{
  "servers": {
    "medagent-fhir": {
      "type": "stdio",
      "command": "python",
      "args": ["${workspaceFolder}/medagent-copilot/src/mcp_server.py"],
      "env": {
        "FHIR_API_BASE": "http://localhost:8080/fhir/"
      }
    }
  }
}
```

#### 6. 啟動 MCP Server

1. 開啟 VS Code
2. 按 `Cmd/Ctrl + Shift + P` → 輸入 `MCP: List Servers`
3. 確認 `medagent-fhir` 顯示為 **Running**
4. 若未執行，使用 `MCP: Start Server` → 選擇 `medagent-fhir`

#### 7. 執行任務

在 GitHub Copilot Chat 中：

```
@workspace 請載入 MedAgentBench V1 任務並開始執行
```

### MCP 工具參考

#### 任務管理
| 工具 | 說明 |
|------|------|
| `load_tasks(version)` | 載入任務 (v1: 100, v2: 300) |
| `get_next_task()` | 取得下一個任務 |
| `submit_answer(task_id, answer)` | 提交答案（自動儲存） |
| `get_task_status()` | 查看進度 |
| `evaluate_results()` | 執行官方評估 |

#### FHIR 操作
| 工具 | 說明 |
|------|------|
| `search_patient` | 依姓名/生日搜尋病患 |
| `get_patient_by_mrn` | 依 MRN 取得病患 |
| `get_lab_observations` | 查詢檢驗值 (MG, K, GLU, A1C) |
| `get_vital_signs` | 查詢生命徵象 |
| `create_vital_sign` | 記錄血壓 |
| `create_medication_order` | 開立藥物醫囑 |
| `create_service_request` | 建立轉診/檢驗單 |

### 答案格式（重要！）

所有答案必須是 **JSON 陣列字串**：

| 任務 | 格式 | 範例 |
|------|------|------|
| task1 | `'["MRN"]'` | `'["S6534835"]'` |
| task2 | `'[age]'`（整數） | `'[60]'` |
| task3 | `'[]'` | `'[]'` |
| task4 | `'[mg]'` 或 `'[-1]'` | `'[2.7]'` |
| task5 | `'[]'` 或 `'[mg]'` | `'[1.8]'` |
| task6 | `'[avg]'`（保留小數！） | `'[89.888889]'` |
| task7 | `'[cbg]'` | `'[123.0]'` |
| task8 | `'[]'` | `'[]'` |
| task9 | `'[]'` 或 `'[k]'` | `'[]'` |
| task10 | `'[val, "datetime"]'` 或 `'[-1]'` | `'[5.9, "2023-11-09T03:05:00+00:00"]'` |

### 結果結構

```
results/
├── v1_20251126_120000/
│   ├── agent_results.json    # Agent 提交的答案
│   └── evaluation.json       # 官方評估結果
└── v2_20251126_130000/
    └── ...
```

### 關鍵參數

| 參數 | 值 |
|------|-----|
| FHIR Base | `http://localhost:8080/fhir/` |
| 參考時間 | `2023-11-13T10:15:00+00:00` |
| 24 小時過濾 | `ge2023-11-12T10:15:00+00:00` |
| 1 年前 | `2022-11-13T10:15:00+00:00` |

### 專案架構

```
medagent-copilot/
├── .med_memory/              # Agent 記憶系統
│   ├── CONSTITUTION.md       # 🔒 Agent 憲法（規則與格式）
│   ├── knowledge/            # 📚 醫學知識庫
│   │   ├── clinical_knowledge.md
│   │   ├── fhir_functions.md
│   │   └── task_instructions.md
│   └── patient_context/      # 🔐 病人情境記憶（隔離區）
├── src/
│   ├── mcp_server.py         # MCP Server 入口
│   ├── config.py             # 設定檔
│   ├── fhir/                 # FHIR 工具模組
│   │   ├── client.py         # FHIR API 客戶端
│   │   ├── tools.py          # FHIR MCP 工具
│   │   └── post_history.py   # POST 歷史追蹤
│   ├── tasks/                # 任務管理模組
│   │   ├── tools.py          # 任務 MCP 工具
│   │   └── state.py          # 任務狀態追蹤
│   └── helpers/              # 輔助工具
│       ├── reminder.py       # 格式提醒系統
│       └── patient.py        # 病人記憶管理
├── docs/                     # 文件
│   └── RESULT_FORMAT.md      # 結果 JSON 格式規範
├── results/                  # 評估結果
├── evaluate_with_official.py # 官方評估腳本
└── requirements.txt
```

### 相關專案

- **MedAgentBench**: https://github.com/stanfordmlgroup/MedAgentBench
- **MCP 規範**: https://modelcontextprotocol.io/

### 授權

MIT License - 詳見 [LICENSE](LICENSE)

---

## Author / 作者

- GitHub: [@u9401066](https://github.com/u9401066)
- Email: u9401066@gap.kmu.edu.tw
