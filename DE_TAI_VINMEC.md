# Đề tài: Trợ lý Đặt lịch & Ước tính Chi phí khám Vinmec (ReAct Agent)

> File này là **bản brief đề tài** dùng để cung cấp ngữ cảnh cho AI (Copilot/Claude/Cursor...) khi vibe coding.
> Đọc file này trước khi nhờ AI sinh code, để AI hiểu đúng mục tiêu, ràng buộc và kiến trúc.

---

## 1. Bối cảnh & Mục tiêu

Đây là **Lab 3** của môn Agentic AI: xây dựng một **ReAct Agent** (Reasoning + Acting) thay cho chatbot LLM thông thường, có **telemetry/monitoring** theo chuẩn công nghiệp.

**Tác giả:** Nguyễn Hoàng Long — 2A202600785

**Sản phẩm:** Trợ lý ảo của bệnh viện **Vinmec** giúp người dùng:
- Tra lịch trống của bác sĩ theo chuyên khoa.
- Tra giá dịch vụ khám và ước tính chi phí sau bảo hiểm.
- Tìm cơ sở Vinmec gần nhất và chỉ đường.
- Đặt lịch hẹn và nhận mã xác nhận.
- Hỗ trợ khẩn cấp: gọi 115, hướng dẫn sơ cứu theo tình trạng.

**Insight cốt lõi cần chứng minh:** Chatbot thường giỏi *nói chuyện* nhưng *bịa số* ở bài toán nhiều bước. ReAct Agent gọi **tool** để lấy dữ liệu thật → trả lời chính xác. Bài lab phải cho thấy rõ sự khác biệt này.

**Trạng thái:** ✅ Hoàn thành — **16/16 test case (100%)** trên bộ kiểm thử phân cấp Dễ → Rất khó.

---

## 2. Mô hình ReAct (Thought → Action → Observation)

Agent lặp theo chu trình cho tới khi ra `Final Answer`:

```
Thought: suy luận bước tiếp theo cần làm gì
Action: tool_name(arg1=..., arg2=...)
Observation: <kết quả tool do CODE chèn vào, không phải LLM tự bịa>
... (lặp lại Thought/Action/Observation) ...
Final Answer: câu trả lời cuối cho người dùng
```

**Quy ước Action:** `Action: tool_name(arg1=..., arg2=...)`

**Cơ chế chống lỗi đã triển khai:**
- **CONTINUE_CUE** (`Thought:`): mồi LLM tiếp tục thay vì restart.
- **`_truncate()`**: cắt output tại `Observation:`/`User:`/`Question:` để chống LLM tự bịa lượt hội thoại.
- **Salvage**: nếu output không có `Action:` nhưng có nội dung → coi là `Final Answer`.
- **Bộ nhớ hội thoại**: `_build_transcript` / `_remember` giúp giữ ngữ cảnh đa lượt.
- **`max_steps = 8`**: giới hạn an toàn.

---

## 3. Bộ công cụ (Tools) — 8 tools

Tất cả tool là **hàm Python với dữ liệu mock** từ `src/tools/vinmec_data.json`, trả về observation ngắn gọn.

| Tool | Input | Use Case |
| :--- | :--- | :--- |
| `get_current_location` | — | Định vị người dùng (GPS trình duyệt → IP → fallback) |
| `find_nearest_vinmec` | lat, lon | Cơ sở Vinmec gần nhất (Haversine) + link Google Maps |
| `get_service_price` | service_name | Giá dịch vụ khám (VND) |
| `apply_insurance` | price, insurance_type | Số tiền phải trả sau bảo hiểm |
| `check_doctor_availability` | specialty, date | Lịch bác sĩ (lọc theo quy tắc đặt trước ≥ 30 phút) |
| `book_appointment` | specialty, time, doctor | Xác nhận đặt lịch + sinh mã VM##### |
| `get_emergency_contact` | lat, lon | Số cấp cứu 115 + cơ sở Vinmec gần nhất |
| `get_first_aid` | condition | Hướng dẫn sơ cứu theo tình trạng (đau ngực, đột quỵ, co giật…) |

**Dữ liệu mock** (tất cả trong `src/tools/vinmec_data.json`):
- **Cơ sở:** Times City (HN), Central Park (HCM), Đà Nẵng, Nha Trang, Hạ Long, Phú Quốc.
- **Bảo hiểm:** `Vinmec Care` (−70%), `Bảo Việt` (−50%), `Không` (0%).
- **Giá khám:** Tim mạch 500k, Da liễu 300k, Nhi 250k, Tiêu hóa 400k, Chấn thương chỉnh hình 350k…
- **Alias chuyên khoa:** "xương khớp" → Chấn thương chỉnh hình, "bụng" → Tiêu hóa…

---

## 4. Bộ test case (16 case — phân cấp)

