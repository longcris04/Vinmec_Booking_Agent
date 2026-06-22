"""
Vinmec ReAct Agent — Bộ công cụ (Tools).

Mỗi tool là một hàm Python trả về **observation NGẮN GỌN** (1 dòng) để hợp với
context window nhỏ. Tool định vị (`get_current_location`) gọi IP-geolocation thật,
có fallback nhập tay; `find_nearest_vinmec` tính khoảng cách Haversine tới các cơ sở.
"""

import json
import math
import os
import re
import sys
from datetime import datetime, timedelta

import requests
from urllib.parse import quote_plus

# Quy tắc: chỉ nhận đặt lịch cách thời điểm hiện tại tối thiểu 30 phút
MIN_LEAD_MINUTES = 30

# ---------------------------------------------------------------------------
# Nạp toàn bộ dữ liệu mock từ file JSON (vinmec_data.json cùng thư mục)
# ---------------------------------------------------------------------------
_DATA_PATH = os.path.join(os.path.dirname(__file__), "vinmec_data.json")
with open(_DATA_PATH, "r", encoding="utf-8") as _f:
    _DATA = json.load(_f)

VINMEC_FACILITIES = _DATA["facilities"]
# JSON lưu toạ độ dạng list [lat, lon] -> chuyển về tuple cho tiện dùng
CITY_COORDS = {k: tuple(v) for k, v in _DATA["city_coords"].items()}
DOCTOR_SCHEDULE = _DATA["doctor_schedule"]
SERVICE_PRICES = _DATA["service_prices"]
INSURANCE_COVERAGE = _DATA["insurance_coverage"]
SPECIALTY_ALIASES = _DATA.get("specialty_aliases", {})
EMERGENCY = _DATA.get("emergency", {"national": "115", "vinmec_hotline": "1900 232389"})
FIRST_AID = _DATA.get("first_aid", {})
FIRST_AID_ALIASES = _DATA.get("first_aid_aliases", {})


def _canonical_specialty(name: str) -> str:
    """Chuẩn hóa tên chuyên khoa qua bảng alias (vd 'cơ xương khớp' -> 'chấn thương chỉnh hình')."""
    key = name.strip().lower()
    return SPECIALTY_ALIASES.get(key, key)


