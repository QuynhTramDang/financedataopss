# Project Document v4
# **Impact-Aware Finance DataOps Twin**

> **Changelog v3 → v4**
> Bản v4 giữ nguyên toàn bộ tầm nhìn kiến trúc của v3, chỉ **bổ sung và làm chặt** để tài liệu đủ
> khả thi cho một internal product thật. Các thay đổi chính:
> - Thêm **§0 Naming clarification** (làm rõ "Twin").
> - Làm chặt **§14.2 Claim-level Verification** với claim schema và ranh giới LLM / rule engine.
> - Thêm ghi chú **pluggable model routing** ở §6 và §23 (Phase 1 chỉ wire thật 1–2 model).
> - Thêm yêu cầu **reconciliation tính từ data thật** ở §13, §17, §28.
> - Thêm **§20A Build Order / Vertical Slice Plan**.
> - Đánh dấu tool **real vs stub ở Phase 1** trong §15.
> - Thêm **negative case** ở §11 và §14.9.
> - Bổ sung **LLM Reliability / Structured Output** ở §26.
> - Thêm 3 risk mới ở §31.

---

## 0. Naming clarification (mới ở v4)

Tên "Twin" trong dự án này **không** mang nghĩa digital twin theo kiểu mô phỏng song song trạng thái
một hệ thống vật lý. Ở đây "Twin" được hiểu là **operational twin của quy trình điều tra của Data
Engineer**: hệ thống tái hiện và tự động hoá đúng các bước mà một DE giỏi sẽ làm khi Finance báo lệch
số (tìm metric → check data → đọc code → tìm root cause → fix → validate → viết RCA → xin approval),
nhưng có thêm governance, verification và memory.

Nếu reviewer hỏi *"twin của cái gì?"*, câu trả lời chuẩn:
> Twin của **investigation workflow** của Data Engineer cho Finance — không phải twin của database.

Tên thay thế có thể cân nhắc nếu muốn tránh hiểu nhầm:
- **Finance DataOps Control Plane**
- **Finance Data Investigation Copilot**

Tài liệu này vẫn dùng tên gốc "Impact-Aware Finance DataOps Twin".

---

## 1. Tổng quan dự án
### 1.1 Tên dự án
**Impact-Aware Finance DataOps Twin**
### 1.2 Subtitle
**LangGraph-based Agentic Workflow for Safe, Verified and Impact-Aware Finance Data Pipeline Automation**
### 1.3 One-liner
**Impact-Aware Finance DataOps Twin là một hệ thống AI Agent Workflow giúp Data Engineer tự động điều tra lỗi dữ liệu Finance, hiểu ngữ cảnh vận hành, biết chọn tool phù hợp, tối ưu token khi xử lý data, sinh code patch an toàn, chạy validation, kiểm chứng từng claim bằng evidence và tạo RCA report trước khi chờ human approval.**
### 1.4 Định vị sản phẩm
Sản phẩm không phải là chatbot hỏi đáp dữ liệu.
Sản phẩm là một **LangGraph-based DataOps Control Plane** cho Data Engineer, có khả năng điều phối workflow vận hành dữ liệu theo flow rõ ràng:

```text
State → Model → Tools → Routing → Verification → Validation → Human Approval
```

Thay vì để AI Agent tự do suy luận và gọi tool, hệ thống được thiết kế như một workflow có kiểm soát:

```text
Finance báo lệch số
→ LangGraph khởi tạo state
→ Agent phân loại intent/risk
→ Agent retrieve memory/RAG
→ Tool Governance kiểm tra quyền
→ Diagnostic tools kiểm tra dữ liệu/code
→ Agent tạo hypothesis
→ Claim Verifier kiểm chứng từng claim
→ Agent sinh safe patch
→ Validation Engine chạy test
→ Trust Scorer đánh giá độ tin cậy
→ RCA report được tạo
→ Human approve trước khi apply
→ Memory write-back sau khi được xác nhận
```

Thông điệp chính:
> AI cho Data Engineering không nên chỉ generate SQL. Nó phải bảo vệ trust của dữ liệu.
---
## 2. Bối cảnh nghiệp vụ
Phòng Data Engineering chịu trách nhiệm xử lý và cung cấp dữ liệu cho Finance. Các báo cáo Finance cần độ chính xác cao, có trace rõ ràng, đúng SLA và có quy trình approval khi thay đổi business logic.
Khi Finance phát hiện số liệu lệch, Data Engineer thường phải làm thủ công nhiều bước:

```text
1. Tìm lại định nghĩa metric.
2. Tìm bảng nguồn liên quan.
3. Kiểm tra schema, partition, freshness.
4. Viết SQL debug.
5. Đọc pipeline code cũ.
6. Tìm nguyên nhân lệch số.
7. Sửa SQL/dbt/PySpark logic.
8. Chạy data quality test.
9. Viết RCA report cho Finance.
10. Xin approval trước khi publish lại số.
```

Quy trình này tốn thời gian, dễ thiếu context, dễ quên test, dễ sai khi business rule thay đổi và khó chuẩn hóa giữa các Data Engineer.
---
## 3. Problem Statement
### 3.1 Vấn đề chính
Các pipeline dữ liệu Finance thường gặp lỗi do:

```text
- Schema evolution từ upstream.
- Enum value mới xuất hiện.
- Business logic thay đổi nhưng pipeline chưa update.
- Late-arriving data.
- Missing partition.
- Duplicate transaction.
- Null value bất thường.
- Mapping logic sai.
- Metric definition không thống nhất giữa Data và Finance.
- Deployment gần đây làm thay đổi logic.
- Data contract không được cập nhật kịp thời.
```

Các lỗi này thường chỉ được phát hiện sau khi Finance báo số liệu lệch.
### 3.2 Pain point của Data Engineer

```text
- Phải tìm metric definition thủ công.
- Phải tự nhớ pipeline lineage.
- Phải viết lại SQL debug lặp đi lặp lại.
- Phải check schema drift, freshness, null, duplicate.
- Phải đọc code transformation cũ.
- Phải tự sửa logic và chạy test.
- Phải viết RCA report cho Finance.
- Phải đảm bảo không deploy sai logic Finance.
- Phải xác minh liệu root cause có thật hay chỉ là suy đoán.
```

### 3.3 Pain point của Finance
Finance cần câu trả lời rõ ràng:

```text
- Vì sao số liệu lệch?
- Lệch bao nhiêu?
- Report nào bị ảnh hưởng?
- Dữ liệu có đáng tin không?
- Fix có làm thay đổi số không?
- Ai cần approve?
- Có bằng chứng validation không?
- Kết luận của AI có được kiểm chứng không?
```

---
## 4. Product Vision
**Impact-Aware Finance DataOps Twin** giúp Data Engineer tự động hóa quy trình điều tra và xử lý lỗi dữ liệu Finance, nhưng vẫn đảm bảo an toàn, có kiểm chứng, có bằng chứng và có con người phê duyệt.
Triết lý sản phẩm:
> Trong Finance DataOps, tự động hóa không khó nhất. Khó nhất là tự động hóa mà vẫn kiểm soát được rủi ro.
Sản phẩm tập trung vào 8 năng lực cốt lõi:

```text
1. LangGraph Control Plane
   Điều phối workflow bằng state, node, routing, condition và human approval.
2. Model Routing
   Không dùng một model cho tất cả. Mỗi node dùng model phù hợp với cost, latency và độ rủi ro.
3. Decision Memory
   Ghi nhớ metric, pipeline, incident, business decision và approval rule.
4. Decision-Aware RAG
   Retrieve đúng ngữ cảnh nghiệp vụ, runbook, data contract và incident cũ.
5. Tool Governance
   Biết khi nào dùng tool nào, khi nào không được dùng tool và khi nào cần human approval.
6. Context Compression
   Không đưa raw data vào LLM; dùng metadata, aggregate, profile và anomaly summary.
7. Trust, Evaluation & Verification
   Không tin answer nếu không có evidence. Mọi claim quan trọng phải được xác minh.
8. Safe Patch + Evidence Pack
   Sinh patch nhỏ, chạy validation, tạo RCA report và chờ approval.
```

---
## 5. Vì sao cần LangGraph?
Dự án này không nên triển khai như một agent đơn giản:

```text
User → LLM → Tool → LLM → Answer
```

Vì workflow Data Engineering cho Finance cần nhiều bước có trạng thái, rẽ nhánh và kiểm soát rủi ro:

```text
- Có task state.
- Có memory retrieval.
- Có tool routing.
- Có policy check.
- Có claim verification.
- Có validation.
- Có conditional branch.
- Có human approval.
- Có memory write-back sau khi incident được xác nhận.
```

Do đó, kiến trúc nên dùng **LangGraph** làm control plane.
### 5.1 LangGraph Workflow

```text
[User Request]
     |
     v
[State Initialization]
     |
     v
[Intent & Risk Classifier]
     |
     v
[Memory + RAG Retrieval]
     |
     v
[Known vs Unknown Issue Router]
     |
     v
[Tool Governance Router]
     |
     +--> Block unsafe tool call
     |
     +--> Allow safe diagnostic tools
     |
     v
[Diagnostic Tools]
     |
     v
[Root Cause Reasoner]
     |
     v
[Claim Verifier]
     |
     v
[Safe Patch Generator]
     |
     v
[Patch Reviewer]
     |
     v
[Validation Engine]
     |
     v
[Trust Scorer]
     |
     v
[RCA Report Generator]
     |
     v
[Human Approval Node]
     |
     v
[Memory Write-back Node]
```

### 5.2 LangGraph State

