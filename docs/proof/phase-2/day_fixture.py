"""Local P2-05 preview of the proposed web interface, with scripted scenes."""
import argparse
import json
import math
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from time import monotonic

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from chonoi.contract import load_contract
from chonoi.day_config import day_plans
from chonoi.scenario import load_scenario
from chonoi.inputs import InputState, LiveInputs, normalize
from chonoi.inventory import items_to_counts
from chonoi.live import LiveGame, read_web_art
from chonoi.interactive_web import InteractiveDayWeb
from chonoi.runner import build_sim

TUNING = load_contract()["tuning"]
SPAWN = {"gather": [34, 8], "quan": [8, 5]}
DISHES = [
    "ca_loc_nuong_trui", "goi_bong_sung", "lau_ca_linh_dien_dien",
    "canh_chua_ca_loc", "ca_keo_nuong", "lau_mam",
]
ITEMS = ["ca_linh", "ca_loc", "ca_keo", "bong_sung", "bong_dien_dien", "keo_neo"]
STOCK = dict(zip(ITEMS, [6, 3, 3, 4, 2, 2]))
OPTIONS = [
    {"id": key, "label": label, "level": level, "price": price}
    for key, label, level, price in [
        ("oxygen_1", "Bình oxy", 1, 200), ("oxygen_2", "Bình oxy", 2, 400),
        ("hp_1", "Máu", 1, 250), ("hp_2", "Máu", 2, 500),
    ]
]


