"""
Knowledge Resources - 醫學知識與憲法暴露

透過 MCP Resource 讓 LLM 可以主動讀取知識庫
"""

from pathlib import Path
from mcp.server.fastmcp import FastMCP
from config import MED_MEMORY_PATH


def register_resources(mcp: FastMCP):
    """向 MCP Server 註冊所有資源
    
    Resources 是靜態內容，LLM 可以主動讀取
    相比 Tools 需要 invoke，Resources 更適合提供 context
    """
    
    # ============ Constitution ============
    
    @mcp.resource("med://constitution")
    def get_constitution() -> str:
        """MedAgent 憲法 - 核心原則與隱私保護規則
        
        這是最重要的資源，包含：
        1. 單病患隔離原則
        2. 記憶層架構說明
        3. 回答格式要求
        """
        constitution_file = MED_MEMORY_PATH / "CONSTITUTION.md"
        if constitution_file.exists():
            return constitution_file.read_text(encoding="utf-8")
        return "# Constitution not found\nCheck .med_memory/CONSTITUTION.md"
    
    
    # ============ Clinical Knowledge ============
    
    @mcp.resource("med://knowledge/clinical")
    def get_clinical_knowledge() -> str:
        """臨床知識參考 - 正常值、劑量規則、計算方法
        
        包含：
        - 電解質正常範圍 (Mg, K, Glucose, A1C)
        - 藥物補充劑量規則
        - 年齡計算方法
        - SBAR 格式
        """
        knowledge_file = MED_MEMORY_PATH / "knowledge" / "clinical_knowledge.md"
        if knowledge_file.exists():
            return knowledge_file.read_text(encoding="utf-8")
        return "# Clinical knowledge not found"
    
    
    @mcp.resource("med://knowledge/tasks")
    def get_task_instructions() -> str:
        """任務類型說明 - 10 種任務的詳細指引
        
        包含：
        - Task 1-10 的目標和步驟
        - 常用 API 路徑
        - 答案格式範例
        """
        task_file = MED_MEMORY_PATH / "knowledge" / "task_instructions.md"
        if task_file.exists():
            return task_file.read_text(encoding="utf-8")
        return "# Task instructions not found"
    
    
    @mcp.resource("med://knowledge/fhir")
    def get_fhir_guide() -> str:
        """FHIR API 使用指南
        
        包含：
        - 常用 Resource 類型
        - Query 參數說明
        - POST payload 格式
        """
        fhir_file = MED_MEMORY_PATH / "knowledge" / "fhir_functions.md"
        if fhir_file.exists():
            return fhir_file.read_text(encoding="utf-8")
        return "# FHIR guide not found"
    
    
    @mcp.resource("med://knowledge/examples")
    def get_task_examples() -> str:
        """成功案例參考
        
        包含過去成功完成的任務範例，
        可用於 few-shot learning
        """
        examples_file = MED_MEMORY_PATH / "knowledge" / "task_examples.md"
        if examples_file.exists():
            return examples_file.read_text(encoding="utf-8")
        return "# No examples available yet"
    
    
    # ============ Patient Context (Dynamic) ============
    
    @mcp.resource("med://patient/current")
    def get_current_patient() -> str:
        """當前病患情境
        
        ⚠️ 這是動態資源，內容會隨著 load_patient_context 改變
        包含當前病患的 MRN, FHIR ID 和相關資訊
        """
        patient_file = MED_MEMORY_PATH / "patient_context" / "current_patient.json"
        if patient_file.exists():
            return patient_file.read_text(encoding="utf-8")
        return '{"status": "no_patient_loaded", "message": "Call load_patient_context first"}'
    
    
    # ============ Resource Templates (Parameterized) ============
    
    @mcp.resource("med://knowledge/{topic}")
    def get_knowledge_by_topic(topic: str) -> str:
        """根據主題取得知識
        
        可用主題: clinical, tasks, fhir, examples
        """
        knowledge_dir = MED_MEMORY_PATH / "knowledge"
        
        # 主題對應檔案
        topic_files = {
            "clinical": "clinical_knowledge.md",
            "tasks": "task_instructions.md",
            "fhir": "fhir_functions.md",
            "examples": "task_examples.md"
        }
        
        if topic in topic_files:
            file_path = knowledge_dir / topic_files[topic]
            if file_path.exists():
                return file_path.read_text(encoding="utf-8")
        
        # 嘗試直接找檔案
        for ext in [".md", ".json", ".txt"]:
            file_path = knowledge_dir / f"{topic}{ext}"
            if file_path.exists():
                return file_path.read_text(encoding="utf-8")
        
        return f"# Topic '{topic}' not found in knowledge base"
