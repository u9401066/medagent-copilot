"""
Composite Tools - 多步邏輯複合工具

對於需要多步查詢+判斷的任務，提供一站式工具
減少 LLM 推理錯誤，提高成功率
"""

import json
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP

from ..helpers import with_reminder, patient_context
from ..fhir.client import fhir_get, fhir_post


# 臨床常數
CURRENT_TIME = "2023-11-13T10:15:00+00:00"
CURRENT_DATE = "2023-11-13"
TIME_24H_AGO = "2023-11-12T10:15:00+00:00"
ONE_YEAR_AGO = "2022-11-13"

# 電解質閾值
MG_NORMAL_MIN = 1.7
K_NORMAL_MIN = 3.5

# 藥物代碼
IV_MAGNESIUM_NDC = "0338-1715-40"
ORAL_POTASSIUM_NDC = "40032-917-01"
SERUM_K_LOINC = "2823-3"
HBA1C_LOINC = "4548-4"


def register_composite_tools(mcp: FastMCP):
    """向 MCP Server 註冊複合工具
    
    這些工具封裝多步驟邏輯，減少 LLM 錯誤
    """
    
    # ============ Task 5: Mg 補充 (查詢 + 判斷 + 開單) ============
    
    @mcp.tool()
    async def check_and_replace_magnesium(patient_id: str) -> str:
        """Check magnesium level and order replacement if needed (Task 5).
        
        This is a composite tool that:
        1. Gets the latest Mg level from the past 24 hours
        2. Determines if replacement is needed (< 1.7 mg/dL)
        3. Calculates the correct dose based on severity
        4. Creates the medication order if needed
        
        Dosing rules:
        - Mild (1.5-1.9): 1g IV over 1h
        - Moderate (1.0-<1.5): 2g IV over 2h
        - Severe (<1.0): 4g IV over 4h
        
        Args:
            patient_id: Patient FHIR ID (same as MRN for MedAgentBench)
        
        Returns:
            Summary of action taken
        """
        # Step 1: 查詢 24h 內的 Mg
        mg_data = await fhir_get("Observation", {
            "patient": patient_id,
            "code": "MG",
            "date": f"ge{TIME_24H_AGO}",
            "_count": "100"
        })
        
        if not mg_data or "error" in mg_data:
            return with_reminder({
                "status": "error",
                "step": "query_mg",
                "message": "Failed to query magnesium level",
                "answer": "[]"
            })
        
        # Step 2: 找最新值
        entries = mg_data.get("entry", [])
        if not entries:
            return with_reminder({
                "status": "no_data",
                "message": "No Mg values found in past 24 hours",
                "answer": "[]"  # 沒有值就不需要補充
            })
        
        # 按時間排序找最新
        latest_entry = None
        latest_time = None
        for e in entries:
            obs = e.get("resource", {})
            effective = obs.get("effectiveDateTime", "")
            if not latest_time or effective > latest_time:
                latest_time = effective
                latest_entry = obs
        
        if not latest_entry:
            return with_reminder({
                "status": "no_valid_data",
                "message": "No valid Mg observation found",
                "answer": "[]"
            })
        
        # 取得數值
        value_quantity = latest_entry.get("valueQuantity", {})
        mg_value = value_quantity.get("value")
        
        if mg_value is None:
            return with_reminder({
                "status": "no_value",
                "message": "Mg observation has no numeric value",
                "answer": "[]"
            })
        
        # Step 3: 判斷是否需要補充
        if mg_value >= MG_NORMAL_MIN:
            return with_reminder({
                "status": "normal",
                "mg_value": mg_value,
                "threshold": MG_NORMAL_MIN,
                "message": f"Mg {mg_value} mg/dL is within normal range. No replacement needed.",
                "answer": "[]"
            })
        
        # Step 4: 計算劑量
        if mg_value >= 1.5:
            dose = 1
            rate = 1
            severity = "mild"
        elif mg_value >= 1.0:
            dose = 2
            rate = 2
            severity = "moderate"
        else:
            dose = 4
            rate = 4
            severity = "severe"
        
        # Step 5: 開立醫囑
        medication_request = {
            "resourceType": "MedicationRequest",
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {
                "coding": [{
                    "system": "http://hl7.org/fhir/sid/ndc",
                    "code": IV_MAGNESIUM_NDC,
                    "display": "IV Magnesium Sulfate"
                }],
                "text": "IV Magnesium Sulfate"
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "authoredOn": CURRENT_TIME,
            "dosageInstruction": [{
                "route": "IV",
                "doseAndRate": [{
                    "doseQuantity": {"value": dose, "unit": "g"},
                    "rateQuantity": {"value": rate, "unit": "h"}
                }]
            }]
        }
        
        result = await fhir_post("MedicationRequest", medication_request)
        
        if not result or "error" in result:
            return with_reminder({
                "status": "order_failed",
                "mg_value": mg_value,
                "dose": f"{dose}g over {rate}h",
                "error": result,
                "answer": "[]"
            })
        
        return with_reminder({
            "status": "order_created",
            "mg_value": mg_value,
            "severity": severity,
            "dose": f"{dose}g IV over {rate}h",
            "order_id": result.get("id"),
            "message": f"Ordered {dose}g IV Mg for {severity} hypomagnesemia ({mg_value} mg/dL)",
            "answer": "[]"
        })
    
    
    # ============ Task 9: K 補充 + 隔日抽血 ============
    
    @mcp.tool()
    async def check_and_replace_potassium(patient_id: str) -> str:
        """Check potassium level and order replacement + follow-up labs if needed (Task 9).
        
        This is a composite tool that:
        1. Gets the latest K level
        2. Determines if replacement is needed (< 3.5 mEq/L)
        3. Calculates the correct dose (10 mEq per 0.1 below 3.5)
        4. Creates medication order AND orders next-day recheck
        
        Args:
            patient_id: Patient FHIR ID
        
        Returns:
            Summary of action taken
        """
        # Step 1: 查詢 K
        k_data = await fhir_get("Observation", {
            "patient": patient_id,
            "code": "K",
            "_count": "100"
        })
        
        if not k_data or "error" in k_data:
            return with_reminder({
                "status": "error",
                "step": "query_k",
                "message": "Failed to query potassium level",
                "answer": "[]"
            })
        
        # Step 2: 找最新值
        entries = k_data.get("entry", [])
        if not entries:
            return with_reminder({
                "status": "no_data",
                "message": "No K values found",
                "answer": "[]"
            })
        
        latest_entry = None
        latest_time = None
        for e in entries:
            obs = e.get("resource", {})
            effective = obs.get("effectiveDateTime", "")
            if not latest_time or effective > latest_time:
                latest_time = effective
                latest_entry = obs
        
        if not latest_entry:
            return with_reminder({
                "status": "no_valid_data",
                "message": "No valid K observation found",
                "answer": "[]"
            })
        
        value_quantity = latest_entry.get("valueQuantity", {})
        k_value = value_quantity.get("value")
        
        if k_value is None:
            return with_reminder({
                "status": "no_value",
                "message": "K observation has no numeric value",
                "answer": "[]"
            })
        
        # Step 3: 判斷是否需要補充
        if k_value >= K_NORMAL_MIN:
            return with_reminder({
                "status": "normal",
                "k_value": k_value,
                "threshold": K_NORMAL_MIN,
                "message": f"K {k_value} mEq/L is within normal range. No replacement needed.",
                "answer": "[]"
            })
        
        # Step 4: 計算劑量 (每低於 3.5 的 0.1，補充 10 mEq)
        deficit = K_NORMAL_MIN - k_value
        dose = int(round(deficit / 0.1) * 10)
        
        # Step 5: 開立補充醫囑
        medication_request = {
            "resourceType": "MedicationRequest",
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {
                "coding": [{
                    "system": "http://hl7.org/fhir/sid/ndc",
                    "code": ORAL_POTASSIUM_NDC,
                    "display": "Potassium Chloride"
                }],
                "text": "Potassium Chloride"
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "authoredOn": CURRENT_TIME,
            "dosageInstruction": [{
                "route": "oral",
                "doseAndRate": [{
                    "doseQuantity": {"value": dose, "unit": "mEq"}
                }]
            }]
        }
        
        med_result = await fhir_post("MedicationRequest", medication_request)
        
        if not med_result or "error" in med_result:
            return with_reminder({
                "status": "medication_order_failed",
                "k_value": k_value,
                "dose": f"{dose} mEq",
                "error": med_result,
                "answer": "[]"
            })
        
        # Step 6: 開立隔日抽血
        next_morning = "2023-11-14T06:00:00+00:00"
        
        lab_request = {
            "resourceType": "ServiceRequest",
            "status": "active",
            "intent": "order",
            "priority": "stat",
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": SERUM_K_LOINC,
                    "display": "Potassium [Moles/volume] in Serum or Plasma"
                }]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "authoredOn": CURRENT_TIME,
            "occurrenceDateTime": next_morning
        }
        
        lab_result = await fhir_post("ServiceRequest", lab_request)
        
        if not lab_result or "error" in lab_result:
            return with_reminder({
                "status": "lab_order_failed",
                "k_value": k_value,
                "medication_ordered": True,
                "dose": f"{dose} mEq",
                "error": lab_result,
                "answer": "[]"
            })
        
        return with_reminder({
            "status": "orders_created",
            "k_value": k_value,
            "dose": f"{dose} mEq oral",
            "medication_order_id": med_result.get("id"),
            "lab_order_id": lab_result.get("id"),
            "follow_up": next_morning,
            "message": f"Ordered {dose} mEq oral K for hypokalemia ({k_value} mEq/L) + recheck tomorrow AM",
            "answer": "[]"
        })
    
    
    # ============ Task 10: A1C 檢查 + 必要時開單 ============
    
    @mcp.tool()
    async def check_hba1c_and_order_if_needed(patient_id: str) -> str:
        """Check HbA1C status and order if needed (Task 10).
        
        This is a composite tool that:
        1. Gets all A1C results
        2. Checks if the most recent one is within the past year
        3. If expired or missing, orders a new A1C
        4. Returns the latest value or -1 if none available
        
        Args:
            patient_id: Patient FHIR ID
        
        Returns:
            Latest A1C value and action taken
        """
        # Step 1: 查詢 A1C
        a1c_data = await fhir_get("Observation", {
            "patient": patient_id,
            "code": "A1C",
            "_count": "100"
        })
        
        if not a1c_data or "error" in a1c_data:
            # 沒有結果，開新單
            lab_request = {
                "resourceType": "ServiceRequest",
                "status": "active",
                "intent": "order",
                "priority": "stat",
                "code": {
                    "coding": [{
                        "system": "http://loinc.org",
                        "code": HBA1C_LOINC,
                        "display": "Hemoglobin A1c/Hemoglobin.total in Blood"
                    }]
                },
                "subject": {"reference": f"Patient/{patient_id}"},
                "authoredOn": CURRENT_TIME
            }
            await fhir_post("ServiceRequest", lab_request)
            
            return with_reminder({
                "status": "no_prior_a1c",
                "action": "ordered_new",
                "message": "No prior A1C found. Ordered new A1C test.",
                "answer": "[-1]"
            })
        
        # Step 2: 找最新 A1C
        entries = a1c_data.get("entry", [])
        if not entries:
            # 沒有結果，開新單
            lab_request = {
                "resourceType": "ServiceRequest",
                "status": "active",
                "intent": "order",
                "priority": "stat",
                "code": {
                    "coding": [{
                        "system": "http://loinc.org",
                        "code": HBA1C_LOINC,
                        "display": "Hemoglobin A1c/Hemoglobin.total in Blood"
                    }]
                },
                "subject": {"reference": f"Patient/{patient_id}"},
                "authoredOn": CURRENT_TIME
            }
            await fhir_post("ServiceRequest", lab_request)
            
            return with_reminder({
                "status": "no_a1c_entries",
                "action": "ordered_new",
                "message": "No A1C entries found. Ordered new A1C test.",
                "answer": "[-1]"
            })
        
        # 找最新的
        latest_entry = None
        latest_time = None
        for e in entries:
            obs = e.get("resource", {})
            effective = obs.get("effectiveDateTime", "")
            if not latest_time or effective > latest_time:
                latest_time = effective
                latest_entry = obs
        
        if not latest_entry or not latest_time:
            return with_reminder({
                "status": "no_valid_a1c",
                "action": "none",
                "answer": "[-1]"
            })
        
        # Step 3: 檢查是否過期 (超過一年)
        is_expired = latest_time < ONE_YEAR_AGO
        
        value_quantity = latest_entry.get("valueQuantity", {})
        a1c_value = value_quantity.get("value")
        
        if is_expired:
            # 過期，開新單
            lab_request = {
                "resourceType": "ServiceRequest",
                "status": "active",
                "intent": "order",
                "priority": "stat",
                "code": {
                    "coding": [{
                        "system": "http://loinc.org",
                        "code": HBA1C_LOINC,
                        "display": "Hemoglobin A1c/Hemoglobin.total in Blood"
                    }]
                },
                "subject": {"reference": f"Patient/{patient_id}"},
                "authoredOn": CURRENT_TIME
            }
            await fhir_post("ServiceRequest", lab_request)
            
            return with_reminder({
                "status": "expired",
                "last_a1c_date": latest_time,
                "last_a1c_value": a1c_value,
                "action": "ordered_new",
                "message": f"Last A1C ({a1c_value}%) on {latest_time} is over 1 year old. Ordered new test.",
                "answer": f"[{a1c_value}]" if a1c_value else "[-1]"
            })
        
        # 還在有效期內
        return with_reminder({
            "status": "current",
            "a1c_value": a1c_value,
            "a1c_date": latest_time,
            "action": "none",
            "message": f"Current A1C: {a1c_value}% from {latest_time}. Within 1 year, no new order needed.",
            "answer": f"[{a1c_value}]" if a1c_value else "[-1]"
        })
    
    
    # ============ Task 6: 計算平均血糖 ============
    
    @mcp.tool()
    async def calculate_average_cbg(patient_id: str) -> str:
        """Calculate average CBG (glucose) over the past 24 hours (Task 6).
        
        This tool:
        1. Gets all glucose readings from past 24 hours
        2. Calculates the average
        3. Returns -1 if no readings available
        
        Args:
            patient_id: Patient FHIR ID
        
        Returns:
            Average CBG value or -1
        """
        # Query glucose
        glu_data = await fhir_get("Observation", {
            "patient": patient_id,
            "code": "GLU",
            "date": f"ge{TIME_24H_AGO}",
            "_count": "5000"
        })
        
        if not glu_data or "error" in glu_data:
            return with_reminder({
                "status": "error",
                "message": "Failed to query glucose",
                "answer": "[-1]"
            })
        
        entries = glu_data.get("entry", [])
        if not entries:
            return with_reminder({
                "status": "no_data",
                "message": "No glucose readings in past 24 hours",
                "answer": "[-1]"
            })
        
        # 收集數值
        values = []
        for e in entries:
            obs = e.get("resource", {})
            vq = obs.get("valueQuantity", {})
            v = vq.get("value")
            if v is not None:
                values.append(float(v))
        
        if not values:
            return with_reminder({
                "status": "no_values",
                "message": "No valid glucose values found",
                "answer": "[-1]"
            })
        
        # 計算平均 (四捨五入到整數)
        avg = round(sum(values) / len(values))
        
        return with_reminder({
            "status": "success",
            "readings_count": len(values),
            "values": values,
            "average": avg,
            "message": f"Average CBG: {avg} mg/dL (from {len(values)} readings)",
            "answer": f"[{avg}]"
        })
    
    
    # ============ Task 4: 查詢最新 Mg (24h 內) ============
    
    @mcp.tool()
    async def get_latest_magnesium_24h(patient_id: str) -> str:
        """Get the latest magnesium level from the past 24 hours (Task 4).
        
        Args:
            patient_id: Patient FHIR ID
        
        Returns:
            Latest Mg value or -1 if none
        """
        mg_data = await fhir_get("Observation", {
            "patient": patient_id,
            "code": "MG",
            "date": f"ge{TIME_24H_AGO}",
            "_count": "100"
        })
        
        if not mg_data or "error" in mg_data:
            return with_reminder({
                "status": "error",
                "message": "Failed to query magnesium",
                "answer": "[-1]"
            })
        
        entries = mg_data.get("entry", [])
        if not entries:
            return with_reminder({
                "status": "no_data",
                "message": "No Mg readings in past 24 hours",
                "answer": "[-1]"
            })
        
        # 找最新
        latest_entry = None
        latest_time = None
        for e in entries:
            obs = e.get("resource", {})
            effective = obs.get("effectiveDateTime", "")
            if not latest_time or effective > latest_time:
                latest_time = effective
                latest_entry = obs
        
        if not latest_entry:
            return with_reminder({
                "status": "no_valid_data",
                "answer": "[-1]"
            })
        
        vq = latest_entry.get("valueQuantity", {})
        mg_value = vq.get("value")
        
        if mg_value is None:
            return with_reminder({
                "status": "no_value",
                "answer": "[-1]"
            })
        
        return with_reminder({
            "status": "success",
            "mg_value": mg_value,
            "datetime": latest_time,
            "message": f"Latest Mg: {mg_value} mg/dL at {latest_time}",
            "answer": f"[{mg_value}]"
        })