```json
{
  "investigation_id": "INV-001",
  "user_request": "Revenue report 2026-06-07 lệch 2.1%",
  "metric": "net_revenue",
  "date": "2026-06-07",
  "intent": "investigate_revenue_mismatch",
  "risk_level": "high",
  "retrieved_context": [],
  "tool_plan": [],
  "tool_results_summary": {},
  "root_cause": null,
  "hypotheses": [],
  "claims": [],
  "claim_verification_result": {},
  "impact_analysis": {},
  "patch": null,
  "validation_result": null,
  "trust_matrix": {},
  "rca_report": null,
  "approval_status": "pending",
  "memory_writeback_status": "not_started"
}
```

---
## 6. Model Routing Strategy
### 6.1 Nguyên tắc
Hệ thống không dùng một model cho tất cả nhiệm vụ.
Thay vào đó, hệ thống dùng **task-aware model routing**:

```text
- Model mạnh chỉ dùng cho reasoning phức tạp và risk cao.
- Model code dùng cho SQL/code/patch.
- Model rẻ/local dùng cho classifier, summarizer, guardrail.
- Long-context model dùng để đọc docs/log/codebase dài.
- Policy, verification và validation quan trọng phải dùng deterministic tools, không giao hết cho LLM.
```

Câu chốt:
> Model mạnh không nên xử lý mọi việc. Model mạnh chỉ nên xử lý những điểm cần reasoning thật sự. Những phần còn lại phải để tool, rule engine, cache và model nhỏ xử lý.

> **Ghi chú thực thi (v4) — Pluggable routing, Phase 1 chỉ wire thật 1–2 model.**
> Model router được **thiết kế** cho cả 4 nhóm model (Claude / Qwen Coder / MiniMax / Gemma) để
> chứng minh kiến trúc task-aware routing. Nhưng **ở Phase 1 chỉ cần wire thật 1–2 model**: Claude
> cho reasoning/planning/patch-review/RCA, cộng tối đa một model nhỏ cho classify. Các slot model
> còn lại để **config-stub** (router trỏ tạm về model đã wire). Lý do: tích hợp đồng thời 4 provider
> (4 SDK, 4 kiểu auth, 4 failure mode) tốn thời gian và dễ vỡ lúc demo/vận hành, trong khi giá trị
> "routing" đã thể hiện đủ qua config + ranh giới rõ ràng giữa các node.
>
> **Fallback strategy:** mỗi route phải có model fallback. Nếu provider chính lỗi/timeout, router
> chuyển sang model đã-wire khác cùng cấp năng lực (hoặc Claude) và **log sự kiện fallback**. Không
> được để một provider lỗi làm hỏng cả investigation.
---
### 6.2 Model Mapping
| Module                                | Model đề xuất               | Lý do                                           | Phase 1 |
| ------------------------------------- | --------------------------- | ----------------------------------------------- | ------- |
| Intent & Risk Classifier              | Gemma hoặc Qwen nhỏ         | Task đơn giản, cần nhanh và rẻ                  | wire thật (hoặc Claude nếu chưa có model nhỏ) |
| Query Rewrite cho Memory/RAG          | Qwen hoặc Gemma             | Rewrite query, extract keyword, route context   | stub → Claude |
| Main Planner / Orchestrator Reasoning | Claude                      | Cần reasoning tốt, xử lý context phức tạp       | wire thật |
| SQL Generation                        | Qwen Coder                  | Phù hợp cho SQL/code generation                 | stub → Claude |
| Code Search Understanding             | Qwen Coder hoặc MiniMax     | Hiểu codebase, đọc code dài                     | stub → Claude |
| Long-context Docs/Logs Analyzer       | MiniMax                     | Phù hợp khi cần đọc context dài                 | stub → Claude |
| Root Cause Reasoner                   | Claude                      | Suy luận nguyên nhân từ nhiều evidence          | wire thật |
| Claim Verifier                        | Rule engine + Claude review | Tách claim, map evidence, phát hiện overclaim   | wire thật (rule engine bắt buộc thật) |
| Safe Patch Generator                  | Qwen Coder                  | Sinh patch SQL/dbt nhanh và chính xác           | stub → Claude |
| Patch Reviewer                        | Claude                      | Review business risk, logic Finance và approval | wire thật |
| RCA Report Generator                  | Claude                      | Viết báo cáo rõ cho cả DE và Finance            | wire thật |
| Guardrail / PII Masking / Summarizer  | Gemma                       | Task nhỏ, có thể chạy local/rẻ                  | stub |
| Tool Governance                       | Python Rule Engine          | Không giao policy quan trọng cho LLM            | wire thật |
| Validation Engine                     | Deterministic Test Runner   | Không dùng LLM để quyết định pass/fail          | wire thật |
---
### 6.3 Model Roles

```text
Claude
= main reasoning, planning, root cause reasoning, patch review, RCA, Finance explanation.
Qwen Coder
= SQL generation, dbt patch, code understanding, test generation.
MiniMax
= long-context analyzer, large docs/logs/codebase summarization, fallback planner.
Gemma
= cheap/local classifier, summarizer, PII guardrail, memory extraction draft.
Python Rules
= SQL policy, tool governance, claim checks, validation, approval control.
```

Cách nói ngắn gọn:

```text
Claude = brain
Qwen = coding hands
MiniMax = long-context reader
Gemma = cheap/local utility model
LangGraph = control plane
Python tools = source of truth
```

---
## 7. Kiến trúc tổng thể

```text
[Streamlit UI]
     |
     v
[LangGraph Orchestrator]
     |
     +--> [State Store]
     |       - current task state
     |       - tool results summary
     |       - claim verification state
     |       - approval state
     |
     +--> [Model Router]
     |       - classifier_model: Gemma/Qwen
     |       - planner_model: Claude
     |       - code_model: Qwen Coder
     |       - long_context_model: MiniMax
     |       - report_model: Claude
     |
     +--> [Short-term Memory]
     |       - current investigation state
     |       - intermediate findings
     |       - selected tools
     |
     +--> [Long-term Structured Memory]
     |       - user memory
     |       - metric memory
     |       - pipeline memory
     |       - incident memory
     |       - decision/policy memory
     |
     +--> [Decision-Aware RAG]
     |       - metric dictionary
     |       - data contracts
     |       - runbooks
     |       - previous incidents
     |       - pipeline docs
     |
     +--> [Tool Governance Engine]
     |       - allow/block tool
     |       - enforce partition filter
     |       - mask sensitive data
     |       - require approval
     |
     +--> [Data Context Compression Engine]
     |       - metadata-first
     |       - SQL aggregate
     |       - anomaly summary
     |       - cached profile
     |
     +--> [Diagnostic Tool Layer]
     |       - metadata_scan
     |       - schema_diff
     |       - sql_profile
     |       - freshness_check
     |       - volume_check
     |       - null_check
     |       - duplicate_check
     |       - distribution_drift_check
     |       - lineage_lookup
     |       - code_search
     |       - deployment_log_search
     |
     +--> [Trust, Evaluation & Verification Layer]
     |       - claim_verifier
     |       - evidence_mapper
     |       - contradiction_checker
     |       - trust_scorer
     |       - golden_set_evaluator
     |
     +--> [Safe Patch & Validation Layer]
     |       - generate_patch
     |       - review_patch
     |       - run_validation
     |       - impact_simulation
     |       - generate_rca_report
     |
     v
[Evidence Pack + RCA Report]
     |
     v
[Human Approval]
```

---
## 8. Memory Architecture
Memory không được nhét toàn bộ vào prompt. Memory phải là một store có cấu trúc, chỉ retrieve phần cần thiết cho từng task.
Mục tiêu:

```text
Store nhiều, retrieve ít.
Memory lớn, prompt nhỏ.
```

---
### 8.1 Short-term Memory
Short-term memory lưu trạng thái của task hiện tại.
Ví dụ:

```json
{
  "investigation_id": "INV-001",
  "task": "investigate_revenue_mismatch",
  "current_step": "code_search_done",
  "selected_tools": [
    "memory_search",
    "rag_retrieve",
    "metadata_scan",
    "sql_profile",
    "code_search"
  ],
  "intermediate_findings": {
    "new_refund_status": "PARTIAL_REFUND",
    "target_file": "models/finance/revenue_daily.sql"
  }
}
```

Short-term memory dùng để:

```text
- Theo dõi agent đang ở bước nào.
- Lưu kết quả tóm tắt của tool.
- Quyết định next action.
- Tránh lặp lại tool call không cần thiết.
```

Không lưu raw data hoặc full log dài trong short-term memory.
---
### 8.2 Long-term Structured Memory
Long-term memory lưu kiến thức bền vững qua nhiều phiên.
Bao gồm:

```text
1. User Memory
2. Metric Memory
3. Pipeline Memory
4. Incident Memory
5. Decision / Policy Memory
6. Approved Runbook Memory
```

#### User Memory

```json
{
  "role": "Data Engineer",
  "team": "Data Platform for Finance",
  "preferred_stack": ["dbt", "PostgreSQL", "Airflow"],
  "coding_rules": [
    "avoid select *",
    "always filter by partition date",
    "never change finance metric without approval"
  ]
}
```

#### Metric Memory

```json
{
  "metric": "net_revenue",
  "definition": "paid_amount - refunded_amount",
  "owner": "Finance",
  "source_tables": ["payment_txn", "order_fact"],
  "sla": "daily 09:00"
}
```

#### Pipeline Memory

```json
{
  "pipeline": "revenue_daily",
  "repo_path": "models/finance/revenue_daily.sql",
  "upstream": ["payment_txn", "order_fact"],
  "downstream": ["finance_revenue_report"],
  "common_issues": [
    "schema drift",
    "late-arriving payment",
    "refund_status mapping"
  ]
}
```

#### Incident Memory

```json
{
  "incident_id": "INC-2026-0520",
  "issue": "Revenue mismatch caused by refund_status mapping",
  "root_cause": "New refund_status value was not handled",
  "fix": "Update refund mapping logic",
  "related_pipeline": "revenue_daily",
  "approved_by": "Data Owner"
}
```

#### Decision / Policy Memory

