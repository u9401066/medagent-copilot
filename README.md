# MedAgent Copilot

使用 MCP (Model Context Protocol) 讓 GitHub Copilot 成為醫療 Agent，執行 MedAgentBench FHIR 任務。

## 📋 前置需求

- Python 3.10+
- VS Code + GitHub Copilot 擴充功能
- Docker (用於 FHIR 伺服器)
- MedAgentBench 資料集 (需另外 clone)

## 🚀 快速開始

### 1. Clone 專案

```bash
git clone https://github.com/u9401066/medagent-copilot.git
cd medagent-copilot
```

### 2. 安裝依賴

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Clone MedAgentBench (放在同層目錄)

```bash
cd ..
git clone https://github.com/stanfordmlgroup/MedAgentBench.git
```

最終目錄結構：
```
workspace/
├── medagent-copilot/    # 本專案
└── MedAgentBench/       # 官方資料集
```

### 4. 啟動 FHIR 伺服器

```bash
docker run -p 8080:8080 jyxsu6/medagentbench:latest
```

驗證：`curl http://localhost:8080/fhir/Patient?_count=1`

### 5. 設定 VS Code MCP

在專案根目錄建立 `.vscode/mcp.json`：

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

或者如果 medagent-copilot 是根目錄：

```json
{
  "servers": {
    "medagent-fhir": {
      "type": "stdio",
      "command": "python",
      "args": ["${workspaceFolder}/src/mcp_server.py"],
      "env": {
        "FHIR_API_BASE": "http://localhost:8080/fhir/"
      }
    }
  }
}
```

### 6. 啟動 MCP Server

1. 開啟 VS Code
2. 按 `Cmd/Ctrl + Shift + P` → 輸入 `MCP: List Servers`
3. 確認 `medagent-fhir` 顯示為 Running
4. 如果沒有，按 `MCP: Start Server` → 選擇 `medagent-fhir`

### 7. 開始使用

在 GitHub Copilot Chat 中：

```
@workspace 請載入 MedAgentBench V1 任務並開始執行
```

## 🏗️ 專案架構

```
medagent-copilot/
├── .med_memory/              # Copilot 記憶系統
│   ├── CONSTITUTION.md       # 🔒 Agent 憲法（規則與格式）
│   ├── knowledge/            # 📚 醫學知識庫
│   │   ├── clinical_protocols.md
│   │   ├── fhir_reference.md
│   │   └── task_instructions.md
│   └── patient_context/      # 🔐 病人情境記憶（隔離區）
├── src/
│   ├── mcp_server.py         # MCP Server 入口
│   ├── config.py             # 設定檔
│   ├── fhir/                 # FHIR 工具
│   │   ├── client.py         # FHIR API 客戶端
│   │   ├── tools.py          # FHIR MCP 工具
│   │   └── post_history.py   # POST 歷史追蹤
│   ├── tasks/                # 任務管理
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

## 📋 MCP 工具一覽

### 任務管理工具
| 工具 | 說明 |
|------|------|
| `load_tasks` | 載入 MedAgentBench 任務 (v1/v2) |
| `get_next_task` | 取得下一個任務 |
| `submit_answer` | 提交答案（自動保存） |
| `get_task_status` | 查看進度 |
| `evaluate_results` | 評估結果 |

### FHIR 工具
| 工具 | 說明 |
|------|------|
| `search_patient` | 搜尋病患 |
| `get_patient_by_mrn` | 用 MRN 查 FHIR ID |
| `get_lab_observations` | 查檢驗值 (MG, K, GLU, A1C...) |
| `get_vital_signs` | 查生命徵象 |
| `create_vital_sign` | 記錄 BP |
| `create_medication_order` | 開藥 |
| `create_service_request` | 轉診/抽血單 |

### 記憶工具
| 工具 | 說明 |
|------|------|
| `get_constitution` | 取得 Agent 憲法 |
| `load_patient_context` | 載入病人記憶 |
| `add_patient_note` | 新增病人筆記 |

## 📊 答案格式（重要！）

所有答案必須是 **JSON 陣列**：

| 任務 | 格式 | 範例 |
|------|------|------|
| task1 | `["MRN"]` | `["S6534835"]` |
| task2 | `[age]` | `[60]` |
| task3 | POST 歷史 | - |
| task4 | `[mg]` 或 `[-1]` | `[2.7]` |
| task5 | `[]` 或 `[mg]` | `[1.8]` |
| task6 | `[avg]` 保留小數 | `[89.888889]` |
| task7 | `[cbg]` | `[123.0]` |
| task8 | POST 歷史 | - |
| task9 | `[]` 或 `[k]` | `[]` |
| task10 | `[val, "datetime"]` | `[5.9, "2023-11-09T03:05:00+00:00"]` |

## 🔄 任務流程

```
load_tasks(version="v1")
    ↓
get_next_task()
    ↓
[使用 FHIR 工具完成任務]
    ↓
submit_answer(task_id, json.dumps([answer]))
    ↓
(重複直到完成)
    ↓
evaluate_results()
```

## 📈 評估

使用官方 MedAgentBench 評估器：

```bash
python evaluate_with_official.py
```

## 🧠 記憶系統

### CONSTITUTION.md (憲法)
- 定義 Agent 行為規則
- 隱私保護原則
- 答案格式規範
- 臨床閾值參考

### knowledge/ (知識庫)
- 通用醫學知識
- 可跨病人使用

### patient_context/ (病人記憶)
- ⚠️ 嚴格隔離
- 一次只能載入一位病人
- 任務結束後清除

## 📝 關鍵參數

| 參數 | 值 |
|------|-----|
| FHIR Base | `http://localhost:8080/fhir/` |
| 參考時間 | `2023-11-13T10:15:00+00:00` |
| 24h 過濾 | `ge2023-11-12T10:15:00+00:00` |
| 1 年前 | `2022-11-13T10:15:00+00:00` |

## License

MIT
