#!/usr/bin/env node
/**
 * MedAgent MCP Server
 * 
 * 這個 MCP Server 提供 FHIR API 工具給 Copilot 使用
 * 讓 Copilot 可以作為醫療 Agent 來回答 MedAgentBench 的問題
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";
import axios from "axios";

// FHIR API 基礎設定
const FHIR_API_BASE = process.env.FHIR_API_BASE || "http://localhost:8080/fhir/";

// 定義 MCP 工具
const TOOLS: Tool[] = [
  {
    name: "fhir_search_patient",
    description: `Search for patients in the FHIR server. 
Use this to find patient information by name, birthdate, identifier (MRN), or other demographics.
Returns patient demographic information including FHIR ID and MRN.`,
    inputSchema: {
      type: "object",
      properties: {
        name: {
          type: "string",
          description: "Patient name (any part of the name)"
        },
        family: {
          type: "string",
          description: "Patient family (last) name"
        },
        given: {
          type: "string",
          description: "Patient given (first) name"
        },
        birthdate: {
          type: "string",
          description: "Patient date of birth in YYYY-MM-DD format"
        },
        identifier: {
          type: "string",
          description: "Patient identifier (MRN)"
        }
      }
    }
  },
  {
    name: "fhir_get_observations",
    description: `Get observations (lab results, vitals) for a patient.
Use this to retrieve lab values like magnesium (MG), potassium (K), glucose (GLU), HbA1C (A1C), 
or vital signs like blood pressure (BP).
The 'code' parameter specifies what type of observation to retrieve.`,
    inputSchema: {
      type: "object",
      properties: {
        patient: {
          type: "string",
          description: "Patient FHIR ID (not MRN)"
        },
        code: {
          type: "string",
          description: "Observation code (e.g., 'MG' for magnesium, 'K' for potassium, 'GLU' for glucose, 'A1C' for HbA1C, 'BP' for blood pressure)"
        },
        date: {
          type: "string",
          description: "Date filter for observations (e.g., 'ge2023-11-12' for greater than or equal)"
        },
        category: {
          type: "string",
          description: "Category filter (e.g., 'vital-signs' for vitals)"
        }
      },
      required: ["patient"]
    }
  },
  {
    name: "fhir_create_observation",
    description: `Create a new observation (vital sign) for a patient.
Use this to record vital signs like blood pressure.
The flowsheet ID for blood pressure is 'BP'.`,
    inputSchema: {
      type: "object",
      properties: {
        patient: {
          type: "string",
          description: "Patient FHIR ID"
        },
        code: {
          type: "string",
          description: "Flowsheet ID (e.g., 'BP' for blood pressure)"
        },
        value: {
          type: "string",
          description: "The measurement value (e.g., '118/77 mmHg')"
        },
        effectiveDateTime: {
          type: "string",
          description: "Date and time of the observation in ISO format"
        }
      },
      required: ["patient", "code", "value", "effectiveDateTime"]
    }
  },
  {
    name: "fhir_get_medication_requests",
    description: `Get medication orders for a patient.
Use this to check what medications have been ordered for a patient.`,
    inputSchema: {
      type: "object",
      properties: {
        patient: {
          type: "string",
          description: "Patient FHIR ID"
        },
        category: {
          type: "string",
          description: "Medication category (Inpatient, Outpatient, Community, Discharge)"
        }
      },
      required: ["patient"]
    }
  },
  {
    name: "fhir_create_medication_request",
    description: `Create a medication order for a patient.
Use this to order medications like IV magnesium replacement or potassium replacement.
NDC codes: IV Magnesium = 0338-1715-40, Potassium = 40032-917-01`,
    inputSchema: {
      type: "object",
      properties: {
        patient: {
          type: "string",
          description: "Patient FHIR ID"
        },
        medicationCode: {
          type: "string",
          description: "NDC code for the medication"
        },
        medicationDisplay: {
          type: "string",
          description: "Display name for the medication"
        },
        doseValue: {
          type: "number",
          description: "Dose amount"
        },
        doseUnit: {
          type: "string",
          description: "Dose unit (e.g., 'g', 'mEq')"
        },
        rateValue: {
          type: "number",
          description: "Rate value for IV medications"
        },
        rateUnit: {
          type: "string",
          description: "Rate unit (e.g., 'h' for hours)"
        },
        route: {
          type: "string",
          description: "Route of administration (e.g., 'IV', 'oral')"
        },
        authoredOn: {
          type: "string",
          description: "Date the order was written in ISO format"
        }
      },
      required: ["patient", "medicationCode", "medicationDisplay", "doseValue", "doseUnit", "authoredOn"]
    }
  },
  {
    name: "fhir_create_service_request",
    description: `Create a service request (lab order, referral) for a patient.
Use this to order lab tests or create referrals.
SNOMED code for orthopedic surgery referral: 306181000000106
LOINC codes: Serum potassium = 2823-3, HbA1C = 4548-4`,
    inputSchema: {
      type: "object",
      properties: {
        patient: {
          type: "string",
          description: "Patient FHIR ID"
        },
        codeSystem: {
          type: "string",
          description: "Code system (e.g., 'http://loinc.org', 'http://snomed.info/sct')"
        },
        code: {
          type: "string",
          description: "The procedure/service code"
        },
        display: {
          type: "string",
          description: "Display name for the service"
        },
        note: {
          type: "string",
          description: "Free text note for the request"
        },
        occurrenceDateTime: {
          type: "string",
          description: "When the service should be performed (ISO format)"
        },
        authoredOn: {
          type: "string",
          description: "When the order was created (ISO format)"
        }
      },
      required: ["patient", "codeSystem", "code", "display", "authoredOn"]
    }
  },
  {
    name: "fhir_get_conditions",
    description: `Get conditions (problems) for a patient from their problem list.`,
    inputSchema: {
      type: "object",
      properties: {
        patient: {
          type: "string",
          description: "Patient FHIR ID"
        },
        category: {
          type: "string",
          description: "Condition category (usually 'problem-list-item')"
        }
      },
      required: ["patient"]
    }
  },
  {
    name: "get_patient_by_mrn",
    description: `Convenience tool to get patient FHIR ID from MRN.
Use this first when you have an MRN and need to call other FHIR APIs.`,
    inputSchema: {
      type: "object",
      properties: {
        mrn: {
          type: "string",
          description: "The patient MRN (e.g., 'S6534835')"
        }
      },
      required: ["mrn"]
    }
  }
];

// FHIR API 呼叫函數
async function fhirGet(endpoint: string, params: Record<string, string> = {}): Promise<any> {
  const url = new URL(endpoint, FHIR_API_BASE);
  Object.entries(params).forEach(([key, value]) => {
    if (value) url.searchParams.append(key, value);
  });
  url.searchParams.append("_format", "json");
  
  try {
    const response = await axios.get(url.toString());
    return response.data;
  } catch (error: any) {
    return { error: error.message, status: error.response?.status };
  }
}

async function fhirPost(endpoint: string, data: any): Promise<any> {
  const url = new URL(endpoint, FHIR_API_BASE);
  
  try {
    const response = await axios.post(url.toString(), data, {
      headers: { "Content-Type": "application/fhir+json" }
    });
    return response.data;
  } catch (error: any) {
    return { error: error.message, status: error.response?.status };
  }
}

// 工具處理函數
async function handleToolCall(name: string, args: any): Promise<string> {
  switch (name) {
    case "fhir_search_patient": {
      const params: Record<string, string> = {};
      if (args.name) params.name = args.name;
      if (args.family) params.family = args.family;
      if (args.given) params.given = args.given;
      if (args.birthdate) params.birthdate = args.birthdate;
      if (args.identifier) params.identifier = args.identifier;
      
      const result = await fhirGet("Patient", params);
      return JSON.stringify(result, null, 2);
    }
    
    case "fhir_get_observations": {
      const params: Record<string, string> = {
        patient: args.patient
      };
      if (args.code) params.code = args.code;
      if (args.date) params.date = args.date;
      if (args.category) params.category = args.category;
      
      const result = await fhirGet("Observation", params);
      return JSON.stringify(result, null, 2);
    }
    
    case "fhir_create_observation": {
      const observation = {
        resourceType: "Observation",
        status: "final",
        category: [{
          coding: [{
            system: "http://hl7.org/fhir/observation-category",
            code: "vital-signs",
            display: "Vital Signs"
          }]
        }],
        code: {
          text: args.code
        },
        subject: {
          reference: `Patient/${args.patient}`
        },
        effectiveDateTime: args.effectiveDateTime,
        valueString: args.value
      };
      
      const result = await fhirPost("Observation", observation);
      return JSON.stringify(result, null, 2);
    }
    
    case "fhir_get_medication_requests": {
      const params: Record<string, string> = {
        patient: args.patient
      };
      if (args.category) params.category = args.category;
      
      const result = await fhirGet("MedicationRequest", params);
      return JSON.stringify(result, null, 2);
    }
    
    case "fhir_create_medication_request": {
      const medicationRequest: any = {
        resourceType: "MedicationRequest",
        status: "active",
        intent: "order",
        medicationCodeableConcept: {
          coding: [{
            system: "http://hl7.org/fhir/sid/ndc",
            code: args.medicationCode,
            display: args.medicationDisplay
          }],
          text: args.medicationDisplay
        },
        subject: {
          reference: `Patient/${args.patient}`
        },
        authoredOn: args.authoredOn,
        dosageInstruction: [{
          doseAndRate: [{
            doseQuantity: {
              value: args.doseValue,
              unit: args.doseUnit
            }
          }]
        }]
      };
      
      if (args.route) {
        medicationRequest.dosageInstruction[0].route = { text: args.route };
      }
      if (args.rateValue && args.rateUnit) {
        medicationRequest.dosageInstruction[0].doseAndRate[0].rateQuantity = {
          value: args.rateValue,
          unit: args.rateUnit
        };
      }
      
      const result = await fhirPost("MedicationRequest", medicationRequest);
      return JSON.stringify(result, null, 2);
    }
    
    case "fhir_create_service_request": {
      const serviceRequest: any = {
        resourceType: "ServiceRequest",
        status: "active",
        intent: "order",
        priority: "stat",
        code: {
          coding: [{
            system: args.codeSystem,
            code: args.code,
            display: args.display
          }]
        },
        subject: {
          reference: `Patient/${args.patient}`
        },
        authoredOn: args.authoredOn
      };
      
      if (args.note) {
        serviceRequest.note = [{ text: args.note }];
      }
      if (args.occurrenceDateTime) {
        serviceRequest.occurrenceDateTime = args.occurrenceDateTime;
      }
      
      const result = await fhirPost("ServiceRequest", serviceRequest);
      return JSON.stringify(result, null, 2);
    }
    
    case "fhir_get_conditions": {
      const params: Record<string, string> = {
        patient: args.patient
      };
      if (args.category) params.category = args.category;
      
      const result = await fhirGet("Condition", params);
      return JSON.stringify(result, null, 2);
    }
    
    case "get_patient_by_mrn": {
      const result = await fhirGet("Patient", { identifier: args.mrn });
      
      // 提取 FHIR ID
      if (result.entry && result.entry.length > 0) {
        const patient = result.entry[0].resource;
        return JSON.stringify({
          fhirId: patient.id,
          mrn: args.mrn,
          name: patient.name,
          birthDate: patient.birthDate,
          gender: patient.gender
        }, null, 2);
      }
      return JSON.stringify({ error: "Patient not found", mrn: args.mrn });
    }
    
    default:
      return JSON.stringify({ error: `Unknown tool: ${name}` });
  }
}

// 主程式
async function main() {
  const server = new Server(
    {
      name: "medagent-fhir-server",
      version: "1.0.0",
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  // 列出可用工具
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return { tools: TOOLS };
  });

  // 處理工具呼叫
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    
    try {
      const result = await handleToolCall(name, args || {});
      return {
        content: [{ type: "text", text: result }],
      };
    } catch (error: any) {
      return {
        content: [{ type: "text", text: `Error: ${error.message}` }],
        isError: true,
      };
    }
  });

  // 啟動 server
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("MedAgent FHIR MCP Server running on stdio");
}

main().catch(console.error);
