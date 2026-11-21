"""Extension tùy chọn Phase 3 (TICKET-03): `current` (dòng nước lũ) và `reservations` (khách đặt trước).

Bật bằng danh sách `extensions` ở gốc `game.contract.json`; `load_contract` chép danh sách đó vào
`tuning["extensions"]` để các sim đọc được. Khi tắt, sim không đổi event/snapshot nào của lõi.
"""

from .errors import BadInput

KNOWN = ("current", "reservations")


def enabled(tuning, name) -> bool:
    return name in tuning.get("extensions", ())


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _pos_int(name, v):
    if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
        raise BadInput(f"tuning.{name} phải là số nguyên dương")


def validate_extensions(contract):
    """Kiểm danh sách `extensions` và cấu hình của extension được bật (lỗi -> mã 2)."""
    exts = contract.get("extensions", [])
    if not isinstance(exts, list) or any(e not in KNOWN for e in exts) or len(set(exts)) != len(exts):
        raise BadInput(f"extensions phải là mảng không trùng, gồm các mã {list(KNOWN)}")
    tuning = contract["tuning"]
    if "current" in exts:
        cur = tuning["gather"].get("current")
        if not isinstance(cur, dict) or set(cur) != {"interval_ticks", "duration_ticks", "warning_ticks",
                                                     "min_depth", "speed"}:
            raise BadInput("tuning.gather.current thiếu/sai khóa")
        for key in ("interval_ticks", "duration_ticks", "warning_ticks"):
            _pos_int(f"gather.current.{key}", cur[key])
        if cur["warning_ticks"] >= cur["interval_ticks"]:
            raise BadInput("tuning.gather.current.warning_ticks phải nhỏ hơn interval_ticks")
        if not (_num(cur["min_depth"]) and cur["min_depth"] >= 0 and _num(cur["speed"]) and cur["speed"] > 0):
            raise BadInput("tuning.gather.current.min_depth >= 0 và speed > 0")
    if "reservations" in exts:
        res = tuning.get("reservations")
        if not isinstance(res, dict) or set(res) != {"count", "table_hold_s", "price_multiplier",
                                                    "failed_reputation_delta"}:
            raise BadInput("tuning.reservations thiếu/sai khóa")
        _pos_int("reservations.count", res["count"])
        if res["count"] > len(tuning["quan"]["tables"]):
            raise BadInput("tuning.reservations.count vượt số bàn")
        if not (_num(res["table_hold_s"]) and res["table_hold_s"] > 0
                and _num(res["price_multiplier"]) and res["price_multiplier"] > 0
                and _num(res["failed_reputation_delta"]) and res["failed_reputation_delta"] < 0):
            raise BadInput("tuning.reservations: table_hold_s, price_multiplier > 0 và failed_reputation_delta < 0")
    tuning["extensions"] = list(exts)
