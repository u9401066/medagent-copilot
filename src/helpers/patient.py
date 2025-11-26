"""
Patient Context - 病人情境記憶管理

強制單一病人機制，防止資料洩漏
"""

import json
from datetime import datetime
from pathlib import Path
from ..config import PATIENT_CONTEXT_PATH


class PatientContext:
    """病人情境記憶管理 - 強制單一病人"""
    
    def __init__(self):
        self.current_mrn = None
        self.current_fhir_id = None
        self.loaded_at = None
        self.task_id = None
    
    def load(self, mrn: str, fhir_id: str = None, task_id: str = None):
        """載入病人情境 - 會先清除舊的
        
        Args:
            mrn: 病人 MRN
            fhir_id: 病人 FHIR ID
            task_id: 關聯的任務 ID
        """
        if self.current_mrn and self.current_mrn != mrn:
            self.clear()  # 強制清除舊病人
        
        self.current_mrn = mrn
        self.current_fhir_id = fhir_id
        self.loaded_at = datetime.now().isoformat()
        self.task_id = task_id
        
        # 寫入檔案
        self._save_to_file()
    
    def clear(self):
        """清除病人情境"""
        self.current_mrn = None
        self.current_fhir_id = None
        self.loaded_at = None
        self.task_id = None
        
        # 刪除檔案
        context_file = PATIENT_CONTEXT_PATH / "current_patient.json"
        if context_file.exists():
            context_file.unlink()
    
    def get_current(self) -> dict | None:
        """取得當前病人情境
        
        Returns:
            病人資訊 dict 或 None
        """
        if not self.current_mrn:
            return None
        return {
            "mrn": self.current_mrn,
            "fhir_id": self.current_fhir_id,
            "loaded_at": self.loaded_at,
            "task_id": self.task_id
        }
    
    def _save_to_file(self):
        """儲存到檔案"""
        PATIENT_CONTEXT_PATH.mkdir(parents=True, exist_ok=True)
        context_file = PATIENT_CONTEXT_PATH / "current_patient.json"
        with open(context_file, "w") as f:
            json.dump(self.get_current(), f, indent=2)


# 全域單例
patient_context = PatientContext()