```json
{
  "decision_id": "FIN-REV-2026-001",
  "topic": "Revenue Definition",
  "decision": "Net revenue = paid_amount - refunded_amount",
  "approved_by": "Finance Manager",
  "effective_from": "2026-01-01",
  "approval_rule": "Any change to Finance metric logic requires Finance Owner approval"
}
```

---
### 8.3 Memory Write-back Rule
Agent không được tự ý ghi long-term memory từ suy đoán của nó.
Chỉ được ghi memory mới khi:

```text
- Root cause đã được validation.
- RCA đã được human approve.
- Patch hoặc decision đã được xác nhận.
```

Ví dụ sau khi incident được approve:

```json
{
  "incident_id": "INC-2026-0607",
  "issue": "Revenue mismatch caused by new refund_status PARTIAL_REFUND",
  "symptom": "net_revenue overstated by 2.1%",
  "root_cause": "pipeline revenue_daily.sql did not map PARTIAL_REFUND",
  "diagnostic_steps": [
    "sql_profile refund_status",
    "code_search revenue_daily.sql",
    "run revenue reconciliation"
  ],
  "fix": "include PARTIAL_REFUND in refund mapping",
  "approval_required": ["Finance Owner", "Data Owner"],
  "created_from": "human_approved_rca"
}
```

---
## 9. Runtime Context Pack
Runtime Context Pack là phần nhỏ được chọn ra để đưa vào LLM.
Ví dụ context pack cho request revenue mismatch:

```json
{
  "task": "investigate_revenue_mismatch",
  "metric_definition": "net_revenue = paid_amount - refunded_amount",
  "pipeline_lineage": "payment_txn -> stg_payment -> revenue_daily -> finance_report",
  "relevant_policy": "Finance metric change requires approval",
  "similar_incident": "refund_status mapping issue on 2026-05-20",
  "sql_profile_summary": {
    "new_value": "PARTIAL_REFUND",
    "affected_amount": 210000000
  },
  "code_snippet": "when refund_status = 'REFUNDED' then refunded_amount"
}
```

Nguyên tắc:

```text
- Không đưa toàn bộ memory vào prompt.
- Không đưa toàn bộ docs vào prompt.
- Không đưa toàn bộ code file vào prompt.
- Không đưa raw data vào prompt.
- Chỉ đưa context đủ để LLM reasoning.
```

---
## 10. Decision-Aware RAG
### 10.1 Mục tiêu
RAG không dùng để đọc raw data. RAG dùng để lấy ngữ cảnh nghiệp vụ và vận hành.
RAG trả lời câu hỏi:

```text
Metric này có nghĩa gì?
Business rule nào đã được approve?
Pipeline nào liên quan?
Incident nào từng xảy ra?
Runbook xử lý issue này là gì?
Data contract hiện tại yêu cầu gì?
```

### 10.2 RAG retrieve các loại tài liệu

```text
- Metric dictionary
- Finance business rules
- Data contracts
- Pipeline documentation
- Previous incident reports
- Runbooks
- Approved decisions
- Code documentation
```

### 10.3 Vai trò của RAG

```text
Tool trả lời: data hiện đang như thế nào?
RAG trả lời: data này có nghĩa gì, liên quan đến đâu, từng được quyết định ra sao?
```

Ví dụ retrieved context:

```text
Metric Definition:
net_revenue = paid_amount - refunded_amount
Finance Decision:
PARTIAL_REFUND should be included in refund amount from 2026-06-01.
Pipeline Lineage:
payment_txn -> stg_payment -> revenue_daily -> finance_report
Previous Incident:
Similar refund_status issue happened on 2026-05-20.
Runbook:
For revenue mismatch, check freshness, enum drift, reconciliation.
```

---
## 11. Unknown Issue Mode
### 11.1 Vì sao cần Unknown Issue Mode?
Memory chỉ giúp agent nhớ kinh nghiệm cũ. Nhưng trong production, sẽ có lỗi mới chưa từng xảy ra.
Vì vậy hệ thống không được phụ thuộc hoàn toàn vào memory.
Khi memory/RAG không tìm thấy incident tương tự, LangGraph chuyển sang **Unknown Issue Mode**.

```text
Memory found similar incident?
     |
     +-- Yes → Follow known runbook
     |
     +-- No  → Unknown Issue Mode
```

### 11.2 Unknown Issue Diagnostic Checklist
Unknown Issue Mode chạy checklist tổng quát:

```text
1. Freshness Check
   Data có load đúng giờ không?
2. Volume Drift Check
   Row count hôm nay có giảm/tăng bất thường không?
3. Schema Drift Check
   Có column mới, column mất, type đổi không?
4. Enum Drift Check
   Có value mới trong status/category không?
5. Null Spike Check
   Null rate có tăng không?
6. Duplicate Spike Check
   Duplicate transaction có tăng không?
7. Distribution Drift Check
   Distribution của amount/status/category có lệch không?
8. Reconciliation Check
   Source và target lệch ở layer nào?
9. Lineage Lookup
   Report này phụ thuộc pipeline nào?
10. Recent Deployment Check
   Có PR/deploy nào gần đây không?
11. Log Search
   Airflow/dbt task có warning/error không?
```

### 11.3 Hypothesis Generation
Sau khi chạy diagnostic tools, agent tạo danh sách giả thuyết:

```json
{
  "hypotheses": [
    {
      "root_cause": "late arriving payment data",
      "confidence": "medium",
      "evidence": [
        "freshness delay",
        "source count lower than usual"
      ]
    },
    {
      "root_cause": "new refund_status enum",
      "confidence": "high",
      "evidence": [
        "PARTIAL_REFUND found",
        "pipeline missing mapping"
      ]
    }
  ]
}
```

Nếu confidence thấp:

```text
- Không kết luận vội.
- Tạo evidence pack.
- Escalate cho human.
- Không sinh patch tự động.
```

### 11.4 Negative Case — Low-confidence Escalation (mới ở v4)
Một hệ thống điều tra đáng tin phải biết **nói "tôi chưa chắc"**. Đây là trường hợp test bắt buộc,
không phải ngoại lệ.

Ví dụ: Finance báo `gross_margin` ngày 2026-06-11 lệch 0.4%. Sau khi chạy full diagnostic checklist:

```json
{
  "investigation_id": "INV-009",
  "max_confidence_hypothesis": 0.35,
  "evidence_found": [
    "freshness OK",
    "volume normal",
    "no schema drift",
    "no new enum",
    "no recent deployment"
  ],
  "decision": "no_confident_root_cause",
  "action": "build_evidence_pack_and_escalate",
  "patch_generated": false
}
```

Hành vi bắt buộc khi không có hypothesis nào đạt ngưỡng confidence:

```text
- KHÔNG kết luận root cause.
- KHÔNG sinh patch.
- Tạo evidence pack tổng hợp những gì đã loại trừ.
- Đánh dấu trust thấp ở phần "code/data root cause".
- Escalate cho human DE với danh sách diagnostic đã chạy + kết quả.
```

Thông điệp:
> Memory giúp agent nhanh hơn với lỗi quen thuộc. Tool-based discovery giúp agent xử lý lỗi lạ.
> Và biết dừng lại khi không đủ evidence là tính năng, không phải thất bại.
---
## 12. Tool Governance Engine
### 12.1 Mục tiêu
Agent không được tự do gọi tool. Mọi tool call phải đi qua governance.
### 12.2 Tool Governance kiểm tra

```text
- Tool này có phù hợp với intent không?
- Query có partition filter không?
- Có nguy cơ full scan không?
- Có động tới PII/raw transaction không?
- Có thay đổi Finance metric logic không?
- Có cần human approval không?
- Có được phép deploy không?
```

### 12.3 Ví dụ SQL Policy
Không cho phép query:

```sql
select *
from payment_txn;
```

Phải chuyển thành aggregate có partition filter:

```sql
select
  refund_status,
  count(*) as txn_count,
  sum(amount) as total_amount
from payment_txn
where txn_date = '2026-06-07'
group by refund_status;
```

### 12.4 Ví dụ policy output

```json
{
  "tool": "run_sql",
  "decision": "blocked",
  "reason": "Query scans payment_txn without txn_date filter",
  "suggestion": "Add txn_date filter before execution"
}
```

### 12.5 Risk Level
| Risk Level | Ví dụ                 | Agent được làm                    |
| ---------- | --------------------- | --------------------------------- |
| Low        | Hỏi định nghĩa metric | Trả lời trực tiếp                 |
| Medium     | Sinh SQL profiling    | Generate SQL read-only            |
| High       | Sửa Finance pipeline  | Tạo patch + validation + approval |
| Critical   | Deploy production     | Block trong MVP                   |
Rule quan trọng:

```text
Nếu request liên quan Finance metric hoặc production pipeline:
- Không được tự deploy.
- Phải tạo patch.
- Phải chạy validation.
- Phải tạo RCA report.
- Phải yêu cầu human approval.
```

---
## 13. Data Context Compression Engine
### 13.1 Mục tiêu
Giảm token và tăng performance khi agent xử lý data.
Nguyên tắc:

```text
LLM không đọc database.
LLM đọc context pack.
Database/tool đọc data.
```

### 13.2 Cách làm
#### Metadata-first
Agent đọc schema, partition, owner, freshness, data contract trước.
#### Query pushdown
Để database tính toán:

```sql
select
  refund_status,
  count(*) as txn_count,
  sum(amount) as total_amount
from payment_txn
where txn_date = '2026-06-07'
group by refund_status;
```

LLM chỉ nhận output nhỏ:

```json
{
  "refund_status_profile": {
    "NONE": {
      "count": 1500000,
      "amount": 12000000000
    },
    "REFUNDED": {
      "count": 20000,
      "amount": 500000000
    },
    "PARTIAL_REFUND": {
      "count": 8000,
      "amount": 210000000
    }
  }
}
```

