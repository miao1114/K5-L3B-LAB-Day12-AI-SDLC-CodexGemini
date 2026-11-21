"""Nạp và kiểm scenario (Contract D). Trả về dict của đúng khối theo mode.

KHUNG: kiểm cú pháp, id trùng, bộ đếm âm, khoang vượt sức chứa, trường lạ.
TODO(nhóm): bổ sung kiểm mâu thuẫn mức luật mà nhóm cần (khách giữ chỗ quá kho, đơn assigned
phải có đúng một món, khách eating thiếu giá/tip...) — xem PRD-0 mục D và 'Mâu thuẫn -> mã 2'.
"""

import json
import math

from .day_config import gather_tuning
from .errors import BadInput
from .extensions import enabled
from .inventory import KINDS_P2, validate_inventory_items, validate_items
from .sim.monsters import monster_config

GATHER_KEYS = {"player", "hold", "nodes", "fish", "monsters", "random_fish", "time_left_ticks"}
GATHER_PLAYER_KEYS = {"pos", "vel", "heading_deg", "hp", "oxygen_ticks", "zero_oxy_ticks",
                      "invuln_ticks", "catch_cd_ticks"}
NODE_KINDS = ("bong_dien_dien", "bong_sung", "keo_neo")
FISH_KINDS = ("ca_linh", "ca_loc", "ca_keo")
QUAN_PLAYER_KEYS = {"pos", "vel"}
QUAN_KEYS = {"player", "stock", "hand", "stoves", "tables", "customers", "random_customers",
             "reputation", "time_left_ticks"}


def _check_ids(name, arr):
    if not isinstance(arr, list):
        raise BadInput(f"{name} phải là mảng")
    seen = set()
    for e in arr:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not e["id"]:
            raise BadInput(f"{name}: mỗi phần tử cần id (chuỗi khác rỗng)")
        if e["id"] in seen:
            raise BadInput(f"{name}: id trùng {e['id']}")
        seen.add(e["id"])


def load_scenario(path, mode: str, tuning: dict) -> dict:
    if path is None:
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise BadInput(f"không đọc được scenario {path}: {e}")
    allowed = {"day", "gather", "quan"} if mode == "day" else {mode}
    if not isinstance(data, dict) or set(data) - allowed:
        raise BadInput(f"khối sai mode: --mode {mode} nhận các khối {sorted(allowed)}")
    if mode == "day":
        effective = _validate_day(data.get("day", {}), tuning)
        _validate_block(data.get("gather", {}), "gather", effective)
        quan = _validate_block(data.get("quan", {}), "quan", tuning)
        if quan.keys() & {"stock", "reputation"}:
            raise BadInput("day không nhận quan.stock hoặc quan.reputation")
        _check_item_ids_across_blocks(data)
        return data
    block = _validate_block(data.get(mode, {}), mode, tuning)
    _check_item_ids_across_blocks({mode: block})
    return block


def _check_item_ids_across_blocks(data):
    seen = set()
    for mode, field in (("gather", "hold"), ("quan", "stock")):
        raw = data.get(mode, {}).get(field)
        if isinstance(raw, list) and (not raw or isinstance(raw[0], dict)):
            for item in validate_inventory_items(raw):
                if item["id"] in seen:
                    raise BadInput(f"id nguyên liệu trùng trong scenario: {item['id']}")
                seen.add(item["id"])


def _validate_day(initial, tuning):
    if not isinstance(initial, dict) or set(initial) - {"money", "earned", "reputation", "upgrades", "day_plan"}:
        raise BadInput("khối day có trường chưa hỗ trợ")
    money, earned = initial.get("money", 0), initial.get("earned", 0)
    _nonneg_int("day.money", money)
    _nonneg_int("day.earned", earned)
    if money > earned:
        raise BadInput("day.money không được vượt day.earned")
    quan = tuning["quan"]
    rep = initial.get("reputation", quan["reputation_initial"])
    if not _num(rep) or not quan["reputation_min"] <= rep <= quan["reputation_max"]:
        raise BadInput("day.reputation ngoài miền")
    if "day_plan" in initial and not isinstance(initial["day_plan"], list):
        raise BadInput("day.day_plan phải là mảng")
    return gather_tuning(tuning, initial.get("upgrades", {}))


def _validate_block(block, mode, tuning):
    if not isinstance(block, dict):
        raise BadInput(f"khối {mode} phải là object")
    allowed = set(GATHER_KEYS if mode == "gather" else QUAN_KEYS)
    if mode == "gather" and enabled(tuning, "current"):
        allowed |= {"random_current", "current_direction"}
    if mode == "quan" and enabled(tuning, "reservations"):
        allowed |= {"reservations", "random_reservations"}
    extra = set(block) - allowed
    if extra:
        raise BadInput(f"trường lạ/chưa hỗ trợ trong {mode}: {sorted(extra)}")
    dur = int(round(tuning[mode]["duration_s"] * 60))
    if "time_left_ticks" in block:
        t = block["time_left_ticks"]
        if isinstance(t, bool) or not isinstance(t, int) or not (1 <= t <= dur):
            raise BadInput(f"time_left_ticks phải là số nguyên trong [1, {dur}]")
    if mode == "gather":
        _validate_gather(block, tuning)
    else:
        _validate_quan(block, tuning)
    return block


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _nonneg_int(name, v):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise BadInput(f"{name} phải là số nguyên không âm")


