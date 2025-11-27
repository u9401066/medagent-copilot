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

### Memory Architecture 🧠

MedAgent uses a **layered memory system** to maintain clinical knowledge while ensuring patient privacy:

```
.med_memory/
├── CONSTITUTION.md              # 📜 Agent Rules (enforced on every tool call)
├── knowledge/                   # 📚 Shared Medical Knowledge
│   ├── clinical_knowledge.md    #    - Clinical protocols & thresholds
│   ├── fhir_functions.md        #    - FHIR API reference
│   ├── task_instructions.md     #    - Task-specific answer formats
│   └── task_examples.md         #    - Worked examples
└── patient_context/             # 🔐 Isolated Patient Memory
    └── {mrn}.json               #    - Single patient at a time (auto-cleared)
```

**Core Principles:**
| Principle | Description |
|-----------|-------------|
| **One Patient at a Time** | Only one patient context loaded simultaneously |
| **Task Isolation** | Patient memory cleared after each task |
| **Knowledge Sharing** | Clinical protocols accessible across all tasks |
| **Privacy by Design** | No cross-patient data access allowed |

**Memory-Aware Workflow:**
```
load_tasks() → get_next_task() → load_patient_context(mrn)
                                          ↓
                              [Complete task with FHIR tools]
                                          ↓
                              submit_answer() → clear_patient_context()
                                          ↓
                              get_next_task() → ... (repeat)
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

### Known Issues & Limitations ⚠️

#### 1. MCP Resources Not Accessed by VS Code Copilot
The project implements MCP Resources for clinical knowledge (`med://knowledge/*`), but **GitHub Copilot in VS Code does not automatically access MCP Resources** - it only calls MCP Tools.

**Impact:** The rich clinical knowledge in `.med_memory/knowledge/` is not utilized during benchmark execution.

**Workaround:** Knowledge hints are embedded in tool responses instead.

#### 2. Patient Memory Not Utilized
The `PatientMemory` system (`src/helpers/patient.py`) is implemented but the agent never calls `add_patient_note()` during benchmark runs.

**Impact:** Important clinical observations are not persisted between tool calls.

**Status:** Working as designed, but underutilized.

#### 3. Large FHIR Response Truncation
Some patients have hundreds of observations (e.g., 372 GLU records). FHIR API responses over ~100KB may be truncated.

**Impact:** Latest values may be missed for data-heavy patients (observed in task7_24, task7_30).

**Mitigation:** Pagination support added (`offset`/`page_size` params) but needs testing.

#### 4. POST History Recording
POST operations are recorded correctly, but the recording happens in the FHIR client layer, which may not be visible in evaluation without proper integration.

### Task Difficulty Classification 📊

We classify task difficulty based on **Agent processing steps** (not API calls). API queries are handled by the FHIR server and don't count as agent steps.

| Task | Description | Agent Steps | Difficulty |
|------|-------------|-------------|------------|
| Task 1 | Patient Search | 1 (return MRN) | Easy |
| Task 2 | Age Calculation | 2 (get patient → calc age) | Easy |
| Task 3 | Record BP | 1 (POST BP) | Easy |
| Task 4 | Query Magnesium | 2 (get labs → find latest) | Easy |
| Task 5 | Mg Replacement | 3 (get Mg → check threshold → conditional POST) | Medium |
| Task 6 | Average Glucose | 3 (get labs → filter 24h → calc average) | Medium |
| Task 7 | Latest CBG | 3 (get patient → get labs → sort & find latest) | Medium |
| Task 8 | Ortho Referral | 2 (compose SBAR → POST) | Easy |
| Task 9 | K Replacement | 4 (get K → check → POST med → POST lab recheck) | Hard |
| Task 10 | HbA1C Check | 4 (get A1C → check date/value → conditional POST → return) | Hard |

**Classification Criteria:**
- **Easy**: 1-2 agent steps
- **Medium**: 3 agent steps  
- **Hard**: 4+ agent steps

> ⚠️ Note: This classification is our own interpretation. The official MedAgentBench paper reports average steps of 2.3±1.3 but does not provide per-task difficulty labels.

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

### 記憶體架構 🧠

MedAgent 使用**分層記憶系統**，在維護臨床知識的同時確保病患隱私：

```
.med_memory/
├── CONSTITUTION.md              # 📜 Agent 憲法（每次工具呼叫時強制執行）
├── knowledge/                   # 📚 共享醫學知識
│   ├── clinical_knowledge.md    #    - 臨床協議與閾值
│   ├── fhir_functions.md        #    - FHIR API 參考
│   ├── task_instructions.md     #    - 任務特定答案格式
│   └── task_examples.md         #    - 範例解答
└── patient_context/             # 🔐 隔離的病患記憶
    └── {mrn}.json               #    - 一次只有一位病患（自動清除）
```