> **Ghi chú thực thi (v4) — số liệu phải tính từ data thật.**
> Tất cả con số profile/aggregate ở trên (count, amount, affected_amount) phải là **kết quả query
> SQL thật** trên data mẫu trong SQLite/Postgres, **không** phải hằng số viết cứng trong JSON. Đây là
> yêu cầu bắt buộc để hệ thống thuyết phục: phần đáng tin nhất của sản phẩm là evidence được tool
> tính ra, không phải số do người soạn demo điền sẵn.

#### Cached profile

```json
{
  "table": "payment_txn",
  "partition_key": "txn_date",
  "known_values": {
    "refund_status": ["NONE", "REFUNDED", "PARTIAL_REFUND"]
  },
  "last_profiled_at": "2026-06-07T09:00:00"
}
```

#### Context budget

```json
{
  "max_context_tokens": 6000,
  "strategy": [
    "retrieve top 3 memories",
    "include only relevant schema columns",
    "include aggregate result only",
    "include only target code block",
    "summarize tool logs"
  ]
}
```

Target:

```text
5k–9k input tokens cho một investigation chính.
0 raw data rows đưa vào LLM.
```

---
## 14. Trust, Evaluation & Verification Layer
### 14.1 Mục tiêu
Hệ thống không được tin vào câu trả lời của LLM chỉ vì nó nghe hợp lý. Mọi kết luận quan trọng phải được xác minh bằng evidence từ tools, validation hoặc human approval.
Nguyên tắc chính:

```text
No evidence, no claim.
No validation, no patch approval.
No business decision, no business logic change.
Low confidence, escalate.
Tool result beats LLM reasoning.
```

Nói cách khác:
> Không tin answer. Tin evidence.
---
### 14.2 Claim-level Verification
Trước khi tạo RCA report, hệ thống tách câu trả lời của agent thành các claim riêng lẻ.

#### 14.2.1 Claim Schema (mới ở v4)
Mỗi claim phải tuân theo schema cố định để có thể verify deterministic:

```json
{
  "claim_id": "C1",
  "claim": "PARTIAL_REFUND appeared in payment_txn on 2026-06-07",
  "claim_type": "data_fact",
  "required_evidence": ["sql_profile"],
  "expected_value": { "field": "refund_status_profile.PARTIAL_REFUND.count", "op": ">", "value": 0 },
  "evidence_value": null,
  "status": "pending"
}
```

`claim_type` quyết định cách verify:

| claim_type            | Verify bằng                          | Có thể auto `verified`? |
| --------------------- | ------------------------------------ | ----------------------- |
| `data_fact`           | sql_profile / schema_diff / *_check  | Có (rule engine so khớp) |
| `code_fact`           | code_search                          | Có (rule engine so khớp) |
| `quantitative`        | reconciliation / impact_simulation   | Có (so khớp ± tolerance) |
| `business_decision`   | decision_memory / human_approval     | Không — luôn `requires_approval` |

#### 14.2.2 Ranh giới LLM vs Rule Engine (mới ở v4 — điểm cốt lõi)
Đây là điểm phân biệt hệ thống này với một LLM-as-judge thông thường:

```text
LLM CHỈ được phép:
- Tách câu trả lời của agent thành danh sách claim.
- Gán claim_type và required_evidence (đề xuất).
- KHÔNG được tự gán status = "verified".

RULE ENGINE (Python, deterministic) chịu trách nhiệm:
- Lấy evidence_value thật từ tool result đã chạy.
- So khớp expected_value vs evidence_value theo op (>, <, =, in, abs-diff < tolerance).
- Gán status cuối cùng: verified / unsupported / requires_approval.
- business_decision luôn → requires_approval, bất kể LLM nói gì.
```

#### 14.2.3 Ví dụ rule cụ thể
Claim định lượng "revenue mismatch là 2.1%":

```python
# claim C3, claim_type = "quantitative"
# expected_value = {"field": "reconciliation.before_fix_diff", "op": "abs_diff_lt",
#                   "value": 0.021, "tolerance": 0.002}
evidence = tool_results["reconciliation_check"]["before_fix_diff"]   # vd 0.0211
if abs(evidence - 0.021) < 0.002:
    status = "verified"
else:
    status = "unsupported"   # block, không cho vào RCA như sự thật
```

#### 14.2.4 Ví dụ tổng hợp

```json
{
  "claims": [
    {
      "claim": "PARTIAL_REFUND appeared in payment_txn on 2026-06-07",
      "claim_type": "data_fact",
      "required_evidence": ["sql_profile"],
      "status": "verified"
    },
    {
      "claim": "revenue_daily.sql does not handle PARTIAL_REFUND",
      "claim_type": "code_fact",
      "required_evidence": ["code_search"],
      "status": "verified"
    },
    {
      "claim": "This caused 2.1% revenue mismatch",
      "claim_type": "quantitative",
      "required_evidence": ["reconciliation_check"],
      "status": "verified"
    },
    {
      "claim": "PARTIAL_REFUND should be treated as refunded amount",
      "claim_type": "business_decision",
      "required_evidence": ["finance_decision", "human_approval"],
      "status": "requires_approval"
    }
  ]
}
```

Nếu claim không có evidence, hệ thống không được trình bày claim đó như sự thật. Claim phải được đánh dấu là:

```text
Unsupported
Need more evidence
Requires human review
```

> Lưu ý: cơ chế so khớp giá trị ở §14.2.3 chính là cơ chế mà **§14.6 Contradiction Checker** dùng —
> cùng một rule engine, chỉ khác đầu vào (claim vs RCA report).
---
### 14.3 Evidence Grounding
Mỗi kết luận trong RCA report phải được gắn với evidence cụ thể:
| Claim                                 | Evidence             | Source            | Status   |
| ------------------------------------- | -------------------- | ----------------- | -------- |
| PARTIAL_REFUND xuất hiện trong source | SQL profile result   | sql_profile       | Verified |
| Pipeline chưa handle PARTIAL_REFUND   | Code search result   | revenue_daily.sql | Verified |
| Revenue bị overstated 2.1%            | Reconciliation test  | validation_engine | Verified |
| Patch làm mismatch giảm còn 0.03%     | After-fix validation | run_validation    | Verified |
Final report chỉ được coi là reliable nếu các claim quan trọng đều có evidence.
---
### 14.4 Trust Matrix
Hệ thống không dùng một confidence score đơn giản. Thay vào đó, hệ thống dùng Trust Matrix:

```text
Metric definition confidence: High
Data anomaly confidence: High
Code root cause confidence: High
Business interpretation confidence: Medium
Patch correctness confidence: High
Deployment safety confidence: Medium
```

Điều này giúp phân biệt phần nào hệ thống chắc chắn, phần nào cần human approval.
Ví dụ:

```text
Technical root cause is verified.
Business mapping requires Finance approval.
```

---
### 14.5 LLM-as-Judge
LLM-as-Judge có thể được dùng để review reasoning và output quality, nhưng không được dùng làm nguồn sự thật cuối cùng.
LLM-as-Judge kiểm tra:

```text
- RCA có đủ evidence chưa?
- Có claim nào không có source không?
- Có contradiction giữa report và tool result không?
- Output có đúng format không?
- Agent có overclaim không?
```

Những thứ không được giao cho LLM-as-Judge quyết định một mình:

```text
- SQL result đúng hay sai
- Patch chạy được hay không
- Reconciliation pass hay fail
- Deploy được hay không
```

Các quyết định này phải dựa trên deterministic tools như SQL executor, test runner, schema checker, reconciliation validator và policy engine.
---
### 14.6 Contradiction Checker
Contradiction Checker kiểm tra xem RCA report có mâu thuẫn với tool result không.
Ví dụ:

```text
Tool result:
After fix mismatch = 0.8%
RCA report:
After fix mismatch = 0.03%
```

Kết quả:

```json
{
  "contradiction_found": true,
  "field": "after_fix_mismatch",
  "tool_value": "0.8%",
  "report_value": "0.03%",
  "action": "block_final_report_and_request_review"
}
```

Nếu có contradiction, hệ thống không được tạo final RCA.
---
### 14.7 Golden Set Evaluation
Trước khi demo hoặc deploy, hệ thống cần có bộ test case chuẩn để đánh giá agent.
Ví dụ golden set:

```text
Case 1: New enum PARTIAL_REFUND
Case 2: Missing partition
Case 3: Late-arriving payment
Case 4: Duplicate transaction
Case 5: Null spike in amount
Case 6: Schema type changed
Case 7: Wrong business mapping
Case 8: Unknown issue with low confidence
```

Mỗi case có expected output:

```json
{
  "case_id": "CASE-001",
  "input": "Revenue 2026-06-07 lệch 2.1%",
  "expected_root_cause": "PARTIAL_REFUND not mapped",
  "expected_tools": [
    "memory_search",
    "sql_profile",
    "code_search",
    "run_validation"
  ],
  "expected_policy": "requires_human_approval",
  "expected_patch_contains": "PARTIAL_REFUND",
  "expected_final_status": "ready_for_approval"
}
```

---
### 14.8 Evaluation Metrics
Hệ thống cần đo các metrics sau:

```text
Root cause accuracy
Tool selection accuracy
Evidence coverage
Grounded claim rate
Unsupported claim count
Contradiction rate
Patch validation pass rate
Human correction rate
False positive root cause rate
Escalation correctness
Memory write-back quality
```

Nếu unsupported claim hoặc contradiction vượt threshold, hệ thống không được tạo final RCA mà phải chuyển sang human review.
---
### 14.9 Runtime Decision Rules