class Preview:
    live_scenes = False

    def __init__(self, days, faint):
        self.days, self.faint = days, faint
        self.set_screen("menu")
        self.day = 1
        self.upgrades = {"oxygen": 0, "hp": 0}
        self.last_active_oxygen = 0
        self.money = 300

    def set_screen(self, screen):
        self.screen, self.paused, self.elapsed = screen, False, 0
        self.started = monotonic()
        self.interact = False
        self.message = ""
        self.move = (0, 0)
        self.move_tick = 0
        self.mover = (build_sim(screen, TUNING, {"player": {"pos": SPAWN[screen]}}, 1, None)
                      if screen in SPAWN and not self.live_scenes else None)

    def advance_movement(self, tick):
        if not self.mover or self.paused:
            return
        inp = InputState(self.move, {}, set())
        for _ in range(self.move_tick, tick):
            self.mover._move(inp)
            if self.mover._ramp_left == 0 and not any(self.mover.vel):
                break
        self.move_tick = tick

    def tick(self):
        return int((self.elapsed + (0 if self.paused else monotonic() - self.started)) * 60)

    def action(self, action, data):
        if action == "start" and self.screen == "menu":
            self.__init__(self.days, self.faint)
            self.set_screen("day_intro")
        elif action == "menu":
            self.set_screen("menu")
        elif action == "pause" and self.screen in ("gather", "quan", "shop") and not self.paused:
            self.advance_movement(self.tick())
            self.elapsed += monotonic() - self.started
            self.move = (0, 0)
            self.paused = True
        elif action == "resume" and self.paused:
            self.paused, self.started = False, monotonic()
        elif action == "continue" and self.screen in ("day_intro", "evening_intro", "day_result"):
            self.set_screen({"day_intro": "gather", "evening_intro": "quan", "day_result": "shop"}[self.screen])
        elif action == "buy" and self.screen == "shop" and not self.paused:
            # Scripted success for one purchase; other attempts exercise feedback.
            if data.get("upgrade_id") == "oxygen_1" and not self.upgrades["oxygen"]:
                self.upgrades["oxygen"] = 1
                self.money -= 200
                self.message = "Đã mua bình oxy cấp 1. Có hiệu lực ngày kế tiếp."
            else:
                self.message = "Mua thất bại: nâng cấp này chưa khả dụng trong kịch bản."
        elif action == "shop_done" and self.screen == "shop" and not self.paused:
            if self.day == self.days:
                self.set_screen("summary")
            else:
                self.day += 1
                self.last_active_oxygen = self.upgrades["oxygen"]
                self.set_screen("day_intro")
        else:
            return False
        return True

    def keys(self, data):
        if "move" in data:
            move = data["move"]
            if not (isinstance(move, list) and len(move) == 2 and
                    all(type(value) in (int, float) and -1 <= value <= 1 for value in move)):
                return False
            if self.mover and not self.paused:
                self.advance_movement(self.tick())
                self.move = normalize(move)
        pressed = data.get("interact") is True
        if pressed and not self.interact and not self.paused:
            if self.screen == "gather":
                self.set_screen("evening_intro")
            elif self.screen == "quan":
                self.set_screen("day_result")
        self.interact = pressed
        return True

    def expire_shop(self):
        if self.screen == "shop" and not self.paused and self.tick() >= 600:
            self.action("shop_done", {})

    def snapshot(self):
        self.expire_shop()
        tick = self.tick()
        self.advance_movement(tick)
        inventory = {} if self.faint else STOCK
        served = 0 if self.faint else 2
        covered_days = self.days if self.screen == "summary" else 1
        state = dict(mode="day", screen=self.screen, day=self.day, days=self.days, fixture=True,
                     paused=self.paused, can_pause=self.screen in ("gather", "quan", "shop"), tick_hz=60,
                     menu=[{"dish_id": dish, "servings": 1} for dish in DISHES],
                     needed=STOCK, inventory=inventory, cookable=[] if self.faint else DISHES,
                     gather_reason="fainted" if self.faint else "docked",
                     result=dict(served=served*covered_days, left=2*covered_days,
                                 earned=110*covered_days if served else 0, tips=10*covered_days if served else 0,
                                 money=self.money, reputation=3.5 if served else 3),
                     shop=dict(money=self.money, time_left_ticks=max(0, 600-tick),
                               upgrades=self.upgrades, options=OPTIONS, message=self.message), events=[])
        if self.screen == "gather":
            oxygen = 2700 if self.last_active_oxygen else 1800
            fish = [{"id": f"F{i+1}", "kind": ITEMS[i%3], "heading_deg": 0,
                     "pos": [8+7*i+.7*math.sin(tick/48+i), 6+6*(i%3)]} for i in range(12)]
            nodes = [{"id": f"N{i+1}", "kind": ITEMS[3+i%3], "ready": True, "pos": [18+13*i, 0]} for i in range(6)]
            monsters = [{"id": "M1", "pos": [50+.8*math.sin(tick/50), 15], "state": "chase"}]
            if self.day >= 3:
                monsters.append({"id": "M2", "pos": [76, 21], "state": "patrol"})
            state["snapshot"] = dict(tick=tick, meta=TUNING["gather"], hold=["ca_keo","bong_sung","keo_neo"],
                hold_capacity=12, time_left_ticks=max(0, 10800-tick), fish=fish, nodes=nodes, monsters=monsters,
                player={"pos": list(self.mover.pos), "at_surface": self.mover._at_surface(),
                        "heading_deg": self.mover.heading, "hp": 2, "hp_max": 3,
                        "oxygen_ticks": max(0, oxygen-tick), "oxygen_max_ticks": oxygen, "catch_cd_ticks": 0})
            if tick >= 120:
                state["events"] = [{"name": "crocodile_hit", "tick": 120, "data": {"damage": 1}}]
        elif self.screen == "quan":
            stoves = [{**stove, "state": "cooking" if served else "idle",
                       "cook_ticks_left": 180+i*60, "dish": {"dish_id": DISHES[i]} if served else None}
                      for i, stove in enumerate(TUNING["quan"]["stoves"])]
            tables = TUNING["quan"]["tables"]
            customers = [{"id": f"C{i+1}", "table_id": t["id"], "state": "waiting", "order_status": "reserved",
                          "dish_id": DISHES[i+2], "reserved": {ITEMS[i]: 1},
                          "patience_ticks_left": max(0, 3600-i*280-tick)} for i, t in enumerate(tables)] if served else []
            state["snapshot"] = dict(tick=tick, meta=TUNING["quan"], time_left_ticks=max(0, 10800-tick),
                player={"pos": list(self.mover.pos)}, money=self.money, reputation=3, hand=None,
                stock=inventory, stoves=stoves, tables=tables, customers=customers)
        return state


