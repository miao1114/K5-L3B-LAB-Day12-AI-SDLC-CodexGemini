"""Buổi sáng — Lặn & Hái (`gather`). KHUNG: bơi, chặn mép, đồng hồ, cập bến, xuất kho.

Mặt cắt dòng sông nhìn NGANG: vị trí `[x, d]` (x sang phải, `d` độ sâu hướng xuống, d = 0 là mặt nước).
`move = [x, d]`: thành phần thứ hai DƯƠNG = bơi xuống. Hướng mặt là góc từ +x, dương = xuống.

Đã làm sẵn để smoke test chạy được: bơi + tăng/giảm tốc, chặn mép (d không âm), đồng hồ và hết giờ,
cập bến (`interact` trong vùng bến -> `gather_end` reason `docked`), xuất kho, snapshot đầy đủ trường gather.

Nhóm viết tiếp (đúng thứ tự một bước trong PRD mục 13.8, "Gather"):
  ĐÃ LÀM (lát 1, haidoan2426): bơi + oxy + biên + ngạt/ngất
      - oxy: dưới nước (d > surface_depth) trừ 1 tick/tick, mặt nước hồi oxygen_refill_per_tick, kẹp [0, max]
      - ngạt: oxy = 0 và đang dưới nước -> đếm zero_oxy_ticks, đủ choke_interval_ticks thì -1 Máu (choke)
      - Máu về 0 -> ngất (faint, gather_end reason `fainted`, mất toàn bộ giỏ, kho rỗng)
      - sự kiện dive / surface / oxygen_empty / choke / faint (test: tests/test_gather_sinh_ton.py)
  TODO(nhóm, lát 1 còn lại): giỏ: thứ tự nhặt (LIFO), sức chứa hold_capacity
  TODO(nhóm, lát 2): hái + bắt cá + cập bến + kho
      - hái nút ở mặt nước (gather, hold_full), nút mọc lại (node_regrown đã có phần đếm ngược)
      - bắt đàn cá bằng `catch` (fish_caught, hold_full, hồi chiêu catch_cd_ticks, chỉ khi dưới nước)
      - cập bến xét TRƯỚC hái (đã có); ghi kho đúng một lần do runner lo
Các tính năng của phase sau chưa nằm trong khung này.
"""

import math

from ..extensions import enabled
from ..ids import id_key, sort_by_id
from ..inventory import clone_items, materialize_items
from .monsters import init_monsters, monster_snapshot, step_monsters, upgrade_limit
from .ramp import ramp_velocity

TICK = 60.0
AXES = ("x", "d")


