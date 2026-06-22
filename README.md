# Vinmec ReAct Agent

Trợ lý ảo bệnh viện **Vinmec** xây dựng trên **ReAct Agent viết tay** (Thought → Action → Observation). Agent gọi tool để lấy dữ liệu thật thay vì "bịa" câu trả lời như chatbot thông thường.

**Tác giả:** Nguyễn Hoàng Long — 2A202600785

---

## Tính năng

- Tra giá dịch vụ khám và ước tính chi phí sau bảo hiểm
- Tìm cơ sở Vinmec gần nhất + chỉ đường Google Maps
- Kiểm tra lịch bác sĩ theo chuyên khoa và đặt lịch hẹn
- Suy luận chuyên khoa từ triệu chứng người dùng mô tả
- Hỗ trợ cấp cứu: gọi 115, hướng dẫn sơ cứu tức thì
- Từ chối câu hỏi ngoài phạm vi y tế (guardrail)
- Web demo (Flask) với trace ReAct, card bản đồ, card cấp cứu

---

## Yêu cầu

- Python **3.10+**
- (Tuỳ chọn) [Ollama](https://ollama.com) nếu chạy local LLM

---

## Cài đặt

```bash
# 1. Clone repo
git clone <repo-url>
cd Vinmec_Booking_Agent

# 2. Tạo virtual environment (khuyến nghị)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 3. Cài thư viện
pip install -r requirements.txt
```

---

## Cấu hình môi trường

Sao chép file mẫu rồi điền API key:

```bash
cp .env.example .env
```

Nội dung `.env`:

```env
# Chọn provider: openai | google | openrouter | local
DEFAULT_PROVIDER=openrouter

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash

# OpenAI
OPENAI_API_KEY=your_openai_api_key
DEFAULT_MODEL=gpt-4o

# OpenRouter (nhiều model, 1 API key)
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=google/gemini-3.1-flash-lite

# Local LLM via Ollama
OLLAMA_MODEL=llama3.1:8b
OLLAMA_BASE_URL=http://localhost:11434
```

> Chỉ cần điền key của provider bạn chọn dùng.

---

## Chạy ứng dụng

### CLI (terminal)

```bash
python main.py
```

Nhập câu hỏi hoặc nhấn Enter để dùng câu mẫu mặc định.

### Web Demo (Flask)

```bash
python app.py
```

Mở trình duyệt tại **http://localhost:5000**

Giao diện web hỗ trợ:
- Chat realtime với agent
- Tự động xin vị trí GPS từ trình duyệt
- Hiển thị trace ReAct (Thought / Action / Observation)
- Card chỉ đường Google Maps
- Card cấp cứu với hướng dẫn sơ cứu
- Metrics mỗi lượt: số bước, token, latency, cost

---

## Chạy với Local LLM (Ollama)

```bash
# 1. Cài Ollama: https://ollama.com/download

# 2. Pull model
ollama pull llama3.1:8b

# 3. Đặt provider trong .env
DEFAULT_PROVIDER=local

# 4. Chạy bình thường
python main.py
# hoặc
python app.py
```

> Llama 3.1 8B yêu cầu ~5 GB RAM. Ollama tự chạy service khi khởi động Windows.

---

## Chạy test

```bash
# Bộ 16 test case chính (Dễ → Rất khó)
python tests/test_case.py

# Test riêng Ollama provider
python tests/test_local.py
```

Kết quả mẫu:

```
=== KIỂM THỬ 16 CASE | model: google/gemini-3.1-flash-lite ===

[L1-01 | 1-Dễ      | PASS ✅] Tra giá 1 dịch vụ
[L2-02 | 2-TB      | PASS ✅] Giá + bảo hiểm (Vinmec Care -70%)
[L3-01 | 3-Khó     | PASS ✅] Tìm cơ sở gần nhất (định vị)
[L4-03 | 4-Rất khó | PASS ✅] Cấp cứu đau ngực: 115 + sơ cứu
...

================================================================
  TỔNG    : 16/16 (100%)
  Token   : 100524 | Latency TB: 1643 ms | Cost: $1.0052
================================================================
```

---

## Cấu trúc thư mục

```
Vinmec_Booking_Agent/
├── main.py                         # CLI entry point
├── app.py                          # Web demo (Flask)
├── requirements.txt
├── .env.example
│
├── src/
│   ├── agent/agent.py              # ReActAgent — vòng lặp ReAct
│   ├── core/
│   │   ├── llm_provider.py         # Abstract base class
│   │   ├── openai_provider.py
│   │   ├── gemini_provider.py
│   │   ├── openrouter_provider.py
│   │   └── local_provider.py       # Ollama provider
│   ├── tools/
│   │   ├── vinmec_tools.py         # 8 tool definitions
│   │   └── vinmec_data.json        # Dữ liệu mock (cơ sở, giá, lịch, sơ cứu)
│   └── telemetry/
│       ├── logger.py               # Structured JSON logging
│       └── metrics.py              # Token / latency / cost tracking
│
├── templates/index.html            # Web chat UI
├── tests/
│   ├── test_case.py                # 16 test cases phân cấp
│   └── test_local.py               # Test Ollama provider
└── report/
    └── individual_reports/
        └── REPORT_Nguyen_Hoang_Long_2A202600785.md
```

---

## Các provider được hỗ trợ

| `DEFAULT_PROVIDER` | Model mặc định | Yêu cầu |
|---|---|---|
| `google` | `gemini-2.5-flash` | `GEMINI_API_KEY` |
| `openrouter` | `google/gemini-3.1-flash-lite` | `OPENROUTER_API_KEY` |
| `openai` | `gpt-4o` | `OPENAI_API_KEY` |
| `local` | `llama3.1:8b` | Ollama đang chạy |

---

## 8 Tools của Agent

| Tool | Chức năng |
|---|---|
| `get_current_location` | Định vị người dùng (GPS → IP → fallback) |
| `find_nearest_vinmec` | Cơ sở Vinmec gần nhất (Haversine) |
| `get_service_price` | Giá dịch vụ khám |
| `apply_insurance` | Tính chi phí sau bảo hiểm |
| `check_doctor_availability` | Kiểm tra lịch bác sĩ |
| `book_appointment` | Đặt lịch + sinh mã xác nhận |
| `get_emergency_contact` | Số cấp cứu 115 + cơ sở gần nhất |
| `get_first_aid` | Hướng dẫn sơ cứu theo tình trạng |
