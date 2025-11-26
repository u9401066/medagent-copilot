"""
Patient Memory - 病人記憶管理

設計理念：
1. 記憶是載入不是清空 - 遇到病人時載入該病人的歷史筆記
2. 記憶是選擇性寫入 - 只記錄 Agent 認為重要的筆記，不是把 FHIR 搬回來
3. 每個病人獨立檔案 - patients/{mrn}.json
"""

import json
from datetime import datetime
from pathlib import Path
from ..config import PATIENT_CONTEXT_PATH


class PatientMemory:
    """病人記憶管理 - 持久化儲存 Agent 筆記"""
    
    def __init__(self):
        self.current_mrn = None
        self.current_fhir_id = None
        self.loaded_at = None
        self.notes = []  # Agent 的筆記列表
        
        # 病人記憶目錄
        self.patients_dir = PATIENT_CONTEXT_PATH / "patients"
        self.patients_dir.mkdir(parents=True, exist_ok=True)
    
    def load(self, mrn: str, fhir_id: str = None) -> dict:
        """載入病人記憶
        
        如果該病人之前有記憶，會載入歷史筆記。
        如果是新病人，會自動建立空白記憶檔案。
        
        Args:
            mrn: 病人 MRN
            fhir_id: 病人 FHIR ID (可選)
            
        Returns:
            載入的記憶內容
        """
        self.current_mrn = mrn
        self.current_fhir_id = fhir_id
        self.loaded_at = datetime.now().isoformat()
        
        # 嘗試載入歷史記憶
        memory_file = self.patients_dir / f"{mrn}.json"
        if memory_file.exists():
            with open(memory_file) as f:
                data = json.load(f)
                self.notes = data.get("notes", [])
                # 如果沒傳 fhir_id，用歷史的
                if not fhir_id and data.get("fhir_id"):
                    self.current_fhir_id = data["fhir_id"]
        else:
            # 新病人 - 建立空白記憶檔案
            self.notes = []
            self._save()  # 自動建立空白檔案
        
        return self.get_memory()
    
    def add_note(self, note: str, category: str = "general") -> dict:
        """新增 Agent 筆記
        
        只記錄 Agent 認為重要的資訊，不是把 FHIR 搬回來。
        
        Args:
            note: 筆記內容
            category: 分類 (general, clinical, alert, etc.)
            
        Returns:
            更新後的記憶
        """
        if not self.current_mrn:
            return {"error": "No patient loaded. Call load() first."}
        
        self.notes.append({
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "note": note
        })
        
        self._save()
        return self.get_memory()
    
    def get_memory(self) -> dict:
        """取得當前病人記憶
        
        Returns:
            病人記憶內容
        """
        if not self.current_mrn:
            return {"status": "no_patient", "message": "No patient loaded"}
        
        return {
            "mrn": self.current_mrn,
            "fhir_id": self.current_fhir_id,
            "loaded_at": self.loaded_at,
            "notes_count": len(self.notes),
            "notes": self.notes
        }
    
    def get_notes_summary(self) -> str:
        """取得筆記摘要（用於 reminder）
        
        Returns:
            筆記摘要文字
        """
        if not self.notes:
            return ""
        
        recent = self.notes[-3:]  # 最近 3 筆
        summary = f"[Patient {self.current_mrn} notes: "
        summary += "; ".join([n["note"][:50] for n in recent])
        summary += "]"
        return summary
    
    def _save(self):
        """儲存到檔案"""
        if not self.current_mrn:
            return
        
        memory_file = self.patients_dir / f"{self.current_mrn}.json"
        data = {
            "mrn": self.current_mrn,
            "fhir_id": self.current_fhir_id,
            "last_updated": datetime.now().isoformat(),
            "notes": self.notes
        }
        
        with open(memory_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# 全域單例
patient_memory = PatientMemory()


# 向後相容 - 舊的 patient_context 別名
patient_context = patient_memory
