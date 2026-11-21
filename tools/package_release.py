"""Package exact HEAD and test clean clone + extracted ZIP on the host OS."""
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
from threading import Thread
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def smoke(directory, screenshot):
    from playwright.sync_api import sync_playwright, expect
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONUTF8"] = "1"
    process = subprocess.Popen([sys.executable, "-m", "chonoi.live", "--mode", "day", "--days", "5", "--port", "0"],
                               cwd=directory, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        lines = queue.Queue()
        Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
        line = lines.get(timeout=20)
        url = re.search(r"http://[^\s]+", line).group(0)
        with urlopen(url + "state", timeout=5) as response:
            assert json.load(response)["screen"] == "menu"
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome")
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(url)
                page.get_by_role("button", name="Chơi", exact=True).click()
                page.get_by_role("button", name="Ra bến", exact=True).click()
                expect(page.locator("#world")).to_be_visible()
                page.wait_for_function("document.getElementById('portrait').naturalWidth>0")
                for name in ("gather", "ca-sau", "ba-ut", "ca-loc"):
                    assert page.request.get(url + f"art/{name}.webp").ok
                page.screenshot(path=str(screenshot), full_page=True)
                assert not errors, errors
            finally:
                browser.close()
        return {"status": "PASS", "startup": line.strip(), "os": sys.platform, "page_errors": errors}
    finally:
        process.terminate()
        process.communicate(timeout=10)


def main():
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    artifacts = ROOT / "release-artifacts"
    artifacts.mkdir(exist_ok=True)
    proof = ROOT / "docs/proof/phase-4/p4-d"
    proof.mkdir(parents=True, exist_ok=True)
    package = artifacts / f"quan-an-cho-noi-v1.0.0-{sha[:8]}.zip"
    subprocess.run(["git", "archive", "--format=zip", "--prefix=quan-an-cho-noi/", "-o", str(package), sha], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory(prefix="chonoi-release-") as temporary:
        temporary = Path(temporary)
        clone = temporary / "clone"
        subprocess.run(["git", "clone", "--no-local", str(ROOT), str(clone)], check=True, capture_output=True)
        subprocess.run(["git", "checkout", "--detach", sha], cwd=clone, check=True, capture_output=True)
        clone_result = smoke(clone, proof / "clean-clone.png")
        with zipfile.ZipFile(package) as archive:
            assert not any("/.git/" in n or "__pycache__" in n or "/.venv/" in n for n in archive.namelist())
            archive.extractall(temporary / "unzip")
        package_result = smoke(temporary / "unzip/quan-an-cho-noi", proof / "package.png")
    report = {"commit": sha, "package": package.name, "sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
              "clean_clone": clone_result, "package_test": package_result,
              "macos_linux": "NOT VERIFIED: no Linux Python/Git runtime available"}
    (proof / "package-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
