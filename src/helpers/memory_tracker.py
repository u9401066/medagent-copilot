"""
Memory Access Tracker - 記憶庫存取追蹤器

追蹤 Agent 對記憶庫和知識庫的存取情況，
用於評估記憶系統的實際使用率和效果。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
from config import RESULTS_PATH


@dataclass
class MemoryAccessEvent:
    """記憶存取事件"""
    timestamp: str
    task_id: str
    access_type: str  # 'read' | 'write' | 'resource'
    resource_name: str  # e.g., 'patient_memory', 'clinical_knowledge', 'constitution'
    patient_mrn: Optional[str] = None
    details: Optional[str] = None
    
    
@dataclass 
class MemoryUsageStats:
    """記憶使用統計"""
    total_tasks: int = 0
    tasks_with_memory_access: int = 0
    
    # 各類型存取次數
    patient_memory_reads: int = 0
    patient_memory_writes: int = 0
    knowledge_reads: int = 0
    constitution_reads: int = 0
    resource_reads: int = 0
    
    # 按任務類型統計
    access_by_task_type: Dict[str, int] = field(default_factory=dict)
    
    # 詳細事件列表
    events: List[dict] = field(default_factory=list)


class MemoryTracker:
    """記憶庫存取追蹤器"""
    
    def __init__(self, run_id: str = None):
        """
        Args:
            run_id: 執行 ID (用於儲存追蹤記錄)
        """
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.events: List[MemoryAccessEvent] = []
        self.current_task_id: Optional[str] = None
        self.tasks_accessed: set = set()  # 有存取記憶的任務
        
        # 追蹤檔案路徑
        self.tracker_dir = RESULTS_PATH / f"memory_tracking"
        self.tracker_dir.mkdir(parents=True, exist_ok=True)
        
    def set_current_task(self, task_id: str):
        """設定當前任務 ID"""
        self.current_task_id = task_id
        
    def track_read(self, resource_name: str, patient_mrn: str = None, details: str = None):
        """追蹤讀取事件
        
        Args:
            resource_name: 資源名稱 (patient_memory, clinical_knowledge, etc.)
            patient_mrn: 病患 MRN (如果適用)
            details: 額外細節
        """
        event = MemoryAccessEvent(
            timestamp=datetime.now().isoformat(),
            task_id=self.current_task_id or "unknown",
            access_type="read",
            resource_name=resource_name,
            patient_mrn=patient_mrn,
            details=details
        )
        self.events.append(event)
        
        if self.current_task_id:
            self.tasks_accessed.add(self.current_task_id)
            
        # 即時儲存
        self._save_event(event)
        
    def track_write(self, resource_name: str, patient_mrn: str = None, details: str = None):
        """追蹤寫入事件"""
        event = MemoryAccessEvent(
            timestamp=datetime.now().isoformat(),
            task_id=self.current_task_id or "unknown",
            access_type="write",
            resource_name=resource_name,
            patient_mrn=patient_mrn,
            details=details
        )
        self.events.append(event)
        
        if self.current_task_id:
            self.tasks_accessed.add(self.current_task_id)
            
        self._save_event(event)
        
    def track_resource_access(self, resource_uri: str, details: str = None):
        """追蹤 MCP Resource 存取"""
        event = MemoryAccessEvent(
            timestamp=datetime.now().isoformat(),
            task_id=self.current_task_id or "unknown",
            access_type="resource",
            resource_name=resource_uri,
            details=details
        )
        self.events.append(event)
        
        if self.current_task_id:
            self.tasks_accessed.add(self.current_task_id)
            
        self._save_event(event)
        
    def get_stats(self, total_tasks: int = None) -> MemoryUsageStats:
        """取得統計數據
        
        Args:
            total_tasks: 總任務數 (用於計算比率)
            
        Returns:
            記憶使用統計
        """
        stats = MemoryUsageStats(
            total_tasks=total_tasks or len(self.tasks_accessed),
            tasks_with_memory_access=len(self.tasks_accessed),
            events=[asdict(e) for e in self.events]
        )
        
        # 計算各類型存取次數
        access_by_task_type = {}
        
        for event in self.events:
            # 按資源類型統計
            if event.resource_name == "patient_memory":
                if event.access_type == "read":
                    stats.patient_memory_reads += 1
                elif event.access_type == "write":
                    stats.patient_memory_writes += 1
            elif event.resource_name in ["clinical_knowledge", "med://knowledge/clinical"]:
                stats.knowledge_reads += 1
            elif event.resource_name in ["constitution", "med://constitution"]:
                stats.constitution_reads += 1
            elif event.access_type == "resource":
                stats.resource_reads += 1
                
            # 按任務類型統計
            if event.task_id and event.task_id != "unknown":
                task_type = event.task_id.split("_")[0]  # e.g., "task7" from "task7_15"
                access_by_task_type[task_type] = access_by_task_type.get(task_type, 0) + 1
                
        stats.access_by_task_type = access_by_task_type
        return stats
    
    def get_usage_rate(self, total_tasks: int) -> float:
        """取得記憶使用率
        
        Args:
            total_tasks: 總任務數
            
        Returns:
            使用率 (0.0 - 1.0)
        """
        if total_tasks == 0:
            return 0.0
        return len(self.tasks_accessed) / total_tasks
    
    def generate_report(self, total_tasks: int = None) -> str:
        """產生記憶使用報告
        
        Args:
            total_tasks: 總任務數
            
        Returns:
            Markdown 格式報告
        """
        stats = self.get_stats(total_tasks)
        
        total = total_tasks or stats.total_tasks
        usage_rate = (stats.tasks_with_memory_access / total * 100) if total > 0 else 0
        
        report = f"""# Memory Usage Report
