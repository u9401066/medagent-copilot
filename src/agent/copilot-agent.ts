/**
 * MedAgent Copilot Client
 * 
 * 這個模組實作了一個符合 MedAgentBench 介面的 Agent
 * 透過 VS Code Copilot Chat API 來進行推論
 * 
 * 架構:
 * MedAgentBench -> CopilotAgent -> VS Code Copilot (with MCP tools) -> FHIR Server
 */

import { spawn, ChildProcess } from "child_process";
import * as readline from "readline";

export interface ChatMessage {
  role: "user" | "agent" | "assistant";
  content: string;
}

export interface AgentResponse {
  content: string;
  raw?: any;
}

/**
 * 將 MedAgentBench 的提示轉換為 Copilot 可理解的格式
 */
export function buildCopilotPrompt(history: ChatMessage[]): string {
  const systemPrompt = `You are a medical AI assistant that helps with FHIR-based EHR tasks.
You have access to FHIR tools to query and modify patient data.

IMPORTANT RESPONSE FORMAT:
You must respond in EXACTLY one of these three formats:

1. For GET requests:
GET {url}?{params}

2. For POST requests:
POST {url}
{json_payload}

3. When you have the final answer:
FINISH([answer1, answer2, ...])

Rules:
- Call only ONE function at a time
- Use the FHIR tools available to you to get patient data
- When you get the answer, use FINISH with a JSON array of answers
- Do NOT include any other text in your response
- The api_base is http://localhost:8080/fhir/

Examples:
- GET http://localhost:8080/fhir/Patient?name=John&birthdate=1990-01-01
- POST http://localhost:8080/fhir/Observation
{"resourceType": "Observation", ...}
- FINISH(["S6534835"])
- FINISH(["Patient not found"])
`;

  let prompt = systemPrompt + "\n\n";
  
  for (const msg of history) {
    if (msg.role === "user") {
      prompt += `User: ${msg.content}\n\n`;
    } else if (msg.role === "agent" || msg.role === "assistant") {
      prompt += `Assistant: ${msg.content}\n\n`;
    }
  }
  
  prompt += "Assistant: ";
  return prompt;
}

/**
 * 解析 Agent 回應，轉換為 MedAgentBench 格式
 */
export function parseAgentResponse(response: string): {
  type: "GET" | "POST" | "FINISH" | "INVALID";
  url?: string;
  payload?: any;
  answers?: string[];
} {
  const trimmed = response.trim();
  
  // 移除可能的 markdown 代碼塊
  const cleaned = trimmed
    .replace(/```tool_code\n?/g, "")
    .replace(/```json\n?/g, "")
    .replace(/```\n?/g, "")
    .trim();
  
  if (cleaned.startsWith("GET ")) {
    const url = cleaned.substring(4).trim();
    return { type: "GET", url };
  }
  
  if (cleaned.startsWith("POST ")) {
    const lines = cleaned.split("\n");
    const url = lines[0].substring(5).trim();
    const payloadStr = lines.slice(1).join("\n").trim();
    try {
      const payload = JSON.parse(payloadStr);
      return { type: "POST", url, payload };
    } catch {
      return { type: "POST", url, payload: payloadStr };
    }
  }
  
  if (cleaned.startsWith("FINISH(") && cleaned.endsWith(")")) {
    const answersStr = cleaned.slice(7, -1);
    try {
      const answers = JSON.parse(answersStr);
      return { type: "FINISH", answers: Array.isArray(answers) ? answers : [answers] };
    } catch {
      return { type: "FINISH", answers: [answersStr] };
    }
  }
  
  return { type: "INVALID" };
}

/**
 * 透過 CLI 與 Copilot 互動的 Agent
 * 這是一個模擬介面，實際使用時需要透過 VS Code Extension API
 */
export class CopilotAgent {
  private conversationHistory: ChatMessage[] = [];
  
  constructor() {}
  
  /**
   * 重置對話
   */
  reset(): void {
    this.conversationHistory = [];
  }
  
  /**
   * 進行推論
   */
  async inference(history: ChatMessage[]): Promise<string> {
    // 建構 prompt
    const prompt = buildCopilotPrompt(history);
    
    // 這裡需要實際呼叫 Copilot API
    // 目前先回傳提示，實際實作需要透過 VS Code Extension
    console.log("\n=== Prompt sent to Copilot ===");
    console.log(prompt);
    console.log("=== End of prompt ===\n");
    
    // TODO: 實際呼叫 Copilot
    // 可以透過以下方式:
    // 1. VS Code Extension API (vscode.lm.*)
    // 2. GitHub Copilot CLI
    // 3. 自定義 MCP Client
    
    throw new Error("Please implement actual Copilot API call");
  }
}

/**
 * 用於與 MedAgentBench 整合的 HTTP Agent
 * 這個 Agent 會透過 HTTP 與 VS Code Extension 通訊
 */
export class MCPCopilotAgent {
  private serverUrl: string;
  
  constructor(serverUrl: string = "http://localhost:3000") {
    this.serverUrl = serverUrl;
  }
  
  async inference(history: ChatMessage[]): Promise<string> {
    const response = await fetch(`${this.serverUrl}/inference`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ history })
    });
    
    const data = await response.json();
    return data.response;
  }
}
