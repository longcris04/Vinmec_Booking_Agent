graph TD
Start([User Input]) --> Step1[Bước 1: NLU & Entity Extraction]
Step1 --> Step2{Bước 2: Kiểm tra Tình trạng khẩn cấp}

    Step2 -->|Khẩn cấp: Đau ngực, Khó thở...| Emergency[Hành động khẩn cấp: Đọc số Hotline Cấp cứu]
    Step2 -->|Bình thường| Step3{Bước 3: Kiểm tra thông tin Slot/Slot-Filling}

    Step3 -->|Thiếu thông tin bắt buộc| AskMissing[Hỏi bổ sung thông tin thiếu]
    Step3 -->|Đủ thông tin| Step4[Bước 4: Gọi Tools & Thực thi Logic]

    Step4 --> Tool1[Tool 1: Phân loại chuyên khoa]
    Tool1 --> Tool2[Tool 2: Xác định cơ sở Vinmec gần nhất]
    Tool2 --> Tool3[Tool 3: Truy vấn lịch trống]

    Tool3 --> Step5{Bước 5: Xử lý Kết quả Truy vấn}
    Step5 -->|Không có lịch trống| Alternate[Đề xuất Giờ khác/Bác sĩ khác/Cơ sở khác]
    Step5 -->|Có lịch trống| Tool4[Tool 4: Đặt lịch Book Appointment]

    Alternate --> Step3
    Tool4 --> Step6[Bước 6: Gửi Xác nhận & Dặn dặn dò]
    Step6 --> End([End Session])
