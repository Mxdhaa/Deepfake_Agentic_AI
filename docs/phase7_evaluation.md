# Phase 7 — Comprehensive Pipeline Evaluation & Benchmarking Report

This report presents the empirical evaluation of the **Deepfake Agentic AI** multi-stage onboarding security pipeline, evaluated across all **60 synthetic onboarding records** (28 Pass, 15 Borderline, 17 Fail).

---

## 1. Executive Summary & Pitch Slide Highlights

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   CORE BENCHMARKS SUMMARY (N=60)                         │
├─────────────────────────────────────────┬────────────────────────────────┤
│ Detection Recall on Injected Bad Cases  │ 100.0% (17/17 caught)          │
│ False-Escalation Rate (Legitimate Pass) │ 0.0% (0/28 falsely escalated)  │
│ Stage 3 Autonomous Resolution Rate      │ 13.3% (resolved without human) │
│ Overall Multi-Stage Decision Accuracy   │ 100.0%                         │
│ Mean End-to-End Latency                 │ 43.67 ms (p95 = 64.04 ms)      │
│ Cryptographic Audit Chain Verification  │ PASSED (277 blocks verified)   │
└─────────────────────────────────────────┴────────────────────────────────┘
```

---

## 2. Evaluation Methodology & Security Invariants

The evaluation was executed using `scripts/evaluate_pipeline.py` in **End-to-End (`e2e`) Mode**:

1. **Wire-Byte Archival Before Scoring**:
   - For every transaction, an in-memory MP4 video buffer is synthesized and hashed immediately upon receipt (`video_sha256 = compute_sha256(clip_bytes)`).
   - Stored in object storage (`storage.write()`) and recorded in the append-only cryptographic hash chain (`log_upload_event()`) before any downstream scoring runs.
2. **Stage 1 (Liveness & Deepfake Anomaly)**:
   - Evaluates frame deepfake score, blink rate, and audio-video sync offset drift.
   - Seals `decision` record into `audit_chain.jsonl`.
3. **Stage 2 (Identity Cosine Similarity & Velocity)**:
   - Evaluates face embedding similarity and 6-hour registry velocity.
4. **Precedence Orchestration**:
   - **Hard Reject**: If Stage 1 == `fail` or Stage 2 == `fail`, the transaction is immediately rejected without wasting agent compute.
   - **Fast Pass**: If Stage 1 == `pass` and Stage 2 == `pass`, the transaction is immediately approved in sub-millisecond residual time.
   - **Borderline Escalation**: If Stage 1 == `borderline` or Stage 2 == `borderline`, the case is escalated to the **Stage 3 LangGraph Autonomous Investigation Agent**.
5. **Stage 3 Autonomous Agent Investigation**:
   - The agent queries 2 live tools:
     - `check_device_id_history(device_id)`
     - `query_registry_velocity(kin_token)`
   - Records raw tool arguments, return values, and execution durations faithfully.
   - Uses local deterministic heuristic dossier synthesis by default (with optional `--use-llm` for OpenAI `gpt-4o-mini`), avoiding API rate limits or unexpected quota exhaustion while preserving real tool execution.
   - Seals `investigation` event into `audit_chain.jsonl`.
   - If resolved, issues autonomous approval/rejection.
   - If unresolved (`REFER_TO_HUMAN`), enqueues case into **Stage 4 Human Review Queue** (`review_queue.jsonl`).

---

## 3. Detailed Results & Metric Tables

### A. Core Performance Metrics

| Metric | Measured Value | Benchmark Target | Definition / Impact |
| :--- | :---: | :---: | :--- |
| **Detection Recall (Bad Cases)** | **100.0%** | $\ge 98.0\%$ | Percentage of ground-truth `fail` cases prevented from fast approval (17/17 caught). Zero fraud bypasses. |
| **False-Escalation Rate (Pass)** | **0.0%** | $\le 5.0\%$ | Percentage of clean, legitimate applicants wrongly routed to Stage 3 or 4 (0/28). Frictionless onboarding. |
| **Stage 3 Autonomous Resolution**| **13.3%** | $\ge 10.0\%$ | Percentage of ambiguous borderline cases resolved autonomously by the agent without human review intervention (2/15). |
| **Overall Classification Accuracy**| **100.0%** | $\ge 95.0\%$ | Exact multi-stage alignment between ground truth and pipeline verdict. |

---

### B. 4-Stage Pipeline Funnel Breakdown

```
Total Ingested Sessions: 60 (100.0%)
 ├── Fast Pass (Approved at Stage 1/2)   : 28 (46.7%)  ──▶ Fast Onboarding
 ├── Hard Reject (Rejected at Stage 1/2) : 17 (28.3%)  ──▶ Immediate Fraud Block
 └── Escalated to Stage 3 Agent          : 15 (25.0%)
      ├── Autonomous Agent Resolved      :  2  (3.3%)  ──▶ Autonomous Pass/Fail
      └── Stage 4 Human Review Escalated : 13 (21.7%)  ──▶ High-Confidence Audit Queue
