# Group Report: Lab 3 — Trợ lý ảo Vinmec (ReAct Agent)

- **Author**: Nguyễn Hoàng Long - 2A202600785

- **Deployment Date**: 2026-06-01

---

## 1. Executive Summary

Dự án xây dựng **trợ lý ảo bệnh viện Vinmec** dựa trên **ReAct Agent viết tay** (chu trình Thought → Action → Observation), chạy trên **Gemini 2.5 Flash** (kèm hỗ trợ OpenAI GPT-4o và Llama 3.1 8B local qua Ollama, sử dụng interface `LLMProvider`). Hệ thống có 8 công cụ, telemetry đầy đủ, và một web demo (Flask).

- **Success Rate**: **16/16 (100%)** trên bộ test phân cấp (Dễ → Rất khó).
- **Key Outcome**: Agent xâu chuỗi tin cậy 3–4 tool cho các tác vụ nhiều bước (định vị → tra lịch → tra giá → bảo hiểm → đặt lịch), xử lý **cấp cứu**, **bộ nhớ hội thoại** và **từ chối ngoài phạm vi** — những việc một chatbot thuần không làm được (sẽ "bịa" giá/địa điểm).

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation
Vòng lặp được hiện thực hoàn toàn thủ công trong [`src/agent/agent.py`](../../src/agent/agent.py):

```
[Bộ nhớ hội thoại] + Question
        │
        ▼
  LLM.generate(system_prompt + transcript + CONTINUE_CUE "…Thought:")
        │
        ▼
  _truncate()  ── cắt phần model bịa (Observation/User/Question)
        │
        ├─ "Final Answer:"  ──► trả lời  ──► _remember()
        ├─ "Action: tool(args)" ──► _parse_action (AST) ──► _execute_tool ──► nối Observation ──► lặp
        └─ (không có Action mà có nội dung) ──► SALVAGE: coi là Final Answer
        │
   hết max_steps (=8) ──► dừng an toàn
```

Điểm thiết kế chính: **mồi `Thought:`** ép model tiếp tục thay vì restart; **chống bịa Observation** (`stop`/truncate); **parser AST** an toàn cho `tool(arg=value)`; **salvage** khi model quên prefix `Final Answer:`; **bộ nhớ** N lượt gần nhất.

### 2.2 Tool Definitions (Inventory) — 8 tools
| Tool | Input | Use Case |
| :--- | :--- | :--- |
| `get_current_location` | — | Định vị người dùng (GPS trình duyệt → IP → fallback) |
| `find_nearest_vinmec` | lat, lon | Cơ sở Vinmec gần nhất (Haversine) |
| `get_service_price` | service_name | Giá dịch vụ khám (VND) |
| `apply_insurance` | price, insurance_type | Số tiền sau bảo hiểm |
| `check_doctor_availability` | specialty, date | Lịch bác sĩ (lọc theo quy tắc đặt trước ≥ 30 phút) |
| `book_appointment` | specialty, time, doctor | Xác nhận đặt lịch + sinh mã |
| `get_emergency_contact` | lat, lon | Số cấp cứu 115 + cơ sở gần nhất |
| `get_first_aid` | condition | Hướng dẫn sơ cứu theo tình trạng |

Dữ liệu tách riêng tại [`vinmec_data.json`](../../src/tools/vinmec_data.json) (cơ sở, lịch, giá, bảo hiểm, alias chuyên khoa, cấu hình cấp cứu, sơ cứu).

### 2.3 LLM Providers Used
- **Primary**: Gemini 2.5 Flash (`gemini-2.5-flash`).
- **Hỗ trợ**: OpenAI GPT-4o, OpenRouter, Llama 3.1 8B local (qua Ollama) — chuyển đổi qua `.env` (`DEFAULT_PROVIDER`).

---

## 3. Telemetry & Performance Dashboard

Đo trên bộ kiểm thử 16 case (mỗi lần gọi LLM ghi token/latency/cost qua `PerformanceTracker`):

- **Tổng token cả suite**: ~109,000 tokens.
- **Average Latency / lần gọi LLM**: ~2,100 ms.
- **Tokens / task**: câu đơn ~600–700 (1 bước); tác vụ đặt lịch nhiều bước ~2,500–3,000 (3–4 bước).
- **Cost (ước tính)**: ~$1.09 cho cả suite — **lưu ý**: công thức cost hiện là mô phỏng ($0.01/1k token trong `metrics.py`), cần thay đơn giá thật khi triển khai.