```text
1. Nếu root cause chưa có evidence từ tool, không được kết luận.
2. Nếu patch chưa pass validation, không được recommend approval.
3. Nếu business mapping chưa có decision memory, phải yêu cầu Finance approval.
4. Nếu confidence thấp, chuyển sang Unknown Issue Mode hoặc human escalation.
5. Nếu tool result mâu thuẫn với LLM reasoning, ưu tiên tool result.
6. Nếu RCA chưa được human approve, không ghi vào long-term memory.
7. (v4) Nếu KHÔNG hypothesis nào đạt ngưỡng confidence (vd max < 0.5) → no_confident_root_cause:
   tạo evidence pack, escalate, KHÔNG sinh patch (xem §11.4 Negative Case).
8. (v4) Nếu LLM trả output sai schema sau N retry → treat như tool fail: không kết luận, escalate.
```

---
## 15. Tool Layer
### 15.1 Tool list cho MVP
Cột **Phase 1** đánh dấu tool chạy thật trong vertical slice đầu tiên (§20A) vs tool được stub.

| #  | Tool                       | Phase 1 |
| -- | -------------------------- | ------- |
| 1  | memory_search              | real (đọc JSON) |
| 2  | rag_retrieve               | real (đọc markdown, keyword/embedding đơn giản) |
| 3  | metadata_scan              | real |
| 4  | schema_diff                | stub |
| 5  | sql_profile                | **real (query DB thật)** |
| 6  | freshness_check            | stub |
| 7  | volume_check               | stub |
| 8  | null_check                 | real (cho Slice 3) |
| 9  | duplicate_check            | stub |
| 10 | enum_drift_check           | real |
| 11 | distribution_drift_check   | stub |
| 12 | lineage_lookup             | real (đọc pipeline_memory) |
| 13 | code_search                | **real (grep file SQL thật)** |
| 14 | deployment_log_search      | stub |
| 15 | generate_patch             | **real** |
| 16 | review_patch               | real |
| 17 | run_validation             | **real (chạy SQL reconciliation thật)** |
| 18 | impact_simulation          | real |
| 19 | claim_verifier             | **real (LLM tách claim + rule engine so khớp)** |
| 20 | evidence_mapper            | real |
| 21 | contradiction_checker      | **real (rule engine)** |
| 22 | trust_scorer               | real |
| 23 | generate_rca_report        | real |
| 24 | approval_state             | real |
| 25 | memory_writeback           | real |

> Nguyên tắc: ~10 tool đánh dấu **real/bold** là đủ để câu chuyện end-to-end đứng vững và thuyết
> phục. Tool stub trả về dữ liệu mẫu có cấu trúc đúng schema, để có thể nâng cấp dần ở các Slice/Phase
> sau mà không đổi interface.

### 15.2 Tool descriptions
#### memory_search
Tìm structured memory liên quan đến metric, pipeline, incident, decision.
#### rag_retrieve
Retrieve tài liệu context: metric dictionary, runbook, data contract, previous incident.
#### metadata_scan
Lấy schema, column types, partition key, freshness.
#### schema_diff
So sánh schema/data contract hiện tại với actual data.
#### sql_profile
Chạy SQL aggregate để tìm anomaly, enum drift, null rate, duplicate rate.
#### freshness_check
Kiểm tra data có được load đúng SLA không.
#### volume_check
So sánh row count hôm nay với baseline.
#### null_check
Kiểm tra null spike ở các column quan trọng.
#### duplicate_check
Kiểm tra duplicate transaction/order/payment.
#### enum_drift_check
Phát hiện value mới trong status/category/type.
#### distribution_drift_check
Phát hiện phân phối amount/status/category bất thường.
#### lineage_lookup
Tìm upstream/downstream assets bị ảnh hưởng.
#### code_search
Tìm file pipeline/code liên quan.
#### deployment_log_search
Tìm PR/deploy gần đây có thể gây lỗi.
#### generate_patch
Sinh patch nhỏ thay vì rewrite toàn file.
#### review_patch
Review patch về business risk, code risk và approval requirement.
#### run_validation
Chạy validation trước/sau fix.
#### impact_simulation
Mô phỏng impact Finance trước/sau fix.
#### claim_verifier
Tách conclusion thành từng claim (LLM) và kiểm tra mỗi claim có evidence không (rule engine, xem §14.2).
#### evidence_mapper
Map từng claim với source evidence cụ thể.
#### contradiction_checker
Phát hiện mâu thuẫn giữa RCA report và tool result.
#### trust_scorer
Tạo Trust Matrix và quyết định có được final report hay phải human review.
#### generate_rca_report
Tạo RCA report cho DE và Finance.
#### approval_state
Quản lý trạng thái approve/reject/request revision.
#### memory_writeback
Ghi incident/runbook mới vào memory sau khi human approve.
---
## 16. Safe Patch Compiler
### 16.1 Mục tiêu
Không để AI rewrite toàn bộ file. Agent chỉ tạo patch nhỏ, có kiểm chứng.
### 16.2 Input

```json
{
  "target_file": "models/finance/revenue_daily.sql",
  "issue": "PARTIAL_REFUND is not handled",
  "current_logic": "refund_status = 'REFUNDED'",
  "expected_logic": "refund_status in ('REFUNDED', 'PARTIAL_REFUND')"
}
```

### 16.3 Output

```json
{
  "patch_id": "PATCH-001",
  "target_file": "models/finance/revenue_daily.sql",
  "change_type": "replace_block",
  "risk_level": "high",
  "requires_approval": true,
  "old_code": "when refund_status = 'REFUNDED' then refunded_amount",
  "new_code": "when refund_status in ('REFUNDED', 'PARTIAL_REFUND') then refunded_amount",
  "reason": "PARTIAL_REFUND should be included in refund calculation",
  "rollback_plan": "Revert patch and restore previous revenue_daily partition"
}
```

Thông điệp:
> Không phải AI generate code lung tung. AI compile business intent thành safe patch.
---
## 17. Validation Engine
### 17.1 Mục tiêu
Không kết luận hoặc propose fix nếu chưa có validation.

> **Ghi chú thực thi (v4):** Validation Engine phải **thực sự chạy SQL** trên data mẫu (SQLite/
> Postgres) để tính reconciliation before/after. `before_fix_diff` và `after_fix_diff` là số tính
> ra từ query, không phải hằng số. Cách làm: chạy logic cũ vs logic patch trên cùng partition, so
> với baseline/source để ra mismatch thật.
### 17.2 Test cần chạy

```text
1. Schema contract check
2. Null check
3. Duplicate transaction check
4. Accepted values check
5. Revenue reconciliation check
6. Before/after impact simulation
7. Patch syntax check
8. Regression check với sample historical data
```

### 17.3 Output

```json
{
  "validation_status": "PASS",
  "tests": [
    {
      "name": "schema_contract_check",
      "status": "PASS"
    },
    {
      "name": "null_check",
      "status": "PASS"
    },
    {
      "name": "duplicate_transaction_check",
      "status": "PASS"
    },
    {
      "name": "accepted_values_check",
      "status": "PASS"
    },
    {
      "name": "revenue_reconciliation_check",
      "status": "PASS",
      "before_fix_diff": "2.1%",
      "after_fix_diff": "0.03%"
    }
  ]
}
```

---
## 18. Evidence Pack & RCA Report
### 18.1 Mục tiêu
Finance không chỉ cần kết luận. Finance cần bằng chứng, impact, validation và action rõ ràng.
### 18.2 RCA Format

```markdown
# Root Cause Analysis Report
## Incident Summary
Revenue report for 2026-06-07 was overstated by 2.1%.
## Root Cause
A new refund_status value `PARTIAL_REFUND` appeared in `payment_txn`.
The `revenue_daily` pipeline only handled `REFUNDED`.
## Evidence
- SQL profile detected `PARTIAL_REFUND`.
- Affected amount: 210,000,000 VND.
- Code search found missing mapping in `revenue_daily.sql`.
- Validation before fix failed reconciliation check.
- Validation after patch passed reconciliation check.
## Claim Verification
| Claim | Evidence | Status |
|---|---|---|
| PARTIAL_REFUND appeared in source | sql_profile | Verified |
| Pipeline does not handle PARTIAL_REFUND | code_search | Verified |
| Revenue mismatch was 2.1% | reconciliation_check | Verified |
| Business mapping requires Finance confirmation | decision_memory/human_approval | Requires Approval |
## Trust Matrix
- Metric definition confidence: High
- Data anomaly confidence: High
- Code root cause confidence: High
- Business interpretation confidence: Medium
- Patch correctness confidence: High
- Deployment safety confidence: Medium
## Business Impact
Net revenue was overstated by 2.1%.
Affected report: finance_revenue_report.
## Proposed Fix
Update refund mapping logic in `revenue_daily.sql`.
## Validation Result
- Before fix mismatch: 2.1%.
- After fix mismatch: 0.03%.
- Tests passed: 5/5.
## Approval Required
Finance Owner and Data Owner approval required before publishing corrected report.
## Rollback Plan
Revert patch and restore previous revenue_daily partition if validation fails after deployment.
```

---
## 19. Demo Scenario chính
### 19.1 User Input

```text
Revenue report ngày 2026-06-07 đang lệch 2.1% so với payment dashboard.
Kiểm tra nguyên nhân và đề xuất fix.
```

### 19.2 Root cause giả lập
Source table `payment_txn` xuất hiện enum value mới:

```text
refund_status = PARTIAL_REFUND
```

Nhưng pipeline `revenue_daily.sql` chỉ xử lý:

```text
refund_status = REFUNDED
```

Do đó `PARTIAL_REFUND` chưa được trừ khỏi revenue, làm `net_revenue` bị overstated 2.1%.
### 19.3 Expected Output