class LiveScenesPreview(Preview):
    """Local day screen flow backed by real Gather and Quán simulations."""
    live_scenes = True

    def __init__(self, days, faint, scenario=None):
        self.scenario = scenario or {}
        self.plans = day_plans(TUNING, self.scenario.get("day", {}).get("day_plan", ()))
        self.inventory = []
        self.gather_reason = None
        self.results = []
        super().__init__(days, faint)
        self.money = 0

    def set_screen(self, screen):
        super().set_screen(screen)
        self.game = None
        self.served, self.left, self.tips = 0, 0, 0
        if screen == "gather":
            scenario = dict(self.scenario.get("gather", {}))
            if self.day != 1:
                scenario.pop("hold", None)
            if self.faint:
                scenario["player"] = {"pos": [50, 10], "hp": 1, "oxygen_ticks": 0, "zero_oxy_ticks": 59}
            self.game = LiveGame(screen, TUNING, scenario, self.day)
        elif screen == "quan":
            scenario = dict(self.scenario.get("quan", {}))
            if self.results:
                scenario["reputation"] = self.results[-1]["reputation"]
            tuning = {**TUNING, "menu": {dish: TUNING["menu"][dish] for dish in self.plans[self.day]["dishes"]}}
            self.game = LiveGame(screen, tuning, scenario, self.day, inventory=self.inventory)

    def update_scene(self):
        game = self.game
        if not game or self.paused:
            return
        target = self.tick()
        # No sim thread in this preview: the HTTP handler lock orders ticks and input changes.
        while game.session.tick < target and not game.session.done:
            game._tick_once()
            for event in reversed(game.events):
                if event["tick"] != game.session.tick:
                    break
                if event["name"] == "served":
                    self.served += 1
                elif event["name"] == "customer_left":
                    self.left += 1
                elif event["name"] == "paid":
                    self.tips += event["data"]["tip"]
        if not game.session.done:
            return
        sim = game.session.sim
        if self.screen == "gather":
            self.inventory = sim.inventory_items()
            self.gather_reason = sim.reason
            self.set_screen("evening_intro")
        else:
            self.money += sim.money
            self.results.append(dict(served=self.served, left=self.left, earned=sim.shift_earned,
                                     tips=self.tips, money=self.money, reputation=sim.reputation))
            self.set_screen("day_result")

    def keys(self, data):
        self.update_scene()
        if self.game and not self.paused:
            try:
                self.game.set_input(data)
            except ValueError:
                return False
        return True

    def action(self, action, data):
        if action == "start" and self.screen == "menu":
            self.__init__(self.days, self.faint, self.scenario)
            self.set_screen("day_intro")
            return True
        if action == "buy" or (action == "pause" and self.screen not in SPAWN):
            return False
        self.update_scene()
        if action == "pause":
            if not self.game:
                return False
            self.game.inputs = LiveInputs()
        return super().action(action, data)

    def expire_shop(self):
        # This preview does not run the Phase 2 shop engine.
        pass

    def snapshot(self):
        self.update_scene()
        state = dict(mode="day", screen=self.screen, day=self.day, days=self.days, live_scenes=True,
                     paused=self.paused, can_pause=self.game is not None, tick_hz=TUNING["tick_hz"], events=[])
        plan = self.plans[self.day]
        state.update(day_plan=plan, needed=plan["ingredients"],
                     menu=[{"dish_id": dish, "servings": count} for dish, count in plan["dishes"].items()])
        if self.game:
            snapshot = json.loads(self.game.state_json())
            snapshot["money"] += self.money
            state.update(snapshot=snapshot, events=snapshot["events"])
        elif self.screen == "evening_intro":
            threshold = TUNING["inventory"]["spoil_threshold"]
            available = items_to_counts([item for item in self.inventory if item["fresh"] >= threshold])
            state.update(inventory=self.inventory, spoil_threshold=threshold, gather_reason=self.gather_reason,
                         cookable=[name for name, dish in TUNING["menu"].items() if name in plan["dishes"]
                                   if all(available.get(k, 0) >= v for k, v in dish["recipe"].items())])
        elif self.screen in ("day_result", "summary"):
            result = self.results[-1].copy()
            if self.screen == "summary":
                for key in ("served", "left", "earned", "tips"):
                    result[key] = sum(row[key] for row in self.results)
            state["result"] = result
        elif self.screen == "shop":
            state["shop_unavailable"] = True
        return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--port", type=int, default=8782)
    parser.add_argument("--faint", action="store_true")
    parser.add_argument("--real-scenes", action="store_true", help="Use the real Gather and Quán simulations")
    parser.add_argument("--scenario", help="Scenario JSON for real scenes, including day.day_plan overrides")
    parser.add_argument("--contract-plan", action="store_true", help="Use the old preview with official targets, without gameplay extensions")
    args = parser.parse_args()
    preview_type = LiveScenesPreview if args.real_scenes else Preview
    if args.scenario and not args.real_scenes:
        parser.error("--scenario requires --real-scenes")
    scenario_path = args.scenario
    if args.real_scenes and not args.contract_plan and not scenario_path:
        scenario_path = str(ROOT / "chonoi/web/day-plan.json")
    options = {"scenario": load_scenario(scenario_path, "day", TUNING)} if scenario_path else {}
    if args.real_scenes and not args.contract_plan:
        config = json.loads((ROOT / "chonoi/web/gameplay.json").read_text(encoding="utf-8"))
        preview = InteractiveDayWeb(args.days, args.faint, tuning=TUNING, config=config, **options)
    else:
        preview = preview_type(args.days, args.faint, **options)
    with create_server(preview, args.port) as server:
        label = "Gameplay mở rộng 5 ngày" if isinstance(preview, InteractiveDayWeb) else (
            "Gather/Quán thật trong UI Phase 2" if args.real_scenes else "Fixture Phase 2")
        print(f"{label} tại http://127.0.0.1:{server.server_port}/", flush=True)
        server.serve_forever()