**核心原則：**
| 原則 | 說明 |
|------|------|
| **一次一位病患** | 同時只能載入一位病患的情境 |
| **任務隔離** | 每個任務完成後清除病患記憶 |
| **知識共享** | 臨床協議可跨任務存取 |
| **隱私優先設計** | 禁止跨病患資料存取 |

**記憶感知工作流程：**
```
load_tasks() → get_next_task() → load_patient_context(mrn)
                                          ↓
                              [使用 FHIR 工具完成任務]
                                          ↓
                              submit_answer() → clear_patient_context()
                                          ↓
                              get_next_task() → ...（重複）
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
│   │   ├── client.py         # FHIR API 客戶端 (含 POST 歷史追蹤)
│   │   └── tools.py          # FHIR MCP 工具
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

### 已知問題與限制 ⚠️

#### 1. MCP Resources 未被 VS Code Copilot 存取
本專案實作了 MCP Resources 來提供臨床知識 (`med://knowledge/*`)，但 **VS Code 中的 GitHub Copilot 不會自動存取 MCP Resources** - 它只會呼叫 MCP Tools。

**影響：** `.med_memory/knowledge/` 中豐富的臨床知識在基準測試執行時未被利用。

**暫時解法：** 將知識提示嵌入到工具回應中。

#### 2. 病患記憶未被利用
`PatientMemory` 系統 (`src/helpers/patient.py`) 已實作，但 agent 在基準測試執行期間從未呼叫 `add_patient_note()`。

**影響：** 重要的臨床觀察無法在工具呼叫之間持續保存。

**狀態：** 按設計運作，但未被充分利用。

#### 3. 大型 FHIR 回應被截斷
某些病患有數百筆觀察記錄（例如 372 筆血糖記錄）。超過約 100KB 的 FHIR API 回應可能被截斷。

**影響：** 資料量大的病患可能遺漏最新數值（在 task7_24、task7_30 中觀察到）。

**緩解措施：** 已新增分頁支援（`offset`/`page_size` 參數），但需要測試。

#### 4. POST 歷史記錄
POST 操作被正確記錄，但記錄發生在 FHIR 客戶端層，若未正確整合可能在評估時不可見。

### 任務難易度分類 📊

我們根據 **Agent 處理步驟數**（非 API 呼叫）來分類任務難易度。API 查詢由 FHIR 伺服器處理，不計入 Agent 步驟。

| 任務 | 說明 | Agent 步驟 | 難易度 |
|------|------|------------|--------|
| Task 1 | 病患搜尋 | 1 (回傳 MRN) | 簡單 |
| Task 2 | 年齡計算 | 2 (取病患 → 算年齡) | 簡單 |
| Task 3 | 記錄血壓 | 1 (POST 血壓) | 簡單 |
| Task 4 | 查詢鎂離子 | 2 (取檢驗 → 找最新值) | 簡單 |
| Task 5 | 鎂離子補充 | 3 (取 Mg → 檢查閾值 → 條件式 POST) | 中等 |
| Task 6 | 平均血糖 | 3 (取檢驗 → 過濾 24h → 計算平均) | 中等 |
| Task 7 | 最新血糖 | 3 (取病患 → 取檢驗 → 排序找最新) | 中等 |
| Task 8 | 骨科轉診 | 2 (組成 SBAR → POST) | 簡單 |
| Task 9 | 鉀離子補充 | 4 (取 K → 檢查 → POST 藥物 → POST 追蹤抽血) | 困難 |
| Task 10 | HbA1C 檢查 | 4 (取 A1C → 檢查日期/值 → 條件式 POST → 回傳) | 困難 |

**分類標準：**
- **簡單 (Easy)**：1-2 個 Agent 步驟
- **中等 (Medium)**：3 個 Agent 步驟
- **困難 (Hard)**：4 個以上 Agent 步驟

> ⚠️ 注意：此分類為本專案自行定義。官方 MedAgentBench 論文報告平均步驟數為 2.3±1.3，但未提供各任務難易度標籤。

### 相關專案

- **MedAgentBench**: https://github.com/stanfordmlgroup/MedAgentBench
- **MCP 規範**: https://modelcontextprotocol.io/

### 授權

MIT License - 詳見 [LICENSE](LICENSE)

---

## Author / 作者

- GitHub: [@u9401066](https://github.com/u9401066)
- Email: u9401066@gap.kmu.edu.tw
