# MedAgent Copilot

使用 MCP (Model Context Protocol) 讓 GitHub Copilot 成為醫療 Agent，回答 MedAgentBench 的 FHIR 任務。

## 專案架構

```
medagent-copilot/
├── .med_memory/           # Copilot 記憶區塊
│   ├── task_instructions.md    # 任務執行指引
│   ├── fhir_functions.md       # FHIR API 說明
│   ├── task_examples.md        # 任務範例
│   └── clinical_knowledge.md   # 臨床知識參考
├── .vscode/
│   └── mcp.json           # MCP Server 設定
├── src/
│   └── mcp_server.py      # Python MCP Server (FHIR 工具)
└── requirements.txt
```

## 安裝

### 1. 建立 Python 虛擬環境

```bash
cd medagent-copilot
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
```

### 2. 安裝依賴

```bash
pip install -r requirements.txt
```

### 3. 啟動 FHIR 伺服器 (MedAgentBench)

```bash
# 在另一個終端機
docker run -p 8080:8080 jyxsu6/medagentbench:latest
```

### 4. 在 VS Code 中啟用 MCP

1. 開啟此專案資料夾
2. VS Code 會自動讀取 `.vscode/mcp.json`
3. 在 Copilot Chat 中使用 `@medagent-fhir` 來呼叫 FHIR 工具

## 使用方式

### 在 Copilot Chat 中

1. 開啟 Copilot Chat (Ctrl+Shift+I 或 Cmd+Shift+I)
2. 使用 Agent 模式
3. 輸入 MedAgentBench 任務問題

### 範例對話

```
User: What's the MRN of the patient with name Peter Stafford and DOB of 1932-12-29?

Copilot: 我會使用 search_patient 工具來查詢...
[呼叫 search_patient]
找到病患 MRN: S6534835

FINISH(["S6534835"])
```

## MCP 工具說明

| 工具名稱 | 說明 |
|---------|------|
| `search_patient` | 搜尋病患資訊 |
| `get_patient_by_mrn` | 根據 MRN 取得 FHIR ID |
| `get_observations` | 查詢檢驗/生命徵象 |
| `create_vital_sign` | 記錄生命徵象 |
| `create_medication_order` | 開立藥物醫囑 |
| `create_service_request` | 開立轉診/檢驗單 |
| `get_conditions` | 查詢問題清單 |
| `get_medication_requests` | 查詢藥物醫囑 |

## 記憶區塊 (.med_memory)

這個資料夾包含 Copilot 需要的背景知識：

- **task_instructions.md**: 任務類型和回應格式說明
- **fhir_functions.md**: FHIR API 詳細說明和範例
- **task_examples.md**: 完整的任務範例流程
- **clinical_knowledge.md**: 臨床參考值和計算規則

## 與 MedAgentBench 整合

要與 MedAgentBench 進行正式評測，需要：

1. 建立一個 HTTP Agent 介面
2. 透過 VS Code Extension API 呼叫 Copilot
3. 將回應轉換為 MedAgentBench 格式

詳見 `src/agent/` 目錄中的整合程式碼。

## 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `FHIR_API_BASE` | `http://localhost:8080/fhir/` | FHIR 伺服器位址 |

## License

MIT
