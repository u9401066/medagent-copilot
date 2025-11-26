#!/usr/bin/env python3
"""
MedAgent FHIR MCP Server

使用 FastMCP 建立 FHIR API 工具給 VS Code Copilot 使用
讓 Copilot 可以作為醫療 Agent 來回答 MedAgentBench 的問題

模組結構:
- config.py: 設定與路徑
- helpers/: 提醒系統與病人情境管理
- fhir/: FHIR API 客戶端與工具
- tasks/: 任務狀態與管理工具
- resources/: MCP 資源暴露 (知識庫)

重要時間點: 所有任務假設當前時間為 2023-11-13T10:15:00+00:00
評估機制: 使用官方 refsol.py 進行評估
提醒系統: 每個工具回傳都會附帶簡短提醒
"""

from mcp.server.fastmcp import FastMCP

# 建立 MCP Server
mcp = FastMCP("medagent-fhir")

# 註冊所有工具
from .fhir import register_fhir_tools
from .tasks import register_task_tools
from .resources import register_resources

register_fhir_tools(mcp)
register_task_tools(mcp)
register_resources(mcp)


def main():
    """Run the MCP server"""
    mcp.run(transport='stdio')


if __name__ == "__main__":
    main()
