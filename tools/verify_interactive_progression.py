"""Collect targets with real movement/timers/RNG, then serve and close Shop over five days."""
from collections import Counter
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chonoi.contract import load_contract
from chonoi.inputs import BUTTONS_V11, LiveInputs, normalize
from chonoi.interactive import InteractiveSession
from chonoi.scenario import load_scenario

PROOF = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/proof/gameplay-enhancement"


def run(seed):
    tuning = load_contract()["tuning"]
    scenario = load_scenario(ROOT / "chonoi/web/day-plan.json", "day", tuning)
    config = json.loads((ROOT / "chonoi/web/gameplay.json").read_text())
    session = InteractiveSession(tuning, scenario, seed, 5, config)
    inputs = LiveInputs(BUTTONS_V11)
    collected = {}
    rows, frames = session.start_events(), []
    previous = None
    while not session.done and session.tick < 5 * 22200:
        sim, target = session.sim, None
        c = sim.current
        interact = catch = shop_done = False
        buy = None
        if sim.phase == "gather":
            g = c
            counts = Counter(i["kind"] for i in g.hold_items if i["fresh"] >= g.spoil_threshold)
            needed = {k: n - counts[k] for k, n in sim.plan["ingredients"].items() if counts[k] < n}
            if not needed:
                collected.setdefault(sim.day, {"tick": session.phase_tick,
                    "seconds": session.phase_tick / tuning["tick_hz"], "items": counts,
                    "slots": g.snapshot()["hold_slots_used"]})
                target = g.t["dock_pos"] if g._at_surface() else [g.pos[0], 0]
                interact = g._in_dock()
            elif g.oxygen_ticks < ((g.pos[1] / g.t["swim_speed"] + 5) * tuning["tick_hz"]):
                target = [g.pos[0], 0]
            elif g._at_surface() and g.oxygen_ticks < g.oxygen_max * .9:
                target = [g.pos[0], 0]
            else:
                candidates = [(math.dist(g.pos, f["pos"]) +
                               (100 if any(math.dist(m["pos"], f["pos"]) < 8 for m in g.monsters) else 0),
                               "fish", f) for f in g.fish if f["kind"] in needed]
                candidates += [(math.dist(g.pos, n["pos"]), "plant", n) for n in g.nodes
                               if n["kind"] in needed and n["regrow_ticks"] == 0]
                if candidates:
                    _, kind, entity = min(candidates, key=lambda row: (row[0], row[2]["id"]))
                    target = entity["pos"]
                    if kind == "fish":
                        nearest = min(g.fish, key=lambda f: (math.dist(g.pos, f["pos"]), f["id"]))
                        catch = (nearest["kind"] in needed and
                                 math.dist(g.pos, nearest["pos"]) <= g.t["catch_radius"] and g.catch_cd_ticks == 0)
                    else:
                        interact = math.dist(g.pos, target) <= g.t["interact_radius"] and g._at_surface()
                else:
                    target = [g.pos[0], 0]
            if target is not None and target[1] == 0 and not g._at_surface():
                target = [g.pos[0], 0]  # Surface before a long horizontal trip.
            if any(math.dist(g.pos, m["pos"]) < 6 for m in g.monsters):
                target = [g.pos[0], 0]
                catch = interact = False
        elif sim.phase == "quan":
            if c.hand:
                order = next(order for order in c.customers if order["id"] == c.hand["order_id"])
                target = next(t["pos"] for t in c.tables if t["id"] == order["table_id"])
            else:
                ready = [s for s in c.stoves if s["state"] == "ready"]
                idle = [s for s in c.stoves if s["state"] == "idle"]
                waiting = any(order["order_status"] == "reserved" for order in c.customers)
                choices = ready or (idle if waiting else [])
                if choices:
                    target = min(choices, key=lambda s: math.dist(c.pos, s["pos"]))["pos"]
            interact = target is not None and math.dist(c.pos, target) <= c.t["interact_radius"]
        else:
            for kind in ("hp", "oxygen"):
                level = sim.upgrades.get(kind, 0)
                levels = tuning["shop"]["upgrades"][kind]
                if level < len(levels) and sim.money >= levels[level]["price"]:
                    buy = kind
                    break
            shop_done = buy is None
        move = normalize([target[i] - c.pos[i] for i in range(2)]) if target is not None else (0, 0)
        if target is not None and math.dist(c.pos, target) < .08:
            move = (0, 0)
        # Pulse action buttons; each press uses LiveInputs rising-edge semantics.
        held = previous or {}
        frame = {"move": list(move), "catch": catch and not held.get("catch", False),
                 "interact": interact and not held.get("interact", False), "shop_done": shop_done, "buy": buy}
        if frame != previous:
            frames.append({"tick": session.tick, **frame})
            previous = frame
        inputs.set(frame["move"], catch=frame["catch"], interact=frame["interact"], shop_done=shop_done)
        inp = inputs.advance()
        inp.buy = buy
        rows.extend(session.step(inp))
    return session, rows, frames, collected


def main():
    PROOF.mkdir(parents=True, exist_ok=True)
    session, rows, frames, collected = run(1)
    report = {"seed": 1, "days_completed": session.sim.days_completed,
              "gather_targets": collected, "results": session.sim.results, "ticks": session.tick,
              "fixtures": "Default spawns, real movement/oxygen/decay/monsters; no teleport or injected inventory."}
    (PROOF / "progression-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (PROOF / "progression-inputs.json").write_text(json.dumps({"frames": frames}), encoding="utf-8")
    (PROOF / "progression-events.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    assert session.sim.days_completed == 5
    assert len(collected) == 5, "Not every daily target was collected; see report"
    assert all(row["seconds"] <= 180 for row in collected.values())
    # Replay exactly the saved inputs through the same backend to prove determinism.
    from chonoi.inputs import InputPlayer
    other = InteractiveSession(session.tuning, load_scenario(ROOT / "chonoi/web/day-plan.json", "day", session.tuning),
                               1, 5, json.loads((ROOT / "chonoi/web/gameplay.json").read_text()))
    player = InputPlayer(frames, BUTTONS_V11)
    replay = other.start_events()
    while not other.done and other.tick < session.tick:
        replay.extend(other.step(player.advance(other.tick)))
    assert replay == rows and other.sim.summary() == session.sim.summary()
    print("PASS: five reachable plans, real Gather/Quan/Shop and deterministic replay")


if __name__ == "__main__":
    main()
