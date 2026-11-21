"""Focused Chrome verification of unlocks and spawn counts over five real Day transitions."""
import json
from pathlib import Path
from runpy import run_path
import sys
from threading import Thread

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chonoi.interactive_web import InteractiveDayWeb
from chonoi.scenario import load_scenario


def main():
    scope = run_path(str(ROOT / "docs/proof/phase-2/day_fixture.py"))
    tuning = scope["TUNING"]
    config = json.loads((ROOT / "chonoi/web/gameplay.json").read_text())
    scenario = load_scenario(ROOT / "chonoi/web/day-plan.json", "day", tuning)
    proof = ROOT / "docs/proof/menu-unlock"
    proof.mkdir(parents=True, exist_ok=True)
    clock = [0.0]
    InteractiveDayWeb._reset_clock.__globals__["monotonic"] = lambda: clock[0]
    web = InteractiveDayWeb(5, False, tuning=tuning, scenario=scenario, config=config)
    server = scope["create_server"](web)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/"
    errors, days = [], []

    def advance():
        with server.preview_lock:
            clock[0] += 1.1 / tuning["tick_hz"]
            web.update_scene()

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome")
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.goto(url)
            page.get_by_role("button", name="Chơi", exact=True).click()
            for day in range(1, 6):
                if day > 1:
                    expect(page.locator("#flow-content")).to_contain_text("Đã mở khóa món mới!")
                state = page.request.get(url + "state").json()
                assert len(state["unlocked_menu"]) == day + 1
                expect(page.locator(".unlocked-menu:visible")).to_be_visible()
                page.screenshot(path=str(proof / f"day{day}-unlock.png"), full_page=True)
                page.get_by_role("button", name="Ra bến", exact=True).click()
                expect(page.locator("#quest-title")).to_have_text(f"Nhiệm vụ ngày {day}")
                state = page.request.get(url + "state").json()
                snap = state["snapshot"]
                fish, plants = snap["fish"], snap["nodes"]
                assert len(fish) == tuning["gather"]["fish_initial"]
                assert len(plants) == len(tuning["gather"]["nodes"])
                if day == 1:
                    assert {f["kind"] for f in fish} == {"ca_loc"}
                    assert {n["kind"] for n in plants} == {"bong_sung"}
                    page.screenshot(path=str(proof / "day1-only-usable-resources.png"))
                days.append({"day": day, "menu": state["unlocked_menu"],
                             "fish_count": len(fish), "plant_count": len(plants),
                             "fish_kinds": sorted({f["kind"] for f in fish}),
                             "plant_kinds": sorted({n["kind"] for n in plants}),
                             "monster_count": len(snap["monsters"])})
                # Dock through the public input API. No inventory or phase is injected.
                page.request.post(url + "input", data={"interact": True})
                advance()
                page.request.post(url + "input", data={"interact": False})
                page.get_by_role("button", name="Mở quán", exact=True).click()
                expect(page.locator(".unlocked-menu:visible")).to_be_visible()
                assert {r["dish_id"] for r in state["unlocked_menu"]} == set(web.session.sim.current.menu)
                advance()
                page.get_by_role("button", name="Ghé cửa hàng", exact=True).click()
                page.get_by_role("button", name="Rời cửa hàng", exact=True).click()
            expect(page.locator("#flow-title")).to_have_text("Kết thúc chuyến chợ")
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        report = {"days": days, "console_errors": errors,
                  "fixtures": "Controlled backend clock; public HTTP dock/action, real DaySim/Shop transitions; no fake spawns or injected inventory."}
        (proof / "browser-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
