"""
FHIR Client - FHIR API 連線與請求

提供 GET/POST 請求方法給 FHIR Server
POST 回應會包含官方評估器需要的歷史格式
"""

import json
from typing import Any
import httpx
from config import FHIR_API_BASE


async def fhir_get(endpoint: str, params: dict = None) -> dict[str, Any] | None:
    """發送 FHIR GET 請求
    
    Args:
        endpoint: FHIR 端點 (如 "Patient", "Observation")
        params: 查詢參數
        
    Returns:
        FHIR Bundle 或錯誤 dict
    """
    url = f"{FHIR_API_BASE.rstrip('/')}/{endpoint}"
    if params:
        query_params = "&".join(f"{k}={v}" for k, v in params.items() if v)
        if query_params:
            url = f"{url}?{query_params}"
    if "_format" not in url:
        url += ("&" if "?" in url else "?") + "_format=json"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}


async def fhir_post(endpoint: str, data: dict) -> dict[str, Any] | None:
    """發送 FHIR POST 請求
    
    回應包含官方評估器需要的歷史格式記錄
    
    Args:
        endpoint: FHIR 端點
        data: 要傳送的 FHIR Resource
        
    Returns:
        包含結果和 POST 歷史記錄的 dict:
        {
            "result": {...},  # FHIR 回應
            "resource_id": "...",
            "_post_record": {  # 官方格式的 POST 記錄
                "agent": "POST {url}\n{json}",
                "user": "POST request accepted..."
            }
        }
    """
    from tasks.state import task_state
    
    url = f"{FHIR_API_BASE.rstrip('/')}/{endpoint}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url, 
                json=data, 
                headers={"Content-Type": "application/fhir+json"},
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            # 取得資源 ID
            resource_id = result.get("id", "unknown")
            
            # 生成官方格式的 POST 歷史記錄
            agent_content = f"POST {url}\n{json.dumps(data)}"
            user_content = f"POST request accepted and executed successfully. Resource created with id: {resource_id}"
            
            # 記錄到 task_state
            task_state.record_post(agent_content, user_content)
            
            return {
                "result": result,
                "resource_id": resource_id,
                "_post_record": {
                    "agent": agent_content,
                    "user": user_content
                }
            }
        except Exception as e:
            return {"error": str(e)}