---

## 4. Root Cause Analysis (RCA) — Failure Traces

### Case A — Vòng lặp chạm `max_steps` (thiếu "Final Answer:")
- **Hiện tượng**: tác vụ đặt lịch gom đủ dữ liệu (3 tool) nhưng không kết thúc → chạm `max_steps`.
- **Root Cause**: model viết câu trả lời nhưng **quên prefix `Final Answer:`** → vòng lặp không nhận ra đã xong (xác định qua log `AGENT_STEP`).
- **Fix**: thêm **salvage** (coi nội dung không-Action là Final Answer) + mồi `Thought:` (CONTINUE_CUE) + nâng `max_steps` 6→8.

### Case B — Bịa lượt hội thoại mới
- **Hiện tượng**: sau khi trả lời đúng, model tự sinh dòng `User: …` rồi đi lạc đề.
- **Fix**: `_truncate()` cắt output tại `Observation:`/`User:`/`Question:`.

### Case C — Mất ngữ cảnh ("có" không hiểu)
- **Hiện tượng**: người dùng xác nhận "có" → agent quên đề xuất trước đó.
- **Fix**: thêm **bộ nhớ hội thoại** (`_build_transcript`/`_remember`).

### Case D — Telemetry token = 0 (Gemini)
- **Root Cause**: SDK không trả `usage_metadata`. **Fix**: fallback `count_tokens`.

### Case E — Pin Google Maps sai
- **Root Cause**: dùng toạ độ nhập tay (lệch ~1km). **Fix**: dùng **tên + địa chỉ** làm `destination` để Google tự geocode.

---

## 5. Ablation Studies & Experiments

### Experiment 1: Prompt/Loop v1 → v2
| | v1 (cơ bản) | v2 (hiện tại) |
| :--- | :--- | :--- |
| Cấu hình | ReAct tối giản, không cue, không memory, max_steps=5 | + CONTINUE_CUE + truncate + salvage + memory + emergency/guardrail |
| Lỗi | Lặp vô hạn, bịa lượt User, không xác nhận đặt lịch | Hết các lỗi trên |
| Kết quả test | nhiều case fail | **16/16** |

### Experiment 2 (định tính): Chatbot vs Agent
| Case | Chatbot thuần | ReAct Agent | Winner |
| :--- | :--- | :--- | :--- |
| Hỏi giá đơn giản | Có thể đúng nếu thuộc giá | Đúng (tra tool) | Hòa |
| Giá + bảo hiểm (nhiều bước) | Dễ tính sai/bịa | Đúng (chuỗi tool) | **Agent** |
| "Vinmec gần tôi nhất" | Bịa địa chỉ | Định vị thật + chỉ đường | **Agent** |
| Đặt lịch + xác nhận "có" | Không có trạng thái | Nhớ ngữ cảnh, đặt được | **Agent** |
| Cấp cứu | Trả lời chung chung | 115 + sơ cứu đúng | **Agent** |

> Lưu ý: cột Chatbot phản ánh **chế độ thất bại đã biết** (không có tool → hallucination); nhóm tập trung benchmark định lượng cho Agent.

---

## 6. Production Readiness Review

- **Security**: giới hạn độ dài tin nhắn (500 ký tự), **rate limiting** chống spam (≤15 tin/phút, ≥2s/tin theo IP), guardrail giới hạn phạm vi.
- **Guardrails**: trần `max_steps`, từ chối câu hỏi ngoài phạm vi, **ưu tiên cấp cứu** (115 + sơ cứu), xử lý lỗi → thông báo thân thiện thay vì traceback.
- **Safety (y tế)**: hướng dẫn sơ cứu chỉ mang tính tham khảo; số cấp cứu dùng **115** (chính xác); cần disclaimer y tế rõ ràng khi triển khai thật.
- **Scaling**: bộ nhớ hiện theo 1 instance dùng chung → cần **tách theo session**; chuyển lịch/giá sang **DB**; dùng **Google Places/Distance Matrix** + hotline đã xác minh; cân nhắc LangGraph/RAG khi số chuyên khoa lớn.

---

> [!NOTE]
> Đổi tên file thành `GROUP_REPORT_[TEAM_NAME].md` trước khi nộp.