```

---

### C. 3×4 Decision Confusion Matrix

| Ground Truth Label (Count) | Fast Pass (Stage 1/2) | Hard Reject (Stage 1/2) | Stage 3 Agent Resolved | Stage 4 Human Escalated | Total Rows |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Pass** (28) | **28** | 0 | 0 | 0 | **28** |
| **Borderline** (15) | 0 | 0 | **2** | **13** | **15** |
| **Fail** (17) | 0 | **17** | 0 | 0 | **17** |
| **Total Columns** | **28** | **17** | **2** | **13** | **60** |

---

### D. Per-Stage Latency Profiling (ms)

| Pipeline Stage | Mean (ms) | Median (ms) | p95 (ms) | Min (ms) | Max (ms) | Operations Measured |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Stage 1 (Liveness & Archival)** | 39.47 | 37.83 | 50.14 | 21.71 | 153.17 | In-memory video synthesis, SHA-256 wire hashing, `storage.write()`, and audit upload/decision sealing. |
| **Stage 2 (Identity & Velocity)** | 0.01 | 0.01 | 0.01 | 0.00 | 0.05 | In-memory cosine embedding thresholding and velocity windowing. |
| **Stage 3 (Autonomous Agent)** | 15.71 | 14.28 | 29.62 | 8.35 | 34.12 | Tool inquiries (`check_device_id_history`, `query_registry_velocity`), dossier synthesis, and investigation audit sealing. |
| **Stage 4 (Review Queue Sealing)**| 0.00 | 0.00 | 0.00 | 0.00 | 0.01 | File append and JSONL record persistence. |
| **Total End-to-End Latency** | **43.67** | **41.22** | **64.04** | **24.18** | **156.40** | Complete client transaction time from ingestion to final verdict. |

---

## 4. Summary Chart Artifact

The high-resolution pitch slide summary chart has been generated and saved to:
`docs/phase7_evaluation_report.png`

It contains the 4 coordinated visual panels:
1. **Pipeline Funnel (N=60)**: Visual bar breakdown of Fast Pass, Hard Reject, Agent Resolved, and Human Escalation.
2. **Key Security & Pitch Metrics**: Styled metric cards displaying Recall (100%), False Escalation (0.0%), and Autonomous Resolution (13.3%).
3. **Latency Benchmarks**: Mean vs p95 comparative bar chart across all active stages.
4. **3×4 Confusion Matrix Heatmap**: Annotated ground truth vs outcome mapping.

---

## 5. Verification Command

To re-run the complete evaluation pipeline and refresh the chart and JSON outputs:
```bash
python scripts/evaluate_pipeline.py --mode e2e --chart docs/phase7_evaluation_report.png --output docs/evaluation_results.json
```
