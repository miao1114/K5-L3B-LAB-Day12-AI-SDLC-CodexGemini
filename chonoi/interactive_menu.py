"""One unlock policy for the web menu, targets and resource pools only."""
from copy import deepcopy
import json
from math import ceil
from pathlib import Path

from .day_config import day_plans
from .errors import BadInput


def web_scenario(tuning, scenario):
    """Partial scenario overrides inherit web plans, never the locked official plans."""
    result = deepcopy(scenario)
    initial = result.setdefault("day", {})
    defaults = json.loads((Path(__file__).parent / "web/day-plan.json").read_text(encoding="utf-8"))
    preset = {**tuning, "day_plan": defaults["day"]["day_plan"]}
    initial["day_plan"] = list(day_plans(preset, initial.get("day_plan", ())).values())
    return result


def unlocked_menu(tuning, config, day):
    opened, new = [], []
    seen = set()
    entries = config["menu_unlocks"]
    if [entry["day"] for entry in entries] != list(range(1, 6)):
        raise BadInput("web menu_unlocks cần đủ ngày 1–5 theo thứ tự")
    for entry in entries:
        for dish in entry["dishes"]:
            if dish not in tuning["menu"] or dish in seen:
                raise BadInput(f"món mở khóa không hợp lệ hoặc trùng: {dish}")
            seen.add(dish)
            if entry["day"] <= day:
                opened.append(dish)
            if entry["day"] == day:
                new.append(dish)
    if seen != set(tuning["menu"]):
        raise BadInput("web menu_unlocks phải mở đủ menu lõi")
    return tuple(sorted(opened)), tuple(sorted(new))


def resource_tuning(tuning, dishes):
    """Keep entity counts/positions/timers; redistribute kinds without filtering entities."""
    allowed = {kind for dish in dishes for kind in tuning["menu"][dish]["recipe"]}
    gather = deepcopy(tuning["gather"])
    for key in ("fish_weights", "fish_depths", "fish_spawn_depths"):
        gather[key] = {kind: value for kind, value in gather[key].items() if kind in allowed}
    plants = sorted({node["kind"] for node in gather["nodes"]} & allowed)
    if not gather["fish_weights"] or not plants:
        raise BadInput("menu web cần có nguồn cá và cây hợp lệ")
    for index, node in enumerate(gather["nodes"]):
        node["kind"] = plants[index % len(plants)]
    return {**tuning, "gather": gather}, allowed


def target_slots(tuning, ingredients):
    """Account for whole-school yields, including the unstacked ca_keo surplus."""
    total = 0
    for kind, count in ingredients.items():
        amount = tuning["gather"]["fish_yield"].get(kind, 1)
        schools = ceil(count / amount)
        total += schools if kind == "ca_linh" else schools * amount
    return total