# ---------------------------------------------------------------------------
# Tiện ích
# ---------------------------------------------------------------------------
def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Khoảng cách (km) giữa 2 toạ độ theo công thức Haversine."""
    radius = 6371.0
    rad = math.radians
    dlat = rad(lat2 - lat1)
    dlon = rad(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(dlon / 2) ** 2)
    return 2 * radius * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# TOOLS
# ---------------------------------------------------------------------------
# Toạ độ chính xác do FE (GPS trình duyệt) cung cấp cho mỗi request; ưu tiên hơn IP.
_LOCATION_OVERRIDE = None


def set_location_override(lat=None, lon=None):
    """FE gọi trước agent.run() để truyền toạ độ GPS thật; gọi với None để xóa."""
    global _LOCATION_OVERRIDE
    _LOCATION_OVERRIDE = (lat, lon) if (lat is not None and lon is not None) else None


def get_current_location() -> str:
    """Xác định vị trí hiện tại: ưu tiên GPS trình duyệt (FE), sau đó IP (ip-api.com),
    cuối cùng fallback nhập tay / mặc định."""
    # 1) Ưu tiên toạ độ GPS chính xác từ trình duyệt
    if _LOCATION_OVERRIDE:
        lat, lon = _LOCATION_OVERRIDE
        return f"lat={lat}, lon={lon}, source=gps"

    # 2) Định vị qua IP (chỉ chính xác mức thành phố)
    try:
        resp = requests.get("http://ip-api.com/json/", timeout=5)
        data = resp.json()
        if data.get("status") == "success":
            return (f"lat={data['lat']}, lon={data['lon']}, "
                    f"city={data.get('city')}, source=ip")
    except Exception:
        pass

    # Fallback: nếu chạy tương tác (CLI) thì hỏi người dùng; nếu chạy web/server thì mặc định
    if sys.stdin and sys.stdin.isatty():
        city = input("[Không định vị được qua IP] Bạn đang ở tỉnh/thành nào? ").strip().lower()
        if city in CITY_COORDS:
            lat, lon = CITY_COORDS[city]
            return f"lat={lat}, lon={lon}, city={city}, source=manual"
    # Mặc định Hà Nội
    lat, lon = CITY_COORDS["hà nội"]
    return f"lat={lat}, lon={lon}, city=hà nội (mặc định), source=fallback"


def nearest_vinmec_info(lat: float, lon: float):
    """Trả về (facility_dict, distance_km) của cơ sở Vinmec gần nhất."""
    nearest = min(
        VINMEC_FACILITIES,
        key=lambda f: _haversine(lat, lon, f["lat"], f["lon"]),
    )
    return nearest, _haversine(lat, lon, nearest["lat"], nearest["lon"])


def maps_directions_url(o_lat: float, o_lon: float, destination: str) -> str:
    """Tạo link Google Maps chỉ đường (lái xe) từ toạ độ người dùng tới cơ sở.

    destination là chuỗi 'tên + địa chỉ' để Google Maps tự geocode đúng vị trí thật,
    tránh phụ thuộc vào toạ độ nhập tay (có thể lệch).
    """
    dest = quote_plus(destination)
    return (f"https://www.google.com/maps/dir/?api=1"
            f"&origin={o_lat},{o_lon}&destination={dest}&travelmode=driving")


def find_nearest_vinmec(lat: float, lon: float) -> str:
    """Tìm cơ sở Vinmec gần nhất so với toạ độ (lat, lon) cho trước."""
    nearest, dist = nearest_vinmec_info(lat, lon)
    return f"{nearest['name']} ({nearest['address']}), cách ~{dist:.1f} km"


def _slot_datetime(slot: str):
    """Parse 'Hôm nay 09:00 - BS. X' / 'Ngày mai 13:00 ...' -> datetime (None nếu không có giờ)."""
    m = re.search(r"(\d{1,2}):(\d{2})", slot)
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    day = datetime.now().date()
    if "ngày mai" in slot.lower():
        day = day + timedelta(days=1)
    return datetime(day.year, day.month, day.day, hh, mm)


def _is_bookable(slot: str, now: datetime = None) -> bool:
    """Slot hợp lệ nếu cách hiện tại >= MIN_LEAD_MINUTES phút."""
    now = now or datetime.now()
    dt = _slot_datetime(slot)
    if dt is None:
        return True  # không xác định được giờ -> cho qua
    return dt >= now + timedelta(minutes=MIN_LEAD_MINUTES)


def emergency_info(lat=None, lon=None) -> dict:
    """Trả thông tin cấp cứu: số 115 + hotline cơ sở Vinmec gần nhất (nếu biết vị trí)."""
    national = EMERGENCY.get("national", "115")
    general = EMERGENCY.get("vinmec_hotline", "1900 232389")
    if lat is not None and lon is not None:
        fac, dist = nearest_vinmec_info(lat, lon)
        return {"national": national, "facility": fac["name"],
                "hotline": fac.get("hotline", general), "distance_km": round(dist, 1)}
    return {"national": national, "facility": None, "hotline": general, "distance_km": None}


def get_emergency_contact(lat=None, lon=None) -> str:
    """Số điện thoại cấp cứu khẩn (gọi NGAY khi tình trạng nguy hiểm)."""
    # Nếu agent không truyền vị trí, dùng toạ độ GPS đã có từ FE (nếu có)
    if (lat is None or lon is None) and _LOCATION_OVERRIDE:
        lat, lon = _LOCATION_OVERRIDE
    info = emergency_info(lat, lon)
    msg = f"CẤP CỨU - gọi NGAY {info['national']} (cấp cứu)."
    if info["facility"]:
        msg += f" Cơ sở gần bạn: {info['facility']} (cách ~{info['distance_km']} km)."
    elif info["hotline"] and info["hotline"] != info["national"]:
        msg += f" Hoặc hotline Vinmec {info['hotline']}."
    return msg


def _match_first_aid_category(condition: str) -> str:
    """Suy ra nhóm sơ cứu từ mô tả tình trạng (qua alias hoặc tên nhóm)."""
    c = (condition or "").strip().lower()
    if c in FIRST_AID:
        return c
    for kw, cat in FIRST_AID_ALIASES.items():
        if kw in c:
            return cat
    for cat in FIRST_AID:
        if cat != "chung" and cat in c:
            return cat
    return "chung"


def first_aid_steps(condition: str) -> list:
    """Trả về danh sách bước sơ cứu phù hợp với tình trạng."""
    return FIRST_AID.get(_match_first_aid_category(condition), FIRST_AID.get("chung", []))


def get_first_aid(condition: str) -> str:
    """Hướng dẫn sơ cứu cho người bị nạn theo tình trạng (vd 'đau ngực', 'co giật', 'chảy máu')."""
    cat = _match_first_aid_category(condition)
    steps = FIRST_AID.get(cat, FIRST_AID.get("chung", []))
    if not steps:
        return "Giữ bình tĩnh, đặt người bệnh ở tư thế an toàn và gọi 115 ngay."
    body = "\n".join(f"• {s}" for s in steps)
    return f"Sơ cứu ({cat}):\n{body}"


def check_doctor_availability(specialty: str, date: str = "") -> str:
    """Tra khung giờ trống (chỉ hiện slot cách hiện tại >= 30 phút). Nếu không có, gợi ý thay thế."""
    slots = DOCTOR_SCHEDULE.get(_canonical_specialty(specialty))
    if not slots:
        available = ", ".join(sorted(DOCTOR_SCHEDULE.keys()))
        return (f"Không có lịch cho chuyên khoa '{specialty}'. "
                f"GỢI Ý: có thể khám 'Nội tổng quát' (khám chung), hoặc chọn khoa đang có lịch: {available}.")
    valid = [s for s in slots if _is_bookable(s)]
    if not valid:
        return (f"Các khung giờ khám {specialty} hôm nay đều đã quá gần giờ hiện tại "
                f"(chỉ nhận đặt trước tối thiểu {MIN_LEAD_MINUTES} phút). Vui lòng chọn ngày mai hoặc khoa khác.")
    return f"Lịch trống {specialty} (đặt trước tối thiểu {MIN_LEAD_MINUTES} phút): " + "; ".join(valid)


def get_service_price(service_name: str) -> str:
    """Tra giá dịch vụ khám (VND)."""
    key = service_name.strip().lower()
    spec = key[5:].strip() if key.startswith("khám ") else key
    price = SERVICE_PRICES.get("khám " + _canonical_specialty(spec)) or SERVICE_PRICES.get(key)
    if price is None:
        return f"Không tìm thấy giá cho dịch vụ '{service_name}'."
    return f"{price:,} VND"


def book_appointment(specialty: str, time: str = "", doctor: str = "") -> str:
    """Xác nhận đặt lịch khám, trả về mã đặt lịch (mock). Từ chối nếu giờ quá gần hiện tại."""
    spec = _canonical_specialty(specialty)
    if time and not _is_bookable(str(time)):
        return (f"Không thể đặt lịch lúc '{time}' vì phải cách hiện tại tối thiểu "
                f"{MIN_LEAD_MINUTES} phút. Vui lòng chọn khung giờ muộn hơn hoặc ngày mai.")
    code = "VM" + str(sum(ord(c) for c in (spec + str(time))) % 100000).zfill(5)
    info = f"Khoa {specialty}, giờ {time}"
    if doctor:
        info += f", {doctor}"
    return f"Đặt lịch thành công! Mã đặt lịch: {code} ({info})."


def apply_insurance(price: float, insurance_type: str) -> str:
    """Tính số tiền phải trả sau khi áp bảo hiểm."""
    coverage = INSURANCE_COVERAGE.get(insurance_type.strip().lower())
    if coverage is None:
        return f"Không nhận diện được loại bảo hiểm '{insurance_type}'."
    payable = price * (1 - coverage)
    return f"{payable:,.0f} VND (bảo hiểm {insurance_type} giảm {int(coverage*100)}%)"


# ---------------------------------------------------------------------------
# Đăng ký tool cho agent (name + description + func)
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "get_current_location",
        "description": "Xác định vị trí hiện tại của người dùng qua IP. Không cần tham số. Trả về lat, lon, city.",
        "func": get_current_location,
    },
    {
        "name": "get_emergency_contact",
        "description": "Lấy số điện thoại CẤP CỨU khẩn (115 + cơ sở Vinmec gần nhất). Dùng khi tình trạng nguy hiểm. Tham số tùy chọn: lat, lon.",
        "func": get_emergency_contact,
    },
    {
        "name": "get_first_aid",
        "description": "Lấy hướng dẫn SƠ CỨU cho người bị nạn theo tình trạng. Tham số: condition (vd 'đau ngực', 'đột quỵ', 'co giật', 'chảy máu', 'khó thở', 'bỏng', 'ngộ độc', 'chấn thương').",
        "func": get_first_aid,
    },
    {
        "name": "find_nearest_vinmec",
        "description": "Tìm cơ sở Vinmec gần nhất. Tham số: lat (float), lon (float).",
        "func": find_nearest_vinmec,
    },
    {
        "name": "check_doctor_availability",
        "description": "Tra lịch bác sĩ trống. Tham số: specialty (chuyên khoa, vd 'Tim mạch'), date (tùy chọn).",
        "func": check_doctor_availability,
    },
    {
        "name": "get_service_price",
        "description": "Tra giá dịch vụ khám. Tham số: service_name (vd 'Khám Tim mạch').",
        "func": get_service_price,
    },
    {
        "name": "apply_insurance",
        "description": "Tính tiền phải trả sau bảo hiểm. Tham số: price (số tiền gốc), insurance_type (vd 'Vinmec Care').",
        "func": apply_insurance,
    },
    {
        "name": "book_appointment",
        "description": "Xác nhận ĐẶT lịch khám sau khi người dùng đồng ý. Tham số: specialty (chuyên khoa), time (khung giờ), doctor (tên bác sĩ, tùy chọn).",
        "func": book_appointment,
    },
]
