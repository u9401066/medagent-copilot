/**
 * MedAgentBench 橋接器
 * 
 * 這個模組負責與 MedAgentBench 的測試框架整合
 * 將 Copilot Agent 包裝成符合 MedAgentBench 格式的 Agent
 */

import * as fs from "fs";
import * as path from "path";
import axios from "axios";

// 測試案例結構
export interface TestCase {
  id: string;
  instruction: string;
  context: string;
  sol?: string[];
  eval_MRN?: string;
}

// Agent 輸出結構
export interface AgentOutput {
  status: string;
  content: string;
}

// 載入測試資料
export function loadTestData(dataPath: string): TestCase[] {
  const content = fs.readFileSync(dataPath, "utf-8");
  return JSON.parse(content);
}

// 載入 FHIR 函數定義
export function loadFunctions(funcPath: string): any[] {
  const content = fs.readFileSync(funcPath, "utf-8");
  return JSON.parse(content);
}

// 建構 MedAgentBench 格式的 prompt
export function buildMedAgentPrompt(
  testCase: TestCase,
  functions: any[],
  apiBase: string = "http://localhost:8080/fhir/"
): string {
  return `You are an expert in using FHIR functions to assist medical professionals. You are given a question and a set of possible functions. Based on the question, you will need to make one or more function/tool calls to achieve the purpose.

1. If you decide to invoke a GET function, you MUST put it in the format of
GET url?param_name1=param_value1&param_name2=param_value2...

2. If you decide to invoke a POST function, you MUST put it in the format of
POST url
[your payload data in JSON format]

3. If you have got answers for all the questions and finished all the requested tasks, you MUST call to finish the conversation in the format of (make sure the list is JSON loadable.)
FINISH([answer1, answer2, ...])

Your response must be in the format of one of the three cases, and you can call only one function each time. You SHOULD NOT include any other text in the response.

Here is a list of functions in JSON format that you can invoke. Note that you should use ${apiBase} as the api_base.
${JSON.stringify(functions, null, 2)}

Context: ${testCase.context}
Question: ${testCase.instruction}`;
}

// 發送 GET 請求到 FHIR 伺服器
export async function sendFhirGet(url: string): Promise<{ data?: any; error?: string }> {
  try {
    // 確保有 _format=json
    const urlWithFormat = url.includes("_format=") ? url : `${url}&_format=json`;
    const response = await axios.get(urlWithFormat);
    return { data: response.data };
  } catch (error: any) {
    return { error: error.message };
  }
}

// 發送 POST 請求到 FHIR 伺服器
export async function sendFhirPost(url: string, payload: any): Promise<{ data?: any; error?: string }> {
  try {
    const response = await axios.post(url, payload, {
      headers: { "Content-Type": "application/fhir+json" }
    });
    return { data: response.data };
  } catch (error: any) {
    return { error: error.message };
  }
}

// 執行單個測試案例
export async function runTestCase(
  testCase: TestCase,
  agentInference: (history: Array<{ role: string; content: string }>) => Promise<string>,
  functions: any[],
  apiBase: string = "http://localhost:8080/fhir/",
  maxRounds: number = 8
): Promise<{
  success: boolean;
  result: string | null;
  history: Array<{ role: string; content: string }>;
  rounds: number;
}> {
  const history: Array<{ role: string; content: string }> = [];
  
  // 初始 prompt
  const initialPrompt = buildMedAgentPrompt(testCase, functions, apiBase);
  history.push({ role: "user", content: initialPrompt });
  
  for (let round = 0; round < maxRounds; round++) {
    // 呼叫 Agent
    const response = await agentInference(history);
    const trimmed = response.trim()
      .replace(/```tool_code\n?/g, "")
      .replace(/```json\n?/g, "")
      .replace(/```\n?/g, "")
      .trim();
    
    history.push({ role: "agent", content: response });
    
    // 解析回應
    if (trimmed.startsWith("GET ")) {
      const url = trimmed.substring(4).trim();
      const urlWithFormat = url.includes("_format=") ? url : `${url}&_format=json`;
      const result = await sendFhirGet(urlWithFormat);
      
      if (result.data) {
        history.push({
          role: "user",
          content: `Here is the response from the GET request:\n${JSON.stringify(result.data, null, 2)}. Please call FINISH if you have got answers for all the questions and finished all the requested tasks`
        });
      } else {
        history.push({
          role: "user",
          content: `Error in sending the GET request: ${result.error}`
        });
      }
    } else if (trimmed.startsWith("POST ")) {
      const lines = trimmed.split("\n");
      const url = lines[0].substring(5).trim();
      const payloadStr = lines.slice(1).join("\n").trim();
      
      try {
        const payload = JSON.parse(payloadStr);
        const result = await sendFhirPost(url, payload);
        
        history.push({
          role: "user",
          content: "POST request accepted and executed successfully. Please call FINISH if you have got answers for all the questions and finished all the requested tasks"
        });
      } catch (error: any) {
        history.push({
          role: "user",
          content: `Invalid POST request: ${error.message}`
        });
      }
    } else if (trimmed.startsWith("FINISH(") && trimmed.endsWith(")")) {
      const resultStr = trimmed.slice(7, -1);
      return {
        success: true,
        result: resultStr,
        history,
        rounds: round + 1
      };
    } else {
      return {
        success: false,
        result: null,
        history,
        rounds: round + 1
      };
    }
  }
  
  return {
    success: false,
    result: null,
    history,
    rounds: maxRounds
  };
}