def _pos(name, pos, bounds, axes=("x", "d")):
    if not (isinstance(pos, list) and len(pos) == 2 and all(_num(c) for c in pos)):
        raise BadInput(f"{name} phải là [{axes[0]}, {axes[1]}]")
    for c, axis in zip(pos, axes):
        lo, hi = bounds[axis]
        if not (lo <= c <= hi):
            raise BadInput(f"{name} nằm ngoài vùng nước ({axis} ∈ [{lo}, {hi}])")


def _validate_gather(b, tuning):
    g = tuning["gather"]
    bounds = g["bounds"]
    for arr in ("nodes", "fish", "monsters"):
        if arr in b:
            _check_ids(arr, b[arr])
    if "random_fish" in b and not isinstance(b["random_fish"], bool):
        raise BadInput("random_fish phải là boolean")
    if "random_current" in b and b["random_current"] is not False:
        raise BadInput("random_current chỉ nhận false")
    if "current_direction" in b and (type(b["current_direction"]) is not int or b["current_direction"] not in (-1, 1)):
        raise BadInput("current_direction phải là -1 hoặc 1")
    if "hold" in b:
        h = b["hold"]
        if isinstance(h, list) and (not h or isinstance(h[0], dict)):
            validate_inventory_items(h)
        elif not isinstance(h, list) or any(k not in KINDS_P2 for k in h):
            raise BadInput("hold phải là mảng nguyên liệu hợp lệ")
        if len(h) > g["hold_capacity"]:
            raise BadInput("hold vượt sức chứa")
    p = b.get("player", {})
    if not isinstance(p, dict):
        raise BadInput("player phải là object")
    extra = set(p) - GATHER_PLAYER_KEYS
    if extra:
        raise BadInput(f"trường lạ/chưa hỗ trợ trong gather.player: {sorted(extra)}")
    if "pos" in p:
        _pos("player.pos", p["pos"], bounds)
    if "vel" in p and not (isinstance(p["vel"], list) and len(p["vel"]) == 2 and all(_num(c) for c in p["vel"])):
        raise BadInput("player.vel phải là [x, d]")
    if "heading_deg" in p and not _num(p["heading_deg"]):
        raise BadInput("player.heading_deg phải là số")
    for key in ("invuln_ticks", "catch_cd_ticks", "zero_oxy_ticks", "oxygen_ticks", "hp"):
        if key in p:
            _nonneg_int(f"player.{key}", p[key])
    omax = int(round(g["oxygen_max_s"] * 60))
    if "oxygen_ticks" in p and p["oxygen_ticks"] > omax:
        raise BadInput("player.oxygen_ticks vượt oxy tối đa")
    if "hp" in p and not (1 <= p["hp"] <= g["hp_max"]):
        raise BadInput("player.hp phải trong [1, hp_max]")
    if "zero_oxy_ticks" in p:
        pos = p.get("pos", g["start_pos"])
        oxy = p.get("oxygen_ticks", omax)
        if p["zero_oxy_ticks"] > 59:
            raise BadInput("player.zero_oxy_ticks phải trong [0, 59]")
        if p["zero_oxy_ticks"] > 0 and not (oxy == 0 and pos[1] > g["surface_depth"]):
            raise BadInput("player.zero_oxy_ticks > 0 chỉ khi oxy = 0 và đang dưới nước")
    for n in b.get("nodes", []):
        if n.get("kind") not in NODE_KINDS:
            raise BadInput(f"nodes.{n['id']}: kind phải là một trong {NODE_KINDS}")
        _pos(f"nodes.{n['id']}.pos", n.get("pos"), bounds)
        if n["pos"][1] != 0:
            raise BadInput(f"nodes.{n['id']}: nút hái nằm ở mặt nước (d = 0)")
        if "regrow_ticks" in n:
            _nonneg_int(f"nodes.{n['id']}.regrow_ticks", n["regrow_ticks"])
    for f in b.get("fish", []):
        if f.get("kind") not in FISH_KINDS:
            raise BadInput(f"fish.{f['id']}: kind phải là một trong {FISH_KINDS}")
        _pos(f"fish.{f['id']}.pos", f.get("pos"), bounds)
        if f["pos"][1] <= g["surface_depth"]:
            raise BadInput(f"fish.{f['id']}: đàn cá phải ở dưới nước")
        if "heading_deg" in f and not _num(f["heading_deg"]):
            raise BadInput(f"fish.{f['id']}.heading_deg phải là số")
        if "age_ticks" in f:
            _nonneg_int(f"fish.{f['id']}.age_ticks", f["age_ticks"])
    for m in b.get("monsters", []):
        _validate_monster(m, g)


