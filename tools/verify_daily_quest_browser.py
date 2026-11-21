"""Verify the real Day web adapter in Chrome; deterministic fixture clock/positions.

Run: .venv/Scripts/python tools/verify_daily_quest_browser.py
No test endpoints are added to the game. Position/clock and basket-loss fixtures
are applied in process; catches/harvests use browser keys and the actual engine.
"""
import json
import sys
from pathlib import Path
from runpy import run_path
from threading import Thread

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
scope = run_path(str(ROOT / "docs/proof/phase-2/day_fixture.py"))
Preview = scope["LiveScenesPreview"]
EVIDENCE = ROOT / "docs/proof/daily-quest"


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    now = [0.0]
    Preview.tick.__globals__["monotonic"] = lambda: now[0]
    preview = Preview(5, False)
    server = scope["create_server"](preview)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/"
    errors, checks = [], []

    def advance(ticks=1):
        now[0] += (ticks + .01) / 60
        return preview.snapshot()

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome")
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

            def start(scenario=None):
                preview.__init__(5, False, scenario)
                page.goto(url)
                page.get_by_role("button", name="Chơi", exact=True).click()
                expect(page.locator(".ingredient-goal")).to_be_visible()
                page.get_by_role("button", name="Ra bến", exact=True).click()
                expect(page.locator("#daily-quest")).to_be_visible()
                page.locator("#playfield").focus()

            def row(kind):
                return page.locator(f'#quest-items [data-kind="{kind}"]')

            def press(key, field):
                page.locator("#playfield").focus()
                with page.expect_response(lambda res: res.url == url + "input" and res.ok
                                          and res.request.post_data_json.get(field) is True):
                    page.keyboard.down(key)
                advance()
                with page.expect_response(lambda res: res.url == url + "input" and res.ok
                                          and res.request.post_data_json.get(field) is False):
                    page.keyboard.up(key)
                advance()

            start()
            expect(page.locator("#quest-title")).to_have_text("Nhiệm vụ ngày 1")
            expect(row("ca_loc")).to_contain_text("0/3")
            expect(row("bong_sung")).to_contain_text("0/6")
            # The quest is outside the canvas and metrics: no entity can be covered.
            boxes = page.locator("#daily-quest, #world, .hud").evaluate_all(
                "els => els.map(el => {const r=el.getBoundingClientRect();return [r.x,r.y,r.right,r.bottom]})")
            quest, hud, world = boxes
            assert quest[2] <= world[0] and quest[2] <= hud[0], boxes
            assert page.evaluate("document.documentElement.scrollWidth === innerWidth")
            page.screenshot(path=str(EVIDENCE / "day1-empty-1280x720.png"))
            sim = preview.game.session.sim
            fish = next(f for f in sim.fish if f["kind"] == "ca_loc")
            sim.pos = list(fish["pos"])
            press("Space", "catch")
            expect(row("ca_loc")).to_contain_text("1/3")
            sim.pos = list(next(n for n in sim.nodes if n["kind"] == "bong_sung")["pos"])
            press("e", "interact")
            expect(row("bong_sung")).to_contain_text("1/6")
            page.screenshot(path=str(EVIDENCE / "day1-collected-1280x720.png"))
            checks.append("Day 1: default targets, real Space catch and E harvest, no HUD overlap PASS")

            # Seeded basket fixture; the final flower is harvested by the browser.
            kinds = ["ca_loc"] * 3 + ["bong_sung"] * 5
            items = [{"id": f"I{i+1}", "kind": kind, "fresh": 100} for i, kind in enumerate(kinds)]
            start({"gather": {"hold": items}})
            expect(row("ca_loc")).to_contain_text("3/3")
            expect(row("bong_sung")).to_contain_text("5/6")
            sim = preview.game.session.sim
            sim.pos = list(next(n for n in sim.nodes if n["kind"] == "bong_sung")["pos"])
            page.evaluate("""() => {window.questChanges=0;
                new MutationObserver(() => window.questChanges++).observe(
                    document.getElementById('quest-status'), {childList:true, subtree:true});} """)
            press("e", "interact")
            expect(page.locator("#quest-status")).to_have_text("Đã đủ nguyên liệu cho thực đơn hôm nay!")
            expect(page.get_by_label("Đạt mục tiêu")).to_have_count(2)
            advance(60)
            expect(page.locator("#daily-quest")).to_have_attribute("data-complete", "true")
            assert preview.screen == "gather" and preview.money == 0
            assert page.evaluate("window.questChanges") == 1
            page.screenshot(path=str(EVIDENCE / "day1-complete-1280x720.png"))
            # Simulate a lost physical item, including the legacy internal adapter.
            sim.hold_items.pop()
            sim.hold.pop()
            expect(row("bong_sung")).to_contain_text("5/6")
            expect(page.locator("#daily-quest")).to_have_attribute("data-complete", "false")
            checks.append("Prefilled basket, completion without reward/transition, single notice, loss reverses completion PASS")

            start({"day": {"day_plan": [{"day": 1, "dishes": {"ca_loc_nuong_trui": 1}}]},
                   "gather": {"hold": [{"id": "I1", "kind": "ca_loc", "fresh": 30},
                                       {"id": "I2", "kind": "ca_loc", "fresh": 29.99}]}})
            expect(row("ca_loc")).to_contain_text("1/1")
            expect(row("ca_loc")).to_contain_text("Đang giữ 2 · Ươn 1")
            advance()
            expect(row("ca_loc")).to_contain_text("0/1")
            expect(row("ca_loc")).to_contain_text("Đang giữ 2 · Ươn 2")
            expect(page.locator("#quest-items li")).to_have_count(1)
            checks.append("Custom plan, exact fresh=30 before/after real decay, spoiled items retained PASS")

            start()
            for day in range(2, 6):
                # Jump only the scene boundary; use the actual shop_done and continue HTTP actions.
                preview.set_screen("shop")
                expect(page.get_by_role("button", name="Sang ngày kế tiếp")).to_be_visible()
                page.get_by_role("button", name="Sang ngày kế tiếp").click()
                page.get_by_role("button", name="Ra bến", exact=True).click()
                expect(page.locator("#quest-title")).to_have_text(f"Nhiệm vụ ngày {day}")
                targets = preview.plans[day]["ingredients"]
                expect(page.locator("#quest-items li")).to_have_count(len(targets))
                for kind, count in targets.items():
                    expect(row(kind)).to_contain_text(f"0/{count}")
                if day == 2:
                    sim = preview.game.session.sim
                    fish = next(f for f in sim.fish if f["kind"] == "ca_linh")
                    sim.pos = list(fish["pos"])
                    press("Space", "catch")
                    expect(row("ca_linh")).to_contain_text("3/6")
                assert page.locator("#daily-quest").evaluate("el => el.getBoundingClientRect().bottom <= innerHeight")
                page.screenshot(path=str(EVIDENCE / f"day{day}-1280x720.png"))
            checks.append("Days 2–5: backend plans and clean baskets; ca_linh school adds three PASS")

            # Standalone mode is deliberately served as a snapshot fixture through /state.
            standalone = json.loads(scope["LiveGame"]("gather", scope["TUNING"], {}, 1).state_json())
            page.route("**/state", lambda route: route.fulfill(json=standalone))
            expect(page.locator("#quest-title")).to_have_text("Chế độ thu thập tự do")
            expect(page.locator("#quest-items li")).to_have_count(0)
            assert not errors, errors
            checks.append("Standalone free collection and Chrome console PASS")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        report = {"checks": checks, "console_errors": errors,
                  "fixtures": "Clock/positions, seeded inventory and physical item loss; browser actions use real HTTP and Gather.",
                  "viewport": "1280x720", "url": url}
        (EVIDENCE / "browser-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
