#!/usr/bin/env python3
"""
測試 MCP Server 是否正常運作
"""

import asyncio
import json
from mcp_server import fhir_get, fhir_post, FHIR_API_BASE


async def test_connection():
    """測試 FHIR 伺服器連線"""
    print(f"Testing connection to FHIR server: {FHIR_API_BASE}")
    
    # 測試搜尋病患
    result = await fhir_get("Patient", {"name": "Peter Stafford", "birthdate": "1932-12-29"})
    
    if result["success"]:
        print("✅ Connection successful!")
        if result["data"].get("entry"):
            patient = result["data"]["entry"][0]["resource"]
            print(f"  Found patient: {patient.get('id')}")
            print(f"  Name: {patient.get('name')}")
            print(f"  Birth Date: {patient.get('birthDate')}")
            
            # 提取 MRN
            identifiers = patient.get("identifier", [])
            for ident in identifiers:
                if ident.get("type", {}).get("text") == "MRN":
                    print(f"  MRN: {ident.get('value')}")
        else:
            print("  No patients found")
    else:
        print(f"❌ Connection failed: {result['error']}")
        print("\n請確保 FHIR 伺服器正在運行：")
        print("  docker run -p 8080:8080 jyxsu6/medagentbench:latest")


async def test_observation_query():
    """測試查詢觀察值"""
    print("\nTesting observation query...")
    
    # 先找一個病患
    patient_result = await fhir_get("Patient", {"identifier": "S6534835"})
    
    if patient_result["success"] and patient_result["data"].get("entry"):
        patient_id = patient_result["data"]["entry"][0]["resource"]["id"]
        print(f"  Patient FHIR ID: {patient_id}")
        
        # 查詢觀察值
        obs_result = await fhir_get("Observation", {
            "patient": patient_id,
            "code": "MG"  # 鎂離子
        })
        
        if obs_result["success"]:
            entries = obs_result["data"].get("entry", [])
            print(f"  Found {len(entries)} magnesium observations")
        else:
            print(f"  ❌ Observation query failed: {obs_result['error']}")
    else:
        print("  ❌ Patient not found")


async def main():
    print("=" * 50)
    print("MedAgent MCP Server Test")
    print("=" * 50)
    
    await test_connection()
    await test_observation_query()
    
    print("\n" + "=" * 50)
    print("Test completed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