Run ID: {self.run_id}
Generated: {datetime.now().isoformat()}

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | {total} |
| Tasks with Memory Access | {stats.tasks_with_memory_access} |
| **Memory Usage Rate** | **{usage_rate:.1f}%** |

## Access Breakdown

| Resource Type | Read | Write | Total |
|---------------|------|-------|-------|
| Patient Memory | {stats.patient_memory_reads} | {stats.patient_memory_writes} | {stats.patient_memory_reads + stats.patient_memory_writes} |
| Clinical Knowledge | {stats.knowledge_reads} | - | {stats.knowledge_reads} |
| Constitution | {stats.constitution_reads} | - | {stats.constitution_reads} |
| MCP Resources | {stats.resource_reads} | - | {stats.resource_reads} |

## Access by Task Type

| Task Type | Access Count |
|-----------|--------------|
"""
        for task_type, count in sorted(stats.access_by_task_type.items()):
            report += f"| {task_type} | {count} |\n"
            
        if not stats.access_by_task_type:
            report += "| (none) | 0 |\n"
            
        report += f"""
## Observations

"""
        if usage_rate == 0:
            report += "⚠️ **No memory access recorded!** Agent did not use the memory system.\n"
        elif usage_rate < 10:
            report += f"⚠️ **Very low usage ({usage_rate:.1f}%)** - Memory system is underutilized.\n"
        elif usage_rate < 50:
            report += f"📊 **Moderate usage ({usage_rate:.1f}%)** - Some tasks benefit from memory.\n"
        else:
            report += f"✅ **Good usage ({usage_rate:.1f}%)** - Memory system is actively used.\n"
            
        return report
    
    def _save_event(self, event: MemoryAccessEvent):
        """即時儲存事件到檔案"""
        events_file = self.tracker_dir / f"{self.run_id}_events.jsonl"
        with open(events_file, "a") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
            
    def save_full_report(self, total_tasks: int = None):
        """儲存完整報告"""
        # 儲存統計 JSON
        stats = self.get_stats(total_tasks)
        stats_file = self.tracker_dir / f"{self.run_id}_stats.json"
        with open(stats_file, "w") as f:
            json.dump(asdict(stats), f, indent=2, ensure_ascii=False)
            
        # 儲存 Markdown 報告
        report = self.generate_report(total_tasks)
        report_file = self.tracker_dir / f"{self.run_id}_report.md"
        with open(report_file, "w") as f:
            f.write(report)
            
        return {
            "stats_file": str(stats_file),
            "report_file": str(report_file),
            "usage_rate": self.get_usage_rate(total_tasks or len(self.tasks_accessed))
        }


# 全域單例
memory_tracker = MemoryTracker()


def get_tracker(run_id: str = None) -> MemoryTracker:
    """取得或創建追蹤器
    
    Args:
        run_id: 執行 ID (如果指定，會創建新的追蹤器)
        
    Returns:
        MemoryTracker instance
    """
    global memory_tracker
    if run_id:
        memory_tracker = MemoryTracker(run_id)
    return memory_tracker
