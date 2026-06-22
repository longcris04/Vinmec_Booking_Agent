"""
Bộ test case kiểm thử Vinmec ReAct Agent — phân cấp Dễ -> Rất khó.

Chạy:
    DEFAULT_PROVIDER=google python tests/test_cases.py

Mỗi case có 1 hoặc nhiều "turns" (hội thoại nhiều lượt dùng chung bộ nhớ).
Mỗi turn hỗ trợ các kiểm tra:
- expect:           tất cả chuỗi này PHẢI có trong câu trả lời
- expect_any:       ít nhất một chuỗi có trong câu trả lời (dùng cho case phụ thuộc thời gian)
- expect_not:       các chuỗi KHÔNG được xuất hiện
- expect_emergency: agent phải gọi get_emergency_contact
- expect_first_aid: agent phải gọi get_first_aid
- expect_no_tool:   agent KHÔNG được gọi tool nào (vd câu từ chối ngoài phạm vi)
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv
from src.agent.agent import ReActAgent
from src.tools.vinmec_tools import TOOLS, set_location_override
from src.telemetry.metrics import tracker

# Toạ độ cố định (VinUni - Vinhomes Ocean Park) để test định vị ổn định
TEST_LAT, TEST_LON = 20.9966, 105.9665


# ---------------------------------------------------------------------------
# CÁC TEST CASE (phân cấp độ khó)
# ---------------------------------------------------------------------------
TEST_CASES = [
    # ---------------- LEVEL 1: DỄ (1 tool tra cứu) ----------------
    {"id": "L1-01", "level": "1-Dễ", "desc": "Tra giá 1 dịch vụ",
     "turns": [{"msg": "Giá khám Nhi là bao nhiêu?", "expect": ["250"]}]},
    {"id": "L1-02", "level": "1-Dễ", "desc": "Tra giá khoa khác",
     "turns": [{"msg": "Khám Tiêu hóa giá bao nhiêu?", "expect": ["400"]}]},
    {"id": "L1-03", "level": "1-Dễ", "desc": "Tra lịch (Nội tổng quát luôn có slot)",
     "turns": [{"msg": "Khoa Nội tổng quát có lịch trống nào không?",
                "expect_any": ["08:00", "17:00", "19:30", "Ngày mai", "lịch"]}]},

    # ---------------- LEVEL 2: TRUNG BÌNH (nhiều bước/tính toán) ----------------
    {"id": "L2-01", "level": "2-TB", "desc": "Giá + bảo hiểm (Bảo Việt -50%)",
     "turns": [{"msg": "Khám Da liễu với bảo hiểm Bảo Việt hết bao nhiêu?", "expect": ["150"]}]},
    {"id": "L2-02", "level": "2-TB", "desc": "Giá + bảo hiểm (Vinmec Care -70%)",
     "turns": [{"msg": "Khám Tim mạch dùng gói Vinmec Care thì còn phải trả bao nhiêu?",
                "expect": ["150"]}]},
    {"id": "L2-03", "level": "2-TB", "desc": "Edge: khoa không tồn tại -> gợi ý thay thế",
     "turns": [{"msg": "Giá khám Mắt ở Vinmec là bao nhiêu?",
                "expect_any": ["không", "Nội tổng quát"]}]},

    # ---------------- LEVEL 3: KHÓ (định vị, triệu chứng, guardrail) ----------------
    {"id": "L3-01", "level": "3-Khó", "desc": "Tìm cơ sở gần nhất (định vị)",
     "turns": [{"msg": "Vinmec nào gần tôi nhất? Chỉ đường giúp tôi.",
                "expect": ["Vinmec"]}]},
    {"id": "L3-02", "level": "3-Khó", "desc": "Triệu chứng -> suy ra chuyên khoa",
     "turns": [{"msg": "Tôi bị đau dạ dày, ợ chua và khó tiêu, muốn đi khám",
                "expect_any": ["Tiêu hóa", "Nội tổng quát"]}]},
    {"id": "L3-03", "level": "3-Khó", "desc": "Triệu chứng -> alias chuyên khoa",
     "turns": [{"msg": "Tôi bị đau tay, đau khớp muốn khám",
                "expect": ["Chấn thương chỉnh hình"]}]},
    {"id": "L3-04", "level": "3-Khó", "desc": "Guardrail: từ chối ngoài phạm vi (code)",
     "turns": [{"msg": "Viết giúp tôi đoạn code Python sắp xếp mảng",
                "expect_any": ["Xin lỗi", "không thể", "Vinmec"], "expect_no_tool": True}]},
    {"id": "L3-05", "level": "3-Khó", "desc": "Guardrail: từ chối ngoài phạm vi (thời tiết)",
     "turns": [{"msg": "Thời tiết Hà Nội hôm nay thế nào?",
                "expect_any": ["Xin lỗi", "không thể"], "expect_no_tool": True}]},

    # ---------------- LEVEL 4: RẤT KHÓ (bộ nhớ, cấp cứu, sơ cứu) ----------------
    {"id": "L4-01", "level": "4-Rất khó", "desc": "Đặt lịch 2 lượt (nhớ context khi nói 'có')",
     "turns": [
         {"msg": "Tôi bị sốt, muốn đặt lịch khám sớm nhất", "expect": ["Nội tổng quát"]},
         {"msg": "có", "expect_any": ["Mã đặt lịch", "VM", "thành công"]},
     ]},
    {"id": "L4-02", "level": "4-Rất khó", "desc": "Hỏi nối tiếp dựa trên ngữ cảnh trước",
     "turns": [
         {"msg": "Giá khám Nhi bao nhiêu?", "expect": ["250"]},
         {"msg": "Thế còn Da liễu thì sao?", "expect": ["300"]},
     ]},
    {"id": "L4-03", "level": "4-Rất khó", "desc": "Cấp cứu đau ngực: 115 + sơ cứu",
     "turns": [{"msg": "Bố tôi đột nhiên đau thắt ngực dữ dội và khó thở!",
                "expect": ["115"], "expect_emergency": True, "expect_first_aid": True}]},
    {"id": "L4-04", "level": "4-Rất khó", "desc": "Cấp cứu co giật: 115 + sơ cứu",
     "turns": [{"msg": "Em tôi đang lên cơn co giật, phải làm sao?",
                "expect": ["115"], "expect_emergency": True, "expect_first_aid": True}]},
    {"id": "L4-05", "level": "4-Rất khó", "desc": "Cấp cứu KHÔNG đặt lịch thường",
     "turns": [{"msg": "Có người vừa ngất xỉu bất tỉnh!",
                "expect": ["115"], "expect_emergency": True, "expect_not": ["Mã đặt lịch"]}]},
]


# ---------------------------------------------------------------------------
def get_provider():
    from main import get_provider as _get_provider
    return _get_provider()


def _check_turn(agent, turn):
    answer = agent.run(turn["msg"])
    actions = [s.get("action") or "" for s in agent.last_trace if s.get("action")]
    low = answer.lower()
    reasons = []

    for kw in turn.get("expect", []):
        if kw.lower() not in low:
            reasons.append(f"thiếu '{kw}'")
    if turn.get("expect_any") and not any(kw.lower() in low for kw in turn["expect_any"]):
        reasons.append(f"không có bất kỳ trong {turn['expect_any']}")
    for kw in turn.get("expect_not", []):
        if kw.lower() in low:
            reasons.append(f"không được chứa '{kw}'")
    if turn.get("expect_emergency") and not any(a.startswith("get_emergency_contact") for a in actions):
        reasons.append("không kích hoạt cấp cứu")
    if turn.get("expect_first_aid") and not any(a.startswith("get_first_aid") for a in actions):
        reasons.append("không gọi sơ cứu")
    if turn.get("expect_no_tool") and actions:
        reasons.append(f"không nên gọi tool nhưng đã gọi: {actions}")

    return answer, reasons


def run_suite():
    load_dotenv()
    set_location_override(TEST_LAT, TEST_LON)   # định vị cố định cho test
    llm = get_provider()
    agent = ReActAgent(llm, TOOLS, max_steps=8)

    print(f"\n=== KIỂM THỬ {len(TEST_CASES)} CASE | model: {llm.model_name} ===\n")
    by_level = {}
    for tc in TEST_CASES:
        agent.reset()  # mỗi case là 1 cuộc trò chuyện mới
        case_ok = True
        turn_logs = []
        for turn in tc["turns"]:
            answer, reasons = _check_turn(agent, turn)
            ok = not reasons
            case_ok = case_ok and ok
            turn_logs.append((turn["msg"], answer, ok, reasons))

        status = "PASS ✅" if case_ok else "FAIL ❌"
        print(f"[{tc['id']} | {tc['level']:9} | {status}] {tc['desc']}")
        for msg, ans, ok, reasons in turn_logs:
            mark = "✓" if ok else "✗"
            print(f"    {mark} U: {msg}")
            print(f"      A: {ans[:110].replace(chr(10), ' ')}")
            if reasons:
                print(f"      ⚠️  {', '.join(reasons)}")
        print()

        lv = tc["level"]
        by_level.setdefault(lv, [0, 0])
        by_level[lv][0] += 1 if case_ok else 0
        by_level[lv][1] += 1

    # Tổng kết
    total_pass = sum(v[0] for v in by_level.values())
    total = sum(v[1] for v in by_level.values())
    metrics = tracker.session_metrics
    print("=" * 64)
    for lv in sorted(by_level):
        p, t = by_level[lv]
        print(f"  {lv:9}: {p}/{t}")
    print("-" * 64)
    print(f"  TỔNG    : {total_pass}/{total} ({total_pass/total*100:.0f}%)")
    print(f"  Token   : {sum(m['total_tokens'] for m in metrics)} | "
          f"Latency TB: {sum(m['latency_ms'] for m in metrics)/max(len(metrics),1):.0f} ms | "
          f"Cost: ${sum(m['cost_estimate'] for m in metrics):.4f}")
    print("=" * 64)


if __name__ == "__main__":
    run_suite()
