"""Focused UI/logic verification in Chrome at 1280x720; no gameplay changes.

Run: python3 tools/verify_p4_c.py
Snapshots derive from real engines; /state fixtures exercise warning boundaries.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chonoi.contract import load_contract
from chonoi.live import LiveGame, LiveServer

PROOF = ROOT / "docs/proof/phase-4/p4-c"


def contrast(a, b):
    def lum(color):
        values = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return sum(v * w for v, w in zip(values, (.2126, .7152, .0722)))
    l1, l2 = sorted((lum(a), lum(b)))
    return (l2 + .05) / (l1 + .05)


class WarningsAccessibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        PROOF.mkdir(parents=True, exist_ok=True)
        tuning = load_contract()["tuning"]
        cls.server = LiveServer(LiveGame("gather", tuning, {}, 1), port=0)
        cls.server.start()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel="chrome")
        cls.gather = json.loads(LiveGame("gather", tuning, {"player": {"pos": [20, 10]}, "monsters": []}, 1).state_json())
        stock = [{"id": f"I{i}", "kind": "ca_loc", "fresh": 100} for i in (1, 2)]
        customers = [
            {"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "reserved": ["I1"], "patience_ticks_left": 3000},
            {"id": "C2", "table_id": "T2", "dish_id": "ca_loc_nuong_trui", "reserved": ["I2"], "patience_ticks_left": 600},
            {"id": "C3", "table_id": "T3", "dish_id": "ca_loc_nuong_trui", "state": "eating", "order_status": "served",
             "reserved": [], "eat_ticks_left": 200, "base_price": 59, "tip": 11},
        ]
        cls.quan = json.loads(LiveGame("quan", tuning, {"customers": customers}, 1, inventory=stock).state_json())

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.stop()

    def setUp(self):
        self.state = deepcopy(self.gather)
        self.errors = []
        self.context = self.browser.new_context(viewport={"width": 1280, "height": 720})
        self.page = self.context.new_page()
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        self.page.route("**/state", lambda r: r.fulfill(json=self.state))
        self.page.add_init_script("""window.barFills=[];
            const fill=CanvasRenderingContext2D.prototype.fill;
            CanvasRenderingContext2D.prototype.fill=function(...args){
                if(this.canvas.id==='world')window.barFills.push(this.fillStyle);
                if(window.barFills.length>5000)window.barFills.splice(0,1000);
                return fill.apply(this,args);};""")
        self.page.goto(self.server.url)
        expect(self.page.locator("#hold-title")).to_be_visible()

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def warning(self, kind):
        return self.page.locator(f'[data-warning="{kind}"]')

    def monster(self, pos=(25, 10), state="patrol", ident="M1"):
        return {"id": ident, "kind": "ca_sau", "pos": list(pos), "state": state}

    def test_monster_near_far_multiple_inactive_and_world_coordinates(self):
        self.state["monsters"] = [self.monster(), self.monster((24, 10), ident="M2")]
        expect(self.warning("monster")).to_have_count(1)
        self.state["monsters"] = [self.monster((80, 25))]
        expect(self.warning("monster")).to_have_count(0)
        self.state["monsters"] = [self.monster(state=s) for s in ("dead", "inactive", "defeated", "stunned")]
        expect(self.warning("monster")).to_have_count(0)
        self.state["meta"]["monsters"]["species"]["ca_sau"]["detect_radius"] = 4
        self.state["monsters"] = [self.monster((25, 10))]
        expect(self.warning("monster")).to_have_count(0)
        self.state["monsters"][0]["pos"] = [24, 10]
        expect(self.warning("monster")).to_have_count(1)

    def test_oxygen_boundary_recovery_surface_and_upgrades(self):
        p = self.state["player"]
        p["oxygen_ticks"] = 451
        expect(self.warning("oxygen")).to_have_count(0)
        p["oxygen_ticks"] = 450
        expect(self.warning("oxygen")).to_be_visible()
        p["oxygen_ticks"] = 451
        expect(self.warning("oxygen")).to_have_count(0)
        p.update(oxygen_max_ticks=2700, oxygen_ticks=675)
        expect(self.warning("oxygen")).to_be_visible()
        p["at_surface"] = True
        expect(self.warning("oxygen")).to_have_count(0)
        p.update(at_surface=False, hp=0)
        expect(self.warning("oxygen")).to_have_count(0)

    def test_customer_priority_eating_departure_and_threshold(self):
        self.state = deepcopy(self.quan)
        expect(self.warning("customer")).to_contain_text("BÀN T2 SẮP BỎ ĐI!")
        self.state["customers"][0]["patience_ticks_left"] = 100
        expect(self.warning("customer")).to_contain_text("BÀN T1 SẮP BỎ ĐI!")
        self.state["customers"] = [self.state["customers"][2]]
        expect(self.warning("customer")).to_have_count(0)
        self.state["customers"] = []
        expect(self.warning("customer")).to_have_count(0)
        c = deepcopy(self.quan["customers"][0])
        c["patience_ticks_left"] = 720
        self.state["customers"] = [c]
        expect(self.warning("customer")).to_be_visible()
        c["patience_ticks_left"] = 721
        expect(self.warning("customer")).to_have_count(0)

    def test_simultaneous_warnings_do_not_overlap_canvas_or_hud(self):
        self.state["monsters"] = [self.monster()]
        self.state["player"]["oxygen_ticks"] = 450
        expect(self.page.locator(".warning")).to_have_count(2)
        self.assertEqual(self.page.locator(".warning").first.get_attribute("data-warning"), "oxygen")
        boxes = self.page.locator(".hud, #warnings, #world").evaluate_all(
            "els=>els.map(el=>{const r=el.getBoundingClientRect();return [r.top,r.bottom]})")
        self.assertLessEqual(boxes[0][1], boxes[1][0])
        self.assertLessEqual(boxes[1][1], boxes[2][0])
        self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth===innerWidth"))
        self.assertTrue(self.page.locator("#metrics").is_visible())

    def test_scene_pause_resume_preference_reload_and_toggle(self):
        self.state["player"]["oxygen_ticks"] = 450
        expect(self.warning("oxygen")).to_be_visible()
        button = self.page.locator("#high-contrast")
        button.click()
        expect(button).to_have_attribute("aria-pressed", "true")
        self.state = dict(mode="day", day=1, days=5, screen="quan", paused=True,
                          snapshot=deepcopy(self.quan), events=[])
        expect(self.warning("oxygen")).to_have_count(0)
        expect(self.warning("customer")).to_be_visible()
        expect(button).to_have_attribute("aria-pressed", "true")
        self.state["paused"] = False
        expect(self.warning("customer")).to_be_visible()
        self.page.reload()
        expect(button).to_have_attribute("aria-pressed", "true")
        for _ in range(4):
            button.click()
        expect(button).to_have_attribute("aria-pressed", "true")
        button.click()
        expect(button).to_have_text("Tương phản cao: Tắt")
        self.state = dict(mode="day", day=1, days=5, screen="day_result", events=[])
        expect(self.page.locator("#warnings")).to_be_hidden()

    def test_storage_failure_and_reduced_motion_are_safe(self):
        self.page.add_init_script("""Storage.prototype.getItem=function(){throw new Error('blocked')};
            Storage.prototype.setItem=function(){throw new Error('blocked')};""")
        self.page.emulate_media(reduced_motion="reduce")
        self.page.reload()
        self.page.locator("#high-contrast").click()
        expect(self.page.locator("#high-contrast")).to_have_attribute("aria-pressed", "true")

    def test_pure_logic_does_not_mutate_snapshot(self):
        before = deepcopy(self.quan)
        self.page.evaluate("s=>warningsFor(s)", self.quan)
        self.assertEqual(self.quan, before)
        self.assertEqual(self.page.evaluate("s=>{const b=JSON.stringify(s);warningsFor(s);return b===JSON.stringify(s)}", self.quan), True)

    def test_evidence_and_canvas_contrast_ratios(self):
        ratios = {"normal_text": contrast("#fff4dc", "#402008"), "high_text": contrast("#ffffff", "#000000"),
                  "border": contrast("#ffff00", "#000000")}
        for kind in ("monster", "oxygen", "customer"):
            self.state = deepcopy(self.quan if kind == "customer" else self.gather)
            if kind == "monster":
                self.state["monsters"] = [self.monster()]
            elif kind == "oxygen":
                self.state["player"]["oxygen_ticks"] = 450
            expect(self.warning(kind)).to_be_visible()
            self.page.evaluate("applyContrast(false)")
            self.page.screenshot(path=str(PROOF / f"warning-{kind}-normal.png"), full_page=True)
            self.page.locator("#high-contrast").click()
            expect(self.page.locator("html")).to_have_attribute("data-high-contrast", "true")
            self.page.screenshot(path=str(PROOF / f"warning-{kind}-contrast.png"), full_page=True)
        self.page.wait_for_function("window.barFills.includes('#ff6b6b')")
        palette = self.page.evaluate("customerBarContrastStyle")
        for kind, style in palette.items():
            ratios["canvas_" + kind] = contrast(style["fill"], "#000000")
            self.assertGreaterEqual(ratios["canvas_" + kind], 3)
        self.assertGreaterEqual(ratios["normal_text"], 4.5)
        self.assertGreaterEqual(ratios["high_text"], 4.5)
        self.assertEqual(self.warning("customer").evaluate("el=>getComputedStyle(el).backgroundColor"), "rgb(0, 0, 0)")
        (PROOF / "contrast-ratios.json").write_text(json.dumps(ratios, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main(verbosity=2)
