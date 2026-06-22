# Individual Report: Lab 3 — Chatbot vs ReAct Agent

- **Student Name**: Huỳnh An Nghiệp
- **Student ID**: 2A202600853
- **Date**: 2026-06-01
- **Vai trò trong nhóm**: Agent Core Engineer (chủ sở hữu `src/agent/agent.py`) + điều phối tích hợp & review/merge cuối.

---

## I. Technical Contribution (15 Points)

**Module chính**: [`src/agent/agent.py`](../../src/agent/agent.py) — lớp `ReActAgent` (toàn bộ "bộ não" của agent).

Phạm vi đóng góp:
- **Thiết kế & hoàn thiện vòng lặp ReAct** (Thought → Action → Observation) trong `run()`.
- **Logic dừng**: phát hiện `Final Answer:`, trần `max_steps`, và cơ chế **salvage** khi model quên prefix.
- **Parser Action**: `_parse_action()` dùng **AST** để bóc tách an toàn `tool(arg=value)` (hỗ trợ cả positional & keyword, ép kiểu số/chuỗi).
- **Gọi tool & xử lý lỗi**: `_execute_tool()` map tên → hàm, bắt 3 loại lỗi: `PARSE_ERROR`, tool không tồn tại, `TOOL_ERROR`.
- **Bộ nhớ hội thoại**: `_build_transcript()`, `_remember()`, `reset()` — cho phép hiểu các lượt nối tiếp ("có", "thế còn… thì sao").
- **Điều phối tích hợp end-to-end** với [`main.py`](../../main.py) (CLI) và [`app.py`](../../app.py) (web FE): chuẩn hoá `last_trace` (trace có cấu trúc) để FE hiển thị.
- **Review/merge cuối** các nhánh tools/telemetry/FE.

**Code Highlights** (file `agent.py`):
- `CONTINUE_CUE` + mồi `Thought:` → ép model tiếp tục, không restart vòng lặp.
- `_truncate()` → cắt phần model "bịa" `Observation:`/`User:`/`Question:`.
- Salvage trong nhánh "không có Action" → coi nội dung dài là `Final Answer` (sửa lỗi chạm `max_steps`).

**Tương tác với ReAct loop**: mỗi vòng tôi nối kết quả tool dưới dạng `Observation:` vào transcript, đồng thời ghi `AGENT_STEP`/`OBSERVATION` qua telemetry để phục vụ phân tích.

---

## II. Debugging Case Study (10 Points)

- **Problem Description**: Tác vụ đặt lịch ("Tôi bị sốt, muốn đặt lịch") gom đủ dữ liệu sau 3 tool (lịch → vị trí → cơ sở) nhưng **không kết thúc**, chạm `max_steps` và trả về "Đã đạt giới hạn số bước".
- **Log Source** (`logs/`): chuỗi `AGENT_STEP` cho thấy bước 1–3 gọi tool đúng, nhưng bước 4 **không có `Action:` và cũng không có `Final Answer:`** → bị chèn Observation "Không tìm thấy Action hợp lệ", bước 5 rỗng.
- **Diagnosis**: model (Gemini) đã viết câu trả lời hoàn chỉnh (dạng "Tôi đã ghi nhận… • Khoa…") **nhưng quên prefix `Final Answer:`**. Vì điều kiện dừng của tôi chỉ dựa vào marker đó, vòng lặp không nhận ra đã xong và tiếp tục → cạn `max_steps`. Đây là lỗi **logic dừng**, không phải lỗi tool.
- **Solution**:
  1. **Salvage**: nếu một bước không có `Action` nhưng nội dung đủ dài (đã qua ≥1 tool), coi đó là `Final Answer` và kết thúc.
  2. **Mồi `Thought:`** (CONTINUE_CUE) để định hướng model "đủ thông tin thì đưa Final Answer".
  3. Nâng `max_steps` 6 → 8 cho luồng nhiều bước.
- **Kết quả**: case L4-01 (đặt lịch 2 lượt) chuyển từ FAIL → PASS; toàn bộ suite đạt **16/16**.

*(Lỗi liên quan tôi cũng xử lý: model tự bịa lượt `User:` → thêm `_truncate()` cắt bỏ.)*

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**: Khối `Thought` buộc model **lập kế hoạch từng bước** (xác định khoa → tra lịch → định vị) thay vì trả lời một phát. Đây là khác biệt cốt lõi: chatbot "nói ngay", agent "nghĩ rồi hành động".
2. **Reliability**: Ở câu **đơn giản**, agent đôi khi **tốn token/latency hơn** chatbot (phải đi qua vòng lặp), và phụ thuộc model bám đúng format — chính vì vậy phần lớn công sức của tôi là làm cho vòng lặp **bền vững** trước output lệch chuẩn (thiếu marker, bịa lượt). Chatbot thắng về tốc độ ở Q&A 1 bước.
3. **Observation feedback**: Việc nối `Observation` (kết quả tool thật) vào prompt giúp agent **sửa hướng** ở bước sau — ví dụ khoa không có lịch → đề xuất Nội tổng quát/ngày mai. Chatbot không có vòng phản hồi này nên dễ bịa số liệu.

Bài học lớn nhất: **"trace là sự thật"** — gần như mọi bug đều lộ ra rõ ràng trong `logs/AGENT_STEP`, và sửa dựa trên log nhanh hơn nhiều so với đoán prompt.

---

## IV. Future Improvements (5 Points)

- **Scalability**: tách **bộ nhớ theo session** (hiện dùng chung 1 instance) + lưu lịch/giá vào **DB** thay vì JSON tĩnh.
- **Safety**: thêm **Supervisor LLM** kiểm duyệt Action trước khi thực thi (đặc biệt cho cấp cứu/đặt lịch), và disclaimer y tế.
- **Performance**: **streaming** từng bước Thought/Action ra FE; cache câu hỏi lặp; với nhiều chuyên khoa dùng **RAG/vector DB** để chọn tool thay vì liệt kê hết trong prompt.
- **Robustness**: thay parser tự viết bằng **function-calling/structured output** của model để loại bỏ lỗi format tận gốc.

---

> [!NOTE]
> Đổi tên file thành `REPORT_[Tên_của_bạn].md` trước khi nộp.
