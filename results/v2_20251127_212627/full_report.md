# MedAgentBench Evaluation Report

**Generated:** 2025-11-28 09:39:28
**Run ID:** v2_20251127_212627
**Version:** v2

## Overall Results

| Metric | Value |
|--------|-------|
| **Overall Accuracy** | **98.30%** |
| Correct | 295 |
| Total | 300 |

## Results by Difficulty Level

| Difficulty | Correct | Total | Accuracy |
|------------|---------|-------|----------|
| Easy | 150 | 150 | 100.00% |
| Medium | 89 | 90 | 98.89% |
| Hard | 56 | 60 | 93.33% |

### Difficulty Classification

| Level | Tasks |
|-------|-------|
| Easy | Task 1 (Patient Search), Task 2 (Age), Task 4 (Query Mg), Task 7 (CBG) |
| Medium | Task 3 (Record BP), Task 6 (Avg Glucose), Task 8 (Referral) |
| Hard | Task 5 (Mg Replacement), Task 9 (K Replacement), Task 10 (HbA1C Check) |

## Results by Task Type

| Task | Name | Correct | Total | Accuracy |
|------|------|---------|-------|----------|
| task1 | Patient Search | 30 | 30 | 100.00% |
| task2 | Age Calculation | 30 | 30 | 100.00% |
| task3 | Record BP | 30 | 30 | 100.00% |
| task4 | Query Magnesium | 30 | 30 | 100.00% |
| task5 | Mg Replacement | 30 | 30 | 100.00% |
| task6 | Avg Glucose | 30 | 30 | 100.00% |
| task7 | Latest CBG | 29 | 30 | 96.67% |
| task8 | Ortho Referral | 30 | 30 | 100.00% |
| task9 | K Replacement | 30 | 30 | 100.00% |
| task10 | HbA1C Check | 26 | 30 | 86.67% |

## Memory System Usage

| Metric | Value |
|--------|-------|
| **Memory Usage Rate** | **0.0%** |
| Tasks with Memory Access | 0 |
| Total Tasks | 0 |

### Access Breakdown

| Type | Count |
|------|-------|
| Patient Memory Reads | 0 |
| Patient Memory Writes | 0 |
| Knowledge Reads | 0 |
| Constitution Reads | 0 |
| MCP Resource Reads | 0 |


### ⚠️ Observation

**No memory access was recorded!** The agent did not utilize the memory system during this evaluation run.

Possible reasons:
1. VS Code Copilot does not automatically access MCP Resources
2. Agent did not call `add_patient_note()` to save observations
3. Memory tracking was not properly initialized