class GatherSim:
    mode = "gather"
    phase = "gather"

    def __init__(self, tuning, scenario, streams, ids, day=1, active_upgrades=None):
        t = tuning["gather"]
        self.t = t
        self.tick_hz = tuning["tick_hz"]
        self.day = day
        self.active_upgrades = dict(active_upgrades or {})
        self.rng = streams
        self.ids = ids
        p = scenario.get("player", {})
        self.pos = [float(c) for c in p.get("pos", t["start_pos"])]
        self.vel = [float(c) for c in p.get("vel", [0.0, 0.0])]
        self._tgt = None
        self._ramp_left = 0
        self.heading = float(p.get("heading_deg", t["start_heading_deg"]))
        oxygen_s = upgrade_limit(tuning, "oxygen", self.active_upgrades.get("oxygen", 0),
                                 "oxygen_max_s", t["oxygen_max_s"])
        self.oxygen_max = int(round(oxygen_s * TICK))
        self.oxygen_ticks = p.get("oxygen_ticks", self.oxygen_max)
        self.hp_max = upgrade_limit(tuning, "hp", self.active_upgrades.get("hp", 0),
                                    "hp_max", t["hp_max"])
        self.hp = p.get("hp", self.hp_max)
        self.zero_oxy_ticks = p.get("zero_oxy_ticks", 0)
        self.invuln_ticks = p.get("invuln_ticks", 0)
        self.catch_cd_ticks = p.get("catch_cd_ticks", 0)
        self.hold_items = materialize_items(scenario.get("hold", []), ids, allow_legacy=True)
        self.hold = [item["kind"] for item in self.hold_items]  # adapter cho luật cũ
        inv = tuning["inventory"]  # độ tươi: số liệu từ contract, không hard-code
        self.fresh_initial = float(inv["initial_fresh"])
        self.decay_tick = float(inv["gather_decay_per_s"]) / self.tick_hz
        self.spoil_threshold = float(inv["spoil_threshold"])
        self.time_left_ticks = scenario.get("time_left_ticks", int(round(t["duration_s"] * TICK)))
        # nút và đàn cá: scenario THAY THẾ danh sách mặc định; random_fish=false tắt cá mặc định
        src_nodes = scenario["nodes"] if "nodes" in scenario else t["nodes"]
        self.nodes = [{"id": n["id"], "kind": n["kind"], "pos": [float(c) for c in n["pos"]],
                       "regrow_ticks": n.get("regrow_ticks", 0)} for n in src_nodes]
        self.random_fish = scenario.get("random_fish", True)
        initial_fish = t["fish_initial"]
        self.fish_swim = self.random_fish and isinstance(initial_fish, int)
        defaults = initial_fish if self.random_fish and isinstance(initial_fish, list) else []
        src_fish = scenario.get("fish", defaults)
        self.fish_spawn_ticks = 0
        self.fish = [{"id": f["id"], "kind": f["kind"], "pos": [float(c) for c in f["pos"]],
                      "heading_deg": f.get("heading_deg", 0), "age_ticks": f.get("age_ticks", 0)} for f in src_fish]
        if self.fish_swim and "fish" not in scenario:
            for _ in range(initial_fish):
                self._spawn_fish()
        self.monsters = init_monsters(t, scenario, day=day)
        for coll in (self.nodes, self.fish, self.monsters):
            for e in coll:
                ids.reserve(e["id"])
        # extension dòng nước lũ (TICKET-03 "current"): chỉ chạy khi manifest bật
        self.phase_tick = 0
        self.current_cfg = t.get("current") if enabled(tuning, "current") else None
        self.random_current = scenario.get("random_current", True)
        self.current_direction = scenario.get("current_direction")
        self.current = None  # {"direction": ±1, "end_tick": phase tick kết thúc}
        self.money = 0
        self.earned = 0
        self.reputation = tuning["quan"]["reputation_initial"]
        self.done = False
        self.reason = None

    # --- giao diện cho runner -------------------------------------------------
    def inventory_items(self) -> list:
        return clone_items(self.hold_items)

    def snapshot(self) -> dict:
        snap = self._core_snapshot()
        if self.current_cfg is not None:
            snap["current"] = None if self.current is None else {
                "direction": self.current["direction"], "ticks_left": self.current["end_tick"] - self.phase_tick}
        return snap

    def _core_snapshot(self) -> dict:
        return {
            "player": {"pos": self.pos, "vel": self.vel, "heading_deg": self.heading,
                       "oxygen_ticks": self.oxygen_ticks, "oxygen_max_ticks": self.oxygen_max,
                       "hp": self.hp, "hp_max": self.hp_max, "zero_oxy_ticks": self.zero_oxy_ticks,
                       "invuln_ticks": self.invuln_ticks, "catch_cd_ticks": self.catch_cd_ticks,
                       "at_surface": self._at_surface()},
            "hold": clone_items(self.hold_items), "hold_count": len(self.hold),
            "hold_capacity": self.t["hold_capacity"],
            "nodes": [{"id": n["id"], "pos": n["pos"], "kind": n["kind"],
                       "ready": n["regrow_ticks"] == 0, "regrow_ticks": n["regrow_ticks"]}
                      for n in sort_by_id(self.nodes)],
            "fish": sort_by_id(self.fish),
            "monsters": monster_snapshot(self.monsters),
        }

    # --- một bước ---------------------------------------------------------------
    def step(self, inp):
        events = self._step(inp)
        if self.done and self.current is not None:
            # ca kết thúc giữa dòng lũ: current_end(phase_end) trước faint (nếu có) và gather_end
            at = next(i for i, (name, _) in enumerate(events) if name in ("faint", "gather_end"))
            events.insert(at, ("current_end", {"direction": self.current["direction"], "reason": "phase_end"}))
            self.current = None
        return events

    def _step_current_schedule(self, events):
        cfg = self.current_cfg
        if cfg is None or not self.random_current:
            return
        tick, interval = self.phase_tick, cfg["interval_ticks"]
        if self.current is not None and tick == self.current["end_tick"]:
            events.append(("current_end", {"direction": self.current["direction"], "reason": "elapsed"}))
            self.current = None
        if tick % interval == 0:
            direction = self.current_direction
            if direction is None:
                direction = self.rng.get("current").choice((-1, 1))
            self.current = {"direction": direction, "end_tick": tick + cfg["duration_ticks"]}
            events.append(("current_start", {"direction": direction, "duration_ticks": cfg["duration_ticks"]}))
        if (tick + cfg["warning_ticks"]) % interval == 0:
            events.append(("current_warning", {"starts_at_phase_tick": tick + cfg["warning_ticks"]}))

    def _step(self, inp):
        events = []
        self.phase_tick += 1
        # 1. đồng hồ và hàng có sẵn: giảm bộ đếm, nút mọc lại
        self.time_left_ticks = max(0, self.time_left_ticks - 1)
        self.invuln_ticks = max(0, self.invuln_ticks - 1)
        self.catch_cd_ticks = max(0, self.catch_cd_ticks - 1)
        for n in sort_by_id(self.nodes):
            if n["regrow_ticks"] > 0:
                n["regrow_ticks"] -= 1
                if n["regrow_ticks"] == 0:
                    events.append(("node_regrown", {"node_id": n["id"]}))
        # 1b. hao tươi hàng ĐÃ có trong giỏ ở đầu bước; spoiled khi vừa vượt xuống dưới ngưỡng, sắp theo ID
        crossed = []
        for item in self.hold_items:
            before = item["fresh"]
            item["fresh"] = max(0.0, before - self.decay_tick)
            if before >= self.spoil_threshold > item["fresh"]:
                crossed.append(item)
        for item in sorted(crossed, key=lambda i: id_key(i["id"])):
            events.append(("spoiled", {"item_id": item["id"], "kind": item["kind"], "location": "hold"}))
        # 1c. lịch dòng nước lũ (extension), trước di chuyển
        self._step_current_schedule(events)
        # 2. bơi + chặn mép + sinh tồn
        was_at_surface = self._at_surface()
        self._move(inp)
        at_surface = self._at_surface()
        if was_at_surface and not at_surface:
            events.append(("dive", {"pos": list(self.pos)}))
        elif not was_at_surface and at_surface:
            events.append(("surface", {"pos": list(self.pos)}))

        oxygen_before = self.oxygen_ticks
        if at_surface:
            self.oxygen_ticks = min(
                self.oxygen_max,
                self.oxygen_ticks + int(self.t["oxygen_refill_per_tick"]),
            )
            self.zero_oxy_ticks = 0
        else:
            self.oxygen_ticks = max(0, self.oxygen_ticks - 1)
            if oxygen_before > 0 and self.oxygen_ticks == 0:
                events.append(("oxygen_empty", {"pos": list(self.pos)}))
            if self.oxygen_ticks == 0:
                self.zero_oxy_ticks += 1
                choke_interval = int(self.t["choke_interval_ticks"])
                if self.zero_oxy_ticks >= choke_interval:
                    self.zero_oxy_ticks = 0
                    self.hp = max(0, self.hp - 1)
                    events.append(("choke", {"hp": self.hp, "pos": list(self.pos)}))
                    if self.hp == 0:
                        events.append(("faint", {
                            "cause": "choke", "lost": clone_items(list(reversed(self.hold_items))),
                            "hp": self.hp,
                        }))
                        self.hold.clear()
                        self.hold_items.clear()
                        self._finish("fainted", events)
                        return events
        monster_events, fainted = self._apply_monsters()
        events.extend(monster_events)
        if fainted:
            self._finish("fainted", events)
            return events
        # 3. interact: bến trước, rồi hái
        if inp.pressed("interact"):
            if self._in_dock():
                self._finish("docked", events)
                return events
            # hái nút `ready` gần nhất trong interact_radius, chỉ khi ở mặt nước
            if self._at_surface():
                candidates = [n for n in sort_by_id(self.nodes)
                              if n["regrow_ticks"] == 0
                              and math.dist(self.pos, n["pos"]) <= self.t["interact_radius"]]
                if candidates:
                    node = min(candidates, key=lambda n: math.dist(self.pos, n["pos"]))
                    amount = int(self.t["node_yield"])
                    free, required = self._collection_slots(node["kind"], amount, "gather")
                    if free < required:
                        events.append(("hold_full", {"action": "gather", "node_id": node["id"],
                                                     "required": required, "free": free}))
                    else:
                        self.hold.extend([node["kind"]] * amount)
                        self.hold_items.extend({"id": self.ids.next_item_id(), "kind": node["kind"],
                                                "fresh": self.fresh_initial} for _ in range(amount))
                        self._collected_items(self.hold_items[-amount:], "gather")
                        node["regrow_ticks"] = int(round(self.t["regrow_s"] * TICK))
                        events.append(("gather", {"node_id": node["id"], "kind": node["kind"],
                                                  "amount": amount}))
        # 4. bắt cá
        if inp.pressed("catch"):
            # bắt đàn gần nhất trong catch_radius, chỉ khi hết hồi chiêu và dưới nước
            if self.catch_cd_ticks == 0 and not self._at_surface():
                candidates = [f for f in sort_by_id(self.fish)
                              if math.dist(self.pos, f["pos"]) <= self.t["catch_radius"]]
                if candidates:
                    fish = min(candidates, key=lambda f: math.dist(self.pos, f["pos"]))
                    amount = int(self.t["fish_yield"][fish["kind"]])
                    free, required = self._collection_slots(fish["kind"], amount, "catch")
                    if free < required:
                        events.append(("hold_full", {"action": "catch", "fish_id": fish["id"],
                                                     "required": required, "free": free}))
                    else:
                        self.hold.extend([fish["kind"]] * amount)
                        self.hold_items.extend({"id": self.ids.next_item_id(), "kind": fish["kind"],
                                                "fresh": self.fresh_initial} for _ in range(amount))
                        self._collected_items(self.hold_items[-amount:], "catch")
                        self.fish.remove(fish)
                        self.catch_cd_ticks = int(round(self.t["catch_cooldown_s"] * TICK))
                        events.append(("fish_caught", {"fish_id": fish["id"], "kind": fish["kind"],
                                                       "yield": amount}))
        # 5. xét hết giờ trước khi cá thường bơi và sinh đàn
        if self.time_left_ticks <= 0:
            self._finish("time", events)
        elif self.fish_swim:
            self._move_fish()
            self.fish_spawn_ticks += 1
            if self.fish_spawn_ticks == self.t["fish_spawn_ticks"]:
                self.fish_spawn_ticks = 0
                fish = self._spawn_fish()
                if fish is not None:
                    events.append(("fish_spawned", {k: fish[k] for k in ("id", "kind", "pos")}))
        return events

    # --- tiện ích ---------------------------------------------------------------
    def _collection_slots(self, kind, amount, action):
        """Standard contract: every physical ingredient occupies one slot."""
        return self.t["hold_capacity"] - len(self.hold), amount

    def _collected_items(self, items, action):
        """Optional interactive basket hook; no additional state in standard mode."""

    def _apply_monsters(self):
        before_items = list(self.hold_items)
        self.hp, self.invuln_ticks, events, fainted = step_monsters(
            self.monsters, self.t, self.pos, self.hp, self.invuln_ticks,
            self.hold, tick_hz=self.tick_hz)
        del self.hold_items[len(self.hold):]
        n_hit = next((len(data["lost"]) for name, data in events if name == "monster_hit"), 0)
        popped = before_items[len(before_items) - n_hit:]
        remaining = before_items[:len(before_items) - n_hit]
        for name, data in events:
            if name == "monster_hit":
                data["lost"] = clone_items(list(reversed(popped)))
            elif name == "faint":
                data["lost"] = clone_items(list(reversed(remaining)))
        return events, fainted

    def _at_surface(self) -> bool:
        return self.pos[1] <= self.t["surface_depth"]

    def _in_dock(self) -> bool:
        return math.dist(self.pos, self.t["dock_pos"]) <= self.t["dock_radius"]

    def _finish(self, reason, events):
        self.done = True
        self.reason = reason
        events.append(("gather_end", {"reason": reason, "inventory": {"items": self.inventory_items()}}))

    def _move(self, inp):
        speed = self.t["swim_speed"]
        mx, md = inp.move
        self.vel = ramp_velocity(self, (mx * speed, md * speed), int(self.t["ramp_max_ticks"]))
        if (mx, md) != (0.0, 0.0):
            self.heading = math.degrees(math.atan2(md, mx)) % 360
        b = self.t["bounds"]
        drift = 0.0  # lực dòng lũ: cộng thẳng vào vị trí, không tích lũy vào vel
        if self.current is not None and self.pos[1] >= self.current_cfg["min_depth"]:
            drift = self.current["direction"] * self.current_cfg["speed"] / TICK
        for i, axis in enumerate(AXES):
            self.pos[i] += self.vel[i] / TICK + (drift if i == 0 else 0.0)
            lo, hi = b[axis]
            if self.pos[i] <= lo:
                self.pos[i] = lo
                self.vel[i] = max(0.0, self.vel[i])
            elif self.pos[i] >= hi:
                self.pos[i] = hi
                self.vel[i] = min(0.0, self.vel[i])

    def _move_fish(self):
        distance = self.t["fish_speed"] / TICK
        turn_ticks = self.t["fish_turn_ticks"]
        rng = self.rng.get("fish_swim")
        for fish in sort_by_id(self.fish):
            fish["age_ticks"] += 1
            heading = fish["heading_deg"]
            if fish["age_ticks"] % turn_ticks == 0:
                heading = rng.random() * 360
            angle = math.radians(heading)
            x, d = fish["pos"]
            x, reflect_x = self._reflect(x, math.cos(angle) * distance, self.t["fish_x"])
            d, reflect_d = self._reflect(d, math.sin(angle) * distance, self.t["fish_depths"][fish["kind"]])
            if reflect_x:
                heading = (180 - heading) % 360
            if reflect_d:
                heading = -heading % 360
            fish.update(pos=[x, d], heading_deg=heading)

    @staticmethod
    def _reflect(position, delta, bounds):
        lo, hi = bounds
        next_pos = min(max(position, lo), hi) + delta
        if next_pos <= lo and delta < 0:
            return 2 * lo - next_pos, True
        if next_pos >= hi and delta > 0:
            return 2 * hi - next_pos, True
        return next_pos, False

    def _spawn_fish(self):
        if len(self.fish) >= self.t["fish_max"]:
            return None
        clearance = self.t["fish_spawn_clearance"]
        spots = {}
        for kind, depths in sorted(self.t["fish_spawn_depths"].items()):
            available = [(x, d) for x in self.t["fish_spawn_x"] for d in depths
                         if all(math.dist((x, d), fish["pos"]) > clearance for fish in self.fish)]
            if available:
                spots[kind] = available
        if not spots:
            return None
        rng = self.rng.get("fish_spawn")
        kinds = list(spots)
        kind = rng.choices(kinds, weights=[self.t["fish_weights"][key] for key in kinds])[0]
        fish = {"id": self.ids.new("F"), "kind": kind, "pos": list(rng.choice(spots[kind])),
                "heading_deg": rng.random() * 360, "age_ticks": 0}
        self.fish.append(fish)
        return fish
