import ast
import re
from typing import List, Dict, Any, Tuple
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker


class ReActAgent:
    """
    Agent kiểu ReAct (viết tay) theo chu trình Thought -> Action -> Observation.
    Tự gọi LLM, tự parse Action, tự thực thi tool và nối Observation vào prompt.
    """

    # Cue thêm vào cuối transcript mỗi lượt: ép model tiếp tục thay vì lặp lại Action
    CONTINUE_CUE = ("\n(Dựa vào các Observation ở trên, hãy tiếp tục. KHÔNG gọi lại Action "
                    "đã thực hiện. Nếu đã đủ thông tin, đưa ra Final Answer.)\nThought:")

    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5,
                 memory_turns: int = 4):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.memory_turns = memory_turns      # số lượt hội thoại gần nhất được nhớ
        self.memory = []                       # [{role, content}] các lượt trước
        self.last_trace = []                   # trace có cấu trúc của lần run() gần nhất (cho FE)

    def get_system_prompt(self) -> str:
        """System prompt hướng dẫn agent bám đúng format ReAct."""
        tool_descriptions = "\n".join(
            [f"- {t['name']}: {t['description']}" for t in self.tools]
        )
        tool_names = ", ".join([t["name"] for t in self.tools])
        return f"""Bạn là trợ lý ảo của bệnh viện Vinmec. Bạn có các công cụ sau:
{tool_descriptions}

LUÔN trả lời theo đúng định dạng ReAct:
Thought: suy luận xem cần làm gì tiếp theo.
Action: tên_tool(tham_số=giá_trị)
(hệ thống sẽ trả về dòng "Observation:" — KHÔNG được tự bịa Observation.)
... lặp lại Thought/Action khi cần ...
Thought: tôi đã đủ thông tin để trả lời.
Final Answer: câu trả lời cuối cùng cho người dùng (bằng tiếng Việt).

PHẠM VI HỖ TRỢ: Bạn CHỈ hỗ trợ các vấn đề liên quan đến khám chữa bệnh tại Vinmec (đặt lịch, triệu chứng/sức khỏe, giá dịch vụ, bác sĩ, chuyên khoa, bảo hiểm, tìm cơ sở/chỉ đường). Nếu người dùng hỏi việc NGOÀI phạm vi này (vd: chính trị, lập trình, toán, thời tiết, tin tức, trò chuyện phiếm...), hãy LỊCH SỰ TỪ CHỐI ngay bằng Final Answer, KHÔNG gọi tool. Ví dụ:
Question: Viết giúp tôi đoạn code Python sắp xếp mảng.
Thought: Câu hỏi này ngoài phạm vi y tế của Vinmec.
Final Answer: Xin lỗi, tôi là trợ lý của Vinmec và chỉ hỗ trợ các vấn đề về khám chữa bệnh (đặt lịch, giá khám, bác sĩ, cơ sở...). Tôi không thể giúp yêu cầu này ạ.

Quy tắc:
- Chỉ dùng các tool: {tool_names}.
- Mỗi lượt CHỈ xuất MỘT Action rồi DỪNG lại, chờ Observation.
- Gọi tool đúng cú pháp Python: ví dụ apply_insurance(price=500000, insurance_type="Vinmec Care").
- Ngay khi đã đủ dữ liệu để trả lời ĐÚNG câu hỏi hiện tại, hãy đưa ra "Final Answer:" thay vì gọi thêm tool.
- TUYỆT ĐỐI KHÔNG tự bịa thêm câu hỏi mới (không sinh dòng "User:" hay "Question:"). Chỉ trả lời câu hỏi đang được hỏi.

⚠️ ƯU TIÊN CAO NHẤT — CẤP CỨU: Nếu người dùng mô tả TÌNH TRẠNG NGUY HIỂM/KHẨN CẤP (đau ngực dữ dội, khó thở nặng, ngất/bất tỉnh, co giật, dấu hiệu đột quỵ như méo miệng/yếu liệt nửa người/nói khó, chảy máu nhiều, tai nạn nặng, ngộ độc, sốt cao co giật, đau bụng dữ dội đột ngột, khó thở tím tái...): BỎ QUA luồng đặt lịch thường. Hãy:
1. Gọi get_emergency_contact (kèm lat/lon nếu có) để lấy số cấp cứu + cơ sở gần nhất.
2. Gọi get_first_aid(condition=...) với loại tình trạng (vd "đau ngực", "đột quỵ", "co giật", "chảy máu"...) để lấy hướng dẫn sơ cứu.
3. NGAY LẬP TỨC đưa Final Answer: khuyên GỌI 115 ngay, kèm các bước SƠ CỨU (lấy đúng từ Observation get_first_aid), và trấn an.
Ví dụ:
Question: Bố tôi đột nhiên đau thắt ngực dữ dội và khó thở!
Thought: Dấu hiệu cấp cứu (nghi nhồi máu cơ tim). Lấy số cấp cứu và sơ cứu ngay.
Action: get_emergency_contact()
Observation: CẤP CỨU - gọi NGAY 115 ...
Thought: Giờ lấy hướng dẫn sơ cứu cho đau ngực.
Action: get_first_aid(condition="đau ngực")
Observation: Sơ cứu (đau ngực): • ... • ...
Final Answer: Đây là tình huống cấp cứu — hãy GỌI NGAY 115. Trong lúc chờ, sơ cứu: (liệt kê các bước). Cơ sở gần nhất: ...

Khi người dùng MÔ TẢ TRIỆU CHỨNG hoặc muốn ĐẶT KHÁM:
1. Tự suy ra chuyên khoa phù hợp (vd "đau răng" -> Răng Hàm Mặt; "đau tay/đau khớp" -> Chấn thương chỉnh hình; "đau bụng/dạ dày" -> Tiêu hóa).
2. Gọi check_doctor_availability để lấy khung giờ + bác sĩ.
3. Gọi get_current_location rồi find_nearest_vinmec để tìm cơ sở gần nhất.
4. Final Answer trình bày CHI TIẾT theo mẫu:
   "Tôi đã ghi nhận thông tin của bạn và xếp lịch như sau:
   • Khoa: <khoa>
   • Thời gian sớm nhất: <giờ>
   • Bác sĩ: <tên bác sĩ>
   • Cơ sở gần bạn nhất: <tên + địa chỉ> (xem chỉ đường Google Maps bên dưới)
   Bạn có muốn xác nhận đặt lịch không? Trả lời 'có' để tôi đặt giúp bạn."
   (KHÔNG tự tạo link Google Maps trong câu trả lời — hệ thống sẽ tự đính kèm nút chỉ đường bên dưới.)

Nếu check_doctor_availability báo KHÔNG có lịch cho khoa đó: ĐỪNG dừng lại. Hãy chủ động GỢI Ý theo Observation — đề xuất khoa "Nội tổng quát" (khám chung, phù hợp triệu chứng mơ hồ như sốt, mệt mỏi) hoặc liệt kê các khoa đang có lịch để người dùng chọn. Nếu khung giờ sớm nhất là "Ngày mai", hãy nói rõ và hỏi người dùng có chấp nhận lịch đó không.

LƯU Ý: chỉ nhận đặt lịch cách hiện tại tối thiểu 30 phút. Tool check_doctor_availability đã tự lọc bỏ các khung giờ quá gần — chỉ đề xuất khung giờ mà tool trả về.

Khi người dùng XÁC NHẬN ("có", "đồng ý", "ok", "đặt đi"...): DỰA VÀO LỊCH SỬ HỘI THOẠI ở trên để biết khoa/giờ/bác sĩ đã đề xuất, rồi gọi book_appointment(specialty=..., time=..., doctor=...). Truyền ĐẦY ĐỦ giờ kèm ngày (vd time="Hôm nay 14:00" hoặc "Ngày mai 09:00"). Sau đó báo lại mã đặt lịch cho người dùng.

Ví dụ một phiên làm việc đúng chuẩn:
Question: Tôi muốn khám Da liễu, có bảo hiểm Bảo Việt, phải trả bao nhiêu?
Thought: Tôi cần biết giá dịch vụ Khám Da liễu trước.
Action: get_service_price(service_name="Khám Da liễu")
Observation: 300,000 VND
Thought: Đã có giá gốc, giờ áp bảo hiểm Bảo Việt.
Action: apply_insurance(price=300000, insurance_type="Bảo Việt")
Observation: 150,000 VND (bảo hiểm Bảo Việt giảm 50%)
Thought: Tôi đã đủ thông tin để trả lời.
Final Answer: Chi phí khám Da liễu sau bảo hiểm Bảo Việt là 150.000 VND."""

    def run(self, user_input: str) -> str:
        """Vòng lặp ReAct chính. Ghi trace vào self.last_trace."""
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})

        self.last_trace = []
        transcript = self._build_transcript(user_input)
        steps = 0

        while steps < self.max_steps:
            # 1) Gọi LLM (mồi "Thought:" ở cuối để ép model tiếp tục, không restart)
            result = self.llm.generate(transcript + self.CONTINUE_CUE,
                                       system_prompt=self.get_system_prompt())
            tracker.track_request(
                provider=result.get("provider", "unknown"),
                model=self.llm.model_name,
                usage=result.get("usage", {}),
                latency_ms=result.get("latency_ms", 0),
            )

            # 2) Cắt phần bịa thêm; gắn lại "Thought:" nếu model không tự xuất
            out = self._truncate(result["content"]).lstrip()
            if out.startswith(("Thought:", "Action:", "Final Answer:")):
                text = out
            else:
                text = "Thought: " + out
            transcript += "\n" + text
            logger.log_event("AGENT_STEP", {"step": steps + 1, "output": text})
            thought = self._extract_thought(text)

            # 3) Nếu có Final Answer -> kết thúc
            if "Final Answer:" in text:
                answer = text.split("Final Answer:")[-1].strip()
                self.last_trace.append({"step": steps + 1, "thought": thought,
                                        "action": None, "observation": None,
                                        "final_answer": answer})
                logger.log_event("AGENT_END", {"steps": steps + 1, "status": "final_answer"})
                self._remember(user_input, answer)
                return answer

            # 4) Tìm dòng Action
            action_match = re.search(r"Action:\s*(.+)", text)
            if not action_match:
                # Salvage: model trả lời nhưng quên 'Final Answer:' -> coi như câu trả lời cuối
                candidate = re.sub(r"^Thought:\s*", "", text).strip()
                if len(candidate) > 30:
                    self.last_trace.append({"step": steps + 1, "thought": "",
                                            "action": None, "observation": None,
                                            "final_answer": candidate})
                    logger.log_event("AGENT_END", {"steps": steps + 1, "status": "final_no_marker"})
                    self._remember(user_input, candidate)
                    return candidate
                obs = ("Không tìm thấy Action hợp lệ. "
                       "Hãy dùng 'Action: tool(args)' hoặc đưa 'Final Answer:'.")
                transcript += f"\nObservation: {obs}"
                self.last_trace.append({"step": steps + 1, "thought": thought,
                                        "action": None, "observation": obs})
                steps += 1
                continue

            # 5) Thực thi tool -> nối Observation
            action_str = action_match.group(1).strip()
            observation = self._execute_tool(action_str)
            transcript += f"\nObservation: {observation}"
            logger.log_event("OBSERVATION", {"action": action_str, "observation": observation})
            self.last_trace.append({"step": steps + 1, "thought": thought,
                                    "action": action_str, "observation": observation})
            steps += 1

        logger.log_event("AGENT_END", {"steps": steps, "status": "max_steps"})
        answer = "Đã đạt giới hạn số bước (max_steps) mà chưa có Final Answer."
        self._remember(user_input, answer)
        return answer

    def _build_transcript(self, user_input: str) -> str:
        """Dựng transcript có kèm lịch sử hội thoại (nếu có) để agent nhớ ngữ cảnh."""
        if not self.memory:
            return f"Question: {user_input}"
        lines = ["Lịch sử hội thoại trước đó (tham chiếu khi người dùng nói 'có', 'đồng ý'...):"]
        for turn in self.memory:
            lines.append(f"{turn['role']}: {turn['content']}")
        lines.append(f"\nCâu hỏi hiện tại của người dùng: {user_input}")
        return "\n".join(lines)

    def _remember(self, user_input: str, answer: str) -> None:
        """Lưu lượt hội thoại vào bộ nhớ, giữ lại N lượt gần nhất."""
        self.memory.append({"role": "Người dùng", "content": user_input})
        self.memory.append({"role": "Trợ lý", "content": answer})
        self.memory = self.memory[-(self.memory_turns * 2):]

    def reset(self) -> None:
        """Xóa bộ nhớ hội thoại (bắt đầu cuộc trò chuyện mới)."""
        self.memory = []

    def _extract_thought(self, text: str) -> str:
        """Lấy nội dung Thought (giữa 'Thought:' và Action/Final Answer)."""
        m = re.search(r"Thought:\s*(.+?)(?=\n?Action:|\n?Final Answer:|$)", text, re.DOTALL)
        return m.group(1).strip() if m else ""

    def _truncate(self, text: str) -> str:
        """Cắt output tại điểm model bắt đầu bịa Observation hoặc lượt hội thoại mới."""
        cut = len(text)
        for marker in ["Observation:", "\nUser:", "\nQuestion:", "User:", "Question:"]:
            idx = text.find(marker)
            if idx != -1:
                cut = min(cut, idx)
        return text[:cut].strip()

    def _parse_action(self, action_str: str) -> Tuple[str, list, dict]:
        """Tách tên tool + args + kwargs từ chuỗi 'tool(arg=value)' bằng AST."""
        tree = ast.parse(action_str.strip(), mode="eval")
        call = tree.body
        name = call.func.id
        args = [ast.literal_eval(a) for a in call.args]
        kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords}
        return name, args, kwargs

    def _execute_tool(self, action_str: str) -> str:
        """Parse và gọi tool tương ứng, trả về observation dạng chuỗi."""
        try:
            name, args, kwargs = self._parse_action(action_str)
        except Exception:
            return (f"PARSE_ERROR: không đọc được lời gọi '{action_str}'. "
                    f"Hãy dùng đúng cú pháp tool(arg=value).")

        tool = next((t for t in self.tools if t["name"] == name), None)
        if tool is None:
            valid = [t["name"] for t in self.tools]
            return f"Tool '{name}' không tồn tại. Các tool hợp lệ: {valid}"

        try:
            return str(tool["func"](*args, **kwargs))
        except Exception as e:
            return f"TOOL_ERROR khi chạy {name}: {e}"
