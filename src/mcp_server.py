#!/usr/bin/env python3
"""
MedAgent FHIR MCP Server

使用 FastMCP 建立 FHIR API 工具給 VS Code Copilot 使用
讓 Copilot 可以作為醫療 Agent 來回答 MedAgentBench 的問題

參考: https://modelcontextprotocol.io/docs/develop/build-server
"""

import os
import json
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("medagent-fhir")

# FHIR API 設定
FHIR_API_BASE = os.getenv("FHIR_API_BASE", "http://localhost:8080/fhir/")


async def fhir_get(endpoint: str, params: dict = None) -> dict[str, Any] | None:
    """發送 FHIR GET 請求"""
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
        except Exception:
            return None


async def fhir_post(endpoint: str, data: dict) -> dict[str, Any] | None:
    """發送 FHIR POST 請求"""
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
            return response.json()
        except Exception:
            return None


# ============ FHIR Tools ============

@mcp.tool()
async def search_patient(
    name: str = None,
    family: str = None, 
    given: str = None,
    birthdate: str = None,
    identifier: str = None
) -> str:
    """Search for patients in the FHIR server.
    
    Use this to find patient information by name, birthdate, identifier (MRN), or other demographics.
    Returns patient demographic information including FHIR ID and MRN.
    
    Args:
        name: Patient name (any part)
        family: Patient family (last) name
        given: Patient given (first) name
        birthdate: Date of birth (YYYY-MM-DD)
        identifier: Patient MRN (e.g., S6534835)
    """
    params = {}
    if name:
        params["name"] = name
    if family:
        params["family"] = family
    if given:
        params["given"] = given
    if birthdate:
        params["birthdate"] = birthdate
    if identifier:
        params["identifier"] = identifier
    
    data = await fhir_get("Patient", params)
    
    if not data:
        return "Unable to search patients. Check FHIR server connection."
    
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_patient_by_mrn(mrn: str) -> str:
    """Get patient FHIR ID from MRN.
    
    Use this first when you have an MRN and need to call other FHIR APIs.
    Returns the patient's FHIR ID, name, birthDate, and other demographics.
    
    Args:
        mrn: Patient MRN (e.g., S6534835)
    """
    data = await fhir_get("Patient", {"identifier": mrn})
    
    if not data or not data.get("entry"):
        return json.dumps({"error": "Patient not found", "mrn": mrn})
    
    patient = data["entry"][0]["resource"]
    summary = {
        "fhir_id": patient["id"],
        "mrn": mrn,
        "name": patient.get("name", []),
        "birthDate": patient.get("birthDate"),
        "gender": patient.get("gender"),
    }
    return json.dumps(summary, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_observations(
    patient_id: str,
    code: str = None,
    date: str = None,
    category: str = None
) -> str:
    """Get observations (lab results, vitals) for a patient.
    
    Use this to retrieve lab values or vital signs.
    
    Common codes:
    - MG: Magnesium
    - K: Potassium  
    - GLU: Glucose/CBG
    - A1C: HbA1C
    - BP: Blood Pressure (vital signs)
    
    Args:
        patient_id: Patient FHIR ID (not MRN)
        code: Observation code (MG, K, GLU, A1C, etc.)
        date: Date filter (e.g., 'ge2023-11-12T10:15:00' for after this time)
        category: Category filter (e.g., 'vital-signs', 'laboratory')
    """
    params = {"patient": patient_id}
    if code:
        params["code"] = code
    if date:
        params["date"] = date
    if category:
        params["category"] = category
    
    data = await fhir_get("Observation", params)
    
    if not data:
        return "Unable to fetch observations. Check patient ID and FHIR connection."
    
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def create_vital_sign(
    patient_id: str,
    code: str,
    value: str,
    datetime: str
) -> str:
    """Record a vital sign observation for a patient.
    
    Use this to record blood pressure or other vital signs.
    The flowsheet ID for blood pressure is 'BP'.
    
    Args:
        patient_id: Patient FHIR ID
        code: Vital sign code (e.g., 'BP')
        value: Measurement value (e.g., '118/77 mmHg')
        datetime: DateTime in ISO format (e.g., '2023-11-12T15:30:00+00:00')
    """
    observation = {
        "resourceType": "Observation",
        "status": "final",
        "category": [{
            "coding": [{
                "system": "http://hl7.org/fhir/observation-category",
                "code": "vital-signs",
                "display": "Vital Signs"
            }]
        }],
        "code": {"text": code},
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": datetime,
        "valueString": value
    }
    
    result = await fhir_post("Observation", observation)
    
    if not result:
        return "Failed to create vital sign observation."
    
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def create_medication_order(
    patient_id: str,
    medication_code: str,
    medication_name: str,
    dose_value: float,
    dose_unit: str,
    datetime: str,
    route: str = None,
    rate_value: float = None,
    rate_unit: str = None
) -> str:
    """Create a medication order for a patient.
    
    Use this to order medications like IV magnesium or potassium replacement.
    
    Common NDC codes:
    - 0338-1715-40: IV Magnesium Sulfate
    - 40032-917-01: Oral Potassium
    
    Magnesium dosing:
    - Mild (1.5-1.9 mg/dL): 1g over 1 hour
    - Moderate (1.0-<1.5 mg/dL): 2g over 2 hours
    - Severe (<1.0 mg/dL): 4g over 4 hours
    
    Potassium dosing:
    - For every 0.1 mEq/L below 3.5, order 10 mEq
    
    Args:
        patient_id: Patient FHIR ID
        medication_code: NDC code (e.g., '0338-1715-40')
        medication_name: Medication display name
        dose_value: Dose amount
        dose_unit: Dose unit (g, mEq, etc.)
        datetime: Order datetime in ISO format
        route: Route (IV, oral, etc.)
        rate_value: Infusion rate (for IV medications)
        rate_unit: Rate unit (h for hours)
    """
    medication_request = {
        "resourceType": "MedicationRequest",
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {
            "coding": [{
                "system": "http://hl7.org/fhir/sid/ndc",
                "code": medication_code,
                "display": medication_name
            }],
            "text": medication_name
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "authoredOn": datetime,
        "dosageInstruction": [{
            "doseAndRate": [{
                "doseQuantity": {
                    "value": dose_value,
                    "unit": dose_unit
                }
            }]
        }]
    }
    
    if route:
        medication_request["dosageInstruction"][0]["route"] = {"text": route}
    
    if rate_value and rate_unit:
        medication_request["dosageInstruction"][0]["doseAndRate"][0]["rateQuantity"] = {
            "value": rate_value,
            "unit": rate_unit
        }
    
    result = await fhir_post("MedicationRequest", medication_request)
    
    if not result:
        return "Failed to create medication order."
    
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def create_service_request(
    patient_id: str,
    code_system: str,
    code: str,
    display: str,
    datetime: str,
    note: str = None,
    occurrence_datetime: str = None
) -> str:
    """Create a service request (lab order, referral) for a patient.
    
    Use this to order lab tests or create referrals.
    
    Common codes:
    - SNOMED 306181000000106: Orthopedic surgery referral
    - LOINC 2823-3: Serum potassium level
    - LOINC 4548-4: HbA1C
    
    For referrals, include SBAR note in the 'note' field.
    
    Args:
        patient_id: Patient FHIR ID
        code_system: Code system (http://snomed.info/sct or http://loinc.org)
        code: Service code
        display: Display name
        datetime: Order datetime in ISO format
        note: Free text note (SBAR for referrals)
        occurrence_datetime: When to perform (ISO format)
    """
    service_request = {
        "resourceType": "ServiceRequest",
        "status": "active",
        "intent": "order",
        "priority": "stat",
        "code": {
            "coding": [{
                "system": code_system,
                "code": code,
                "display": display
            }]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "authoredOn": datetime
    }
    
    if note:
        service_request["note"] = [{"text": note}]
    
    if occurrence_datetime:
        service_request["occurrenceDateTime"] = occurrence_datetime
    
    result = await fhir_post("ServiceRequest", service_request)
    
    if not result:
        return "Failed to create service request."
    
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_conditions(patient_id: str) -> str:
    """Get conditions (problems) from a patient's problem list.
    
    Args:
        patient_id: Patient FHIR ID
    """
    params = {
        "patient": patient_id,
        "category": "problem-list-item"
    }
    
    data = await fhir_get("Condition", params)
    
    if not data:
        return "Unable to fetch conditions. Check patient ID and FHIR connection."
    
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_medication_requests(
    patient_id: str,
    category: str = None
) -> str:
    """Get medication orders for a patient.
    
    Args:
        patient_id: Patient FHIR ID
        category: Category (Inpatient, Outpatient, Community, Discharge)
    """
    params = {"patient": patient_id}
    if category:
        params["category"] = category
    
    data = await fhir_get("MedicationRequest", params)
    
    if not data:
        return "Unable to fetch medication requests. Check patient ID and FHIR connection."
    
    return json.dumps(data, indent=2, ensure_ascii=False)


# ============ Run Server ============

def main():
    """Run the MCP server"""
    mcp.run(transport='stdio')


if __name__ == "__main__":
    main()
