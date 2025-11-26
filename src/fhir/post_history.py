"""
POST History - 記錄所有 FHIR POST 操作

用於生成官方 refsol.py 需要的 POST 歷史格式
"""

import json
from dataclasses import dataclass, field
from typing import List, Tuple
from datetime import datetime


@dataclass
class PostRecord:
    """單一 POST 記錄"""
    url: str
    payload: dict
    response_id: str
    timestamp: str
    task_id: str = None


class PostHistory:
    """POST 歷史管理器 - 單例模式"""
    
    def __init__(self):
        self.records: List[PostRecord] = []
        self._current_task_id: str = None
    
    def set_current_task(self, task_id: str):
        """設定當前任務 ID"""
        self._current_task_id = task_id
    
    def record_post(self, url: str, payload: dict, response_id: str):
        """記錄一次 POST 操作"""
        record = PostRecord(
            url=url,
            payload=payload,
            response_id=response_id,
            timestamp=datetime.now().isoformat(),
            task_id=self._current_task_id
        )
        self.records.append(record)
        return record
    
    def get_posts_for_task(self, task_id: str) -> List[PostRecord]:
        """取得特定任務的所有 POST"""
        return [r for r in self.records if r.task_id == task_id]
    
    def clear_task_posts(self, task_id: str):
        """清除特定任務的 POST 記錄"""
        self.records = [r for r in self.records if r.task_id != task_id]
    
    def clear_all(self):
        """清除所有記錄"""
        self.records = []
    
    def generate_official_history(self, task_id: str) -> List[dict]:
        """生成官方 refsol.py 格式的歷史記錄
        
        官方 extract_posts() 解析邏輯：
        1. 找 role='agent' 且 content 包含 'POST' 的訊息
        2. 下一條訊息的 content 必須包含 "POST request accepted"
        3. 解析 agent content: 
           - url = content.split('\n')[0][4:].strip()  # 去掉 "POST " 前綴
           - payload = json.loads('\n'.join(content.split('\n')[1:]))
        
        Returns:
            List of history entries in official format
        """
        history = []
        posts = self.get_posts_for_task(task_id)
        
        for post in posts:
            # Agent 發送的 POST 請求
            # 格式: "POST {url}\n{json}"  注意 POST 後面有空格
            agent_content = f"POST {post.url}\n{json.dumps(post.payload)}"
            history.append({
                "role": "agent",
                "content": agent_content
            })
            
            # 下一條訊息必須包含 "POST request accepted"
            history.append({
                "role": "user",  # 根據原始對話，系統回應通常標記為 user
                "content": f"POST request accepted and executed successfully. Resource created with id: {post.response_id}"
            })
        
        return history
    
    def has_posts_for_task(self, task_id: str) -> bool:
        """檢查任務是否有 POST 記錄"""
        return any(r.task_id == task_id for r in self.records)
    
    def get_post_count_for_task(self, task_id: str) -> int:
        """取得任務的 POST 數量"""
        return len([r for r in self.records if r.task_id == task_id])


# 全域單例
post_history = PostHistory()