def create_server(preview, port=0):
    """Share the actual HTTP adapter with browser verification; no test-only endpoints."""
    lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, body, kind="application/json; charset=utf-8"):
            payload = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "public, max-age=300" if kind == "image/webp" else "no-store")
            self.end_headers()
            try:
                for i in range(0, len(payload), 65536):  # khúc 64 KB, xem chonoi/live.py _send
                    self.wfile.write(payload[i:i + 65536])
            except ConnectionError:
                # Poll requests may be cancelled when the browser navigates/closes.
                pass

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self.reply(200, (ROOT / "chonoi/web/index.html").read_bytes(), "text/html; charset=utf-8")
            elif path == "/state":
                with lock:
                    self.reply(200, preview.snapshot())
            elif (art := read_web_art(path)) is not None:
                self.reply(200, art, "image/webp")
            else:
                self.reply(404, {"ok": False})

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise ValueError
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError
            except ValueError:
                self.reply(400, {"ok": False})
                return
            with lock:
                preview.expire_shop()
                if self.path == "/input":
                    ok = preview.keys(data)
                    self.reply(200 if ok else 400, {"ok": ok})
                elif self.path == "/action":
                    ok = preview.action(data.get("action"), data)
                    self.reply(200 if ok else 409, {"ok": ok})
                else:
                    self.reply(404, {"ok": False})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.preview_lock = lock
    return server


if __name__ == "__main__":
    main()
