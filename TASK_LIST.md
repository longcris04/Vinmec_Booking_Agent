# Task List — Dự án Vinmec ReAct Agent (5 người)

> Đề tài & ngữ cảnh đầy đủ: xem **[DE_TAI_VINMEC.md](DE_TAI_VINMEC.md)**.
> Mỗi người sở hữu một module riêng để có nội dung viết Individual Report (40đ).

---

## 🌐 P0 — Cả nhóm (30 phút đầu)
- [ ] Chốt scope: 3 tool Vinmec + test case lõi
- [ ] Mỗi người `cp .env.example .env`, điền API key (hoặc dùng `local` Phi-3)
- [ ] `pip install -r requirements.txt`
- [ ] Thống nhất format Action: `Action: tool_name(arg1=..., arg2=...)`
- [ ] Mỗi người tạo nhánh git riêng để tránh conflict

---

## 👤 P1 — Tools Engineer
**File sở hữu:** `src/tools/vinmec_tools.py`
- [ ] Tạo thư mục `src/tools/` + `__init__.py`
- [ ] `find_nearest_vinmec(location)` + map quận/thành phố → cơ sở gần nhất + khoảng cách
- [ ] `check_doctor_availability(specialty, date)` + data mock (3-4 chuyên khoa)
- [ ] `get_service_price(service_name)` + bảng giá mock
- [ ] `apply_insurance(price, insurance_type)` (vd Vinmec Care = giảm 70%)
- [ ] Viết list `TOOLS_SPEC` (name + description + cách gọi) — mô tả thật rõ ràng
- [ ] Đảm bảo mọi tool trả observation **NGẮN** (số / 1 dòng)
- [ ] (Bonus) Tool thứ 5: `book_appointment(specialty, time)`

**Rubric:** Tool Design (4đ) + Extra Tools bonus (+2)

---

## 👤 P2 — Agent Core Engineer ⭐ (trọng tâm / đường găng)
**File sở hữu:** `src/agent/agent.py`
- [ ] Hoàn thiện `get_system_prompt()` (chèn tool descriptions + few-shot ví dụ)
- [ ] Viết `run()`: gọi LLM → nhận text trả về
- [ ] Parser regex tách `Thought` / `Action` / `Final Answer`
- [ ] Tách tên tool + arguments từ dòng `Action`
- [ ] Gọi `_execute_tool()` → nối `Observation:` vào prompt cho vòng sau
- [ ] Điều kiện dừng: gặp `Final Answer` hoặc hết `max_steps` (đặt = 3)
- [ ] `_execute_tool()`: map tên → hàm thật, bắt lỗi tool không tồn tại
- [ ] Log `AGENT_STEP` mỗi vòng lặp

**Rubric:** Agent v1 Working (7đ)

---

## 👤 P3 — Baseline & Integration
**File sở hữu:** `chatbot.py`, `main.py`
- [ ] `chatbot.py`: chatbot LLM thuần, KHÔNG tool (để so sánh)
- [ ] `main.py`: đọc `.env`, chọn provider (openai/google/local)
- [ ] `main.py`: nạp tools từ P1, khởi tạo `ReActAgent`, chạy input người dùng
- [ ] Hàm `get_provider(name)` — switch 3 provider
- [ ] Chạy thử provider switching (OpenAI ↔ Local), ghi nhận latency
- [ ] Viết hướng dẫn chạy: `python main.py`

**Rubric:** Chatbot Baseline (2đ) + Code Quality (4đ)

---

## 👤 P4 — Telemetry & Failure Analysis (quan trọng cho điểm)
**File sở hữu:** `src/telemetry/metrics.py`, `analyze_logs.py`
- [ ] Viết `_calculate_cost()` thật (đơn giá token theo model)
- [ ] Gọi `tracker.track_request()` trong agent (phối hợp P2)
- [ ] `analyze_logs.py`: đọc `logs/*.log`, parse JSON
- [ ] Tính: tổng token, latency trung bình, số loop, đếm lỗi
- [ ] Tìm **1 trace lỗi** (hallucination / parser / loop vô hạn)
- [ ] Cùng P2 sửa prompt **v1 → v2**, đo lại để chứng minh cải thiện

**Rubric:** Trace Quality (9đ) + Extra Monitoring bonus (+3) + góp Agent v2 (7đ)

---

## 👤 P5 — Evaluation & Reports
**File sở hữu:** `tests/test_cases.py`, `report/`
- [ ] Soạn 5-10 test case (vài câu đơn giản + vài câu nhiều bước)
- [ ] Chạy **Chatbot vs Agent** trên cùng bộ test
- [ ] Lập bảng so sánh: success rate, token, latency, cost
- [ ] Vẽ **flowchart** vòng lặp Thought-Action-Observation
- [ ] Điền `report/group_report/TEMPLATE_GROUP_REPORT.md`
- [ ] Nhắc mỗi người nộp `REPORT_[Tên].md` cá nhân
- [ ] (Bonus) Ablation: prompt v1 vs v2

**Rubric:** Evaluation (7đ) + Flowchart & Insight (5đ) + Ablation bonus (+2)

---

## 🔗 Mốc ghép nối (timeline 4 giờ)

| Mốc | Thời điểm | Nội dung |
| :--- | :--- | :--- |
| Khởi động | 0:00–0:30 | P0 xong, P3 dựng `main.py` skeleton để mọi người chạy được |
| Song song | 0:30–1:30 | P1 viết tools ∥ P2 viết ReAct loop (**đường găng**) |
| Ghép lần 1 | 1:30–2:15 | P3 nối tools + agent → chạy test case lõi → trace đầu tiên |
| Cải tiến | 2:15–3:00 | P4 đào log → P2+P4 nâng prompt v1→v2 (Agent v2) |
| Đánh giá | 3:00–3:40 | P5 chạy full test, lập bảng + flowchart |
| Hoàn thiện | 3:40–4:00 | Group report + 5 individual report |

⚠️ **Lưu ý Phi-3 4K context:** observation phải ngắn, `max_steps=3`, nếu không agent tràn context → lặp vô hạn.
