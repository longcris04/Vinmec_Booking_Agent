# Đề tài: Trợ lý Đặt lịch & Ước tính Chi phí khám Vinmec (ReAct Agent)

> File này là **bản brief đề tài** dùng để cung cấp ngữ cảnh cho AI (Copilot/Claude/Cursor...) khi vibe coding.
> Đọc file này trước khi nhờ AI sinh code, để AI hiểu đúng mục tiêu, ràng buộc và kiến trúc.

---

## 1. Bối cảnh & Mục tiêu

Đây là **Lab 3** của môn Agentic AI: xây dựng một **ReAct Agent** (Reasoning + Acting) thay cho chatbot LLM thông thường, có **telemetry/monitoring** theo chuẩn công nghiệp.

**Sản phẩm:** Trợ lý ảo của bệnh viện **Vinmec** giúp người dùng:
- Tra lịch trống của bác sĩ theo chuyên khoa.
- Tra giá dịch vụ khám.
- Ước tính số tiền phải trả sau khi áp bảo hiểm.

**Insight cốt lõi cần chứng minh:** Chatbot thường giỏi *nói chuyện* nhưng *bịa số* ở bài toán nhiều bước. ReAct Agent gọi **tool** để lấy dữ liệu thật → trả lời chính xác. Bài lab phải cho thấy rõ sự khác biệt này.

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

**Quy ước Action thống nhất toàn nhóm:** `Action: tool_name(arg1=..., arg2=...)`

---

## 3. Bộ công cụ (Tools) — 4 tool lõi

Tất cả tool là **hàm Python với dữ liệu mock**, trả về **observation NGẮN GỌN** (số hoặc 1 dòng).

| Tool | Input | Output (mock) |
| :--- | :--- | :--- |
| `find_nearest_vinmec(location)` | địa điểm/quận của người dùng | Cơ sở Vinmec gần nhất + khoảng cách |
| `check_doctor_availability(specialty, date)` | chuyên khoa, ngày | Khung giờ trống + tên bác sĩ |
| `get_service_price(service_name)` | tên dịch vụ | Giá dịch vụ (VND) |
| `apply_insurance(price, insurance_type)` | giá gốc, loại BH | Số tiền phải trả sau bảo hiểm |

**Dữ liệu mock gợi ý:**
- Cơ sở Vinmec: `Times City (Hà Nội)`, `Central Park (TP.HCM)`, `Đà Nẵng`, `Nha Trang`, `Hạ Long`. Map quận/thành phố → cơ sở gần nhất + khoảng cách (km).
- Chuyên khoa: `Tim mạch`, `Da liễu`, `Nhi`, `Thần kinh`.
- Bảo hiểm: `Vinmec Care` (giảm 70%), `Bảo Việt` (giảm 50%), `Không` (0%).
- Giá: Khám Tim mạch 500.000đ, Da liễu 300.000đ, Nhi 250.000đ...

**(Bonus)** Tool thứ 5: `book_appointment(specialty, time)` → xác nhận đặt lịch.

---

## 4. Test case lõi (bắt buộc chạy được)

> *"Tôi ở Cầu Giấy, muốn khám Tim mạch tuần này ở Vinmec gần nhất, dùng gói Vinmec Care, tổng tiền tôi phải trả là bao nhiêu?"*

Chuỗi mong đợi của agent:
1. `find_nearest_vinmec("Cầu Giấy")` → Vinmec Times City, cách 5km.
2. `check_doctor_availability("Tim mạch", "tuần này")` → có lịch trống.
3. `get_service_price("Khám Tim mạch")` → 500.000đ.
4. `apply_insurance(500000, "Vinmec Care")` → 150.000đ.
5. `Final Answer`: cơ sở gần nhất là Times City, còn lịch ngày X, chi phí sau bảo hiểm là **150.000đ**.

> ⚠️ Với Phi-3 (4K context, `max_steps=3`), test 4 tool có thể tràn bước — dùng test case 3 tool (bỏ `find_nearest`) cho model local, và test 4 tool cho gpt-4o/gemini.

---

## 5. Kiến trúc & cấu trúc thư mục

```
src/
├── agent/agent.py          # ReActAgent: vòng lặp Thought-Action-Observation (CẦN HOÀN THIỆN)
├── core/                   # ĐÃ XONG: các LLM provider
│   ├── llm_provider.py     #   - interface trừu tượng
│   ├── openai_provider.py  #   - gpt-4o
│   ├── gemini_provider.py  #   - gemini-1.5-flash
│   └── local_provider.py   #   - Phi-3-mini (GGUF, chạy CPU)
├── telemetry/
│   ├── logger.py           # ĐÃ XONG: log JSON ra logs/
│   └── metrics.py          # CẦN HOÀN THIỆN: _calculate_cost()
└── tools/                  # CẦN TẠO MỚI: vinmec_tools.py

# File cần tạo thêm: main.py, chatbot.py, analyze_logs.py, tests/test_cases.py
```

---

## 6. Ràng buộc kỹ thuật (RẤT QUAN TRỌNG khi vibe code)

1. **Context window nhỏ:** Model local Phi-3-mini chỉ có **4.096 token**. Vì vòng lặp ReAct tích lũy lịch sử → **observation phải ngắn**, `max_steps = 3`. Nếu không, agent tràn context → lặp vô hạn.
2. **Chống bịa Observation:** LLM phải DỪNG trước khi tự sinh `Observation:`. Provider local đã có sẵn `stop=["Observation:"]` — code mới là nơi thực thi tool và chèn observation thật.
3. **Parser bền vững:** LLM hay xuất markdown ```` ```json ... ``` ````, thừa khoảng trắng, hoặc sai format. Parser (regex) phải xử lý các trường hợp này.
4. **Provider switching:** đọc `DEFAULT_PROVIDER` từ `.env` (`openai` | `google` | `local`) để chọn model.
5. **Telemetry:** mọi lần gọi LLM ghi log qua `tracker.track_request()` để phân tích token/latency/cost.

---

## 7. Mô hình & cấu hình

| Provider | Model | Khi nào dùng |
| :--- | :--- | :--- |
| `openai` | `gpt-4o` | Mặc định, demo "agent chạy ngon" |
| `google` | `gemini-1.5-flash` | Backup, so sánh latency |
| `local` | `Phi-3-mini-4k-instruct-q4.gguf` | Offline/CPU, dễ tạo trace lỗi để phân tích |

Cấu hình ở `.env` (copy từ `.env.example`).

---

## 8. Tiêu chí chấm điểm (tham chiếu SCORING.md)

- **Nhóm (max 60đ):** Chatbot baseline, Agent v1, Agent v2 (cải tiến), tool design, chất lượng trace, đánh giá, flowchart, code quality.
- **Cá nhân (40đ):** đóng góp kỹ thuật, debugging case study từ log, insight chatbot vs agent, đề xuất tương lai.
- **Triết lý:** *"Fail Early, Learn Fast"* — một trace lỗi được phân tích kỹ giá trị hơn một hệ thống "hoàn hảo" không giải thích được.

---

## 9. Phân công

Xem chi tiết task list của 5 thành viên tại **[TASK_LIST.md](TASK_LIST.md)**.