```text
Root cause:
- Source table payment_txn xuất hiện refund_status mới: PARTIAL_REFUND.
- Pipeline revenue_daily.sql chưa mapping value này.
Evidence:
- SQL profile xác nhận PARTIAL_REFUND xuất hiện.
- Code search xác nhận revenue_daily.sql chưa handle value này.
- Reconciliation check xác nhận mismatch 2.1%.
Impact:
- Net revenue ngày 2026-06-07 bị overstated 2.1%.
- Affected amount: 210,000,000 VND.
- Affected report: finance_revenue_report.
Proposed fix:
- Update refund mapping logic trong revenue_daily.sql.
- Include PARTIAL_REFUND vào refunded_amount.
Validation:
- Before fix mismatch: 2.1%.
- After fix mismatch: 0.03%.
- Tests passed: 5/5.
Trust:
- Technical root cause: Verified.
- Business mapping: Requires Finance approval.
Status:
- Ready for human approval.
```

---
## 20. End-to-end Workflow

```text
Step 1: User submits issue
Finance/Data Engineer nhập request vào UI.
Step 2: State initialization
LangGraph tạo investigation state.
Step 3: Intent & risk classification
Gemma/Qwen phân loại intent, metric, date, risk level.
Step 4: Memory/RAG retrieval
System retrieve metric definition, decision memory, pipeline lineage, previous incident, runbook.
Step 5: Known vs Unknown Routing
Nếu có incident/runbook tương tự → follow known runbook.
Nếu không có → chuyển sang Unknown Issue Mode.
Step 6: Tool governance
Python rule engine kiểm tra tool nào được phép chạy.
Block full scan, block unsafe SQL, enforce partition filter.
Step 7: Diagnostic tools
Chạy metadata_scan, schema_diff, sql_profile, freshness_check, volume_check, enum_drift_check.
Step 8: Root cause reasoning
Claude suy luận root cause từ evidence đã được tool xác nhận.
Step 9: Claim verification
Claim Verifier tách từng claim và kiểm tra có evidence hay không.
Step 10: Impact simulation
Tool tính mismatch trước/sau fix và affected amount.
Step 11: Code search
Qwen/MiniMax tìm đoạn code mapping trong revenue_daily.sql.
Step 12: Safe patch generation
Qwen Coder tạo patch nhỏ.
Step 13: Patch review
Claude review patch về business risk, approval requirement và missing tests.
Step 14: Validation
Deterministic validation engine chạy schema check, null check, duplicate check, reconciliation check.
Step 15: Trust scoring
Trust Scorer tạo Trust Matrix và check unsupported claim/contradiction.
Step 16: RCA report
Claude tạo báo cáo cho Finance và Data Engineer.
Step 17: Human approval
Agent không deploy. Agent chờ approve/reject/request revision.
Step 18: Memory write-back
Nếu human approve RCA/root cause, system ghi incident/runbook mới vào long-term memory.
```

---
## 20A. Build Order / Vertical Slice Plan (mới ở v4)

Đây là phần quan trọng nhất bổ sung ở v4. §21 mô tả "build cái gì"; phần này mô tả "build theo thứ
tự nào". Nguyên tắc:

> Build **một lát cắt dọc chạy thật xuyên suốt** trước, phần còn lại stub/mock đúng schema. Không
> build theo chiều ngang (làm xong hết tool rồi mới ráp), vì rủi ro có nhiều mảnh rời và không chạy
> được end-to-end.

### Slice 1 — Happy path chạy thật end-to-end (case PARTIAL_REFUND)
Mục tiêu: một request đi trọn vẹn từ UI đến "ready for approval", với các tool lõi chạy **thật**.

```text
State init → intent/risk classify → memory+RAG retrieve →
sql_profile (query DB thật) → code_search (grep file SQL thật) →
root cause reasoning → claim_verifier (LLM tách + rule engine so khớp) →
generate_patch → run_validation (reconciliation tính thật trên DB) →
trust_scorer → generate_rca_report → approval_state.
```

Definition of done: chạy được, RCA hiển thị trên Streamlit, số 2.1%/0.03% là **tính ra từ SQL**,
claim verification có status đúng, status cuối = "ready_for_approval".

### Slice 2 — Governance thật
Mục tiêu: chứng minh hệ thống chặn hành vi nguy hiểm.

```text
- Block SQL full scan / thiếu partition filter (sql_policy).
- Hiển thị policy decision + suggestion trên UI.
- Finance metric change → require approval (approval_policy).
```

### Slice 3 — Case thứ hai khác loại (phá "single-scenario trap")
Mục tiêu: chứng minh hệ thống tổng quát, không hardcode quanh PARTIAL_REFUND.
Đề xuất: **missing partition + null spike** (dùng `freshness_check`/`volume_check`/`null_check`).

```text
- Data ngày X thiếu partition hoặc null rate amount tăng đột biến.
- Diagnostic checklist tự phát hiện, root cause khác hẳn case 1.
- Claim verification + RCA vẫn chạy đúng với loại lỗi mới.
```

### Slice 4 — Negative case (chống hallucination)
Mục tiêu: chứng minh agent biết dừng (xem §11.4).

```text
- Một case không có root cause rõ ràng (max confidence < ngưỡng).
- Agent KHÔNG sinh patch, KHÔNG kết luận.
- Tạo evidence pack + escalate cho human.
```

### Thứ tự ưu tiên
```text
Slice 1 (bắt buộc, là xương sống)
  → Slice 2 (governance — điểm bán hàng về an toàn)
  → Slice 3 (tổng quát hoá — chống nghi ngờ "demo dàn dựng")
  → Slice 4 (trust — chống hallucination)
```
Mỗi slice xong phải **chạy được độc lập trên UI** trước khi sang slice sau.

---
## 21. MVP Scope
### 21.1 In Scope
MVP cần demo được:

```text
- Streamlit UI.
- LangGraph workflow cơ bản.
- Model router config.
- Mock finance data bằng CSV hoặc SQLite/PostgreSQL.
- Local JSON memory.
- Local markdown/json RAG context.
- Local SQL pipeline file.
- Tool governance rule engine.
- SQL profiling.
- Known issue route.
- Unknown Issue Mode basic checklist.
- Root cause detection.
- Claim verification.
- Evidence mapping.
- Safe code patch generation.
- Patch review.
- Validation result.
- Trust Matrix.
- RCA report.
- Approval state.
```

### 21.2 Out of Scope
MVP chưa cần:

```text
- Kết nối production database thật.
- Deploy patch thật.
- Full MCP server.
- Full GraphRAG.
- Full CI/CD integration.
- Slack/Jira integration thật.
- Full enterprise permission system.
- Real-time monitoring production.
- Fine-tuning model.
- Multi-tenant production isolation.
- Wire thật cả 4 model provider (Phase 1 chỉ 1–2 model, xem §6.1).
```

---
## 22. Tech Stack đề xuất
### 22.1 MVP Stack

```text
UI: Streamlit
Backend: Python
Agent Orchestration: LangGraph
Database Demo: SQLite hoặc PostgreSQL
Memory Store: JSON / SQLite
RAG Context: Local markdown/json
Pipeline Code: Local SQL/dbt file
Validation: Python test functions
Reports: Markdown
Model Router: simple YAML config
Evaluation: Golden set JSON + pytest
```

### 22.2 Production-ready Stack

```text
UI: Internal Web App
Backend: FastAPI
Agent Orchestration: LangGraph
Database: PostgreSQL / Data Warehouse
Vector Search: pgvector / Qdrant
Cache: Redis
Observability: OpenTelemetry + custom LLM traces
CI/CD: GitHub/GitLab PR integration
Approval: Slack/Jira/ServiceNow integration
Evaluation: Golden set + human review + LLM-as-judge
Model Gateway: central model router
```

---
## 23. Model Router Config
Ví dụ config. Mỗi route có thêm `phase1` (`real`/`stub`) và `fallback` để hiện thực hoá ghi chú ở §6.1:

```yaml
defaults:
  fallback: planner   # nếu model lỗi/timeout → dùng route này
models:
  classifier:
    provider: local_or_api
    model: gemma_or_qwen_small
    use_case: intent_and_risk_classification
    phase1: real          # hoặc stub→planner nếu chưa có model nhỏ
    fallback: planner
  query_rewriter:
    provider: api
    model: qwen
    use_case: memory_and_rag_query_rewrite
    phase1: stub
    fallback: planner
  planner:
    provider: api
    model: claude
    use_case: orchestration_reasoning
    phase1: real
  sql_generator:
    provider: api
    model: qwen_coder
    use_case: sql_profile_generation
    phase1: stub
    fallback: planner
  code_model:
    provider: api
    model: qwen_coder
    use_case: code_search_and_patch_generation
    phase1: stub
    fallback: planner
  long_context_analyzer:
    provider: api
    model: minimax
    use_case: long_docs_logs_codebase_analysis
    phase1: stub
    fallback: planner
  claim_verifier:
    provider: hybrid
    model: claude_plus_rules
    use_case: claim_level_verification
    phase1: real          # rule engine bắt buộc thật
  patch_reviewer:
    provider: api
    model: claude
    use_case: patch_risk_review
    phase1: real
  rca_generator:
    provider: api
    model: claude
    use_case: rca_report_generation
    phase1: real
  guardrail:
    provider: local
    model: gemma
    use_case: pii_masking_and_small_summarization
    phase1: stub
    fallback: planner
```

---
## 24. Folder Structure đề xuất

