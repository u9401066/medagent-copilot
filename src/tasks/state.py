"""
Task State - 任務狀態追蹤

管理任務載入、進度和結果
"""


class TaskState:
    """任務狀態追蹤 (支援反覆呼叫)"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置所有狀態"""
        self.tasks = []
        self.current_index = 0
        self.results = []
        self.version = None
        self.task_file = None
        self.awaiting_submit = False  # 是否正在等待 submit
    
    @property
    def has_tasks(self) -> bool:
        """是否有載入任務"""
        return len(self.tasks) > 0
    
    @property
    def is_complete(self) -> bool:
        """是否全部完成"""
        return self.current_index >= len(self.tasks)
    
    @property
    def current_task(self) -> dict | None:
        """取得當前任務"""
        if not self.has_tasks or self.is_complete:
            return None
        return self.tasks[self.current_index]
    
    @property
    def remaining(self) -> int:
        """剩餘任務數"""
        return max(0, len(self.tasks) - self.current_index)
    
    def mark_task_started(self):
        """標記任務開始，等待 submit"""
        self.awaiting_submit = True
    
    def add_result(self, task_id: str, answer: str, task_data: dict):
        """記錄答案
        
        Args:
            task_id: 任務 ID
            answer: 提交的答案
            task_data: 原始任務資料
        """
        from datetime import datetime
        from fhir.post_history import post_history
        
        # 生成官方格式的 POST 歷史
        official_history = post_history.generate_official_history(task_id)
        
        self.results.append({
            "task_id": task_id,
            "answer": answer,
            "expected_sol": task_data.get("sol"),
            "eval_MRN": task_data.get("eval_MRN"),
            "timestamp": datetime.now().isoformat(),
            # 官方評估器需要的格式
            "post_history": official_history,
            "post_count": post_history.get_post_count_for_task(task_id)
        })
        self.current_index += 1
        self.awaiting_submit = False  # 解鎖，允許 get_next_task


# 全域單例
task_state = TaskState()
