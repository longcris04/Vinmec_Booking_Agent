# Lab 3 Report — Trợ lý ảo Vinmec (ReAct Agent)

- **Student Name**: Nguyễn Hoàng Long
- **Student ID**: 2A202600785
- **Date**: 01/06/2026

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

### 2.3 LLM Providers

- **Primary**: Gemini 2.5 Flash (`gemini-2.5-flash`).
- **Hỗ trợ**: OpenAI GPT-4o, OpenRouter, Llama 3.1 8B local (qua Ollama) — chuyển đổi qua `.env` (`DEFAULT_PROVIDER`).

---

## 3. Technical Contribution

Trong lab này, tôi tập trung vào phần telemetry để biến agent từ một skeleton khó debug thành một hệ thống có trace rõ ràng. Cụ thể, tôi chuẩn hóa đo lường token, cost và latency trong [src/telemetry/metrics.py](../../src/telemetry/metrics.py), đồng thời chuẩn hóa log có cấu trúc trong [src/telemetry/logger.py](../../src/telemetry/logger.py).

- **Modules Implemented**: [src/telemetry/metrics.py](../../src/telemetry/metrics.py), [src/telemetry/logger.py](../../src/telemetry/logger.py)
- **Code Highlights**:
	- `PerformanceTracker.track_request()` lưu lại `prompt_tokens`, `completion_tokens`, `total_tokens`, `latency_ms` và `cost_estimate` cho từng request.
	- `logger.log_event()` ghi payload theo format JSON với ba trường chính: `timestamp`, `event`, `data`.
	- Trace của agent có thể được nối lại thành chuỗi sự kiện `AGENT_START -> AGENT_STEP_OUTPUT/AGENT_ACTION -> AGENT_FINAL -> AGENT_END`, giúp theo dõi toàn bộ vòng lặp ReAct.
- **Documentation**: Thiết kế này giúp tách bạch giữa logic suy luận của agent và lớp quan sát hệ thống. Khi agent gọi model hoặc tool, chỉ cần nhìn log JSON là biết request nào tốn bao nhiêu token, chạy bao lâu và dừng ở bước nào.

---

## 4. Telemetry & Performance Dashboard

Đo trên bộ kiểm thử 16 case (mỗi lần gọi LLM ghi token/latency/cost qua `PerformanceTracker`):

- **Tổng token cả suite**: ~109,000 tokens.
- **Average Latency / lần gọi LLM**: ~2,100 ms.
- **Tokens / task**: câu đơn ~600–700 (1 bước); tác vụ đặt lịch nhiều bước ~2,500–3,000 (3–4 bước).
- **Cost (ước tính)**: ~$1.09 cho cả suite — **lưu ý**: công thức cost hiện là mô phỏng ($0.01/1k token trong `metrics.py`), cần thay đơn giá thật khi triển khai.

---

## 5. Debugging & Root Cause Analysis

### 5.1 Root Cause Analysis (RCA)

**Case A — Vòng lặp chạm `max_steps` (thiếu "Final Answer:")**
- **Hiện tượng**: tác vụ đặt lịch gom đủ dữ liệu (3 tool) nhưng không kết thúc → chạm `max_steps`.
- **Root Cause**: model viết câu trả lời nhưng **quên prefix `Final Answer:`** → vòng lặp không nhận ra đã xong (xác định qua log `AGENT_STEP`).
- **Fix**: thêm **salvage** (coi nội dung không-Action là Final Answer) + mồi `Thought:` (CONTINUE_CUE) + nâng `max_steps` 6→8.

**Case B — Bịa lượt hội thoại mới**
- **Hiện tượng**: sau khi trả lời đúng, model tự sinh dòng `User: …` rồi đi lạc đề.
- **Fix**: `_truncate()` cắt output tại `Observation:`/`User:`/`Question:`.

**Case C — Mất ngữ cảnh ("có" không hiểu)**
- **Hiện tượng**: người dùng xác nhận "có" → agent quên đề xuất trước đó.
- **Fix**: thêm **bộ nhớ hội thoại** (`_build_transcript`/`_remember`).