```text
finance-dataops-twin/
│
├── app/
│   ├── main.py
│   └── components/
│       ├── request_input.py
│       ├── timeline.py
│       ├── context_panel.py
│       ├── patch_viewer.py
│       ├── trust_matrix.py
│       └── rca_viewer.py
│
├── graph/
│   ├── state.py
│   ├── workflow.py
│   ├── nodes.py
│   ├── edges.py
│   └── conditions.py
│
├── agents/
│   ├── intent_classifier.py
│   ├── context_retriever.py
│   ├── diagnostic_planner.py
│   ├── root_cause_reasoner.py
│   ├── claim_verifier.py
│   ├── patch_reviewer.py
│   └── rca_generator.py
│
├── model_router/
│   ├── router.py
│   ├── providers.py
│   └── models.yaml
│
├── tools/
│   ├── memory_search.py
│   ├── rag_retrieve.py
│   ├── metadata_scan.py
│   ├── schema_diff.py
│   ├── sql_profile.py
│   ├── freshness_check.py
│   ├── volume_check.py
│   ├── null_check.py
│   ├── duplicate_check.py
│   ├── enum_drift_check.py
│   ├── distribution_drift_check.py
│   ├── lineage_lookup.py
│   ├── code_search.py
│   ├── deployment_log_search.py
│   ├── generate_patch.py
│   ├── run_validation.py
│   ├── impact_simulation.py
│   ├── evidence_mapper.py
│   ├── contradiction_checker.py
│   ├── trust_scorer.py
│   ├── generate_rca_report.py
│   └── memory_writeback.py
│
├── governance/
│   ├── sql_policy.py
│   ├── tool_policy.py
│   ├── approval_policy.py
│   ├── pii_policy.py
│   └── claim_policy.py
│
├── memory/
│   ├── user_memory.json
│   ├── metric_memory.json
│   ├── pipeline_memory.json
│   ├── incident_memory.json
│   ├── decision_policy_memory.json
│   └── approved_runbooks.json
│
├── rag_docs/
│   ├── finance_metric_dictionary.md
│   ├── data_contracts.md
│   ├── runbook_revenue_mismatch.md
│   ├── previous_incidents.md
│   └── pipeline_docs.md
│
├── evals/
│   ├── golden_set.json
│   ├── expected_outputs/
│   ├── evaluate_root_cause.py
│   ├── evaluate_tool_selection.py
│   ├── evaluate_grounding.py
│   └── evaluate_patch.py
│
├── data/
│   ├── sample_payment_txn.csv
│   ├── sample_revenue_daily.csv
│   └── seed_data/
│
├── database/
│   ├── postgres/
│   │   ├── init.sql
│   │   └── schema.sql
│   ├── connection.py
│   └── db_config.yaml
│
├── pipelines/
│   └── models/
│       └── finance/
│           └── revenue_daily.sql
│
├── reports/
│   └── rca_INV_001.md
│
├── tests/
│   ├── test_schema_contract.py
│   ├── test_reconciliation.py
│   ├── test_patch_generation.py
│   ├── test_claim_verification.py
│   └── test_unknown_issue_mode.py
│
├── observability/
│   ├── trace_logger.py
│   ├── token_tracker.py
│   └── latency_tracker.py
│
├── requirements.txt
└── README.md
```

---
## 25. Functional Requirements
### FR-001: Submit Investigation Request
User có thể nhập issue bằng natural language.
Acceptance criteria:

```text
- UI có input box.
- System parse được metric/date nếu có.
- Request được tạo thành investigation_id.
- State được khởi tạo trong LangGraph.
```

### FR-002: Intent & Risk Classification
System phân loại intent và risk.
Acceptance criteria:

```text
- Parse được intent.
- Parse được metric/date nếu có.
- Gán được risk level.
- Finance metric issue phải được gán risk high.
```

### FR-003: Retrieve Context
System retrieve context từ memory và RAG.
Acceptance criteria:

```text
- Retrieve được metric definition.
- Retrieve được pipeline lineage.
- Retrieve được previous incident nếu có.
- Retrieve được approval rule.
- Context được hiển thị trên UI.
```

### FR-004: Known vs Unknown Routing
System quyết định follow known runbook hoặc Unknown Issue Mode.
Acceptance criteria:

```text
- Nếu tìm thấy incident tương tự, dùng known runbook.
- Nếu không tìm thấy, chạy Unknown Issue checklist.
- Routing decision được log lại.
```

### FR-005: Tool Governance
System kiểm tra tool call trước khi chạy.
Acceptance criteria:

```text
- Block query không có partition filter.
- Không cho raw data vào LLM.
- Finance metric change phải require approval.
- Tool decision được hiển thị trên UI.
```

### FR-006: SQL Profiling
System chạy SQL aggregate để tìm anomaly.
Acceptance criteria:

```text
- Chạy profile theo refund_status.
- Phát hiện PARTIAL_REFUND.
- Trả về count và amount theo refund_status.
- Không gửi raw rows vào LLM.
```

### FR-007: Root Cause Detection
System xác định root cause.
Acceptance criteria:

```text
- Phát hiện enum value mới.
- Xác định pipeline chưa handle value đó.
- Có evidence từ SQL profile và code search.
- Nếu confidence thấp, system không kết luận vội.
```

### FR-008: Claim Verification
System kiểm chứng từng claim quan trọng.
Acceptance criteria:

```text
- Mỗi claim phải có required evidence.
- Claim thiếu evidence phải được đánh dấu Unsupported hoặc Requires Review.
- RCA không được final nếu có critical unsupported claim.
- (v4) LLM chỉ tách claim; rule engine quyết status verified/unsupported/requires_approval.
- (v4) Claim loại business_decision luôn requires_approval.
```

### FR-009: Impact Simulation
System tính impact business.
Acceptance criteria:

```text
- Tính mismatch trước fix.
- Tính mismatch sau fix.
- Tính affected amount.
- Xác định affected report.
- (v4) Các số này tính từ query SQL thật, không hardcode.
```

### FR-010: Code Patch Generation
System sinh patch nhỏ.
Acceptance criteria:

```text
- Patch chỉ sửa đoạn mapping liên quan.
- Có old code và new code.
- Có reason.
- Có risk level.
- Không tự deploy.
```

### FR-011: Patch Review
System review patch trước validation.
Acceptance criteria:

```text
- Review syntax risk.
- Review business risk.
- Xác định approval requirement.
- Đề xuất test cần chạy.
```

### FR-012: Validation
System chạy validation.
Acceptance criteria:

```text
- Schema check pass.
- Null check pass.
- Duplicate check pass.
- Revenue reconciliation pass.
- Tests result được hiển thị.
- (v4) Reconciliation chạy SQL thật trên data mẫu.
```

### FR-013: Trust Scoring
System tạo Trust Matrix.
Acceptance criteria:

```text
- Có confidence cho metric definition, data anomaly, code root cause, business interpretation, patch correctness, deployment safety.
- Nếu trust thấp ở phần critical, system chuyển human review.
```

### FR-014: RCA Report
System tạo RCA report.
Acceptance criteria:

```text
- Có incident summary.
- Có root cause.
- Có evidence.
- Có claim verification.
- Có trust matrix.
- Có business impact.
- Có proposed fix.
- Có validation result.
- Có approval required.
- Có rollback plan.
```

### FR-015: Approval Flow
System có trạng thái approval.
Acceptance criteria:

```text
- User có thể approve.
- User có thể reject.
- User có thể request revision.
- Patch không được apply nếu chưa approve.
```

### FR-016: Memory Write-back
System ghi incident mới vào memory sau khi được approve.
Acceptance criteria:

```text
- Chỉ write memory sau human approval.
- Không ghi memory từ suy đoán chưa xác thực.
- Memory mới có root cause, evidence, fix, diagnostic steps.
```

### FR-017: Low-confidence Escalation (mới ở v4)
System biết dừng khi không đủ evidence.
Acceptance criteria:

```text
- Nếu max confidence của mọi hypothesis < ngưỡng, không kết luận root cause.
- Không sinh patch.
- Tạo evidence pack tổng hợp diagnostic đã chạy.
- Escalate cho human.
```

### FR-018: LLM Output Reliability (mới ở v4)
System xử lý được khi LLM trả output sai định dạng.
Acceptance criteria:

```text
- Mọi LLM node yêu cầu structured output theo schema.
- Validate output; retry tối đa N lần nếu sai schema.
- Sau N lần vẫn sai → treat như tool fail, không kết luận, escalate.
```

---
## 26. Non-functional Requirements
### Performance

```text
- Không đưa raw data vào LLM.
- Mỗi LLM call có context budget.
- Cache schema/profile/tool result nếu có thể.
- Các bước deterministic như SQL/profile/validation không cần LLM.
- Dùng model nhỏ cho task đơn giản.
- Dùng model mạnh cho task rủi ro cao.
```

### Reliability

```text
- Tool output phải có schema rõ ràng.
- Nếu tool fail, agent phải ghi nhận lỗi và không kết luận vội.
- Patch phải có validation trước khi report.
- Không tự deploy production.
- Unknown Issue Mode phải escalate nếu confidence thấp.
- RCA phải pass claim verification trước khi final.
```

### LLM Reliability / Structured Output (mới ở v4)

```text
- Mọi LLM node trả structured output (JSON theo schema cố định).
- Validate schema sau mỗi call; retry với hướng dẫn sửa nếu sai (tối đa N lần).
- Sau N retry vẫn sai schema → coi như tool fail: không kết luận, log lỗi, escalate human.
- LLM không bao giờ là nơi quyết pass/fail, verified/unverified, hay deploy/không.
- Tách rõ: LLM sinh nội dung; rule engine + deterministic tools ra phán quyết.
```

### Security

```text
- Read-only SQL trong MVP.
- Không expose PII/raw transaction.
- Mask sample data nếu cần.
- Finance metric change requires approval.
- Tool Governance là rule engine, không phụ thuộc hoàn toàn vào LLM.
```

### Observability

```text
- Log tool call timeline.
- Log model used per node.
- Log token usage.
- Log latency từng bước.
- Log validation result.
- Log claim verification result.
- Log trust matrix.
- Log approval status.
- Log memory writeback event.
- (v4) Log model fallback event khi provider chính lỗi.
- (v4) Log LLM schema-retry count.
```

### Maintainability

```text
- Mỗi tool là một module riêng.
- Mỗi LangGraph node tách riêng.
- Model routing tách bằng config.
- Governance rule tách khỏi prompt.
- Memory/RAG docs tách khỏi code.
- Eval logic tách trong folder evals.
- Test logic tách trong folder tests.
```

