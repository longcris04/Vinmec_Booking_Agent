# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Nguyễn Hoàng Long
- **Student ID**: 2A202600785
- **Date**: 01/06/2026

---

## I. Technical Contribution (15 Points)

Trong lab này, tôi tập trung vào phần telemetry để biến agent từ một skeleton khó debug thành một hệ thống có trace rõ ràng. Cụ thể, tôi chuẩn hóa đo lường token, cost và latency trong [src/telemetry/metrics.py](../../src/telemetry/metrics.py), đồng thời chuẩn hóa log có cấu trúc trong [src/telemetry/logger.py](../../src/telemetry/logger.py).

- **Modules Implemented**: [src/telemetry/metrics.py](../../src/telemetry/metrics.py), [src/telemetry/logger.py](../../src/telemetry/logger.py)
- **Code Highlights**:
	- `PerformanceTracker.track_request()` lưu lại `prompt_tokens`, `completion_tokens`, `total_tokens`, `latency_ms` và `cost_estimate` cho từng request.
	- `logger.log_event()` ghi payload theo format JSON với ba trường chính: `timestamp`, `event`, `data`.
	- Trace của agent có thể được nối lại thành chuỗi sự kiện `AGENT_START -> AGENT_STEP_OUTPUT/AGENT_ACTION -> AGENT_FINAL -> AGENT_END`, giúp theo dõi toàn bộ vòng lặp ReAct.
- **Documentation**: Thiết kế này giúp tách bạch giữa logic suy luận của agent và lớp quan sát hệ thống. Khi agent gọi model hoặc tool, tôi chỉ cần nhìn log JSON là biết request nào tốn bao nhiêu token, chạy bao lâu và dừng ở bước nào.

---

## II. Debugging Case Study (10 Points)

Một lỗi hữu ích để phân tích là trường hợp agent nhận câu hỏi “Tôi muốn tìm bệnh viện gần nhất” nhưng lại đi qua tool `emergency` thay vì một luồng tìm kiếm địa điểm rõ ràng. Trace trong [tests/logs/2026-06-01.log](../../tests/logs/2026-06-01.log#L8) cho thấy agent tạo `AGENT_START`, sau đó sinh `AGENT_STEP_OUTPUT` với `Action: emergency(...)`, rồi kết thúc bằng `AGENT_FINAL` và `AGENT_END`.

- **Problem Description**: Agent chọn tool chưa thật sự chính xác với ý định người dùng, vì prompt và mô tả tool còn đủ rộng để model gán nhầm intent.
- **Log Source**: [tests/logs/2026-06-01.log](../../tests/logs/2026-06-01.log#L8)
- **Diagnosis**: Vấn đề không nằm ở việc thiếu trace, mà ở chỗ trace đã cho thấy ngay bước chọn action. Log JSON làm rõ raw input, tên tool được gọi và payload từng bước, nên có thể thấy lỗi xuất phát từ prompt/tool spec hơn là từ output cuối cùng.
- **Solution**: Tôi chuẩn hóa log và dùng trace theo từng bước để khoanh vùng lỗi. Từ đó, hướng sửa hợp lý là làm rõ mô tả tool, siết format `Action`, và tách các intent như cấp cứu, tìm cơ sở y tế, và hỗ trợ vị trí thành các tool/luồng riêng biệt hơn.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**: `Thought` block giúp agent bộc lộ bước suy luận trung gian, nên tôi có thể kiểm tra tại sao nó chọn một action thay vì chỉ thấy một câu trả lời cuối cùng. Với chatbot thuần, lỗi thường bị “ẩn” trong một response duy nhất; với ReAct, trace cho thấy từng quyết định.
2. **Reliability**: Agent có thể tệ hơn chatbot khi prompt chưa đủ chặt, vì model sẽ “hành động” sớm và dễ chọn sai tool. Trong các câu hỏi ngắn, rõ nghĩa, chatbot đôi khi lại an toàn hơn vì không có chi phí sai tool hoặc sai vòng lặp.
3. **Observation**: Phần observation là tín hiệu quan trọng nhất để agent tự sửa hướng đi. Khi observation phù hợp, agent có thể chuyển sang `Final Answer` rất nhanh; khi observation mơ hồ, nó sẽ lặp sai hoặc đi lạc sang action khác.

---

## IV. Future Improvements (5 Points)

Nếu nâng hệ thống này lên mức production, tôi sẽ ưu tiên các cải tiến sau:

- **Scalability**: Thêm job queue hoặc async executor cho tool calls để tránh chặn luồng chính khi agent xử lý nhiều request đồng thời.
- **Safety**: Gắn correlation ID cho mỗi phiên và thêm guardrail để giới hạn số vòng lặp, tránh agent chạy quá lâu hoặc sinh chi phí không cần thiết.
- **Performance**: Thay mock cost bằng bảng giá thật theo provider/model, và bổ sung parser đọc log JSONL để tổng hợp dashboard về token, latency và error rate.

---

> [!NOTE]
> Báo cáo này bám theo phần telemetry và trace trong repo hiện tại. Khi nộp, giữ đúng tên file `REPORT_Nguyen_Hoang_Long_2A202600785.md` trong thư mục này.
