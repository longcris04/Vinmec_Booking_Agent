# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Phùng Bá Quân
- **Student ID**: 2A202600866
- **Date**: 01/06/2026

---

## I. Technical Contribution (15 Points)

### 1) Scope phụ trách
Tôi đảm nhiệm vai trò Người 3 (Provider + Runtime Integration), tập trung vào:
- Provider switching và model configuration theo biến môi trường trong `main.py`.
- Căn chỉnh adapter của 3 provider để trả về schema thống nhất cho agent:
  - `src/core/openai_provider.py`
  - `src/core/gemini_provider.py`
  - `src/core/local_provider.py`

### 2) Các thay đổi kỹ thuật chính
- Implement hàm `get_provider()` để switch provider dựa trên `DEFAULT_PROVIDER` trong `.env`.
- Tách cấu hình model theo provider:
  - OpenAI dùng `DEFAULT_MODEL`.
  - Gemini dùng `GEMINI_MODEL` (không dùng chung với OpenAI).
  - Local dùng `LOCAL_MODEL_PATH`.
- Chuẩn hóa schema output cho tất cả provider theo dạng:
  - `content`
  - `usage` (`prompt_tokens`, `completion_tokens`, `total_tokens`)
  - `latency_ms`
  - `provider`
- Bổ sung cơ chế fallback trong Gemini khi SDK không trả `usage_metadata`:
  - Thử đọc metadata an toàn.
  - Nếu token = 0 thì ước lượng bằng `count_tokens`.

### 3) Code highlights
#### a) Provider switching tại runtime
```python
def get_provider():
    provider = os.getenv("DEFAULT_PROVIDER", "google").lower()

    if provider == "openai":
        return OpenAIProvider(
            model_name=os.getenv("DEFAULT_MODEL", "gpt-4o"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    if provider == "google":
        return GeminiProvider(
            model_name=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            api_key=os.getenv("GEMINI_API_KEY"),
        )
    if provider == "local":
        return LocalProvider(model_path=os.getenv("LOCAL_MODEL_PATH"))

    raise ValueError(f"DEFAULT_PROVIDER không hợp lệ: {provider}")
```

  #### b) Response schema thống nhất cho agent
```python
return {
    "content": content,
    "usage": usage,
    "latency_ms": latency_ms,
    "provider": "google"
}
```

### 4) Giá trị mang lại cho hệ thống
- Runtime dễ mở rộng: đổi provider bằng 1 biến môi trường, không cần sửa logic agent.
- Dễ theo dõi telemetry: cùng một schema giúp tracker và logger xử lý đồng nhất.
- Dễ benchmark Chatbot vs Agent: có dữ liệu token/latency để so sánh giữa OpenAI, Gemini, Local.


---

## II. Debugging Case Study (10 Points)

### 1) Problem description
Trong giai đoạn đầu với Gemini, log ghi nhận nhiều request có:
- `prompt_tokens = 0`
- `completion_tokens = 0`
- `total_tokens = 0`

dẫn đến `cost_estimate = 0.0`, làm sai lệch phần telemetry và evaluation.

### 2) Log source (trích từ hệ thống)
Từ file log ngày 2026-06-01:
```json
{"event":"LLM_METRIC","data":{"provider":"google","model":"gemini-2.5-flash","prompt_tokens":0,"completion_tokens":0,"total_tokens":0,"latency_ms":3430,"cost_estimate":0.0}}
```

Sau khi fix adapter, log đã có token hợp lệ:
```json
{"event":"LLM_METRIC","data":{"provider":"google","model":"gemini-2.5-flash","prompt_tokens":479,"completion_tokens":142,"total_tokens":621,"latency_ms":2679,"cost_estimate":0.00621}}
```

### 3) Diagnosis
Nguyên nhân là sự khác biệt giữa các phiên bản SDK Gemini:
- Thuộc tính `usage_metadata` không phải lúc nào cũng có sẵn ở cùng một vị trí.
- Adapter cũ đọc metadata theo một đường duy nhất, nên một số response bị mất token metrics.

### 4) Solution
- Đọc metadata theo cách an toàn (`_result.usage_metadata` hoặc `usage_metadata`).
- Nếu vẫn không có token thì fallback bằng `model.count_tokens(...)`.
- Chuẩn hóa output schema để telemetry nhận dữ liệu đầy đủ.

### 5) Kết quả
- Token/cost metric không còn bằng 0 giả tạo.
- Dashboard log phản ánh đúng chi phí và hiệu năng provider.
- Tạo nền tảng để so sánh công bằng giữa các provider trong phần test/evaluation.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**
ReAct có lợi thế rõ ở bài toán nhiều bước (ví dụ: tìm giá dịch vụ rồi áp bảo hiểm), vì nó tự chia nhỏ bài toán qua Thought -> Action -> Observation. Chatbot thường trả lời trực tiếp, dễ thiếu bước hoặc thiếu căn cứ tool.

2. **Reliability**
Agent có thể tệ hơn chatbot nếu output parser không ổn định hoặc model lặp Action (loop). Thực tế log có case lặp `get_service_price("Kham Nhi")` nhiều lần đến `max_steps`, trong khi chatbot có thể đưa ra câu trả lời ngắn ngay.

3. **Observation impact**
Observation ngắn, rõ ràng giúp model ra quyết định tiếp theo chính xác hơn. Nếu observation dài, mơ hồ hoặc thiếu cấu trúc thì model dễ lặp và tốn thêm token.

---

## IV. Future Improvements (5 Points)

- **Scalability**
  - Triển khai provider registry theo pattern plugin để bổ sung provider mới mà không sửa `main.py`.
  - Tách benchmark harness riêng để so sánh latency/token theo batch test.

- **Safety**
  - Validate schema response bằng Pydantic trước khi đưa vào ReAct loop.
  - Thêm guardrail cho Action repeat (nếu trùng Action quá N lần thì ép tổng kết).

- **Performance**
  - Cache kết quả tool cho truy vấn lặp.
  - Bật retry có backoff cho lỗi mạng ở provider API.
  - Tối ưu max_steps theo loại câu hỏi để giảm token không cần thiết.

---

## V. Self-Evaluation
- Mức độ hoàn thành vai trò: **Đạt**
- Ảnh hưởng đến nhóm:
  - Đảm bảo hệ thống chạy đa provider ổn định.
  - Cung cấp token/latency metric đúng để P4-P5 phân tích và báo cáo.
  - Giảm rủi ro integration giữa agent core và telemetry.

---