---
## 27. Token & Performance Strategy
### 27.1 Nguyên tắc

```text
Không phải mọi bước đều gọi LLM.
Không phải mọi memory đều vào prompt.
Không phải mọi data đều đưa cho AI.
```

### 27.2 Cách giảm token

```text
1. Memory retrieval có chọn lọc.
2. Chỉ lấy top relevant memory.
3. RAG chỉ lấy đúng docs liên quan.
4. SQL aggregate thay vì raw rows.
5. Code search chỉ lấy block cần sửa.
6. Tool log được summarize.
7. Patch-based editing, không rewrite full file.
8. Cache schema/profile/result.
9. Model routing: model nhỏ xử lý task nhỏ.
10. Prompt chỉ nhận Runtime Context Pack.
11. Claim verification dùng structured evidence thay vì nhét full logs.
```

### 27.3 Token budget đề xuất

```text
System + tool instruction: 800–1,500 tokens
User request + task state: 300–800 tokens
Retrieved memory/RAG: 800–1,500 tokens
Schema/profile summary: 1,000–2,000 tokens
Relevant code block: 800–1,500 tokens
Tool result summary: 500–1,000 tokens
Claim verification summary: 500–1,000 tokens
```

Target:

```text
5k–10k input tokens cho một investigation chính.
0 raw data rows đưa vào LLM.
```

---
## 28. Metrics đo hiệu quả
### 28.1 Demo Metrics

```text
- Time to find metric definition.
- Time to detect root cause.
- Time to generate patch.
- Tests passed.
- Mismatch before fix.
- Mismatch after fix.
- Number of raw rows sent to LLM: 0.
- Model used per node.
- Claim verification status.
- Trust matrix.
```

> **Ghi chú (v4):** "Mismatch before/after fix" trong demo phải là số do `run_validation` tính từ
> SQL thật, không phải số minh hoạ. Nên hiển thị cả query đã chạy để tăng độ tin cậy khi review.

### 28.2 Production Metrics

```text
- Average investigation latency.
- Token usage per investigation.
- Tool call success rate.
- Cache hit rate.
- Retrieval precision.
- Validation pass rate.
- Human correction rate.
- Approval rate.
- Incident resolution time reduction.
- False positive root cause rate.
- Unknown Issue escalation rate.
- Grounded claim rate.
- Unsupported claim count.
- Contradiction rate.
- Memory writeback quality.
```

---
## 29. Demo Script 2–3 phút
### 0:00–0:20 — Problem

```text
Finance data cần chính xác, có trace và có approval.
Hiện tại khi report lệch số, Data Engineer phải tìm metric, check data, đọc code, sửa pipeline, chạy test và viết RCA thủ công.
```

### 0:20–0:40 — Product

```text
Tôi xây Impact-Aware Finance DataOps Twin, một LangGraph-based Agentic Workflow giúp tự động điều tra lỗi dữ liệu, sinh patch và tạo RCA report, nhưng vẫn kiểm soát rủi ro bằng memory, tool governance, model routing, claim verification và human approval.
```

### 0:40–1:00 — Input

```text
Revenue report 2026-06-07 lệch 2.1% so với payment dashboard.
```

### 1:00–1:20 — LangGraph + Retrieved Context
Show:

```text
LangGraph State initialized.
Intent: investigate_revenue_mismatch.
Risk level: high.
Retrieved Context:
- Metric definition
- Pipeline lineage
- Previous incident
- Decision memory
- Approval rule
```

### 1:20–1:35 — Model Routing
Show:

```text
Intent classifier: Gemma/Qwen
Planner: Claude
SQL/code generation: Qwen Coder
Patch review/RCA: Claude
```

### 1:35–1:55 — Tool Execution
Show:

```text
metadata_scan → sql_profile → code_search → impact_simulation
```

Show governance:

```text
Blocked full scan payment_txn.
Selected aggregate SQL with txn_date filter.
```

### 1:55–2:15 — Root Cause
Show:

```text
PARTIAL_REFUND appeared in source data but is not handled in revenue_daily.sql.
```

### 2:15–2:30 — Claim Verification
Show:

```text
Claim 1: PARTIAL_REFUND appeared in source data → Verified by SQL profile.
Claim 2: revenue_daily.sql missing mapping → Verified by code search.
Claim 3: revenue mismatch 2.1% → Verified by reconciliation test.
Claim 4: business mapping requires approval → Requires Finance approval.
```

### 2:30–2:40 — Patch
Show:

```sql
when refund_status in ('REFUNDED', 'PARTIAL_REFUND')
then refunded_amount
```

### 2:40–2:52 — Validation
Show:

```text
Before fix mismatch: 2.1%
After fix mismatch: 0.03%
Tests passed: 5/5
```

### 2:52–3:00 — RCA + Trust + Approval
Show:

```text
RCA report generated.
Trust Matrix: Technical root cause verified, business mapping requires approval.
Patch is ready.
Waiting for Finance/Data Owner approval.
```

> **Gợi ý demo nâng cao (v4):** nếu có thời gian, thêm 20–30s cho **một case thứ hai khác loại**
> (Slice 3) hoặc **negative case** (Slice 4) để chứng minh hệ thống không phải kịch bản dàn dựng
> quanh đúng PARTIAL_REFUND. Đây là yếu tố tăng độ thuyết phục mạnh nhất khi review nội bộ.

Kết luận:

```text
Điểm chính của project là agent không chỉ viết SQL, mà còn có LangGraph control flow, model routing, memory phân tầng, tool governance, context compression, claim verification, validation và human approval.
```

---
## 30. Future Roadmap
### Phase 1 — MVP

```text
- Local demo (4 vertical slice ở §20A).
- LangGraph workflow.
- Mock finance data (SQLite/Postgres, reconciliation tính thật).
- JSON memory.
- Markdown RAG docs.
- Model router config (pluggable, wire thật 1–2 model).
- SQL profiling.
- Claim verification (LLM tách + rule engine).
- Patch generation.
- Validation.
- Trust Matrix.
- RCA report.
```

### Phase 2 — Internal Pilot

```text
- Kết nối read-only data warehouse.
- Kết nối Git repo thật.
- PR generation.
- Slack/Jira notification.
- Approval workflow thật.
- Observability dashboard.
- Wire thật thêm model (Qwen Coder / MiniMax / Gemma) theo nhu cầu cost/latency.
- Golden set evaluation dashboard.
```

### Phase 3 — Production

```text
- Role-based access control.
- Multi-tenant isolation.
- Tool contracts.
- Audit log.
- Evaluation suite.
- Incident learning loop.
- Auto data contract proposal.
- Monitoring and alert triage.
- Central model gateway.
- Production memory governance.
```

---
## 31. Risks & Mitigation
| Risk                                | Mitigation                                                            |
| ----------------------------------- | --------------------------------------------------------------------- |
| Agent hallucinate root cause        | Bắt buộc evidence từ SQL/profile/code search                          |
| Agent generate wrong SQL            | Read-only SQL, partition filter, SQL policy validator                 |
| Agent trả lời nghe hợp lý nhưng sai | Claim-level verification + contradiction checker                      |
| RCA report mâu thuẫn tool result    | Contradiction checker block final report                              |
| Đốt token quá nhiều                 | Context compression, no raw data, cache profile                       |
| Memory retrieve sai                 | Typed memory, top-k retrieval, confidence score                       |
| Patch sai logic business            | Claude review + Finance approval required                             |
| Tool chạy quá lâu                   | Timeout, query budget, aggregate-only profiling                       |
| Data leakage                        | Mask PII, no raw rows to LLM                                          |
| Agent loop vô hạn                   | LangGraph step limit, tool budget, termination condition              |
| Lỗi lạ không có trong memory        | Unknown Issue Mode + diagnostic checklist                             |
| Agent học sai memory                | Chỉ write memory sau validation/human approval                        |
| Model cost cao                      | Model routing: model nhỏ cho task nhỏ, model mạnh cho task rủi ro cao |
| **(v4) Single-scenario demo**       | Build ≥2 case khác loại (Slice 3) + negative case (Slice 4)           |
| **(v4) Multi-model integration vỡ** | Router pluggable; Phase 1 chỉ wire 1–2 model; fallback về planner     |
| **(v4) LLM trả output sai schema**  | Structured output + retry N lần + treat-as-fail/escalate              |
---
## 32. Câu pitch cuối

```text
Impact-Aware Finance DataOps Twin không phải là chatbot hỏi đáp dữ liệu.
Đây là một LangGraph-based Agentic Workflow có structured memory, decision-aware RAG, model routing, risk-aware tool governance, claim-level verification và validation workflow để giúp Data Engineer bảo vệ độ tin cậy của dữ liệu Finance.
```

Câu ngắn:

```text
AI cho Data Engineering không nên chỉ generate SQL. Nó phải bảo vệ trust của dữ liệu.
```

Câu production-ready:

```text
Tôi không xây agent nhớ mọi thứ bằng cách nhét mọi thứ vào prompt.
Tôi xây một memory-driven context engine: lưu nhiều, retrieve ít, verify bằng tool, validate trước khi output, và luôn kiểm soát token budget.
```

Câu nhấn mạnh về architecture:

```text
Đây không phải một AI Agent đơn lẻ.
Đây là một LangGraph control plane: State → Model → Tools → Routing → Verification → Validation → Human Approval.
```

Câu nhấn mạnh về model routing:

```text
Claude là brain, Qwen là coding hands, MiniMax là long-context reader, Gemma là cheap utility model, còn Python tools là source of truth.
```

Câu nhấn mạnh về hallucination:

```text
Tôi không để AI tự tin là đủ.
Tôi bắt AI chứng minh từng claim bằng evidence từ tool, validation và human approval.
Và khi không đủ evidence, hệ thống biết dừng lại và escalate, thay vì đoán bừa.
```
