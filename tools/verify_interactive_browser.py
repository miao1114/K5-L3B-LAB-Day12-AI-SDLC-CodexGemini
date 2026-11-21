"""Chrome UI over the real interactive HTTP adapter; fixtures are named in the report."""
import json
from pathlib import Path
from runpy import run_path
import sys
from threading import Thread

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chonoi.inputs import BUTTONS_V11, InputPlayer
from chonoi.interactive_web import InteractiveDayWeb
from chonoi.scenario import load_scenario

SCOPE = run_path(str(ROOT / "docs/proof/phase-2/day_fixture.py"))
TUNING = SCOPE["TUNING"]
CONFIG = json.loads((ROOT / "chonoi/web/gameplay.json").read_text())
PROOF = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/proof/gameplay-enhancement"


def main():
    PROOF.mkdir(parents=True, exist_ok=True)
    now = [0.0]
    InteractiveDayWeb._reset_clock.__globals__["monotonic"] = lambda: now[0]
    base = load_scenario(ROOT / "chonoi/web/day-plan.json", "day", TUNING)
    web = InteractiveDayWeb(5, False, tuning=TUNING, scenario=base, config=CONFIG)
    server = SCOPE["create_server"](web)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/"
    checks, errors = [], []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome")
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

            def start(scenario):
                with server.preview_lock:
                    web.__init__(5, False, tuning=TUNING, scenario=scenario, config=CONFIG)
                page.goto(url)
                page.get_by_role("button", name="Chơi", exact=True).click()
                page.get_by_role("button", name="Ra bến", exact=True).click()
                expect(page.locator("#daily-quest")).to_be_visible()

            def advance(ticks=1):
                with server.preview_lock:
                    now[0] += (ticks + .01) / TUNING["tick_hz"]
                    web.update_scene()

            def press(key, field):
                page.locator("#playfield").focus()
                with page.expect_response(lambda r: r.url == url + "input" and r.ok
                                          and r.request.post_data_json.get(field) is True):
                    page.keyboard.down(key)
                advance()
                with page.expect_response(lambda r: r.url == url + "input" and r.ok
                                          and r.request.post_data_json.get(field) is False):
                    page.keyboard.up(key)
                advance()

            scenario = json.loads(json.dumps(base))
            scenario["day"].update(money=400, earned=400)
            scenario["gather"] = {"random_fish": False, "monsters": [], "fish": [
                {"id": "F1", "kind": "ca_loc", "pos": [20, 10]},
                {"id": "F2", "kind": "ca_loc", "pos": [20, 10]}]}
            start(scenario)
            with server.preview_lock:
                # Fish-stack fixture now belongs to Day 4, when ca_linh unlocks.
                sim = web.session.sim
                for fish in sim.gather_scenario["fish"]:
                    fish["kind"] = "ca_linh"
                sim.day = 4
                sim._start_day()
                web.session.sim.current.pos = [20, 10]
            expect(page.locator("#quest-title")).to_have_text("Nhiệm vụ ngày 4")
            press("Space", "catch")
            expect(page.locator("#hold-title")).to_contain_text("1/12 ô · 3 nguyên liệu")
            expect(page.locator(".stack-quantity")).to_have_text("×3")
            advance(31)
            press("Space", "catch")
            expect(page.locator("#hold-title")).to_contain_text("2/12 ô · 6 nguyên liệu")
            expect(page.locator(".stack-quantity")).to_have_count(2)
            page.screenshot(path=str(PROOF / "fish-stacks-1280x720.png"))
            with server.preview_lock:
                web.session.sim.current.pos = TUNING["gather"]["dock_pos"][:]
            press("e", "interact")
            page.get_by_role("button", name="Mở quán", exact=True).click()
            advance()
            expect(page.locator("#flow-content")).to_contain_text("Đã hết nguyên liệu có thể chế biến")
            expect(page.locator("#flow-content")).to_contain_text("6 con (2 đàn)")
            assert web.session.sim.results[-1]["remaining"] == {"ca_linh": 6}
            page.screenshot(path=str(PROOF / "day-result-real-counts.png"), full_page=True)
            page.get_by_role("button", name="Ghé cửa hàng", exact=True).click()
            page.get_by_role("button", name="Mua Bình oxy cấp 1", exact=True).click()
            expect(page.locator("#flow-content")).to_contain_text("Đã mua nâng cấp")
            assert web.session.sim.money == 200
            page.screenshot(path=str(PROOF / "real-shop.png"), full_page=True)
            page.get_by_role("button", name="Rời cửa hàng", exact=True).click()
            page.get_by_role("button", name="Ra bến", exact=True).click()
            expect(page.locator("#quest-title")).to_have_text("Nhiệm vụ ngày 5")
            expect(page.locator("#hold-title")).to_contain_text("0/12 ô")
            checks.append("Day 4 Space catches two real schools: 6 items/2 slots; true counts in DayResult; real Shop purchase and Day 5 PASS")

            scenario = json.loads(json.dumps(base))
            scenario["gather"] = {"hold": [{"id": "I1", "kind": "bong_sung", "fresh": 100}]}
            start(scenario)
            press("e", "interact")
            page.get_by_role("button", name="Mở quán", exact=True).click()
            advance()
            expect(page.locator("#flow-content")).to_contain_text("Đã hết nguyên liệu có thể chế biến")
            assert web.session.sim.results[-1]["remaining"] == {"bong_sung": 1}
            assert web.session.sim.results[-1]["money"] == 0
            page.screenshot(path=str(PROOF / "one-flower-auto-end.png"), full_page=True)
            checks.append("Mandatory Day 1 one-flower stock closes once, preserves leftover, no fake payment PASS")

            # Replay proven movement/input frames through the backend; use actual browser
            # buttons for intro/result/shop screens. No scene skips or fake results.
            start(base)
            frames = json.loads((PROOF / "progression-inputs.json").read_text())["frames"]
            player = InputPlayer(frames, BUTTONS_V11)
            while web.screen != "summary":
                if web.screen == "evening_intro":
                    page.get_by_role("button", name="Mở quán", exact=True).click()
                elif web.screen == "day_result":
                    day = web.session.sim.day
                    expect(page.locator("#flow-title")).to_have_text("Kết quả trong ngày")
                    page.screenshot(path=str(PROOF / f"replay-day{day}-result.png"), full_page=True)
                    page.get_by_role("button", name="Ghé cửa hàng", exact=True).click()
                elif web.screen == "day_intro":
                    page.get_by_role("button", name="Ra bến", exact=True).click()
                    expect(page.locator("#quest-title")).to_have_text(f"Nhiệm vụ ngày {web.session.sim.day}")
                elif web.screen == "shop":
                    inp = player.advance(web.session.tick)
                    if inp.buy:
                        label = {"hp": "Máu", "oxygen": "Bình oxy"}[inp.buy]
                        level = web.session.sim.upgrades.get(inp.buy, 0) + 1
                        page.get_by_role("button", name=f"Mua {label} cấp {level}", exact=True).click()
                    else:
                        assert inp.pressed("shop_done")
                        page.get_by_role("button", name="Rời cửa hàng", exact=True).click()
                else:
                    with server.preview_lock:
                        for _ in range(120):
                            web._step(player.advance(web.session.tick))
                            if web.screen not in ("gather", "quan"):
                                break
            expect(page.locator("#flow-title")).to_have_text("Kết thúc chuyến chợ")
            expected = json.loads((PROOF / "progression-report.json").read_text())
            assert web.session.sim.results == expected["results"]
            assert web.session.sim.days_completed == 5
            page.screenshot(path=str(PROOF / "five-day-summary.png"), full_page=True)
            assert not errors, errors
            checks.append("Five-day backend input replay with real HTTP intro/result/Shop actions, matching statistics and clean Chrome console PASS")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        report = {"checks": checks, "console_errors": errors, "viewport": "1280x720",
                  "fixtures": "Named fish/position and one-flower fixtures for UI edges; full five-day replay uses default spawns and saved real movement inputs."}
        report_name = "integration-browser-report.json" if len(sys.argv) > 1 else "browser-report.json"
        (PROOF / report_name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
