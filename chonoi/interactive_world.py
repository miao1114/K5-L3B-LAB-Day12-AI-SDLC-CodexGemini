"""Bản đồ Gather dài hơn cho bản web 5 ngày (`chonoi/web/gameplay.json` → `gather_world`).

Chỉ InteractiveDaySim gọi module này; headless/Test Contract giữ nguyên bounds 0..100.
Số đàn cá, số cây, nhịp sinh, yield, loại nguyên liệu và cá sấu giữ nguyên: chỉ giãn tọa độ x
theo chiều dài mới. Bến (`dock_pos`) và điểm xuất phát giữ vị trí quen thuộc.
"""
from copy import deepcopy
from numbers import Real

from .errors import BadInput


def world_tuning(tuning, config):
    world = config.get("gather_world")
    if not world:
        return tuning
    keys = {"length_m", "natural_fish", "swim_speed_multiplier", "current_speed", "monster_chase_speed"}
    if not isinstance(world, dict) or set(world) - keys:
        raise BadInput(f"gather_world chỉ nhận {sorted(keys)}")
    gather = deepcopy(tuning["gather"])
    lo, hi = gather["bounds"]["x"]
    span = hi - lo
    length = world.get("length_m", span)
    if isinstance(length, bool) or not isinstance(length, Real) or not span <= length <= 4 * span:
        raise BadInput(f"gather_world.length_m phải trong [{span}, {4 * span}]")
    scale = length / span
    swim = world.get("swim_speed_multiplier", 1)
    if isinstance(swim, bool) or not isinstance(swim, Real) or not 1 <= swim <= 5:
        raise BadInput("gather_world.swim_speed_multiplier phải trong [1, 5]")
    speeds = {}
    for key in ("current_speed", "monster_chase_speed"):  # m/s, ghi đè số chuẩn khi có
        if key in world:
            value = world[key]
            if isinstance(value, bool) or not isinstance(value, Real) or not 0 < value <= 20:
                raise BadInput(f"gather_world.{key} phải trong (0, 20] m/s")
            speeds[key] = float(value)

    def stretch(x):
        return round(lo + (x - lo) * scale, 2)

    gather["bounds"] = {**gather["bounds"], "x": [lo, lo + length]}
    # Biên bơi của cá giữ nguyên khoảng cách tới hai mép như bản chuẩn.
    gather["fish_x"] = [gather["fish_x"][0], lo + length - (hi - gather["fish_x"][1])]
    # Điểm sinh giãn theo chiều dài và thêm điểm giữa để rải đều hơn; số đàn do fish_initial/fish_max quyết định.
    spots = [stretch(x) for x in gather["fish_spawn_x"]]
    gather["fish_spawn_x"] = sorted(set(spots + [round((a + b) / 2, 2) for a, b in zip(spots, spots[1:])]))
    gather["nodes"] = [{**node, "pos": [stretch(node["pos"][0]), node["pos"][1]]} for node in gather["nodes"]]
    monsters = gather["monsters"]
    monsters["spawns"] = [{**m, "pos": [stretch(m["pos"][0]), m["pos"][1]],
                           "waypoints": [[stretch(p[0]), p[1]] for p in m["waypoints"]]}
                          for m in monsters["spawns"]]
    # Dữ liệu cho giao diện: ảnh nền gốc vẽ đúng `art_span_m` mét sông.
    gather["swim_speed"] = gather["swim_speed"] * swim  # bơi nhanh hơn trên sông dài (chỉ bản web)
    if "current_speed" in speeds and isinstance(gather.get("current"), dict):
        gather["current"]["speed"] = speeds["current_speed"]  # dòng lũ cuốn người chơi ở độ sâu ≥ min_depth
    if "monster_chase_speed" in speeds:
        for species in monsters["species"].values():
            species["chase_speed"] = speeds["monster_chase_speed"]  # chỉ tốc độ đuổi; tuần tra giữ nguyên
    gather["view"] = {"art_span_m": span}
    gather["natural_fish"] = bool(world.get("natural_fish", False))
    return {**tuning, "gather": gather}