def _validate_monster(monster, gather):
    name = f"monsters.{monster['id']}"
    allowed = {"id", "kind", "pos", "waypoints", "target_idx", "state", "state_ticks_left", "recoil_dir"}
    kind = monster.get("kind")
    species = monster_config(gather)["species"]
    if set(monster) - allowed or not isinstance(kind, str) or kind not in species:
        raise BadInput(f"{name}: loài hoặc trường không hợp lệ")
    bounds = {**gather["bounds"], "d": species[kind]["depths"]}
    _pos(f"{name}.pos", monster.get("pos"), bounds)
    waypoints = monster.get("waypoints")
    if not isinstance(waypoints, list) or len(waypoints) != 2:
        raise BadInput(f"{name}: cần đúng hai waypoint")
    for point in waypoints:
        _pos(f"{name}.waypoints", point, bounds)
    target = monster.get("target_idx", 1)
    state = monster.get("state", "patrol")
    ticks = monster.get("state_ticks_left", 0)
    _nonneg_int(f"{name}.state_ticks_left", ticks)
    if type(target) is not int or target not in (0, 1) or state not in ("patrol", "chase", "recoil", "stunned"):
        raise BadInput(f"{name}: target_idx hoặc state không hợp lệ")
    direction = monster.get("recoil_dir")
    if state == "recoil":
        if (ticks == 0 or not isinstance(direction, list) or len(direction) != 2
                or not all(_num(value) and math.isfinite(value) for value in direction)
                or not math.isclose(math.hypot(*direction), 1.0, rel_tol=0, abs_tol=1e-6)):
            raise BadInput(f"{name}: recoil cần timer dương và vector đơn vị")
    elif (state == "stunned" and ticks == 0) or (state != "stunned" and ticks != 0) or direction is not None:
        raise BadInput(f"{name}: timer và hướng recoil không khớp trạng thái")


def _validate_quan(b, tuning):
    for arr in ("stoves", "tables", "customers"):
        if arr in b:
            _check_ids(arr, b[arr])
    if "stock" in b:
        if isinstance(b["stock"], list):
            validate_inventory_items(b["stock"])
        else:
            validate_items(b["stock"])
    p = b.get("player", {})
    if not isinstance(p, dict) or set(p) - QUAN_PLAYER_KEYS:
        raise BadInput("quan.player chỉ có pos và vel")
    qb = tuning["quan"]["bounds"]
    if "pos" in p:
        _pos("player.pos", p["pos"], qb, axes=("x", "z"))
    if "vel" in p and not (isinstance(p["vel"], list) and len(p["vel"]) == 2 and all(_num(c) for c in p["vel"])):
        raise BadInput("player.vel phải là [x, z]")
    table_ids = [c.get("table_id") for c in b.get("customers", [])]
    known = {t["id"] for t in tuning["quan"]["tables"]} | {t.get("id") for t in b.get("tables", [])}
    for c in b.get("customers", []):
        if not isinstance(c.get("table_id"), str) or c["table_id"] not in known:
            raise BadInput(f"customers.{c['id']}: table_id phải là bàn có thật")
    if len(table_ids) != len(set(table_ids)):
        raise BadInput("hai khách cùng bàn")
    if "random_reservations" in b and b["random_reservations"] is not False:
        raise BadInput("random_reservations chỉ nhận false")
    if "reservations" in b:
        _validate_reservations(b["reservations"], tuning, known)


def _validate_reservations(arr, tuning, tables):
    _check_ids("reservations", arr)
    cfg = tuning["reservations"]
    dur = int(round(tuning["quan"]["duration_s"] * 60))
    if len(arr) > cfg["count"]:
        raise BadInput(f"reservations tối đa {cfg['count']} đơn")
    seen_tables = set()
    for r in arr:
        if set(r) != {"id", "table_id", "dish_id", "arrival_tick"}:
            raise BadInput(f"reservations.{r['id']}: cần đúng id, table_id, dish_id, arrival_tick")
        if r["table_id"] not in tables or r["table_id"] in seen_tables:
            raise BadInput(f"reservations.{r['id']}: bàn không có thật hoặc trùng bàn")
        seen_tables.add(r["table_id"])
        if r["dish_id"] not in tuning["menu"]:
            raise BadInput(f"reservations.{r['id']}: món không có trong thực đơn")
        t = r["arrival_tick"]
        if isinstance(t, bool) or not isinstance(t, int) or not 1 <= t < dur:
            raise BadInput(f"reservations.{r['id']}: arrival_tick phải nguyên trong [1, {dur - 1}]")