| Level | Mô tả | Kết quả |
| :--- | :--- | :--- |
| L1 — Dễ (3 case) | Tra giá 1 dịch vụ, tra lịch đơn | **3/3 ✅** |
| L2 — Trung bình (3 case) | Giá + bảo hiểm, edge case khoa không tồn tại | **3/3 ✅** |
| L3 — Khó (5 case) | Định vị, suy ra chuyên khoa từ triệu chứng, guardrail ngoài phạm vi | **5/5 ✅** |
| L4 — Rất khó (5 case) | Hội thoại đa lượt, bộ nhớ context, cấp cứu + sơ cứu | **5/5 ✅** |
| **Tổng** | | **16/16 (100%) ✅** |

**Telemetry thực tế** (OpenRouter — `google/gemini-3.1-flash-lite`):
- Token tiêu thụ: ~100,500 tokens / cả suite.
- Latency trung bình: ~1,640 ms / lần gọi LLM.
- Chi phí ước tính: ~$1.00 / cả suite.

---

## 5. Kiến trúc & cấu trúc thư mục

```
Vinmec_Booking_Agent/
├── main.py                         # CLI entry point
├── app.py                          # Web demo (Flask) — http://localhost:5000
├── requirements.txt
├── .env / .env.example
│
├── src/
│   ├── agent/agent.py              # ReActAgent: vòng lặp ReAct hoàn chỉnh
│   ├── core/
│   │   ├── llm_provider.py         # Abstract base class
│   │   ├── openai_provider.py      # GPT-4o
│   │   ├── gemini_provider.py      # Gemini 2.5 Flash
│   │   ├── openrouter_provider.py  # OpenRouter (nhiều model)
│   │   └── local_provider.py       # Llama 3.1 8B via Ollama
│   ├── tools/
│   │   ├── vinmec_tools.py         # 8 tool definitions
│   │   └── vinmec_data.json        # Toàn bộ dữ liệu mock
│   └── telemetry/
│       ├── logger.py               # Structured JSON logging
│       └── metrics.py              # PerformanceTracker (token/latency/cost)
│
├── templates/index.html            # Web chat UI (dùng với app.py)
├── tests/
│   ├── test_case.py                # Bộ 16 test case chính
│   └── test_local.py               # Test riêng Ollama provider
└── report/
    └── individual_reports/
        └── REPORT_Nguyen_Hoang_Long_2A202600785.md
```

---

## 6. Ràng buộc kỹ thuật

1. **Chống bịa Observation:** LLM phải DỪNG trước khi tự sinh `Observation:`. Vòng lặp agent dùng `_truncate()` để cắt phần bịa, kết hợp `stop` tokens ở provider.
2. **Parser bền vững:** Dùng AST (`ast.parse`) thay vì regex để parse `tool(arg=value)` — an toàn hơn với các format LLM trả về.
3. **Provider switching:** Đọc `DEFAULT_PROVIDER` từ `.env` (`openai` | `google` | `openrouter` | `local`).
4. **Telemetry:** Mọi lần gọi LLM ghi qua `tracker.track_request()` — token, latency, cost estimate.
5. **Rate limiting (web):** ≤15 tin/phút, ≥2s/tin theo IP; độ dài tin nhắn ≤500 ký tự.
6. **Guardrail y tế:** Câu hỏi ngoài phạm vi bị từ chối; tình huống cấp cứu được ưu tiên xử lý ngay (115 + sơ cứu) trước khi tư vấn đặt lịch.

---

## 7. Mô hình & cấu hình

| Provider | Model | Khi nào dùng |
| :--- | :--- | :--- |
| `google` | `gemini-2.5-flash` | Primary — chất lượng cao, có quota miễn phí |
| `openrouter` | `google/gemini-3.1-flash-lite` (mặc định) | Linh hoạt — đổi model qua `OPENROUTER_MODEL` |
| `openai` | `gpt-4o` | Backup, so sánh chất lượng |
| `local` | `llama3.1:8b` via Ollama | Offline/không tốn API cost |

**Cấu hình `.env`:**
```env
DEFAULT_PROVIDER=openrouter        # openai | google | openrouter | local
GEMINI_API_KEY=...
OPENAI_API_KEY=...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=google/gemini-3.1-flash-lite
OLLAMA_MODEL=llama3.1:8b           # dùng khi DEFAULT_PROVIDER=local
OLLAMA_BASE_URL=http://localhost:11434
```

**Chạy local LLM (Ollama):**
```bash
ollama pull llama3.1:8b
# Đặt DEFAULT_PROVIDER=local trong .env
python main.py
```

---

## 8. Tiêu chí chấm điểm (tham chiếu SCORING.md)

- **Kỹ thuật:** Chatbot baseline → Agent v1 → Agent v2 (cải tiến), tool design, chất lượng trace, đánh giá, code quality.
- **Cá nhân (40đ):** Đóng góp kỹ thuật (telemetry), debugging case study từ log, insight chatbot vs agent, đề xuất tương lai.
- **Triết lý:** *"Fail Early, Learn Fast"* — một trace lỗi được phân tích kỹ giá trị hơn một hệ thống "hoàn hảo" không giải thích được.