**Case D — Telemetry token = 0 (Gemini)**
- **Root Cause**: SDK không trả `usage_metadata`. **Fix**: fallback `count_tokens`.

**Case E — Pin Google Maps sai**
- **Root Cause**: dùng toạ độ nhập tay (lệch ~1km). **Fix**: dùng **tên + địa chỉ** làm `destination` để Google tự geocode.

### 5.2 Debugging Case Study (Telemetry)

Một lỗi hữu ích để phân tích là trường hợp agent nhận câu hỏi "Tôi muốn tìm bệnh viện gần nhất" nhưng lại đi qua tool `emergency` thay vì một luồng tìm kiếm địa điểm rõ ràng.

- **Problem Description**: Agent chọn tool chưa thật sự chính xác với ý định người dùng, vì prompt và mô tả tool còn đủ rộng để model gán nhầm intent.
- **Diagnosis**: Vấn đề không nằm ở việc thiếu trace, mà ở chỗ trace đã cho thấy ngay bước chọn action. Log JSON làm rõ raw input, tên tool được gọi và payload từng bước, nên có thể thấy lỗi xuất phát từ prompt/tool spec hơn là từ output cuối cùng.
- **Solution**: Chuẩn hóa log và dùng trace theo từng bước để khoanh vùng lỗi. Hướng sửa hợp lý là làm rõ mô tả tool, siết format `Action`, và tách các intent như cấp cứu, tìm cơ sở y tế, và hỗ trợ vị trí thành các tool/luồng riêng biệt hơn.

---

## 6. Ablation Studies & Experiments

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

---

## 7. Insights: Chatbot vs ReAct Agent

1. **Reasoning**: `Thought` block giúp agent bộc lộ bước suy luận trung gian, nên có thể kiểm tra tại sao nó chọn một action thay vì chỉ thấy một câu trả lời cuối cùng. Với chatbot thuần, lỗi thường bị "ẩn" trong một response duy nhất; với ReAct, trace cho thấy từng quyết định.
2. **Reliability**: Agent có thể tệ hơn chatbot khi prompt chưa đủ chặt, vì model sẽ "hành động" sớm và dễ chọn sai tool. Trong các câu hỏi ngắn, rõ nghĩa, chatbot đôi khi lại an toàn hơn vì không có chi phí sai tool hoặc sai vòng lặp.
3. **Observation**: Phần observation là tín hiệu quan trọng nhất để agent tự sửa hướng đi. Khi observation phù hợp, agent có thể chuyển sang `Final Answer` rất nhanh; khi observation mơ hồ, nó sẽ lặp sai hoặc đi lạc sang action khác.

---

## 8. Production Readiness & Future Improvements

### 8.1 Production Readiness

- **Security**: giới hạn độ dài tin nhắn (500 ký tự), **rate limiting** chống spam (≤15 tin/phút, ≥2s/tin theo IP), guardrail giới hạn phạm vi.
- **Guardrails**: trần `max_steps`, từ chối câu hỏi ngoài phạm vi, **ưu tiên cấp cứu** (115 + sơ cứu), xử lý lỗi → thông báo thân thiện thay vì traceback.
- **Safety (y tế)**: hướng dẫn sơ cứu chỉ mang tính tham khảo; số cấp cứu dùng **115** (chính xác); cần disclaimer y tế rõ ràng khi triển khai thật.
- **Scaling**: bộ nhớ hiện theo 1 instance dùng chung → cần **tách theo session**; chuyển lịch/giá sang **DB**; dùng **Google Places/Distance Matrix** + hotline đã xác minh; cân nhắc LangGraph/RAG khi số chuyên khoa lớn.

### 8.2 Future Improvements

- **Scalability**: Thêm job queue hoặc async executor cho tool calls để tránh chặn luồng chính khi agent xử lý nhiều request đồng thời.
- **Safety**: Gắn correlation ID cho mỗi phiên và thêm guardrail để giới hạn số vòng lặp, tránh agent chạy quá lâu hoặc sinh chi phí không cần thiết.
- **Performance**: Thay mock cost bằng bảng giá thật theo provider/model, và bổ sung parser đọc log JSONL để tổng hợp dashboard về token, latency và error rate.
